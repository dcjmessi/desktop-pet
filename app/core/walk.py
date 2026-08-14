from __future__ import annotations

import random

from PySide6.QtCore import QObject, QPoint, QRect, QTimer
from PySide6.QtWidgets import QWidget


class WalkController(QObject):
    def __init__(self, window: QWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._enabled = False
        self._dir = 1
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._step)
        self._on_walk_action = None

    def set_action_callback(self, cb) -> None:
        self._on_walk_action = cb

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self._dir = random.choice([-1, 1])
            if self._on_walk_action:
                self._on_walk_action("walk_r" if self._dir > 0 else "walk_l")
            self._timer.start()
        else:
            self._timer.stop()
            if self._on_walk_action:
                self._on_walk_action("idle")

    def _screen_rect(self) -> QRect:
        screen = self._window.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

    def _step(self) -> None:
        if not self._enabled or not self._window.isVisible():
            return
        geo = self._window.geometry()
        area = self._screen_rect()
        x = geo.x() + self._dir * 2
        y = geo.y()
        if x < area.left():
            x = area.left()
            self._dir = 1
            if self._on_walk_action:
                self._on_walk_action("walk_r")
        elif x + geo.width() > area.right():
            x = area.right() - geo.width()
            self._dir = -1
            if self._on_walk_action:
                self._on_walk_action("walk_l")
        # keep near bottom
        target_y = area.bottom() - geo.height() - 40
        if abs(y - target_y) > 8:
            y += 1 if y < target_y else -1
        self._window.move(QPoint(x, y))
