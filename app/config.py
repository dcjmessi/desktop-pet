from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.paths import SETTINGS_PATH, STATE_PATH, ensure_dirs

ACCESSORIES = [
    ("acc_none", "无配件"),
    ("acc_hat_beanie", "毛线帽"),
    ("acc_hat_party", "派对帽"),
    ("acc_hat_crown", "皇冠"),
    ("acc_glasses_round", "圆框眼镜"),
    ("acc_glasses_sun", "墨镜"),
    ("acc_bow", "蝴蝶结"),
    ("acc_scarf", "围巾"),
    ("acc_star_stick", "星星棒"),
]

ACTIONS = (
    "idle",
    "hit",
    "sleep",
    "eat",
    "wave",
    "walk_l",
    "walk_r",
    "vanish",
    "appear",
    "jump",
    "dance",
    "think",
    "shy",
)

# Actions offered in the pet right-click "做动作" submenu
ACTION_MENU = [
    ("wave", "招手"),
    ("jump", "跳一下"),
    ("dance", "跳舞"),
    ("think", "思考"),
    ("shy", "害羞"),
    ("hit", "打它"),
]

# Removed from gameplay; sprite folders may still exist for pack compatibility.
DISABLED_ACTIONS = frozenset({"eat", "sleep"})

LOOPING_ACTIONS = {"idle", "walk_l", "walk_r", "dance", "think"}

ACCESSORY_PROMPTS = {
    "acc_none": "",
    "acc_hat_beanie": "wearing a cute blue beanie hat",
    "acc_hat_party": "wearing a colorful party cone hat",
    "acc_hat_crown": "wearing a small golden crown",
    "acc_glasses_round": "wearing round glasses",
    "acc_glasses_sun": "wearing sunglasses",
    "acc_bow": "with a pink bow on the head",
    "acc_scarf": "wearing a green scarf",
    "acc_star_stick": "holding a star magic wand",
}


@dataclass
class Settings:
    walk_enabled: bool = False
    scale: float = 1.0
    peer_port: int = 38475

    @classmethod
    def load(cls) -> "Settings":
        ensure_dirs()
        if not SETTINGS_PATH.exists():
            return cls()
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})
        except Exception:
            return cls()

    def save(self) -> None:
        ensure_dirs()
        SETTINGS_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


@dataclass
class AppState:
    last_pet_id: str | None = None
    pet_visible: bool = True

    @classmethod
    def load(cls) -> "AppState":
        ensure_dirs()
        if not STATE_PATH.exists():
            return cls()
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})
        except Exception:
            return cls()

    def save(self) -> None:
        ensure_dirs()
        STATE_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def default_manifest(
    pet_id: str,
    name: str,
    source: str = "default",
    personality: str = "custom",
) -> dict[str, Any]:
    return {
        "id": pet_id,
        "name": name,
        "source": source,
        "personality": personality,
        "scale": 1.0,
        "active_variant": "acc_none",
        "walk_enabled": False,
        "actions": {
            "idle": {"fps": 7, "loop": True},
            "hit": {"fps": 10, "loop": False},
            "sleep": {"fps": 4, "loop": True},
            "eat": {"fps": 7, "loop": False},
            "wave": {"fps": 8, "loop": False},
            "walk_l": {"fps": 10, "loop": True},
            "walk_r": {"fps": 10, "loop": True},
            "vanish": {"fps": 12, "loop": False},
            "appear": {"fps": 12, "loop": False},
            "jump": {"fps": 10, "loop": False},
            "dance": {"fps": 12, "loop": True},
            "think": {"fps": 5, "loop": True},
            "shy": {"fps": 7, "loop": False},
        },
        "variants": ["acc_none"],
        "base_image": None,
    }
