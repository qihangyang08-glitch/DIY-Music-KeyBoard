"""Main window: header, left rail, performance page, status bar, wiring."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.accessibility import (
    AccessibilityPrefs,
    normalize_font_scale,
    normalize_language,
)
from ..core.accessibility import default_path as accessibility_path_default
from ..core.calibration import (
    CalibrationProfile,
    format_thresholds,
    parse_threshold_reply,
)
from ..core.calibration import default_path as calibration_path_default
from ..core.accompaniment import split_accompaniment
from ..core.curriculum import (
    SCORE_DIR,
    mapping_for_library_path,
    project_path,
    score_path,
    stage_by_index,
)
from ..core.drill import DrillTarget, drill_spec
from ..core.exam import exam_by_key
from ..core.follow import FollowSession
from ..core.instrument import Instrument
from ..core.library import DISPLAY_SUFFIXES, default_import_dir
from ..core.onboarding import OnboardingState
from ..core.onboarding import default_path as onboarding_path_default
from ..core.progress import LearningProgress
from ..core.project import Project, default_project_dir
from ..core.score import ScoreError, parse_score
from ..core.score_prefs import ScorePrefs, default_path as score_prefs_path, score_key
from ..core.serial_service import SerialService
from ..core.synth_service import make_synth
from .creation_page import CreationPage
from .drill_page import DrillPage
from .keybindings import KeyBindings
from .keybindings_page import KeyBindingsPage
from .learning_page import ExamTarget, LearningPage, PracticeTarget, ProjectTarget
from .i18n_ui import apply_language, set_language, tr
from .calibration_page import CalibrationPage
from .help_page import HelpPage
from .library_page import LibraryPage
from .onboarding import OnboardingDialog
from .pages import DevicePage, SettingsPage, SoundPage, MODULES
from .perform_view import PerformView
from .theme import (
    THEMES,
    Theme,
    refresh_scaled_fonts,
    set_scaled_font,
)
from .widgets import DotStrip, GlassFrame, Toast, VolumeButton, hairline

NAV_ITEMS = (
    ("▶", "演奏"),
    ("✦", "学习"),
    ("♬", "曲谱"),
    ("✎", "创作"),
    ("▣", "设备"),
    ("⚙", "设置"),
    ("?", "帮助"),
)

SAMPLE_SCORE = (
    Path(__file__).resolve().parents[2] / "resources" / "scores" / "xiaoxingxing.musicxml"
)


class RootWidget(QWidget):
    """Background wash behind the glass panels."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setObjectName("Root")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), t.bg)

        w, h = self.width(), self.height()
        warm = QRadialGradient(w * 0.84, -h * 0.08, w * 0.62)
        amber = QColor(t.amber)
        amber.setAlpha(30 if not t.dark else 22)
        clear = QColor(t.amber)
        clear.setAlpha(0)
        warm.setColorAt(0, amber)
        warm.setColorAt(1, clear)
        p.fillRect(self.rect(), warm)

        cool = QRadialGradient(w * 0.06, h * 1.02, w * 0.6)
        light = QColor(t.bg2)
        light.setAlpha(235 if not t.dark else 190)
        light_clear = QColor(t.bg2)
        light_clear.setAlpha(0)
        cool.setColorAt(0, light)
        cool.setColorAt(1, light_clear)
        p.fillRect(self.rect(), cool)
        p.end()


class MainWindow(QMainWindow):
    def __init__(
        self,
        port: Optional[str] = None,
        serial_enabled: bool = True,
        audio_enabled: bool = True,
        gain: float = 0.6,
        theme_name: str = "studio",
        fullscreen: bool = False,
        bindings_path: str | Path | None = None,
        progress_path: str | Path | None = None,
        library_root: str | Path | None = None,
        projects_root: str | Path | None = None,
        prefs_path: str | Path | None = None,
        accessibility_path: str | Path | None = None,
        calibration_path: str | Path | None = None,
        onboarding_path: str | Path | None = None,
        auto_onboarding: bool = False,
        library_watch: bool = True,
    ):
        super().__init__()
        self.setWindowTitle("KeyBorad · 32 键电子琴")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 760)
        self.learning_progress = LearningProgress.load(progress_path)
        self.library_root = (
            Path(library_root)
            if library_root is not None
            else default_import_dir()
        )
        self.projects_root = (
            Path(projects_root)
            if projects_root is not None
            else default_project_dir()
        )
        self.library_watch = library_watch
        self.score_prefs = ScorePrefs.load(
            prefs_path if prefs_path is not None else score_prefs_path()
        )
        self.accessibility = AccessibilityPrefs.load(
            accessibility_path
            if accessibility_path is not None
            else accessibility_path_default()
        )
        self.calibration_path = (
            Path(calibration_path)
            if calibration_path is not None
            else calibration_path_default()
        )
        self.calibration_applied = False
        self._calibration_apply_pending = False
        self._calibration_warning_shown = False
        self.onboarding_path = (
            Path(onboarding_path)
            if onboarding_path is not None
            else onboarding_path_default()
        )
        self.auto_onboarding = bool(auto_onboarding)
        self._onboarding_shown = False
        self._calibration_timeout = QTimer(self)
        self._calibration_timeout.setSingleShot(True)
        self._calibration_timeout.timeout.connect(
            self._on_calibration_timeout
        )
        set_language(self.accessibility.language)
        self._score_key: str | None = None
        self._study_active = False
        self._study_target: PracticeTarget | None = None
        self._project_active = False
        self._project_target: ProjectTarget | None = None

        self.theme_name = theme_name if theme_name in THEMES else "studio"
        self.theme: Theme = self._build_theme(self.theme_name)
        self.bindings = KeyBindings(bindings_path)
        self.serial_enabled = serial_enabled
        self._serial: Optional[SerialService] = None
        self._closed = False
        self._first_refresh = True
        self._last_preset_key = ""
        self._last_auto = False
        self._window_config = None

        self.synth, self.audio_message = make_synth(audio_enabled, gain)
        self.instrument = Instrument(self.synth)

        self.root = RootWidget(self.theme)
        self.setCentralWidget(self.root)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(18, 18, 18, 14)
        outer.setSpacing(12)

        self.toast = Toast(self.root)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(12)
        self.rail = self._build_rail()
        body.addWidget(self.rail)
        self.stack = QStackedWidget()
        self._build_pages()
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        outer.addWidget(self._build_status())

        self.follow = FollowSession(self.instrument, self)
        self.follow.scoreChanged.connect(self._on_score_changed)
        self.follow.nextChanged.connect(self._on_next_note)
        self.follow.stateChanged.connect(self._on_follow_state)
        self.follow.judged.connect(self._on_judged)
        self.follow.finished.connect(self._on_score_finished)
        self.follow.message.connect(self.toast.show_message)
        self.follow.demoNote.connect(self.perform.add_wave)
        self.follow.windowChanged.connect(self._on_window_changed)
        self.perform.score.scoreFileDropped.connect(self._load_score_file)
        self.perform.score.imageOpened.connect(self._on_display_opened)
        self.perform.score.restartRequested.connect(self._restart_score)
        self._load_builtin_score()

        self.apply_theme(self.theme_name, first=True)
        self._connect_instrument()
        self._start_serial(port)
        self._refresh_state()
        apply_language(self)
        QApplication.instance().installEventFilter(self)

        if self.auto_onboarding:
            QTimer.singleShot(600, self._maybe_show_onboarding)
        if fullscreen:
            QTimer.singleShot(0, self.showFullScreen)

    # -- construction -----------------------------------------------------

    def _build_header(self) -> QWidget:
        header = GlassFrame()
        header.setFixedHeight(54)
        row = QHBoxLayout(header)
        row.setContentsMargins(18, 0, 14, 0)
        row.setSpacing(12)

        wordmark = QLabel("KEYBORAD")
        wordmark.setProperty("role", "brand")
        set_scaled_font(wordmark, self.theme, 14, QFont.Weight.Bold)
        row.addWidget(wordmark)
        sub = QLabel("32 键电子琴")
        sub.setProperty("role", "faint")
        set_scaled_font(sub, self.theme, 9, QFont.Weight.DemiBold)
        row.addWidget(sub)
        divider = hairline(vertical=True)
        divider.setFixedHeight(22)
        row.addWidget(divider)

        self.dots = DotStrip(self.theme)
        row.addWidget(self.dots)
        self.device_label = QLabel("等待设备")
        self.device_label.setProperty("role", "muted")
        row.addWidget(self.device_label)

        self.map_chip = QPushButton("映射 · 半音阶 · F4–C7")
        self.map_chip.setProperty("role", "chip")
        self.map_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.map_chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.map_chip.setToolTip("切换映射预设（Ctrl+M）")
        self.map_chip.clicked.connect(self.instrument.cycle_preset)
        row.addWidget(self.map_chip)

        profile = QPushButton("方案 · 裸铜")
        profile.setProperty("role", "chip")
        profile.setCursor(Qt.CursorShape.PointingHandCursor)
        profile.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        profile.clicked.connect(
            lambda: self.toast.show_message("方案 · 裸铜 · 多套方案在后续版本接入")
        )
        row.addWidget(profile)
        row.addStretch(1)

        # Study session indicator: visible only after 学习 hands off to another
        # page, and on every page, so the user can always come back. Hidden in
        # a normal session, so non-learners never see it.
        self.study_return = QPushButton("← 返回学习")
        self.study_return.setProperty("role", "action")
        self.study_return.setCursor(Qt.CursorShape.PointingHandCursor)
        self.study_return.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.study_return.setToolTip("回到学习页的当前阶段 / 指导书")
        self.study_return.clicked.connect(
            lambda checked=False: self._return_to_study()
        )
        self.study_return.hide()
        row.addWidget(self.study_return)

        # The 创作 page reports its take clock here; hidden otherwise so the
        # header does not grow for users who never record.
        self.record_dot = QLabel("● 00:00")
        self.record_dot.setProperty("role", "danger")
        set_scaled_font(self.record_dot, self.theme, 11, QFont.Weight.DemiBold, mono=True)
        self.record_dot.setToolTip("录音中")
        self.record_dot.hide()
        row.addWidget(self.record_dot)

        self.latency_label = QLabel("20 ms")
        self.latency_label.setProperty("role", "faint")
        row.addWidget(self.latency_label)
        self._rate_text = (
            f"{self.synth.samplerate // 1000} kHz"
            if self.synth.samplerate
            else tr("无音频")
        )
        self.rate_label = QLabel(self._rate_text)
        self.rate_label.setProperty("role", "faint")
        self.rate_label.setToolTip(self.audio_message)
        row.addWidget(self.rate_label)

        self.volume_btn = VolumeButton(self.theme)
        self.volume_btn.toggled.connect(self._on_mute_toggled)
        row.addWidget(self.volume_btn)

        self.help_button = QPushButton("?")
        self.help_button.setProperty("role", "icon")
        self.help_button.setFixedSize(34, 34)
        self.help_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.help_button.setToolTip(tr("怎么用（F1）"))
        self.help_button.clicked.connect(
            lambda checked=False: self._show_help_page()
        )
        row.addWidget(self.help_button)

        settings = QPushButton("⋯")
        settings.setProperty("role", "icon")
        settings.setFixedSize(34, 34)
        settings.setCursor(Qt.CursorShape.PointingHandCursor)
        settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        settings.setToolTip("设置")
        settings.clicked.connect(lambda: self._show_page(5))
        row.addWidget(settings)
        return header

    def _build_rail(self) -> QWidget:
        rail = GlassFrame()
        rail.setFixedWidth(156)
        col = QVBoxLayout(rail)
        col.setContentsMargins(10, 12, 10, 12)
        col.setSpacing(4)

        mode = QLabel("导航")
        mode.setProperty("role", "faint")
        set_scaled_font(mode, self.theme, 9, QFont.Weight.DemiBold)
        col.addWidget(mode)
        col.addSpacing(2)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, (glyph, label) in enumerate(NAV_ITEMS):
            if index == 5:
                col.addStretch(1)
                col.addWidget(hairline())
            btn = QPushButton(f"{glyph}   {tr(label)}")
            btn.setProperty("role", "nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setToolTip(f"{label}（Ctrl+{index + 1}）")
            self.nav_group.addButton(btn, index)
            btn.clicked.connect(lambda checked=False, i=index: self._show_page(i))
            col.addWidget(btn)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)
        return rail

    def _build_pages(self) -> None:
        self.perform = PerformView(self.theme, self.instrument, self.bindings)
        self.perform.message.connect(self.toast.show_message)
        self.perform.focusToggled.connect(self._on_focus_mode)
        self.perform.band.splitBarDragged.connect(self._on_split_bar_dragged)
        self.perform.band.splitBarCommitted.connect(
            self._on_split_bar_committed
        )
        self.perform.resetSplitRequested.connect(self._reset_split_bar)

        self.learning_page = LearningPage(self.theme, self.learning_progress)
        self.learning_page.practiceRequested.connect(self._start_study_practice)
        self.learning_page.drillRequested.connect(self._start_drill)
        self.learning_page.examRequested.connect(self._start_exam)
        self.learning_page.projectRequested.connect(self._start_project)
        self.learning_page.message.connect(self.toast.show_message)
        self.drill_page = DrillPage(
            self.theme, self.instrument, self.bindings, self.learning_progress
        )
        self.drill_page.closed.connect(self._on_drill_closed)
        self.drill_page.progressChanged.connect(self._on_drill_progress)
        self.drill_page.message.connect(self.toast.show_message)
        self.library_page = LibraryPage(
            self.theme,
            import_dir=self.library_root,
            watch_enabled=self.library_watch,
        )
        self.library_page.scoreRequested.connect(self._open_library_score)
        self.library_page.displayRequested.connect(self._open_library_image)
        self.library_page.message.connect(self.toast.show_message)
        self.compose_page = CreationPage(
            self.theme, self.instrument, self.bindings, self.projects_root
        )
        self.compose_page.message.connect(self.toast.show_message)
        self.compose_page.recordingChanged.connect(self._on_compose_recording)
        self.compose_page.durationChanged.connect(self._on_compose_duration)
        self.compose_page.learningCheckRequested.connect(self._check_project_steps)
        self.device_page = DevicePage(self.theme, self.instrument)
        self.settings_page = SettingsPage(self.theme)
        self.settings_page.themeRequested.connect(self.apply_theme)
        self.settings_page.soundRequested.connect(
            lambda: self._show_subpage(self.sound_page, 5)
        )
        self.settings_page.keybindingsRequested.connect(
            lambda: self._show_subpage(self.keybindings_page, 5)
        )
        self.settings_page.helpRequested.connect(self._show_help_page)

        self.calibration_page = CalibrationPage(
            self.theme,
            self.instrument,
            send_line=self._send_serial_line,
            profile_path=self.calibration_path,
            ready=self._calibration_ready,
        )
        self.calibration_page.message.connect(self.toast.show_message)
        self.sound_page = SoundPage(self.theme, self.instrument, self.audio_message)
        self.keybindings_page = KeyBindingsPage(
            self.theme, self.bindings, self.instrument
        )
        self.keybindings_page.changed.connect(self._on_bindings_changed)
        self.device_page.calibrationRequested.connect(
            lambda: self._show_subpage(self.calibration_page, 4)
        )
        self.help_page = HelpPage(
            self.theme, self.instrument, self.bindings
        )
        self.help_page.onboardingRequested.connect(
            lambda: self._show_onboarding(force=True)
        )
        self.help_page.calibrationRequested.connect(
            lambda: self._show_subpage(self.calibration_page, 4)
        )
        self.help_page.keybindingsRequested.connect(
            lambda: self._show_subpage(self.keybindings_page, 5)
        )

        # Seven v3 nav pages; calibration / sound / keybindings are sub-pages.
        self.pages = (
            self.perform,
            self.learning_page,
            self.library_page,
            self.compose_page,
            self.device_page,
            self.settings_page,
            self.help_page,
        )
        for page in self.pages:
            self.stack.addWidget(page)
        for page in (
            self.calibration_page,
            self.sound_page,
            self.keybindings_page,
            self.drill_page,
        ):
            self.stack.addWidget(page)

        self.settings_page.reduceMotionChanged.connect(
            self._set_reduce_motion
        )
        self.settings_page.fontScaleChanged.connect(self._set_font_scale)
        self.settings_page.languageRequested.connect(self._set_language)
        self.perform.set_accessibility(self.accessibility.reduce_motion)
        self.settings_page.set_reduce_motion(
            self.accessibility.reduce_motion
        )
        self.settings_page.set_font_scale(self.accessibility.font_scale)
        self.settings_page.set_language(self.accessibility.language)

    def _build_status(self) -> QWidget:
        status = GlassFrame()
        status.setFixedHeight(34)
        row = QHBoxLayout(status)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(8)

        caption = QLabel("当前")
        caption.setProperty("role", "faint")
        row.addWidget(caption)
        self.now_label = QLabel("—")
        self.now_label.setProperty("role", "amber")
        set_scaled_font(self.now_label, self.theme, 11, QFont.Weight.DemiBold, mono=True)
        row.addWidget(self.now_label)
        row.addSpacing(10)

        next_caption = QLabel("下一键")
        next_caption.setProperty("role", "faint")
        row.addWidget(next_caption)
        self.next_status_value = QLabel("—")
        self.next_status_value.setProperty("role", "mono")
        set_scaled_font(self.next_status_value, self.theme, 10, mono=True)
        row.addWidget(self.next_status_value)
        row.addSpacing(10)

        last_caption = QLabel("最近")
        last_caption.setProperty("role", "faint")
        row.addWidget(last_caption)
        self.last_label = QLabel("—")
        self.last_label.setProperty("role", "faint")
        set_scaled_font(self.last_label, self.theme, 10, mono=True)
        self.last_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.last_label, 1)
        row.addStretch(1)

        self.source_label = QLabel("输入 · 无")
        self.source_label.setProperty("role", "faint")
        set_scaled_font(self.source_label, self.theme, 9, QFont.Weight.Medium, mono=True)
        row.addWidget(self.source_label)

        self.status_modules = QLabel("电脑键盘")
        self.status_modules.setProperty("role", "faint")
        row.addWidget(self.status_modules)
        self.status_latency = QLabel(f"20 ms · {self._rate_text}")
        self.status_latency.setProperty("role", "faint")
        row.addWidget(self.status_latency)
        return status

    # -- wiring -----------------------------------------------------------

    def _connect_instrument(self) -> None:
        inst = self.instrument
        inst.events.connect(self._on_events)
        inst.activeChanged.connect(self._on_active)
        inst.stateChanged.connect(self._refresh_state)
        inst.padStateChanged.connect(self.perform.set_pad_state)
        inst.sourceChanged.connect(self._refresh_notes)

    def _start_serial(self, port: Optional[str]) -> None:
        if not self.serial_enabled:
            return
        self._serial = SerialService(port, self)
        self._serial.frameReady.connect(self.instrument.set_hardware_frame)
        self._serial.calibrationFrame.connect(self.calibration_page.feed_frame)
        self._serial.connectionChanged.connect(self._on_connection)
        self._serial.notice.connect(self._on_notice)
        self._serial.notice.connect(self.calibration_page.handle_reply)
        self._serial.notice.connect(self._on_calibration_reply)
        self._serial.start()

    def _send_serial_line(self, text: str) -> bool:
        if self._serial is None:
            return False
        return self._serial.send_line(text)

    def _calibration_ready(self) -> bool:
        inst = self.instrument
        return (
            self.serial_enabled
            and inst.connected
            and inst.module_count() >= 3
            and not inst.hardware_stale()
        )

    def _on_connection(self, connected: bool, detail: str) -> None:
        self.instrument.set_connection(connected, detail)
        if not connected:
            self._calibration_apply_pending = False
            self._calibration_timeout.stop()
            if hasattr(self, "calibration_page"):
                self.calibration_page.device_disconnected()
        if connected:
            self.toast.show_message(f"设备已连接 · {detail}")
            self._apply_saved_calibration()
        elif "等待设备" not in detail:
            self.toast.show_message(f"设备断开 · {detail}")

    def _apply_saved_calibration(self) -> bool:
        """Re-send calibration.json after every connect; the firmware RAM is
        wiped by a power cycle, so the PC is the source of truth."""
        profile, warning = CalibrationProfile.load(self.calibration_path)
        if warning:
            self.calibration_applied = False
            if not self._calibration_warning_shown:
                self._calibration_warning_shown = True
                self.toast.show_message(warning, 3200)
            return False
        if profile is None:
            self.calibration_applied = False
            return False
        if not self._send_serial_line(
            format_thresholds(profile.values_by_channel())
        ):
            return False
        self._calibration_apply_pending = True
        self._calibration_timeout.start(3000)
        self.toast.show_message(
            f"正在应用校准方案 · {profile.name or '未命名'}…", 2200
        )
        return True

    def _on_calibration_reply(self, text: str) -> None:
        reply = parse_threshold_reply(text)
        if reply is None:
            return
        kind, _channel = reply
        self._calibration_apply_pending = False
        self._calibration_timeout.stop()
        self.calibration_applied = kind == "ok"

    def _on_calibration_timeout(self) -> None:
        if not self._calibration_apply_pending:
            return
        self._calibration_apply_pending = False
        self.calibration_applied = False
        self.toast.show_message("校准方案未应用 · 设备无应答", 3000)

    def _on_notice(self, text: str) -> None:
        # Firmware boot banners and notices: keep the last one visible in the
        # status line rather than spamming toasts.
        if text:
            self.last_label.setText(text[:70])
            self.last_label.setToolTip(text)

    def _on_compose_recording(self, on: bool) -> None:
        self.record_dot.setVisible(on)
        if not on:
            self.record_dot.setText("● 00:00")

    def _on_compose_duration(self, text: str) -> None:
        self.record_dot.setText(f"● {text}")

    def _on_events(self, events: list) -> None:
        stamp = time.strftime("%H:%M:%S")
        current = self.stack.currentWidget()
        on_drill = current is self.drill_page
        on_compose = current is getattr(self, "compose_page", None)
        drill_notes: list[int] = []
        for event in events:
            if event.kind == "on":
                if on_compose:
                    self.compose_page.note_event(event)
                elif not on_drill:
                    self.perform.add_wave(event.key)
                self.last_label.setText(f"{stamp} · {event.note} 按下")
                if on_drill:
                    # The drill owns the note while its page is showing; the
                    # loaded score must not collect phantom hits/misses.
                    drill_notes.append(event.midi)
                elif not on_compose and hasattr(self, "follow"):
                    self.follow.note_on(event.key)
            else:
                if on_compose:
                    self.compose_page.note_event(event)
                self.last_label.setText(f"{stamp} · {event.note} 松开")
        if drill_notes:
            # One verdict per 20 ms engine batch; see DrillPage.note_batch.
            self.drill_page.note_batch(drill_notes)
        self._refresh_notes()

    # -- score / follow ---------------------------------------------------

    def _load_builtin_score(self) -> None:
        if not SAMPLE_SCORE.exists():
            self.toast.show_message("未找到内置示例谱 · 可拖入 MusicXML/MIDI")
            return
        self._load_score_file(str(SAMPLE_SCORE), announce=False)

    def _load_score_file(
        self,
        path: str,
        announce: bool = True,
        from_study: bool = False,
        accompaniment: str = "",
        mapping: str = "",
    ) -> bool:
        if Path(path).suffix.lower() in DISPLAY_SUFFIXES:
            self.toast.show_message("图片/PDF 仅显示 · 不能进入跟弹")
            return False
        # Parse before ending a drill or a study session: a stale or corrupt
        # card must not throw away the user's current practice context.
        try:
            score = parse_score(path)
        except ScoreError as exc:
            self.toast.show_message(f"谱面载入失败：{exc}")
            return False
        except Exception as exc:  # truncated MIDI / malformed tempo etc.
            self.toast.show_message(
                f"谱面载入失败：无法解析文件（{type(exc).__name__}）"
            )
            return False
        if not from_study:
            if self.drill_page.is_active:
                self.drill_page.leave(notify=False)
                self._set_drill_chrome(False)
            self._clear_study()
        self._score_key = score_key(path, SCORE_DIR)
        # Apply the content mapping before set_score: FollowSession plans
        # phrase windows from the instrument's current preset at set_score.
        if mapping:
            self.instrument.begin_content_mapping(mapping)
        else:
            self.instrument.end_content_mapping()
        # The user's dragged split bar for this score wins over the declared
        # one, but is cleared when a score without a saved bar opens.
        self.instrument.clear_split_override()
        saved_bar = (
            self.score_prefs.split_bar(self._score_key)
            if self._score_key
            else None
        )
        if saved_bar is not None:
            self.instrument.set_split_override(saved_bar, notify=False)
        practice, backing = split_accompaniment(score, accompaniment)
        self.follow.set_score(practice, backing)
        if announce:
            self.toast.show_message(f"已载入 · {score.title}")
        return True

    def _open_library_score(self, path: str) -> None:
        path_obj = Path(path)
        if not path_obj.is_file():
            self.toast.show_message("谱面已不在 · 已刷新曲库")
            self.library_page.refresh()
            return
        try:
            loaded = self._load_score_file(
                path,
                announce=True,
                mapping=mapping_for_library_path(path_obj),
            )
        except Exception as exc:  # card went stale between scan and click
            self.toast.show_message(f"谱面载入失败：{exc}")
            self.library_page.refresh()
            return
        if loaded:
            self.library_page.record_recent_path(path)
            self._show_page(0)
        else:
            self.library_page.refresh()

    def _open_library_image(self, path: str) -> None:
        path_obj = Path(path)
        if not path_obj.is_file():
            self.toast.show_message("图片已不在 · 已刷新曲库")
            self.library_page.refresh()
            return
        if not self.perform.score.open_image(path_obj):
            self.toast.show_message("无法读取这张图片")

    def _on_display_opened(self, path: str) -> None:
        """A display asset loaded successfully: drop any follow/study state."""
        if self.drill_page.is_active:
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        self._clear_study()
        self.follow.clear_score()
        self.instrument.clear_split_override()
        self._score_key = None
        self.library_page.record_recent_path(path)
        self._show_page(0)
        self.toast.show_message(f"仅显示 · {Path(path).stem}")

    # -- study hand-off ----------------------------------------------------

    def _start_study_practice(self, target: PracticeTarget) -> None:
        self._end_project_session()
        if self.drill_page.is_active:
            self.drill_page.leave(notify=False)
        path = score_path(target.score)
        if path is None:
            self.toast.show_message("这个练习还没有可跟的谱 · 内容制作中")
            return
        if not self._load_score_file(
            str(path),
            announce=False,
            from_study=True,
            accompaniment=target.accompaniment,
            mapping=target.mapping,
        ):
            return
        self._study_active = True
        self._study_target = target
        self.study_return.setToolTip(
            f"阶段 {target.stage_index} · {target.item_name} · 回到学习页"
        )
        self.study_return.show()
        self._show_page(0)
        detail = (
            " · 左手自动伴奏" if self.follow.accompaniment else ""
        )
        self.toast.show_message(
            f"已带入练习谱 · {target.item_name}{detail} · 按 Space 听示范",
            2400,
        )

    def _start_project(self, target: ProjectTarget) -> None:
        path = project_path(target.project)
        if path is None:
            self.toast.show_message("这个项目模板还没做好 · 内容制作中")
            return
        project = Project.load(path)
        if not project.tracks:
            self.toast.show_message("项目模板不可用 · 内容制作中")
            return
        if self.drill_page.is_active:
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        self._clear_study()
        if self.follow.playing:
            self.follow.stop()
        self._project_active = True
        self._project_target = target
        self.compose_page.open_project(
            project,
            target.task,
            save_path=self.projects_root / f"{target.project}.json",
        )
        self.study_return.setToolTip(
            f"阶段 {target.stage_index} · {target.item_name} · 回到学习页"
        )
        self.study_return.show()
        self._show_page(3)
        self.toast.show_message(f"已打开项目 · {target.item_name}", 2400)

    def _check_project_steps(self) -> None:
        target = self._project_target
        if target is None or target.task is None:
            return
        task = target.task
        project = self.compose_page.session.project
        done = task.evaluate(project)
        self.compose_page.set_learning_steps(done)
        if not all(done):
            remaining = [
                label for label, ok in zip(task.labels, done) if not ok
            ]
            self.toast.show_message("还差：" + "；".join(remaining[:2]), 2600)
            return
        self.learning_progress.record_practice(
            target.stage_index,
            target.item_name,
            hits=len(done),
            misses=0,
            total=len(done),
        )
        self.learning_page.refresh_progress()
        message = f"项目完成 · 已记录 {len(done)}/{len(done)} 步"
        message += self._stage_completion_suffix(
            stage_by_index(target.stage_index)
        )
        self.toast.show_message(message, 2800)

    def _end_project_session(self) -> None:
        if not self._project_active:
            return
        self._project_active = False
        self._project_target = None
        if hasattr(self, "compose_page"):
            self.compose_page.finalize()
            self.compose_page.clear_learning_task()
        if hasattr(self, "study_return"):
            self.study_return.hide()

    # -- generated drills --------------------------------------------------

    def _start_drill(self, target: DrillTarget) -> None:
        spec = drill_spec(target.drill)
        if spec is None:
            self.toast.show_message("这个训练还没有生成器 · 内容制作中")
            return
        self._begin_drill(target, spec)

    def _start_exam(self, target: ExamTarget) -> None:
        exam = exam_by_key(target.exam_key)
        if exam is None:
            self.toast.show_message("这个考核还没有生成器 · 内容制作中")
            return
        drill_target = DrillTarget(
            target.stage_index,
            exam.title,
            exam.drill.key,
            target.origin_view,
            target.guide_title,
        )
        self._begin_drill(drill_target, exam.drill)

    def _begin_drill(self, target: DrillTarget, spec) -> None:
        if self.drill_page.is_active:
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        self._clear_study()
        self.instrument.release_all_keyboard()
        self.instrument.hold_sustain(False)
        self.instrument.panic()
        if self.follow.playing:
            self.follow.stop()
        self.drill_page.start(target, spec)
        self._show_subpage(self.drill_page, 1)
        self._set_drill_chrome(True)
        self._on_next_note(self.follow.next_note)

    def _set_drill_chrome(self, active: bool) -> None:
        self.map_chip.setEnabled(not active)
        self.map_chip.setToolTip(
            "训练中锁定音域（C4–G6）"
            if active
            else "切换映射预设（Ctrl+M）"
        )

    def _on_drill_closed(self) -> None:
        self._set_drill_chrome(False)
        self.learning_page.return_from_practice()
        self._show_page(1, keep_learning_view=True)

    def _on_drill_progress(self) -> None:
        self.learning_page.refresh_progress()
        if self.drill_page.run_finished or self.drill_page.showing_summary:
            # The summary card already carries the result; a toast would only
            # duplicate it (and on smaller windows cover the card). run_finished
            # is checked because progressChanged is emitted just before the
            # summary page is switched in.
            return
        message = self.drill_page.result_message()
        target = self.drill_page.target
        if target is not None:
            message += self._stage_completion_suffix(
                stage_by_index(target.stage_index)
            )
        if message:
            self.toast.show_message(message, 2800)

    def _stage_completion_suffix(self, stage) -> str:
        if not self.learning_page.stage_done(stage):
            return ""
        if stage.ready_count < stage.total_count:
            return " · 阶段可练内容已完成"
        return " · 阶段已完成"

    def _return_to_study(self) -> None:
        if self.drill_page.is_active:
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        if self._project_active:
            self._end_project_session()
            if self.follow.playing:
                self.follow.stop()
            self.learning_page.return_from_practice()
            self._show_page(1, keep_learning_view=True)
            return
        if not self._study_active:
            return
        self._clear_study()
        if self.follow.playing:
            self.follow.stop()
        self.learning_page.return_from_practice()
        self._show_page(1, keep_learning_view=True)

    def _record_study_result(self, show_toast: bool = True) -> None:
        """Write the practice run back to the local learning file.

        Only runs when the user actually pressed something; listening to the
        demo and leaving records nothing.
        """
        target = self._study_target
        score = self.follow.score if hasattr(self, "follow") else None
        if target is None or score is None:
            return
        hits, misses = self.follow.hits, self.follow.misses
        if hits + misses == 0:
            return
        total = len(score.notes)
        self.learning_progress.record_practice(
            target.stage_index, target.item_name, hits, misses, total
        )
        self.learning_page.refresh_progress()
        if not show_toast:
            return
        accuracy = round(100 * hits / (hits + misses)) if hits + misses else 0
        message = (
            f"练习记录 · 命中 {hits}/{total} · 未中 {misses} · {accuracy}%"
        )
        if total > 0 and hits >= total:
            message += " · 完成"
        message += self._stage_completion_suffix(
            stage_by_index(target.stage_index)
        )
        self.toast.show_message(message, 2800)

    def _clear_study(self) -> None:
        """Drop the study context without touching the loaded score.

        Called when the user clicks the 返回学习 chip, opens 学习 from the rail,
        or loads another score. A normal session never sets this in the first
        place, so non-learners never see the chip.
        """
        if self._study_active:
            self._record_study_result()
        self._study_active = False
        self._study_target = None
        # Restore the user's mapping on every exit path (return chip, another
        # score, a drill/project, or the rail 学习 entry). Idempotent.
        self.instrument.end_content_mapping()
        self._end_project_session()
        if hasattr(self, "study_return"):
            self.study_return.hide()

    # -- draggable split boundary (H7f) -----------------------------------

    def _on_split_bar_dragged(self, bar: int) -> None:
        self.instrument.set_split_override(bar)

    def _on_split_bar_committed(self, bar: int) -> None:
        if not self.instrument.set_split_override(bar):
            return
        if self._score_key:
            self.score_prefs.set_split_bar(self._score_key, bar)
        self.toast.show_message(
            f"分区点 · 键 {bar} / {bar + 1} 之间 · 已按曲目保存", 1800
        )

    def _reset_split_bar(self) -> None:
        restored = self.instrument.clear_split_override()
        if self._score_key:
            self.score_prefs.clear_split_bar(self._score_key)
        if restored:
            self.toast.show_message("已恢复内容默认分区", 1600)

    def _on_score_changed(self, score) -> None:
        self.perform.set_score(score)
        self._apply_auto_windows()
        self._on_next_note(self.follow.next_note)
        self._on_follow_state()

    def _apply_auto_windows(self) -> None:
        """Keep 自动跟随 on the phrase window planned for the next note.

        The plan is rebuilt only when the mapping or transpose changes, so a
        manual octave change inside a phrase is left alone. Loading a new score
        rebuilds it in FollowSession.set_score().
        """
        if not hasattr(self, "follow"):
            return
        if not self.instrument.auto_follow:
            if self._window_config is not None:
                self._window_config = None
                self.follow.clear_window()
                self.perform.set_window_info(None)
            return
        preset = self.instrument.current_preset
        config = (
            preset.key,
            self.instrument.transpose,
            preset.split.bar if preset.split is not None else None,
        )
        if config != self._window_config:
            self._window_config = config
            self.follow.rebuild_windows()
        self.follow.sync_window()

    def _map_chip_text(self) -> str:
        inst = self.instrument
        if inst.drums_enabled:
            return f"{tr('映射')} · {tr('鼓垫')} · 32 键"
        preset = inst.current_preset
        map_name = (
            f"{tr('自动跟随')} · {tr(preset.label_cn)}"
            if inst.auto_follow
            else tr(preset.label_cn)
        )
        window = self.follow.window_label() if hasattr(self, "follow") else None
        detail = (
            window
            if inst.auto_follow and window
            else preset.range_label(inst.offset)
        )
        return f"{tr('映射')} · {map_name} · {detail}"

    def _on_window_changed(self, segment) -> None:
        value = self.follow.window_label()
        self.perform.set_window_info(value)
        if hasattr(self, "map_chip"):
            self.map_chip.setText(self._map_chip_text())
        if segment is not None and segment.index > 0 and not self.follow.playing:
            total = len(self.follow.window_plan.segments)
            self.toast.show_message(
                f"换窗口 · {segment.range_label} · 第 {segment.index + 1}/{total} 段",
                1600,
            )
        self.perform.refresh()

    def _on_next_note(self, note) -> None:
        if self.instrument.drums_enabled:
            self.perform.set_next_key(None, None)
            self.next_status_value.setText(tr("鼓垫模式 · 不参与判定"))
            return
        if self.drill_page.is_active:
            # A generated drill is not the loaded score; do not show its next
            # key in the status/guide while the drill page owns the input.
            self.perform.set_next_key(None, None)
            if self.drill_page.is_rhythm:
                text = tr("节奏 · 按任意键踩拍")
            elif self.drill_page.is_onboarding:
                text = tr("训练 · 按步骤操作")
            else:
                text = tr("训练 · 看谱找音")
            self.next_status_value.setText(text)
            return
        bar = self.instrument.bar_for_midi(note.midi) if note is not None else None
        self.perform.set_next_key(bar, note)
        if note is None:
            text = "—"
        elif bar is None:
            text = f"{note.name} · {tr('超出音域')}"
        else:
            text = f"{note.name} · {tr('光条')} {bar}"
        self.next_status_value.setText(text)

    def _on_follow_state(self) -> None:
        f = self.follow
        index = f.next_note_index
        drums = self.instrument.drums_enabled
        self.perform.set_follow_state(
            f.position,
            f.index if index is None else index,
            f.hits,
            f.misses,
            f.playing,
            None if drums else f.next_note,
            drums,
        )

    def _on_judged(self, hit: bool, expected) -> None:
        stamp = time.strftime("%H:%M:%S")
        bar = self.instrument.bar_for_midi(expected.midi)
        if hit:
            self.last_label.setText(f"{stamp} · 命中 {expected.name}")
            if bar is not None:
                self.perform.band.flash_hit(bar)
        else:
            self.last_label.setText(f"{stamp} · 未中 · 应按 {expected.name}")
            if bar is not None:
                self.perform.band.flash_wrong(bar)

    def _on_score_finished(self) -> None:
        f = self.follow
        message = f"完成 · 命中 {f.hits} · 未中 {f.misses}"
        if self._study_active and self._study_target is not None:
            # Save immediately: closing the app before returning should not
            # throw away a finished study run.
            self._record_study_result(show_toast=False)
            message += self._stage_completion_suffix(
                stage_by_index(self._study_target.stage_index)
            )
        self.toast.show_message(message, 2800)

    def _restart_score(self) -> None:
        if self.follow.score is None:
            return
        self.follow.restart()
        self.toast.show_message("回到开头 · 重新练习")

    def _on_active(self, keys: set) -> None:
        self.perform.set_active(keys)
        self.drill_page.set_active(keys)
        self.compose_page.set_active(keys)
        self._refresh_notes()

    def _refresh_notes(self) -> None:
        notes = self.instrument.active_notes()
        self.now_label.setText(" · ".join(notes) if notes else "—")
        sources = self.instrument.input_sources()
        if {"instrument", "keyboard"} <= sources:
            source = "琴 + 电脑键盘"
        elif "instrument" in sources:
            source = "琴"
        elif "keyboard" in sources:
            source = "电脑键盘"
        elif "sim" in sources:
            source = "模拟"
        else:
            source = "无"
        self.source_label.setText(f"输入 · {source}")

    def _refresh_state(self) -> None:
        inst = self.instrument
        if hasattr(self, "follow"):
            self._apply_auto_windows()
        preset = inst.current_preset
        self.map_chip.setText(self._map_chip_text())
        with QSignalBlocker(self.volume_btn):
            self.volume_btn.setChecked(inst.muted)
        self.perform.refresh()
        if hasattr(self, "follow"):
            self._on_next_note(self.follow.next_note)
            self._on_follow_state()
        self.device_page.refresh()
        self.sound_page.refresh()
        self.keybindings_page.refresh()
        self.drill_page.refresh()
        self.calibration_page.refresh()
        self.help_page.refresh()
        self._refresh_devices()
        self._refresh_notes()

        auto = inst.auto_follow
        drill_visible = (
            self.drill_page.is_active
            or self.stack.currentWidget() is self.drill_page
        )
        if not self._first_refresh and not drill_visible:
            if preset.key != self._last_preset_key or auto != self._last_auto:
                if auto:
                    count = (
                        len(self.follow.window_plan.segments)
                        if self.follow.window_plan
                        else 0
                    )
                    if count > 1:
                        message = f"自动跟随已开 · {count} 个窗口 · 按乐句切换"
                    elif count == 1:
                        message = "自动跟随已开 · 整曲一个窗口"
                    else:
                        message = "自动跟随已开 · 等待可解析曲谱"
                    self.toast.show_message(message)
                else:
                    self.toast.show_message(
                        f"映射 · {preset.label_cn} · {preset.range_label(inst.offset)}"
                    )
        self._last_preset_key = preset.key
        self._last_auto = auto
        self._first_refresh = False

    def _refresh_devices(self) -> None:
        inst = self.instrument
        states = [bool(inst.modules.get(addr)) for addr, _name in MODULES]
        stale = inst.hardware_stale()
        self.dots.set_state(states, inst.connected, stale)
        if not self.serial_enabled:
            text = "电脑键盘 · 未连接设备"
        elif inst.connected and stale:
            text = "设备无心跳"
        elif inst.connected and inst.modules:
            online = sum(states)
            text = "3 模块在线" if online == 3 else f"{online}/3 模块在线"
        elif inst.connected:
            text = "设备在线 · 等待模块"
        else:
            text = "等待设备 · 可电脑键盘弹"
        self.device_label.setText(tr(text))
        if not self.serial_enabled:
            self.status_modules.setText(tr("电脑键盘"))
        else:
            self.status_modules.setText(f"{sum(states)} 模块" if inst.connected else "0 模块")

    def _show_page(self, index: int, keep_learning_view: bool = False) -> None:
        current = self.stack.currentWidget()
        if current is getattr(self, "calibration_page", None):
            self.calibration_page.leave()
        if current is getattr(self, "compose_page", None) and index != 3:
            # Merge the take before keys are released / the page is hidden.
            self.compose_page.finalize()
        left_drill = current is self.drill_page
        if left_drill:
            # Any rail/shortcut page change ends the drill; the drill's own
            # back button emits closed and then lands here too (idempotent).
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        if index == 1:
            # Clicking 学习 is itself a return; drop the study hand-off chip.
            # The rail entry always opens the full 9-stage overview. The
            # study return chip is the only path that restores the exact
            # stage/course the user came from.
            self._clear_study()
            if not keep_learning_view:
                self.learning_page.show_overview()
        if index != 0:
            self.perform.score.exit_focus()
            self.instrument.release_all_keyboard()
            self.instrument.hold_sustain(False)
            if hasattr(self, "follow") and self.follow.playing:
                self.follow.stop()
        if self.stack.currentWidget() is self.keybindings_page:
            self.keybindings_page.cancel_capture("已离开键位页；未保存这次改绑。")
        self.stack.setCurrentWidget(self.pages[index])
        apply_language(self.pages[index])
        btn = self.nav_buttons[index]
        if not btn.isChecked():
            btn.setChecked(True)
        if index == 2:
            self.library_page.refresh()
        if index == 3:
            self.compose_page.refresh()
        if index == 4:
            self.device_page.refresh()
        if index == 6:
            self.help_page.refresh()
        if left_drill:
            self._restore_follow_status()

    def _restore_follow_status(self) -> None:
        if not hasattr(self, "follow"):
            return
        self._on_next_note(self.follow.next_note)
        self._on_follow_state()

    def _show_subpage(self, widget, nav_index: int) -> None:
        current = self.stack.currentWidget()
        if current is getattr(self, "calibration_page", None) and widget is not self.calibration_page:
            self.calibration_page.leave()
        if self.stack.currentWidget() is getattr(self, "compose_page", None):
            self.compose_page.finalize()
        left_drill = (
            self.stack.currentWidget() is self.drill_page
            and widget is not self.drill_page
        )
        if left_drill:
            self.drill_page.leave(notify=False)
            self._set_drill_chrome(False)
        self.instrument.release_all_keyboard()
        self.instrument.hold_sustain(False)
        if hasattr(self, "follow") and self.follow.playing:
            self.follow.stop()
        if self.stack.currentWidget() is self.keybindings_page and widget is not self.keybindings_page:
            self.keybindings_page.cancel_capture("已离开键位页；未保存这次改绑。")
        self.stack.setCurrentWidget(widget)
        btn = self.nav_buttons[nav_index]
        if not btn.isChecked():
            btn.setChecked(True)
        if widget is self.calibration_page:
            self.calibration_page.enter()
        elif widget is self.sound_page:
            self.sound_page.refresh()
        elif widget is self.keybindings_page:
            self.keybindings_page.refresh()
        if left_drill:
            self._restore_follow_status()

    def _on_bindings_changed(self) -> None:
        self.perform.band.update()
        self.perform.refresh()
        self.compose_page.band.update()
        self.keybindings_page.refresh()
        self.drill_page.refresh()

    def _show_help_page(self) -> None:
        self._show_page(6)

    def _maybe_show_onboarding(self) -> None:
        if self._closed or self._onboarding_shown:
            return
        state = OnboardingState.load(self.onboarding_path)
        if state.done:
            return
        self._show_onboarding()

    def _show_onboarding(self, force: bool = False) -> None:
        """Open the wizard; the caller may force it from the Help page."""
        state = OnboardingState.load(self.onboarding_path)
        if not force and state.done:
            return
        self._onboarding_shown = True
        dialog = OnboardingDialog(
            self.theme,
            self.instrument,
            self.calibration_path,
            self,
        )
        dialog.exec()
        outcome = dialog.outcome
        if outcome in ("completed", "calibration", "lesson"):
            state.mark_completed()
            state.save()
        elif outcome == "skipped":
            state.mark_skipped()
            state.save()
        if outcome == "calibration":
            self._show_subpage(self.calibration_page, 4)
        elif outcome == "lesson":
            self._show_page(1, keep_learning_view=True)
            self.learning_page.open_stage(0)

    def _on_focus_mode(self, on: bool) -> None:
        self.rail.setVisible(not on)
        self.perform.set_right_panel_visible(not on)

    # -- theme / accessibility / shortcuts --------------------------------

    def _build_theme(self, name: str) -> Theme:
        base = THEMES[name if name in THEMES else "studio"]
        return replace(base, font_scale=self.accessibility.font_scale)

    def _set_reduce_motion(self, on: bool) -> None:
        reduce_motion = bool(on)
        if self.accessibility.reduce_motion == reduce_motion:
            return
        self.accessibility.reduce_motion = reduce_motion
        self.accessibility.save()
        self.perform.set_accessibility(reduce_motion)

    def _set_font_scale(self, scale: float) -> None:
        normalized = normalize_font_scale(scale)
        if self.accessibility.font_scale == normalized:
            return
        self.accessibility.font_scale = normalized
        self.accessibility.save()
        self.apply_theme(self.theme_name)
        self.settings_page.set_font_scale(normalized)

    def _set_language(self, code: str) -> None:
        normalized = normalize_language(code)
        self.accessibility.language = normalized
        self.accessibility.save()
        self.settings_page.set_language(normalized)
        self.toast.show_message(
            "语言将在下次启动生效 · Language changes on next start",
            2600,
        )

    def apply_theme(self, name: str, first: bool = False) -> None:
        self.theme_name = name if name in THEMES else "studio"
        self.theme = self._build_theme(self.theme_name)
        self.setStyleSheet(self.theme.qss())
        self.root.set_theme(self.theme)
        # Base size for widgets that never call setFont(); children with an
        # explicit Theme.font() still get their own scaled size. The global QSS
        # rule deliberately does not set font-size, because a stylesheet size
        # would override every setFont() and flatten the title/score hierarchy.
        set_scaled_font(self.root, self.theme, 12)
        self.dots.set_theme(self.theme)
        self.volume_btn.set_theme(self.theme)
        self.perform.set_theme(self.theme)
        for page in (
            self.learning_page,
            self.drill_page,
            self.library_page,
            self.compose_page,
            self.calibration_page,
            self.device_page,
            self.sound_page,
            self.settings_page,
            self.keybindings_page,
            self.help_page,
        ):
            page.set_theme(self.theme)
        self.settings_page.set_current_theme(self.theme_name)
        self.settings_page.set_font_scale(self.accessibility.font_scale)
        refresh_scaled_fonts(self, self.theme)
        if not first:
            self._refresh_state()

    # -- computer keyboard input (§7.2 / §7.3) ----------------------------

    def _move_nav_focus(self, key: int) -> None:
        if not self.nav_buttons:
            return
        current = QApplication.focusWidget()
        try:
            index = self.nav_buttons.index(current)
        except ValueError:
            index = 0
        if key == int(Qt.Key.Key_Home):
            target = 0
        elif key == int(Qt.Key.Key_End):
            target = len(self.nav_buttons) - 1
        elif key == int(Qt.Key.Key_Up):
            target = (index - 1) % len(self.nav_buttons)
        else:
            target = (index + 1) % len(self.nav_buttons)
        self.nav_buttons[target].setFocus()

    def eventFilter(self, watched, event) -> bool:
        etype = event.type()
        if etype not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return super().eventFilter(watched, event)
        if QApplication.activeModalWidget() is not None:
            return super().eventFilter(watched, event)
        focus = QApplication.focusWidget()
        if isinstance(
            focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)
        ):
            return super().eventFilter(watched, event)

        if (
            self.stack.currentWidget() is self.keybindings_page
            and self.keybindings_page.is_capturing()
        ):
            return self.keybindings_page.handle_capture(event)

        key = int(event.key())
        mods = int(event.modifiers().value)
        current = self.stack.currentWidget()
        on_drill = current is self.drill_page
        on_compose = current is getattr(self, "compose_page", None)
        playing = current is self.perform or on_drill or on_compose
        if etype == QEvent.Type.KeyPress:
            if event.isAutoRepeat():
                return super().eventFilter(watched, event)
            if on_drill and self.drill_page.showing_summary:
                if key in (
                    int(Qt.Key.Key_Return),
                    int(Qt.Key.Key_Enter),
                    int(Qt.Key.Key_Space),
                ):
                    self.drill_page.retry()
                    return True
                if key in (int(Qt.Key.Key_Escape), int(Qt.Key.Key_Backspace)):
                    self.drill_page.leave()
                    return True
            if (
                on_drill
                and self.drill_page.is_rhythm
                and not self.drill_page.showing_summary
            ):
                if key in (
                    int(Qt.Key.Key_Return),
                    int(Qt.Key.Key_Enter),
                    int(Qt.Key.Key_Space),
                ):
                    self.drill_page.toggle_rhythm()
                    return True
                if key == int(Qt.Key.Key_Backspace):
                    self.drill_page.leave()
                    return True
                if key == int(Qt.Key.Key_Escape):
                    if self.drill_page.rhythm_running:
                        self.drill_page.stop_rhythm()
                    else:
                        self.drill_page.leave()
                    return True
            if focus is not None and isinstance(focus, QAbstractButton):
                if key in (int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
                    focus.click()
                    return True
                if key == int(Qt.Key.Key_Space):
                    # A focused control owns Space; play/pause must not
                    # swallow it on the performance pages.
                    return super().eventFilter(watched, event)
            if (
                focus in self.nav_buttons
                and mods == 0
                and key
                in (
                    int(Qt.Key.Key_Up),
                    int(Qt.Key.Key_Down),
                    int(Qt.Key.Key_Home),
                    int(Qt.Key.Key_End),
                )
            ):
                self._move_nav_focus(key)
                return True
            if self.settings_page.move_chip_focus(focus, key):
                return True
            if (
                current is self.keybindings_page
                and self.keybindings_page.move_chip_focus(focus, key)
            ):
                return True
            action = self.bindings.action_for_key(key, mods)
            if action is not None:
                if on_drill and action in (
                    "sustain",
                    "labels",
                    "play_pause",
                    "map",
                    "oct_down",
                    "oct_up",
                    "transpose_down",
                    "transpose_up",
                ):
                    # The drill owns the keyboard: no demo, no sustain, no
                    # mapping/octave changes while a question is showing. The
                    # stage-0 sustain lesson is the one exception: it must see
                    # the real sustain key to teach what it does.
                    if not (
                        action == "sustain" and self.drill_page.wants_sustain
                    ):
                        return True
                # Sustain and label toggling belong to the performance band;
                # elsewhere let Tab/Shift do their normal thing.
                if action in ("sustain", "labels", "play_pause") and not playing:
                    return super().eventFilter(watched, event)
                self._dispatch_action(action, True)
                return True
            if playing:
                bar = self.bindings.bar_for_key(key, mods)
                if bar is not None:
                    self.instrument.press_keyboard(bar)
                    return True
        else:
            # Always honour releases, even after leaving the perform page, so
            # a held note cannot get stuck.
            sustain = self.bindings.function_chord("sustain")
            if sustain is not None and sustain.key == key:
                self.instrument.hold_sustain(False)
                return True
            bar = self.bindings.bar_for_key(key, mods)
            if bar is not None:
                self.instrument.release_keyboard(bar)
                return True
        return super().eventFilter(watched, event)

    def _dispatch_action(self, action: str, down: bool) -> None:
        inst = self.instrument
        if action == "sustain":
            inst.hold_sustain(down)
            return
        if not down:
            return
        if action == "play_pause":
            if self.stack.currentWidget() is getattr(self, "compose_page", None):
                self.compose_page.toggle_playback()
                return
            if self.follow.score is not None:
                self.follow.toggle_play()
            else:
                self.perform.score.toggle_play()
        elif action == "panic":
            self._panic()
        elif action == "labels":
            if self.stack.currentWidget() is getattr(self, "compose_page", None):
                band = self.compose_page.band
                band.set_labels(not band.labels_on)
            else:
                self.perform.toggle_labels()
        elif action == "help":
            self._show_help_page()
        elif action == "map":
            inst.cycle_preset()
        elif action == "tone":
            inst.cycle_program()
        elif action == "oct_down":
            inst.set_octave(-1)
        elif action == "oct_up":
            inst.set_octave(+1)
        elif action == "transpose_down":
            inst.set_transpose(-1)
        elif action == "transpose_up":
            inst.set_transpose(+1)
        elif action == "fullscreen":
            self._toggle_fullscreen()
        elif action.startswith("page_"):
            try:
                self._show_page(int(action.split("_")[1]) - 1)
            except (IndexError, ValueError):
                pass

    def changeEvent(self, event) -> None:
        # Alt-Tab or a modal dialog must not leave notes held forever.
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.instrument.release_all_keyboard()
            self.instrument.hold_sustain(False)
        super().changeEvent(event)

    def _on_mute_toggled(self, on: bool) -> None:
        if hasattr(self, "compose_page"):
            self.compose_page.stop_playback()
        if on != self.instrument.muted:
            self.instrument.toggle_mute()
        if hasattr(self, "compose_page"):
            self.compose_page.sync_audio_outputs()

    def _panic(self) -> None:
        if hasattr(self, "follow") and self.follow.playing:
            self.follow.stop()
        if hasattr(self, "compose_page"):
            self.compose_page.stop_playback()
        self.instrument.panic()
        if self.drill_page.is_active:
            # The stage-0 sustain lesson checks that Esc actually silenced
            # everything; other drills simply ignore the event.
            self.drill_page.panicked()
        self.toast.show_message("全部静音 · 所有正在响的音已停止")

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.toast.show_message("退出全屏")
        else:
            self.showFullScreen()
            self.toast.show_message("全屏 · 按 F11 退出")

    # -- lifecycle --------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._closed:
            super().closeEvent(event)
            return
        self._closed = True
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if hasattr(self, "compose_page"):
            self.compose_page.finalize()
        self.instrument.release_all_keyboard()
        if hasattr(self, "drill_page"):
            self.drill_page.leave(notify=False)
        if hasattr(self, "follow"):
            self.follow.stop()
        if hasattr(self, "calibration_page"):
            # Sends 'c' off and restores performance before the port closes.
            self.calibration_page.leave()
        if self._serial is not None:
            self._serial.stop()
        self.instrument.shutdown()
        super().closeEvent(event)
