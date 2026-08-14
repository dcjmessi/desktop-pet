#!/usr/bin/env python3
"""Rebuild every default pet pack from Codex-format sprite atlases.

Usage:
    python scripts/build_pets.py            # rebuild all pets
    python scripts/build_pets.py nailong    # rebuild one pet
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import default_manifest  # noqa: E402
from app.paths import DATA, PETS_ASSETS, ensure_dirs  # noqa: E402
from app.services.accessory import bake_all_variants  # noqa: E402
from app.services.sheet import build_actions_from_sheet, tint_sheet  # noqa: E402

SHEET_CACHE = DATA / "_sheet_cache"

GALLERY = "https://raw.githubusercontent.com/legeling/awesome-codex-pet/main/pets/{}/spritesheet.webp"

# Real fan-made Codex pet atlases from public galleries. Personal use only —
# see assets/pets/NOTICE.txt. 章鱼哥 / 史迪仔 / 闪电 have no public Codex atlas, so
# those slots use other authentic mascots from the same gallery.
PETS: dict[str, dict] = {
    "nailong": {
        "name": "奶龙",
        "personality": "nailong",
        "urls": [
            "https://raw.githubusercontent.com/erich207/nailong-codex-pet/main/spritesheet.webp",
            GALLERY.format("happynailong--aquaxyy"),
        ],
        "tint": None,
    },
    "dagongniu": {
        "name": "打工牛",
        "personality": "dagongniu",
        "urls": [GALLERY.format("niumou--jarvis-2")],
        "tint": None,
    },
    "salarycat": {
        "name": "打工猫",
        "personality": "salarycat",
        "urls": [GALLERY.format("salary-cat--zuochunjie")],
        "tint": None,
    },
    "koukou": {
        "name": "扣扣企鹅",
        "personality": "koukou",
        "urls": [GALLERY.format("koukou-penguin--hoody")],
        "tint": None,
    },
    "capybara": {
        "name": "水豚噜噜",
        "personality": "capybara",
        "urls": [GALLERY.format("capybara-lulu--jiushu")],
        "tint": None,
    },
}

RETIRED = ("zhangyuge", "stidzai", "shandian")

FALLBACK_SHEET = "nailong"


def log(msg: str) -> None:
    print(msg, flush=True)


def download(url: str, dest: Path) -> bool:
    try:
        import requests

        log(f"  GET {url}")
        r = requests.get(url, timeout=45)
        if r.status_code != 200 or len(r.content) < 2000:
            log(f"  -> HTTP {r.status_code}")
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        log(f"  -> {type(e).__name__}")
        return False


def resolve_sheet(pet_id: str, meta: dict) -> tuple[Path, bool]:
    """Return (sheet path, is_authentic). Recolors the fallback atlas when needed."""
    own = SHEET_CACHE / f"{pet_id}.webp"
    if own.exists():
        return own, True
    for url in meta.get("urls", []):
        if download(url, own):
            return own, True

    base = SHEET_CACHE / f"{FALLBACK_SHEET}.webp"
    if not base.exists():
        for url in PETS[FALLBACK_SHEET]["urls"]:
            if download(url, base):
                break
    if not base.exists():
        raise FileNotFoundError("没有可用的精灵表，请检查网络或手动放入 data/_sheet_cache/nailong.webp")

    tint = meta.get("tint") or (200, 200, 200)
    recolored = SHEET_CACHE / f"{pet_id}_recolor.webp"
    tint_sheet(base, recolored, tint)
    log(f"  使用 {FALLBACK_SHEET} 精灵表重着色（未取到 {pet_id} 原始素材）")
    return recolored, False


def build(pet_id: str, meta: dict) -> None:
    log(f"[{pet_id}] {meta['name']}")
    sheet, authentic = resolve_sheet(pet_id, meta)

    root = PETS_ASSETS / pet_id
    if root.exists():
        shutil.rmtree(root)
    actions_root = root / "actions"
    actions_root.mkdir(parents=True, exist_ok=True)

    counts = build_actions_from_sheet(sheet, actions_root, progress=lambda m: log(f"  {m}"))

    idle_frames = sorted((actions_root / "idle").glob("*.png"))
    if idle_frames:
        shutil.copy2(idle_frames[0], root / "base.png")

    log("  预烘配件帧包…")
    variants = bake_all_variants(actions_root, root / "variants", progress=lambda m: log(f"  {m}"))

    manifest = default_manifest(pet_id, meta["name"], "default", meta["personality"])
    manifest["variants"] = variants
    manifest["base_image"] = "base.png"
    manifest["authentic_art"] = authentic
    manifest["frame_counts"] = counts
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"  完成：{sum(counts.values())} 帧动作 / {len(variants)} 套配件")


def main(argv: list[str]) -> int:
    ensure_dirs()
    SHEET_CACHE.mkdir(parents=True, exist_ok=True)
    targets = argv[1:] or list(PETS)
    if not argv[1:]:
        for old in RETIRED:
            stale = PETS_ASSETS / old
            if stale.exists():
                shutil.rmtree(stale)
                log(f"移除旧占位宠物：{old}")
    for pet_id in targets:
        meta = PETS.get(pet_id)
        if not meta:
            log(f"未知宠物：{pet_id}")
            continue
        build(pet_id, meta)

    (PETS_ASSETS / "NOTICE.txt").write_text(
        "默认宠物素材来自公开网络的粉丝 Codex 桌宠精灵表，仅供个人学习使用，请勿商用分发。\n"
        "取不到原始素材的角色使用同一精灵表重着色作为占位，可用 scripts/import_sheet.py 换成真实素材。\n"
        "Sources: github.com/erich207/nailong-codex-pet 等公开仓库。\n",
        encoding="utf-8",
    )
    log("all done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
