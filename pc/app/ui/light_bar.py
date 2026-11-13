"""v3 light-bar performance band (C "curtain" variant) + hint band.

Verdict from pc/prototype (2026-11-01): C won — one continuous semi-transparent
curtain, no piano geometry, colour only on press, note labels on press, and a
flatter band than the 64 px spec (52 px total / 32 px slots).

Mouse notes are gone by design. The four function capsules may be clicked;
the 32 slots never produce a note from the mouse. Pressed state and light
columns come from Instrument (hardware serial + computer keyboard).
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QToolTip, QWidget

from ..core.mapping import KEY_COUNT
from ..core.note_engine import is_black_key
from .i18n_ui import tr
from .theme import Theme

KEY_COUNT = 32
BAND_HEIGHT = 52
SLOT_HEIGHT = 32
WAVE_MS = 650.0
FADE_MS = 160.0

PILL_TITLES = ("延音", "八度−", "八度+", "映射")
PILL_ACTIONS = ("sustain", "oct_down", "oct_up", "map")
PILL_HELP = (
    "延音：按住时松开的音继续响（Shift 同样有效）",
    "八度 −：整体降一个八度（Ctrl+[）",
    "八度 +：整体升一个八度（Ctrl+]）",
    "映射：循环音域映射预设（Ctrl+M）",
)


def _split_boundary_bar(instrument) -> int | None:
    """Last left-side bar when the current mapping is split, else None."""
    split = instrument.current_preset.split
    if split is None or not 0 < split.bar < KEY_COUNT:
        return None
    return split.bar


def with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, alpha)))
    return out


def pitch_color(midi: int, theme: Theme) -> QColor:
    """12 pitch classes → 12 hues; brightness follows the octave."""
    hue = int(((midi % 12) * 30 + 40) % 360)
    sat = 168 if theme.dark else 182
    val = 255 if theme.dark else 214
    return QColor.fromHsv(hue, sat, val)


SPLIT_GRAB_PX = 9.0


class LightBarBand(QWidget):
    """The 32-slot C curtain, with four function capsules above the right end."""

    function = Signal(str, bool)  # action, down
    splitBarDragged = Signal(int)    # live bar while dragging the amber line
    splitBarCommitted = Signal(int)  # final bar on release

    def __init__(self, theme: Theme, instrument, bindings, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self._active: set[int] = set()
        self._sustain = False
        self._labels_on = False
        self._next_key: int | None = None
        self._hover: tuple[str, int] | None = None
        self._pill_down: int | None = None
        self._release_at: dict[int, float] = {}
        self._wrong_bar: int | None = None
        self._wrong_until = 0.0
        self._hit_bar: int | None = None
        self._hit_until = 0.0
        self._last_tooltip = ""
        self._project_split_bar: int | None = None
        self._split_drag_bar: int | None = None
        self._reduce_motion = False

        self.setFixedHeight(BAND_HEIGHT)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # -- state ----------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_active(self, keys: set[int]) -> None:
        now = time.monotonic()
        for bar in self._active - set(keys):
            self._release_at[bar] = now
        self._active = set(keys)
        if self._active or self._release_at or self._next_key is not None:
            self._timer.start()
        self.update()

    def set_sustain(self, on: bool) -> None:
        if self._sustain != on:
            self._sustain = on
            self.update()

    def set_labels(self, on: bool) -> None:
        self._labels_on = on
        self.update()

    def set_reduce_motion(self, on: bool) -> None:
        self._reduce_motion = bool(on)
        self.update()

    @property
    def reduce_motion(self) -> bool:
        return self._reduce_motion

    @property
    def labels_on(self) -> bool:
        return self._labels_on

    def set_next_key(self, bar: int | None) -> None:
        self._next_key = bar
        if bar is not None:
            self._timer.start()
        self.update()

    def split_boundary_bar(self) -> int | None:
        """Last left-side bar when the current mapping is split, else None."""
        return _split_boundary_bar(self.instrument)

    @property
    def project_split_bar(self) -> int | None:
        return self._project_split_bar

    def set_split_bar(self, bar: int | None) -> None:
        value = bar if bar is not None and 0 < bar < KEY_COUNT else None
        if value != self._project_split_bar:
            self._project_split_bar = value
            self.update()

    def flash_wrong(self, bar: int) -> None:
        self._wrong_bar = bar
        self._wrong_until = time.monotonic() + 0.45
        self._hit_bar = None
        self._timer.start()
        self.update()

    def flash_hit(self, bar: int) -> None:
        self._hit_bar = bar
        self._hit_until = time.monotonic() + 0.45
        self._wrong_bar = None
        self._timer.start()
        self.update()

    def feedback_marker(self, bar: int) -> str:
        """Non-colour success/failure cue for one slot ("×" / "✓" / "")."""
        now = time.monotonic()
        if self._wrong_bar == bar and now < self._wrong_until:
            return "×"
        if self._hit_bar == bar and now < self._hit_until:
            return "✓"
        return ""

    def _tick(self) -> None:
        now = time.monotonic()
        for bar, started in list(self._release_at.items()):
            if now - started > FADE_MS / 1000:
                del self._release_at[bar]
        if (
            not self._active
            and not self._release_at
            and self._next_key is None
            and now >= self._wrong_until
            and now >= self._hit_until
        ):
            self._timer.stop()
        self.update()

    # -- geometry -------------------------------------------------------

    def _slot_rects(self) -> list[QRectF]:
        gap = 1.0
        width = (self.width() - gap * 31) / KEY_COUNT
        top = float(self.height() - SLOT_HEIGHT)
        return [
            QRectF(i * (width + gap), top, width, SLOT_HEIGHT)
            for i in range(KEY_COUNT)
        ]

    def slot_rect(self, bar: int) -> QRectF | None:
        if not 1 <= bar <= KEY_COUNT:
            return None
        return self._slot_rects()[bar - 1]

    def _pill_rects(self) -> list[QRectF]:
        width = 35.0
        gap = 3.0
        x0 = self.width() - (4 * width + 3 * gap)
        return [QRectF(x0 + i * (width + gap), 2, width, 16) for i in range(4)]

    def _midi(self, bar: int) -> int:
        # Drum mode colours pads by their GM percussion note, not by the
        # melody mapping.
        return max(0, min(127, self.instrument.display_midi(bar)))

    def _note(self, bar: int) -> str:
        return self.instrument.note_for_key(bar)

    # -- painting -------------------------------------------------------

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        now = time.monotonic()
        rects = self._slot_rects()
        top = self.height() - SLOT_HEIGHT

        # the continuous curtain
        strip = QRectF(0, top, self.width(), SLOT_HEIGHT)
        p.setBrush(with_alpha(QColor(255, 255, 255), 14 if not t.dark else 10))
        p.setPen(QPen(t.hair, 0.9))
        p.drawRoundedRect(strip, 6, 6)

        p.setPen(QPen(with_alpha(t.hair, 140), 0.8))
        for rect in rects[1:]:
            p.drawLine(
                QPointF(rect.left() - 0.5, rect.top() + 5),
                QPointF(rect.left() - 0.5, rect.bottom() - 5),
            )

        split_bar = self.split_boundary_bar()
        if split_bar is not None:
            left, right = rects[split_bar - 1], rects[split_bar]
            x = (left.right() + right.left()) / 2
            p.setPen(QPen(t.amber, 2.0))
            p.drawLine(
                QPointF(x, top + 3), QPointF(x, top + SLOT_HEIGHT - 3)
            )
            # A small grip makes it obvious that the amber boundary is
            # draggable instead of just a 1 px decoration.
            grip = QRectF(
                x - 4.5, top + SLOT_HEIGHT / 2 - 8, 9, 16
            )
            p.setPen(QPen(with_alpha(t.amber, 220), 1.0))
            p.setBrush(with_alpha(t.amber, 55))
            p.drawRoundedRect(grip, 3, 3)
            p.setPen(QPen(with_alpha(t.amber, 220), 1.0))
            for dx in (-1.8, 1.8):
                p.drawLine(
                    QPointF(x + dx, grip.top() + 4),
                    QPointF(x + dx, grip.bottom() - 4),
                )

        project_bar = self._project_split_bar
        if project_bar is not None:
            left, right = rects[project_bar - 1], rects[project_bar]
            x = (left.right() + right.left()) / 2
            p.setPen(QPen(t.danger, 1.4))
            p.drawLine(
                QPointF(x, top + 2), QPointF(x, top + SLOT_HEIGHT - 2)
            )

        breath = (
            1.0
            if self._reduce_motion
            else 0.5 + 0.5 * math.sin(now * 2 * math.pi / 1.2)
        )
        for i, rect in enumerate(rects):
            bar = i + 1
            if not self.instrument.key_enabled(bar):
                # The current mapping leaves this slot silent. Keep the slot
                # geometry (the hardware still has 32 bars) but drop pitch
                # color, labels, hover and next-key decorations.
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(
                    with_alpha(t.card, 80 if not t.dark else 55)
                )
                p.drawRect(rect)
                if self._labels_on and rect.width() >= 14:
                    p.setPen(with_alpha(t.faint, 130))
                    p.setFont(self._theme.font(9, QFont.Weight.Medium, mono=True))
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
                continue
            midi = self._midi(bar)
            if is_black_key(midi):
                # A clear black-key marker: a top-down shade plus a dot.
                # The C curtain stays equal-width; this is orientation only.
                shade = QColor(0, 0, 0) if t.dark else t.ink
                top_alpha = 72 if t.dark else 52
                wash = QLinearGradient(0, rect.top(), 0, rect.bottom())
                wash.setColorAt(0.0, with_alpha(shade, top_alpha))
                wash.setColorAt(0.65, with_alpha(shade, top_alpha // 3))
                wash.setColorAt(1.0, with_alpha(shade, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(wash)
                p.drawRect(rect)
                p.setBrush(with_alpha(t.faint, 245))
                p.drawEllipse(
                    QPointF(rect.center().x(), rect.top() + 4.2), 2.1, 2.1
                )
            down = bar in self._active
            released = self._release_at.get(bar)
            fade = 0.0
            if released is not None and not self._reduce_motion:
                fade = max(0.0, 1.0 - (now - released) / (FADE_MS / 1000))
            color = pitch_color(midi, t)

            if self._hover == ("bar", bar) and not down:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(with_alpha(QColor(255, 255, 255), 18 if not t.dark else 12))
                p.drawRect(rect)

            strength = 1.0 if down else fade
            if strength > 0.0:
                p.setPen(QPen(with_alpha(color, int(235 * strength)), 2.0))
                p.drawLine(
                    QPointF(rect.left() + 1, rect.top() + 1),
                    QPointF(rect.right() - 1, rect.top() + 1),
                )
                wash = QLinearGradient(0, rect.top(), 0, rect.bottom())
                wash.setColorAt(0.0, with_alpha(color, int(78 * strength)))
                wash.setColorAt(0.45, with_alpha(color, int(24 * strength)))
                wash.setColorAt(1.0, with_alpha(color, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(wash)
                p.drawRect(rect)

            if self._labels_on and rect.width() >= 14:
                p.setPen(with_alpha(t.faint, 225))
                p.setFont(self._theme.font(7, QFont.Weight.Medium, mono=True))
                p.drawText(
                    QRectF(rect.left(), rect.top() + 2, rect.width(), 10),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    self.bindings.keycap(bar),
                )
                p.setPen(with_alpha(t.muted, 235))
                p.setFont(self._theme.font(8, QFont.Weight.Medium, mono=True))
                p.drawText(
                    QRectF(rect.left(), rect.bottom() - 14, rect.width(), 11),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    self._note(bar),
                )

            if down:
                self._draw_press_label(p, rect, bar, with_alpha(t.ink, 240))

            if self._next_key == bar:
                pen = QPen(with_alpha(t.amber, int(70 + 150 * breath)), 2.0)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
                self._draw_press_label(
                    p, rect, bar, with_alpha(t.amber, int(110 + 100 * breath))
                )

            marker = self.feedback_marker(bar)
            if marker:
                # Shape + text carry the verdict; red/amber is only secondary.
                color = t.danger if marker == "×" else t.amber
                style = (
                    Qt.PenStyle.DashLine
                    if marker == "×"
                    else Qt.PenStyle.SolidLine
                )
                p.setPen(QPen(with_alpha(color, 230), 2.0, style))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
                p.setPen(with_alpha(color, 245))
                p.setFont(self._theme.font(13, QFont.Weight.Bold))
                p.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignHCenter
                    | Qt.AlignmentFlag.AlignVCenter,
                    marker,
                )

        for index, rect in enumerate(self._pill_rects()):
            self._draw_pill(p, rect, index)
        p.end()

    def _draw_press_label(self, p: QPainter, rect: QRectF, bar: int, color: QColor) -> None:
        label = QRectF(rect.center().x() - 28, 0, 56, 17)
        pills = self._pill_rects()
        if pills and label.right() > pills[0].left() - 4:
            label.moveRight(pills[0].left() - 6)
        p.setPen(color)
        p.setFont(self._theme.font(8, QFont.Weight.DemiBold, mono=True))
        p.drawText(
            label,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._note(bar),
        )

    def _draw_pill(self, p: QPainter, rect: QRectF, index: int) -> None:
        t = self._theme
        on = index == 0 and self._sustain
        fill = with_alpha(t.amber, 62) if on else with_alpha(t.card, 190)
        edge = with_alpha(t.amber, 220) if on else t.hair
        p.setBrush(fill)
        p.setPen(QPen(edge, 1.0))
        p.drawRoundedRect(rect, 5, 5)
        p.setPen(t.ink)
        p.setFont(self._theme.font(8, QFont.Weight.DemiBold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr(PILL_TITLES[index]))

    # -- mouse: capsules only, never notes ------------------------------

    def _pill_at(self, pos: QPointF) -> int | None:
        for index, rect in enumerate(self._pill_rects()):
            if rect.contains(pos):
                return index
        return None

    def _bar_at(self, pos: QPointF) -> int | None:
        for index, rect in enumerate(self._slot_rects()):
            if rect.contains(pos):
                return index + 1
        return None

    def split_line_x(self, bar: int | None = None) -> float | None:
        """X of the amber split line, or None when the mapping is not split."""
        split = self.instrument.current_preset.split
        if split is None:
            return None
        value = max(1, min(KEY_COUNT - 1, split.bar if bar is None else bar))
        rects = self._slot_rects()
        return (rects[value - 1].right() + rects[value].left()) / 2

    def _bar_after_x(self, x: float) -> int:
        """Nearest split boundary (1..31) for a pointer x."""
        for index, rect in enumerate(self._slot_rects()):
            if x < rect.center().x():
                return max(1, min(KEY_COUNT - 1, index + 1))
        return KEY_COUNT - 1

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self._pill_at(event.position())
        if index is not None:
            self._pill_down = index
            if index == 0:
                self.function.emit("sustain", True)
            else:
                self.function.emit(PILL_ACTIONS[index], True)
            event.accept()
            return
        line = self.split_line_x()
        if line is not None and abs(event.position().x() - line) <= SPLIT_GRAB_PX:
            self._split_drag_bar = self.instrument.split_bar
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            event.accept()
            return
        event.ignore()  # clicking a bar deliberately does nothing

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._split_drag_bar is not None:
            bar = self._split_drag_bar
            self._split_drag_bar = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.splitBarCommitted.emit(bar)
            event.accept()
            return
        if self._pill_down == 0:
            self.function.emit("sustain", False)
        self._pill_down = None
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._split_drag_bar is not None:
            bar = self._bar_after_x(event.position().x())
            if bar != self._split_drag_bar:
                self._split_drag_bar = bar
                self.splitBarDragged.emit(bar)
            event.accept()
            return

        line = self.split_line_x()
        near_line = (
            line is not None
            and abs(event.position().x() - line) <= SPLIT_GRAB_PX
        )
        self.setCursor(
            Qt.CursorShape.SizeHorCursor
            if near_line
            else Qt.CursorShape.ArrowCursor
        )

        pill = self._pill_at(event.position())
        bar = self._bar_at(event.position())
        hover = (
            ("pill", pill)
            if pill is not None
            else (("bar", bar) if bar is not None else None)
        )
        if hover != self._hover:
            self._hover = hover
            self.update()

        if near_line:
            text = (
                f"分区 {self.instrument.split_bar} · 拖动调整左右手音域"
                "（松手按曲目保存）"
            )
        elif pill is not None:
            text = PILL_HELP[pill]
        elif bar is not None:
            split = self.instrument.current_preset.split
            split_bar = split.bar if split is not None else 16
            if self.instrument.drums_enabled:
                hand = "鼓垫"
            else:
                hand = "左手" if bar <= split_bar else "右手"
            keycap = self.bindings.keycap(bar)
            key_text = f"电脑键 {keycap}" if keycap != "—" else "电脑键未绑定"
            if not self.instrument.key_enabled(bar):
                text = (
                    f"光条 {bar} · 当前映射禁用此键 · {key_text}"
                    "（按键不发声）"
                )
            else:
                text = (
                    f"光条 {bar} · {self._note(bar)} · {key_text} · "
                    f"{hand}（点击不发声）"
                )
        else:
            text = ""
        if text and text != self._last_tooltip:
            self._last_tooltip = text
            QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def leaveEvent(self, event) -> None:
        self._hover = None
        self._last_tooltip = ""
        self.update()
        super().leaveEvent(event)


class HintBand(QWidget):
    """Top 32-cell display strip: pressed keys + the next key from the score."""

    def __init__(self, theme: Theme, instrument, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self._active: set[int] = set()
        self._next_key: int | None = None
        self.setFixedHeight(28)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_active(self, keys: set[int]) -> None:
        self._active = set(keys)
        self.update()

    def set_next_key(self, bar: int | None) -> None:
        self._next_key = bar
        self.update()

    def split_boundary_bar(self) -> int | None:
        """Last left-side bar when the current mapping is split, else None."""
        return _split_boundary_bar(self.instrument)

    def paintEvent(self, event) -> None:
        t = self._theme
        w, h = self.width(), self.height()
        if w <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        gap = 2.0
        cell_w = (w - gap * 31) / 32
        y = (h - 20) / 2
        preset = self.instrument.current_preset
        for index in range(32):
            bar = index + 1
            rect = QRectF(index * (cell_w + gap), y, cell_w, 20)
            if bar in self._active:
                midi = max(0, min(127, preset.midi_for_key(bar) + self.instrument.offset))
                color = pitch_color(midi, t)
                p.setBrush(with_alpha(color, 150))
                p.setPen(QPen(with_alpha(color, 220), 1))
            elif not self.instrument.key_enabled(bar):
                p.setBrush(with_alpha(t.card, 70))
                p.setPen(QPen(with_alpha(t.hair, 120), 0.8))
            else:
                p.setBrush(with_alpha(t.card, 120))
                p.setPen(QPen(t.hair, 0.8))
            p.drawRoundedRect(rect, 3, 3)
            if self._next_key == bar:
                p.setPen(QPen(t.amber, 1.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(0.8, 0.8, -0.8, -0.8), 3, 3)
        split_bar = self.split_boundary_bar()
        if split_bar is not None:
            x = split_bar * (cell_w + gap) - gap / 2
            p.setPen(QPen(t.amber, 1))
            p.drawLine(QPointF(x, y - 3), QPointF(x, y + 23))
        p.end()


class LightColumnOverlay(QWidget):
    """Transparent light-column layer above the band; never takes layout/mouse."""

    def __init__(self, parent: QWidget, band: LightBarBand):
        super().__init__(parent)
        self._band = band
        self._theme: Theme = band._theme
        self._columns: list[tuple[int, QColor, float]] = []
        self._reduce_motion = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme

    def set_reduce_motion(self, on: bool) -> None:
        self._reduce_motion = bool(on)
        if self._reduce_motion:
            self._columns.clear()
            self._timer.stop()
            self.update()

    @property
    def reduce_motion(self) -> bool:
        return self._reduce_motion

    @property
    def active_columns(self) -> int:
        return len(self._columns)

    def spawn(self, bar: int) -> None:
        if self._reduce_motion:
            return
        self._columns.append(
            (bar, pitch_color(self._band._midi(bar), self._theme), time.monotonic())
        )
        self._columns = self._columns[-24:]
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self) -> None:
        now = time.monotonic()
        self._columns = [
            column for column in self._columns if now - column[2] < WAVE_MS / 1000
        ]
        if not self._columns:
            self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        if not self._columns or self.height() <= 0:
            return
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Plus
            if self._theme.dark
            else QPainter.CompositionMode.CompositionMode_SourceOver
        )
        for bar, color, started in self._columns:
            progress = (now - started) / (WAVE_MS / 1000)
            if progress >= 1:
                continue
            slot = self._band.slot_rect(bar)
            if slot is None:
                continue
            # The overlay is a sibling of the band, so map through global
            # coordinates (QWidget.mapTo needs an ancestor as the target).
            global_pt = self._band.mapToGlobal(QPoint(int(slot.center().x()), 0))
            x = self.mapFromGlobal(global_pt).x()
            bottom = self.height() - 1
            height = 70 + 155 * min(1.0, progress * 2.4)
            top = bottom - height
            fade = max(0.0, 1.0 - progress) ** 1.35
            base = slot.width()

            for width_f, strength in ((1.55, 0.16), (1.05, 0.38), (0.46, 0.88)):
                width = max(3.0, base * width_f)
                grad = QLinearGradient(0, top, 0, bottom)
                glow = with_alpha(color, int(255 * fade * strength))
                grad.setColorAt(0.0, with_alpha(color, 0))
                grad.setColorAt(0.55, glow)
                grad.setColorAt(1.0, glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                path = QPainterPath()
                path.moveTo(x - width / 2, bottom)
                path.lineTo(x - width / 2, top + width / 2)
                path.quadTo(x, top - width / 3, x + width / 2, top + width / 2)
                path.lineTo(x + width / 2, bottom)
                path.closeSubpath()
                p.drawPath(path)
        p.end()
