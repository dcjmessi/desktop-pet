from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller keeps bundled read-only assets under _MEIPASS, while user
    # settings must stay beside the executable in the portable folder.
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS"))
else:
    ROOT = Path(__file__).resolve().parent.parent
    BUNDLE_ROOT = ROOT

ASSETS = BUNDLE_ROOT / "assets"
PETS_ASSETS = ASSETS / "pets"
DATA = ROOT / "data"
USER_PETS = DATA / "user_pets"
SETTINGS_PATH = DATA / "settings.json"
STATE_PATH = DATA / "state.json"


def ensure_dirs() -> None:
    for p in (DATA, USER_PETS):
        p.mkdir(parents=True, exist_ok=True)
    if not getattr(sys, "frozen", False):
        for p in (ASSETS, PETS_ASSETS):
            p.mkdir(parents=True, exist_ok=True)
