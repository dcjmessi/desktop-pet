from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap

from app.core.pack import PetPack


class SpritePlayer(QObject):
    frame_changed = Signal(QPixmap)
    action_finished = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pack: PetPack | None = None
        self._action = "idle"
        self._frames: list[Path] = []
        self._pixmaps: list[QPixmap] = []
        self._index = 0
        self._loop = True
        self._repeat_left = 1
        self._pixmap_cache: dict[tuple[str, int, int], QPixmap] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._scale = 1.0

    @property
    def action(self) -> str:
        return self._action

    @property
    def pack(self) -> PetPack | None:
        return self._pack

    def set_pack(self, pack: PetPack | None) -> None:
        self._pack = pack
        if pack:
            self.play("idle")
        else:
            self._timer.stop()
            self._frames = []
            self._pixmaps = []

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.4, min(2.5, scale))
        if self._pixmaps:
            self.frame_changed.emit(self._scaled(self._pixmaps[self._index % len(self._pixmaps)]))

    def play(self, action: str, *, force: bool = False, repeat: int = 1) -> None:
        """Play an action. One-shot actions can repeat so short rows stay readable."""
        if not self._pack:
            return
        if not force and action == self._action and self._timer.isActive() and self._loop:
            return
        frames = self._pack.list_frames(action)
        if not frames and action != "idle":
            frames = self._pack.list_frames("idle")
            action = "idle"
        if not frames:
            self._timer.stop()
            return
        meta = self._pack.action_meta(action)
        self._action = action
        self._frames = frames
        self._pixmaps = [self._load_pixmap(path) for path in frames]
        self._index = 0
        self._loop = bool(meta["loop"])
        self._repeat_left = max(1, repeat)
        fps = max(1, int(meta["fps"]))
        self._timer.start(int(1000 / fps))
        self.frame_changed.emit(self._scaled(self._pixmaps[0]))

    def _load_pixmap(self, path: Path) -> QPixmap:
        """Cache decoded frames so repeated accessory switches are immediate."""
        try:
            stat = path.stat()
            key = (str(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return QPixmap(str(path))
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        pixmap = QPixmap(str(path))
        self._pixmap_cache[key] = pixmap
        # Bound memory while retaining all frames seen in normal interaction.
        if len(self._pixmap_cache) > 512:
            oldest = next(iter(self._pixmap_cache))
            self._pixmap_cache.pop(oldest, None)
        return pixmap

    def current_pixmap(self) -> QPixmap | None:
        if not self._pixmaps:
            return None
        return self._scaled(self._pixmaps[self._index % len(self._pixmaps)])

    def _scaled(self, pm: QPixmap) -> QPixmap:
        if abs(self._scale - 1.0) < 0.01:
            return pm
        w = max(1, int(pm.width() * self._scale))
        h = max(1, int(pm.height() * self._scale))
        return pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _tick(self) -> None:
        if not self._pixmaps:
            return
        self._index += 1
        if self._index >= len(self._pixmaps):
            if self._loop:
                self._index = 0
            elif self._repeat_left > 1:
                self._repeat_left -= 1
                self._index = 0
            else:
                finished = self._action
                self._index = len(self._pixmaps) - 1
                self._timer.stop()
                self.frame_changed.emit(self._scaled(self._pixmaps[self._index]))
                self.action_finished.emit(finished)
                if finished != "idle" and finished != "sleep":
                    self.play("idle")
                return
        self.frame_changed.emit(self._scaled(self._pixmaps[self._index]))
