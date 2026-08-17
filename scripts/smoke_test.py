"""Offscreen smoke test: lifecycle, UI signals, actions, accessories and chat."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import ACCESSORIES, ACTIONS, DISABLED_ACTIONS, Settings  # noqa: E402
from app.core.dialogue import match_keyword_reply  # noqa: E402
from app.core.pack import list_packs  # noqa: E402
from app.main import DesktopPetApp  # noqa: E402


def run() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet_app = DesktopPetApp(app)
    app.setProperty("desktopPetController", pet_app)
    problems: list[str] = []
    switch_started = time.perf_counter()

    for pack in list_packs():
        # Exercise the real workshop selection/button signal path.
        matches = pet_app.tool.list.findItems(
            pack.name, Qt.MatchFlag.MatchStartsWith
        )
        if not matches:
            problems.append(f"{pack.id}: 工坊列表中不存在")
            continue
        pet_app.tool.list.setCurrentItem(matches[0])
        pet_app.tool.btn_summon.click()
        app.processEvents()
        current = pet_app.pet.player.pack
        if not current or current.id != pack.id:
            problems.append(f"{pack.id}: 工坊无法选择并召唤")
            continue
        for action in ACTIONS:
            if action in DISABLED_ACTIONS:
                continue
            pet_app.pet.controller.do(action)
            got = pet_app.pet.player.action
            if got != action:
                problems.append(f"{pack.id}: {action} -> 实际播放 {got}")
            if not pet_app.pet.player.current_pixmap():
                problems.append(f"{pack.id}: {action} 没有帧")
        for acc_id, _ in ACCESSORIES:
            # Exercise the pet menu's deferred accessory signal.
            pet_app.pet._change_accessory(acc_id)
            app.processEvents()
            active = pet_app.pet.player.pack.active_variant
            if active != acc_id:
                problems.append(f"{pack.id}: 配件 {acc_id} -> 实际 {active}")
            if acc_id != "acc_none":
                expected = f"variants{os.sep}{acc_id}"
                if not pet_app.pet.player._frames or expected not in str(
                    pet_app.pet.player._frames[0]
                ):
                    problems.append(f"{pack.id}: 配件 {acc_id} 未加载对应帧")
        pet_app.pet.controller.do("idle")
        pet_app.pet.open_chat()
        if not pet_app.pet.chat.isVisible():
            problems.append(f"{pack.id}: 聊天输入框没有显示")
        pet_app.pet.chat.setText("你好呀")
        pet_app.pet._submit_chat()
        if not pet_app.pet.bubble.isVisible():
            problems.append(f"{pack.id}: 聊天没有回复气泡")
        pet_app.pet.close_chat()

    switch_seconds = time.perf_counter() - switch_started

    original_terms = {
        "狗狗狗": "肉肉肉",
        "狗东西": "肉东西",
        "狗狗": "汪汪~",
        "狗": "肉",
        "丁小成": "刘大芳",
    }
    for text, expected in original_terms.items():
        actual = match_keyword_reply(text, "测试宠物")
        if actual != expected:
            problems.append(f"原始对话词库 {text} -> {actual}，应为 {expected}")

    # Long status/API errors must not stretch the workshop.
    pet_app.tool._set_status("https://example.invalid/" + "x" * 4000)
    app.processEvents()
    if pet_app.tool.width() > 920:
        problems.append(f"工坊被状态文本拉宽到 {pet_app.tool.width()}px")

    # Saving the default scale must apply immediately and survive reload.
    old_scale = pet_app.settings.scale
    pet_app.tool.scale.lineEdit().setText("1.4")
    pet_app.tool._save_settings()
    app.processEvents()
    if abs(Settings.load().scale - 1.4) > 0.001:
        problems.append("默认缩放未持久化")
    if abs(pet_app.pet.player._scale - 1.4) > 0.001:
        problems.append("默认缩放保存后未应用到当前宠物")
    pet_app.tool.scale.setValue(old_scale)
    pet_app.tool._save_settings()

    # Pet → workshop signal path.
    pet_app.tool.hide()
    pet_app.pet.open_tool.emit()
    app.processEvents()
    if not pet_app.tool.isVisible():
        problems.append("宠物菜单无法打开工坊")

    # Tray menu actions (available on a normal Windows session; offscreen
    # platforms may report that no system tray exists).
    if pet_app.tray_menu is not None:
        tray_actions = {
            action.text(): action
            for action in pet_app.tray_menu.actions()
            if not action.isSeparator()
        }
        pet_app.tool.hide()
        tray_actions["打开工坊"].trigger()
        app.processEvents()
        if not pet_app.tool.isVisible():
            problems.append("托盘菜单无法打开工坊")
        pet_app.pet.hide()
        tray_actions["显示宠物"].trigger()
        app.processEvents()
        if not pet_app.pet.isVisible():
            problems.append("托盘菜单无法显示宠物")

    QTimer.singleShot(0, app.quit)
    app.exec()

    if problems:
        print("发现问题：")
        for p in problems:
            print(" -", p)
        return 1
    print(f"smoke test OK; accessory/UI pass={switch_seconds:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
