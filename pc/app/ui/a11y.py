"""Screen-reader labels for the widget tree (A7).

Qt derives a button's accessible name from its visible text, which is fine for
"演奏" and useless for "?" or "⋯". This helper fills only the gaps: widgets
with an explicit ``setAccessibleName`` keep it, text buttons keep their text
(minus leading glyphs), and icon-only controls fall back to their tooltip. The
window calls it on every page switch so lazily built widgets are covered.
"""

from __future__ import annotations

import string
import unicodedata

from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QWidget,
)

# Glyphs used as leading decoration on otherwise textual buttons.
_LEADING_GLYPHS = "▶✦♬✎▣⚙●◆■✚＋−↺↻♩?⋯"


def meaningful_text(text: str) -> bool:
    """True when ``text`` carries a word, digit or CJK character."""
    for char in text:
        if char.isalnum():
            return True
        if unicodedata.category(char).startswith("L"):
            return True
    return False


def _clean(text: str) -> str:
    stripped = text.strip()
    while stripped and (
        stripped[0] in _LEADING_GLYPHS
        or stripped[0] in string.punctuation
        or stripped[0].isspace()
    ):
        stripped = stripped[1:].lstrip()
    return stripped


def _name_for(widget: QWidget) -> str:
    tooltip = widget.toolTip().strip()
    if isinstance(widget, (QLabel, QGroupBox)):
        text = widget.text().strip()
        return text if meaningful_text(text) else tooltip
    if isinstance(widget, QLineEdit):
        return widget.placeholderText().strip() or tooltip
    if isinstance(widget, QComboBox):
        return widget.currentText().strip() or tooltip
    if isinstance(widget, QAbstractButton):
        text = _clean(widget.text())
        if text and meaningful_text(text):
            return text
        return tooltip or widget.text().strip()
    return tooltip


def ensure_accessible_names(root: QWidget) -> None:
    """Name every interactive child that lacks an accessible name."""
    for widget in [root, *root.findChildren(QWidget)]:
        if not widget.accessibleName().strip():
            name = _name_for(widget)
            if name:
                widget.setAccessibleName(name)
        tooltip = widget.toolTip().strip()
        if (
            tooltip
            and not widget.accessibleDescription().strip()
            and tooltip != widget.accessibleName().strip()
        ):
            widget.setAccessibleDescription(tooltip)


__all__ = ["ensure_accessible_names", "meaningful_text"]
