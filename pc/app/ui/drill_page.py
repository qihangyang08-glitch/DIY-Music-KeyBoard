"""Full-page generated drill: staff question + 32-key answer strip.

The first drill is stage 1's note-name flashcard. It is deliberately a page of
its own rather than a modal: the learning page keeps its stage/course state,
and the drill can take the whole page while the actual playing happens on the
same 32-key instrument (hardware or computer keyboard).

No mouse-to-note: the strip only shows state. The user answers by pressing a
bar on the instrument or a bound computer key. The drill temporarily maps the
32 bars to a chromatic C4–G6 range and restores the previous mapping when it
closes, so a learner who has never touched 学习 keeps the same performance
mapping afterwards.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.curriculum import stage_by_index
from ..core.drill import (
    DrillSpec,
    DrillTarget,
    NoteNameSession,
    NoteQuestion,
    OnboardingSession,
)
from ..core.exam import evaluate, exam_by_key
from ..core.note_engine import midi_name
from ..core.rhythm import RhythmSession
from ..core.synth_service import CLICK_CHANNEL
from .light_bar import pitch_color, with_alpha
from .rhythm_view import RhythmCanvas
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame


def staff_spacing(area: QRectF, step: int) -> float:
    """Line spacing that keeps a note at ``step`` inside the paint area.

    The staff is centred in the card, but a note far above the staff (E6/G6 in
    the octave drill and the stage-1 exam) would otherwise be drawn above the
    widget and clipped. Shrinking the staff for extreme notes keeps the note
    head and its ledger lines visible without changing the card height.
    """
    spacing = max(10.0, min(24.0, area.height() / 7.5))
    offset = 2.0 - step / 2.0  # note y = center + spacing * offset
    margin = 8.0
    if offset < 0:
        spacing = min(
            spacing,
            max(10.0, (area.center().y() - area.top() - margin) / -offset),
        )
    elif offset > 0:
        spacing = min(
            spacing,
            max(10.0, (area.bottom() - margin - area.center().y()) / offset),
        )
    return spacing


def staff_note_y(area: QRectF, step: int) -> float:
    """Y coordinate of the note head for a staff step, inside ``area``."""
    spacing = staff_spacing(area, step)
    return area.center().y() + spacing * (2.0 - step / 2.0)


class StaffView(QWidget):
    """A minimal treble staff with one note; no music font required."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._question: NoteQuestion | None = None
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName("五线谱单音题")
        self.setAccessibleDescription("高音谱号上显示一个音，请在光条上按下它")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_question(self, question: NoteQuestion | None) -> None:
        self._question = question
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        area = QRectF(self.rect()).adjusted(10, 6, -10, -6)
        if area.width() < 280 or area.height() < 80:
            p.end()
            return

        question = self._question
        step = question.staff_step if question is not None else 0
        spacing = staff_spacing(area, step)
        staff_h = spacing * 4
        bottom = area.center().y() + staff_h / 2
        top = bottom - staff_h
        left = area.left() + (82.0 if area.width() > 430 else 54.0)
        right = area.right() - 22.0

        # staff lines
        ink = QColor(t.score_ink)
        ink.setAlpha(150)
        p.setPen(QPen(ink, 1.0))
        for index in range(5):
            y = top + index * spacing
            p.drawLine(QPointF(left, y), QPointF(right, y))

        # Treble U+1D11E / bass U+1D122 from Segoe UI Symbol. The caption
        # names the clef, so a missing glyph is a font problem, not a note name.
        clef = question.clef if question is not None else "treble"
        clef_glyph = "𝄢" if clef == "bass" else "𝄞"
        clef_font = QFont("Segoe UI Symbol")
        clef_font.setPixelSize(max(34, int(staff_h * 1.55)))
        p.setFont(clef_font)
        p.setPen(QPen(QColor(t.score_ink), 1.0))
        p.drawText(
            QRectF(left - 72, top - spacing * 1.2, 64, staff_h + spacing * 2.4),
            Qt.AlignmentFlag.AlignCenter,
            clef_glyph,
        )

        if question is None:
            p.end()
            return

        nx = left + (right - left) * 0.55
        ny = staff_note_y(area, step)

        # accidental glyph (♯/♭) sits before the note head; the note's staff
        # step comes from its spelled letter, so B♭4 is drawn on the B line.
        if question.accidental:
            acc_font = QFont("Segoe UI Symbol")
            acc_font.setPixelSize(max(18, int(spacing * 1.8)))
            p.setFont(acc_font)
            p.setPen(QPen(QColor(t.score_ink), 1.0))
            p.drawText(
                QRectF(nx - 34, ny - spacing, 24, spacing * 2),
                Qt.AlignmentFlag.AlignCenter,
                question.accidental,
            )

        # ledger lines for notes outside the five-line staff
        if step <= -2:
            for ledger in range(-2, step - 1, -2):
                y = bottom - ledger * spacing / 2.0
                p.drawLine(QPointF(nx - 13, y), QPointF(nx + 13, y))
        if step >= 10:
            for ledger in range(10, step + 1, 2):
                y = bottom - ledger * spacing / 2.0
                p.drawLine(QPointF(nx - 13, y), QPointF(nx + 13, y))

        # note head, slightly tilted like engraved music
        p.save()
        p.translate(nx, ny)
        p.rotate(-18)
        p.setPen(QPen(QColor(t.score_ink), 1.0))
        p.setBrush(QColor(t.score_ink))
        p.drawEllipse(QRectF(-8.0, -5.4, 16.0, 10.8))
        p.restore()

        # stem: up below the middle line, down above it
        stem = 3.15 * spacing
        p.setPen(QPen(QColor(t.score_ink), 1.5))
        if step <= 4:
            p.drawLine(nx + 6.8, ny - 1, nx + 6.8, ny - stem)
        else:
            p.drawLine(nx - 6.8, ny + 1, nx - 6.8, ny + stem)
        p.end()


class DrillKeyStrip(QWidget):
    """The 32 slots used to answer; labels are the current mapped pitches."""

    def __init__(self, theme: Theme, instrument, bindings, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self._active: set[int] = set()
        self._correct: int | None = None
        self._wrong: int | None = None
        self._flash_until = 0.0
        self._pool: set[int] = set()
        self.setFixedHeight(62)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("32 键作答光条")
        self.setAccessibleDescription("显示当前训练音域、键位与题目答案槽")
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_active(self, keys: set[int]) -> None:
        self._active = set(keys)
        self.update()

    def set_pool(self, midis: set[int]) -> None:
        """Question pool; other slots stay as dim distractors."""
        self._pool = set(midis)
        self.update()

    def flash_correct(self, bar: int | None) -> None:
        # The correct-slot outline stays until the question is solved; it is
        # the one piece of feedback a wrong answer must keep visible.
        self._correct = bar
        self.update()

    def flash_wrong(self, bar: int | None) -> None:
        self._wrong = bar
        if bar is not None:
            self._flash_until = time.monotonic() + 1.2
            self._timer.start()
        self.update()

    def clear_flash(self) -> None:
        self._correct = None
        self._wrong = None
        self._flash_until = 0.0
        self.update()

    def _tick(self) -> None:
        if time.monotonic() >= self._flash_until:
            self._wrong = None
            self._flash_until = 0.0
            self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        gap = 1.0
        slot_w = max(8.0, (self.width() - gap * 31) / 32.0)
        top = 6.0
        slot_h = max(28.0, self.height() - 12.0)

        for index in range(32):
            bar = index + 1
            rect = QRectF(index * (slot_w + gap), top, slot_w, slot_h)
            midi = self.instrument.midi_for_key(bar)
            note = self.instrument.note_for_key(bar)
            active = bar in self._active
            in_pool = not self._pool or midi in self._pool
            if active:
                color = pitch_color(midi, t)
                p.setBrush(with_alpha(color, 150))
                p.setPen(QPen(with_alpha(color, 220), 1.0))
            elif t.dark:
                # A light/dark theme needs opposite slot fills: white-alpha 150
                # would turn into an opaque grey block in Stage and swallow the
                # light note labels.
                p.setBrush(with_alpha(QColor(255, 255, 255), 16))
                p.setPen(QPen(with_alpha(QColor(255, 255, 255), 32), 0.8))
            else:
                p.setBrush(with_alpha(QColor(255, 255, 255), 150))
                p.setPen(QPen(t.hair, 0.8))
            p.drawRoundedRect(rect, 4, 4)

            if self._wrong == bar:
                p.setPen(QPen(t.danger, 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
            elif self._correct == bar:
                p.setPen(QPen(t.amber, 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

            if slot_w >= 17:
                key_font = self._theme.font(7, QFont.Weight.Medium, mono=True)
                p.setFont(key_font)
                keycap = self.bindings.keycap(bar)
                keycap = QFontMetrics(key_font).elidedText(
                    keycap,
                    Qt.TextElideMode.ElideRight,
                    max(6, int(rect.width()) - 3),
                )
                keycap_color = t.ink if active else t.faint
                if not in_pool:
                    keycap_color = with_alpha(keycap_color, 80)
                p.setPen(keycap_color)
                p.drawText(
                    QRectF(rect.left(), rect.top() + 2, rect.width(), 10),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    keycap,
                )
            p.setFont(self._theme.font(9, QFont.Weight.DemiBold, mono=True))
            if midi % 12 == 0:
                text_color = t.ink if active else t.amber
            else:
                text_color = t.ink if active else t.muted
            if not in_pool:
                text_color = with_alpha(text_color, 90)
            p.setPen(text_color)
            p.drawText(
                QRectF(rect.left(), rect.bottom() - 17, rect.width(), 14),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                note,
            )
        p.end()


class DrillPage(GlassFrame):
    closed = Signal()
    progressChanged = Signal()
    message = Signal(str)

    def __init__(self, theme: Theme, instrument, bindings, progress, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self.progress = progress
        self._target: DrillTarget | None = None
        self._spec: DrillSpec | None = None
        self._exam = None
        self._session: NoteNameSession | RhythmSession | None = None
        self._left = True
        self._recorded = True
        self._locked = False
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._after_correct)
        self._rhythm_timer = QTimer(self)
        self._rhythm_timer.setInterval(20)
        self._rhythm_timer.timeout.connect(self._rhythm_tick)
        self._click_off_timer = QTimer(self)
        self._click_off_timer.setSingleShot(True)
        self._click_off_timer.setInterval(55)
        self._click_off_timer.timeout.connect(self._stop_click_notes)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        self._back = QPushButton("← 学习")
        self._back.setProperty("role", "chip")
        self._back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._back.clicked.connect(lambda checked=False: self.leave())
        top.addWidget(self._back)
        self._index = QLabel("01")
        self._index.setProperty("role", "amber")
        set_scaled_font(self._index, self.theme, 12, QFont.Weight.DemiBold, mono=True)
        top.addWidget(self._index)
        self._title = QLabel("音名闪卡")
        set_scaled_font(self._title, self.theme, 20, QFont.Weight.DemiBold)
        top.addWidget(self._title)
        self._meta = QLabel("识谱训练")
        self._meta.setProperty("role", "faint")
        top.addWidget(self._meta)
        top.addStretch(1)
        self._progress_label = QLabel("第 1/10 题")
        self._progress_label.setProperty("role", "mono")
        set_scaled_font(self._progress_label, self.theme, 11, QFont.Weight.DemiBold, mono=True)
        top.addWidget(self._progress_label)
        self._stats_label = QLabel("✓ 0 · ✗ 0 · 连对 0")
        self._stats_label.setProperty("role", "faint")
        set_scaled_font(self._stats_label, self.theme, 10, mono=True)
        top.addWidget(self._stats_label)
        outer.addLayout(top)

        self._stack = QStackedWidget()
        self._drill_view = self._build_drill_view()
        self._summary_view = self._build_summary_view()
        self._stack.addWidget(self._drill_view)
        self._stack.addWidget(self._summary_view)
        outer.addWidget(self._stack, 1)
        self._stack.setCurrentWidget(self._drill_view)

    # -- construction -----------------------------------------------------

    def _build_drill_view(self) -> QWidget:
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._body_stack = QStackedWidget()
        self._note_view = self._build_note_view()
        self._rhythm_view = self._build_rhythm_view()
        self._onboarding_view = self._build_onboarding_view()
        self._body_stack.addWidget(self._note_view)
        self._body_stack.addWidget(self._rhythm_view)
        self._body_stack.addWidget(self._onboarding_view)
        self._body_stack.setCurrentWidget(self._note_view)
        lay.addWidget(self._body_stack)
        return view

    def _build_note_view(self) -> QWidget:
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addStretch(1)
        staff_card = CardFrame()
        staff_card.setMinimumHeight(220)
        staff_card.setMaximumHeight(330)
        staff_lay = QVBoxLayout(staff_card)
        staff_lay.setContentsMargins(16, 12, 16, 10)
        staff_lay.setSpacing(2)
        self._staff_caption = QLabel("高音谱号 · C4–C5")
        self._staff_caption.setProperty("role", "faint")
        set_scaled_font(self._staff_caption, self.theme, 9, QFont.Weight.Medium)
        staff_lay.addWidget(self._staff_caption)
        self._staff = StaffView(self.theme)
        staff_lay.addWidget(self._staff, 1)
        lay.addWidget(staff_card)
        lay.addStretch(1)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(12)
        self._prompt = QLabel("看谱 → 在光条上按下这个音")
        self._prompt.setProperty("role", "muted")
        set_scaled_font(self._prompt, self.theme, 13, QFont.Weight.DemiBold)
        prompt_row.addWidget(self._prompt)
        prompt_row.addStretch(1)
        self._feedback = QLabel(" ")
        self._feedback.setProperty("role", "amber")
        set_scaled_font(self._feedback, self.theme, 12, QFont.Weight.DemiBold)
        self._feedback.setWordWrap(True)
        prompt_row.addWidget(self._feedback, 2)
        lay.addLayout(prompt_row)

        strip_card = CardFrame()
        strip_lay = QVBoxLayout(strip_card)
        strip_lay.setContentsMargins(10, 8, 10, 7)
        strip_lay.setSpacing(3)
        self._strip = DrillKeyStrip(self.theme, self.instrument, self.bindings)
        strip_lay.addWidget(self._strip)
        hint = QHBoxLayout()
        hint.setSpacing(8)
        self._range_hint = QLabel("训练音域 C4–G6 · 光条 1 = C4")
        self._range_hint.setProperty("role", "faint")
        set_scaled_font(self._range_hint, self.theme, 9, QFont.Weight.Medium, mono=True)
        hint.addWidget(self._range_hint)
        hint.addStretch(1)
        mode_hint = QLabel("只判音名与八度 · 错按可重试")
        mode_hint.setProperty("role", "faint")
        hint.addWidget(mode_hint)
        strip_lay.addLayout(hint)
        lay.addWidget(strip_card)
        return view

    def _build_rhythm_view(self) -> QWidget:
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addStretch(1)
        canvas_card = CardFrame()
        canvas_card.setMinimumHeight(220)
        canvas_card.setMaximumHeight(330)
        canvas_lay = QVBoxLayout(canvas_card)
        canvas_lay.setContentsMargins(16, 12, 16, 10)
        canvas_lay.setSpacing(2)
        self._rhythm_caption = QLabel("节奏训练")
        self._rhythm_caption.setProperty("role", "faint")
        set_scaled_font(self._rhythm_caption, self.theme, 9, QFont.Weight.Medium)
        canvas_lay.addWidget(self._rhythm_caption)
        self._rhythm_canvas = RhythmCanvas(self.theme)
        canvas_lay.addWidget(self._rhythm_canvas, 1)
        lay.addWidget(canvas_card)
        lay.addStretch(1)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(12)
        self._rhythm_prompt = QLabel("按任意键踩拍 · 先听 1 小节预备")
        self._rhythm_prompt.setProperty("role", "muted")
        set_scaled_font(self._rhythm_prompt, self.theme, 13, QFont.Weight.DemiBold)
        prompt_row.addWidget(self._rhythm_prompt)
        prompt_row.addStretch(1)
        self._rhythm_status = QLabel("准备 · 按开始")
        self._rhythm_status.setProperty("role", "faint")
        set_scaled_font(self._rhythm_status, self.theme, 11)
        self._rhythm_status.setWordWrap(True)
        prompt_row.addWidget(self._rhythm_status, 2)
        lay.addLayout(prompt_row)

        controls_card = CardFrame()
        controls = QHBoxLayout(controls_card)
        controls.setContentsMargins(12, 9, 12, 9)
        controls.setSpacing(8)
        self._rhythm_start = QPushButton("开始")
        self._rhythm_start.setProperty("role", "action")
        self._rhythm_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rhythm_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rhythm_start.clicked.connect(
            lambda checked=False: self.toggle_rhythm()
        )
        controls.addWidget(self._rhythm_start)
        self._rhythm_stop = QPushButton("重来")
        self._rhythm_stop.setProperty("role", "chip")
        self._rhythm_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rhythm_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rhythm_stop.clicked.connect(
            lambda checked=False: self.restart_rhythm()
        )
        controls.addWidget(self._rhythm_stop)
        controls.addSpacing(6)
        self._rhythm_meta = QLabel("80 BPM · 4/4")
        self._rhythm_meta.setProperty("role", "faint")
        set_scaled_font(self._rhythm_meta, self.theme, 9, QFont.Weight.Medium, mono=True)
        controls.addWidget(self._rhythm_meta)
        controls.addStretch(1)
        key_hint = QLabel("Enter / Space 开始或停止 · Esc 停止 / 返回")
        key_hint.setProperty("role", "faint")
        controls.addWidget(key_hint)
        lay.addWidget(controls_card)
        return view

    def _build_onboarding_view(self) -> QWidget:
        """Stage 0: a guided action card plus the same 32-slot answer strip."""
        view = QWidget()
        lay = QVBoxLayout(view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addStretch(1)
        card = CardFrame()
        card.setMinimumHeight(220)
        card.setMaximumHeight(330)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(28, 20, 28, 16)
        card_lay.setSpacing(8)
        self._onboard_step = QLabel("第 1/4 步")
        self._onboard_step.setProperty("role", "label")
        set_scaled_font(self._onboard_step, self.theme, 10, QFont.Weight.DemiBold)
        card_lay.addWidget(self._onboard_step)
        self._onboard_title = QLabel("找到中央 C")
        set_scaled_font(self._onboard_title, self.theme, 26, QFont.Weight.DemiBold)
        self._onboard_title.setWordWrap(True)
        card_lay.addWidget(self._onboard_title)
        self._onboard_detail = QLabel(" ")
        self._onboard_detail.setProperty("role", "muted")
        set_scaled_font(self._onboard_detail, self.theme, 13)
        self._onboard_detail.setWordWrap(True)
        card_lay.addWidget(self._onboard_detail)
        self._onboard_feedback = QLabel(" ")
        self._onboard_feedback.setProperty("role", "amber")
        set_scaled_font(self._onboard_feedback, self.theme, 12, QFont.Weight.DemiBold)
        self._onboard_feedback.setWordWrap(True)
        card_lay.addWidget(self._onboard_feedback)
        card_lay.addStretch(1)
        self._onboard_checks = QLabel("")
        self._onboard_checks.setProperty("role", "muted")
        set_scaled_font(self._onboard_checks, self.theme, 10, QFont.Weight.Medium)
        card_lay.addWidget(self._onboard_checks)
        lay.addWidget(card)
        lay.addStretch(1)

        strip_card = CardFrame()
        strip_lay = QVBoxLayout(strip_card)
        strip_lay.setContentsMargins(10, 8, 10, 7)
        strip_lay.setSpacing(3)
        self._onboard_strip = DrillKeyStrip(
            self.theme, self.instrument, self.bindings
        )
        strip_lay.addWidget(self._onboard_strip)
        hint = QHBoxLayout()
        hint.setSpacing(8)
        tip = QLabel("按提示操作 · 做完这一步会自动进入下一步")
        tip.setProperty("role", "faint")
        set_scaled_font(tip, self.theme, 9, QFont.Weight.Medium)
        hint.addWidget(tip)
        hint.addStretch(1)
        mode = QLabel("只判这一步的动作 · 按错可重试")
        mode.setProperty("role", "faint")
        hint.addWidget(mode)
        strip_lay.addLayout(hint)
        lay.addWidget(strip_card)
        return view

    def _build_summary_view(self) -> QWidget:
        view = QWidget()
        outer = QVBoxLayout(view)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(0)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        card = CardFrame()
        card.setMinimumWidth(420)
        card.setMaximumWidth(680)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(34, 28, 34, 26)
        lay.setSpacing(8)
        self._summary_title = QLabel("训练完成")
        set_scaled_font(self._summary_title, self.theme, 22, QFont.Weight.DemiBold)
        lay.addWidget(self._summary_title)
        self._summary_score = QLabel("10/10")
        set_scaled_font(self._summary_score, self.theme, 46, QFont.Weight.DemiBold, mono=True)
        lay.addWidget(self._summary_score)
        self._summary_detail = QLabel("")
        self._summary_detail.setProperty("role", "muted")
        set_scaled_font(self._summary_detail, self.theme, 12)
        self._summary_detail.setWordWrap(True)
        lay.addWidget(self._summary_detail)
        self._summary_note = QLabel("")
        self._summary_note.setProperty("role", "faint")
        self._summary_note.setWordWrap(True)
        lay.addWidget(self._summary_note)
        lay.addSpacing(6)
        actions = QHBoxLayout()
        self._retry_button = QPushButton("再练一次")
        retry = self._retry_button
        retry.setProperty("role", "action")
        retry.setCursor(Qt.CursorShape.PointingHandCursor)
        retry.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        retry.clicked.connect(lambda checked=False: self._retry())
        back = QPushButton("返回阶段")
        back.setProperty("role", "chip")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        back.clicked.connect(lambda checked=False: self.leave())
        actions.addWidget(retry)
        actions.addWidget(back)
        actions.addStretch(1)
        lay.addLayout(actions)
        self._summary_keys = QLabel("Enter / Space 再练一次 · Esc / Backspace 返回阶段")
        self._summary_keys.setProperty("role", "faint")
        lay.addWidget(self._summary_keys)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.set_theme(self.theme)
        return view

    # -- lifecycle --------------------------------------------------------

    def start(self, target: DrillTarget, spec: DrillSpec) -> None:
        self._target = target
        self._spec = spec
        self._exam = exam_by_key(spec.key)
        self._left = False
        self._recorded = False
        self._locked = False
        stage = stage_by_index(target.stage_index)
        self._back.setText(f"← 阶段 {stage.index} · {stage.name}")
        self._index.setText(f"{stage.index:02d}")
        self._title.setText(spec.title)
        if self._exam is not None:
            meta_prefix = "考核"
        elif spec.kind == "rhythm":
            meta_prefix = "节奏训练"
        else:
            meta_prefix = "识谱训练"
        exam_mode = self._exam is not None
        self._summary_title.setText("考核成绩" if exam_mode else "训练完成")
        self._retry_button.setText("再考一次" if exam_mode else "再练一次")
        self._summary_keys.setText(
            "Enter / Space 再考一次 · Esc / Backspace 返回阶段"
            if exam_mode
            else "Enter / Space 再练一次 · Esc / Backspace 返回阶段"
        )
        if spec.kind == "rhythm" and spec.rhythm is not None:
            self._meta.setText(f"{meta_prefix} · {spec.subtitle}")
            self._rhythm_caption.setText(spec.subtitle)
            self._rhythm_meta.setText(
                f"{spec.rhythm.bpm} BPM · "
                f"{spec.rhythm.meter_label} · {spec.rhythm.bars} 小节"
            )
            self._body_stack.setCurrentWidget(self._rhythm_view)
            self._rhythm_canvas.set_spec(spec.rhythm)
            # Rhythm does not need a pitch mapping, but it should not let a
            # stray pad change the user's performance mapping mid-run either.
            self.instrument.mapping_locked = True
            self._new_session()
            return
        if spec.kind == "onboarding":
            self._meta.setText(f"上手训练 · {spec.subtitle}")
            self._body_stack.setCurrentWidget(self._onboarding_view)
            self._new_session()
            self.instrument.begin_drill_mapping(
                spec.mapping_base, label_cn="上手训练"
            )
            return
        self._meta.setText(f"{meta_prefix} · {spec.subtitle}")
        self._staff_caption.setText(spec.staff_caption)
        self._strip.set_pool(set(spec.midis))
        self._body_stack.setCurrentWidget(self._note_view)
        # Create the session first so stateChanged during the mapping switch
        # already knows the drill is active (the status bar then suppresses the
        # score's next-key hint).
        self._new_session()
        self.instrument.begin_drill_mapping(spec.mapping_base)
        self._update_range_hint()

    def _new_session(self) -> None:
        if self._spec is None:
            return
        self._advance_timer.stop()
        self._rhythm_timer.stop()
        if self._spec.kind == "rhythm" and self._spec.rhythm is not None:
            self._session = RhythmSession(self._spec.rhythm)
            self._left = False
            self._recorded = False
            self._locked = False
            self._rhythm_canvas.set_spec(self._spec.rhythm)
            self._rhythm_canvas.set_session(self._session)
            self._rhythm_start.setText("开始")
            self._rhythm_prompt.setText("按任意键踩拍 · 先听 1 小节预备")
            self._rhythm_status.setText("准备 · 按开始 / Enter")
            self._rhythm_canvas.update()
            self._stack.setCurrentWidget(self._drill_view)
            self._update_header()
            return
        if self._spec.kind == "onboarding":
            self._session = OnboardingSession(self._spec)
            self._left = False
            self._recorded = False
            self._locked = False
            self._onboard_strip.clear_flash()
            self._set_onboard_feedback(" ", "amber")
            self._refresh_onboarding()
            self._stack.setCurrentWidget(self._drill_view)
            self._session.mark_shown()
            self._update_header()
            return
        self._session = NoteNameSession(self._spec)
        self._left = False
        self._recorded = False
        self._locked = False
        self._feedback.setText(" ")
        self._feedback.setProperty("role", "amber")
        self._repolish(self._feedback)
        self._staff.set_question(self._session.current)
        self._strip.clear_flash()
        self._stack.setCurrentWidget(self._drill_view)
        self._session.mark_shown()
        self._update_header()

    def leave(self, notify: bool = True) -> None:
        """Record a partial run, restore the user's mapping, emit closed."""
        if self._left:
            return
        self._left = True
        self._advance_timer.stop()
        self._rhythm_timer.stop()
        if isinstance(self._session, RhythmSession):
            self._session.stop()
            self._stop_click_notes()
        self._record_result()
        self.instrument.end_drill_mapping()
        self.instrument.mapping_locked = False
        if notify:
            self.closed.emit()

    @property
    def is_active(self) -> bool:
        return not self._left and self._session is not None

    @property
    def target(self) -> DrillTarget | None:
        return self._target

    @property
    def showing_summary(self) -> bool:
        return self._stack.currentWidget() is self._summary_view

    @property
    def run_finished(self) -> bool:
        return self._session is not None and self._session.finished

    @property
    def is_rhythm(self) -> bool:
        return self._spec is not None and self._spec.kind == "rhythm"

    @property
    def is_onboarding(self) -> bool:
        return self._spec is not None and self._spec.kind == "onboarding"

    @property
    def wants_sustain(self) -> bool:
        """True while the current onboarding step needs the sustain key."""
        if not self.is_onboarding or not isinstance(
            self._session, OnboardingSession
        ):
            return False
        step = self._session.current
        if step is None:
            return False
        return step.action == "sustain" or step.require_sustain

    @property
    def rhythm_running(self) -> bool:
        return isinstance(self._session, RhythmSession) and self._session.running

    def retry(self) -> None:
        self._retry()

    # -- rhythm controls --------------------------------------------------

    def toggle_rhythm(self) -> None:
        if not self.is_rhythm or self._session is None:
            return
        if isinstance(self._session, RhythmSession) and self._session.running:
            self.stop_rhythm()
            return
        if isinstance(self._session, RhythmSession) and (
            self._session.started_at is not None or self._session.finished
        ):
            self._new_session()
        self.start_rhythm()

    def start_rhythm(self) -> None:
        if not isinstance(self._session, RhythmSession) or self._session.running:
            return
        self._session.start()
        self._rhythm_timer.start()
        self._rhythm_start.setText("停止")
        self._rhythm_status.setText("预备 · 听节拍")
        self._rhythm_canvas.update()
        self._update_header()

    def stop_rhythm(self) -> None:
        if not isinstance(self._session, RhythmSession):
            return
        self._rhythm_timer.stop()
        self._session.stop()
        self._stop_click_notes()
        self._rhythm_start.setText("开始")
        self._rhythm_status.setText("已停止 · 按开始重来")
        self._rhythm_canvas.update()
        self._update_header()
        if self._session.finished:
            # Every onset was already judged; show the verdict now instead of
            # losing it when the user stops during the post-roll tail.
            self._record_result()
            self._show_summary()

    def restart_rhythm(self) -> None:
        if not self.is_rhythm:
            return
        self._rhythm_timer.stop()
        if isinstance(self._session, RhythmSession):
            self._session.stop()
        self._stop_click_notes()
        self._new_session()

    def _rhythm_tick(self) -> None:
        if not isinstance(self._session, RhythmSession):
            self._rhythm_timer.stop()
            return
        now = time.monotonic()
        clicks = self._session.tick(now)
        for click in clicks:
            self._play_click(click.accent)
        self._rhythm_canvas.update()
        self._update_header()
        self._update_rhythm_status(now)
        if self._session.finished:
            self._rhythm_timer.stop()
            self._rhythm_start.setText("开始")
            self._stop_click_notes()
            self._record_result()
            self._show_summary()

    def _update_rhythm_status(self, now: float | None = None) -> None:
        if not isinstance(self._session, RhythmSession):
            return
        session = self._session
        now = time.monotonic() if now is None else now
        remaining = session.count_in_remaining(now)
        if session.finished:
            text = "完成"
        elif remaining > 0:
            text = f"预备 {remaining} · 听节拍"
        elif session.running:
            text = (
                f"踩准 {session.hits}/{session.total}"
                f" · 漏拍 {session.misses} · 多按 {session.extras}"
            )
            press = session.last_press
            if press is not None:
                text += (
                    f" · 上次 {press.error_ms:+d} ms"
                    if press.hit
                    else " · 多按"
                )
        else:
            text = "已停止 · 按开始重来"
        self._rhythm_status.setText(text)

    def _play_click(self, accent: bool) -> None:
        midi = 96 if accent else 84
        self.instrument.synth.note_on(midi, 100, channel=CLICK_CHANNEL)
        self._click_off_timer.start()

    def _stop_click_notes(self) -> None:
        self._click_off_timer.stop()
        for midi in (84, 96):
            self.instrument.synth.note_off(midi, channel=CLICK_CHANNEL)

    # -- input ------------------------------------------------------------

    def note_on(self, midi: int) -> None:
        self.note_batch([midi])

    def note_batch(self, midis: list[int]) -> None:
        """Judge at most one answer per 20 ms engine batch.

        Two simultaneous note-ons (a chord, a gliss, keyboard+hardware) must
        not answer question N and then immediately miss question N+1. If the
        batch contains the expected pitch, the batch is correct; otherwise the
        first note is one miss. The rest of the batch is ignored.
        """
        if self._left or self._locked or self._session is None:
            return
        if self.is_rhythm:
            if isinstance(self._session, RhythmSession) and self._session.running:
                self._session.press(time.monotonic())
                self._rhythm_canvas.update()
                self._update_rhythm_status()
                self._update_header()
            return
        if self.is_onboarding:
            if isinstance(self._session, OnboardingSession):
                self._answer_onboarding(midis)
            return
        current = self._session.current
        if current is None:
            return
        notes = [int(midi) for midi in midis]
        if not notes:
            return
        if self._exam is not None:
            # An exam asks for one first press. A batch containing the expected
            # pitch *and* other keys (a chord/sweep over the whole strip) must
            # not be scored as a correct first answer.
            unique = set(notes)
            if unique == {current.midi}:
                choice = current.midi
            else:
                choice = next(
                    (midi for midi in unique if midi != current.midi), notes[0]
                )
        else:
            choice = current.midi if current.midi in notes else notes[0]
        result = self._session.answer(choice)
        if result is None:
            return
        expected = result.expected
        correct_bar = self.instrument.bar_for_midi(expected.midi)
        key_hint = self._key_name_hint(correct_bar, expected.name)
        if result.correct:
            self._strip.flash_wrong(None)
            self._strip.flash_correct(correct_bar)
            self._set_feedback(
                f"✓ 正确 · {expected.name}{key_hint}", "amber"
            )
            self._locked = True
            self._advance_timer.start(340)
        else:
            pressed_bar = self.instrument.bar_for_midi(result.pressed_midi)
            self._strip.flash_wrong(pressed_bar)
            self._strip.flash_correct(correct_bar)
            location = f" · 光条 {correct_bar}" if correct_bar is not None else ""
            self._set_feedback(
                f"这是 {result.pressed_name}；正确是 {expected.name}"
                f"{location}{key_hint}",
                "danger",
            )
        self._update_header()

    def _answer_onboarding(self, midis: list[int]) -> None:
        """A press answers a "press" step; other steps ignore note input."""
        if not isinstance(self._session, OnboardingSession):
            return
        step = self._session.current
        note = step.midi if step is not None else None
        if step is None or step.action != "press" or note is None:
            return
        notes = [int(midi) for midi in midis]
        if not notes:
            return
        choice = note if note in notes else notes[0]
        result = self._session.press(
            choice, sustain=self.instrument.sustain
        )
        if result is not None:
            self._handle_step_result(result)

    def _handle_step_result(self, result) -> None:
        if self._session is None or self._left:
            return
        step = result.step
        if result.correct:
            self._onboard_strip.flash_wrong(None)
            if step.midi is not None:
                self._onboard_strip.flash_correct(
                    self.instrument.bar_for_midi(step.midi)
                )
            else:
                self._onboard_strip.clear_flash()
            self._set_onboard_feedback(f"✓ {step.title}", "amber")
            self._locked = True
            self._advance_timer.start(340)
            self._update_header()
            return

        expected = midi_name(step.midi) if step.midi is not None else ""
        correct_bar = (
            self.instrument.bar_for_midi(step.midi)
            if step.midi is not None
            else None
        )
        if result.sustain_required:
            text = f"先按住 Shift（延音），再按 {expected}。"
            self._onboard_strip.flash_wrong(None)
            self._onboard_strip.flash_correct(correct_bar)
        else:
            pressed_bar = (
                self.instrument.bar_for_midi(result.pressed_midi)
                if result.pressed_midi is not None
                else None
            )
            self._onboard_strip.flash_wrong(pressed_bar)
            self._onboard_strip.flash_correct(correct_bar)
            location = f"（光条 {correct_bar}）" if correct_bar is not None else ""
            text = (
                f"这是 {result.pressed_name}；这一步要按 {expected}{location}"
            )
        self._set_onboard_feedback(text, "danger")
        self._update_header()

    def _refresh_onboarding(self) -> None:
        session = self._session
        if not isinstance(session, OnboardingSession):
            return
        step = session.current
        if step is None:
            return
        self._onboard_step.setText(
            f"第 {session.index + 1}/{session.total} 步"
        )
        self._onboard_title.setText(step.title)
        self._onboard_detail.setText(step.detail)
        marks = []
        for index, item in enumerate(session.steps):
            if index < session.index:
                marks.append(f"✓  {item.title}")
            elif index == session.index:
                marks.append(f"●  {item.title}")
            else:
                marks.append(f"○  {item.title}")
        self._onboard_checks.setText("\n".join(marks))
        target = step.midi if step.action == "press" else None
        self._onboard_strip.set_pool({target} if target is not None else set())

    def panicked(self) -> None:
        """Called by the window after a user-triggered 全部静音."""
        if (
            not self.is_onboarding
            or self._left
            or not isinstance(self._session, OnboardingSession)
        ):
            return
        result = self._session.panic()
        if result is not None:
            self._handle_step_result(result)

    def _observe_sustain(self) -> None:
        if (
            not self.is_onboarding
            or self._left
            or self._locked
            or not isinstance(self._session, OnboardingSession)
        ):
            return
        result = self._session.sustain(self.instrument.sustain)
        if result is not None:
            self._handle_step_result(result)

    def set_active(self, keys: set[int]) -> None:
        self._strip.set_active(keys)
        self._onboard_strip.set_active(keys)

    def refresh(self) -> None:
        self._strip.update()
        self._onboard_strip.update()
        if hasattr(self, "_rhythm_canvas"):
            self._rhythm_canvas.update()
        self._update_range_hint()
        self._observe_sustain()

    # -- state -> view ----------------------------------------------------

    def _after_correct(self) -> None:
        self._locked = False
        if self._session is None or self.is_rhythm:
            return
        if self._session.finished:
            self._record_result()
            self._show_summary()
            return
        if self.is_onboarding:
            self._onboard_strip.clear_flash()
            self._set_onboard_feedback(" ", "amber")
            self._refresh_onboarding()
            self._session.mark_shown()
            self._update_header()
            return
        self._staff.set_question(self._session.current)
        self._strip.clear_flash()
        self._set_feedback(" ", "amber")
        self._session.mark_shown()
        self._update_header()

    def _update_header(self) -> None:
        session = self._session
        if session is None:
            return
        if isinstance(session, OnboardingSession):
            if session.finished:
                self._progress_label.setText("完成")
            else:
                self._progress_label.setText(
                    f"第 {session.index + 1}/{session.total} 步"
                )
            self._stats_label.setText(
                f"✓ {session.hits} · ✗ {session.misses}"
            )
            return
        if isinstance(session, RhythmSession):
            if session.finished:
                self._progress_label.setText("完成")
            else:
                self._progress_label.setText(
                    f"踩准 {session.hits}/{session.total}"
                )
            self._stats_label.setText(
                f"漏拍 {session.misses} · 多按 {session.extras}"
                f" · 连对 {session.streak}"
            )
            return
        if session.finished:
            self._progress_label.setText("完成")
        else:
            self._progress_label.setText(
                f"第 {session.index + 1}/{session.total} 题"
            )
        self._stats_label.setText(
            f"✓ {session.hits} · ✗ {session.misses} · 连对 {session.streak}"
        )

    def _update_range_hint(self) -> None:
        if self._spec is None or self.is_rhythm or self.is_onboarding:
            return
        base_bar = self.instrument.bar_for_midi(self._spec.mapping_base)
        octave_bar = self.instrument.bar_for_midi(
            self._spec.mapping_base + 12
        )
        parts = [
            f"按键 {self._spec.range_label}",
            f"题目 {self._spec.question_range_label}",
        ]
        if base_bar is not None:
            parts.append(
                f"光条 {base_bar} = {self.instrument.note_for_key(base_bar)}"
            )
        if octave_bar is not None:
            parts.append(
                f"光条 {octave_bar} = "
                f"{self.instrument.note_for_key(octave_bar)}"
            )
        self._range_hint.setText(" · ".join(parts))

    def _set_feedback(self, text: str, role: str) -> None:
        self._feedback.setText(text)
        self._feedback.setProperty("role", role)
        self._repolish(self._feedback)

    def _set_onboard_feedback(self, text: str, role: str) -> None:
        self._onboard_feedback.setText(text)
        self._onboard_feedback.setProperty("role", role)
        self._repolish(self._onboard_feedback)

    def _key_name_hint(self, bar: int | None, expected_name: str) -> str:
        """Explain enharmonics: B♭4 is labelled A#4 on the 32-key strip."""
        if bar is None:
            return ""
        mapped = self.instrument.note_for_key(bar)
        if mapped == expected_name:
            return ""
        return f"（键面 {mapped}）"

    def _repolish(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def _stage_note(self) -> str:
        stage = stage_by_index(self._target.stage_index) if self._target else None
        if stage is not None and self._target is not None:
            if self._stage_done(stage):
                if stage.ready_count < stage.total_count:
                    return (
                        "本阶段可练内容已完成；其余训练仍显示“制作中”，"
                        "不会被算作已学会。"
                    )
                return "本阶段已全部完成。"
            return "这一项已记录；阶段里还有其他可练项目。"
        return "结果已写入本地学习档案。"

    def _show_summary(self) -> None:
        session = self._session
        if session is None:
            return
        out = session.outcome()
        self._progress_label.setText("完成")
        if self._exam is not None:
            result = evaluate(self._exam, out)
            self._summary_score.setText(
                f"{result.hits}/{result.total}"
                if result.kind == "rhythm"
                else f"{result.first_try}/{result.total}"
            )
            if result.kind == "rhythm":
                self._stats_label.setText(
                    f"踩准 {out.hits} · 漏拍 {out.misses}"
                    f" · 多按 {out.extras}"
                )
                avg = f"{result.avg_ms} ms" if result.avg_ms else "—"
                self._summary_detail.setText(
                    f"平均偏差 {avg} · 最长连对 {out.best_streak}\n"
                    f"{self._spec.rhythm.bpm} BPM · "
                    f"{self._spec.rhythm.meter_label} · "
                    f"{self._spec.rhythm.bars} 小节"
                )
            else:
                avg = f"{out.avg_ms / 1000:.1f} s" if out.avg_ms else "—"
                self._stats_label.setText(
                    f"✓ {out.hits} · ✗ {out.misses}"
                    f" · 连对 {out.best_streak}"
                )
                self._summary_detail.setText(
                    f"首答 {result.first_try}/{result.total}"
                    f" · 错按 {out.misses} · 平均反应 {avg}"
                )
            verdict = "考核通过 ✓" if result.passed else "考核未通过"
            self._summary_note.setText(
                f"{verdict} · {self._exam.criteria}\n"
                "可随时重考；阶段通关仍按普通练习记录，考核不阻止普通练习完成。"
            )
            self._stack.setCurrentWidget(self._summary_view)
            return
        self._summary_score.setText(f"{out.hits}/{out.total}")
        if isinstance(session, OnboardingSession):
            self._stats_label.setText(f"✓ {out.hits} · ✗ {out.misses}")
            self._summary_detail.setText(
                f"完成 {out.hits}/{out.total} 步 · 错按 {out.misses}"
                f" · 一次做对 {out.first_try}/{out.total}"
            )
            self._summary_note.setText(self._stage_note())
            self._stack.setCurrentWidget(self._summary_view)
            return
        if isinstance(session, RhythmSession):
            self._stats_label.setText(
                f"踩准 {out.hits} · 漏拍 {out.misses}"
                f" · 多按 {out.extras}"
            )
            avg = f"{out.avg_ms} ms" if out.avg_ms else "—"
            rhythm = self._spec.rhythm if self._spec else None
            meta = (
                f"{rhythm.bpm} BPM · {rhythm.meter_label}"
                if rhythm is not None
                else "节奏训练"
            )
            self._summary_detail.setText(
                f"漏拍 {out.misses} · 多按 {out.extras}"
                f" · 准确率 {out.accuracy}% · 平均偏差 {avg}\n"
                f"最长连对 {out.best_streak} · {meta}"
            )
            self._summary_note.setText(self._stage_note())
            self._stack.setCurrentWidget(self._summary_view)
            return
        self._stats_label.setText(
            f"✓ {out.hits} · ✗ {out.misses} · 连对 {out.best_streak}"
        )
        avg = f"{out.avg_ms / 1000:.1f} s" if out.avg_ms else "—"
        self._summary_detail.setText(
            f"首次答对 {out.first_try}/{out.total} · 错按 {out.misses}"
            f" · 准确率 {out.accuracy}%\n平均反应 {avg} · 最长连对 {out.best_streak}"
        )
        self._summary_note.setText(self._stage_note())
        self._stack.setCurrentWidget(self._summary_view)

    def _stage_done(self, stage) -> bool:
        ready = stage.ready_items
        if not ready:
            return False
        for item in ready:
            result = self.progress.result_for(stage.index, item.name)
            if result is None or not result.completed:
                return False
        return True

    def _retry(self) -> None:
        self._new_session()

    # -- result recording -------------------------------------------------

    def _record_result(self) -> None:
        if self._recorded or self._session is None or self._target is None:
            return
        out = self._session.outcome()
        if out.attempts == 0:
            return
        if self._exam is not None:
            # An abandoned run is not an exam attempt: only a finished run
            # produces a verdict, and it never enters the practice archive.
            if not out.finished:
                return
            self.progress.record_exam(evaluate(self._exam, out))
            self._recorded = True
            self.progressChanged.emit()
            return
        self.progress.record_practice(
            self._target.stage_index,
            self._target.item_name,
            out.hits,
            out.misses + getattr(out, "extras", 0),
            out.total,
            avg_ms=out.avg_ms,
            best_streak=out.best_streak,
            first_try=out.first_try,
        )
        self._recorded = True
        self.progressChanged.emit()

    def result_message(self) -> str:
        session = self._session
        if session is None:
            return ""
        out = session.outcome()
        if self._exam is not None:
            result = evaluate(self._exam, out)
            verdict = "通过" if result.passed else "未通过"
            return f"考核{verdict} · {result.summary}"
        if isinstance(session, OnboardingSession):
            prefix = "完成" if out.finished else "已完成"
            text = f"上手训练 · {prefix} {out.hits}/{out.total} 步"
            if out.misses:
                text += f" · 错按 {out.misses}"
            return text
        if isinstance(session, RhythmSession):
            text = (
                f"节奏记录 · 踩准 {out.hits}/{out.total}"
                f" · 漏拍 {out.misses} · 多按 {out.extras}"
            )
            if out.avg_ms:
                text += f" · 平均偏差 {out.avg_ms}ms"
            return text
        if out.finished:
            text = f"训练记录 · 答对 {out.hits}/{out.total}"
        else:
            text = f"训练记录 · 已答 {out.hits}/{out.total}"
        text += f" · 错按 {out.misses} · {out.accuracy}%"
        if out.avg_ms:
            text += f" · 平均 {out.avg_ms / 1000:.1f}s"
        if out.best_streak:
            text += f" · 连对 {out.best_streak}"
        return text

    # -- theme ------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        if hasattr(self, "_staff"):
            self._staff.set_theme(theme)
            self._strip.set_theme(theme)
        if hasattr(self, "_rhythm_canvas"):
            self._rhythm_canvas.set_theme(theme)
        if hasattr(self, "_onboard_strip"):
            self._onboard_strip.set_theme(theme)
        if hasattr(self, "_summary_score"):
            self._summary_score.setStyleSheet(
                f"color: {theme.amber.name()}; background: transparent;"
            )
