"""Where bundled assets live (source tree vs. a frozen Windows build).

Running from source, the PC root is ``pc/`` and resources sit next to ``app/``.
In a PyInstaller bundle the package is extracted under ``sys._MEIPASS`` (the
``_internal`` directory of a one-folder build), and the same relative layout is
recreated there, so ``app/core/paths.py`` still resolves to
``<_MEIPASS>/app/core`` and ``parents[2]`` is the bundle root. The explicit
``_MEIPASS`` branch keeps the intent readable and covers a frozen layout where
``__file__`` is rewritten.
"""

from __future__ import annotations

import sys
from pathlib import Path


def bundle_root() -> Path:
    """Root that contains ``resources/`` and ``prototype/vendor/``."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        if base:
            return Path(base)
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath("resources", *parts)


def vendor_path(*parts: str) -> Path:
    return bundle_root().joinpath("prototype", "vendor", *parts)


def source_root() -> Path:
    """Repository root that holds the shared ``mapping/`` table."""
    return Path(__file__).resolve().parents[3]


def mapping_path(*parts: str) -> Path:
    """``mapping/keymap.json`` from the repo or from the bundle root."""
    base = bundle_root() if getattr(sys, "frozen", False) else source_root()
    return base.joinpath("mapping", *parts)


__all__ = [
    "bundle_root",
    "mapping_path",
    "resource_path",
    "source_root",
    "vendor_path",
]
