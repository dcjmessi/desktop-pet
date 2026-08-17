"""Local WebSocket relay and encrypted invite-code client sessions.

The relay sees room ids and control messages only. Chat/action payloads are
Fernet-encrypted client-to-client before they enter the relay.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import secrets
import threading
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from PySide6.QtCore import QThread, Signal
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect
from websockets.sync.server import ServerConnection, serve

MAX_PACKET = 256 * 1024


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class Invite:
    endpoint: str
    room_id: str
    key: str

    def encode(self) -> str:
        payload = {"v": 1, "u": self.endpoint, "r": self.room_id, "k": self.key}
        return "PET1-" + _b64(json.dumps(payload, separators=(",", ":")).encode())

    @classmethod
    def decode(cls, code: str) -> "Invite":
        raw = code.strip().replace(" ", "")
        if not raw.startswith("PET1-"):
            raise ValueError("邀请码格式不正确")
        try:
            data = json.loads(_unb64(raw[5:]).decode("utf-8"))
            endpoint = str(data["u"]).rstrip("/")
            room_id = str(data["r"])
            key = str(data["k"])
        except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("邀请码无法解析") from exc
        if not endpoint.startswith(("ws://", "wss://")):
            raise ValueError("邀请码中的中继地址无效")
        if len(room_id) < 12 or len(key) < 32:
            raise ValueError("邀请码不完整")
        return cls(endpoint, room_id, key)

    @classmethod
    def create(cls, endpoint: str) -> "Invite":
        endpoint = endpoint.strip().rstrip("/")
        if endpoint.startswith("http://"):
            endpoint = "ws://" + endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = "wss://" + endpoint[8:]
        if not endpoint.startswith(("ws://", "wss://")):
            raise ValueError("请输入花生壳 HTTP/HTTPS 映射地址")
        return cls(endpoint, _b64(secrets.token_bytes(12)), Fernet.generate_key().decode())


class LocalRelay:
    """Tiny two-person relay server to expose through 花生壳 HTTP/HTTPS mapping."""

    def __init__(self, port: int = 38475) -> None:
        self.port = int(port)
        self._thread: threading.Thread | None = None
        self._server = None
        self._rooms: dict[str, list[ServerConnection]] = {}
        self._identities: dict[ServerConnection, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error: Exception | None = None

    def ensure_running(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="desktop-pet-relay", daemon=True)
        self._thread.start()
        if not self._ready.wait(3):
            raise RuntimeError("本机中继启动超时")
        if self._error:
            raise RuntimeError(f"本机中继启动失败：{self._error}")

    def _run(self) -> None:
        try:
            self._server = serve(self._handler, "0.0.0.0", self.port, max_size=MAX_PACKET)
            self._ready.set()
            self._server.serve_forever()
        except Exception as exc:
            self._error = exc
            self._ready.set()

    def _handler(self, websocket: ServerConnection) -> None:
        room_id: str | None = None
        try:
            first = websocket.recv(timeout=20)
            if not isinstance(first, str):
                return
            hello = json.loads(first)
            role = hello.get("type")
            requested = str(hello.get("room") or "")
            identity = hello.get("identity")
            if role not in {"create", "join"} or len(requested) < 12 or not isinstance(identity, dict):
                websocket.send(json.dumps({"type": "error", "message": "无效请求"}))
                return
            room_id = requested
            with self._lock:
                peers = self._rooms.setdefault(room_id, [])
                if role == "create":
                    if peers:
                        websocket.send(json.dumps({"type": "error", "message": "房间已存在"}))
                        return
                    peers.append(websocket)
                    self._identities[websocket] = identity
                    websocket.send(json.dumps({"type": "created"}))
                else:
                    if len(peers) != 1:
                        websocket.send(json.dumps({"type": "error", "message": "邀请码无效、已过期或房间已满"}))
                        return
                    host = peers[0]
                    peers.append(websocket)
                    self._identities[websocket] = identity
                    host.send(json.dumps({"type": "peer", "identity": identity}))
                    websocket.send(json.dumps({"type": "joined", "identity": self._identities[host]}, ensure_ascii=False))
            for message in websocket:
                if not isinstance(message, bytes) or len(message) > MAX_PACKET:
                    continue
                with self._lock:
                    targets = [peer for peer in self._rooms.get(room_id, []) if peer is not websocket]
                for peer in targets:
                    try:
                        peer.send(message)
                    except ConnectionClosed:
                        pass
        except (ConnectionClosed, TimeoutError, json.JSONDecodeError):
            pass
        finally:
            if room_id:
                with self._lock:
                    peers = self._rooms.get(room_id, [])
                    if websocket in peers:
                        peers.remove(websocket)
                    self._identities.pop(websocket, None)
                    if not peers:
                        self._rooms.pop(room_id, None)
                    else:
                        for peer in peers:
                            try:
                                peer.send(json.dumps({"type": "left"}))
                            except ConnectionClosed:
                                pass


class RelaySession(QThread):
    status_changed = Signal(str)
    connected = Signal(object)
    packet_received = Signal(object)
    disconnected = Signal(str)

    def __init__(self, invite: Invite, identity: dict[str, Any], creating: bool) -> None:
        super().__init__()
        self.invite = invite
        self.identity = identity
        self.creating = creating
        self._outgoing: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._socket = None
        self._cipher = Fernet(invite.key.encode())

    def send_packet(self, packet: dict[str, Any]) -> None:
        if not self._stop.is_set():
            self._outgoing.put(dict(packet))

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass

    def run(self) -> None:
        reason = "联机已断开"
        try:
            self.status_changed.emit("正在连接邀请服务器…")
            with connect(self.invite.endpoint, open_timeout=12, max_size=MAX_PACKET) as websocket:
                self._socket = websocket
                websocket.send(json.dumps({
                    "type": "create" if self.creating else "join",
                    "room": self.invite.room_id,
                    "identity": self.identity,
                }, ensure_ascii=False))
                while not self._stop.is_set():
                    while True:
                        try:
                            packet = self._outgoing.get_nowait()
                        except queue.Empty:
                            break
                        websocket.send(self._cipher.encrypt(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode()))
                    try:
                        incoming = websocket.recv(timeout=0.1)
                    except TimeoutError:
                        continue
                    if isinstance(incoming, str):
                        control = json.loads(incoming)
                        kind = control.get("type")
                        if kind == "created":
                            self.status_changed.emit("邀请码已创建，等待好友加入…")
                        elif kind in {"peer", "joined"}:
                            peer = control.get("identity")
                            if not isinstance(peer, dict):
                                raise ValueError("对方宠物信息无效")
                            self.connected.emit(peer)
                            self.status_changed.emit("已与好友宠物加密联机")
                        elif kind == "left":
                            reason = "对方已离开"
                            break
                        elif kind == "error":
                            raise ValueError(str(control.get("message") or "邀请码连接失败"))
                    elif isinstance(incoming, bytes):
                        try:
                            packet = json.loads(self._cipher.decrypt(incoming).decode("utf-8"))
                        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
                            raise ValueError("收到无效或被篡改的联机数据") from exc
                        if isinstance(packet, dict):
                            self.packet_received.emit(packet)
        except Exception as exc:
            if not self._stop.is_set():
                reason = f"连接失败：{exc}"
        finally:
            self._socket = None
            self.disconnected.emit(reason)
