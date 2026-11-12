"""Per-score user preferences (H7f): the split bar the learner dragged.

These are user data, never written into content files. Built-in scores are
keyed by stem; imported scores by resolved path, so a same-stem import cannot
inherit a built-in override. Loading is tolerant and saving is atomic, like
the library metadata.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

PREFS_VERSION = 1
MIN_SPLIT_BAR = 1
MAX_SPLIT_BAR = 31


def default_path() -> Path:
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "score_prefs.json"


def score_key(path: str | Path, builtin_dir: str | Path) -> str:
    """Stable preference key: builtin stem, or the imported file path."""
    path = Path(path)
    try:
        path.resolve().relative_to(Path(builtin_dir).resolve())
    except ValueError:
        return f"file:{os.path.normcase(str(path.resolve()))}"
    return f"builtin:{path.stem.casefold()}"


class ScorePrefs:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self.split_bars: dict[str, int] = {}

    def split_bar(self, key: str) -> int | None:
        return self.split_bars.get(key)

    def set_split_bar(
        self, key: str, bar: int, save: bool = True
    ) -> int:
        value = max(MIN_SPLIT_BAR, min(MAX_SPLIT_BAR, int(bar)))
        if key:
            self.split_bars[key] = value
            if save:
                self.save()
        return value

    def clear_split_bar(self, key: str, save: bool = True) -> bool:
        if key and self.split_bars.pop(key, None) is not None:
            if save:
                self.save()
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "version": PREFS_VERSION,
            "split_bars": dict(sorted(self.split_bars.items())),
        }

    @classmethod
    def from_dict(cls, raw, path: str | Path | None = None) -> "ScorePrefs":
        prefs = cls(path)
        if not isinstance(raw, dict):
            return prefs
        values = raw.get("split_bars")
        if not isinstance(values, dict):
            return prefs
        for key, bar in values.items():
            if not isinstance(key, str) or not key:
                continue
            if isinstance(bar, bool):
                continue
            try:
                number = int(bar)
            except (TypeError, ValueError):
                continue
            if MIN_SPLIT_BAR <= number <= MAX_SPLIT_BAR:
                prefs.split_bars[key] = number
        return prefs

    @classmethod
    def load(cls, path: str | Path) -> "ScorePrefs":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(path)
        return cls.from_dict(raw, path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(
            f".tmp-{uuid.uuid4().hex}-{self.path.name}"
        )
        try:
            temp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp, self.path)
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
