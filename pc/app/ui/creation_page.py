"""创作页: record takes, overdub, loop, tracks, save/load (P5 / H2).

The page is a thin view over ComposeSession. It records note events (never
audio), reuses the 32-key LightBarBand for input feedback, and keeps only the
selected track's GM program on the single live synth voice. Mixing, playback,
and MIDI export remain later slices.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.compose import ComposeSession
from ..core.curriculum import CREATION_TEMPLATES, project_path
from ..core.editor import NoteEditor
from ..core.metronome import Metronome
from ..core.midi_export import export_midi
from ..core.project import (
    MAX_TRACKS,
    Layer,
    Project,
    SplitSpec,
    Track,
    default_project_dir,
)
from ..core.programs import fallback_notice, index_for_gm, label_for_gm
from ..core.project_task import ProjectTask
from ..core.synth_service import (
    CLICK_ACCENT_MIDI,
    CLICK_CHANNEL,
    CLICK_MIDI,
    LAYER_CHANNEL,
    PROGRAMS,
    SPLIT_LEFT_CHANNEL,
    SPLIT_RIGHT_CHANNEL,
)
from .learning_page import clear_layout, scroll_area
from .light_bar import LightBarBand
from .piano_roll import HEIGHT as ROLL_HEIGHT, PianoRollCanvas
from .project_player import ProjectPlayer
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame

VOLUME_STEP = 0.1


def _fallback_notices(project: Project) -> list[str]:
    """One notice per substituted sound, in track order, without duplicates."""
    notices: list[str] = []
    for track in project.tracks:
        programs = [track.program]
        if track.layer is not None:
            programs.append(track.layer.program)
        if track.split is not None:
            programs.extend([track.split.left_program, track.split.right_program])
        for program in programs:
            notice = fallback_notice(program)
            if notice and notice not in notices:
                notices.append(notice)
    return notices


def _program_index(program: int) -> int:
    index = index_for_gm(program)
    return 0 if index is None else index


def _pan_text(pan: float) -> str:
    value = round(max(-1.0, min(1.0, pan)) * 100)
    if value == 0:
        return "C"
    return f"{'L' if value < 0 else 'R'}{abs(value)}"


class TrackRow(CardFrame):
    selectRequested = Signal(int)
    programRequested = Signal(int)
    volumeRequested = Signal(int, float)
    muteToggled = Signal(int, bool)
    soloToggled = Signal(int, bool)
    panChanged = Signal(int, float)
    layerToggled = Signal(int, bool)
    splitToggled = Signal(int, bool)

    def __init__(self, theme: Theme, index: int, track: Track, current: bool):
        super().__init__()
        self._theme = theme
        self.index = index
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(8)

        self.select_button = QPushButton()
        self.select_button.setProperty("role", "chip")
        self.select_button.setCheckable(True)
        self.select_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.select_button.clicked.connect(
            lambda checked=False: self.selectRequested.emit(self.index)
        )
        row.addWidget(self.select_button, 1)

        self.program_button = QPushButton()
        self.program_button.setProperty("role", "chip")
        self.program_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.program_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.program_button.setToolTip("切换 GM 音色")
        self.program_button.clicked.connect(
            lambda checked=False: self.programRequested.emit(self.index)
        )
        row.addWidget(self.program_button)

        self.volume_down = QPushButton("−")
        self.volume_down.setProperty("role", "icon")
        self.volume_down.setFixedSize(26, 26)
        self.volume_down.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.volume_down.setToolTip("音量 −10%")
        self.volume_down.clicked.connect(
            lambda checked=False: self.volumeRequested.emit(self.index, -VOLUME_STEP)
        )
        row.addWidget(self.volume_down)

        self.volume_label = QLabel()
        self.volume_label.setProperty("role", "mono")
        set_scaled_font(self.volume_label, self._theme, 10, mono=True)
        self.volume_label.setMinimumWidth(38)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.volume_label)

        self.volume_up = QPushButton("＋")
        self.volume_up.setProperty("role", "icon")
        self.volume_up.setFixedSize(26, 26)
        self.volume_up.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.volume_up.setToolTip("音量 +10%")
        self.volume_up.clicked.connect(
            lambda checked=False: self.volumeRequested.emit(self.index, VOLUME_STEP)
        )
        row.addWidget(self.volume_up)

        self.pan_slider = QSlider(Qt.Orientation.Horizontal)
        self.pan_slider.setRange(-100, 100)
        self.pan_slider.setFixedWidth(58)
        self.pan_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pan_slider.setToolTip("声像：左 ← C → 右")
        self.pan_slider.valueChanged.connect(
            lambda value: self.panChanged.emit(self.index, value / 100.0)
        )
        row.addWidget(self.pan_slider)

        self.pan_label = QLabel()
        self.pan_label.setProperty("role", "faint")
        self.pan_label.setFixedWidth(30)
        self.pan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.pan_label)

        self.layer_button = QPushButton("叠")
        self.layer_button.setProperty("role", "icon")
        set_scaled_font(self.layer_button, self._theme, 9, QFont.Weight.Bold)
        self.layer_button.setCheckable(True)
        self.layer_button.setFixedSize(28, 26)
        self.layer_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.layer_button.setToolTip("一键双音色 · 叠加第二音色")
        self.layer_button.toggled.connect(
            lambda on: self.layerToggled.emit(self.index, on)
        )
        row.addWidget(self.layer_button)

        self.split_button = QPushButton("分")
        self.split_button.setProperty("role", "icon")
        set_scaled_font(self.split_button, self._theme, 9, QFont.Weight.Bold)
        self.split_button.setCheckable(True)
        self.split_button.setFixedSize(28, 26)
        self.split_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.split_button.setToolTip("键盘分区 · C4 以下/以上不同音色")
        self.split_button.toggled.connect(
            lambda on: self.splitToggled.emit(self.index, on)
        )
        row.addWidget(self.split_button)

        self.mute_button = QPushButton("M")
        self.mute_button.setProperty("role", "icon")
        set_scaled_font(self.mute_button, self._theme, 9, QFont.Weight.Bold)
        self.mute_button.setCheckable(True)
        self.mute_button.setFixedSize(28, 26)
        self.mute_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mute_button.setToolTip("静音这条音轨（导出时剔除）")
        self.mute_button.toggled.connect(
            lambda on: self.muteToggled.emit(self.index, on)
        )
        row.addWidget(self.mute_button)

        self.solo_button = QPushButton("S")
        self.solo_button.setProperty("role", "icon")
        set_scaled_font(self.solo_button, self._theme, 9, QFont.Weight.Bold)
        self.solo_button.setCheckable(True)
        self.solo_button.setFixedSize(28, 26)
        self.solo_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.solo_button.setToolTip("独奏这条音轨（导出时只留独奏轨）")
        self.solo_button.toggled.connect(
            lambda on: self.soloToggled.emit(self.index, on)
        )
        row.addWidget(self.solo_button)

        self.notes_label = QLabel()
        self.notes_label.setProperty("role", "faint")
        self.notes_label.setMinimumWidth(46)
        self.notes_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self.notes_label)

        # One explicit, wrapping focus order for the whole row. Qt's built-in
        # QAbstractButton arrow navigation stops at the edges and knows
        # nothing about the pan slider, so it is not enough on its own.
        self._focus_controls = (
            self.select_button,
            self.program_button,
            self.volume_down,
            self.volume_up,
            self.pan_slider,
            self.layer_button,
            self.split_button,
            self.mute_button,
            self.solo_button,
        )
        for control in self._focus_controls:
            control.installEventFilter(self)

        self.refresh(track, current)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and watched in self._focus_controls:
            key = int(event.key())
            # The pan slider owns Left/Right (it is the only keyboard way to
            # set pan), so Up/Down step focus off it instead.
            if watched is self.pan_slider:
                if key in (int(Qt.Key.Key_Up), int(Qt.Key.Key_Down)):
                    delta = -1 if key == int(Qt.Key.Key_Up) else 1
                    self._move_control_focus(watched, delta)
                    return True
                return super().eventFilter(watched, event)
            if key in (int(Qt.Key.Key_Left), int(Qt.Key.Key_Right)):
                delta = -1 if key == int(Qt.Key.Key_Left) else 1
                self._move_control_focus(watched, delta)
                return True
        return super().eventFilter(watched, event)

    def _move_control_focus(self, watched, delta: int) -> None:
        index = self._focus_controls.index(watched)
        self._focus_controls[
            (index + delta) % len(self._focus_controls)
        ].setFocus()

    def refresh(self, track: Track, current: bool) -> None:
        self.select_button.setText(f"音轨 {self.index + 1} · {track.name}")
        self.select_button.setChecked(current)
        self.program_button.setText(label_for_gm(track.program))
        self.program_button.setToolTip(f"GM {track.program} · 点击切换")
        self.volume_label.setText(f"{round(track.volume * 100)}%")
        self.notes_label.setText(f"{len(track.notes)} 音")
        with QSignalBlocker(self.pan_slider):
            self.pan_slider.setValue(round(track.pan * 100))
        self.pan_label.setText(_pan_text(track.pan))
        with QSignalBlocker(self.layer_button):
            self.layer_button.setChecked(track.layer is not None)
        if track.layer is not None:
            self.layer_button.setToolTip(
                f"叠加中 · {label_for_gm(track.layer.program)}（点击关闭）"
            )
        else:
            self.layer_button.setToolTip("一键双音色 · 叠加第二音色")
        with QSignalBlocker(self.split_button):
            self.split_button.setChecked(track.split is not None)
        if track.split is not None:
            self.split_button.setToolTip(
                "分区中 · 低音 "
                f"{label_for_gm(track.split.left_program)} / 高音 "
                f"{label_for_gm(track.split.right_program)}"
            )
        else:
            self.split_button.setToolTip("键盘分区 · 低音区/高音区不同音色")
        with QSignalBlocker(self.mute_button):
            self.mute_button.setChecked(track.mute)
        with QSignalBlocker(self.solo_button):
            self.solo_button.setChecked(track.solo)


class CreationPage(GlassFrame):
    message = Signal(str)
    recordingChanged = Signal(bool)
    durationChanged = Signal(str)
    learningCheckRequested = Signal()

    def __init__(
        self,
        theme: Theme,
        instrument,
        bindings,
        projects_dir: str | Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self.projects_dir = (
            Path(projects_dir) if projects_dir is not None else default_project_dir()
        )
        self.session = ComposeSession()
        self.editor = NoteEditor(self.session.project, 0)
        self.track_rows: list[TrackRow] = []
        self._loaded = False
        self._loop_bars = 4
        self._session_path: Path | None = None
        self._task: ProjectTask | None = None
        self._step_labels: list[QLabel] = []
        self._step_texts: list[str] = []
        self._record_from = 0.0
        self._layer_held: set[int] = set()
        self._split_held: set[tuple[int, int]] = set()
        self.metronome = Metronome(
            bpm=self.session.project.tempo,
            beats_per_bar=self.session.project.time_signature[0],
        )
        self._click_midi: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 12)
        outer.setSpacing(10)

        scroll, content = scroll_area()
        self.scroll = scroll
        content.addWidget(self._build_header())
        content.addWidget(self._build_learning())
        content.addWidget(self._build_transport())
        content.addWidget(self._build_tracks())
        content.addWidget(self._build_roll())
        content.addStretch(1)
        outer.addWidget(scroll, 1)

        self.band = LightBarBand(theme, instrument, bindings)
        self.band.function.connect(self._on_function)
        outer.addWidget(self.band)

        self.player = ProjectPlayer(self.instrument.synth, parent=self)
        self.player.positionChanged.connect(self.roll.set_position)
        self.player.stateChanged.connect(self._sync_play_button)
        self.player.message.connect(self.message)

        self._clock = QTimer(self)
        self._clock.setInterval(100)
        self._clock.timeout.connect(self._tick_clock)

        self._metronome_timer = QTimer(self)
        self._metronome_timer.setInterval(20)
        self._metronome_timer.timeout.connect(self._tick_metronome)
        self._click_off_timer = QTimer(self)
        self._click_off_timer.setSingleShot(True)
        self._click_off_timer.setInterval(60)
        self._click_off_timer.timeout.connect(self._stop_click_notes)
        self._render()

    # -- construction -----------------------------------------------------

    def _build_header(self) -> QWidget:
        card = CardFrame()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)
        title = QLabel("创作")
        set_scaled_font(title, self._theme, 20, QFont.Weight.DemiBold)
        top.addWidget(title)
        badge = QLabel("录音 · 编曲")
        badge.setProperty("role", "faint")
        top.addWidget(badge)
        top.addStretch(1)
        self.project_title = QLabel()
        self.project_title.setProperty("role", "value")
        top.addWidget(self.project_title)
        box.addLayout(top)

        hint = QLabel("只录音符事件 · 最多 8 轨 · 不录音频 · 鼠标点光条不发声")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        box.addWidget(hint)
        return card

    def _build_learning(self) -> QWidget:
        card = CardFrame()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 10, 16, 10)
        box.setSpacing(5)

        self.learning_title = QLabel()
        self.learning_title.setProperty("role", "title")
        box.addWidget(self.learning_title)

        self.learning_steps_box = QVBoxLayout()
        self.learning_steps_box.setSpacing(2)
        box.addLayout(self.learning_steps_box)

        row = QHBoxLayout()
        row.addStretch(1)
        self.check_button = self._button("检查完成", "action")
        self.check_button.setToolTip("按阶段 7 的验收规则检查当前项目")
        self.check_button.clicked.connect(
            lambda: self.learningCheckRequested.emit()
        )
        row.addWidget(self.check_button)
        box.addLayout(row)

        self.learning_card = card
        card.hide()
        return card

    # -- learning task ----------------------------------------------------

    def set_learning_task(self, task: ProjectTask) -> None:
        self._task = task
        self.learning_title.setText(f"学习项目 · {task.name}")
        clear_layout(self.learning_steps_box)
        self._step_labels = []
        self._step_texts = list(task.labels)
        for text in self._step_texts:
            label = QLabel()
            label.setProperty("role", "muted")
            label.setWordWrap(True)
            self.learning_steps_box.addWidget(label)
            self._step_labels.append(label)
        self.learning_card.show()
        self.templates_row.setEnabled(False)
        self.set_learning_steps([False] * len(self._step_texts))

    def set_learning_steps(self, done: list[bool]) -> None:
        for index, label in enumerate(self._step_labels):
            ok = index < len(done) and done[index]
            label.setText(("● " if ok else "○ ") + self._step_texts[index])
            label.setProperty("role", "amber" if ok else "muted")
            label.style().unpolish(label)
            label.style().polish(label)

    def clear_learning_task(self) -> None:
        self._task = None
        self.learning_card.hide()
        self.templates_row.setEnabled(True)
        clear_layout(self.learning_steps_box)
        self._step_labels = []
        self._step_texts = []

    def load_template(self, project_id: str) -> bool:
        if self._task is not None:
            self.message.emit("学习项目中不能换模板 · 先返回学习页")
            return False
        path = project_path(project_id)
        if path is None:
            self.message.emit("这个模板还没做好 · 内容制作中")
            return False
        project = Project.load(path)
        if not project.tracks:
            self.message.emit("模板不可用 · 内容制作中")
            return False
        self.open_project(project)
        self.message.emit(f"已载入模板 · {project.title}")
        return True

    def open_project(
        self,
        project: Project,
        task: ProjectTask | None = None,
        save_path: str | Path | None = None,
    ) -> None:
        """Load a learning template without touching the user's saved project.

        ``save_path`` is the user-side copy for this lesson (never the shared
        default project.json), so saving a stage-7 take cannot overwrite the
        user's own work.
        """
        self.finalize()
        self.session.set_project(project)
        self.editor.set_project(project, 0)
        self._session_path = Path(save_path) if save_path is not None else None
        self._loaded = True
        self._render()
        for notice in _fallback_notices(project):
            self.message.emit(notice)
        if task is not None:
            self.set_learning_task(task)
        else:
            self.clear_learning_task()

    def _build_transport(self) -> QWidget:
        card = CardFrame()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 10, 16, 10)
        box.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.record_button = self._button("● 录音", "action")
        self.record_button.setToolTip("从当前音轨开始录音（Ctrl+4 到达本页）")
        self.record_button.clicked.connect(lambda: self.start_recording(False))
        row.addWidget(self.record_button)

        self.overdub_button = self._button("✚ 叠录", "chip")
        self.overdub_button.setToolTip("把本次演奏并入当前音轨")
        self.overdub_button.clicked.connect(lambda: self.start_recording(True))
        row.addWidget(self.overdub_button)

        self.stop_button = self._button("■ 停止", "chip")
        self.stop_button.clicked.connect(lambda: self.stop_recording())
        row.addWidget(self.stop_button)

        self.play_button = self._button("▶ 播放", "chip")
        self.play_button.setToolTip("试听项目（Space）；播放时卷帘显示播放头")
        self.play_button.clicked.connect(lambda: self.toggle_playback())
        row.addWidget(self.play_button)

        self.loop_button = self._button("↻ 循环", "chip")
        self.loop_button.setCheckable(True)
        self.loop_button.setToolTip("循环 1–4 小节；录音中不可改")
        self.loop_button.toggled.connect(self._on_loop_toggled)
        row.addWidget(self.loop_button)

        self.metronome_button = self._button("♩ 节拍器", "chip")
        self.metronome_button.setCheckable(True)
        self.metronome_button.setToolTip("按项目速度开/关节拍器")
        self.metronome_button.toggled.connect(self._on_metronome_toggled)
        row.addWidget(self.metronome_button)

        self.count_in_button = self._button("预备拍", "chip")
        self.count_in_button.setCheckable(True)
        self.count_in_button.setToolTip("录音前先空一小节，只响节拍不记录")
        row.addWidget(self.count_in_button)

        row.addSpacing(10)
        self.duration_label = QLabel("00:00")
        self.duration_label.setProperty("role", "mono")
        set_scaled_font(self.duration_label, self._theme, 11, QFont.Weight.DemiBold, mono=True)
        row.addWidget(self.duration_label)
        row.addStretch(1)

        self.save_button = self._button("保存", "chip")
        self.save_button.clicked.connect(lambda: self.save_project())
        row.addWidget(self.save_button)

        self.load_button = self._button("载入", "chip")
        self.load_button.clicked.connect(lambda: self.load_project())
        row.addWidget(self.load_button)

        self.export_button = self._button("导出 MIDI", "chip")
        self.export_button.clicked.connect(lambda: self.export_project())
        row.addWidget(self.export_button)
        box.addLayout(row)

        self.status_label = QLabel("按 ● 录音开始 · 第一轨会自动建立")
        self.status_label.setProperty("role", "faint")
        self.status_label.setWordWrap(True)
        box.addWidget(self.status_label)

        self.templates_row = QWidget()
        templates = QHBoxLayout(self.templates_row)
        templates.setContentsMargins(0, 0, 0, 0)
        templates.setSpacing(6)
        caption = QLabel("模板")
        caption.setProperty("role", "faint")
        templates.addWidget(caption)
        self.template_buttons: list[QPushButton] = []
        for template in CREATION_TEMPLATES:
            button = self._button(template.name, "chip")
            button.setToolTip(f"从模板新建 · {template.name}")
            button.clicked.connect(
                lambda checked=False, pid=template.project: self.load_template(pid)
            )
            templates.addWidget(button)
            self.template_buttons.append(button)
        templates.addStretch(1)
        box.addWidget(self.templates_row)
        return card

    def _build_tracks(self) -> QWidget:
        card = CardFrame()
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 10, 16, 10)
        box.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("音轨")
        set_scaled_font(title, self._theme, 14, QFont.Weight.DemiBold)
        head.addWidget(title)
        self.track_count_label = QLabel()
        self.track_count_label.setProperty("role", "faint")
        head.addWidget(self.track_count_label)
        head.addStretch(1)

        reverb_caption = QLabel("混响")
        reverb_caption.setProperty("role", "faint")
        reverb_caption.setToolTip("项目混响：回放与 MIDI 导出同步")
        head.addWidget(reverb_caption)
        self.reverb_slider = QSlider(Qt.Orientation.Horizontal)
        self.reverb_slider.setRange(0, 100)
        self.reverb_slider.setFixedWidth(76)
        self.reverb_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reverb_slider.setToolTip("项目混响 0–100%")
        self.reverb_slider.valueChanged.connect(self._on_reverb_changed)
        head.addWidget(self.reverb_slider)
        self.reverb_label = QLabel("0%")
        self.reverb_label.setProperty("role", "mono")
        self.reverb_label.setFixedWidth(34)
        self.reverb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.reverb_label)

        self.add_track_button = self._button("＋ 新增音轨", "chip")
        self.add_track_button.clicked.connect(lambda: self.add_track())
        head.addWidget(self.add_track_button)
        box.addLayout(head)

        self.track_container = QWidget()
        self.track_layout = QVBoxLayout(self.track_container)
        self.track_layout.setContentsMargins(0, 0, 0, 0)
        self.track_layout.setSpacing(5)
        box.addWidget(self.track_container)
        return card

    def _build_roll(self) -> QWidget:
        card = CardFrame()
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("钢琴卷帘")
        set_scaled_font(title, self._theme, 14, QFont.Weight.DemiBold)
        head.addWidget(title)
        hint = QLabel("左键画 · 右键擦 · 拖动移动 · Ctrl+拖动复制 · 拖右缘改时值")
        hint.setProperty("role", "faint")
        head.addWidget(hint)
        head.addStretch(1)

        self.zoom_out_button = self._button("−", "icon")
        self.zoom_out_button.setFixedSize(26, 26)
        self.zoom_out_button.setToolTip("缩小卷帘")
        self.zoom_out_button.clicked.connect(lambda: self._zoom(1 / 1.25))
        head.addWidget(self.zoom_out_button)

        self.zoom_in_button = self._button("＋", "icon")
        self.zoom_in_button.setFixedSize(26, 26)
        self.zoom_in_button.setToolTip("放大卷帘")
        self.zoom_in_button.clicked.connect(lambda: self._zoom(1.25))
        head.addWidget(self.zoom_in_button)

        self.quantize_button = self._button("量化 1/8", "chip")
        self.quantize_button.setToolTip("把当前轨音符起点对齐到 1/8 网格")
        self.quantize_button.clicked.connect(self.quantize_current_track)
        head.addWidget(self.quantize_button)

        self.undo_button = self._button("撤销", "chip")
        self.undo_button.setToolTip("撤销上一次音符编辑")
        self.undo_button.clicked.connect(self._undo_edit)
        head.addWidget(self.undo_button)
        box.addLayout(head)

        self.roll = PianoRollCanvas(self._theme, self.editor)
        self.roll.noteEdited.connect(self._on_roll_edited)
        self.roll_scroll = QScrollArea()
        self.roll_scroll.setWidgetResizable(True)
        self.roll_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.roll_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.roll_scroll.setWidget(self.roll)
        self.roll_scroll.setFixedHeight(ROLL_HEIGHT + 18)
        box.addWidget(self.roll_scroll)
        return card

    # -- piano-roll edits -------------------------------------------------

    def _zoom(self, factor: float) -> None:
        self.roll.set_zoom(self.roll.pixels_per_beat * factor)

    def _on_roll_edited(self) -> None:
        self.player.stop()
        self._refresh_rows()
        self._update_undo()

    def quantize_current_track(self) -> int:
        if self.session.recording:
            self.message.emit("录音中不能量化 · 先按停止")
            return 0
        count = self.session.quantize_track(0.5)
        if count == 0:
            self.message.emit("当前轨没有可量化的音符")
            return 0
        self.player.stop()
        self.roll.refresh()
        self._refresh_rows()
        self._update_undo()
        self.message.emit(f"已量化 {count} 个音 · 1/8")
        return count

    def _undo_edit(self) -> None:
        if not self.editor.undo():
            self.message.emit("没有可撤销的编辑")
            return
        self.roll.refresh()
        self._refresh_rows()
        self._update_undo()
        self.message.emit("已撤销上一步音符编辑")

    def _update_undo(self) -> None:
        self.undo_button.setEnabled(self.editor.can_undo)

    def _button(self, text: str, role: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("role", role)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button

    # -- presentation -----------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.band.set_theme(theme)
        self.roll.set_theme(theme)

    def set_active(self, keys: set[int]) -> None:
        self.band.set_active(keys)

    def refresh(self) -> None:
        if not self._loaded:
            self._loaded = True
            path = self.default_path()
            if path.is_file():
                self.session.load(path)
                self.editor.set_project(
                    self.session.project, self.session.track_index
                )
        self._render()

    def default_path(self) -> Path:
        return self._session_path or (self.projects_dir / "project.json")

    def duration_text(self) -> str:
        seconds = int(self.session.elapsed_seconds(time.monotonic()))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _render(self) -> None:
        self._sync_metronome()
        self._sync_reverb()
        self.project_title.setText(self.session.project.title)
        self.track_count_label.setText(f"{len(self.session.project.tracks)}/{MAX_TRACKS}")
        self._render_tracks()
        self._set_transport()
        self._sync_live_program()
        self._sync_live_layer()
        self._sync_live_split()
        self._sync_play_button()
        self.roll.refresh()
        self._update_undo()

    def _render_tracks(self) -> None:
        clear_layout(self.track_layout)
        self.track_rows = []
        if not self.session.project.tracks:
            hint = QLabel("还没有音轨 · 按 ● 录音会自动建第一轨")
            hint.setProperty("role", "faint")
            self.track_layout.addWidget(hint)
            return
        for index, track in enumerate(self.session.project.tracks):
            row = TrackRow(
                self._theme, index, track, index == self.session.track_index
            )
            row.selectRequested.connect(self.select_track)
            row.programRequested.connect(self.cycle_program)
            row.volumeRequested.connect(self.adjust_volume)
            row.muteToggled.connect(self.set_track_mute)
            row.soloToggled.connect(self.set_track_solo)
            row.panChanged.connect(self.set_track_pan)
            row.layerToggled.connect(self.set_track_layer)
            row.splitToggled.connect(self.set_track_split)
            self.track_layout.addWidget(row)
            self.track_rows.append(row)

    def _refresh_rows(self) -> None:
        for row in self.track_rows:
            if row.index < len(self.session.project.tracks):
                row.refresh(
                    self.session.project.tracks[row.index],
                    row.index == self.session.track_index,
                )
        self.track_count_label.setText(
            f"{len(self.session.project.tracks)}/{MAX_TRACKS}"
        )

    def _set_transport(self) -> None:
        recording = self.session.recording
        self.record_button.setEnabled(not recording)
        self.overdub_button.setEnabled(not recording)
        self.stop_button.setEnabled(recording)
        self.loop_button.setEnabled(not recording)
        self.add_track_button.setEnabled(
            not recording and len(self.session.project.tracks) < MAX_TRACKS
        )
        with QSignalBlocker(self.loop_button):
            self.loop_button.setChecked(self.session.loop_enabled)

    def _sync_live_program(self) -> None:
        if self.session.track is None:
            return
        index = self.session.program_index()
        if getattr(self.instrument, "program_index", None) != index:
            self.instrument.set_program(index)

    # -- reverb -----------------------------------------------------------

    def _on_reverb_changed(self, value: int) -> None:
        self.set_reverb(value / 100.0)

    def set_reverb(self, value: float, notify: bool = True) -> None:
        amount = round(max(0.0, min(1.0, value)), 2)
        self.session.project.reverb = amount
        self.instrument.synth.set_reverb(amount)
        with QSignalBlocker(self.reverb_slider):
            self.reverb_slider.setValue(round(amount * 100))
        self.reverb_label.setText(f"{round(amount * 100)}%")
        if notify:
            self.message.emit(f"混响 {round(amount * 100)}%")

    def _sync_reverb(self) -> None:
        amount = max(0.0, min(1.0, self.session.project.reverb))
        self.instrument.synth.set_reverb(amount)
        with QSignalBlocker(self.reverb_slider):
            self.reverb_slider.setValue(round(amount * 100))
        self.reverb_label.setText(f"{round(amount * 100)}%")

    # -- recording --------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self.session.recording

    @property
    def is_playing(self) -> bool:
        return self.player.playing

    # -- metronome / count-in ---------------------------------------------

    def _sync_metronome(self) -> None:
        tempo = self.session.project.tempo
        self.metronome.bpm = tempo if tempo > 0 else 120.0
        self.metronome.beats_per_bar = self.session.project.time_signature[0]

    def start_metronome(self, at: float | None = None) -> None:
        self._sync_metronome()
        self.metronome.start(time.monotonic() if at is None else at)
        if not self._metronome_timer.isActive():
            self._metronome_timer.start()

    def stop_metronome(self) -> None:
        self.metronome.stop()
        self._metronome_timer.stop()
        self._stop_click_notes()
        if hasattr(self, "metronome_button"):
            with QSignalBlocker(self.metronome_button):
                self.metronome_button.setChecked(False)

    def tick_metronome(self, now: float) -> None:
        for click in self.metronome.advance(now):
            self._play_click(click.accent)

    def _tick_metronome(self) -> None:
        self.tick_metronome(time.monotonic())

    def _on_metronome_toggled(self, on: bool) -> None:
        if on:
            self.start_metronome()
        else:
            self.stop_metronome()

    def _play_click(self, accent: bool) -> None:
        midi = CLICK_ACCENT_MIDI if accent else CLICK_MIDI
        self._click_midi = midi
        self.instrument.synth.note_on(midi, 100, channel=CLICK_CHANNEL)
        self._click_off_timer.start()

    def _stop_click_notes(self) -> None:
        self._click_off_timer.stop()
        for midi in (CLICK_MIDI, CLICK_ACCENT_MIDI):
            self.instrument.synth.note_off(midi, channel=CLICK_CHANNEL)
        self._click_midi = None

    def toggle_playback(self) -> bool:
        if self.session.recording:
            self.message.emit("先停止录音再回放")
            return False
        if self.player.playing:
            self.player.stop()
            return False
        self._release_layer()
        self._release_split()
        self.player.set_project(self.session.project)
        return self.player.play()

    def stop_playback(self) -> None:
        if self.player.playing:
            self.player.stop()

    def _sync_play_button(self) -> None:
        self.play_button.setText("⏸ 暂停" if self.player.playing else "▶ 播放")

    def start_recording(
        self,
        overdub: bool = False,
        now: float | None = None,
        count_in: bool | None = None,
    ) -> bool:
        self.player.stop()
        self._sync_metronome()
        now = time.monotonic() if now is None else now
        if count_in is None:
            count_in = self.count_in_button.isChecked()
        tempo = self.session.project.tempo if self.session.project.tempo > 0 else 120.0
        count_in_beats = self.session.beats_per_bar if count_in else 0.0
        self._record_from = now + count_in_beats * 60.0 / tempo
        if not self.session.start(self._record_from, overdub):
            self.message.emit("已经在录音 · 先按停止")
            return False
        if count_in:
            self.session.project.count_in_used = True
        if count_in or self.metronome_button.isChecked():
            self.session.project.metronome_used = True
            self.start_metronome(now)
        self.editor.select_track(self.session.track_index)
        self._render_tracks()
        self._set_transport()
        self.roll.refresh()
        self._update_undo()
        self.duration_label.setText("00:00")
        self._clock.start()
        self.recordingChanged.emit(True)
        self.durationChanged.emit("00:00")
        self.status_label.setText(
            "叠录中 · 新音符并入当前音轨" if overdub else "录音中 · 松开按键结束一个音"
        )
        self.message.emit(
            f"开始叠录 · 音轨 {self.session.track_index + 1}"
            if overdub
            else f"开始录音 · 音轨 {self.session.track_index + 1}"
        )
        return True

    def note_event(self, event) -> None:
        track = self.session.track
        split = track.split if track is not None else None
        layer = track.layer if track is not None else None
        if split is not None:
            channel = (
                SPLIT_LEFT_CHANNEL
                if event.midi < split.midi
                else SPLIT_RIGHT_CHANNEL
            )
            key = (channel, event.midi)
            if event.kind == "on":
                self.instrument.synth.note_on(event.midi, 100, channel=channel)
                self._split_held.add(key)
            elif key in self._split_held:
                self.instrument.synth.note_off(event.midi, channel=channel)
                self._split_held.discard(key)
        elif event.kind == "on":
            if layer is not None:
                self.instrument.synth.note_on(
                    event.midi, 100, channel=LAYER_CHANNEL
                )
                self._layer_held.add(event.midi)
        elif event.midi in self._layer_held:
            self.instrument.synth.note_off(event.midi, channel=LAYER_CHANNEL)
            self._layer_held.discard(event.midi)

        if not self.session.recording:
            return
        if event.t < self._record_from - 1e-9:
            return  # count-in clicks are not recorded
        if event.kind == "on":
            self.session.note_on(event.midi, event.t)
        else:
            self.session.note_off(event.midi, event.t)

    def stop_recording(self, now: float | None = None, notify: bool = True) -> int:
        if not self.session.recording:
            return 0
        now = time.monotonic() if now is None else now
        count = self.session.stop(now)
        self._record_from = 0.0
        if not self.metronome_button.isChecked():
            self.stop_metronome()
        self._clock.stop()
        self.duration_label.setText("00:00")
        self._render_tracks()
        self._set_transport()
        self.roll.refresh()
        self._update_undo()
        self.status_label.setText("录音已停止 · 可继续叠录或保存")
        self.recordingChanged.emit(False)
        self.durationChanged.emit("00:00")
        if notify:
            self.message.emit(
                f"已录制 {count} 个音" if count else "本段没有录到音符"
            )
        return count

    def finalize(
        self,
        stop_metronome: bool = True,
        restore_audio: bool = True,
    ) -> None:
        self.stop_recording(notify=False)
        self.player.stop()
        self._release_layer()
        self._release_split()
        if restore_audio:
            self.instrument.synth.set_reverb(0.0)
            self._restore_base_channel()
        if stop_metronome:
            self.stop_metronome()

    def _tick_clock(self) -> None:
        if not self.session.recording:
            self._clock.stop()
            return
        text = self.duration_text()
        self.duration_label.setText(text)
        self.durationChanged.emit(text)

    # -- tracks -----------------------------------------------------------

    def add_track(self) -> Track | None:
        if self.session.recording:
            self.message.emit("录音中不能新增音轨")
            return None
        try:
            track = self.session.add_track()
        except ValueError as exc:
            self.message.emit(str(exc))
            return None
        self._render_tracks()
        self._set_transport()
        self.roll.refresh()
        self._update_undo()
        self.message.emit(f"已新增 {track.name}")
        return track

    def select_track(self, index: int) -> bool:
        if not self.session.select_track(index):
            return False
        self.editor.select_track(index)
        self._refresh_rows()
        self._sync_live_program()
        self._sync_live_layer()
        self._sync_live_split()
        self.roll.refresh()
        self._update_undo()
        return True

    def cycle_program(self, track_index: int) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        track = self.session.project.tracks[track_index]
        index = (_program_index(track.program) + 1) % len(PROGRAMS)
        track.program = PROGRAMS[index][0]
        self._refresh_rows()
        if track_index == self.session.track_index:
            self._sync_live_program()

    def adjust_volume(self, track_index: int, delta: float) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        track = self.session.project.tracks[track_index]
        track.volume = round(max(0.0, min(1.0, track.volume + delta)), 2)
        self._refresh_rows()

    def set_track_mute(self, track_index: int, on: bool) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        self.player.stop()
        self.session.project.tracks[track_index].mute = on
        self._refresh_rows()
        self.message.emit(
            f"音轨 {track_index + 1} · 静音{'开' if on else '关'}"
        )

    def set_track_solo(self, track_index: int, on: bool) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        self.player.stop()
        self.session.project.tracks[track_index].solo = on
        self._refresh_rows()
        self.message.emit(
            f"音轨 {track_index + 1} · 独奏{'开' if on else '关'}"
        )

    def set_track_pan(self, track_index: int, pan: float) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        self.player.stop()
        self.session.project.tracks[track_index].pan = round(
            max(-1.0, min(1.0, pan)), 2
        )
        self._refresh_rows()

    def set_track_layer(self, track_index: int, on: bool) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        self.player.stop()
        track = self.session.project.tracks[track_index]
        if on:
            track.split = None
            program = 48 if track.program != 48 else 4
            track.layer = Layer(program=program, volume=0.7)
        else:
            track.layer = None
        self._release_layer()
        self._release_split()
        self._sync_live_split()
        self._sync_live_layer()
        self._refresh_rows()
        self.message.emit(
            f"音轨 {track_index + 1} · 音色叠加{'开' if on else '关'}"
        )

    def set_track_split(self, track_index: int, on: bool) -> None:
        if not 0 <= track_index < len(self.session.project.tracks):
            return
        self.player.stop()
        track = self.session.project.tracks[track_index]
        if on:
            track.layer = None
            track.split = SplitSpec(
                midi=self.instrument.midi_for_key(17),
                left_program=32,
                right_program=track.program,
                left_volume=0.8,
                right_volume=min(1.0, max(0.0, track.volume)),
            )
        else:
            track.split = None
        self._release_layer()
        self._release_split()
        self._sync_live_split()
        self._sync_live_layer()
        self._refresh_rows()
        self.message.emit(
            f"音轨 {track_index + 1} · 键盘分区{'开' if on else '关'}"
        )

    def _sync_live_layer(self) -> None:
        track = self.session.track
        if track is not None and track.split is not None:
            self._release_layer()
            return
        layer = track.layer if track is not None else None
        if layer is None:
            self._release_layer()
            return
        self.instrument.synth.program_on(LAYER_CHANNEL, layer.program)
        self.instrument.synth.channel_volume(LAYER_CHANNEL, layer.volume)
        self.instrument.synth.channel_pan(LAYER_CHANNEL, track.pan)

    def _release_layer(self) -> None:
        for midi in self._layer_held:
            self.instrument.synth.note_off(midi, channel=LAYER_CHANNEL)
        self._layer_held.clear()

    def _sync_live_split(self) -> None:
        track = self.session.track
        split = track.split if track is not None else None
        if split is None:
            self._release_split()
            if hasattr(self, "band"):
                self.band.set_split_bar(None)
            self._restore_base_channel()
            return
        synth = self.instrument.synth
        synth.program_on(SPLIT_LEFT_CHANNEL, split.left_program)
        synth.channel_volume(SPLIT_LEFT_CHANNEL, split.left_volume)
        synth.channel_pan(SPLIT_LEFT_CHANNEL, -0.6)
        synth.program_on(SPLIT_RIGHT_CHANNEL, split.right_program)
        synth.channel_volume(SPLIT_RIGHT_CHANNEL, split.right_volume)
        synth.channel_pan(SPLIT_RIGHT_CHANNEL, 0.6)
        synth.channel_volume(0, 0.0)
        if hasattr(self, "band"):
            self.band.set_split_bar(self.split_bar)

    def _restore_base_channel(self) -> None:
        self.instrument.synth.channel_volume(
            0, 0.0 if self.instrument.muted else 1.0
        )

    def _release_split(self) -> None:
        for channel, midi in self._split_held:
            self.instrument.synth.note_off(midi, channel=channel)
        self._split_held.clear()

    @property
    def split_bar(self) -> int | None:
        track = self.session.track
        split = track.split if track is not None else None
        if split is None:
            return None
        for bar in range(1, 33):
            if self.instrument.midi_for_key(bar) >= split.midi:
                boundary = bar - 1
                return boundary if 0 < boundary < 32 else None
        return None

    def sync_audio_outputs(self) -> None:
        self._sync_live_split()
        self._sync_live_layer()

    # -- loop / persistence ----------------------------------------------

    def set_loop(self, enabled: bool, bars: int = 4) -> bool:
        if not self.session.set_loop(enabled, bars):
            self.message.emit("录音中不能改循环 · 先按停止")
            with QSignalBlocker(self.loop_button):
                self.loop_button.setChecked(self.session.loop_enabled)
            return False
        self.player.stop()
        with QSignalBlocker(self.loop_button):
            self.loop_button.setChecked(enabled)
        self.roll.refresh()
        self.message.emit(f"循环 1–{bars} 小节" if enabled else "循环关")
        return True

    def _on_loop_toggled(self, checked: bool) -> None:
        self.set_loop(checked, self._loop_bars)

    def export_project(self, path: Path | str | None = None) -> bool:
        self.finalize(stop_metronome=False, restore_audio=False)
        project = self.session.project
        solo = any(track.solo for track in project.tracks)
        audible = [
            track
            for track in project.tracks
            if not track.mute and (not solo or track.solo)
        ]
        if not any(track.notes for track in audible):
            self.message.emit("项目里还没有可导出的音符 · 先录一段或画一个音")
            return False
        path = (
            Path(path)
            if path is not None
            else self.default_path().with_suffix(".mid")
        )
        try:
            export_midi(project, path)
        except OSError as exc:
            self.message.emit(f"MIDI 导出失败：{exc}")
            return False
        project.exported = True
        self.message.emit(f"已导出 MIDI · {path.name}")
        return True

    def save_project(self, path: Path | str | None = None) -> bool:
        self.finalize(stop_metronome=False, restore_audio=False)
        path = Path(path) if path is not None else self.default_path()
        try:
            self.session.project.save(path)
        except OSError as exc:
            self.message.emit(f"保存失败：{exc}")
            return False
        self.message.emit(f"已保存 · {path.name}")
        return True

    def load_project(self, path: Path | str | None = None) -> bool:
        self.finalize(stop_metronome=False)
        path = Path(path) if path is not None else self.default_path()
        if not path.is_file():
            self.message.emit("还没有可载入的项目 · 先录一段并保存")
            return False
        if not self.session.load(path):
            self.message.emit("载入失败 · 文件不可读")
            return False
        self.editor.set_project(self.session.project, self.session.track_index)
        self._render()
        self.message.emit(f"已载入 · {path.name}")
        for notice in _fallback_notices(self.session.project):
            self.message.emit(notice)
        return True

    # -- 32-key band ------------------------------------------------------

    def _on_function(self, action: str, down: bool) -> None:
        inst = self.instrument
        if action == "sustain":
            inst.hold_sustain(down)
        elif down and action == "oct_down":
            inst.set_octave(-1)
        elif down and action == "oct_up":
            inst.set_octave(+1)
        elif down and action == "map":
            inst.cycle_preset()
