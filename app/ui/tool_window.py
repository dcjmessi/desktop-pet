from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from app.config import Settings
from app.core.pack import PetPack, delete_pack, get_pack, is_default_pack, list_packs


class AccessoryWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(object, str)
    finished_err = Signal(str)

    def __init__(self, pack: PetPack, settings: Settings, accessory: str) -> None:
        super().__init__()
        self.pack, self.settings, self.accessory = pack, settings, accessory

    def run(self) -> None:
        try:
            from app.services.accessory_regen import regenerate_accessory_variant
            regenerate_accessory_variant(self.pack, self.settings, self.accessory, progress=self.progress.emit)
            self.finished_ok.emit(self.pack, self.accessory)
        except Exception as exc:
            self.finished_err.emit(str(exc))


class ToolWindow(QWidget):
    summon_pet = Signal(str)
    settings_changed = Signal(object)
    relay_create_requested = Signal(str)
    relay_join_requested = Signal(str)
    peer_disconnect_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("桌面宠物工坊")
        self.resize(760, 580)
        self.setMinimumSize(700, 520)
        self.setMaximumWidth(960)
        self._worker: QThread | None = None
        root = QHBoxLayout(self)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        left.addWidget(QLabel("宠物列表"))
        left.addWidget(self.list, 1)
        actions = QHBoxLayout()
        self.btn_summon, self.btn_delete, self.btn_refresh = QPushButton("放到桌面"), QPushButton("删除"), QPushButton("刷新")
        self.btn_delete.setEnabled(False)
        for button in (self.btn_summon, self.btn_delete, self.btn_refresh):
            actions.addWidget(button)
        left.addLayout(actions)
        root.addLayout(left, 2)

        right = QVBoxLayout()
        self.preview = QLabel("预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet("background:#eef3f8; border-radius:8px;")
        right.addWidget(self.preview)

        peer = QGroupBox("好友联机（邀请码）")
        peer_form = QFormLayout(peer)
        self.relay_url = QLineEdit(settings.relay_public_url)
        self.relay_url.setPlaceholderText("主机填写花生壳 HTTP/HTTPS 映射地址")
        self.invite_code = QLineEdit()
        self.invite_code.setPlaceholderText("创建后生成；好友只需粘贴并加入")
        for field in (self.relay_url, self.invite_code):
            field.setMinimumWidth(0)
            field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        peer_form.addRow("花生壳地址", self.relay_url)
        peer_form.addRow("邀请码", self.invite_code)
        peer_buttons = QHBoxLayout()
        self.btn_peer_host = QPushButton("创建邀请码")
        self.btn_copy_invite = QPushButton("复制")
        self.btn_peer_connect = QPushButton("加入邀请码")
        self.btn_peer_disconnect = QPushButton("断开")
        self.btn_peer_disconnect.setEnabled(False)
        for button in (self.btn_peer_host, self.btn_copy_invite, self.btn_peer_connect, self.btn_peer_disconnect):
            peer_buttons.addWidget(button)
        peer_form.addRow(peer_buttons)
        self.peer_status = QLabel("未连接")
        self.peer_status.setWordWrap(True)
        peer_form.addRow("状态", self.peer_status)
        hint = QLabel("主机：填地址 → 创建邀请码 → 发给好友。好友：只粘贴邀请码 → 加入。")
        hint.setWordWrap(True)
        peer_form.addRow(hint)
        right.addWidget(peer)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setMaximumHeight(44)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        right.addWidget(self.progress)
        right.addWidget(self.status)

        config = QGroupBox("设置")
        form = QFormLayout(config)
        self.walk = QCheckBox("默认开启桌面走动")
        self.walk.setChecked(settings.walk_enabled)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.4, 2.5)
        self.scale.setSingleStep(0.1)
        self.scale.setValue(settings.scale)
        form.addRow(self.walk)
        form.addRow("默认缩放", self.scale)
        save_button = QPushButton("保存设置")
        form.addRow(save_button)
        right.addWidget(config)
        right.addStretch(1)
        root.addLayout(right, 3)

        self.btn_summon.clicked.connect(self._summon)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_peer_host.clicked.connect(self._request_create_invite)
        self.btn_copy_invite.clicked.connect(self._copy_invite)
        self.btn_peer_connect.clicked.connect(self._request_join_invite)
        self.btn_peer_disconnect.clicked.connect(
            lambda: self.peer_disconnect_requested.emit()
        )
        save_button.clicked.connect(self._save_settings)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for pack in list_packs():
            label = f"{pack.name}（默认）" if is_default_pack(pack) else f"{pack.name} ({pack.source})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, pack.id)
            self.list.addItem(item)
        self._update_delete_button()

    def _update_delete_button(self) -> None:
        item = self.list.currentItem()
        pack = get_pack(item.data(Qt.ItemDataRole.UserRole)) if item else None
        enabled = bool(pack and not is_default_pack(pack))
        self.btn_delete.setEnabled(enabled)
        self.btn_delete.setToolTip("删除用户宠物" if enabled else "默认宠物不可删除")

    def _on_select(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._update_delete_button()
        if not current:
            return
        pack = get_pack(current.data(Qt.ItemDataRole.UserRole))
        if not pack:
            return
        frame = pack.preview_frame()
        self.preview.setPixmap(QPixmap(str(frame)).scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)) if frame else self.preview.setText(pack.name)

    def _summon(self) -> None:
        item = self.list.currentItem()
        if item:
            self.summon_pet.emit(item.data(Qt.ItemDataRole.UserRole))
        else:
            QMessageBox.information(self, "提示", "请先选择宠物")

    def _delete(self) -> None:
        item = self.list.currentItem()
        if item and not delete_pack(item.data(Qt.ItemDataRole.UserRole)):
            QMessageBox.warning(self, "无法删除", "默认宠物不可删除，或宠物不存在")
        self.refresh()

    def _save_settings(self) -> None:
        self.scale.interpretText()
        self.settings.walk_enabled = self.walk.isChecked()
        self.settings.scale = float(self.scale.value())
        self.settings.relay_public_url = self.relay_url.text().strip()
        self.settings.save()
        self.settings_changed.emit(self.settings)

    def _request_create_invite(self) -> None:
        url = self.relay_url.text().strip()
        if not url:
            QMessageBox.information(self, "花生壳地址", "请填写花生壳 HTTP 或 HTTPS 映射地址")
            return
        self.settings.relay_public_url = url
        self.settings.save()
        self.relay_create_requested.emit(url)

    def _request_join_invite(self) -> None:
        code = self.invite_code.text().strip()
        if not code:
            QMessageBox.information(self, "邀请码", "请粘贴好友发来的邀请码")
            return
        self.relay_join_requested.emit(code)

    def set_invite_code(self, code: str) -> None:
        self.invite_code.setText(code)

    def _copy_invite(self) -> None:
        code = self.invite_code.text().strip()
        if not code:
            QMessageBox.information(self, "邀请码", "请先创建邀请码")
            return
        QApplication.clipboard().setText(code)
        self.peer_status.setText("邀请码已复制，发给好友即可")

    def set_peer_status(self, text: str, active: bool = False) -> None:
        self.peer_status.setText(text)
        self.btn_peer_host.setEnabled(not active)
        self.btn_peer_connect.setEnabled(not active)
        self.btn_peer_disconnect.setEnabled(active)

    def run_accessory_regen(self, pack: PetPack, accessory: str) -> None:
        self.progress.show()
        self._set_status(f"正在生成配件帧：{accessory}")
        self._worker = AccessoryWorker(pack, self.settings, accessory)
        self._worker.progress.connect(self._set_status)
        self._worker.finished_ok.connect(self._accessory_ready)
        self._worker.finished_err.connect(self._accessory_error)
        self._worker.start()

    def _accessory_ready(self, pack: PetPack, accessory: str) -> None:
        self.progress.hide()
        self._set_status(f"配件就绪：{accessory}")
        fresh = get_pack(pack.id) or pack
        fresh.set_variant(accessory)
        self.summon_pet.emit(fresh.id)

    def _accessory_error(self, message: str) -> None:
        self.progress.hide()
        self._set_status("配件生成失败")
        QMessageBox.critical(self, "配件生成失败", message)

    def _set_status(self, text: str) -> None:
        raw = str(text)
        compact = " ".join(raw.split())
        self.status.setText(compact[:177] + "…" if len(compact) > 180 else compact)
        self.status.setToolTip(raw)
