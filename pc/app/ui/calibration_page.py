"""Per-key threshold calibration page (A2 slice 3).

The page owns a CalibrationSession, draws one curve per pressed key, lets the
user pick a touch threshold on the curve, and sends the result to the firmware
as a channel-keyed ``T`` line. While the page is open the instrument is in
calibration mode: keys still light the bar, but no note sounds and nothing is
judged or recorded.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.calibration import (
    BASELINE_SECONDS,
    SIGNAL_MAX,
    CalibrationFrame,
    CalibrationProfile,
    CalibrationSession,
    KeyCurve,
    format_thresholds,
    parse_threshold_reply,
)
from ..core.instrument import Instrument
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame

SendLine = Callable[[str], bool]
Clock = Callable[[], float]
ReadyCheck = Callable[[], bool]


class CurveWidget(QWidget):
    """A signal-vs-time plot with a draggable threshold line."""

    thresholdPicked = Signal(int)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.curve: KeyCurve | None = None
        self.threshold = 0
        self.release = 0
        self.setMinimumHeight(132)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("点曲线或拖动阈值线；←/→ 微调，Shift+←/→ ±5")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_data(
        self, curve: KeyCurve, threshold: int, release: int
    ) -> None:
        self.curve = curve
        self.threshold = int(threshold)
        self.release = int(release)
        self.update()

    # -- geometry ---------------------------------------------------------

    def _plot_rect(self) -> QRectF:
        return QRectF(36, 10, max(20.0, self.width() - 48.0), max(20.0, self.height() - 34.0))

    def _y_for_value(self, value: int, plot: QRectF | None = None) -> float:
        rect = plot or self._plot_rect()
        fraction = max(0.0, min(1.0, value / SIGNAL_MAX))
        return rect.bottom() - fraction * rect.height()

    def value_at_y(self, y: float) -> int:
        rect = self._plot_rect()
        fraction = (rect.bottom() - y) / max(1.0, rect.height())
        value = round(max(0.0, min(1.0, fraction)) * SIGNAL_MAX)
        return max(1, min(SIGNAL_MAX, value))

    # -- painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        plot = self._plot_rect()

        grid = QPen(t.hair)
        grid.setWidthF(1.0)
        p.setFont(t.font(9, mono=True))
        for value in (0, 64, 128, 192, 255):
            y = self._y_for_value(value, plot)
            p.setPen(grid)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QPen(t.faint))
            p.drawText(
                QRectF(0, y - 8, plot.left() - 5, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(value),
            )
        p.setPen(QPen(t.card_edge))
        p.drawRect(plot)

        curve = self.curve
        if curve is None or not curve.samples:
            p.setPen(QPen(t.faint))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "等待按键…")
            p.end()
            return

        first = curve.samples[0].t
        last = curve.samples[-1].t
        span = max(0.10, last - first)

        def x_for(moment: float) -> float:
            return plot.left() + (moment - first) / span * plot.width()

        # Noise floor and release line are context, not the decision.
        for value, colour, style in (
            (curve.noise, t.faint, Qt.PenStyle.DotLine),
            (self.release, t.faint, Qt.PenStyle.DashLine),
        ):
            pen = QPen(colour)
            pen.setStyle(style)
            p.setPen(pen)
            y = self._y_for_value(value, plot)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        polyline = QPolygonF(
            [
                QPointF(x_for(sample.t), self._y_for_value(sample.value, plot))
                for sample in curve.samples
            ]
        )
        p.setPen(QPen(t.ink, 2.0))
        p.drawPolyline(polyline)

        peak_sample = max(curve.samples, key=lambda sample: sample.value)
        p.setPen(QPen(t.amber))
        p.setBrush(t.amber)
        p.drawEllipse(
            QPointF(x_for(peak_sample.t), self._y_for_value(peak_sample.value, plot)),
            3.0,
            3.0,
        )
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setFont(t.font(9, mono=True))
        p.drawText(
            QRectF(plot.left() + 4, plot.top() + 2, plot.width() - 8, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"峰值 {curve.peak}",
        )

        threshold_y = self._y_for_value(self.threshold, plot)
        pen = QPen(t.amber, 2.0)
        p.setPen(pen)
        p.drawLine(
            QPointF(plot.left(), threshold_y),
            QPointF(plot.right(), threshold_y),
        )
        label_rect = QRectF(plot.right() - 96, threshold_y - 21, 92, 17)
        backing = QColor(t.card)
        backing.setAlpha(238)
        p.fillRect(label_rect.adjusted(-2, -1, 2, 1), backing)
        p.setPen(QPen(t.amber))
        p.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"阈值 {self.threshold}",
        )
        p.setPen(QPen(t.faint))
        p.drawText(
            QRectF(plot.left(), plot.bottom() + 2, plot.width(), 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "时间 →",
        )
        p.end()

    # -- picking ----------------------------------------------------------

    def _pick(self, y: float) -> None:
        self.thresholdPicked.emit(self.value_at_y(y))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(event.position().y())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position().y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event) -> None:
        step = (
            5
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            else 1
        )
        if event.key() == Qt.Key.Key_Left:
            self.thresholdPicked.emit(max(1, self.threshold - step))
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self.thresholdPicked.emit(min(SIGNAL_MAX, self.threshold + step))
            event.accept()
        else:
            super().keyPressEvent(event)


class VerifyStrip(QWidget):
    """32 live cells after apply: pass / low margin / not recognised."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._values: dict[int, int] = {}
        self._thresholds: dict[int, tuple[int, int]] = {}
        self._noise: dict[int, int] = {}
        self._states: dict[int, str] = {}
        self.setMinimumHeight(56)
        self.setToolTip(
            "按和弦：✓ 超过阈值，! 余量不足 15%，× 按了但未识别"
        )

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def clear(self) -> None:
        self._values = {}
        self._states = {}
        self.update()

    def set_data(
        self,
        values: dict[int, int],
        thresholds: dict[int, tuple[int, int]],
        noise: dict[int, int],
    ) -> None:
        self._values = dict(values)
        self._thresholds = dict(thresholds)
        self._noise = dict(noise)
        self._states = {}
        for key in range(1, 33):
            value = self._values.get(key, -1)
            touch = self._thresholds.get(key, (0, 0))[0]
            if value < 0 or touch <= 0:
                self._states[key] = "idle"
                continue
            floor = max(8, self._noise.get(key, 0) + 5)
            if value >= touch:
                self._states[key] = "margin" if value < touch * 1.15 else "pass"
            elif value >= floor:
                self._states[key] = "fail"
            else:
                self._states[key] = "idle"
        self.update()

    def state_for(self, key: int) -> str:
        return self._states.get(key, "idle")

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width() / 32.0
        p.setFont(t.font(8, mono=True))
        for key in range(1, 33):
            state = self._states.get(key, "idle")
            value = self._values.get(key, -1)
            left = (key - 1) * w + 1
            rect = QRectF(left, 2, max(2.0, w - 2), self.height() - 6)
            if state == "pass":
                fill, edge = t.amber_soft, t.amber
                marker = "✓"
            elif state == "margin":
                fill = QColor(t.amber)
                fill.setAlpha(60)
                edge, marker = t.amber, "!"
            elif state == "fail":
                fill = QColor(t.danger)
                fill.setAlpha(55)
                edge, marker = t.danger, "×"
            else:
                fill, edge, marker = t.card, t.hair, ""
            p.setBrush(fill)
            p.setPen(QPen(edge))
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QPen(t.faint if state == "idle" else t.ink))
            p.drawText(
                QRectF(rect.left(), rect.top() + 1, rect.width(), 14),
                Qt.AlignmentFlag.AlignCenter,
                str(key),
            )
            if value >= 0:
                p.setPen(QPen(t.ink if state != "idle" else t.faint))
                p.drawText(
                    QRectF(rect.left(), rect.top() + 15, rect.width(), 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{marker}{value}" if marker else str(value),
                )
        p.end()


class CurveCard(CardFrame):
    def __init__(self, theme: Theme, page: "CalibrationPage", curve: KeyCurve):
        super().__init__()
        self._theme = theme
        self.page = page
        self.key = curve.key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        top = QHBoxLayout()
        self.title = QLabel("")
        set_scaled_font(self.title, theme, 12, weight=QFont.Weight.DemiBold)
        top.addWidget(self.title)
        top.addStretch(1)
        self.threshold_label = QLabel("")
        self.threshold_label.setProperty("role", "amber")
        self.threshold_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.threshold_label)
        layout.addLayout(top)

        self.meta = QLabel("")
        self.meta.setProperty("role", "faint")
        set_scaled_font(self.meta, theme, 9)
        layout.addWidget(self.meta)

        self.curve_widget = CurveWidget(theme)
        self.curve_widget.thresholdPicked.connect(
            lambda value: self.page.set_threshold(self.key, value)
        )
        layout.addWidget(self.curve_widget)

        controls = QHBoxLayout()
        controls.setSpacing(4)
        for text, action in (
            ("峰值 60%", self._peak_60),
            ("稳定段一半", self._hold_half),
            ("建议", self._suggest),
            ("−5", lambda: self._step(-5)),
            ("−1", lambda: self._step(-1)),
            ("+1", lambda: self._step(1)),
            ("+5", lambda: self._step(5)),
        ):
            button = QPushButton(text)
            button.setProperty("role", "chip")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda checked=False, fn=action: fn())
            controls.addWidget(button)
        controls.addStretch(1)
        self.release_label = QLabel("")
        self.release_label.setProperty("role", "faint")
        set_scaled_font(self.release_label, theme, 9, mono=True)
        controls.addWidget(self.release_label)
        layout.addLayout(controls)

        self.check = QLabel("")
        self.check.setProperty("role", "faint")
        self.check.setWordWrap(True)
        set_scaled_font(self.check, theme, 9)
        layout.addWidget(self.check)

        self.refresh()

    # -- actions ----------------------------------------------------------

    def _curve(self) -> KeyCurve | None:
        return self.page.session.curves.get(self.key)

    def _step(self, delta: int) -> None:
        self.page.set_threshold(
            self.key, self.page.threshold_for(self.key) + delta
        )

    def _peak_60(self) -> None:
        curve = self._curve()
        if curve is not None:
            self.page.set_threshold(
                self.key, max(1, min(SIGNAL_MAX, round(curve.peak * 0.60)))
            )

    def _hold_half(self) -> None:
        curve = self._curve()
        if curve is not None:
            self.page.set_threshold(
                self.key, max(1, min(SIGNAL_MAX, round(curve.hold * 0.50)))
            )

    def _suggest(self) -> None:
        suggestion = self.page.session.suggest(self.key)
        if suggestion:
            self.page.set_threshold(self.key, suggestion)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.curve_widget.set_theme(theme)
        self.refresh()

    def refresh(self) -> None:
        curve = self._curve()
        if curve is None:
            return
        threshold = self.page.threshold_for(self.key)
        release = self.page.session.release_for(threshold)
        self.title.setText(f"键 {curve.key} · {curve.note or '—'}")
        self.threshold_label.setText(f"阈值 {threshold}")
        self.meta.setText(
            f"峰值 {curve.peak} · 噪声 {curve.noise} · 稳定段 {curve.hold}"
            + ("  · 可能卡键" if curve.stuck else "")
        )
        self.release_label.setText(f"释放 {release}")
        self.curve_widget.set_data(curve, threshold, release)

        check = self.page.session.validate(self.key, threshold)
        if not check.ok:
            self.check.setText(check.reason)
            self.check.setStyleSheet(f"color: {self._theme.danger.name()};")
        elif check.warnings:
            self.check.setText("；".join(check.warnings))
            self.check.setStyleSheet(f"color: {self._theme.amber.name()};")
        else:
            self.check.setText(
                f"校验：噪声 {curve.noise} + 5 ≤ {threshold} ≤ 峰值 "
                f"{curve.peak} × 0.9 ✓"
            )
            self.check.setStyleSheet(f"color: {self._theme.faint.name()};")


class CalibrationPage(GlassFrame):
    message = Signal(str)

    def __init__(
        self,
        theme: Theme,
        instrument: Instrument,
        send_line: SendLine,
        profile_path: str | Path | None = None,
        clock: Clock | None = None,
        ready: ReadyCheck | None = None,
    ):
        super().__init__()
        self._theme = theme
        self.instrument = instrument
        self._send = send_line
        self.profile_path = (
            Path(profile_path) if profile_path is not None else None
        )
        self._clock = clock or time.monotonic
        self._ready = ready or (
            lambda: instrument.connected
            and instrument.module_count() >= 3
            and not instrument.hardware_stale()
        )
        self.session = CalibrationSession()
        self.profile: CalibrationProfile | None = None
        self.profile_warning = ""
        self.thresholds: dict[int, int] = {}
        self._user_set: set[int] = set()
        self.stream_on = False
        self.applied = False
        self._active = False
        self._started_at = 0.0
        self._finalized = False
        self._want_stream = False
        self._stream_retries = 0
        self._cards: dict[int, CurveCard] = {}
        self._shown_keys: set[int] = set()
        self.verifying = False
        self._verify_summary = ""
        self.applied_values: dict[int, tuple[int, int]] = {}
        self.applied_by_key: dict[int, tuple[int, int]] = {}
        self._pending_values: dict[int, tuple[int, int]] = {}
        self._pending_by_key: dict[int, tuple[int, int]] = {}
        self._build_ui()
        self.refresh()

    # -- construction -----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(9)

        header = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        badge = QLabel("设备校准")
        badge.setProperty("role", "amber")
        set_scaled_font(badge, self._theme, 11)
        badge.setStyleSheet(
            f"color: {self._theme.amber.name()}; "
            f"font-size: {self._theme.px(11)}px; font-weight: 600;"
        )
        self._badge_label = badge
        heading = QLabel("逐键阈值")
        set_scaled_font(heading, self._theme, 24, weight=QFont.Weight.DemiBold)
        self.sub = QLabel(
            "只调每个键的触键阈值，不做力度。校准期间不发声、不判定、不写学习记录。"
        )
        self.sub.setProperty("role", "muted")
        self.sub.setWordWrap(True)
        left.addWidget(badge)
        left.addWidget(heading)
        left.addWidget(self.sub)
        header.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(5)
        self.scheme_label = QLabel("")
        self.scheme_label.setProperty("role", "muted")
        self.scheme_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.scheme_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.start_button = QPushButton("开始检测")
        self.start_button.setProperty("role", "action")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.start_button.clicked.connect(
            lambda checked=False: self.start_detection()
        )
        self.stop_button = QPushButton("停止")
        self.stop_button.setProperty("role", "chip")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.stop_button.clicked.connect(
            lambda checked=False: self.stop_detection()
        )
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        right.addLayout(buttons)
        header.addLayout(right)
        layout.addLayout(header)

        hint = QLabel(
            "按下想校准的键，可以一次按多个；每个键一张曲线。松开并回落后自动结束。"
        )
        hint.setProperty("role", "faint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        status_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_detail = QLabel("")
        self.status_detail.setProperty("role", "faint")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.status_detail)
        layout.addLayout(status_row)

        self.verify_strip = VerifyStrip(self._theme)
        self.verify_strip.hide()
        layout.addWidget(self.verify_strip)
        self.verify_legend = QLabel(
            "✓ 通过 · ! 余量不足 15% · × 按了未识别 · 按和弦验证"
        )
        self.verify_legend.setProperty("role", "faint")
        self.verify_legend.hide()
        layout.addWidget(self.verify_legend)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.curves_host = QWidget()
        self.curves_host.setObjectName("ScrollContent")
        self._curves_layout = QVBoxLayout(self.curves_host)
        self._curves_layout.setContentsMargins(0, 0, 0, 0)
        self._curves_layout.setSpacing(8)
        self._curves_layout.addStretch(1)
        self.scroll.setWidget(self.curves_host)
        layout.addWidget(self.scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.apply_button = QPushButton("应用到设备")
        self.apply_button.setProperty("role", "action")
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.apply_button.clicked.connect(
            lambda checked=False: self.apply_to_device()
        )
        self.save_button = QPushButton("保存方案")
        self.save_button.setProperty("role", "chip")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.save_button.clicked.connect(
            lambda checked=False: self.save_profile()
        )
        self.retest_button = QPushButton("再测一次")
        self.retest_button.setProperty("role", "chip")
        self.retest_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retest_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.retest_button.clicked.connect(lambda checked=False: self.retest())
        footer.addWidget(self.apply_button)
        self.verify_button = QPushButton("多指验证")
        self.verify_button.setProperty("role", "chip")
        self.verify_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.verify_button.clicked.connect(
            lambda checked=False: self.toggle_verification()
        )
        footer.addWidget(self.verify_button)
        footer.addWidget(self.save_button)
        footer.addWidget(self.retest_button)
        footer.addStretch(1)
        self.device_label = QLabel("")
        self.device_label.setProperty("role", "faint")
        footer.addWidget(self.device_label)
        layout.addLayout(footer)

    # -- public state -----------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._badge_label.setStyleSheet(
            f"color: {theme.amber.name()}; "
            f"font-size: {theme.px(11)}px; font-weight: 600;"
        )
        self.verify_strip.set_theme(theme)
        for card in list(self._cards.values()):
            card.set_theme(theme)
        self.refresh()

    def enter(self) -> None:
        """Begin a calibration visit: mute/lock and load the saved plan."""
        if self._active:
            return
        self._active = True
        self._load_profile()
        self.session = CalibrationSession(self.session.keymap)
        self.thresholds.clear()
        self._user_set.clear()
        self.stream_on = False
        self._want_stream = False
        self._stream_retries = 0
        self._finalized = False
        self._shown_keys = set()
        self.verifying = False
        self._verify_summary = ""
        self.applied_values = {}
        self.applied_by_key = {}
        self._pending_values = {}
        self._pending_by_key = {}
        if (
            self.applied
            and self.profile is not None
            and self.profile.is_complete()
        ):
            # An auto-applied plan is already on the device; verification can
            # start without making the user re-apply it.
            self.applied_values = self.profile.values_by_channel()
            self.applied_by_key = {
                item.key: (item.touch, item.release)
                for item in self.profile.keys
            }
        self.verify_strip.hide()
        self.verify_legend.hide()
        self._rebuild_cards()
        self.instrument.begin_calibration()
        self.refresh()

    def leave(self) -> None:
        """Stop the stream, freeze the session and restore performance."""
        if not self._active:
            return
        self._end_verification(send_off=False)
        if self.session.state in ("baseline", "monitoring"):
            self.session.stop(self._clock())
        self._stop_stream()
        self.instrument.end_calibration()
        self._active = False
        self._want_stream = False
        self.refresh()

    @property
    def active(self) -> bool:
        return self._active

    def threshold_for(self, key: int) -> int:
        value = self.thresholds.get(key)
        if value is None:
            value = self.session.suggest(key) or 8
        return max(1, min(SIGNAL_MAX, int(value)))

    def set_threshold(self, key: int, value: int) -> None:
        if key not in self.session.curves:
            return
        self.thresholds[key] = max(1, min(SIGNAL_MAX, int(value)))
        self._user_set.add(key)
        card = self._cards.get(key)
        if card is not None:
            card.refresh()

    # -- detection --------------------------------------------------------

    def start_detection(self) -> bool:
        if not self._ready():
            self.message.emit("先连接设备并确认 3 个模块在线")
            return False
        self._end_verification(send_off=False)
        self.applied_values = {}
        self.applied_by_key = {}
        self._pending_values = {}
        self._pending_by_key = {}
        if not self.stream_on:
            if not self._send("c"):
                self.message.emit("串口未连接，无法开始校准")
                return False
            self.stream_on = True
            self._want_stream = True
            self._stream_retries = 0
        self.session = CalibrationSession(self.session.keymap)
        self.thresholds.clear()
        self._user_set.clear()
        self.applied = False
        self._finalized = False
        self._shown_keys = set()
        self._started_at = self._clock()
        self.session.start(self._started_at)
        self._rebuild_cards()
        self.refresh()
        return True

    def stop_detection(self) -> None:
        if self.session.state in ("baseline", "monitoring"):
            self.session.stop(self._clock())
        self._stop_stream()
        self._sync_thresholds()
        self._finalized = True
        self._refresh_cards()
        self.refresh()

    def retest(self) -> None:
        self._stop_stream()
        self.start_detection()

    def device_disconnected(self) -> None:
        """Freeze the curves and stop pretending the stream is alive."""
        if not self._active:
            return
        self._end_verification(send_off=False)
        if self.session.state in ("baseline", "monitoring"):
            self.session.stop(self._clock())
        self.stream_on = False
        self._want_stream = False
        self.applied = False
        self._finalized = True
        self._sync_thresholds()
        self._refresh_cards()
        self.refresh()

    # -- multi-key verification ------------------------------------------

    def toggle_verification(self) -> None:
        if self.verifying:
            self._end_verification(send_off=True)
            return
        if not self.applied_values:
            self.message.emit("先应用阈值，再验证多指和弦")
            return
        if not self.stream_on:
            if not self._send("c"):
                self.message.emit("串口未连接，无法验证")
                return
            self.stream_on = True
        self.verifying = True
        self._verify_summary = ""
        self.verify_strip.clear()
        self.verify_strip.show()
        self.verify_legend.show()
        self.verify_button.setText("结束验证")
        self.refresh()

    def _end_verification(self, send_off: bool) -> None:
        if not self.verifying:
            return
        self.verifying = False
        self._verify_summary = ""
        self.verify_strip.hide()
        self.verify_legend.hide()
        self.verify_button.setText("多指验证")
        if send_off and self.stream_on:
            self._send("c")
            self.stream_on = False
        self.refresh()

    def _update_verification(self, frame: CalibrationFrame) -> None:
        values: dict[int, int] = {}
        for channel, value in frame.values.items():
            info = self.session.keymap.get(channel)
            if info is not None:
                values[int(info["key"])] = value
        noise = {
            key: curve.noise
            for key, curve in self.session.curves.items()
        }
        self.verify_strip.set_data(values, self.applied_by_key, noise)
        total = len(self.applied_by_key)
        passed = sum(
            1
            for key in self.applied_by_key
            if self.verify_strip.state_for(key) in ("pass", "margin")
        )
        self._verify_summary = (
            f"多指验证 · 通过 {passed}/{total} · 按和弦"
            if total
            else "多指验证 · 先应用阈值"
        )
        self.status_label.setText(self._verify_summary)

    def feed_frame(self, frame: CalibrationFrame) -> None:
        if not self._active:
            return
        if self.verifying:
            self._update_verification(frame)
            return
        if self.session.state not in ("baseline", "monitoring"):
            return
        self.session.feed(frame)
        if self.session.state == "monitoring" and set(self.session.curves) != self._shown_keys:
            self._sync_thresholds()
            self._rebuild_cards()
        elif self.session.state != "baseline":
            self._refresh_cards()
        if self.session.auto_stopped and self.stream_on:
            self._stop_stream()
            self._want_stream = False
        if self.session.state == "stopped" and not self._finalized:
            self._finalized = True
            self._sync_thresholds()
            self._refresh_cards()
        self.refresh()

    def _sync_thresholds(self) -> None:
        for key in self.session.curves:
            if key not in self._user_set:
                suggestion = self.session.suggest(key)
                if suggestion:
                    self.thresholds[key] = suggestion

    def _stop_stream(self) -> None:
        if self.stream_on:
            self._send("c")
        self.stream_on = False
        self._want_stream = False

    # -- apply / save / replies ------------------------------------------

    def apply_to_device(self) -> bool:
        values = self.session.apply_values(self.thresholds)
        if not values:
            self.message.emit("还没有采集到按键")
            return False
        for key in sorted(self.session.curves):
            check = self.session.validate(key, self.threshold_for(key))
            if not check.ok:
                self.message.emit(f"键 {key}：{check.reason}")
                return False
        if self.profile is not None and self.profile.is_complete():
            merged = self.profile.values_by_channel()
            merged.update(values)
            values = merged
        key_to_channel = {
            int(info["key"]): channel
            for channel, info in self.session.keymap.items()
        }
        self._pending_values = dict(values)
        self._pending_by_key = {
            key: values[channel]
            for key, channel in key_to_channel.items()
            if channel in values
        }
        if not self._send(format_thresholds(values)):
            self._pending_values = {}
            self._pending_by_key = {}
            self.message.emit("串口未连接，阈值未发送")
            return False
        # Verification uses what the device confirmed, not what we asked for.
        self.applied_values = {}
        self.applied_by_key = {}
        self.applied = False
        self.message.emit("已发送阈值，等待设备确认")
        self.refresh()
        return True

    def save_profile(self) -> bool:
        profile = self.session.profile(
            name=(self.profile.name if self.profile else "本机校准"),
            gain=(self.profile.gain if self.profile else 0),
            touch_overrides=self.thresholds,
            base=self.profile,
        )
        if not profile.is_complete():
            self.message.emit("还没有覆盖 32 个键；先继续校准或应用已有方案")
            return False
        if self.profile_path is None:
            self.message.emit("没有可写的校准文件路径")
            return False
        profile.save(self.profile_path)
        self.profile = profile
        self.message.emit("校准方案已保存")
        self.refresh()
        return True

    def handle_reply(self, text: str) -> bool:
        text = text.strip()
        if text == "CAL ON":
            self.stream_on = True
            return True
        if text == "CAL OFF":
            self.stream_on = False
            if (
                self._active
                and self._want_stream
                and self.session.state in ("baseline", "monitoring")
                and self._stream_retries < 1
            ):
                # The stream was already on from a previous session; one
                # retry turns it back on instead of waiting forever.
                self._stream_retries += 1
                if self._send("c"):
                    self.stream_on = True
            return True
        reply = parse_threshold_reply(text)
        if reply is None:
            return False
        kind, channel = reply
        if kind == "ok":
            self.applied = True
            self.applied_values = dict(self._pending_values)
            self.applied_by_key = dict(self._pending_by_key)
            self._pending_values = {}
            self._pending_by_key = {}
            self.message.emit("阈值已应用到设备")
        else:
            self.applied = False
            self._pending_values = {}
            self._pending_by_key = {}
            self.message.emit(f"设备拒绝通道 {channel} 的阈值")
        self.refresh()
        return True

    # -- view updates -----------------------------------------------------

    def refresh(self) -> None:
        ready = bool(self._ready())
        active = self._active
        carrying = self.session.state in ("baseline", "monitoring")
        stopped = self.session.state == "stopped"
        self.start_button.setEnabled(ready and not active)
        self.stop_button.setEnabled(active and carrying)
        self.apply_button.setEnabled(active and stopped and bool(self.session.curves))
        self.save_button.setEnabled(active and stopped and bool(self.session.curves))
        self.retest_button.setEnabled(active and self.session.state != "idle")
        self.verify_button.setText("结束验证" if self.verifying else "多指验证")
        self.verify_button.setEnabled(
            active and (self.verifying or bool(self.applied_values))
        )

        if self.profile is not None:
            gain = f"增益 {self.profile.gain}" if self.profile.gain else "增益未知"
            status = "已应用" if self.applied else "未应用"
            self.scheme_label.setText(
                f"方案 · {self.profile.name or '未命名'} · "
                f"{self.profile.created_at[:10] or '—'} · {gain} · {status}"
            )
        else:
            status = "本次已应用" if self.applied else "未校准"
            self.scheme_label.setText(f"方案 · {status}")

        online = self.instrument.module_count()
        self.device_label.setText(
            f"{online}/3 模块在线 · "
            + ("串口已连接" if self.instrument.connected else "串口未连接")
        )

        if not active:
            text = (
                "点「开始检测」；先松手采集噪声底"
                if ready
                else "先连接设备并确认 3 个模块在线"
            )
            detail = ""
        elif not self.instrument.connected:
            text = "设备已断开；重新连接后点「再测一次」"
            detail = ""
        elif self.verifying:
            text = self._verify_summary or "多指验证：按和弦"
            detail = ""
        elif self.session.state == "baseline":
            elapsed = max(0.0, self._clock() - self._started_at)
            remaining = max(0.0, BASELINE_SECONDS - elapsed)
            text = "请松手，正在采集噪声底…"
            detail = f"{remaining:.1f} s"
        elif self.session.state == "monitoring":
            if self.session.curves:
                text = f"已捕获 {len(self.session.curves)} 个键 · 松开后自动结束"
            else:
                text = "请按键…（可多键同时按）"
            stuck = any(curve.stuck for curve in self.session.curves.values())
            detail = "可能卡键" if stuck else ""
        elif self.session.state == "stopped":
            text = f"检测完成 · {len(self.session.curves)} 个键"
            if self.applied:
                text += " · 已应用"
            stuck = any(curve.stuck for curve in self.session.curves.values())
            detail = "可能卡键" if stuck else ("自动停止" if self.session.auto_stopped else "")
        else:
            text = "就绪"
            detail = ""
        self.status_label.setText(text)
        self.status_detail.setText(detail)

    def _load_profile(self) -> None:
        if self.profile_path is None:
            self.profile = None
            self.profile_warning = ""
            return
        self.profile, self.profile_warning = CalibrationProfile.load(
            self.profile_path
        )
        if self.profile_warning:
            self.message.emit(self.profile_warning)

    def _rebuild_cards(self) -> None:
        while self._curves_layout.count():
            item = self._curves_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        keys = sorted(self.session.curves)
        self._shown_keys = set(keys)
        if not keys:
            empty = QLabel("还没有曲线。连接设备后点「开始检测」。")
            empty.setProperty("role", "faint")
            empty.setWordWrap(True)
            self._curves_layout.addWidget(empty)
        else:
            for key in keys:
                card = CurveCard(self._theme, self, self.session.curves[key])
                self._curves_layout.addWidget(card)
                self._cards[key] = card
        self._curves_layout.addStretch(1)

    def _refresh_cards(self) -> None:
        for card in self._cards.values():
            card.refresh()
