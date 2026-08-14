from __future__ import annotations

from typing import Callable

from app.config import Settings
from app.core.pack import PetPack
from app.services.accessory import bake_variant

Progress = Callable[[str], None]


def regenerate_accessory_variant(
    pack: PetPack,
    settings: Settings,
    accessory: str,
    progress: Progress | None = None,
) -> None:
    """Prebake one accessory across the pet's whole action set.

    Accessories are drawn onto every action frame with head/eye anchors instead of
    being re-imagined by the cloud model: it is instant, keeps the pose identical,
    and cannot fail halfway through a 90-frame pack.
    """

    def p(msg: str) -> None:
        if progress:
            progress(msg)

    if accessory == "acc_none":
        pack.set_variant("acc_none")
        return

    actions_root = pack.root / "actions"
    if not actions_root.exists():
        raise FileNotFoundError("缺少动作帧目录，无法生成配件")

    p(f"预烘配件「{accessory}」整套动作帧…")
    count = bake_variant(actions_root, pack.root / "variants" / accessory, accessory)
    variants = pack.manifest.setdefault("variants", ["acc_none"])
    if accessory not in variants:
        variants.append(accessory)
    pack.set_variant(accessory)
    p(f"配件帧包已缓存（{count} 帧）")
