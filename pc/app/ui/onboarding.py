"""First-run onboarding wizard (A3).

Four short steps: connect/test, optional calibration, page map, first lesson.
Skipping or finishing writes onboarding.json (handled by MainWindow). The
dialog never blocks the app's tests because MainWindow only auto-opens it when
constructed with auto_onboarding=True.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.calibration import CalibrationProfile
from ..core.instrument import Instrument
from .help_page import PAGE_HELP
from .theme import Theme, set_scaled_font
from .widgets import CardFrame

STEP_TITLES = (
    "连接与试弹",
    "校准（可选）",
    "页面地图",
    "第一课",
)


class OnboardingDialog(QDialog):
    """The four-step wizard. ``outcome`` is one of completed/skipped/
    calibration/lesson, or "" when the dialog was not closed conclusively."""

    def __init__(
        self,
        theme: Theme,
        instrument: Instrument,
        calibration_path: str | Path | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._theme = theme
        self.instrument = instrument
        self.calibration_path = (
            Path(calibration_path) if calibration_path is not None else None
        )
        self.step_index = 0
        self.outcome = ""
        self.setWindowTitle("欢迎使用 KeyBorad")
        self.setModal(True)
        self.resize(760, 560)
        self.setStyleSheet(
            theme.qss() + f"\nQDialog {{ background: {theme.bg.name()}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)
        outer.addWidget(card)

        head = QHBoxLayout()
        badge = QLabel("首次使用 · KeyBorad")
        badge.setProperty("role", "amber")
        set_scaled_font(badge, theme, 10)
        self.step_label = QLabel("")
        self.step_label.setProperty("role", "faint")
        head.addWidget(badge)
        head.addStretch(1)
        head.addWidget(self.step_label)
        layout.addLayout(head)

        self.title = QLabel("")
        set_scaled_font(self.title, theme, 22, weight=QFont.Weight.DemiBold)
        layout.addWidget(self.title)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_connect())
        self.stack.addWidget(self._build_calibration())
        self.stack.addWidget(self._build_map())
        self.stack.addWidget(self._build_lesson())
        layout.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.skip_button = QPushButton("跳过")
        self.skip_button.setProperty("role", "chip")
        self.skip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.skip_button.clicked.connect(self.reject)
        footer.addWidget(self.skip_button)
        footer.addStretch(1)
        self.back_button = QPushButton("上一步")
        self.back_button.setProperty("role", "chip")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.back_button.clicked.connect(self.previous_step)
        footer.addWidget(self.back_button)
        self.next_button = QPushButton("下一步")
        self.next_button.setProperty("role", "action")
        self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.next_step)
        footer.addWidget(self.next_button)
        layout.addLayout(footer)

        self.instrument.stateChanged.connect(self._refresh_device)
        self._refresh_device()
        self._refresh_calibration()
        self._update_step()

    # -- steps ------------------------------------------------------------

    def _build_connect(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)
        self.device_label = QLabel("")
        self.device_label.setProperty("role", "muted")
        self.device_label.setWordWrap(True)
        layout.addWidget(self.device_label)
        hint = QLabel(
            "电脑键盘：Z X C… / A S D… / Q W E… 三行，"
            "中文输入法下仍按物理位置。Ctrl+Tab 可显示键帽。"
        )
        hint.setProperty("role", "faint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        refresh = QPushButton("重新检测")
        refresh.setProperty("role", "chip")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        refresh.clicked.connect(self._refresh_device)
        layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _build_calibration(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)
        self.calibration_label = QLabel("")
        self.calibration_label.setProperty("role", "muted")
        self.calibration_label.setWordWrap(True)
        layout.addWidget(self.calibration_label)
        hint = QLabel(
            "逐键阈值解决小拇指弱信号与多指齐按丢键；可以稍后从"
            " 设备 → 校准 进入。跳过不影响演奏。"
        )
        hint.setProperty("role", "faint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        go = QPushButton("去校准")
        go.setProperty("role", "chip")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        go.clicked.connect(self._go_calibration)
        layout.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _build_map(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(4)
        for name, text in PAGE_HELP:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(name)
            label.setProperty("role", "amber")
            label.setFixedWidth(48)
            set_scaled_font(label, self._theme, 10, weight=QFont.Weight.DemiBold)
            row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
            desc = QLabel(text)
            desc.setProperty("role", "muted")
            desc.setWordWrap(True)
            row.addWidget(desc, 1)
            layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_lesson(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)
        text = QLabel(
            "学习 → 阶段 0 →「找到中央 C」。弹 3 个音即可完成，"
            "之后可以继续学五线谱或直接演奏。"
        )
        text.setProperty("role", "muted")
        text.setWordWrap(True)
        layout.addWidget(text)
        go = QPushButton("打开阶段 0")
        go.setProperty("role", "action")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        go.clicked.connect(self._go_lesson)
        layout.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    # -- navigation -------------------------------------------------------

    def next_step(self) -> None:
        if self.step_index >= len(STEP_TITLES) - 1:
            self._finish()
            return
        self.step_index += 1
        self._update_step()

    def previous_step(self) -> None:
        if self.step_index == 0:
            return
        self.step_index -= 1
        self._update_step()

    def _update_step(self) -> None:
        self.stack.setCurrentIndex(self.step_index)
        self.title.setText(STEP_TITLES[self.step_index])
        self.step_label.setText(
            f"第 {self.step_index + 1} / {len(STEP_TITLES)} 步"
        )
        self.back_button.setEnabled(self.step_index > 0)
        self.next_button.setText(
            "完成" if self.step_index == len(STEP_TITLES) - 1 else "下一步"
        )

    def _finish(self) -> None:
        self.outcome = "completed"
        self.accept()

    def _go_calibration(self) -> None:
        self.outcome = "calibration"
        self.accept()

    def _go_lesson(self) -> None:
        self.outcome = "lesson"
        self.accept()

    def reject(self) -> None:
        if not self.outcome:
            self.outcome = "skipped"
        super().reject()

    # -- live status ------------------------------------------------------

    def _refresh_device(self) -> None:
        inst = self.instrument
        online = inst.module_count()
        if inst.connected and online >= 3:
            text = "已连接 · 3 个模块在线。可以按实体琴键试弹。"
        elif inst.connected:
            text = f"已连接 · {online}/3 模块在线。可以先用电脑键盘。"
        else:
            text = (
                "未检测到琴。你仍然可以用电脑键盘演奏："
                "Z X C… / A S D… / Q W E…。"
            )
        self.device_label.setText(text)

    def _refresh_calibration(self) -> None:
        profile = None
        if self.calibration_path is not None:
            profile, _warning = CalibrationProfile.load(self.calibration_path)
        if profile is not None and profile.is_complete():
            name = profile.name or "未命名"
            self.calibration_label.setText(
                f"已保存方案 · {name} · {profile.created_at[:10] or '—'}"
            )
        else:
            self.calibration_label.setText(
                "当前未校准。建议先做一次逐键校准；也可以先跳过。"
            )
