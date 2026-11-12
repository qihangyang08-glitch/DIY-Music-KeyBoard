"""User accessibility preferences (H9b).

Kept separate from score/keybinding state: this file only holds display
choices that must survive restarts. Loading is tolerant (a corrupt or
half-written file means "defaults") and saving is atomic, like
``score_prefs.py`` and the library metadata.
"""

from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path

PREFS_VERSION = 1

LANGUAGE_ZH = "zh-CN"
LANGUAGE_EN = "en"
LANGUAGE_CODES = (LANGUAGE_ZH, LANGUAGE_EN)

FONT_SCALE_MIN = 0.8
FONT_SCALE_MAX = 1.3
FONT_SCALE_PRESETS = ((0.9, "小"), (1.0, "标准"), (1.2, "大"))


def normalize_language(value) -> str:
    """Only the supported UI languages are accepted; anything else is zh-CN."""
    return value if value in LANGUAGE_CODES else LANGUAGE_ZH


def normalize_font_scale(value) -> float:
    """Clamp numeric scales; reject bool/NaN/inf and non-numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return 1.0
    if not math.isfinite(number):
        return 1.0
    return max(FONT_SCALE_MIN, min(FONT_SCALE_MAX, number))


def default_path() -> Path:
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "accessibility.json"


class AccessibilityPrefs:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self.reduce_motion = False
        self.font_scale = 1.0
        self.language = LANGUAGE_ZH

    def to_dict(self) -> dict:
        return {
            "version": PREFS_VERSION,
            "reduce_motion": self.reduce_motion,
            "font_scale": self.font_scale,
            "language": self.language,
        }

    @classmethod
    def from_dict(
        cls, raw, path: str | Path | None = None
    ) -> "AccessibilityPrefs":
        prefs = cls(path)
        if not isinstance(raw, dict):
            return prefs
        # Only a real JSON boolean opts in; "yes"/1/None keep the default.
        prefs.reduce_motion = raw.get("reduce_motion") is True
        prefs.font_scale = normalize_font_scale(raw.get("font_scale", 1.0))
        prefs.language = normalize_language(raw.get("language", LANGUAGE_ZH))
        return prefs

    @classmethod
    def load(cls, path: str | Path) -> "AccessibilityPrefs":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            return cls(path)
        return cls.from_dict(raw, path)

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".tmp-{uuid.uuid4().hex}-{target.name}")
        try:
            temp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp, target)
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
