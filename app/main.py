from __future__ import annotations

import sys
import math

from PySide6.QtCore import QLockFile, QObject, QPoint, Qt
from PySide6.QtGui import QIcon, QPainter, QColor, QPixmap, QPolygon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu

from app.config import ACCESSORIES, ACTIONS, Settings, AppState
from app.core.dialogue import match_keyword_reply
from app.core.pack import get_pack, list_packs
from app.paths import DATA, ensure_dirs
from app.services.peer import PeerSession
from app.ui.pet_window import PetWindow
from app.ui.tool_window import ToolWindow

# Chat keywords that also trigger an action, checked in order
CHAT_ACTIONS: list[tuple[tuple[str, ...], str]] = [
    (("隐藏", "消失", "走开"), "vanish"),
    (("出来", "现身", "回来"), "appear"),
    (("跳舞", "摇"), "dance"),
    (("跳一下", "蹦"), "jump"),
    (("你好", "嗨", "招手"), "wave"),
    (("想", "思考"), "think"),
    (("可爱", "喜欢", "夸"), "shy"),
]


def _make_workshop_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Yellow pet face.
    p.setBrush(QColor("#ffb703"))
    p.setPen(QColor("#e58f00"))
    p.drawEllipse(5, 5, 44, 44)
    p.setBrush(QColor("#023047"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(17, 21, 6, 7)
    p.drawEllipse(31, 21, 6, 7)
    p.setBrush(QColor("#e63946"))
    p.drawEllipse(22, 34, 9, 7)
    # Blue workshop gear.
    cx, cy, outer, inner = 44, 44, 18, 13
    points = []
    for index in range(24):
        angle = -math.pi / 2 + index * math.pi / 12
        radius = outer if index % 3 != 1 else inner
        points.append(QPoint(int(cx + radius * math.cos(angle)), int(cy + radius * math.sin(angle))))
    p.setBrush(QColor("#219ebc"))
    p.setPen(QColor("#126782"))
    p.drawPolygon(QPolygon(points))
    p.setBrush(QColor("#e9f5f8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(cx - 6, cy - 6, 12, 12)
    p.setBrush(QColor("#126782"))
    p.drawEllipse(cx - 3, cy - 3, 6, 6)
    p.end()
    return QIcon(pm)


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "DesktopPet.Workshop.3"
        )
    except Exception:
        pass


class DesktopPetApp(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        ensure_dirs()
        self.settings = Settings.load()
        self.state = AppState.load()
        self.pet = PetWindow()
        self.tool = ToolWindow(self.settings)
        self.tool.setWindowIcon(QApplication.instance().windowIcon())
        self.tool.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        self.tool.summon_pet.connect(self.summon)
        self.tool.settings_changed.connect(self._on_settings)
        self.pet.open_tool.connect(self.show_tool)
        self.pet.chat_submitted.connect(self._on_chat)
        self.pet.accessory_changed.connect(self._accessory)
        self.pet.walk_toggled.connect(self._walk_toggled)
        self.pet.scale_changed.connect(self._scale_changed)
        self.pet.manual_action.connect(self._send_manual_action)
        self.tool.peer_host_requested.connect(self._host_peer)
        self.tool.peer_connect_requested.connect(self._connect_peer)
        self.tool.peer_disconnect_requested.connect(self._disconnect_peer)

        self.peer_session: PeerSession | None = None
        self.peer_connected = False
        self.remote_pet: PetWindow | None = None

        self.tray: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None
        self._setup_tray()

        packs = list_packs()
        target = None
        if self.state.last_pet_id:
            target = get_pack(self.state.last_pet_id)
        if not target and packs:
            target = packs[0]
        if target:
            self.summon(target.id)
        self.show_tool()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(
            QApplication.instance().windowIcon(), QApplication.instance()
        )
        # QSystemTrayIcon does not own its context menu. Keep it on the
        # controller so Python cannot collect the menu or its callbacks.
        self.tray_menu = QMenu()
        self.tray_menu.addAction("显示宠物", self._show_pet)
        self.tray_menu.addAction("打开工坊", self.show_tool)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("退出", QApplication.instance().quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.setToolTip("桌面宠物工坊")
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def shutdown(self) -> None:
        self._disconnect_peer()
        if self.tray is not None:
            self.tray.hide()

    def show_tool(self) -> None:
        self.tool.show()
        self.tool.raise_()
        self.tool.activateWindow()

    def _tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_pet()

    def _show_pet(self) -> None:
        if self.pet.controller.hidden:
            self.pet.controller.appear()
            self._send_peer_packet({"type": "action", "action": "appear"})
        self.pet.show()
        self.pet.raise_()

    def summon(self, pet_id: str) -> None:
        pack = get_pack(pet_id)
        if not pack:
            QMessageBox.warning(self.tool, "错误", f"找不到宠物：{pet_id}")
            return
        current = self.pet.player.pack
        peer_running = (
            self.peer_session is not None and self.peer_session.isRunning()
        )
        if peer_running and (not current or current.id != pack.id):
            QMessageBox.information(
                self.tool,
                "联机宠物",
                "请先断开联机，再切换宠物。",
            )
            return
        self.pet.controller.set_pack(pack)
        # Scale is a global display preference. Pack manifests historically
        # defaulted to 1.0, which incorrectly overrode the saved setting.
        self.pet.player.set_scale(self.settings.scale)
        walk = bool(pack.manifest.get("walk_enabled", self.settings.walk_enabled))
        self.pet.set_walk_enabled(walk)
        self.pet.show()
        self.pet.place_bottom_right()
        self.state.last_pet_id = pet_id
        self.state.save()
        if self._peer_active() and pack.source == "default":
            self._send_peer_packet(
                {"type": "pet", "pet_id": pack.id, "name": pack.name}
            )

    def _on_settings(self, settings: Settings) -> None:
        self.settings = settings
        if self.pet.player.pack:
            self.pet.set_walk_enabled(settings.walk_enabled)
            self.pet.player.set_scale(settings.scale)

    def _on_chat(self, text: str) -> None:
        """Keyword reply plus a matching action, so chatting feels interactive."""
        pack = self.pet.player.pack
        if not pack:
            return
        if self._peer_active():
            message = text.strip()[:300]
            if message:
                self.pet.show_bubble(message, 5000)
                self._send_peer_packet({"type": "chat", "text": message})
            return
        self.pet.show_bubble(match_keyword_reply(text, pack.name), 4000)
        for keys, action in CHAT_ACTIONS:
            if any(k in text for k in keys):
                if action == "appear":
                    self.pet.show()
                # Preserve the established keyword-corpus reply; the action
                # must not overwrite it with its generic menu line.
                self.pet.controller.do(action, announce=False)
                break

    def _accessory(self, acc_id: str) -> None:
        pack = self.pet.player.pack
        if not pack:
            return
        label = next((n for i, n in ACCESSORIES if i == acc_id), acc_id)
        variant_path = pack.root / "variants" / acc_id
        if acc_id == "acc_none":
            pack.set_variant("acc_none")
            self.pet.player.play(self.pet.player.action, force=True)
            self.pet.show_bubble(f"已换下配件", 1200)
            return
        variant_ready = variant_path.exists() and any(
            any((variant_path / action).glob("*.png")) for action in ACTIONS
        )
        if variant_ready:
            pack.set_variant(acc_id)
            # Reload only the currently playing action. Reinitializing the
            # whole controller interrupted animation and decoded extra frames.
            self.pet.player.play(self.pet.player.action, force=True)
            self.pet.show_bubble(f"已换上：{label}", 1500)
            return
        self.pet.show_bubble(f"正在生成：{label}…", 2000)
        self.show_tool()
        self.tool.run_accessory_regen(pack, acc_id)

    def _walk_toggled(self, enabled: bool) -> None:
        self.settings.walk_enabled = enabled
        self.settings.save()
        pack = self.pet.player.pack
        if pack:
            pack.manifest["walk_enabled"] = enabled
            pack.save()

    def _scale_changed(self, scale: float) -> None:
        self.settings.scale = scale
        self.settings.save()
        if self.remote_pet is not None:
            self.remote_pet.player.set_scale(scale)

    def _peer_identity(self) -> dict[str, str] | None:
        pack = self.pet.player.pack
        if not pack or pack.source != "default":
            QMessageBox.information(
                self.tool,
                "联机宠物",
                "请先在工坊选择一只默认宠物，再开始联机。",
            )
            return None
        return {"pet_id": pack.id, "name": pack.name}

    def _host_peer(self, port: int, password: str) -> None:
        identity = self._peer_identity()
        if identity:
            self._start_peer("host", "", port, password, identity)

    def _connect_peer(
        self, host: str, port: int, password: str
    ) -> None:
        identity = self._peer_identity()
        if identity:
            self._start_peer(
                "client", host, port, password, identity
            )

    def _start_peer(
        self,
        mode: str,
        host: str,
        port: int,
        password: str,
        identity: dict[str, str],
    ) -> None:
        self._disconnect_peer()
        self.peer_connected = False
        session = PeerSession(mode, host, port, password, identity)
        self.peer_session = session
        session.status_changed.connect(
            lambda text: self.tool.set_peer_status(text, True)
        )
        session.connected.connect(self._peer_connected)
        session.packet_received.connect(self._peer_packet)
        session.disconnected.connect(self._peer_disconnected)
        session.finished.connect(
            lambda current=session: self._peer_finished(current)
        )
        self.tool.set_peer_status(
            "正在启动主机…" if mode == "host" else "正在连接…", True
        )
        session.start()

    def _peer_connected(self, identity: object) -> None:
        if not isinstance(identity, dict):
            self._disconnect_peer()
            return
        pet_id = str(identity.get("pet_id") or "")
        pack = get_pack(pet_id)
        if not pack or pack.source != "default":
            self.tool.set_peer_status("对方使用了不支持的宠物", False)
            self._disconnect_peer()
            return
        self._show_remote_pet(pack)
        self.peer_connected = True
        self.tool.peer_password.clear()
        self.tool.set_peer_status(
            f"已连接：{pack.name}（端到端加密）", True
        )

    def _show_remote_pet(self, pack) -> None:
        if self.remote_pet is None:
            self.remote_pet = PetWindow()
            self.remote_pet.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
        self.remote_pet.controller.set_pack(pack)
        self.remote_pet.controller.set_autonomous_enabled(False)
        self.remote_pet.player.set_scale(self.settings.scale)
        self.remote_pet.show()
        self.remote_pet.raise_()
        x = self.pet.x() - self.remote_pet.width() - 24
        y = self.pet.y() + self.pet.height() - self.remote_pet.height()
        self.remote_pet.move(max(0, x), max(0, y))
        self.remote_pet.show_bubble("对方已上线", 1800)

    def _peer_packet(self, packet: object) -> None:
        if not isinstance(packet, dict):
            return
        kind = packet.get("type")
        if kind == "chat" and self.remote_pet is not None:
            text = str(packet.get("text") or "").strip()[:300]
            if text:
                self.remote_pet.show_bubble(text, 5000)
        elif kind == "action" and self.remote_pet is not None:
            action = str(packet.get("action") or "")
            if action in ACTIONS:
                if action == "appear":
                    self.remote_pet.show()
                self.remote_pet.controller.do(action, announce=False)
        elif kind == "pet":
            pet_id = str(packet.get("pet_id") or "")
            pack = get_pack(pet_id)
            if pack and pack.source == "default":
                self._show_remote_pet(pack)

    def _send_manual_action(self, action: str) -> None:
        if action in ACTIONS:
            self._send_peer_packet({"type": "action", "action": action})

    def _send_peer_packet(self, packet: dict) -> None:
        if self._peer_active() and self.peer_session is not None:
            self.peer_session.send_packet(packet)

    def _peer_active(self) -> bool:
        return (
            self.peer_connected
            and
            self.peer_session is not None
            and self.peer_session.isRunning()
        )

    def _disconnect_peer(self) -> None:
        session = self.peer_session
        self.peer_session = None
        self.peer_connected = False
        if session is not None:
            session.stop()
            if session.isRunning():
                session.wait(1200)
        if self.remote_pet is not None:
            self.remote_pet.hide()
            self.remote_pet.deleteLater()
            self.remote_pet = None
        if hasattr(self, "tool"):
            self.tool.set_peer_status("未连接", False)

    def _peer_disconnected(self, reason: str) -> None:
        if self.peer_session is None:
            return
        self.peer_connected = False
        if self.remote_pet is not None:
            self.remote_pet.hide()
            self.remote_pet.deleteLater()
            self.remote_pet = None
        self.tool.set_peer_status(reason, False)

    def _peer_finished(self, session: PeerSession) -> None:
        if self.peer_session is session:
            self.peer_session = None
            self.peer_connected = False
        session.deleteLater()


def main() -> int:
    _set_windows_app_id()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("桌面宠物工坊")
    app.setWindowIcon(_make_workshop_icon())
    ensure_dirs()
    # A second process was the source of duplicate tray icons. QLockFile also
    # recovers stale locks left by a crashed process.
    instance_lock = QLockFile(str(DATA / "desktop-pet.lock"))
    instance_lock.setStaleLockTime(5000)
    if not instance_lock.tryLock(100):
        return 0
    # Keep both a QObject parent and an explicit Python reference. Without
    # this, bound signal receivers are collected after startup while the
    # top-level widgets remain visible, making every controller action inert.
    controller = DesktopPetApp(app)
    app.setProperty("desktopPetController", controller)
    app.aboutToQuit.connect(controller.shutdown)
    app.aboutToQuit.connect(instance_lock.unlock)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
