"""User-editable computer-keyboard bindings (UI_DESIGN_V3 §7.3–§7.5).

One profile maps 32 bars to physical key codes and function actions to key
chords. The defaults are the three-row layout; every entry can be rebound and
the profile is saved as JSON under the user's app-config directory.

Key codes (Qt.Key values) are used, not characters: a Chinese IME may change
the character but not the physical position.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt

from .keyboard_layout import DEFAULT_NOTE_KEYS

NOTE_COUNT = 32
BINDINGS_VERSION = 2

MOD_CTRL = int(Qt.KeyboardModifier.ControlModifier.value)
MOD_SHIFT = int(Qt.KeyboardModifier.ShiftModifier.value)
MOD_ALT = int(Qt.KeyboardModifier.AltModifier.value)
MOD_META = int(Qt.KeyboardModifier.MetaModifier.value)
MOD_ALL = MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_META
NOTE_BLOCK = MOD_CTRL | MOD_ALT | MOD_META

MODIFIER_KEYS = {
    int(Qt.Key.Key_Shift),
    int(Qt.Key.Key_Control),
    int(Qt.Key.Key_Alt),
    int(Qt.Key.Key_Meta),
}

# action id, Chinese label, default key, default modifiers
FUNCTIONS = (
    ("play_pause", "播放 / 暂停", int(Qt.Key.Key_Space), 0),
    ("panic", "全部静音", int(Qt.Key.Key_Escape), 0),
    ("sustain", "延音（按住）", int(Qt.Key.Key_Shift), 0),
    # Tab belongs to focus traversal. The label toggle keeps a Ctrl chord so
    # every page stays keyboard-reachable; v1 profiles are migrated in
    # apply_dict().
    ("labels", "显示 / 隐藏标签", int(Qt.Key.Key_Tab), MOD_CTRL),
    ("help", "帮助 / 怎么用", int(Qt.Key.Key_F1), 0),
    ("page_1", "页面：演奏", int(Qt.Key.Key_1), MOD_CTRL),
    ("page_2", "页面：学习", int(Qt.Key.Key_2), MOD_CTRL),
    ("page_3", "页面：曲谱", int(Qt.Key.Key_3), MOD_CTRL),
    ("page_4", "页面：创作", int(Qt.Key.Key_4), MOD_CTRL),
    ("page_5", "页面：设备", int(Qt.Key.Key_5), MOD_CTRL),
    ("page_6", "页面：设置", int(Qt.Key.Key_6), MOD_CTRL),
    ("map", "切换音域映射", int(Qt.Key.Key_M), MOD_CTRL),
    ("tone", "切换音色", int(Qt.Key.Key_P), MOD_CTRL),
    ("oct_down", "八度 −", int(Qt.Key.Key_BracketLeft), MOD_CTRL),
    ("oct_up", "八度 +", int(Qt.Key.Key_BracketRight), MOD_CTRL),
    ("transpose_down", "移调 −", int(Qt.Key.Key_Minus), MOD_CTRL),
    ("transpose_up", "移调 +", int(Qt.Key.Key_Equal), MOD_CTRL),
    ("fullscreen", "全屏", int(Qt.Key.Key_F11), 0),
)

FUNCTION_LABELS = {action: label for action, label, _key, _mods in FUNCTIONS}
FUNCTION_DEFAULTS = {
    action: (key, mods) for action, _label, key, mods in FUNCTIONS
}

_PUNCT = {
    int(Qt.Key.Key_Comma): ",",
    int(Qt.Key.Key_Period): ".",
    int(Qt.Key.Key_Slash): "/",
    int(Qt.Key.Key_Semicolon): ";",
    int(Qt.Key.Key_Apostrophe): "'",
    int(Qt.Key.Key_BracketLeft): "[",
    int(Qt.Key.Key_BracketRight): "]",
    int(Qt.Key.Key_Minus): "-",
    int(Qt.Key.Key_Equal): "=",
    int(Qt.Key.Key_QuoteLeft): "`",
    int(Qt.Key.Key_Backslash): "\\",
}

_SPECIAL = {
    int(Qt.Key.Key_Space): "Space",
    int(Qt.Key.Key_Escape): "Esc",
    int(Qt.Key.Key_Tab): "Tab",
    int(Qt.Key.Key_Return): "Enter",
    int(Qt.Key.Key_Enter): "Enter",
    int(Qt.Key.Key_Backspace): "Backspace",
    int(Qt.Key.Key_Delete): "Delete",
    int(Qt.Key.Key_Insert): "Insert",
    int(Qt.Key.Key_Home): "Home",
    int(Qt.Key.Key_End): "End",
    int(Qt.Key.Key_PageUp): "PageUp",
    int(Qt.Key.Key_PageDown): "PageDown",
    int(Qt.Key.Key_Up): "↑",
    int(Qt.Key.Key_Down): "↓",
    int(Qt.Key.Key_Left): "←",
    int(Qt.Key.Key_Right): "→",
    int(Qt.Key.Key_Shift): "Shift",
    int(Qt.Key.Key_Control): "Ctrl",
    int(Qt.Key.Key_Alt): "Alt",
    int(Qt.Key.Key_Meta): "Win",
}


def key_text(key: int, mods: int = 0) -> str:
    """Human-readable key chord, e.g. Z / , / Ctrl+M / Shift."""
    key = int(key)
    if int(Qt.Key.Key_A) <= key <= int(Qt.Key.Key_Z):
        base = chr(ord("A") + key - int(Qt.Key.Key_A))
    elif int(Qt.Key.Key_0) <= key <= int(Qt.Key.Key_9):
        base = chr(ord("0") + key - int(Qt.Key.Key_0))
    elif int(Qt.Key.Key_F1) <= key <= int(Qt.Key.Key_F12):
        base = f"F{key - int(Qt.Key.Key_F1) + 1}"
    else:
        base = _SPECIAL.get(key, _PUNCT.get(key, f"Key{key}"))

    parts: list[str] = []
    if mods & MOD_CTRL:
        parts.append("Ctrl")
    if mods & MOD_ALT:
        parts.append("Alt")
    if mods & MOD_SHIFT:
        parts.append("Shift")
    if mods & MOD_META:
        parts.append("Win")
    return "+".join(parts + [base]) if parts else base


@dataclass(frozen=True)
class Chord:
    key: int
    mods: int = 0

    @property
    def text(self) -> str:
        return key_text(self.key, self.mods)

    def to_dict(self) -> dict:
        return {"key": self.key, "mods": self.mods}

    @classmethod
    def from_dict(cls, data) -> "Chord | None":
        if not isinstance(data, dict):
            return None
        key = data.get("key")
        mods = data.get("mods", 0)
        if not isinstance(key, int) or not isinstance(mods, int):
            return None
        if key < 0:
            return None
        return cls(key, mods & MOD_ALL)

    def note_matches(self, key: int, mods: int) -> bool:
        # Shift is the sustain hold, so a note still plays with Shift held.
        return self.key == key and (self.mods & NOTE_BLOCK) == (mods & NOTE_BLOCK)

    def function_matches(self, key: int, mods: int) -> bool:
        if self.key in MODIFIER_KEYS:
            # Pressing Shift itself: accept the modifier bit being set.
            return self.key == key
        return self.key == key and (self.mods & MOD_ALL) == (mods & MOD_ALL)


def default_path() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "keybindings.json"


class KeyBindings:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.preset = "three_row"
        self.notes: dict[int, Chord] = {}
        self.functions: dict[str, Chord] = {}
        self.reset_defaults(save=False)
        self.loaded = self.load()

    # -- defaults / persistence -----------------------------------------

    def reset_defaults(self, save: bool = True) -> None:
        self.notes = {
            index + 1: Chord(int(key))
            for index, key in enumerate(DEFAULT_NOTE_KEYS)
        }
        self.functions = {
            action: Chord(key, mods)
            for action, (key, mods) in FUNCTION_DEFAULTS.items()
        }
        self.preset = "three_row"
        if save:
            self.save()

    def to_dict(self) -> dict:
        return {
            "version": BINDINGS_VERSION,
            "preset": self.preset,
            "notes": {
                str(bar): (self.notes[bar].to_dict() if bar in self.notes else None)
                for bar in range(1, NOTE_COUNT + 1)
            },
            "functions": {
                action: (
                    self.functions[action].to_dict()
                    if action in self.functions
                    else None
                )
                for action in FUNCTION_LABELS
            },
        }

    def apply_dict(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        try:
            version = int(data.get("version", 1))
        except (TypeError, ValueError):
            version = 1
        self.reset_defaults(save=False)
        notes = data.get("notes")
        if isinstance(notes, dict):
            for bar_text, item in notes.items():
                try:
                    bar = int(bar_text)
                except (TypeError, ValueError):
                    continue
                if not 1 <= bar <= NOTE_COUNT:
                    continue
                if item is None:
                    self.notes.pop(bar, None)
                else:
                    chord = Chord.from_dict(item)
                    if chord is not None:
                        self.notes[bar] = chord
        funcs = data.get("functions")
        if isinstance(funcs, dict):
            for action, item in funcs.items():
                if action not in FUNCTION_LABELS:
                    continue
                if item is None:
                    self.functions.pop(action, None)
                else:
                    chord = Chord.from_dict(item)
                    if chord is not None:
                        self.functions[action] = chord
        if version < BINDINGS_VERSION:
            labels = self.functions.get("labels")
            if (
                labels is not None
                and labels.key == int(Qt.Key.Key_Tab)
                and labels.mods == 0
            ):
                # v1 used Tab for the label toggle; free Tab for traversal.
                self.functions["labels"] = Chord(
                    int(Qt.Key.Key_Tab), MOD_CTRL
                )
        self.preset = str(data.get("preset", "custom"))
        return True

    def load(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return self.apply_dict(data)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # -- lookup ---------------------------------------------------------

    def note_chord(self, bar: int) -> Chord | None:
        return self.notes.get(bar)

    def keycap(self, bar: int) -> str:
        chord = self.notes.get(bar)
        return chord.text if chord is not None else "—"

    def bar_for_key(self, key: int, mods: int) -> int | None:
        for bar, chord in self.notes.items():
            if chord.note_matches(key, mods):
                return bar
        return None

    def function_chord(self, action: str) -> Chord | None:
        return self.functions.get(action)

    def action_for_key(self, key: int, mods: int) -> str | None:
        for action, chord in self.functions.items():
            if chord.function_matches(key, mods):
                return action
        return None

    # -- edits ----------------------------------------------------------

    def set_note(self, bar: int, chord: Chord) -> None:
        self.notes[bar] = chord
        self.preset = "custom"
        self.save()

    def clear_note(self, bar: int) -> None:
        self.notes.pop(bar, None)
        self.preset = "custom"
        self.save()

    def set_function(self, action: str, chord: Chord) -> None:
        self.functions[action] = chord
        self.preset = "custom"
        self.save()

    def clear_function(self, action: str) -> None:
        self.functions.pop(action, None)
        self.preset = "custom"
        self.save()

    # -- conflicts ------------------------------------------------------

    def conflict_for_note(self, bar: int, chord: Chord) -> list[tuple[str, str, int | str]]:
        """[(description, kind, id)] for bindings that would clash."""
        out: list[tuple[str, str, int | str]] = []
        for other_bar, other in self.notes.items():
            if other_bar == bar:
                continue
            if other.key == chord.key and (other.mods & NOTE_BLOCK) == (chord.mods & NOTE_BLOCK):
                out.append((f"光条 {other_bar}", "note", other_bar))
        for action, other in self.functions.items():
            if other.key == chord.key and (other.mods & NOTE_BLOCK) == (chord.mods & NOTE_BLOCK):
                out.append((f"功能“{FUNCTION_LABELS[action]}”", "function", action))
        return out

    def conflict_for_function(
        self, action: str, chord: Chord
    ) -> list[tuple[str, str, int | str]]:
        out: list[tuple[str, str, int | str]] = []
        for bar, other in self.notes.items():
            if other.key == chord.key and (other.mods & NOTE_BLOCK) == (chord.mods & NOTE_BLOCK):
                out.append((f"光条 {bar}", "note", bar))
        for other_action, other in self.functions.items():
            if other_action == action:
                continue
            if other.key == chord.key and (other.mods & MOD_ALL) == (chord.mods & MOD_ALL):
                out.append(
                    (f"功能“{FUNCTION_LABELS[other_action]}”", "function", other_action)
                )
        return out

    def conflicts(self) -> list[str]:
        messages: list[str] = []
        bars = sorted(self.notes)
        for index, bar in enumerate(bars):
            for other_bar in bars[index + 1:]:
                a, b = self.notes[bar], self.notes[other_bar]
                if a.key == b.key and (a.mods & NOTE_BLOCK) == (b.mods & NOTE_BLOCK):
                    messages.append(
                        f"光条 {bar} 与光条 {other_bar} 都绑定了 {a.text}"
                    )
        for bar in bars:
            for action, chord in self.functions.items():
                note = self.notes[bar]
                if note.key == chord.key and (note.mods & NOTE_BLOCK) == (chord.mods & NOTE_BLOCK):
                    messages.append(
                        f"光条 {bar}（{note.text}）与功能“{FUNCTION_LABELS[action]}”"
                        f"（{chord.text}）冲突"
                    )
        actions = sorted(self.functions)
        for index, action in enumerate(actions):
            for other_action in actions[index + 1:]:
                a, b = self.functions[action], self.functions[other_action]
                if a.key == b.key and (a.mods & MOD_ALL) == (b.mods & MOD_ALL):
                    messages.append(
                        f"功能“{FUNCTION_LABELS[action]}”与“{FUNCTION_LABELS[other_action]}”"
                        f"都绑定了 {a.text}"
                    )
        return messages
