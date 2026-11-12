"""Settings → 键位: rebind the 32 note keys and the function shortcuts."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .keybindings import (
    Chord,
    FUNCTION_LABELS,
    MOD_ALT,
    MOD_CTRL,
    MOD_META,
    MOD_SHIFT,
    MODIFIER_KEYS,
    NOTE_COUNT,
    KeyBindings,
)
from .theme import Theme, set_scaled_font
from .widgets import GlassFrame, hairline


class KeyBindingsPage(GlassFrame):
    changed = Signal()
    capturingChanged = Signal(bool)

    def __init__(self, theme: Theme, bindings: KeyBindings, instrument, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.bindings = bindings
        self.instrument = instrument
        self._capture: tuple[str, int | str] | None = None
        self._note_key_labels: dict[int, QLabel] = {}
        self._note_name_labels: dict[int, QLabel] = {}
        self._function_labels: dict[str, QLabel] = {}
        # Exposed so keyboard tests (and future tab-order code) can address
        # the capture buttons without searching by button text.
        self.note_edit_buttons: dict[int, QPushButton] = {}
        self.function_edit_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 22)
        outer.setSpacing(8)

        heading = QLabel("键位")
        set_scaled_font(heading, self._theme, 24, QFont.Weight.DemiBold)
        sub = QLabel(
            "电脑键盘和实体琴共用同一台乐器。字母默认留给音符，功能动作放在 "
            "Ctrl 组合；每个音符键和功能键都可以改绑。"
        )
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        outer.addWidget(heading)
        outer.addWidget(sub)
        outer.addSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        preset_caption = QLabel("方案")
        preset_caption.setProperty("role", "faint")
        self.preset_label = QLabel("三行顺序")
        set_scaled_font(self.preset_label, self._theme, 10, QFont.Weight.DemiBold)
        toolbar.addWidget(preset_caption)
        toolbar.addWidget(self.preset_label)
        toolbar.addSpacing(14)

        reset = self._button("恢复默认")
        reset.clicked.connect(self._reset_defaults)
        toolbar.addWidget(reset)
        export = self._button("导出")
        export.clicked.connect(self._export)
        toolbar.addWidget(export)
        import_btn = self._button("导入")
        import_btn.clicked.connect(self._import)
        toolbar.addWidget(import_btn)
        toolbar.addStretch(1)

        self.conflict_label = QLabel("")
        self.conflict_label.setProperty("role", "faint")
        toolbar.addWidget(self.conflict_label)
        outer.addLayout(toolbar)

        self.status = QLabel("就绪")
        self.status.setProperty("role", "muted")
        set_scaled_font(self.status, self._theme, 9)
        outer.addWidget(self.status)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_buttons: list[QPushButton] = []
        for index, text in enumerate(("演奏键位（32）", "功能键位")):
            btn = QPushButton(text)
            btn.setProperty("role", "chip")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=index: self._switch_tab(i))
            self._tab_group.addButton(btn, index)
            self._tab_buttons.append(btn)
            tabs.addWidget(btn)
        self._tab_buttons[0].setChecked(True)
        tabs.addStretch(1)
        outer.addLayout(tabs)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_note_page())
        self._stack.addWidget(self._build_function_page())
        self._stack.setMaximumWidth(1000)
        stack_row = QHBoxLayout()
        stack_row.setContentsMargins(0, 0, 0, 0)
        stack_row.addWidget(self._stack, 1)
        outer.addLayout(stack_row, 1)

        outer.addWidget(hairline())
        footer = QLabel(
            "改绑时按一个键；Esc 取消。冲突会提示替换；方案自动保存，可导出/导入。"
        )
        footer.setProperty("role", "faint")
        footer.setWordWrap(True)
        set_scaled_font(footer, self._theme, 8)
        outer.addWidget(footer)

        self.refresh()

    # -- construction ---------------------------------------------------

    def _button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("role", "chip")
        btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setAutoFillBackground(False)
        content.setObjectName("ScrollContent")
        scroll.setWidget(content)
        return scroll

    def _build_note_page(self) -> QWidget:
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(2, 6, 2, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        headers = ("光条", "电脑键", "音名", "")
        for column, text in enumerate(headers):
            label = QLabel(text)
            label.setProperty("role", "faint")
            set_scaled_font(label, self._theme, 9, QFont.Weight.DemiBold)
            grid.addWidget(label, 0, column)
        grid.setColumnStretch(4, 1)  # compact table, left aligned

        for row, bar in enumerate(range(1, NOTE_COUNT + 1), start=1):
            bar_label = QLabel(f"光条 {bar}")
            set_scaled_font(bar_label, self._theme, 9)
            bar_label.setProperty("role", "muted")
            grid.addWidget(bar_label, row, 0)

            key_label = QLabel(self.bindings.keycap(bar))
            set_scaled_font(key_label, self._theme, 10, QFont.Weight.DemiBold, mono=True)
            key_label.setMinimumWidth(86)
            grid.addWidget(key_label, row, 1)
            self._note_key_labels[bar] = key_label

            name_label = QLabel(self.instrument.note_for_key(bar))
            name_label.setProperty("role", "faint")
            set_scaled_font(name_label, self._theme, 9, mono=True)
            grid.addWidget(name_label, row, 2)
            self._note_name_labels[bar] = name_label

            edit = self._button("改")
            edit.setMinimumHeight(22)
            edit.setFixedWidth(44)
            edit.clicked.connect(lambda checked=False, b=bar: self.start_capture("note", b))
            self.note_edit_buttons[bar] = edit
            clear = self._button("清除")
            clear.setMinimumHeight(22)
            clear.setFixedWidth(54)
            clear.clicked.connect(lambda checked=False, b=bar: self._clear_note(b))
            actions = QHBoxLayout()
            actions.setSpacing(4)
            actions.addWidget(edit)
            actions.addWidget(clear)
            holder = QWidget()
            holder.setLayout(actions)
            grid.addWidget(holder, row, 3)

        return self._scroll(content)

    def _build_function_page(self) -> QWidget:
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(2, 6, 2, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        for column, text in enumerate(("动作", "当前键", "")):
            label = QLabel(text)
            label.setProperty("role", "faint")
            set_scaled_font(label, self._theme, 9, QFont.Weight.DemiBold)
            grid.addWidget(label, 0, column)
        grid.setColumnStretch(3, 1)  # compact table, left aligned

        for row, (action, label_text) in enumerate(FUNCTION_LABELS.items(), start=1):
            action_label = QLabel(label_text)
            set_scaled_font(action_label, self._theme, 10)
            grid.addWidget(action_label, row, 0)

            chord_label = QLabel(self._function_text(action))
            set_scaled_font(chord_label, self._theme, 10, QFont.Weight.DemiBold, mono=True)
            chord_label.setMinimumWidth(100)
            grid.addWidget(chord_label, row, 1)
            self._function_labels[action] = chord_label

            edit = self._button("改")
            edit.setMinimumHeight(22)
            edit.setFixedWidth(44)
            edit.clicked.connect(
                lambda checked=False, a=action: self.start_capture("function", a)
            )
            self.function_edit_buttons[action] = edit
            clear = self._button("清除")
            clear.setMinimumHeight(22)
            clear.setFixedWidth(54)
            clear.clicked.connect(lambda checked=False, a=action: self._clear_function(a))
            actions = QHBoxLayout()
            actions.setSpacing(4)
            actions.addWidget(edit)
            actions.addWidget(clear)
            holder = QWidget()
            holder.setLayout(actions)
            grid.addWidget(holder, row, 2)

        return self._scroll(content)

    # -- state ----------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._paint_status_color()
        self.refresh()

    def refresh(self) -> None:
        for bar, label in self._note_key_labels.items():
            label.setText(self.bindings.keycap(bar))
        for bar, label in self._note_name_labels.items():
            label.setText(self.instrument.note_for_key(bar))
        for action, label in self._function_labels.items():
            label.setText(self._function_text(action))
        self.preset_label.setText(
            "三行顺序" if self.bindings.preset == "three_row" else "自定义"
        )
        conflicts = self.bindings.conflicts()
        if conflicts:
            self.conflict_label.setText(f"⚠ {len(conflicts)} 个冲突")
            self.conflict_label.setStyleSheet(f"color: {self._theme.danger.name()};")
            self.conflict_label.setToolTip("\n".join(conflicts))
        else:
            self.conflict_label.setText("无冲突")
            self.conflict_label.setStyleSheet("")

    def move_chip_focus(self, widget, key: int) -> bool:
        """Left/Right cycle focus across the two table tabs."""
        if key == int(Qt.Key.Key_Left):
            delta = -1
        elif key == int(Qt.Key.Key_Right):
            delta = 1
        else:
            return False
        if widget not in self._tab_buttons:
            return False
        enabled = [button for button in self._tab_buttons if button.isEnabled()]
        if widget not in enabled:
            return True
        index = enabled.index(widget)
        enabled[(index + delta) % len(enabled)].setFocus()
        return True

    def _function_text(self, action: str) -> str:
        chord = self.bindings.function_chord(action)
        return chord.text if chord is not None else "—"

    def _paint_status_color(self) -> None:
        if self._capture is not None:
            self.status.setStyleSheet(f"color: {self._theme.amber.name()};")
        else:
            self.status.setStyleSheet("")

    # -- capture API used by MainWindow ---------------------------------

    def is_capturing(self) -> bool:
        return self._capture is not None

    def cancel_capture(self, message: str = "已取消；键位未修改。") -> None:
        if self._capture is not None:
            self._cancel_capture(message)

    def start_capture(self, kind: str, ident: int | str) -> None:
        self._capture = (kind, ident)
        target = f"光条 {ident}" if kind == "note" else f"功能“{FUNCTION_LABELS[ident]}”"
        self.status.setText(f"请按下要绑定的键…（Esc 取消） · 目标：{target}")
        self._paint_status_color()
        self.capturingChanged.emit(True)
        self._stack.setFocus()

    def handle_capture(self, event) -> bool:
        if event.type() == QEvent.Type.KeyRelease:
            return True
        if event.type() != QEvent.Type.KeyPress or event.isAutoRepeat():
            return True
        assert self._capture is not None
        kind, ident = self._capture
        key = int(event.key())
        mods = int(event.modifiers().value)

        if key == int(Qt.Key.Key_Escape):
            self._cancel_capture("已取消；键位未修改。")
            return True
        if key in MODIFIER_KEYS and not (kind == "function" and ident == "sustain"):
            self.status.setText(
                "请再按一个字母 / 数字 / 符号键（单独的修饰键只能用于延音）。"
            )
            self._paint_status_color()
            return True

        if kind == "note":
            if mods & (MOD_CTRL | MOD_ALT | MOD_META):
                self.status.setText("音符键暂不支持 Ctrl / Alt / Win 组合；请重按，或 Esc 取消。")
                self._paint_status_color()
                return True
            chord = Chord(key, 0)
            conflicts = self.bindings.conflict_for_note(int(ident), chord)
        else:
            if key in MODIFIER_KEYS:
                mods = 0
            else:
                mods &= MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_META
            chord = Chord(key, mods)
            conflicts = self.bindings.conflict_for_function(str(ident), chord)

        if conflicts:
            if not self._ask_replace(conflicts):
                self._cancel_capture("已取消；键位未修改。")
                return True
            for _description, conflict_kind, conflict_id in conflicts:
                if conflict_kind == "note":
                    self.bindings.clear_note(int(conflict_id))
                else:
                    self.bindings.clear_function(str(conflict_id))

        if kind == "note":
            self.bindings.set_note(int(ident), chord)
            message = f"已绑定：光条 {ident} → {chord.text}"
        else:
            self.bindings.set_function(str(ident), chord)
            message = f"已绑定：功能“{FUNCTION_LABELS[ident]}” → {chord.text}"

        self._capture = None
        self.capturingChanged.emit(False)
        self.status.setText(message)
        self._paint_status_color()
        self.refresh()
        self.changed.emit()
        return True

    def _cancel_capture(self, message: str) -> None:
        self._capture = None
        self.capturingChanged.emit(False)
        self.status.setText(message)
        self._paint_status_color()

    def _switch_tab(self, index: int) -> None:
        self.cancel_capture()
        self._stack.setCurrentIndex(index)

    def _clear_note(self, bar: int) -> None:
        self.cancel_capture()
        self.bindings.clear_note(bar)
        self.status.setText(f"已清除光条 {bar} 的电脑键；仍可用实体琴弹。")
        self.refresh()
        self.changed.emit()

    def _clear_function(self, action: str) -> None:
        self.cancel_capture()
        self.bindings.clear_function(action)
        self.status.setText(f"已清除功能“{FUNCTION_LABELS[action]}”的按键。")
        self.refresh()
        self.changed.emit()

    def _ask_replace(self, conflicts: list[tuple[str, str, int | str]]) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("键位冲突")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "这个键已经绑定：\n"
            + "\n".join(f"· {description}" for description, _kind, _ident in conflicts)
        )
        box.setInformativeText("替换会清除上面的绑定。")
        replace = box.addButton("替换", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is replace

    # -- toolbar --------------------------------------------------------

    def _reset_defaults(self) -> None:
        self.cancel_capture()
        box = QMessageBox(self)
        box.setWindowTitle("恢复默认")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("恢复三行顺序默认会覆盖当前所有键位，确定吗？")
        reset = box.addButton("恢复默认", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not reset:
            return
        self.bindings.reset_defaults(save=True)
        self.status.setText("已恢复：三行顺序默认键位。")
        self.refresh()
        self.changed.emit()

    def _export(self) -> None:
        self.cancel_capture()
        path, _filter = QFileDialog.getSaveFileName(
            self, "导出键位方案", "keybindings.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self.bindings.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.status.setText(f"已导出：{path}")
        except OSError as exc:
            self.status.setText(f"导出失败：{exc}")

    def _import(self) -> None:
        self.cancel_capture()
        path, _filter = QFileDialog.getOpenFileName(
            self, "导入键位方案", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.status.setText(f"导入失败：{exc}")
            return
        if not self.bindings.apply_dict(data):
            self.status.setText("导入失败：文件格式不正确。")
            return
        self.bindings.save()
        self.status.setText(f"已导入：{path}")
        self.refresh()
        self.changed.emit()
