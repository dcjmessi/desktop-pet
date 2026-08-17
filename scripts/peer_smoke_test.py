"""Loopback test for encrypted relay chat and action synchronization."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from app.services.relay import Invite, LocalRelay, RelaySession  # noqa: E402


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run() -> int:
    app = QCoreApplication([])
    port = free_port()
    relay = LocalRelay(port)
    relay.ensure_running()
    invite = Invite.create(f"ws://127.0.0.1:{port}")
    host = RelaySession(
        invite, {"pet_id": "nailong", "name": "奶龙"}, creating=True
    )
    client = RelaySession(
        invite, {"pet_id": "dagongniu", "name": "打工牛"}, creating=False
    )
    state: dict[str, object] = {
        "host_peer": None,
        "client_peer": None,
        "sent": False,
    }
    received: list[dict] = []
    errors: list[str] = []

    host.connected.connect(lambda peer: state.__setitem__("host_peer", peer))
    client.connected.connect(
        lambda peer: state.__setitem__("client_peer", peer)
    )
    host.packet_received.connect(received.append)
    host.disconnected.connect(
        lambda text: errors.append(text)
        if text.startswith(("连接失败", "联机错误"))
        else None
    )
    client.disconnected.connect(
        lambda text: errors.append(text)
        if text.startswith(("连接失败", "联机错误"))
        else None
    )

    host.start()
    QTimer.singleShot(100, client.start)

    def poll() -> None:
        if (
            state["host_peer"]
            and state["client_peer"]
            and not state["sent"]
        ):
            state["sent"] = True
            client.send_packet({"type": "chat", "text": "你好，联机宠物"})
            client.send_packet({"type": "action", "action": "wave"})
        if len(received) >= 2 or errors:
            host.stop()
            client.stop()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)
    QTimer.singleShot(8000, app.quit)
    app.exec()
    host.stop()
    client.stop()
    host.wait(1500)
    client.wait(1500)

    expected = [
        {"type": "chat", "text": "你好，联机宠物"},
        {"type": "action", "action": "wave"},
    ]
    if errors or received != expected:
        print("peer smoke failed", errors, received)
        return 1
    print("peer smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
