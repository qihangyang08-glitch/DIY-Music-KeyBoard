"""Secondary pages: 曲谱 / 校准 (info), 设备, 音色, 设置.

P1 is the performance shell. The pages that belong to P2/P3 are honest
placeholders with the planned scope written down; 设备 and 音色 get a small
read-only slice because it costs little and makes the shell feel real.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.accessibility import FONT_SCALE_PRESETS
from ..core.drums import DRUM_KITS
from ..core.instrument import Instrument
from ..core.programs import CATALOG, CATEGORIES
from .i18n_ui import tr
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame, ToggleSwitch

MODULES = (
    (0x5A, "模块 1 · 左侧 · 键 1–12"),
    (0x5C, "模块 2 · 中间 · 键 13–24"),
    (0x5D, "模块 3 · 右侧 · 键 25–32 + 4 个功能键"),
)


class InfoPage(GlassFrame):
    def __init__(self, theme: Theme, badge: str, title: str, subtitle: str, items: list[str]):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(12)

        badge_label = QLabel(badge)
        badge_label.setStyleSheet(f"color: {theme.amber.name()}; font-size: {theme.px(11)}px; font-weight: 600;")
        self._badge_label = badge_label
        heading = QLabel(title)
        set_scaled_font(heading, theme, 24, QFont.Weight.DemiBold)
        sub = QLabel(subtitle)
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        layout.addWidget(badge_label)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(6)
        for item in items:
            row = QLabel(f"·  {item}")
            row.setProperty("role", "muted")
            row.setWordWrap(True)
            layout.addWidget(row)
        layout.addStretch(1)

    def set_theme(self, theme: Theme) -> None:
        self._badge_label.setStyleSheet(
            f"color: {theme.amber.name()}; font-size: {theme.px(11)}px; font-weight: 600;"
        )


class DevicePage(GlassFrame):
    calibrationRequested = Signal()

    def __init__(self, theme: Theme, instrument: Instrument):
        super().__init__()
        self._theme = theme
        self.instrument = instrument
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(10)

        heading = QLabel("设备")
        set_scaled_font(heading, self._theme, 24, QFont.Weight.DemiBold)
        sub = QLabel("当前只读状态。通道表、原始监视与重新初始化在后续版本。")
        sub.setProperty("role", "muted")
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(8)

        self._rows: list[tuple[int, QLabel, QLabel]] = []
        for address, name in MODULES:
            card = CardFrame()
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)
            left = QVBoxLayout()
            left.setSpacing(2)
            title = QLabel(name)
            set_scaled_font(title, self._theme, 13, QFont.Weight.DemiBold)
            address_label = QLabel(f"0x{address:02X}")
            address_label.setProperty("role", "faint")
            set_scaled_font(address_label, self._theme, 10, mono=True)
            left.addWidget(title)
            left.addWidget(address_label)
            row.addLayout(left, 1)
            state = QLabel("—")
            set_scaled_font(state, self._theme, 12, QFont.Weight.DemiBold)
            row.addWidget(state)
            layout.addWidget(card)
            self._rows.append((address, state, title))

        note = QLabel("通道表、原始监视、错误计数：后续版本")
        note.setProperty("role", "faint")
        layout.addWidget(note)
        calibration = QPushButton("打开校准页")
        calibration.setProperty("role", "chip")
        calibration.setCursor(Qt.CursorShape.PointingHandCursor)
        calibration.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.calibration_button = calibration
        calibration.clicked.connect(
            lambda checked=False: self.calibrationRequested.emit()
        )
        layout.addWidget(calibration, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.refresh()

    def refresh(self) -> None:
        inst = self.instrument
        for address, state, _title in self._rows:
            if not inst.connected:
                text, color = "未连接", self._theme.faint
            elif inst.hardware_stale():
                text, color = "无心跳", self._theme.danger
            elif inst.modules.get(address):
                text, color = "在线", self._theme.amber
            else:
                text, color = "离线", self._theme.faint
            state.setText(text)
            state.setStyleSheet(f"color: {color.name()};")


class SoundPage(GlassFrame):
    def __init__(self, theme: Theme, instrument: Instrument, audio_message: str = ""):
        super().__init__()
        self._theme = theme
        self.instrument = instrument
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 26)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        holder = QWidget()
        holder.setObjectName("ScrollContent")
        holder.setMaximumWidth(820)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 6, 8)
        layout.setSpacing(10)
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll)

        heading = QLabel("音色")
        set_scaled_font(heading, self._theme, 24, QFont.Weight.DemiBold)
        sub = QLabel("当前简版：GM 音色切换。混响、亮度、SoundFont 导入在后续版本。")
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)
        if audio_message:
            rate = (
                f" · {instrument.synth.samplerate // 1000} kHz"
                if getattr(instrument.synth, "samplerate", 0)
                else ""
            )
            audio = QLabel(f"音频 · {audio_message}{rate}")
            audio.setProperty("role", "muted" if instrument.synth.available else "faint")
            audio.setWordWrap(True)
            if not instrument.synth.available:
                audio.setStyleSheet(f"color: {theme.danger.name()};")
            self._audio_label = audio
            layout.addWidget(audio)
        layout.addSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索音色、英文名或 GM 编号")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.set_search)
        layout.addWidget(self.search_edit)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self.category_buttons: dict[str, QPushButton] = {}
        self._category_group = QButtonGroup(self)
        self._category_group.setExclusive(True)
        for name in ("全部",) + CATEGORIES:
            chip = QPushButton(name)
            chip.setCheckable(True)
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            chip.setMinimumHeight(30)
            chip.setChecked(name == "全部")
            value = None if name == "全部" else name
            chip.clicked.connect(
                lambda checked=False, category=value: self.set_category(category)
            )
            filters.addWidget(chip)
            self._category_group.addButton(chip)
            self.category_buttons[name] = chip
        filters.addStretch(1)
        layout.addLayout(filters)
        layout.addSpacing(4)
        self._filter_category: str | None = None
        self._filter_text = ""

        self._grid = QGridLayout()
        self._grid.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for index, program in enumerate(CATALOG):
            btn = QPushButton(program.label)
            btn.setToolTip(f"{program.name} · GM {program.gm}")
            btn.setCheckable(True)
            btn.setProperty("role", "chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setMinimumHeight(38)
            btn.setMaximumWidth(240)
            btn.clicked.connect(
                lambda checked=False, i=index: instrument.set_program(i)
            )
            self._group.addButton(btn, index)
            self._buttons.append(btn)
        layout.addLayout(self._grid)
        self._apply_filter()
        layout.addSpacing(10)

        drum_head = QHBoxLayout()
        drum_title = QLabel("鼓组 · 专用通道 9")
        set_scaled_font(drum_title, self._theme, 14, QFont.Weight.DemiBold)
        drum_head.addWidget(drum_title)
        drum_head.addStretch(1)
        drum_label = QLabel("鼓垫模式")
        drum_label.setProperty("role", "muted")
        drum_head.addWidget(drum_label)
        self.drum_switch = ToggleSwitch(theme)
        self.drum_switch.toggled.connect(self._set_drums)
        drum_head.addWidget(self.drum_switch)
        layout.addLayout(drum_head)

        kit_grid = QGridLayout()
        kit_grid.setSpacing(6)
        self.kit_buttons: list[QPushButton] = []
        for index, kit in enumerate(DRUM_KITS):
            chip = QPushButton(kit.label)
            chip.setToolTip(f"{kit.name} · bank 128 / {kit.program}")
            chip.setCheckable(True)
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            chip.setMinimumHeight(34)
            chip.clicked.connect(
                lambda checked=False, i=index: instrument.set_drum_kit(i)
            )
            kit_grid.addWidget(chip, index // 4, index % 4)
            self.kit_buttons.append(chip)
        layout.addLayout(kit_grid)
        drum_note = QLabel("鼓垫模式：32 键显示鼓件名，不参与跟弹/学习判定。")
        drum_note.setProperty("role", "faint")
        drum_note.setWordWrap(True)
        layout.addWidget(drum_note)
        layout.addSpacing(6)

        mute_row = QHBoxLayout()
        mute_text = QLabel("静音")
        mute_text.setProperty("role", "muted")
        self._audio_label = None
        self.mute_switch = ToggleSwitch(theme)
        self.mute_switch.toggled.connect(lambda on: self._set_mute(on))
        mute_row.addWidget(mute_text, 0)
        mute_row.addSpacing(18)
        mute_row.addWidget(self.mute_switch)
        mute_row.addStretch(1)
        layout.addLayout(mute_row)

        fixed = QLabel("固定力度 100 · 不做按键力度（探针结论）")
        fixed.setProperty("role", "faint")
        layout.addWidget(fixed)
        layout.addStretch(1)
        self.refresh()

    def _set_mute(self, on: bool) -> None:
        if on != self.instrument.muted:
            self.instrument.toggle_mute()

    def _set_drums(self, on: bool) -> None:
        if on != self.instrument.drums_enabled:
            self.instrument.set_drums(on)
            self.refresh()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.mute_switch.set_theme(theme)
        if self._audio_label is not None:
            if self.instrument.synth.available:
                self._audio_label.setStyleSheet("")
            else:
                self._audio_label.setStyleSheet(f"color: {theme.danger.name()};")

    def set_category(self, category: str | None) -> None:
        """Show only one category; ``None`` means 全部."""
        self._filter_category = category
        name = "全部" if category is None else category
        button = self.category_buttons[name]
        with QSignalBlocker(button):
            button.setChecked(True)
        self._apply_filter()

    def set_search(self, text: str) -> None:
        """Filter by Chinese label, English GM name or GM number."""
        self._filter_text = text
        self._apply_filter()

    def _visible_indices(self) -> list[int]:
        text = self._filter_text.strip().lower()
        visible: list[int] = []
        for index, program in enumerate(CATALOG):
            if (
                self._filter_category is not None
                and program.category != self._filter_category
            ):
                continue
            if text and not (
                text in program.label.lower()
                or text in program.name.lower()
                or text == str(program.gm)
            ):
                continue
            visible.append(index)
        return visible

    def _apply_filter(self) -> None:
        for button in self._buttons:
            self._grid.removeWidget(button)
            button.hide()
        for slot, index in enumerate(self._visible_indices()):
            self._grid.addWidget(self._buttons[index], slot // 3, slot % 3)
            self._buttons[index].show()

    def refresh(self) -> None:
        for index, btn in enumerate(self._buttons):
            with QSignalBlocker(btn):
                btn.setChecked(index == self.instrument.program_index)
        for index, btn in enumerate(self.kit_buttons):
            with QSignalBlocker(btn):
                btn.setChecked(index == self.instrument.drum_kit_index)
        with QSignalBlocker(self.drum_switch):
            self.drum_switch.setChecked(self.instrument.drums_enabled)
        with QSignalBlocker(self.mute_switch):
            self.mute_switch.setChecked(self.instrument.muted)


class SettingsPage(GlassFrame):
    themeRequested = Signal(str)
    soundRequested = Signal()
    keybindingsRequested = Signal()
    helpRequested = Signal()
    reduceMotionChanged = Signal(bool)
    fontScaleChanged = Signal(float)
    languageRequested = Signal(str)

    def __init__(self, theme: Theme):
        super().__init__()
        self._theme = theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 26)
        outer.setSpacing(0)
        holder = QWidget()
        holder.setMaximumWidth(820)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        outer.addWidget(holder, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        outer.addStretch(1)

        heading = QLabel("设置")
        set_scaled_font(heading, self._theme, 24, QFont.Weight.DemiBold)
        sub = QLabel("主题、语言、辅助功能、键位与音色；更多设置在后续版本。")
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(6)

        theme_row = QHBoxLayout()
        theme_label = QLabel("主题")
        theme_label.setProperty("role", "muted")
        theme_row.addWidget(theme_label, 0)
        theme_row.addSpacing(18)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_buttons: dict[str, QPushButton] = {}
        for name, text in (("studio", "纸白（Studio）"), ("stage", "暗场（Stage）")):
            btn = QPushButton(text)
            btn.setProperty("role", "chip")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setToolTip("Tab 聚焦，←/→ 移动，Enter/Space 选择")
            btn.clicked.connect(lambda checked=False, n=name: self.themeRequested.emit(n))
            self._theme_group.addButton(btn)
            self._theme_buttons[name] = btn
            theme_row.addWidget(btn)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)

        language_row = QHBoxLayout()
        language_label = QLabel("语言")
        language_label.setProperty("role", "muted")
        language_row.addWidget(language_label, 0)
        language_row.addSpacing(18)
        self._language_group = QButtonGroup(self)
        self._language_group.setExclusive(True)
        self._language_buttons: list[QPushButton] = []
        self._language_codes: list[str] = []
        for code, text in (("zh-CN", "中文"), ("en", "English")):
            btn = QPushButton(text)
            btn.setProperty("role", "chip")
            btn.setCheckable(True)
            btn.setChecked(code == "zh-CN")
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.clicked.connect(
                lambda checked=False, c=code: self.languageRequested.emit(c)
            )
            self._language_group.addButton(btn)
            self._language_buttons.append(btn)
            self._language_codes.append(code)
            language_row.addWidget(btn)
        language_row.addStretch(1)
        layout.addLayout(language_row)

        layout.addSpacing(8)
        access = QLabel("辅助功能")
        access.setProperty("role", "label")
        layout.addWidget(access)
        motion_row = QHBoxLayout()
        motion_text = QLabel("减少动效")
        motion_text.setProperty("role", "muted")
        motion_help = (
            "关闭光条上的呼吸、光柱与松键淡出；跟弹判定与播放头不受影响。"
        )
        motion_text.setToolTip(motion_help)
        motion_row.addWidget(motion_text, 1)
        self.reduce_motion_switch = ToggleSwitch(theme)
        self.reduce_motion_switch.setToolTip(motion_help)
        self.reduce_motion_switch.toggled.connect(self.reduceMotionChanged.emit)
        motion_row.addWidget(self.reduce_motion_switch)
        layout.addLayout(motion_row)

        font_row = QHBoxLayout()
        font_label = QLabel("字号")
        font_label.setProperty("role", "muted")
        font_label.setToolTip("只缩放界面文字；光条与谱面几何不变")
        font_row.addWidget(font_label, 1)
        self._font_group = QButtonGroup(self)
        self._font_group.setExclusive(True)
        self.font_scale_buttons: dict[float, QPushButton] = {}
        for scale, text in FONT_SCALE_PRESETS:
            btn = QPushButton(text)
            btn.setProperty("role", "chip")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setToolTip(f"界面文字 {int(scale * 100)}%")
            btn.clicked.connect(
                lambda checked=False, s=scale: self.fontScaleChanged.emit(s)
            )
            self._font_group.addButton(btn)
            self.font_scale_buttons[scale] = btn
            font_row.addWidget(btn)
        font_row.addStretch(1)
        layout.addLayout(font_row)
        cue_hint = QLabel("对错反馈不只靠颜色：× / ✓ 与文字同时显示。")
        cue_hint.setProperty("role", "faint")
        cue_hint.setWordWrap(True)
        layout.addWidget(cue_hint)

        layout.addSpacing(8)
        advanced = QLabel("高级（只读）")
        advanced.setProperty("role", "label")
        layout.addWidget(advanced)
        for text in (
            "松开宽限 20 ms · 连奏关闭",
            "固定力度 100",
            "方案 · 裸铜 · 未校准（校准页制作中）",
            "会话日志：后续版本接入",
        ):
            row = QLabel(f"·  {tr(text)}")
            row.setProperty("role", "muted")
            layout.addWidget(row)

        layout.addSpacing(8)
        tools = QLabel("工具")
        tools.setProperty("role", "label")
        layout.addWidget(tools)
        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        for text, signal in (
            ("键位设置", self.keybindingsRequested),
            ("音色页", self.soundRequested),
            ("怎么用（F1）", self.helpRequested),
        ):
            btn = QPushButton(text)
            btn.setProperty("role", "chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.clicked.connect(lambda checked=False, s=signal: s.emit())
            tool_row.addWidget(btn)
        tool_row.addStretch(1)
        layout.addLayout(tool_row)

        hint = QLabel("键位可在“键位设置”里全部改绑；字母默认留给音符。")
        hint.setProperty("role", "faint")
        layout.addWidget(hint)
        layout.addStretch(1)
        self.set_current_theme("studio")

    def set_current_theme(self, name: str) -> None:
        btn = self._theme_buttons.get(name)
        if btn is not None:
            with QSignalBlocker(btn):
                btn.setChecked(True)

    def set_reduce_motion(self, on: bool) -> None:
        with QSignalBlocker(self.reduce_motion_switch):
            self.reduce_motion_switch.setChecked(bool(on))

    def set_language(self, code: str) -> None:
        for button, button_code in zip(
            self._language_buttons, self._language_codes
        ):
            with QSignalBlocker(button):
                button.setChecked(button_code == code)

    def move_chip_focus(self, widget, key: int) -> bool:
        """Left/Right move focus inside a chip row; consumed when relevant."""
        if key == int(Qt.Key.Key_Left):
            delta = -1
        elif key == int(Qt.Key.Key_Right):
            delta = 1
        else:
            return False
        for row in (
            list(self._theme_buttons.values()),
            self._language_buttons,
            list(self.font_scale_buttons.values()),
        ):
            if widget not in row:
                continue
            enabled = [button for button in row if button.isEnabled()]
            if widget not in enabled:
                return True
            index = enabled.index(widget)
            enabled[(index + delta) % len(enabled)].setFocus()
            return True
        return False

    def set_font_scale(self, scale: float) -> None:
        """Check the chip for the applied scale; custom values stay unchecked."""
        exact = next(
            (
                preset
                for preset in self.font_scale_buttons
                if abs(preset - scale) < 1e-9
            ),
            None,
        )
        self._font_group.setExclusive(False)
        for preset, button in self.font_scale_buttons.items():
            with QSignalBlocker(button):
                button.setChecked(preset == exact)
        self._font_group.setExclusive(True)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.reduce_motion_switch.set_theme(theme)
