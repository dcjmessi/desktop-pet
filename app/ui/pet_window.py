from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMenu, QWidget

from app.config import ACCESSORIES, ACTION_MENU
from app.core.pet_controller import PetController
from app.core.sprite_player import SpritePlayer
from app.core.walk import WalkController


class PetWindow(QWidget):
    open_tool = Signal()
    chat_submitted = Signal(str)
    manual_action = Signal(str)
    accessory_changed = Signal(str)
    scale_changed = Signal(float)
    walk_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bubble = QLabel(self)
        self.bubble.setStyleSheet(
            "QLabel { background: rgba(255,255,255,235); color: #222; border-radius: 10px;"
            " padding: 8px 12px; font-size: 13px; font-weight: 600; }"
        )
        self.bubble.hide()
        self._bubble_timer: QTimer | None = None

        # Inline chat box: a separate dialog can end up behind this always-on-top
        # tool window, so the input lives inside the pet window itself.
        self.chat = QLineEdit(self)
        self.chat.setPlaceholderText("和我说点什么…（回车发送，Esc 关闭）")
        self.chat.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,245); color: #222; border: 2px solid #8ecae6;"
            " border-radius: 14px; padding: 6px 12px; font-size: 13px; }"
        )
        self.chat.hide()
        self.chat.returnPressed.connect(self._submit_chat)
        self._chat_open = False

        self.player = SpritePlayer(self)
        self.controller = PetController(self.player, self)
        self.walk = WalkController(self, self)
        self.walk.set_action_callback(self._on_walk_action)

        self.player.frame_changed.connect(self._on_frame)
        self.controller.bubble.connect(self.show_bubble)
        self.controller.vanished.connect(self._on_vanished)
        self.controller.action_started.connect(self._on_action_started)

        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._shake_origin: QPoint | None = None
        self._shake_timer = QTimer(self)
        self._shake_timer.timeout.connect(self._tick_shake)
        self._shake_left = 0

    def _on_frame(self, pm: QPixmap) -> None:
        self.label.setPixmap(pm)
        self.label.resize(pm.size())
        self._pet_size = pm.size()
        self._apply_layout()

    def _apply_layout(self) -> None:
        pet = getattr(self, "_pet_size", None) or QSize(120, 160)
        pad_top = 40
        chat_h = 44 if self._chat_open else 0
        width = max(pet.width(), 320 if self._chat_open else 120)
        self.setFixedSize(width, pet.height() + pad_top + chat_h)
        self.label.move(max(0, (width - pet.width()) // 2), pad_top)
        if self._chat_open:
            self.chat.setFixedWidth(width - 24)
            self.chat.move(12, pad_top + pet.height() + 4)
            self.chat.raise_()
        self._layout_bubble()

    def _layout_bubble(self) -> None:
        if self.bubble.isHidden():
            return
        self.bubble.adjustSize()
        x = max(0, (self.width() - self.bubble.width()) // 2)
        self.bubble.move(x, 2)
        self.bubble.raise_()

    def open_chat(self) -> None:
        self._chat_open = True
        self.chat.clear()
        self.chat.show()
        self._apply_layout()
        self.show()
        self.raise_()
        self.activateWindow()
        self.chat.setFocus(Qt.FocusReason.OtherFocusReason)

    def close_chat(self) -> None:
        if not self._chat_open:
            return
        self._chat_open = False
        self.chat.hide()
        self._apply_layout()

    def _submit_chat(self) -> None:
        text = self.chat.text().strip()
        self.chat.clear()
        if not text:
            self.close_chat()
            return
        self.chat_submitted.emit(text)

    def show_bubble(self, text: str, ms: int = 2800) -> None:
        self.bubble.setText(text)
        self.bubble.show()
        self._layout_bubble()
        if self._bubble_timer:
            self._bubble_timer.stop()
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self._bubble_timer.start(ms)

    def _on_vanished(self, hidden: bool) -> None:
        if hidden:
            self.hide()
        else:
            self.show()
            self.raise_()

    def _on_action_started(self, action: str) -> None:
        # Props and expressions are baked into the frames; the window only adds
        # physical reactions the sprite itself cannot show.
        if action == "hit":
            self._start_shake()

    def _start_shake(self) -> None:
        self._shake_origin = self.pos()
        self._shake_left = 10
        self._shake_timer.start(30)

    def _tick_shake(self) -> None:
        if not self._shake_origin or self._shake_left <= 0:
            self._shake_timer.stop()
            if self._shake_origin:
                self.move(self._shake_origin)
            self._shake_origin = None
            return
        import random

        dx = random.randint(-6, 6)
        dy = random.randint(-4, 4)
        self.move(self._shake_origin + QPoint(dx, dy))
        self._shake_left -= 1

    def _on_walk_action(self, action: str) -> None:
        if self.controller.sleeping or self.controller.hidden:
            return
        self.player.play(action, force=True)

    def set_walk_enabled(self, enabled: bool) -> None:
        self.walk.set_enabled(enabled)

    def hit_test(self, pos: QPoint) -> bool:
        pm = self.label.pixmap()
        if pm is None or pm.isNull():
            return False
        local = pos - self.label.pos()
        img = pm.toImage()
        x, y = local.x(), local.y()
        if x < 0 or y < 0 or x >= img.width() or y >= img.height():
            return False
        return img.pixelColor(x, y).alpha() > 20

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.hit_test(event.position().toPoint()):
                event.ignore()
                return
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            if self.hit_test(event.position().toPoint()):
                self._show_menu(event.globalPosition().toPoint())
                event.accept()
            else:
                event.ignore()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.walk.set_enabled(False)
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            if self._press_pos is not None:
                delta = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                if delta < 4:
                    self.controller.talk_bubble()
            self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.hit_test(event.position().toPoint()):
            if self.controller.sleeping:
                self._manual_wake()
                self.show_bubble("醒啦！", 1200)
            else:
                self.open_chat()
            event.accept()

    def _show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        # QAction.triggered passes a bool, so never bind Signal.emit directly.
        # Anything that opens a window is deferred: doing it inside the menu's own
        # event loop leaves the new window behind this always-on-top pet.
        act_menu = menu.addMenu("做动作")
        for action, label in ACTION_MENU:
            act_menu.addAction(label, lambda a=action: self._manual_action(a))
        menu.addAction("说话", lambda: self.controller.talk_bubble())
        menu.addAction("聊天…", lambda: QTimer.singleShot(0, self.open_chat))
        if self.controller.sleeping:
            menu.addAction("叫醒", self._manual_wake)
        menu.addAction("消失", lambda: self._manual_action("vanish"))
        acc_menu = menu.addMenu("配件")
        pack = self.player.pack
        current = pack.active_variant if pack else "acc_none"
        for acc_id, label in ACCESSORIES:
            act = acc_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(acc_id == current)
            act.triggered.connect(lambda checked=False, a=acc_id: self._change_accessory(a))
        scale_menu = menu.addMenu("缩放")
        for s in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
            act = scale_menu.addAction(f"{s:.1f}x")
            act.triggered.connect(lambda checked=False, v=s: self._change_scale(v))
        walk_act = menu.addAction("桌面走动")
        walk_act.setCheckable(True)
        walk_act.setChecked(self.walk.enabled)
        walk_act.triggered.connect(self._toggle_walk)
        menu.addSeparator()
        menu.addAction("打开工坊", lambda: QTimer.singleShot(0, self.open_tool.emit))
        menu.addAction("退出", QApplication.instance().quit)
        menu.exec(global_pos)

    def _change_accessory(self, acc_id: str) -> None:
        QTimer.singleShot(0, lambda: self.accessory_changed.emit(acc_id))

    def _manual_action(self, action: str) -> None:
        self.controller.do(action)
        self.manual_action.emit(action)

    def _manual_wake(self) -> None:
        self.controller.wake()
        self.manual_action.emit("idle")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._chat_open:
            self.close_chat()
            event.accept()
            return
        super().keyPressEvent(event)

    def _change_scale(self, scale: float) -> None:
        self.player.set_scale(scale)
        self.scale_changed.emit(scale)
        self.show_bubble(f"缩放 {scale:.1f}x", 1000)

    def _toggle_walk(self, checked: bool) -> None:
        self.set_walk_enabled(checked)
        self.walk_toggled.emit(checked)
        self.show_bubble("开始走动" if checked else "停止走动", 1000)

    def place_bottom_right(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 40, geo.bottom() - self.height() - 60)
