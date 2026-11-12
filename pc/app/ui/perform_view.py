"""The performance page: guide strip, score, right panel, keyboard + pads."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.instrument import Instrument
from ..core.mapping import PRESETS
from ..core.synth_service import program_label_cn
from .i18n_ui import tr
from .light_bar import HintBand, LightBarBand, LightColumnOverlay
from .score_view import ScoreView
from .theme import Theme, rgba, set_scaled_font
from .widgets import CardFrame, GlassFrame, ToggleSwitch


class ClickCard(CardFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PerformView(QWidget):
    message = Signal(str)
    focusToggled = Signal(bool)
    resetSplitRequested = Signal()

    def __init__(self, theme: Theme, instrument: Instrument, bindings, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self._window_info: str | None = None
        self.setObjectName("Perform")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        # -- guide strip ---------------------------------------------------
        guide_frame = GlassFrame()
        guide_frame.setFixedHeight(46)
        guide_row = QHBoxLayout(guide_frame)
        guide_row.setContentsMargins(14, 0, 14, 0)
        guide_row.setSpacing(14)

        next_caption = QLabel("下一键")
        next_caption.setProperty("role", "faint")
        set_scaled_font(next_caption, self._theme, 9, QFont.Weight.DemiBold)
        self.next_value = QLabel("—")
        self.next_value.setProperty("role", "amber")
        set_scaled_font(self.next_value, self._theme, 12, QFont.Weight.DemiBold, mono=True)
        self.follow_label = QLabel("无跟随 · 手动翻页")
        self.follow_label.setProperty("role", "faint")
        guide_row.addWidget(next_caption)
        guide_row.addWidget(self.next_value)
        guide_row.addWidget(self.follow_label)

        self.guide = HintBand(theme, instrument)
        self.guide.setFixedHeight(28)
        self.guide.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        guide_row.addWidget(self.guide, 1)

        self.map_label = QLabel("范围 F4–C7")
        self.map_label.setProperty("role", "faint")
        set_scaled_font(self.map_label, self._theme, 9, QFont.Weight.Medium, mono=True)
        guide_row.addWidget(self.map_label)
        outer.addWidget(guide_frame)

        # -- score + right panel ------------------------------------------
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        self.score = ScoreView(theme)
        self.score.message.connect(self.message)
        self.score.focusToggled.connect(self.focusToggled)
        workspace.addWidget(self.score, 1)
        self.panel = self._build_panel()
        workspace.addWidget(self.panel, 0)
        outer.addLayout(workspace, 1)

        # -- v3 light bar (C curtain, 52 px) -------------------------------
        self.band = LightBarBand(theme, instrument, bindings)
        self.band.function.connect(self._on_function)
        outer.addWidget(self.band)

        # Note waves are an overlay: they rise into the score and never take
        # part in layout or mouse input.
        self.effects = LightColumnOverlay(self, self.band)
        self.effects.set_theme(theme)
        self.effects.setGeometry(0, 0, self.width(), 0)
        QTimer.singleShot(0, self._place_effects)

        self.refresh()

    # -- right panel ------------------------------------------------------

    def _build_panel(self) -> QWidget:
        t = self._theme
        panel = GlassFrame()
        panel.setFixedWidth(286)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        content.setObjectName("ScrollContent")
        content.setAutoFillBackground(False)
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        # 音色
        self.sound_card = ClickCard()
        sound = QVBoxLayout(self.sound_card)
        sound.setContentsMargins(12, 9, 12, 9)
        sound.setSpacing(3)
        sound_label = QLabel("音色")
        sound_label.setProperty("role", "label")
        sound.addWidget(sound_label)
        sound_row = QHBoxLayout()
        self.sound_value = QLabel("钢琴 1")
        self.sound_value.setProperty("role", "value")
        sound_row.addWidget(self.sound_value, 1)
        chev = QLabel("›")
        chev.setProperty("role", "faint")
        set_scaled_font(chev, self._theme, 15)
        sound_row.addWidget(chev)
        sound.addLayout(sound_row)
        self.sound_card.clicked.connect(self.instrument.cycle_program)
        col.addWidget(self.sound_card)

        # 映射
        map_card = CardFrame()
        mapping = QVBoxLayout(map_card)
        mapping.setContentsMargins(12, 10, 12, 10)
        mapping.setSpacing(4)
        map_label = QLabel("映射")
        map_label.setProperty("role", "label")
        mapping.addWidget(map_label)
        self.map_name = QLabel("半音阶")
        self.map_name.setProperty("role", "value")
        mapping.addWidget(self.map_name)
        self.map_range = QLabel("F4–C7")
        self.map_range.setProperty("role", "faint")
        set_scaled_font(self.map_range, self._theme, 10, QFont.Weight.Normal, mono=True)
        mapping.addWidget(self.map_range)
        split_row = QHBoxLayout()
        split_row.setSpacing(6)
        self.split_hint = QLabel("")
        self.split_hint.setProperty("role", "faint")
        set_scaled_font(self.split_hint, self._theme, 9, QFont.Weight.DemiBold)
        self.split_hint.setStyleSheet(f"color: {rgba(t.amber)};")
        split_row.addWidget(self.split_hint, 1)
        self.split_reset = QPushButton("重置")
        self.split_reset.setFlat(True)
        self.split_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.split_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        set_scaled_font(self.split_reset, self._theme, 9, QFont.Weight.DemiBold)
        self.split_reset.setStyleSheet(f"color: {rgba(t.amber)};")
        self.split_reset.setToolTip(
            "清除本曲目保存的分区点，恢复内容默认的分区位置"
        )
        self.split_reset.clicked.connect(self.resetSplitRequested.emit)
        split_row.addWidget(self.split_reset, 0)
        mapping.addLayout(split_row)

        auto_row = QHBoxLayout()
        auto_row.setSpacing(8)
        auto_text = QLabel("自动跟随乐谱")
        auto_text.setProperty("role", "muted")
        auto_help = (
            "开启后按乐句（最多 4 小节）自动切换 32 键的八度窗口，"
            "让宽音域谱也能弹；关闭则保持当前映射与八度。"
        )
        auto_text.setToolTip(auto_help)
        auto_row.addWidget(auto_text, 1)
        self.auto_switch = ToggleSwitch(t)
        self.auto_switch.setToolTip(auto_help)
        self.auto_switch.toggled.connect(self.instrument.toggle_auto_follow)
        auto_row.addWidget(self.auto_switch)
        mapping.addLayout(auto_row)

        chips = QGridLayout()
        chips.setContentsMargins(0, 2, 0, 0)
        chips.setHorizontalSpacing(6)
        chips.setVerticalSpacing(6)
        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        self._preset_buttons: list[QPushButton] = []
        for index, preset in enumerate(PRESETS):
            btn = QPushButton(tr(preset.label_cn))
            btn.setToolTip(f"{preset.label} · {preset.note}")
            btn.setProperty("role", "chip")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda checked=False, i=index: self.instrument.set_preset(i))
            self._preset_group.addButton(btn, index)
            self._preset_buttons.append(btn)
            chips.addWidget(btn, index // 2, index % 2)
        mapping.addLayout(chips)
        col.addWidget(map_card)

        # 八度 / 移调
        offset_card = CardFrame()
        offsets = QVBoxLayout(offset_card)
        offsets.setContentsMargins(12, 10, 12, 10)
        offsets.setSpacing(6)
        self.octave_value = self._offset_row(
            offsets, "八度", lambda d: self.instrument.set_octave(d)
        )
        self.transpose_value = self._offset_row(
            offsets, "移调", lambda d: self.instrument.set_transpose(d)
        )
        col.addWidget(offset_card)

        # actions
        actions = QHBoxLayout()
        actions.setSpacing(8)
        record = QPushButton("● 录音")
        record.setProperty("role", "action")
        record.setCursor(Qt.CursorShape.PointingHandCursor)
        record.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        record.clicked.connect(
            lambda: self.message.emit("录音请到创作页 · MIDI 导出在后续版本接入")
        )
        panic = QPushButton("全部静音")
        panic.setProperty("role", "danger")
        panic.setToolTip("立刻停掉所有正在响的音（Esc）")
        panic.setCursor(Qt.CursorShape.PointingHandCursor)
        panic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        panic.clicked.connect(self.instrument.panic)
        actions.addWidget(record, 1)
        actions.addWidget(panic, 1)
        col.addLayout(actions)

        col.addStretch(1)
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(2, 0, 0, 0)
        profile = QLabel("方案 · 裸铜")
        profile.setProperty("role", "faint")
        calibrated = QLabel("未校准 · 后续版本")
        calibrated.setProperty("role", "faint")
        footer.addWidget(profile, 1)
        footer.addWidget(calibrated)
        lay.addLayout(footer)
        return panel

    def _offset_row(self, layout: QVBoxLayout, caption: str, step) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(6)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        cap = QLabel(caption)
        cap.setProperty("role", "faint")
        value = QLabel("+0")
        set_scaled_font(value, self._theme, 18, QFont.Weight.DemiBold, mono=True)
        text_col.addWidget(cap)
        text_col.addWidget(value)
        row.addLayout(text_col, 1)

        reset = QPushButton("↺")
        reset.setProperty("role", "step")
        reset.setFixedSize(24, 24)
        reset.setToolTip(f"复位{caption}")
        reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset.clicked.connect(lambda: self._reset_offset(caption))
        minus = QPushButton("−")
        minus.setProperty("role", "step")
        minus.setFixedSize(24, 24)
        minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        minus.clicked.connect(lambda: step(-1))
        plus = QPushButton("+")
        plus.setProperty("role", "step")
        plus.setFixedSize(24, 24)
        plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        plus.clicked.connect(lambda: step(+1))
        row.addWidget(reset)
        row.addWidget(minus)
        row.addWidget(plus)
        layout.addLayout(row)
        return value

    def _reset_offset(self, caption: str) -> None:
        if caption == "八度":
            self.instrument.set_octave(-self.instrument.octave)
        else:
            self.instrument.set_transpose(-self.instrument.transpose)

    # -- state -> view ----------------------------------------------------

    def refresh(self) -> None:
        inst = self.instrument
        preset = inst.current_preset
        with QSignalBlocker(self.auto_switch):
            self.auto_switch.setChecked(inst.auto_follow)
        program_name = inst.synth_programs()[inst.program_index][1]
        self.sound_value.setText(program_label_cn(program_name))
        self.sound_value.setToolTip(program_name)
        if inst.auto_follow:
            self.map_name.setText(f"自动跟随 · {preset.label_cn}")
            detail = self._window_info or f"{preset.range_label(inst.offset)} · 音域适配"
            self.map_range.setText(detail)
        else:
            self.map_name.setText(preset.label_cn)
            self.map_range.setText(preset.range_label(inst.offset))
        self.map_label.setText(f"{tr('范围')} {preset.range_label(inst.offset)}")
        split = preset.split
        if split is not None:
            self.split_hint.setText(
                f"分区 {split.bar} · 拖动光条琥珀线调整"
            )
            self.split_hint.show()
            self.split_reset.show()
        else:
            self.split_hint.clear()
            self.split_hint.hide()
            self.split_reset.hide()
        current_key = preset.key
        # An exclusive QButtonGroup refuses to uncheck its current button, so
        # a content mapping ("content", no chip) would leave the old preset
        # highlighted. Drop exclusivity for the refresh, then restore it.
        self._preset_group.setExclusive(False)
        try:
            for index, btn in enumerate(self._preset_buttons):
                with QSignalBlocker(btn):
                    btn.setChecked(PRESETS[index].key == current_key)
        finally:
            self._preset_group.setExclusive(True)
        self.octave_value.setText(f"{inst.octave:+d}")
        self.transpose_value.setText(f"{inst.transpose:+d}")
        self.band.set_sustain(inst.sustain)
        self.band.update()
        self.guide.update()

    def set_window_info(self, text: str | None) -> None:
        """Auto-follow's current phrase window, or None when it is off."""
        self._window_info = text

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        for widget in (
            self.guide,
            self.band,
            self.effects,
            self.score,
            self.auto_switch,
        ):
            widget.set_theme(theme)
        self._place_effects()

    def set_accessibility(self, reduce_motion: bool) -> None:
        self.band.set_reduce_motion(reduce_motion)
        self.effects.set_reduce_motion(reduce_motion)

    def set_active(self, keys: set[int]) -> None:
        self.band.set_active(keys)
        self.guide.set_active(keys)

    def set_next_key(self, bar: int | None, note) -> None:
        self.band.set_next_key(bar)
        self.guide.set_next_key(bar)
        if note is None:
            self.next_value.setText("—")
            self.follow_label.setText(tr("无跟随 · 手动翻页"))
        elif bar is None:
            self.next_value.setText(f"{note.name} · {tr('超出音域')}")
            self.follow_label.setText(tr("跟弹 · 当前音域不够"))
        else:
            self.next_value.setText(f"{note.name} · {tr('光条')} {bar}")
            self.follow_label.setText(tr("跟弹 · 按对前进"))

    def set_follow_state(
        self,
        position: float,
        expected_index: int,
        hits: int,
        misses: int,
        playing: bool,
        next_note,
    ) -> None:
        self.score.set_follow_state(
            position, expected_index, hits, misses, playing, next_note
        )

    def set_score(self, score) -> None:
        self.score.set_score(score)

    def set_pad_state(self, state: dict[int, bool]) -> None:
        # Pad 1 is sustain; the other pads act on the instrument directly.
        self.band.set_sustain(state.get(1, False))

    def toggle_labels(self) -> None:
        self.band.set_labels(not self.band.labels_on)

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

    def set_right_panel_visible(self, visible: bool) -> None:
        self.panel.setVisible(visible)

    def add_wave(self, key_no: int) -> None:
        self.effects.spawn(key_no)

    # -- overlay geometry -------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_effects()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._place_effects)

    def _place_effects(self) -> None:
        if not hasattr(self, "effects"):
            return
        top = self.band.mapTo(self, QPoint(0, 0)).y()
        self.effects.setGeometry(0, 0, self.width(), max(0, top))
        self.effects.raise_()
        self.band.raise_()
