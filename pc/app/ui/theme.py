"""Studio / Stage themes for the P1 shell.

Colors and proportions come from pc/UI_DESIGN.md §2 and the v2 mockup
(pc/mockups/perform_studio.html). Custom-painted widgets read the Theme
object; standard widgets get the stylesheet built by Theme.qss().
"""

from __future__ import annotations

from functools import lru_cache

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QWidget


def c(hex_or_rgba, alpha: int | None = None) -> QColor:
    color = QColor(hex_or_rgba)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def rgba(color: QColor) -> str:
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"


def set_scaled_font(
    widget: QWidget,
    theme: "Theme",
    px: int,
    weight: QFont.Weight = QFont.Weight.Normal,
    mono: bool = False,
) -> None:
    """Apply a theme font and remember its design size for live rescaling."""
    widget.setProperty("designFontPx", int(px))
    widget.setProperty("designFontWeight", int(weight))
    widget.setProperty("designFontMono", bool(mono))
    widget.setFont(theme.font(px, weight, mono))


def refresh_scaled_fonts(root: QWidget, theme: "Theme") -> None:
    """Re-apply every registered font after a font-scale/theme change."""
    for widget in root.findChildren(QWidget):
        px = widget.property("designFontPx")
        if px is None:
            continue
        weight = widget.property("designFontWeight")
        mono = widget.property("designFontMono")
        widget.setFont(
            theme.font(
                int(px),
                QFont.Weight(int(weight)),
                bool(mono),
            )
        )


@lru_cache(maxsize=64)
def font(px: int, weight: QFont.Weight = QFont.Weight.Normal, mono: bool = False) -> QFont:
    if mono:
        f = QFont("Cascadia Mono")
        f.setStyleHint(QFont.StyleHint.Monospace)
        if not f.exactMatch():
            f = QFont("Consolas")
            f.setStyleHint(QFont.StyleHint.Monospace)
    else:
        f = QFont("Microsoft YaHei UI")
        if not f.exactMatch():
            f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


@dataclass(frozen=True)
class Theme:
    name: str
    dark: bool

    bg: QColor
    bg2: QColor
    ink: QColor
    muted: QColor
    faint: QColor
    amber: QColor
    amber_soft: QColor
    danger: QColor

    panel: QColor
    panel_edge: QColor
    card: QColor
    card_edge: QColor
    hair: QColor
    chip: QColor

    nav_active_bg: QColor
    nav_active_fg: QColor

    wood_hi: QColor
    wood_mid: QColor
    wood_lo: QColor
    wood_edge: QColor
    wood_line: QColor

    key_white_hi: QColor
    key_white_lo: QColor
    key_edge: QColor
    key_num: QColor
    key_note: QColor
    key_black_hi: QColor
    key_black_lo: QColor
    key_black_edge: QColor
    key_active_bg: QColor
    key_active_fg: QColor
    key_active_note: QColor
    key_glow: QColor

    wave: QColor
    wave_core: QColor

    score_ink: QColor
    score_faint: QColor
    score_measure: QColor
    score_playhead: QColor

    # Global text scale; 1.0 keeps the original sizes. Declared last so the
    # keyword construction of STUDIO/STAGE stays unchanged.
    font_scale: float = 1.0

    def px(self, size: int) -> int:
        """Scale a design-time pixel size, rounding half-up, never below 1."""
        return max(1, int(size * self.font_scale + 0.5))

    def font(
        self,
        px: int,
        weight: QFont.Weight = QFont.Weight.Normal,
        mono: bool = False,
    ) -> QFont:
        """Scaled counterpart of the module-level ``font()`` helper."""
        return font(self.px(px), weight, mono)

    def qss(self) -> str:
        ink = rgba(self.ink)
        muted = rgba(self.muted)
        faint = rgba(self.faint)
        pill_bg = f"rgba({self.ink.red()},{self.ink.green()},{self.ink.blue()},236)"
        pill_fg = rgba(self.bg)
        return f"""
QWidget {{
    color: {ink};
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
}}
QMainWindow, QWidget#Root {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#ScrollContent {{ background: transparent; }}
QFrame[glass="true"] {{
    background: {rgba(self.panel)};
    border: 1px solid {rgba(self.panel_edge)};
    border-radius: 20px;
}}
QFrame[card="true"] {{
    background: {rgba(self.card)};
    border: 1px solid {rgba(self.card_edge)};
    border-radius: 14px;
}}
QFrame[card="true"]:focus {{ border: 1px solid {rgba(self.amber)}; }}
QFrame[hair="true"] {{ background: {rgba(self.hair)}; border: none; }}
QLabel[role="muted"] {{ color: {muted}; font-size: {self.px(11)}px; }}
QLabel[role="faint"] {{ color: {faint}; font-size: {self.px(10)}px; }}
QLabel[role="label"] {{ color: {faint}; font-size: {self.px(10)}px; }}
QLabel[role="value"] {{ color: {ink}; font-size: {self.px(15)}px; font-weight: 600; }}
QLabel[role="title"] {{ color: {ink}; font-size: {self.px(16)}px; font-weight: 600; }}
QLabel[role="mono"] {{
    color: {ink};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {self.px(12)}px;
}}
QLabel[role="amber"] {{
    color: {rgba(self.amber)};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {self.px(12)}px;
}}
QLabel[role="danger"] {{ color: {rgba(self.danger)}; font-size: {self.px(12)}px; }}
QLabel[role="brand"] {{ color: {ink}; font-size: {self.px(14)}px; font-weight: 700; }}
QPushButton {{ border: none; background: transparent; color: {ink}; }}
QPushButton[role="nav"] {{
    text-align: left;
    padding: 9px 12px;
    border-radius: 10px;
    color: {muted};
    font-size: {self.px(13)}px;
}}
QPushButton[role="nav"]:hover {{ background: {rgba(self.card)}; color: {ink}; }}
QPushButton[role="nav"]:checked {{
    background: {rgba(self.nav_active_bg)};
    color: {rgba(self.nav_active_fg)};
}}
QPushButton[role="chip"] {{
    background: {rgba(self.chip)};
    border: 1px solid {rgba(self.hair)};
    border-radius: 999px;
    padding: 5px 11px;
    color: {muted};
    font-size: {self.px(11)}px;
}}
QPushButton[role="chip"]:hover {{ color: {ink}; border-color: {rgba(self.faint)}; }}
QPushButton[role="chip"]:disabled {{ color: {rgba(self.faint)}; border-color: {rgba(self.hair)}; }}
QPushButton[role="chip"]:checked {{
    background: {rgba(self.amber_soft)};
    border-color: {rgba(self.amber)};
    color: {ink};
}}
QPushButton[role="icon"] {{
    background: {rgba(self.chip)};
    border: 1px solid {rgba(self.hair)};
    border-radius: 12px;
    color: {muted};
    font-size: {self.px(13)}px;
}}
QPushButton[role="icon"]:hover {{ color: {ink}; }}
QPushButton[role="icon"]:checked {{
    background: {rgba(self.amber_soft)};
    border-color: {rgba(self.amber)};
    color: {ink};
}}
QPushButton[role="step"] {{
    background: {rgba(self.chip)};
    border: 1px solid {rgba(self.hair)};
    border-radius: 8px;
    color: {muted};
    font-size: {self.px(14)}px;
}}
QPushButton[role="step"]:hover {{ color: {ink}; border-color: {rgba(self.faint)}; }}
QPushButton[role="cardbtn"] {{ text-align: left; padding: 0; background: transparent; }}
QPushButton[role="action"] {{
    background: {rgba(self.nav_active_bg)};
    color: {rgba(self.nav_active_fg)};
    border-radius: 12px;
    padding: 8px 12px;
    font-size: {self.px(12)}px;
    font-weight: 600;
}}
QPushButton[role="danger"] {{
    background: {rgba(self.chip)};
    border: 1px solid {rgba(self.hair)};
    border-radius: 12px;
    padding: 8px 12px;
    color: {ink};
    font-size: {self.px(12)}px;
}}
QPushButton[role="tab"] {{
    color: {muted};
    font-size: {self.px(12)}px;
    padding: 6px 12px;
    border-radius: 9px;
}}
QPushButton[role="tab"]:checked {{
    background: {rgba(self.panel)};
    border: 1px solid {rgba(self.hair)};
    color: {ink};
}}
QPushButton[role="flat"] {{ color: {muted}; font-size: {self.px(11)}px; }}
QPushButton[role="flat"]:hover {{ color: {ink}; }}
QPushButton:focus {{ border: 1px solid {rgba(self.amber)}; }}
QPushButton[role="nav"]:focus {{
    background: {rgba(self.amber_soft)};
    color: {ink};
}}
QPushButton[role="chip"]:focus {{
    border: 1px solid {rgba(self.amber)};
    color: {ink};
}}
QCheckBox {{
    color: {muted};
    font-size: {self.px(11)}px;
    spacing: 8px;
}}
QCheckBox:focus {{ color: {ink}; }}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {rgba(self.faint)};
    border-radius: 4px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {rgba(self.amber)};
    border: 1px solid {rgba(self.amber)};
}}
QToolTip {{
    background: {rgba(self.nav_active_bg)};
    color: {rgba(self.nav_active_fg)};
    border: 1px solid {rgba(self.hair)};
    padding: 5px 8px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {rgba(self.hair)};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLabel#Toast {{
    background: {rgba(self.nav_active_bg)};
    color: {rgba(self.nav_active_fg)};
    border: 1px solid {rgba(self.hair)};
    border-radius: 12px;
    padding: 8px 16px;
    font-size: {self.px(12)}px;
}}
"""


STUDIO = Theme(
    name="studio",
    dark=False,
    bg=c("#EEECE6"),
    bg2=c("#F7F5EF"),
    ink=c("#121214"),
    muted=c("#6F6F69"),
    faint=c("#9B9B94"),
    amber=c("#C9963F"),
    amber_soft=c("#C9963F", 46),
    danger=c("#B94A3E"),
    panel=c("#FFFFFF", 158),
    panel_edge=c("#FFFFFF", 184),
    card=c("#FFFFFF", 107),
    card_edge=c("#121214", 20),
    hair=c("#121214", 20),
    chip=c("#FFFFFF", 115),
    nav_active_bg=c("#121214"),
    nav_active_fg=c("#F6F6F3"),
    wood_hi=c("#E4D2B3"),
    wood_mid=c("#D4BD98"),
    wood_lo=c("#C9AE86"),
    wood_edge=c("#785426", 56),
    wood_line=c("#785426", 10),
    key_white_hi=c("#FDFCF8"),
    key_white_lo=c("#E8E3D7"),
    key_edge=c("#1E1810", 56),
    key_num=c("#B9B4A7"),
    key_note=c("#5E5B52"),
    key_black_hi=c("#242427"),
    key_black_lo=c("#08080A"),
    key_black_edge=c("#060607"),
    key_active_bg=c("#131315"),
    key_active_fg=c("#F7F5EF"),
    key_active_note=c("#F1D9A8"),
    key_glow=c("#C9963F", 140),
    wave=c("#C9963F", 100),
    wave_core=c("#F6DEAE", 155),
    score_ink=c("#121214", 200),
    score_faint=c("#121214", 46),
    score_measure=c("#C9963F", 26),
    score_playhead=c("#C9963F"),
)

STAGE = Theme(
    name="stage",
    dark=True,
    bg=c("#0E0E10"),
    bg2=c("#17171A"),
    ink=c("#F6F6F3"),
    muted=c("#A6A6A0"),
    faint=c("#73736D"),
    amber=c("#D8A24A"),
    amber_soft=c("#D8A24A", 46),
    danger=c("#D0655A"),
    panel=c("#FFFFFF", 17),
    panel_edge=c("#FFFFFF", 26),
    card=c("#FFFFFF", 11),
    card_edge=c("#FFFFFF", 18),
    hair=c("#FFFFFF", 26),
    chip=c("#FFFFFF", 14),
    nav_active_bg=c("#FFFFFF", 30),
    nav_active_fg=c("#F6F6F3"),
    wood_hi=c("#4A3A25"),
    wood_mid=c("#3A2D1D"),
    wood_lo=c("#2C2216"),
    wood_edge=c("#000000", 90),
    wood_line=c("#FFFFFF", 8),
    key_white_hi=c("#F7F5EF"),
    key_white_lo=c("#DCD6C8"),
    key_edge=c("#000000", 150),
    key_num=c("#8D887B"),
    key_note=c("#4E4B44"),
    key_black_hi=c("#222225"),
    key_black_lo=c("#08080A"),
    key_black_edge=c("#000000"),
    key_active_bg=c("#141413"),
    key_active_fg=c("#F6F6F3"),
    key_active_note=c("#F1D9A8"),
    key_glow=c("#D8A24A", 150),
    wave=c("#FFFFFF", 78),
    wave_core=c("#FFFFFF", 128),
    score_ink=c("#F6F6F3", 190),
    score_faint=c("#F6F6F3", 40),
    score_measure=c("#D8A24A", 30),
    score_playhead=c("#D8A24A"),
)

THEMES = {"studio": STUDIO, "stage": STAGE}
