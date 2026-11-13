"""Help page (A3): a functional index, not a marketing page.

Seven page sections, a live key map, function-key chords and troubleshooting.
Entries are one or two lines and tell the user what to press or click.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..core.instrument import Instrument
from .keybindings import FUNCTION_LABELS, KeyBindings
from .keyboard_layout import KEY_ROWS
from .learning_page import scroll_area
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame

PAGE_HELP = (
    (
        "演奏",
        "Space 示范 / Esc 停止 / Ctrl+M 映射 / Ctrl+P 音色；"
        "Shift 延音，[ / ] 八度。",
    ),
    (
        "学习",
        "阶段卡 → 指导书 → 去练习；点「返回学习」回到原阶段或课次。",
    ),
    (
        "曲库",
        "搜索、筛选、导入 MusicXML/MIDI/图片；★ 收藏；图片与 PDF 只显示。",
    ),
    (
        "创作",
        "录音/叠录/循环、最多 8 轨、混音、节拍器、导出 MIDI。",
    ),
    (
        "设备",
        "3 个 MPR121 在线状态；「打开校准页」做逐键阈值；重新检测。",
    ),
    (
        "设置",
        "主题、语言、字号、减少动效；「键位设置」改音符键与功能键。",
    ),
    (
        "帮助",
        "本页：快速开始、页面按钮、键位图、故障排查、重开向导。",
    ),
)

QUICK_START = (
    "连接：插上 USB，应用自动识别 ESP32-S3；状态条显示 3 个模块在线。",
    "发声：实体琴键与电脑键盘进入同一个 20 ms 引擎；顶栏有 48 kHz 即可出声。",
    "电脑键盘：Z X C… / A S D… / Q W E… 三行；Ctrl+Tab 显示当前键帽。",
    "中央 C：学习 → 阶段 0 →「找到中央 C」会把键位临时映射到 C4 起。",
)

TROUBLE = (
    "没声音：看顶栏是否 48 kHz；先关闭 PlatformIO 串口监视器；--no-audio 会静音。",
    "没设备：状态条显示「等待设备」；仍可用电脑键盘；确认 COM 口未被占用。",
    "按键无反应：中文输入法下仍按物理位置；多键无冲时优先用实体琴。",
    "谱面不跟随：确认曲目可跟弹（不是图片/PDF）；按 Space 开始示范。",
    "校准后仍丢键：设备 → 校准，用「多指验证」重按和弦；弱键单独调阈值。",
    "按键卡住：Esc 全部静音并松开所有键；必要时重新插拔设备。",
)


class HelpPage(GlassFrame):
    onboardingRequested = Signal()
    calibrationRequested = Signal()
    keybindingsRequested = Signal()

    def __init__(
        self,
        theme: Theme,
        instrument: Instrument,
        bindings: KeyBindings,
    ):
        super().__init__()
        self._theme = theme
        self.instrument = instrument
        self.bindings = bindings
        self.page_titles = tuple(title for title, _text in PAGE_HELP)
        self.key_labels: dict[int, QLabel] = {}
        self.function_labels: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 26)
        outer.setSpacing(8)

        header = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        badge = QLabel("帮助")
        badge.setProperty("role", "amber")
        set_scaled_font(badge, theme, 11)
        heading = QLabel("怎么用")
        set_scaled_font(heading, theme, 24, weight=QFont.Weight.DemiBold)
        sub = QLabel(
            "按页面查找按钮说明；每条 1–2 行，照着做即可。"
        )
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        left.addWidget(badge)
        left.addWidget(heading)
        left.addWidget(sub)
        header.addLayout(left, 1)
        self.keymap_button = QPushButton("看键位图")
        self.keymap_button.setProperty("role", "chip")
        self.keymap_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keymap_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.keymap_button.clicked.connect(
            lambda checked=False: self.scroll.ensureWidgetVisible(
                self.keymap_card
            )
        )
        header.addWidget(self.keymap_button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        self.scroll, content = scroll_area()
        self.scroll.setParent(self)
        outer.addWidget(self.scroll, 1)

        self._card(content, "快速开始", QUICK_START)

        pages = CardFrame()
        pages_layout = QVBoxLayout(pages)
        pages_layout.setContentsMargins(14, 12, 14, 12)
        pages_layout.setSpacing(6)
        title = QLabel("页面与按钮")
        set_scaled_font(title, theme, 13, weight=QFont.Weight.DemiBold)
        pages_layout.addWidget(title)
        for name, text in PAGE_HELP:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(name)
            label.setProperty("role", "amber")
            label.setFixedWidth(48)
            set_scaled_font(label, theme, 11, weight=QFont.Weight.DemiBold)
            row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
            description = QLabel(text)
            description.setProperty("role", "muted")
            description.setWordWrap(True)
            row.addWidget(description, 1)
            pages_layout.addLayout(row)
        content.addWidget(pages)

        self.keymap_card = self._build_keymap(content)
        self._build_functions(content)
        self._card(content, "故障排查", TROUBLE)
        self._build_actions(content)
        content.addStretch(1)
        self.refresh()

    # -- construction helpers --------------------------------------------

    def _card(
        self, parent_layout: QVBoxLayout, title: str, rows: tuple[str, ...]
    ) -> CardFrame:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        heading = QLabel(title)
        set_scaled_font(heading, self._theme, 13, weight=QFont.Weight.DemiBold)
        layout.addWidget(heading)
        for text in rows:
            row = QLabel(f"·  {text}")
            row.setProperty("role", "muted")
            row.setWordWrap(True)
            layout.addWidget(row)
        parent_layout.addWidget(card)
        return card

    def _build_keymap(self, parent_layout: QVBoxLayout) -> CardFrame:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        heading = QLabel("键位图")
        set_scaled_font(heading, self._theme, 13, weight=QFont.Weight.DemiBold)
        layout.addWidget(heading)
        hint = QLabel("键帽可改；点击 设置 → 键位设置。光条号 1–32 与琴键对应。")
        hint.setProperty("role", "faint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        rows = QVBoxLayout()
        rows.setSpacing(4)
        for start, end in KEY_ROWS:
            row = QHBoxLayout()
            row.setSpacing(4)
            for bar in range(start + 1, end + 1):
                cell = QLabel()
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setProperty("role", "muted")
                cell.setFixedHeight(44)
                cell.setMinimumWidth(40)
                cell.setToolTip(f"光条 {bar}")
                set_scaled_font(cell, self._theme, 9, mono=True)
                row.addWidget(cell)
                self.key_labels[bar] = cell
            row.addStretch(1)
            rows.addLayout(row)
        layout.addLayout(rows)
        parent_layout.addWidget(card)
        return card

    def _build_functions(self, parent_layout: QVBoxLayout) -> None:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        heading = QLabel("功能键")
        set_scaled_font(heading, self._theme, 13, weight=QFont.Weight.DemiBold)
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(3)
        for index, (action, label) in enumerate(FUNCTION_LABELS.items()):
            text = QLabel()
            text.setProperty("role", "muted")
            text.setWordWrap(True)
            set_scaled_font(text, self._theme, 9, mono=True)
            grid.addWidget(text, index // 3, index % 3)
            self.function_labels[action] = text
            text.setToolTip(label)
        layout.addLayout(grid)
        parent_layout.addWidget(card)

    def _build_actions(self, parent_layout: QVBoxLayout) -> None:
        card = CardFrame()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        for text, signal in (
            ("重新打开首启向导", self.onboardingRequested),
            ("去校准", self.calibrationRequested),
            ("键位设置", self.keybindingsRequested),
        ):
            button = QPushButton(text)
            button.setProperty("role", "chip")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(
                lambda checked=False, sig=signal: sig.emit()
            )
            layout.addWidget(button)
        layout.addStretch(1)
        parent_layout.addWidget(card)

    # -- updates ----------------------------------------------------------

    def refresh(self) -> None:
        for bar, label in self.key_labels.items():
            note = self.instrument.note_for_key(bar)
            label.setText(f"{self.bindings.keycap(bar)}\n{note}")
            label.setToolTip(f"光条 {bar} · {note}")
        for action, label in self.function_labels.items():
            chord = self.bindings.function_chord(action)
            label.setText(
                f"{chord.text if chord is not None else '—'}  "
                f"{FUNCTION_LABELS[action]}"
            )

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.refresh()
