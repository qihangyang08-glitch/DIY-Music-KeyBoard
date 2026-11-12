"""Rhythm timeline widget: bars, beats, note blocks, playhead and feedback."""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.rhythm import RhythmSession, RhythmSpec
from .light_bar import with_alpha
from .theme import Theme


def _duration_label(beats: float, is_rest: bool = False) -> str:
    if is_rest:
        return "休"
    labels = {
        0.25: "¼",
        0.5: "½",
        0.75: "½·",
        1.0: "1",
        1.5: "1·",
        2.0: "2",
        3.0: "3",
        4.0: "4",
    }
    for value, label in labels.items():
        if abs(beats - value) < 1e-6:
            return label
    return f"{beats:g}"


class RhythmCanvas(QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._spec: RhythmSpec | None = None
        self._session: RhythmSession | None = None
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName("节奏型时间线")
        self.setAccessibleDescription("显示小节、拍点、节奏块、休止与命中状态")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_spec(self, spec: RhythmSpec | None) -> None:
        self._spec = spec
        self.update()

    def set_session(self, session: RhythmSession | None) -> None:
        self._session = session
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        spec = self._spec
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if spec is None:
            p.end()
            return

        area = QRectF(self.rect()).adjusted(14, 8, -14, -8)
        if area.width() < 260 or area.height() < 90:
            p.end()
            return

        left = area.left() + 10
        right = area.right() - 10
        total_beats = spec.total_beats
        beat_w = (right - left) / total_beats
        top = area.top() + 34
        bottom = area.bottom() - 26
        block_y = top + 18
        block_h = max(26.0, min(42.0, bottom - block_y - 8))

        # beat and bar grid
        for beat in range(int(total_beats) + 1):
            x = left + beat * beat_w
            is_bar = beat % spec.beats_per_bar == 0
            p.setPen(
                QPen(
                    with_alpha(t.score_measure, 150 if is_bar else 55),
                    1.2 if is_bar else 0.7,
                )
            )
            p.drawLine(QPointF(x, top - 4), QPointF(x, bottom + 4))
        p.setPen(QPen(with_alpha(t.score_faint, 120), 0.8))
        p.drawLine(QPointF(left, block_y + block_h + 10), QPointF(right, block_y + block_h + 10))

        # bar numbers and beat numbers
        p.setFont(self._theme.font(8, QFont.Weight.Medium, mono=True))
        for bar in range(spec.bars):
            x = left + bar * spec.beats_per_bar * beat_w
            p.setPen(t.faint)
            p.drawText(
                QRectF(x + 3, top - 20, 54, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{bar + 1}",
            )
        for beat in range(int(total_beats)):
            x = left + beat * beat_w
            p.setPen(with_alpha(t.faint, 150))
            p.drawText(
                QRectF(x, bottom - 2, beat_w, 14),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                f"{beat % spec.beats_per_bar + 1}",
            )

        session = self._session
        now = time.monotonic()
        pos = session.position_beats(now) if session is not None else -999.0
        for rhythm_event in spec.events:
            idx = rhythm_event.index
            x = left + rhythm_event.beat * beat_w + 2
            w = max(12.0, rhythm_event.duration * beat_w - 4)
            rect = QRectF(x, block_y, w, block_h)
            is_rest = rhythm_event.rest
            hit = bool(not is_rest and session is not None and session.hit[idx])
            missed = bool(
                not is_rest and session is not None and session.missed[idx]
            )
            if is_rest:
                p.setBrush(with_alpha(QColor(t.card), 90))
                pen = QPen(with_alpha(t.hair, 170), 0.9)
                pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
            elif hit:
                p.setBrush(with_alpha(QColor(t.amber), 150))
                p.setPen(QPen(t.amber, 1.4))
            elif missed:
                p.setBrush(with_alpha(QColor(t.danger), 38))
                p.setPen(QPen(t.danger, 1.3))
            else:
                p.setBrush(with_alpha(QColor(t.card), 170))
                p.setPen(QPen(t.hair, 0.9))
            p.drawRoundedRect(rect, 5, 5)

            p.setFont(self._theme.font(10, QFont.Weight.DemiBold, mono=True))
            if is_rest:
                p.setPen(with_alpha(t.faint, 210))
                label = _duration_label(rhythm_event.duration, is_rest=True)
            elif hit:
                p.setPen(t.ink)
                label = "✓"
            elif missed:
                p.setPen(t.danger)
                label = "漏"
            else:
                p.setPen(t.muted)
                label = _duration_label(rhythm_event.duration)
            p.drawText(
                rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        # playhead
        if session is not None and session.started_at is not None:
            display_pos = max(0.0, min(total_beats, pos))
            x = left + display_pos * beat_w
            p.setPen(QPen(t.score_playhead, 1.6))
            p.drawLine(QPointF(x, top - 8), QPointF(x, bottom + 8))
            p.setBrush(t.score_playhead)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x - 3.5, top - 12, 7, 7))

            # metronome pulse: a soft ring that fades after each click
            if session.last_click_at is not None:
                age = max(0.0, now - session.last_click_at)
                if age < 0.22:
                    fade = 1.0 - age / 0.22
                    color = QColor(t.amber)
                    color.setAlpha(int(180 * fade))
                    p.setPen(QPen(color, 1.6))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    radius = 8 + 14 * (1.0 - fade)
                    p.drawEllipse(QRectF(x - radius, top - 24 - radius, radius * 2, radius * 2))

        # Ready/count-in text lives in the page's prompt and status rows; the
        # canvas keeps the bar/beat grid unobstructed.

        # last press feedback
        if session is not None and session.last_press is not None:
            press = session.last_press
            if press.hit:
                text = f"✓ 偏差 {press.error_ms:+d} ms"
                color = t.amber
            else:
                text = "多按"
                color = t.danger
            p.setFont(self._theme.font(10, QFont.Weight.DemiBold, mono=True))
            p.setPen(color)
            p.drawText(
                QRectF(left, bottom + 10, right - left, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
        p.end()
