from __future__ import annotations

import random

from PySide6.QtCore import QObject, QTimer, Signal

from app.config import LOOPING_ACTIONS
from app.core.dialogue import random_bubble
from app.core.pack import PetPack
from app.core.sprite_player import SpritePlayer


ACTION_REPEAT = {
    "wave": 3,
    "eat": 3,
    "hit": 2,
    "jump": 2,
    "shy": 2,
}

ACTION_LINES = {
    "hit": "哎呦！",
    "sleep": "呼……我先睡一会儿。",
    "eat": "干饭时间到！",
    "wave": "你好呀～",
    "jump": "嘿！",
    "dance": "一起摇起来～",
    "think": "让我想想……",
    "shy": "别、别看我啦。",
    "vanish": "我先躲一下…",
    "appear": "我回来啦！",
}


class PetController(QObject):
    bubble = Signal(str)
    vanished = Signal(bool)
    action_started = Signal(str)

    def __init__(self, player: SpritePlayer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.player = player
        self._sleeping = False
        self._hidden = False
        self._idle = QTimer(self)
        self._idle.timeout.connect(self._idle_tick)
        self._idle.setInterval(4000)
        self._back_to_idle = QTimer(self)
        self._back_to_idle.setSingleShot(True)
        self._back_to_idle.timeout.connect(self._idle_again)
        self.player.action_finished.connect(self._on_action_finished)

    @property
    def sleeping(self) -> bool:
        return self._sleeping

    @property
    def hidden(self) -> bool:
        return self._hidden

    def set_pack(self, pack: PetPack | None) -> None:
        self.player.set_pack(pack)
        self._sleeping = False
        self._hidden = False
        if pack:
            self._idle.start()
            self.action_started.emit("idle")
        else:
            self._idle.stop()

    def set_autonomous_enabled(self, enabled: bool) -> None:
        if enabled and self.player.pack:
            self._idle.start()
        else:
            self._idle.stop()

    def _play(self, action: str, repeat: int = 1) -> None:
        self.player.play(action, force=True, repeat=repeat)
        self._back_to_idle.stop()
        # looping moods (dance / think) have no end frame, so time-box them
        if action in LOOPING_ACTIONS and action not in {"idle", "sleep", "walk_l", "walk_r"}:
            self._back_to_idle.start(3200)
        self.action_started.emit(action)

    def _idle_again(self) -> None:
        if self._hidden or self._sleeping:
            return
        self._play("idle")

    def do(self, action: str, announce: bool = True) -> None:
        """Trigger any action from the menu, with pacing and a matching line."""
        if self._hidden and action != "appear":
            return
        self._sleeping = action == "sleep"
        self._play(action, ACTION_REPEAT.get(action, 1))
        line = ACTION_LINES.get(action)
        if announce and line:
            self.bubble.emit(line)

    def hit(self) -> None:
        self.do("hit")

    def sleep(self) -> None:
        self.do("sleep")

    def wake(self) -> None:
        self._sleeping = False
        self._play("idle")

    def eat(self) -> None:
        self.do("eat")

    def wave(self) -> None:
        self.do("wave")

    def vanish(self) -> None:
        # the window hides once the puff animation reaches its last frame
        self.do("vanish")

    def appear(self) -> None:
        self._hidden = False
        self.vanished.emit(False)
        self.do("appear")

    def talk_bubble(self) -> None:
        pack = self.player.pack
        if not pack:
            return
        self.bubble.emit(random_bubble(pack.personality))

    def _idle_tick(self) -> None:
        if self._hidden or self._sleeping:
            return
        if self.player.action not in {"idle", "walk_l", "walk_r"}:
            return
        if random.random() < 0.4:
            action = random.choice(["wave", "idle", "think", "shy", "jump", "dance"])
            self._play(action, ACTION_REPEAT.get(action, 1))
            if random.random() < 0.4:
                self.talk_bubble()

    def _on_action_finished(self, action: str) -> None:
        if action == "vanish":
            self._hidden = True
            self.vanished.emit(True)
            return
        if self._sleeping:
            self._play("sleep")
