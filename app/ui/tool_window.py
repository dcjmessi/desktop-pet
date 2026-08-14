from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings
from app.core.pack import PetPack, delete_pack, get_pack, is_default_pack, list_packs


class AccessoryWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(object, str)
    finished_err = Signal(str)

    def __init__(self, pack: PetPack, settings: Settings, accessory: str) -> None:
        super().__init__()
        self.pack = pack
        self.settings = settings
        self.accessory = accessory

    def run(self) -> None:
        try:
            from app.services.accessory_regen import regenerate_accessory_variant

            regenerate_accessory_variant(
                self.pack,
                self.settings,
                self.accessory,
                progress=lambda m: self.progress.emit(m),
            )
            self.finished_ok.emit(self.pack, self.accessory)
        except Exception as e:
            self.finished_err.emit(str(e))


class ToolWindow(QWidget):
    summon_pet = Signal(str)
    settings_changed = Signal(object)
    peer_host_requested = Signal(int, str)
    peer_connect_requested = Signal(str, int, str)
    peer_disconnect_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("桌面宠物工坊")
        self.resize(720, 560)
        self.setMinimumSize(680, 520)
        self.setMaximumWidth(920)
        self._worker: QThread | None = None

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        left.addWidget(QLabel("宠物列表"))
        left.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.btn_summon = QPushButton("放到桌面")
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setToolTip("默认宠物不可删除")
        self.btn_delete.setEnabled(False)
        self.btn_refresh = QPushButton("刷新")
        btns.addWidget(self.btn_summon)
        btns.addWidget(self.btn_delete)
        btns.addWidget(self.btn_refresh)
        left.addLayout(btns)
        root.addLayout(left, 2)

        right = QVBoxLayout()
        self.preview = QLabel("预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet("background:#eef3f8; border-radius:8px;")
        right.addWidget(self.preview)

        peer = QGroupBox("宠物联机（互联网 IP 直连）")
        peer_form = QFormLayout(peer)
        self.peer_host = QLineEdit()
        self.peer_host.setPlaceholderText("主机公网 IP 或域名")
        self.peer_port = QSpinBox()
        self.peer_port.setRange(1024, 65535)
        self.peer_port.setValue(settings.peer_port)
        self.peer_password = QLineEdit()
        self.peer_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.peer_password.setPlaceholderText("至少 6 个字符，不会保存")
        for field in (self.peer_host, self.peer_password):
            field.setMinimumWidth(0)
            field.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
        peer_form.addRow("对方地址", self.peer_host)
        peer_form.addRow("端口", self.peer_port)
        peer_form.addRow("连接口令", self.peer_password)
        peer_buttons = QHBoxLayout()
        self.btn_peer_host = QPushButton("作为主机")
        self.btn_peer_connect = QPushButton("连接主机")
        self.btn_peer_disconnect = QPushButton("断开")
        self.btn_peer_disconnect.setEnabled(False)
        peer_buttons.addWidget(self.btn_peer_host)
        peer_buttons.addWidget(self.btn_peer_connect)
        peer_buttons.addWidget(self.btn_peer_disconnect)
        peer_form.addRow(peer_buttons)
        self.peer_status = QLabel("未连接")
        self.peer_status.setWordWrap(True)
        peer_form.addRow("状态", self.peer_status)
        right.addWidget(peer)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setMaximumHeight(44)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        right.addWidget(self.progress)
        right.addWidget(self.status)

        cfg = QGroupBox("设置")
        form = QFormLayout(cfg)
        self.walk = QCheckBox("默认开启桌面走动")
        self.walk.setChecked(settings.walk_enabled)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.4, 2.5)
        self.scale.setSingleStep(0.1)
        self.scale.setValue(settings.scale)
        form.addRow(self.walk)
        form.addRow("默认缩放", self.scale)
        save_btn = QPushButton("保存设置")
        form.addRow(save_btn)
        right.addWidget(cfg)
        right.addStretch(1)
        root.addLayout(right, 3)

        self.btn_summon.clicked.connect(self._summon)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_peer_host.clicked.connect(self._request_peer_host)
        self.btn_peer_connect.clicked.connect(self._request_peer_connect)
        self.btn_peer_disconnect.clicked.connect(
            lambda: self.peer_disconnect_requested.emit()
        )
        save_btn.clicked.connect(self._save_settings)

        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for pack in list_packs():
            if is_default_pack(pack):
                label = f"{pack.name}（默认）"
            else:
                label = f"{pack.name} ({pack.source})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, pack.id)
            self.list.addItem(item)
        self._update_delete_button()

    def _update_delete_button(self) -> None:
        item = self.list.currentItem()
        if not item:
            self.btn_delete.setEnabled(False)
            self.btn_delete.setToolTip("请先选择宠物")
            return
        pack = get_pack(item.data(Qt.ItemDataRole.UserRole))
        if not pack or is_default_pack(pack):
            self.btn_delete.setEnabled(False)
            self.btn_delete.setToolTip("默认宠物不可删除")
            return
        self.btn_delete.setEnabled(True)
        self.btn_delete.setToolTip("删除该用户宠物")

    def _on_select(self, cur: QListWidgetItem | None, _prev) -> None:
        self._update_delete_button()
        if not cur:
            return

        pack = get_pack(cur.data(Qt.ItemDataRole.UserRole))
        if not pack:
            return
        frame = pack.preview_frame()
        if frame:
            pm = QPixmap(str(frame)).scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(pm)
        else:
            self.preview.setText(pack.name)

    def _summon(self) -> None:
        item = self.list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择宠物")
            return
        self.summon_pet.emit(item.data(Qt.ItemDataRole.UserRole))

    def _delete(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        pet_id = item.data(Qt.ItemDataRole.UserRole)
        pack = get_pack(pet_id)
        if pack and is_default_pack(pack):
            QMessageBox.warning(self, "无法删除", "默认宠物不可删除")
            return
        if not delete_pack(pet_id):
            QMessageBox.warning(self, "无法删除", "默认宠物不可删除，或宠物不存在")
            return
        self.refresh()

    def _gen_err(self, msg: str) -> None:
        self.progress.hide()
        self.btn_gen.setEnabled(True)
        self._set_status("失败")
        QMessageBox.critical(self, "生成失败", msg)

    def _save_settings(self) -> None:
        # Commit text currently being edited before reading value(). Without
        # this, clicking Save directly after typing can persist the old 1.00.
        self.scale.interpretText()
        self.settings.walk_enabled = self.walk.isChecked()
        self.settings.scale = float(self.scale.value())
        self.settings.peer_port = int(self.peer_port.value())
        self.settings.save()
        self.settings_changed.emit(self.settings)
        self.scale.setValue(self.settings.scale)

    def run_accessory_regen(self, pack: PetPack, accessory: str) -> None:
        self.progress.show()
        self._set_status(f"正在生成配件帧：{accessory}")
        self._worker = AccessoryWorker(pack, self.settings, accessory)
        self._worker.progress.connect(self._set_status)
        self._worker.finished_ok.connect(self._acc_ok)
        self._worker.finished_err.connect(self._gen_err)
        self._worker.start()

    def _acc_ok(self, pack: PetPack, accessory: str) -> None:
        self.progress.hide()
        self._set_status(f"配件就绪：{accessory}")
        from app.core.pack import get_pack

        fresh = get_pack(pack.id) or pack
        fresh.set_variant(accessory)
        self.summon_pet.emit(fresh.id)

    def _set_status(self, text: str) -> None:
        """Bound API messages so long URLs/errors cannot resize the window."""
        raw = str(text)
        compact = " ".join(raw.split())
        if len(compact) > 180:
            compact = compact[:177] + "…"
        self.status.setText(compact)
        self.status.setToolTip(raw)

    def _peer_credentials(self) -> tuple[int, str] | None:
        password = self.peer_password.text()
        if len(password) < 6:
            QMessageBox.information(
                self, "连接口令", "连接口令至少需要 6 个字符"
            )
            return None
        port = int(self.peer_port.value())
        self.settings.peer_port = port
        self.settings.save()
        return port, password

    def _request_peer_host(self) -> None:
        credentials = self._peer_credentials()
        if credentials:
            self.peer_host_requested.emit(*credentials)

    def _request_peer_connect(self) -> None:
        credentials = self._peer_credentials()
        if not credentials:
            return
        host = self.peer_host.text().strip()
        if not host:
            QMessageBox.information(self, "对方地址", "请输入主机公网 IP 或域名")
            return
        self.peer_connect_requested.emit(host, *credentials)

    def set_peer_status(self, text: str, active: bool = False) -> None:
        self.peer_status.setText(text)
        self.btn_peer_host.setEnabled(not active)
        self.btn_peer_connect.setEnabled(not active)
        self.btn_peer_disconnect.setEnabled(active)
