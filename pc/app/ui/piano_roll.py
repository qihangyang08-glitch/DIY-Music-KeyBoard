"""Piano-roll canvas for one project track (H3 slice).

Edits only: left-click draws, right-click erases, drag moves, Ctrl-drag copies,
drag the right edge to resize, Ctrl+wheel zooms. Nothing here sounds a note —
auditioning stays on the 32-key band / keyboard.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.editor import MIN_DURATION, NoteEditor
from .light_bar import pitch_color
from .theme import Theme

LOW_MIDI = 48   # C3
HIGH_MIDI = 87  # D#6, the standard 32-key top
ROW_H = 7
HEADER_H = 18
MIN_BEATS = 16
GRID = 0.25
ZOOM_MIN = 20.0
ZOOM_MAX = 160.0
HEIGHT = HEADER_H + (HIGH_MIDI - LOW_MIDI + 1) * ROW_H

BLACK_PITCHES = {1, 3, 6, 8, 10}


class PianoRollCanvas(QWidget):
    noteEdited = Signal()

    def __init__(self, theme: Theme, editor: NoteEditor, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.editor = editor
        self._ppb = 48.0
        self._selection: int | None = None
        self._position = 0.0
        self._gesture: dict | None = None

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFixedHeight(HEIGHT)
        self.refresh()

    # -- state ------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_editor(self, editor: NoteEditor) -> None:
        self.editor = editor
        self._selection = None
        self._gesture = None
        self.refresh()

    def set_position(self, beat: float) -> None:
        self._position = max(0.0, beat)
        self.update()

    @property
    def position(self) -> float:
        return self._position

    @property
    def pixels_per_beat(self) -> float:
        return self._ppb

    def set_zoom(self, pixels_per_beat: float) -> None:
        self._ppb = max(ZOOM_MIN, min(ZOOM_MAX, pixels_per_beat))
        self.refresh()

    def total_beats(self) -> float:
        notes = self.editor.notes
        last = max((note.end for note in notes), default=0.0)
        loop = self.editor.project.loop
        if loop is not None:
            last = max(last, loop.end)
        return max(MIN_BEATS, math.ceil(last + 4))

    def refresh(self) -> None:
        self.setMinimumWidth(int(self.total_beats() * self._ppb) + 1)
        self.setFixedHeight(HEIGHT)
        self.update()

    # -- geometry ---------------------------------------------------------

    def x_for_beat(self, beat: float) -> float:
        return beat * self._ppb

    def beat_at(self, x: float) -> float:
        return max(0.0, x / self._ppb)

    def y_for_midi(self, midi: int) -> float:
        return HEADER_H + (HIGH_MIDI - midi) * ROW_H

    def midi_at(self, y: float) -> int:
        raw = HIGH_MIDI - int((y - HEADER_H) // ROW_H)
        return max(0, min(127, raw))

    @staticmethod
    def snap(beat: float) -> float:
        return round(round(beat / GRID) * GRID, 6)

    def note_rect(self, index: int) -> QRectF | None:
        notes = self.editor.notes
        if not 0 <= index < len(notes):
            return None
        note = notes[index]
        return QRectF(
            self.x_for_beat(note.start),
            self.y_for_midi(note.midi),
            max(3.0, note.duration * self._ppb),
            ROW_H - 1,
        )

    def loop_rect(self) -> QRectF | None:
        loop = self.editor.project.loop
        if loop is None:
            return None
        return QRectF(
            self.x_for_beat(loop.start),
            HEADER_H,
            self.x_for_beat(loop.length),
            HEIGHT - HEADER_H,
        )

    def note_index_at(self, pos) -> int | None:
        for index in range(len(self.editor.notes) - 1, -1, -1):
            rect = self.note_rect(index)
            if rect is not None and rect.adjusted(-2, -2, 2, 2).contains(pos):
                return index
        return None

    def _on_resize_handle(self, pos, index: int) -> bool:
        rect = self.note_rect(index)
        return bool(rect is not None and pos.x() >= rect.right() - 5)

    # -- painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), t.bg2)

        width = self.width()
        for midi in range(LOW_MIDI, HIGH_MIDI + 1):
            y = self.y_for_midi(midi)
            if midi % 12 in BLACK_PITCHES:
                shade = QColor(t.bg)
                shade.setAlpha(90)
                p.fillRect(QRectF(0, y, width, ROW_H), shade)
            p.setPen(QPen(t.hair, 1))
            p.drawLine(0, int(y), width, int(y))

        total = int(self.total_beats()) + 1
        for beat in range(total):
            x = self.x_for_beat(beat)
            if beat % 4 == 0:
                p.setPen(QPen(t.faint, 1))
                p.drawLine(int(x), HEADER_H, int(x), HEIGHT)
                p.setPen(t.faint)
                p.setFont(self._theme.font(8))
                p.drawText(QRectF(x + 3, 1, 40, HEADER_H - 2),
                           Qt.AlignmentFlag.AlignVCenter, str(beat // 4 + 1))
            else:
                p.setPen(QPen(t.hair, 1))
                p.drawLine(int(x), HEADER_H, int(x), HEIGHT)
        p.setPen(QPen(t.faint, 1))
        p.drawLine(0, HEADER_H, width, HEADER_H)

        loop = self.loop_rect()
        if loop is not None:
            fill = QColor(t.amber)
            fill.setAlpha(28)
            p.fillRect(loop, fill)
            p.setPen(QPen(t.amber, 1, Qt.PenStyle.DashLine))
            p.drawLine(loop.left(), HEADER_H, loop.left(), HEIGHT)
            p.drawLine(loop.right(), HEADER_H, loop.right(), HEIGHT)

        x = self.x_for_beat(self._position)
        p.setPen(QPen(t.amber, 2))
        p.drawLine(int(x), HEADER_H, int(x), HEIGHT)

        for index, note in enumerate(self.editor.notes):
            rect = self.note_rect(index)
            if rect is None or rect.right() < 0 or rect.left() > width:
                continue
            color = pitch_color(note.midi, t)
            color.setAlpha(215)
            p.setBrush(color)
            p.setPen(QPen(t.amber if index == self._selection else t.ink, 1))
            p.drawRoundedRect(rect, 2, 2)
        p.end()

    # -- mouse ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        index = self.note_index_at(pos)
        if event.button() == Qt.MouseButton.RightButton:
            if index is not None and self.editor.erase_note(index):
                self._selection = None
                self.noteEdited.emit()
                self.refresh()
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        if index is None:
            note_index = self.editor.add_note(
                self.snap(self.beat_at(pos.x())), self.midi_at(pos.y()), 1.0
            )
            self._selection = note_index if note_index >= 0 else None
            self.noteEdited.emit()
            self.refresh()
            event.accept()
            return

        note = self.editor.notes[index]
        self.editor.begin_gesture()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            copy = self.editor.insert_note(note.start, note.midi, note.duration)
            if copy >= 0:
                index = copy
                note = self.editor.notes[index]
        self._selection = index
        self._gesture = {
            "index": index,
            "mode": "resize" if self._on_resize_handle(pos, index) else "move",
            "start": note.start,
            "midi": note.midi,
            "duration": note.duration,
            "press_beat": self.beat_at(pos.x()),
            "press_midi": self.midi_at(pos.y()),
        }
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._gesture is None:
            super().mouseMoveEvent(event)
            return
        gesture = self._gesture
        pos = event.position()
        beat = self.beat_at(pos.x())
        if gesture["mode"] == "resize":
            duration = self.snap(
                gesture["duration"] + (beat - gesture["press_beat"])
            )
            self.editor.update_note(
                gesture["index"], duration=max(MIN_DURATION, duration)
            )
        else:
            start = self.snap(gesture["start"] + (beat - gesture["press_beat"]))
            midi = gesture["midi"] + (self.midi_at(pos.y()) - gesture["press_midi"])
            self.editor.update_note(gesture["index"], start=start, midi=midi)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._gesture is not None and event.button() == Qt.MouseButton.LeftButton:
            self.editor.end_gesture()
            self._gesture = None
            self._selection = None
            self.noteEdited.emit()
            self.refresh()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self._ppb * step)
            event.accept()
            return
        super().wheelEvent(event)
