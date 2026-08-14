"""Encrypted one-to-one desktop-pet connection over a direct TCP socket."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import queue
import select
import socket
import struct
import threading
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from PySide6.QtCore import QThread, Signal

PROTOCOL_VERSION = 1
MAX_PACKET = 256 * 1024


class PeerSession(QThread):
    status_changed = Signal(str)
    connected = Signal(object)
    packet_received = Signal(object)
    disconnected = Signal(str)

    def __init__(
        self,
        mode: str,
        host: str,
        port: int,
        password: str,
        identity: dict[str, Any],
    ) -> None:
        super().__init__()
        if mode not in {"host", "client"}:
            raise ValueError("mode must be host or client")
        self.mode = mode
        self.host = host
        self.port = int(port)
        self.password = password
        self.identity = identity
        self._outgoing: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop_event = threading.Event()
        self._socket: socket.socket | None = None
        self._listener: socket.socket | None = None

    def send_packet(self, packet: dict[str, Any]) -> None:
        if not self._stop_event.is_set():
            self._outgoing.put(dict(packet))

    def stop(self) -> None:
        self._stop_event.set()
        for sock in (self._socket, self._listener):
            if sock is None:
                continue
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def run(self) -> None:
        reason = "连接已断开"
        try:
            if self.mode == "host":
                conn, cipher, peer = self._accept_peer()
            else:
                conn, cipher, peer = self._connect_peer()
            self._socket = conn
            self.connected.emit(peer)
            self.status_changed.emit("已建立端到端加密连接")
            reason = self._message_loop(conn, cipher)
        except (OSError, ValueError, InvalidToken, json.JSONDecodeError) as exc:
            if not self._stop_event.is_set():
                reason = f"连接失败：{exc}"
        except Exception as exc:
            if not self._stop_event.is_set():
                reason = f"联机错误：{type(exc).__name__}: {exc}"
        finally:
            self.stop()
            self.disconnected.emit(reason)

    def _accept_peer(self) -> tuple[socket.socket, Fernet, dict[str, Any]]:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener = listener
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", self.port))
        listener.listen(1)
        listener.settimeout(0.25)
        self.status_changed.emit(
            f"等待连接：0.0.0.0:{self.port}（请确保端口已转发）"
        )
        while not self._stop_event.is_set():
            try:
                conn, address = listener.accept()
                break
            except socket.timeout:
                continue
        else:
            raise OSError("已取消等待")
        conn.settimeout(15)
        self.status_changed.emit(f"正在验证 {address[0]}…")
        salt = os.urandom(16)
        challenge = os.urandom(32)
        _send_plain(
            conn,
            {
                "type": "hello",
                "version": PROTOCOL_VERSION,
                "salt": base64.b64encode(salt).decode("ascii"),
                "challenge": base64.b64encode(challenge).decode("ascii"),
            },
        )
        auth = _recv_plain(conn)
        if auth.get("type") != "auth":
            raise ValueError("握手响应无效")
        cipher = _derive_cipher(self.password, salt)
        try:
            returned = cipher.decrypt(
                str(auth.get("token", "")).encode("ascii"), ttl=60
            )
        except InvalidToken as exc:
            raise ValueError("连接口令错误") from exc
        if not hmac.compare_digest(returned, challenge):
            raise ValueError("连接验证失败")
        _send_encrypted(
            conn,
            cipher,
            {"type": "ready", "identity": self.identity},
        )
        peer = auth.get("identity")
        if not isinstance(peer, dict):
            raise ValueError("对方宠物信息无效")
        return conn, cipher, peer

    def _connect_peer(self) -> tuple[socket.socket, Fernet, dict[str, Any]]:
        self.status_changed.emit(f"正在连接 {self.host}:{self.port}…")
        conn = socket.create_connection((self.host, self.port), timeout=12)
        conn.settimeout(15)
        hello = _recv_plain(conn)
        if (
            hello.get("type") != "hello"
            or int(hello.get("version", 0)) != PROTOCOL_VERSION
        ):
            raise ValueError("联机协议版本不兼容")
        salt = base64.b64decode(str(hello["salt"]))
        challenge = base64.b64decode(str(hello["challenge"]))
        cipher = _derive_cipher(self.password, salt)
        _send_plain(
            conn,
            {
                "type": "auth",
                "token": cipher.encrypt(challenge).decode("ascii"),
                "identity": self.identity,
            },
        )
        ready = _recv_encrypted(conn, cipher)
        if ready.get("type") != "ready":
            raise ValueError("主机未完成验证")
        peer = ready.get("identity")
        if not isinstance(peer, dict):
            raise ValueError("对方宠物信息无效")
        return conn, cipher, peer

    def _message_loop(self, conn: socket.socket, cipher: Fernet) -> str:
        conn.setblocking(False)
        buffer = bytearray()
        while not self._stop_event.is_set():
            while True:
                try:
                    packet = self._outgoing.get_nowait()
                except queue.Empty:
                    break
                _send_encrypted(conn, cipher, packet)

            readable, _, _ = select.select([conn], [], [], 0.05)
            if not readable:
                continue
            chunk = conn.recv(65536)
            if not chunk:
                return "对方已断开"
            buffer.extend(chunk)
            for payload in _extract_frames(buffer):
                try:
                    decoded = cipher.decrypt(payload)
                    packet = json.loads(decoded.decode("utf-8"))
                except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError):
                    return "收到无效或被篡改的数据"
                if isinstance(packet, dict):
                    self.packet_received.emit(packet)
        return "已主动断开"


def _derive_cipher(password: str, salt: bytes) -> Fernet:
    if len(password) < 6:
        raise ValueError("连接口令至少需要 6 个字符")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=350_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return Fernet(key)


def _encode_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _send_frame(sock: socket.socket, payload: bytes) -> None:
    if len(payload) > MAX_PACKET:
        raise ValueError("数据包过大")
    data = memoryview(struct.pack("!I", len(payload)) + payload)
    while data:
        try:
            sent = sock.send(data)
        except (BlockingIOError, InterruptedError):
            _, writable, _ = select.select([], [sock], [], 5)
            if not writable:
                raise TimeoutError("发送数据超时")
            continue
        if sent <= 0:
            raise OSError("连接已关闭")
        data = data[sent:]


def _recv_frame(sock: socket.socket) -> bytes:
    header = _recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    if length <= 0 or length > MAX_PACKET:
        raise ValueError("数据包长度无效")
    return _recv_exact(sock, length)


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise OSError("连接提前关闭")
        chunks.extend(chunk)
    return bytes(chunks)


def _extract_frames(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    while len(buffer) >= 4:
        length = struct.unpack("!I", buffer[:4])[0]
        if length <= 0 or length > MAX_PACKET:
            raise ValueError("数据包长度无效")
        if len(buffer) < 4 + length:
            break
        frames.append(bytes(buffer[4 : 4 + length]))
        del buffer[: 4 + length]
    return frames


def _send_plain(sock: socket.socket, data: dict[str, Any]) -> None:
    _send_frame(sock, _encode_json(data))


def _recv_plain(sock: socket.socket) -> dict[str, Any]:
    data = json.loads(_recv_frame(sock).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("握手数据无效")
    return data


def _send_encrypted(
    sock: socket.socket, cipher: Fernet, data: dict[str, Any]
) -> None:
    _send_frame(sock, cipher.encrypt(_encode_json(data)))


def _recv_encrypted(
    sock: socket.socket, cipher: Fernet
) -> dict[str, Any]:
    data = json.loads(cipher.decrypt(_recv_frame(sock)).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("加密数据无效")
    return data
