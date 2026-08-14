from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import ACTIONS, default_manifest
from app.paths import PETS_ASSETS, USER_PETS, ensure_dirs

# Built-in pets shipped under assets/pets — never deletable from the workshop.
DEFAULT_PET_IDS = frozenset(
    {"nailong", "dagongniu", "salarycat", "koukou", "capybara"}
)


@dataclass
class PetPack:
    root: Path
    manifest: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.manifest.get("id") or self.root.name)

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.id)

    @property
    def source(self) -> str:
        return str(self.manifest.get("source") or "default")

    @property
    def personality(self) -> str:
        return str(self.manifest.get("personality") or "custom")

    @property
    def active_variant(self) -> str:
        return str(self.manifest.get("active_variant") or "acc_none")

    @property
    def scale(self) -> float:
        try:
            return float(self.manifest.get("scale") or 1.0)
        except (TypeError, ValueError):
            return 1.0

    def save(self) -> None:
        path = self.root / "manifest.json"
        data = json.dumps(self.manifest, ensure_ascii=False, indent=2)
        # Antivirus / indexers occasionally hold the file right after a frame bake,
        # so write via a temp file and retry instead of losing the pet's state.
        for attempt in range(3):
            try:
                tmp = path.with_suffix(".json.tmp")
                tmp.write_text(data, encoding="utf-8")
                tmp.replace(path)
                return
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(0.15)

    def variant_root(self, variant: str | None = None) -> Path:
        v = variant or self.active_variant
        if v == "acc_none":
            actions = self.root / "actions"
            if actions.exists():
                return actions
        candidate = self.root / "variants" / v
        if candidate.exists():
            return candidate
        return self.root / "actions"

    def list_frames(self, action: str, variant: str | None = None) -> list[Path]:
        folder = self.variant_root(variant) / action
        if not folder.exists():
            # fallback to base actions
            folder = self.root / "actions" / action
        if not folder.exists():
            return []
        frames = sorted(
            [
                p
                for p in folder.iterdir()
                if p.suffix.lower() in {".png", ".webp", ".gif"} and p.is_file()
            ]
        )
        return frames

    def action_meta(self, action: str) -> dict[str, Any]:
        actions = self.manifest.get("actions") or {}
        meta = actions.get(action) or {}
        return {
            "fps": int(meta.get("fps") or 8),
            "loop": bool(meta.get("loop", action in {"idle", "sleep", "walk_l", "walk_r"})),
        }

    def available_variants(self) -> list[str]:
        declared = list(self.manifest.get("variants") or ["acc_none"])
        variants_dir = self.root / "variants"
        if variants_dir.exists():
            for child in variants_dir.iterdir():
                if child.is_dir() and child.name not in declared:
                    declared.append(child.name)
        if "acc_none" not in declared:
            declared.insert(0, "acc_none")
        return declared

    def set_variant(self, variant: str) -> None:
        if variant not in self.available_variants() and variant != "acc_none":
            # allow setting before frames exist (generation pending)
            variants = self.manifest.setdefault("variants", ["acc_none"])
            if variant not in variants:
                variants.append(variant)
        self.manifest["active_variant"] = variant
        self.save()

    def preview_frame(self) -> Path | None:
        for action in ("idle", "wave", "appear"):
            frames = self.list_frames(action)
            if frames:
                return frames[0]
        return None


def load_pack(root: Path) -> PetPack | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return PetPack(root=root, manifest=manifest)


def list_packs() -> list[PetPack]:
    ensure_dirs()
    packs: list[PetPack] = []
    for base in (PETS_ASSETS, USER_PETS):
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            pack = load_pack(child)
            if pack:
                packs.append(pack)
    return packs


def get_pack(pet_id: str) -> PetPack | None:
    for pack in list_packs():
        if pack.id == pet_id:
            return pack
    return None


def is_default_pack(pack: PetPack) -> bool:
    """True for the five built-in pets (and anything still living under assets/pets)."""
    if pack.id in DEFAULT_PET_IDS:
        return True
    try:
        if pack.root.resolve().parent == PETS_ASSETS.resolve():
            return True
    except OSError:
        pass
    return False


def create_pack_dir(
    root: Path,
    pet_id: str,
    name: str,
    source: str = "default",
    personality: str = "custom",
) -> PetPack:
    root.mkdir(parents=True, exist_ok=True)
    actions = root / "actions"
    for action in ACTIONS:
        (actions / action).mkdir(parents=True, exist_ok=True)
    (root / "variants" / "acc_none").mkdir(parents=True, exist_ok=True)
    manifest = default_manifest(pet_id, name, source, personality)
    pack = PetPack(root=root, manifest=manifest)
    pack.save()
    return pack


def delete_pack(pet_id: str) -> bool:
    pack = get_pack(pet_id)
    if not pack:
        return False
    if is_default_pack(pack):
        return False
    shutil.rmtree(pack.root, ignore_errors=True)
    return True
