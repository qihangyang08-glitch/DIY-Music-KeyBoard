"""Score container: image scores, a self-drawn staff, and a parsed piano roll.

The sheet tab hosts an image or draws a parsed score as a staff (systems of
measures, clefs, key/time signatures, accidentals, playhead); the 落键 tab
draws the real notes, playhead, current/next highlight and auto-scrolls with
the follow session. Drop a PNG/JPG for an image score, or MusicXML/MIDI to
parse it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.note_engine import midi_name
from ..core.score import Score, ScoreNote
from ..core.staff import (
    FLAT_ORDER,
    SHARP_ORDER,
    StaffLayout,
    StaffNote,
    build_staff_layout,
)
from .i18n_ui import language, tr
from .theme import Theme, font
from .widgets import GlassFrame


def with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, alpha)))
    return out


class ScoreCanvas(QWidget):
    pageChanged = Signal(int)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._mode = "sheet"
        self._zoom = 1.0
        self._page = 0
        self._playing = False
        self._progress = 0.0
        self._pixmap: Optional[QPixmap] = None
        self._pixmap_name = ""
        self._score: Optional[Score] = None
        self._layout: Optional[StaffLayout] = None
        self._follow_position = 0.0
        self._expected_index = 0
        self._hits = 0
        self._misses = 0
        self._next_note: Optional[ScoreNote] = None
        self._follow_playing = False
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    @property
    def has_score(self) -> bool:
        return self._score is not None

    def set_score(self, score: Score) -> None:
        self._timer.stop()
        self._playing = False
        self._score = score
        self._pixmap = None
        self._layout = build_staff_layout(
            score,
            measures_per_system=4 if score.measure_count <= 8 else 8,
        )
        self._page = 0
        self._mode = "roll"
        self._follow_position = score.notes[0].start if score.notes else 0.0
        self._expected_index = 0
        self._hits = 0
        self._misses = 0
        self._next_note = score.notes[0] if score.notes else None
        self.update()

    def set_follow_state(
        self,
        position: float,
        expected_index: int,
        hits: int,
        misses: int,
        playing: bool,
        next_note: Optional[ScoreNote],
    ) -> None:
        self._follow_position = position
        self._expected_index = expected_index
        self._hits = hits
        self._misses = misses
        self._follow_playing = playing
        self._next_note = next_note
        if self._layout is not None and self._layout.systems:
            self.set_page(self._page_for_position(position))
        self.update()

    # -- sheet pagination -------------------------------------------------

    SYSTEMS_PER_PAGE = 2

    @property
    def page(self) -> int:
        return self._page

    @property
    def page_count(self) -> int:
        if self._layout is None or not self._layout.systems:
            return 1
        count = len(self._layout.systems)
        return max(1, (count + self.SYSTEMS_PER_PAGE - 1) // self.SYSTEMS_PER_PAGE)

    def _page_for_position(self, position: float) -> int:
        if self._layout is None or not self._layout.systems:
            return 0
        system, _ = self._layout.playhead(position)
        return min(
            max(0, system // self.SYSTEMS_PER_PAGE),
            self.page_count - 1,
        )

    def set_page(self, page: int) -> None:
        page = max(0, min(int(page), self.page_count - 1))
        if page == self._page:
            return
        self._page = page
        self.pageChanged.emit(page)
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.75, min(1.35, zoom))
        self.update()

    def clear_score(self) -> None:
        self._score = None
        self._layout = None
        self._page = 0
        self._timer.stop()
        self._playing = False
        self._follow_position = 0.0
        self._next_note = None
        self.update()

    def set_image(self, path: Path) -> bool:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        self._pixmap = pixmap
        self._pixmap_name = path.name
        self.update()
        return True

    def clear_image(self) -> None:
        self._pixmap = None
        self._pixmap_name = ""
        self.update()

    @property
    def has_image(self) -> bool:
        return self._pixmap is not None

    def toggle_play(self) -> bool:
        if self._pixmap is not None:
            return False
        self._playing = not self._playing
        if self._playing:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()
        return self._playing

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        if playing and self._pixmap is None:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _advance(self) -> None:
        self._progress += 0.0018
        if self._progress >= 1.0:
            self._progress = 0.0
        self.update()

    # -- painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self._pixmap is not None:
            self._draw_image(p)
        elif self._mode == "roll":
            self._draw_roll(p)
        elif self._score is not None:
            self._draw_staff_score(p)
        else:
            self._draw_sheet(p)

        # Bottom fade into the keyboard area (UI_DESIGN §4.2). Use the page
        # tone, not the translucent panel color: in Stage the latter is a
        # translucent white and would paint a grey band over the dark card.
        # The parsed roll keeps its bottom status line visible.
        if not (self._score is not None and self._mode == "roll"):
            fade_h = min(78.0, max(50.0, self.height() * 0.17))
            fade = QLinearGradient(0, self.height() - fade_h, 0, self.height())
            top = QColor(self._theme.bg2)
            top.setAlpha(0)
            bottom = QColor(self._theme.bg2)
            bottom.setAlpha(225)
            fade.setColorAt(0, top)
            fade.setColorAt(1, bottom)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fade)
            p.drawRect(QRectF(0, self.height() - fade_h, self.width(), fade_h))
        p.end()

    def _draw_image(self, p: QPainter) -> None:
        t = self._theme
        if self._pixmap is None:
            return
        area = QRectF(self.rect()).adjusted(20, 10, -20, -12)
        scaled = self._pixmap.scaled(
            area.size().toSize(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = area.center().x() - scaled.width() / 2
        y = area.center().y() - scaled.height() / 2
        target = QRectF(x, y, scaled.width(), scaled.height())
        path = QPainterPath()
        path.addRoundedRect(target, 6, 6)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(target.toRect(), scaled)
        p.restore()
        p.setPen(QPen(t.hair, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(target, 6, 6)

    def _draw_sheet(self, p: QPainter) -> None:
        t = self._theme
        p.save()
        p.scale(self._zoom, self._zoom)
        w = self.width() / self._zoom
        h = self.height() / self._zoom
        left, right = 40.0, w - 26.0
        if right - left < 200:
            left, right = 16.0, max(220.0, w - 16.0)
        measure_w = (right - left) / 4
        compact = h < 360
        system_tops = [18.0, max(135.0, h * 0.58)] if compact else [22.0, max(190.0, h * 0.56)]
        staff_gap = 9.0 if compact else 12.0
        staff_h = 24.0 if compact else 28.0

        active_measure = int(self._progress * 8) if self._playing else -1
        if active_measure == 8:
            active_measure = 7

        for system, top in enumerate(system_tops):
            self._draw_staff(p, left, right, top, staff_h)
            self._draw_staff(p, left, right, top + staff_h + staff_gap, staff_h)
            for measure in range(4):
                x = left + measure * measure_w
                idx = system * 4 + measure
                if idx == active_measure:
                    fill = QColor(t.score_measure)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(fill)
                    p.drawRoundedRect(
                        QRectF(x + 2, top - 10, measure_w - 4, staff_h * 2 + staff_gap + 20),
                        4,
                        4,
                    )
                if measure > 0:
                    p.setPen(QPen(t.score_faint, 1))
                    p.drawLine(x, top, x, top + staff_h * 2 + staff_gap)
                self._draw_notes(p, x, measure_w, top, staff_h, staff_gap, idx)
            p.setPen(QPen(t.score_faint, 1.4))
            p.drawLine(right, top, right, top + staff_h * 2 + staff_gap)

        if self._playing:
            x = left + self._progress * (right - left)
            p.setPen(QPen(t.score_playhead, 1.4))
            p.drawLine(x, 8, x, min(h, system_tops[1] + staff_h * 2 + staff_gap + 14))
            p.setBrush(t.score_playhead)
            p.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.moveTo(x - 4, 8)
            path.lineTo(x + 4, 8)
            path.lineTo(x, 14)
            path.closeSubpath()
            p.drawPath(path)
        p.restore()

    def _draw_staff(self, p: QPainter, left: float, right: float, top: float, height: float) -> None:
        t = self._theme
        p.setPen(QPen(t.score_faint, 1))
        for i in range(5):
            y = top + i * (height / 4)
            p.drawLine(left, y, right, y)

    def _draw_notes(
        self,
        p: QPainter,
        x: float,
        width: float,
        top: float,
        staff_h: float,
        staff_gap: float,
        measure_idx: int,
    ) -> None:
        t = self._theme
        clef_ink = QColor(t.score_ink)
        p.setPen(QPen(clef_ink, 1))
        p.setBrush(clef_ink)

        treble = [(-3, 0), (-1, 1), (1, 0), (2, 1), (0, 2)]
        bass = [(2, 0), (0, 2)]
        ratio = (staff_h / 4) / 2  # half a staff step
        treble_top = top + staff_h / 2

        for step, beat in treble:
            nx = x + width * (0.16 + beat * 0.22)
            ny = treble_top - step * ratio * 1.7
            p.drawEllipse(QRectF(nx - 4, ny - 2.8, 8, 5.6))
            p.drawLine(nx + 3.4, ny - 1, nx + 3.4, ny - 19)

        bass_top = top + staff_h + staff_gap + staff_h / 2
        for step, beat in bass:
            nx = x + width * (0.24 + beat * 0.26)
            ny = bass_top - step * ratio * 1.7
            p.drawEllipse(QRectF(nx - 4, ny - 2.8, 8, 5.6))
            p.drawLine(nx + 3.4, ny - 1, nx + 3.4, ny - 17)

        if measure_idx in (1, 5):
            # a couple of beamed eighth notes, for visual rhythm
            bx = x + width * 0.58
            by = treble_top - 1 * ratio * 1.7
            p.drawEllipse(QRectF(bx - 4, by - 2.8, 8, 5.6))
            p.drawEllipse(QRectF(bx + 18, by - 5, 8, 5.6))
            p.drawLine(bx + 3.4, by - 1, bx + 3.4, by - 18)
            p.drawLine(bx + 21.4, by - 3, bx + 21.4, by - 20)
            p.setPen(QPen(clef_ink, 2.4))
            p.drawLine(bx + 3.4, by - 18, bx + 21.4, by - 20)

    # -- parsed score drawn as a staff -----------------------------------

    def _draw_staff_score(self, p: QPainter) -> None:
        layout = self._layout
        if layout is None or not layout.systems:
            self._draw_parsed_placeholder(p)
            return
        t = self._theme
        w, h = self.width(), self.height()
        if w < 240 or h < 140:
            return
        left, right = 18.0, w - 16.0
        top, bottom = 16.0, h - 24.0
        page = min(self._page, self.page_count - 1)
        start = page * self.SYSTEMS_PER_PAGE
        systems = layout.systems[start:start + self.SYSTEMS_PER_PAGE]
        system_h = (bottom - top) / max(1, len(systems))
        staves = int(layout.treble) + int(layout.bass)
        line_gap = max(4.0, min(9.0, system_h / (staves * 8 + 3)))
        staff_h = line_gap * 4
        content_h = staves * staff_h + (staves - 1) * line_gap * 3
        play_system, play_x = (-1, 0.0)
        if self._follow_playing or self._playing or self._follow_position > 0:
            play_system, play_x = layout.playhead(self._follow_position)

        faint = QColor(t.score_faint)
        ink = QColor(t.score_ink)
        for local_index, system in enumerate(systems):
            sys_top = top + local_index * system_h
            block_top = sys_top + max(2.0, (system_h - content_h) / 2.0)
            treble_top = None
            bass_top = None
            if layout.treble and layout.bass:
                treble_top = block_top
                bass_top = block_top + staff_h + line_gap * 3
            elif layout.treble:
                treble_top = block_top
            else:
                bass_top = block_top

            clef_w = 40.0
            key_w = 6.0 + 10.0 * abs(layout.key_fifths)
            time_w = 24.0 if system.index == 0 else 0.0
            music_left = left + clef_w + key_w + time_w
            if right - music_left < 80:
                music_left = left + 46.0
            measure_w = (right - music_left) / max(1, len(system.measures))

            for staff, staff_top in (
                ("treble", treble_top),
                ("bass", bass_top),
            ):
                if staff_top is None:
                    continue
                self._draw_staff_lines(p, left, right, staff_top, line_gap, faint)
                self._draw_clef(p, staff, left, staff_top, staff_h, line_gap, ink)
                self._draw_key_signature(
                    p, layout, staff, left + clef_w, staff_top, line_gap, ink
                )
                if system.index == 0:
                    self._draw_time_signature(
                        p, layout, left + clef_w + key_w, staff_top, line_gap, ink
                    )

            bottom_y = block_top + content_h
            bar_ink = QColor(t.score_ink)
            bar_ink.setAlpha(170)
            p.setPen(QPen(bar_ink, 1.4))
            for index in range(len(system.measures) + 1):
                x = music_left + index * measure_w
                if index == len(system.measures):
                    x = right
                p.drawLine(QPointF(x, block_top), QPointF(x, bottom_y))

            for index, measure in enumerate(system.measures):
                measure_x = music_left + index * measure_w
                if index == 0:
                    p.setFont(self._theme.font(8, mono=True))
                    p.setPen(QPen(bar_ink, 1))
                    p.drawText(
                        QPointF(measure_x + 2, block_top - 3),
                        f"{measure.number}",
                    )
                for item in measure.notes:
                    staff_top = (
                        treble_top if item.staff == "treble" else bass_top
                    )
                    if staff_top is None:
                        staff_top = bass_top if bass_top is not None else treble_top
                    if staff_top is None:
                        continue
                    self._draw_staff_note(
                        p, item, measure_x, measure_w, measure.beats,
                        staff_top, line_gap, ink,
                    )

            if system.index == play_system:
                x = music_left + play_x * (right - music_left)
                p.setPen(QPen(t.score_playhead, 1.5))
                p.drawLine(QPointF(x, block_top - 5), QPointF(x, bottom_y + 5))

    def _draw_staff_lines(self, p, left, right, staff_top, gap, faint) -> None:
        p.setPen(QPen(faint, 1.0))
        for index in range(5):
            y = staff_top + index * gap
            p.drawLine(QPointF(left, y), QPointF(right, y))
        p.setPen(QPen(faint, 1.2))
        p.drawLine(QPointF(left, staff_top), QPointF(left, staff_top + gap * 4))
        p.drawLine(QPointF(right, staff_top), QPointF(right, staff_top + gap * 4))

    def _draw_clef(self, p, staff, left, staff_top, staff_h, gap, ink) -> None:
        clef_font = QFont("Segoe UI Symbol")
        clef_font.setPixelSize(max(18, int(staff_h * 1.55)))
        p.setFont(clef_font)
        p.setPen(QPen(ink, 1))
        p.drawText(
            QRectF(left + 2, staff_top - gap * 1.1, 34, staff_h + gap * 2.2),
            Qt.AlignmentFlag.AlignCenter,
            "𝄞" if staff == "treble" else "𝄢",
        )

    def _draw_key_signature(
        self, p, layout, staff, x, staff_top, gap, ink
    ) -> None:
        fifths = layout.key_fifths
        if fifths == 0:
            return
        if staff == "treble":
            sharp_steps = (8, 5, 9, 6, 3, 7, 4)
            flat_steps = (4, 7, 3, 6, 2, 5, 1)
        else:
            sharp_steps = (6, 3, 7, 4, 1, 5, 2)
            flat_steps = (2, 5, 1, 4, -1, 3, 0)
        if fifths > 0:
            steps = sharp_steps[:fifths]
            glyph = "♯"
        else:
            steps = flat_steps[: abs(fifths)]
            glyph = "♭"
        p.setFont(font(max(8, int(gap * 1.6)), mono=True))
        p.setPen(QPen(ink, 1))
        for index, step in enumerate(steps):
            y = staff_top + gap * 4 - step * gap / 2.0
            p.drawText(
                QRectF(x + index * gap * 0.95, y - gap, gap * 1.2, gap * 2),
                Qt.AlignmentFlag.AlignCenter,
                glyph,
            )

    def _draw_time_signature(self, p, layout, x, staff_top, gap, ink) -> None:
        p.setFont(font(max(8, int(gap * 1.9)), mono=True))
        p.setPen(QPen(ink, 1))
        beats, unit = layout.time_signature
        p.drawText(
            QRectF(x, staff_top, gap * 2.0, gap * 4),
            Qt.AlignmentFlag.AlignCenter,
            f"{beats}\n{unit}",
        )

    def _draw_staff_note(
        self, p, item: StaffNote, measure_x, measure_w, beats,
        staff_top, gap, ink,
    ) -> None:
        beat = max(1.0, min(beats, item.note.beat))
        x = measure_x + (beat - 1.0) / beats * measure_w
        x += min(7.0, max(1.0, measure_w * 0.07))
        bottom = staff_top + gap * 4
        y = bottom - item.step * gap / 2.0
        highlighted = (
            self._next_note is not None and item.note == self._next_note
        )
        color = QColor(self._theme.amber) if highlighted else ink

        p.setPen(QPen(color, 1.0))
        if item.step <= -2:
            for ledger in range(-2, item.step - 1, -2):
                ly = bottom - ledger * gap / 2.0
                p.drawLine(QPointF(x - 8, ly), QPointF(x + 8, ly))
        if item.step >= 10:
            for ledger in range(10, item.step + 1, 2):
                ly = bottom - ledger * gap / 2.0
                p.drawLine(QPointF(x - 8, ly), QPointF(x + 8, ly))

        if item.accidental:
            acc_font = QFont("Segoe UI Symbol")
            acc_font.setPixelSize(max(10, int(gap * 1.5)))
            p.setFont(acc_font)
            p.drawText(
                QRectF(x - gap * 2.6, y - gap, gap * 2.0, gap * 2),
                Qt.AlignmentFlag.AlignCenter,
                item.accidental,
            )

        note_beats = item.note.duration * self._layout.tempo / 60.0
        open_head = note_beats >= 1.9
        p.setPen(QPen(color, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush if open_head else color)
        p.save()
        p.translate(x, y)
        p.rotate(-18)
        p.drawEllipse(QRectF(-5.2, -3.6, 10.4, 7.2))
        p.restore()

        stem = gap * 3.2
        p.setPen(QPen(color, 1.2))
        if item.step <= 4:
            p.drawLine(QPointF(x + 4.4, y - 1), QPointF(x + 4.4, y - stem))
        else:
            p.drawLine(QPointF(x - 4.4, y + 1), QPointF(x - 4.4, y + stem))

    def _draw_roll(self, p: QPainter) -> None:
        if self._score is not None:
            self._draw_score_roll(p)
        else:
            self._draw_placeholder_roll(p)

    def _draw_score_roll(self, p: QPainter) -> None:
        score = self._score
        if score is None:
            return
        t = self._theme
        w, h = self.width(), self.height()
        left, right = 58.0, w - 22.0
        top, bottom = 16.0, h - 42.0
        if right - left < 120 or bottom - top < 60:
            return

        span = 8.0 / max(0.75, self._zoom)
        start = max(0.0, self._follow_position - span * 0.35)
        if start + span > score.duration:
            start = max(0.0, score.duration - span)
        lo = score.min_midi - 2
        hi = score.max_midi + 2
        rows = max(1, hi - lo + 1)
        row_h = (bottom - top) / rows

        for midi in range(lo, hi + 1):
            y = top + (hi - midi) * row_h
            is_c = midi % 12 == 0
            p.setPen(QPen(t.score_measure if is_c else t.score_faint, 1.0 if is_c else 0.8))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            if is_c:
                p.setPen(t.faint)
                p.setFont(self._theme.font(8))
                p.drawText(
                    QRectF(6, y - row_h / 2, left - 12, row_h),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    midi_name(midi),
                )

        beat_seconds = 60.0 / max(1.0, score.tempo)
        measure_seconds = beat_seconds * score.bars_per_measure
        first_measure = int(start // measure_seconds)
        last_measure = int(min(score.duration, start + span) // measure_seconds) + 1
        for measure in range(first_measure, last_measure + 1):
            x = left + (measure * measure_seconds - start) / span * (right - left)
            if left - 1 <= x <= right + 1:
                p.setPen(QPen(t.score_measure, 1.2))
                p.drawLine(QPointF(x, top), QPointF(x, bottom))
                p.setPen(t.faint)
                p.setFont(self._theme.font(7))
                p.drawText(
                    QRectF(x + 3, top - 13, 40, 12),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"{measure + 1}",
                )
        beat = first_measure * score.bars_per_measure
        while beat * beat_seconds < start + span:
            x = left + (beat * beat_seconds - start) / span * (right - left)
            if left <= x <= right and abs((beat % score.bars_per_measure)) > 1e-6:
                p.setPen(QPen(with_alpha(t.score_faint, 120), 0.7))
                p.drawLine(QPointF(x, top), QPointF(x, bottom))
            beat += 1

        for index, note in enumerate(score.notes):
            if note.end < start - 0.02 or note.start > start + span + 0.02:
                continue
            x0 = left + (note.start - start) / span * (right - left)
            x1 = left + (note.end - start) / span * (right - left)
            width = max(3.0, x1 - x0)
            y = top + (hi - note.midi) * row_h + row_h * 0.18
            rect = QRectF(x0, y, width, max(3.0, row_h * 0.64))

            if index < self._expected_index - 1:
                fill = with_alpha(QColor(t.faint), 80)
                edge = None
            elif index == self._expected_index - 1:
                fill = with_alpha(QColor(t.amber), 210)
                edge = QColor(t.amber)
            elif index == self._expected_index:
                fill = with_alpha(QColor(t.amber), 48)
                edge = QColor(t.amber)
            else:
                fill = with_alpha(QColor(t.card), 170)
                edge = t.hair
            p.setBrush(fill)
            p.setPen(QPen(edge, 1.5) if edge is not None else Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            if rect.width() > 28 and rect.height() > 9:
                p.setPen(
                    t.ink
                    if index in (self._expected_index - 1, self._expected_index)
                    else t.faint
                )
                p.setFont(self._theme.font(7, QFont.Weight.Medium, mono=True))
                p.drawText(
                    rect.adjusted(3, 0, -3, 0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    note.name,
                )

        px = left + (self._follow_position - start) / span * (right - left)
        if left <= px <= right:
            p.setPen(QPen(t.score_playhead, 1.6))
            p.drawLine(QPointF(px, top - 2), QPointF(px, bottom + 2))
            p.setBrush(t.score_playhead)
            p.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.moveTo(px - 4, top - 2)
            path.lineTo(px + 4, top - 2)
            path.lineTo(px, top + 4)
            path.closeSubpath()
            p.drawPath(path)

        p.setPen(t.muted)
        p.setFont(self._theme.font(9))
        p.drawText(
            QRectF(left, bottom + 8, 220, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{tr('命中')} {self._hits} · {tr('未中')} {self._misses}"
            + (f" · {tr('示范播放中')}" if self._follow_playing else ""),
        )
        if self._next_note is not None:
            if language() == "en":
                text = (
                    f"Next {self._next_note.name} · "
                    f"Bar {self._next_note.measure}"
                )
            else:
                text = (
                    f"下一键 {self._next_note.name} · "
                    f"第 {self._next_note.measure} 小节"
                )
        else:
            text = tr("已完成 · 按“重来”或空格示范")
        p.drawText(
            QRectF(left + 220, bottom + 8, right - left - 220, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

    def _draw_parsed_placeholder(self, p: QPainter) -> None:
        score = self._score
        if score is None:
            return
        t = self._theme
        w = self.width()
        p.setPen(t.ink)
        p.setFont(self._theme.font(18, QFont.Weight.DemiBold))
        p.drawText(
            QRectF(30, 26, w - 60, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            score.title,
        )
        p.setPen(t.muted)
        p.setFont(self._theme.font(10))
        meta = (
            f"{score.format} · {score.tempo:.0f} BPM · "
            f"{score.time_signature[0]}/{score.time_signature[1]} · "
            f"{len(score.notes)} {tr('音')} · {score.duration:.1f} s"
        )
        p.drawText(
            QRectF(30, 58, w - 60, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            meta,
        )
        p.setPen(t.faint)
        p.setFont(self._theme.font(12))
        p.drawText(
            QRectF(30, 96, w - 60, 44),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "已解析成功。谱面渲染在后续版本；请用“落键”查看音符、播放头和下一键。",
        )
        p.setFont(self._theme.font(9))
        names = "  ".join(note.name for note in score.notes[:18])
        if len(score.notes) > 18:
            names += "  …"
        p.drawText(
            QRectF(30, 148, w - 60, 50),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            names,
        )

    def _draw_placeholder_roll(self, p: QPainter) -> None:
        t = self._theme
        p.save()
        p.scale(self._zoom, self._zoom)
        w = self.width() / self._zoom
        h = self.height() / self._zoom
        left, right = 44.0, w - 24.0
        top, bottom = 24.0, h - 28.0
        rows = 24
        row_h = (bottom - top) / rows

        p.setPen(QPen(t.score_faint, 1))
        for r in range(rows + 1):
            p.drawLine(left, top + r * row_h, right, top + r * row_h)
        for beat in range(17):
            x = left + (right - left) * beat / 16
            p.setPen(QPen(t.score_faint, 1))
            p.drawLine(x, top, x, bottom)

        pattern = [
            (2, 0, 2), (4, 2, 1), (5, 3, 1), (7, 4, 2), (9, 5, 1),
            (11, 6, 2), (12, 7, 1), (14, 8, 2), (16, 9, 2), (18, 10, 1),
            (20, 11, 2), (21, 12, 1), (22, 11, 1), (23, 10, 2), (24, 9, 1),
        ]
        p.setPen(Qt.PenStyle.NoPen)
        for start, row, length in pattern:
            x = left + (right - left) * start / 26
            width = (right - left) * length / 26
            color = QColor(t.amber)
            color.setAlpha(190)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, top + row * row_h + 2, width, row_h - 4), 3, 3)

        if self._playing:
            x = left + self._progress * (right - left)
            p.setPen(QPen(t.score_playhead, 1.4))
            p.drawLine(x, top - 6, x, bottom)

        p.setPen(QColor(t.faint))
        p.setFont(self._theme.font(9))
        p.drawText(
            QRectF(left, bottom + 4, right - left, 18),
            Qt.AlignmentFlag.AlignHCenter,
            "落键视图 · 拖入 MusicXML / MIDI 或载入示例谱开始跟弹",
        )
        p.restore()


class ScoreView(GlassFrame):
    focusToggled = Signal(bool)
    message = Signal(str)
    scoreFileDropped = Signal(str)
    imageOpened = Signal(str)
    restartRequested = Signal()

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setAcceptDrops(True)
        self._zoom = 1.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(4)
        self._tabs = QButtonGroup(self)
        self._tabs.setExclusive(True)
        self._tab_buttons: dict[str, QPushButton] = {}
        for key, text in (("sheet", "谱面"), ("roll", "落键"), ("focus", "专注")):
            btn = QPushButton(text)
            btn.setProperty("role", "tab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._tabs.addButton(btn)
            self._tab_buttons[key] = btn
            top.addWidget(btn)
        self._tab_buttons["sheet"].setChecked(True)
        self._tabs.buttonClicked.connect(self._on_tab)

        restart = QPushButton("重来")
        restart.setProperty("role", "tab")
        restart.setCursor(Qt.CursorShape.PointingHandCursor)
        restart.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        restart.setToolTip("回到谱子开头，重新练习")
        restart.clicked.connect(self.restartRequested)
        top.addWidget(restart)

        self._page_prev = QPushButton("‹")
        self._page_prev.setProperty("role", "step")
        self._page_prev.setFixedSize(26, 26)
        self._page_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._page_prev.setToolTip("上一页谱面")
        self._page_prev.clicked.connect(
            lambda: self.canvas.set_page(self.canvas.page - 1)
        )
        self._page_label = QLabel("1/1")
        self._page_label.setProperty("role", "faint")
        self._page_next = QPushButton("›")
        self._page_next.setProperty("role", "step")
        self._page_next.setFixedSize(26, 26)
        self._page_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._page_next.setToolTip("下一页谱面")
        self._page_next.clicked.connect(
            lambda: self.canvas.set_page(self.canvas.page + 1)
        )
        for widget in (self._page_prev, self._page_label, self._page_next):
            top.addWidget(widget)
        self._page_prev.hide()
        self._page_label.hide()
        self._page_next.hide()

        top.addStretch(1)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setProperty("role", "faint")
        top.addWidget(self._zoom_label)
        minus = QPushButton("−")
        minus.setProperty("role", "step")
        minus.setFixedSize(26, 26)
        minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        minus.clicked.connect(lambda: self._nudge_zoom(-0.1))
        plus = QPushButton("+")
        plus.setProperty("role", "step")
        plus.setFixedSize(26, 26)
        plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        plus.clicked.connect(lambda: self._nudge_zoom(0.1))
        top.addWidget(minus)
        top.addWidget(plus)
        outer.addLayout(top)

        head = QHBoxLayout()
        head.setSpacing(12)
        self._title = QLabel("示例谱 · 占位")
        self._title.setProperty("role", "title")
        self._meta = QLabel("谱面占位 · 拖入 PNG / JPG 查看图片")
        self._meta.setProperty("role", "muted")
        head.addWidget(self._title)
        head.addWidget(self._meta, 0, Qt.AlignmentFlag.AlignBottom)
        head.addStretch(1)
        outer.addLayout(head)

        self.canvas = ScoreCanvas(theme)
        self.canvas.pageChanged.connect(self._sync_page_controls)
        outer.addWidget(self.canvas, 1)

    # -- API --------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.canvas.set_theme(theme)

    def open_image(self, path: str | Path) -> bool:
        path = Path(path)
        probe = QPixmap(str(path))
        if probe.isNull():
            return False  # do not disturb the current score on a bad image
        self.canvas.clear_score()
        if not self.canvas.set_image(path):
            return False
        self._title.setText(path.stem)
        self._meta.setText(f"{path.suffix[1:].upper()} · 图片谱 · 不跟随")
        self._sync_page_controls()
        self._tab_buttons["sheet"].setChecked(True)
        self.canvas.set_mode("sheet")
        self.focusToggled.emit(False)
        self.imageOpened.emit(str(path))
        return True

    def set_score(self, score: Score) -> None:
        was_focus = self._tab_buttons["focus"].isChecked()
        self.canvas.set_score(score)
        self._title.setText(score.title)
        self._meta.setText(
            f"{score.format} · {score.tempo:.0f} BPM · "
            f"{len(score.notes)} {tr('音')} · {score.duration:.1f} s"
        )
        self._sync_page_controls()
        self._tab_buttons["roll"].setChecked(True)
        if was_focus:
            self.focusToggled.emit(False)

    def set_follow_state(
        self,
        position: float,
        expected_index: int,
        hits: int,
        misses: int,
        playing: bool,
        next_note: Optional[ScoreNote],
    ) -> None:
        self.canvas.set_follow_state(
            position, expected_index, hits, misses, playing, next_note
        )

    @property
    def has_score(self) -> bool:
        return self.canvas.has_score

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.75, min(1.35, zoom))
        self._zoom_label.setText(f"{int(round(self._zoom * 100))}%")
        self.canvas.set_zoom(self._zoom)

    def _nudge_zoom(self, delta: float) -> None:
        self.set_zoom(self._zoom + delta)

    def _sync_page_controls(self) -> None:
        count = self.canvas.page_count if self.canvas.has_score else 1
        page = min(self.canvas.page, count - 1) + 1
        self._page_label.setText(f"{page}/{count}")
        show = (
            self.canvas.has_score
            and count > 1
            and self.canvas._mode == "sheet"
        )
        for widget in (self._page_prev, self._page_label, self._page_next):
            widget.setVisible(show)
        self._page_prev.setEnabled(page > 1)
        self._page_next.setEnabled(page < count)

    def toggle_play(self) -> None:
        if self.canvas.has_score:
            # The main window drives FollowSession; this path is only for the
            # image / placeholder score.
            return
        if self.canvas.has_image:
            self.message.emit("图片谱不跟随 · 手动翻页")
            return
        playing = self.canvas.toggle_play()
        self.message.emit("播放中 · 示例播放头" if playing else "已暂停")

    def is_playing(self) -> bool:
        return self.canvas._playing

    def exit_focus(self) -> None:
        """Leave 专注 mode if it is active (called when navigating away)."""
        if not self._tab_buttons["focus"].isChecked():
            return
        landing = "roll" if self.canvas.has_score else "sheet"
        self._tab_buttons[landing].setChecked(True)
        self.canvas.set_mode(landing)
        self.focusToggled.emit(False)

    def _on_tab(self, button: QPushButton) -> None:
        key = next((k for k, b in self._tab_buttons.items() if b is button), "sheet")
        if key == "focus":
            self.canvas.set_mode("roll" if self.canvas.has_score else "sheet")
            self.focusToggled.emit(True)
        else:
            self.canvas.set_mode(key)
            self._sync_page_controls()
            self.focusToggled.emit(False)

    # -- drag & drop ------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = Path(urls[0].toLocalFile())
        suffix = path.suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            if self.open_image(path):
                self.message.emit("已载入图片谱")
            else:
                self.message.emit("无法读取这张图片")
        elif suffix in (".mid", ".midi", ".musicxml", ".mxl", ".xml"):
            self.scoreFileDropped.emit(str(path))
            self.message.emit(f"正在解析 {path.name}…")
        else:
            self.message.emit(f"暂不支持 {suffix or '该文件'}")
        event.acceptProposedAction()
