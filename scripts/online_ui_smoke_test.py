"""Offscreen end-to-end test for two encrypted desktop-pet controllers."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main import DesktopPetApp, _make_workshop_icon  # noqa: E402


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run() -> int:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_make_workshop_icon())
    host = DesktopPetApp(app)
    client = DesktopPetApp(app)
    host.summon("nailong")
    client.summon("dagongniu")
    port = free_port()
    host.settings.relay_local_port = port
    host._create_invite(f"ws://127.0.0.1:{port}")
    QTimer.singleShot(
        100,
        lambda: client._join_invite(host.tool.invite_code.text()),
    )
    stage = {"value": 0}
    failures: list[str] = []

    def poll() -> None:
        if stage["value"] == 0:
            if host.peer_connected and client.peer_connected:
                if (
                    not host.remote_pet
                    or host.remote_pet.player.pack.id != "dagongniu"
                ):
                    failures.append("主机没有显示对方宠物")
                if (
                    not client.remote_pet
                    or client.remote_pet.player.pack.id != "nailong"
                ):
                    failures.append("客户端没有显示对方宠物")
                host._on_chat("联机原文")
                host.pet._manual_action("wave")
                stage["value"] = 1
        elif stage["value"] == 1 and client.remote_pet:
            if client.remote_pet.bubble.text() != "联机原文":
                return
            if client.remote_pet.player.action != "wave":
                failures.append("手动动作没有同步")
            stage["value"] = 2
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(40)
    QTimer.singleShot(9000, app.quit)
    app.exec()
    if stage["value"] != 2:
        failures.append("联机 UI 测试超时")
    host.shutdown()
    client.shutdown()
    if failures:
        print("online UI smoke failed:", failures)
        return 1
    print("online UI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
