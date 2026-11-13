"""First-run onboarding state (A3).

The wizard is discovery, not a gate: it shows once on first launch, can be
skipped at any step, and can always be reopened from the Help page. Only
``completed`` and ``skipped`` are persisted; a corrupt or missing file means
"not seen yet", never a crash.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ONBOARDING_VERSION = 1


def default_path() -> Path:
    """User onboarding file, next to learning.json in the app config dir."""
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "onboarding.json"


@dataclass
class OnboardingState:
    completed: bool = False
    skipped: bool = False
    seen_at: str = ""
    version: int = ONBOARDING_VERSION
    path: Path = field(default_factory=default_path)

    @property
    def done(self) -> bool:
        """True when the wizard should not auto-open again."""
        return self.completed or self.skipped

    @classmethod
    def load(cls, path: str | Path | None = None) -> "OnboardingState":
        target = Path(path) if path is not None else default_path()
        state = cls(path=target)
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return state
        except (OSError, ValueError, RecursionError):
            return state
        if not isinstance(raw, dict):
            return state
        if raw.get("version") != ONBOARDING_VERSION:
            return state
        state.completed = raw.get("completed") is True
        state.skipped = raw.get("skipped") is True
        seen = raw.get("seen_at")
        state.seen_at = seen if isinstance(seen, str) else ""
        return state

    def mark_completed(self) -> None:
        self.completed = True
        self.skipped = False
        self.seen_at = datetime.now().isoformat(timespec="seconds")

    def mark_skipped(self) -> None:
        self.skipped = True
        self.seen_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "completed": self.completed,
            "skipped": self.skipped,
            "seen_at": self.seen_at,
        }

    def save(self) -> None:
        target = Path(self.path)
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
