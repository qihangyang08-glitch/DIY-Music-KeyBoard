# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder spec for the Windows desktop build (A4).

Build from ``pc/``:

    python tools/build_app.py

The output is ``pc/dist/KeyBorad/KeyBorad.exe`` beside ``_internal/``, which
contains ``resources/`` (public content) and ``prototype/vendor/`` (FluidSynth
DLLs + TimGM6mb). ``app/core/paths.py`` resolves both from ``sys._MEIPASS`` at
runtime, so the same code runs from source and from the bundle.
"""

import sys
from pathlib import Path

_spec_dir = Path(globals().get("SPECPATH", Path.cwd()))
ROOT = _spec_dir.parent if _spec_dir.name == "packaging" else _spec_dir
sys.path.insert(0, str(ROOT))

from app.core.packaging import pyinstaller_datas  # noqa: E402

datas = pyinstaller_datas(ROOT, ROOT.parent)
ENTRY = str(ROOT / "app" / "main.py")  # app/main.py

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["app", "app.core", "app.ui"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KeyBorad",
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KeyBorad",
)
