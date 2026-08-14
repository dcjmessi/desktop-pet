# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPEC).resolve().parent

a = Analysis(
    ["app/main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "assets" / "pets"), "assets/pets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "dashscope",
        "alibabacloud_imageseg20191230",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "numpy",
        "requests",
        "charset_normalizer",
        "urllib3",
        "certifi",
        "idna",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DesktopPetWorkshop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "workshop.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DesktopPetWorkshop",
)
