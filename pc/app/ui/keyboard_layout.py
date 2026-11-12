"""Default computer-keyboard note layout (UI_DESIGN_V3 §7.3).

Physical key codes, not characters: the three rows work by position under a
Chinese IME. KEYCAPS are display-only. Binding is data so a future settings
page can import/export it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

DEFAULT_NOTE_KEYS: tuple[Qt.Key, ...] = (
    # bars 1–10
    Qt.Key.Key_Z, Qt.Key.Key_X, Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_B,
    Qt.Key.Key_N, Qt.Key.Key_M, Qt.Key.Key_Comma, Qt.Key.Key_Period,
    Qt.Key.Key_Slash,
    # bars 11–21
    Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D, Qt.Key.Key_F, Qt.Key.Key_G,
    Qt.Key.Key_H, Qt.Key.Key_J, Qt.Key.Key_K, Qt.Key.Key_L,
    Qt.Key.Key_Semicolon, Qt.Key.Key_Apostrophe,
    # bars 22–32
    Qt.Key.Key_Q, Qt.Key.Key_W, Qt.Key.Key_E, Qt.Key.Key_R, Qt.Key.Key_T,
    Qt.Key.Key_Y, Qt.Key.Key_U, Qt.Key.Key_I, Qt.Key.Key_O, Qt.Key.Key_P,
    Qt.Key.Key_BracketLeft,
)

KEYCAPS: tuple[str, ...] = (
    "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/",
    "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'",
    "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[",
)

# (start, end) slices into DEFAULT_NOTE_KEYS / KEYCAPS.
KEY_ROWS: tuple[tuple[int, int], ...] = ((0, 10), (10, 21), (21, 32))

KEY_TO_BAR: dict[Qt.Key, int] = {
    key: index + 1 for index, key in enumerate(DEFAULT_NOTE_KEYS)
}
