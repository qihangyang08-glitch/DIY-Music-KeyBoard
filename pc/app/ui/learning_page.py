"""The 学习 page: overview first, then a stage, then a full-page guide.

Structure chosen from the P3 prototype (variant C, adjusted):

- opening 学习 shows the whole 9-stage path and a prominent "继续上次";
- clicking a stage replaces the page with that stage's full content;
- clicking a guide opens a full-page course view;
- practice buttons hand off to the real 演奏 page with the score loaded and a
  "返回学习" chip, and come back to the same stage/course.

Learning state lives in LearningProgress and is written only when the user
actually opens or practices something. A user who never touches 学习 sees the
rest of the app exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.curriculum import (
    BANDS,
    SCORE_DIR,
    STAGES,
    Guide,
    PracticeItem,
    Stage,
    lesson_ref_label,
    stage_by_index,
)
from ..core.lesson import KnowledgeCard
from ..core.mapping import MappingSpec
from ..core.drill import DrillTarget, drill_spec
from ..core.exam import exam_spec
from ..core.progress import LearningProgress
from ..core.score import ScoreError, excerpt_score, parse_score
from .score_view import ScoreCanvas
from .theme import Theme, set_scaled_font
from .widgets import CardFrame, GlassFrame

STATUS_TEXT = {
    "ready": ("可开始", "amber"),
    "partial": ("部分就绪", "muted"),
    "wip": ("制作中", "faint"),
    "done": ("✓ 已完成", "amber"),
    "done_partial": ("✓ 可练内容完成", "amber"),
}


@dataclass(frozen=True)
class PracticeTarget:
    stage_index: int
    item_name: str
    score: str | None
    origin_view: str
    guide_title: str = ""
    accompaniment: str = ""  # MusicXML part the synth plays (H7e)
    mapping: str | MappingSpec = ""  # preset key or structured mapping (H7f)


@dataclass(frozen=True)
class ExamTarget:
    stage_index: int
    exam_key: str
    origin_view: str
    guide_title: str = ""


@dataclass(frozen=True)
class ProjectTarget:
    stage_index: int
    item_name: str
    project: str
    task: object
    origin_view: str
    guide_title: str = ""


class ClickFrame(CardFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        # Cards are not buttons, so the window-wide Enter/Space rule does not
        # see them. Activate the same action the mouse click would.
        if event.key() in (
            int(Qt.Key.Key_Return),
            int(Qt.Key.Key_Enter),
            int(Qt.Key.Key_Space),
        ):
            event.accept()
            self.clicked.emit()
            return
        super().keyPressEvent(event)


class ProgressBar(QWidget):
    def __init__(self, theme: Theme, value: float = 0.0, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._value = max(0.0, min(1.0, value))
        self.setFixedHeight(4)
        self.setMinimumWidth(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        p.setBrush(QColor(self._theme.hair))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        if self._value > 0:
            fill = max(h, w * self._value)
            p.setBrush(QColor(self._theme.amber))
            p.drawRoundedRect(QRectF(0, 0, fill, h), h / 2, h / 2)
        p.end()


def hline() -> QFrame:
    line = QFrame()
    line.setProperty("hair", True)
    line.setFixedHeight(1)
    return line


def section(theme: Theme, text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "label")
    set_scaled_font(label, theme, 9, QFont.Weight.DemiBold)
    return label


def status_label(theme: Theme, stage: Stage, completed: bool = False) -> QLabel:
    if completed:
        # A stage with unfinished content can only claim its *ready* items are
        # done. Saying "✓ 已完成" would overstate what exists.
        key = "done" if stage.ready_count == stage.total_count else "done_partial"
    else:
        key = stage.status
    text, role = STATUS_TEXT[key]
    label = QLabel(text)
    label.setProperty("role", role)
    set_scaled_font(label, theme, 10, QFont.Weight.DemiBold)
    return label


def is_drill_result(result) -> bool:
    return result is not None and (result.avg_ms > 0 or result.first_try > 0)


def result_extra(result) -> str:
    """First-try / timing / streak suffix for drills (empty for scores)."""
    parts: list[str] = []
    if result is not None and result.first_try > 0:
        parts.append(f"首答 {result.first_try}/{result.total}")
    if result is not None and result.avg_ms > 0:
        if result.avg_ms >= 1000:
            parts.append(f"平均 {result.avg_ms / 1000:.1f}s")
        else:
            parts.append(f"平均 {result.avg_ms}ms")
    if result is not None and result.best_streak > 0:
        parts.append(f"连对 {result.best_streak}")
    return (" · " + " · ".join(parts)) if parts else ""


def result_line(result) -> tuple[str, str] | None:
    """Row text + role for a stored result, with drill-specific wording.

    Partial drills deliberately do not show the press-accuracy percentage: a
    3/10 partial run with no wrong presses would read "100%" and hide that
    seven questions were never asked. Solved/total and first-try/total carry
    the honest information.
    """
    if result is None:
        return None
    extra = result_extra(result)
    if is_drill_result(result):
        if result.completed:
            return (
                f"✓ 已完成 · 最佳 {result.hits}/{result.total}"
                f" · 错误 {result.misses} · 准确率 {result.accuracy}%{extra}",
                "amber",
            )
        return (
            f"已练 {result.hits}/{result.total}"
            f" · 错误 {result.misses}{extra}",
            "faint",
        )
    if result.completed:
        return (
            f"✓ 已完成 · 最佳 {result.hits}/{result.total}"
            f" · 未中 {result.misses} · {result.accuracy}%",
            "amber",
        )
    return (
        f"最佳 {result.hits}/{result.total}"
        f" · 未中 {result.misses} · {result.accuracy}%",
        "faint",
    )


def counts_text(stage: Stage) -> str:
    return f"训练 {sum(1 for i in stage.trainings if i.ready)}/{len(stage.trainings)}" + (
        f" · 曲目 {sum(1 for i in stage.pieces if i.ready)}/{len(stage.pieces)}"
        if stage.pieces
        else ""
    )


def scroll_area() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    # These pages are designed to fit the minimum window width; a stray
    # 1 px rounding difference on another font/DPI must not add a bar.
    scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    content = QWidget()
    content.setObjectName("ScrollContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(2, 2, 6, 8)
    layout.setSpacing(10)
    scroll.setWidget(content)
    return scroll, layout


def resolve_score_asset(asset: str) -> Path | None:
    """Find a lesson score by absolute path, bare id, or packaged path."""
    text = asset.strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return path
    name = path.name
    stem = Path(name).stem
    for filename in (
        name,
        f"{stem}.musicxml",
        f"{stem}.xml",
        f"{stem}.mid",
        f"{stem}.midi",
    ):
        candidate = SCORE_DIR / filename
        if candidate.is_file():
            return candidate
    return None


def resolve_image_asset(asset: str) -> Path | None:
    """Find a lesson figure by absolute path or under ``resources/``."""
    text = asset.strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return path
    if path.is_absolute():
        return None
    resource_dir = SCORE_DIR.parent
    for candidate in (
        resource_dir / text,
        resource_dir / "images" / path.name,
    ):
        if candidate.is_file():
            return candidate
    return None


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class StageCard(ClickFrame):
    def __init__(
        self,
        theme: Theme,
        stage: Stage,
        last: bool,
        completed: bool,
        done: int,
        on_click,
    ):
        super().__init__()
        self._theme = theme
        self.stage = stage
        self.setMinimumHeight(96)
        self.setMinimumWidth(176)
        self.clicked.connect(on_click)
        ready = max(1, stage.ready_count)
        self.setToolTip(f"可练内容完成 {done}/{stage.ready_count}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        index = QLabel(f"{stage.index:02d}")
        index.setProperty("role", "amber" if last else "faint")
        set_scaled_font(index, self._theme, 9, QFont.Weight.DemiBold, mono=True)
        name = QLabel(stage.name)
        set_scaled_font(name, self._theme, 12, QFont.Weight.DemiBold)
        head.addWidget(index)
        head.addWidget(name, 1)
        if last:
            mark = QLabel("上次")
            mark.setProperty("role", "amber")
            set_scaled_font(mark, self._theme, 9, QFont.Weight.DemiBold)
            head.addWidget(mark)
        lay.addLayout(head)

        row = QHBoxLayout()
        row.addWidget(status_label(theme, stage, completed))
        row.addStretch(1)
        counts = QLabel(counts_text(stage))
        counts.setProperty("role", "faint")
        set_scaled_font(counts, self._theme, 9, mono=True)
        row.addWidget(counts)
        lay.addLayout(row)
        lay.addStretch(1)
        # Completion of what can actually be practised, not content coverage:
        # a stage with one ready item shows a full bar once that item is done,
        # while the "训练 1/4" count still tells the truth about content.
        lay.addWidget(ProgressBar(theme, done / ready))


class OverviewView(QWidget):
    """The whole path at a glance, plus where the user left off."""

    def __init__(self, page: "LearningPage"):
        super().__init__()
        self._page = page
        self._theme = page.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("学习")
        set_scaled_font(title, self._theme, 22, QFont.Weight.DemiBold)
        head.addWidget(title)
        sub = QLabel("9 个阶段：基础 → 演奏 → 创作。先看全貌，再选一课。")
        sub.setProperty("role", "muted")
        head.addWidget(sub)
        head.addStretch(1)
        direct = QLabel("不学也可以直接演奏 / 创作")
        direct.setProperty("role", "faint")
        head.addWidget(direct)
        outer.addLayout(head)

        self._continue = GlassFrame()
        self._continue_lay = QHBoxLayout(self._continue)
        self._continue_lay.setContentsMargins(16, 11, 16, 11)
        self._continue_lay.setSpacing(12)
        outer.addWidget(self._continue)

        scroll, self._path = scroll_area()
        outer.addWidget(scroll, 1)
        self.render()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.render()

    def render(self) -> None:
        progress = self._page.progress
        clear_layout(self._continue_lay)
        left = QVBoxLayout()
        left.setSpacing(2)
        caption = QLabel("继续上次" if progress.last_stage is not None else "从这里开始")
        caption.setProperty("role", "label")
        left.addWidget(caption)

        if progress.last_stage is not None:
            stage = stage_by_index(progress.last_stage)
            if progress.last_item:
                heading = f"阶段 {stage.index} · {progress.last_item}"
            elif progress.last_view == "course" and progress.last_guide:
                heading = f"阶段 {stage.index} · {progress.last_guide}"
            else:
                heading = f"阶段 {stage.index} · {stage.name}"
            title = QLabel(heading)
            set_scaled_font(title, self._theme, 15, QFont.Weight.DemiBold)
            result = (
                progress.result_for(progress.last_stage, progress.last_item)
                if progress.last_item
                else None
            )
            if result is not None:
                meta_text = (
                    f"正确 {result.hits}/{result.total} · 错误 {result.misses}"
                    f" · {result.accuracy}% · {progress.relative_time()}"
                )
            else:
                meta_text = " · ".join(
                    part for part in (progress.relative_time(), "本地学习档案") if part
                )
            button_text = "继续"
        else:
            stage = stage_by_index(0)
            title = QLabel("阶段 0 · 上手")
            set_scaled_font(title, self._theme, 15, QFont.Weight.DemiBold)
            meta_text = "还没有学习记录 · 先弹出第一个音"
            button_text = "开始"
        meta = QLabel(meta_text)
        meta.setProperty("role", "faint")
        left.addWidget(title)
        left.addWidget(meta)
        self._continue_lay.addLayout(left, 1)

        go = QPushButton(button_text)
        go.setProperty("role", "action")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        go.clicked.connect(self._page.continue_last)
        self._continue_lay.addWidget(go)

        clear_layout(self._path)
        for band in BANDS:
            stages = [s for s in STAGES if s.band == band]
            band_head = QHBoxLayout()
            label = QLabel(band)
            label.setProperty("role", "label")
            set_scaled_font(label, self._theme, 10, QFont.Weight.DemiBold)
            band_head.addWidget(label)
            line = hline()
            band_head.addWidget(line, 1)
            span = QLabel(f"阶段 {stages[0].index}–{stages[-1].index}")
            span.setProperty("role", "faint")
            set_scaled_font(span, self._theme, 9, mono=True)
            band_head.addWidget(span)
            self._path.addLayout(band_head)

            # Uniform four columns across every band, so stage cards line up
            # and the shorter 创作 band is not stretched to giant tiles.
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for column in range(4):
                grid.setColumnStretch(column, 1)
            for column, stage in enumerate(stages):
                done = 0
                for item in stage.ready_items:
                    result = progress.result_for(stage.index, item.name)
                    if result is not None and result.completed:
                        done += 1
                card = StageCard(
                    self._theme,
                    stage,
                    progress.last_stage == stage.index,
                    self._page.stage_done(stage),
                    done,
                    lambda s=stage: self._page.open_stage(s.index),
                )
                grid.addWidget(card, 0, column)
            for column in range(len(stages), 4):
                spacer = QWidget()
                spacer.setMinimumWidth(176)
                grid.addWidget(spacer, 0, column)
            self._path.addLayout(grid)

        ready_pairs = [(s, item) for s in STAGES for item in s.ready_items]
        done = 0
        for stage_item, item in ready_pairs:
            result = progress.result_for(stage_item.index, item.name)
            if result is not None and result.completed:
                done += 1
        note = QLabel(
            f"可练习项目 {done}/{len(ready_pairs)} 已完成 · "
            "只把已有谱面、训练生成器或可用项目模板的内容标为可练习；"
            "其余显示“制作中”，不伪装成可跟弹。"
        )
        note.setProperty("role", "faint")
        note.setWordWrap(True)
        self._path.addWidget(note)
        self._path.addStretch(1)


class StageView(QWidget):
    def __init__(self, page: "LearningPage"):
        super().__init__()
        self._page = page
        self._theme = page.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll, self._body = scroll_area()
        outer.addWidget(scroll)
        self._stage: Stage | None = None

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._stage is not None:
            self.set_stage(self._stage)

    def set_stage(self, stage: Stage) -> None:
        self._stage = stage
        progress = self._page.progress
        clear_layout(self._body)

        head = QHBoxLayout()
        back = QPushButton("← 学习路线")
        back.setProperty("role", "chip")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        back.clicked.connect(self._page.show_overview)
        head.addWidget(back)
        index = QLabel(f"{stage.index:02d}")
        index.setProperty("role", "amber")
        set_scaled_font(index, self._theme, 12, QFont.Weight.DemiBold, mono=True)
        title = QLabel(stage.name)
        set_scaled_font(title, self._theme, 20, QFont.Weight.DemiBold)
        head.addWidget(index)
        head.addWidget(title)
        head.addWidget(
            status_label(self._theme, stage, self._page.stage_done(stage))
        )
        head.addStretch(1)
        counts = QLabel(counts_text(stage))
        counts.setProperty("role", "faint")
        set_scaled_font(counts, self._theme, 10, mono=True)
        head.addWidget(counts)
        self._body.addLayout(head)

        goal = QLabel(stage.goal)
        goal.setProperty("role", "muted")
        goal.setWordWrap(True)
        self._body.addWidget(goal)
        pre = QLabel(f"前置 · {stage.prereq}")
        pre.setProperty("role", "faint")
        self._body.addWidget(pre)

        self._body.addSpacing(4)
        self._body.addWidget(section(self._theme, "指导书 · 点开看整页"))
        guides = QHBoxLayout()
        guides.setSpacing(8)
        for guide in stage.guides:
            card = ClickFrame()
            card.clicked.connect(
                lambda g=guide: self._page.open_course(g.title)
            )
            lay = QVBoxLayout(card)
            lay.setContentsMargins(12, 9, 12, 9)
            lay.setSpacing(3)
            title_label = QLabel(guide.title)
            set_scaled_font(title_label, self._theme, 12, QFont.Weight.DemiBold)
            title_label.setWordWrap(True)
            meta = QLabel(
                f"约 {guide.minutes} 分钟 · "
                + ("打开 →" if guide.is_ready() else "正文制作中")
            )
            meta.setProperty("role", "faint")
            lay.addWidget(title_label)
            lay.addWidget(meta)
            lay.addStretch(1)
            guides.addWidget(card, 1)
        self._body.addLayout(guides)

        self._body.addSpacing(4)
        self._body.addWidget(section(self._theme, "训练"))
        for item in stage.trainings:
            self._body.addWidget(self._item_row(stage, item))
        if not stage.trainings:
            empty = QLabel("内容制作中")
            empty.setProperty("role", "faint")
            self._body.addWidget(empty)

        self._body.addSpacing(4)
        self._body.addWidget(section(self._theme, "曲目"))
        if stage.pieces:
            for item in stage.pieces:
                self._body.addWidget(self._item_row(stage, item))
        else:
            note = QLabel("阶段 0–2 以训练代替完整曲目；训练即通关内容。")
            note.setProperty("role", "faint")
            self._body.addWidget(note)

        exam = exam_spec(stage.index)
        if exam is not None:
            self._body.addSpacing(4)
            self._body.addWidget(section(self._theme, "考核 · 可选，不影响普通练习"))
            self._body.addWidget(self._exam_row(stage, exam, progress))

        self._body.addSpacing(4)
        self._body.addWidget(section(self._theme, "通关标准"))
        rule = QLabel(stage.pass_rule)
        rule.setProperty("role", "muted")
        rule.setWordWrap(True)
        self._body.addWidget(rule)

        actions = QHBoxLayout()
        if stage.index + 1 < len(STAGES):
            nxt = QPushButton(f"下一步 · {stage.next_step}")
            nxt.setProperty("role", "chip")
            nxt.setCursor(Qt.CursorShape.PointingHandCursor)
            nxt.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            nxt.clicked.connect(
                lambda: self._page.open_stage(stage.index + 1)
            )
            actions.addWidget(nxt)
        actions.addStretch(1)
        self._body.addLayout(actions)
        self._body.addStretch(1)

    def _item_row(self, stage: Stage, item: PracticeItem) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(8)
        dot = QLabel("●" if item.ready else "○")
        dot.setProperty("role", "amber" if item.ready else "faint")
        dot.setFixedWidth(12)
        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(item.name)
        name.setProperty("role", "muted" if item.ready else "faint")
        meta = QLabel(item.meta)
        meta.setProperty("role", "faint")
        set_scaled_font(meta, self._theme, 9)
        text.addWidget(name)
        text.addWidget(meta)
        result = self._page.progress.result_for(stage.index, item.name)
        line = result_line(result)
        if line is not None:
            text_value, role = line
            record = QLabel(text_value)
            record.setProperty("role", role)
            set_scaled_font(record, self._theme, 9)
            record.setWordWrap(True)
            text.addWidget(record)
        lay.addWidget(dot)
        lay.addLayout(text, 1)
        if item.ready:
            label = "开始训练" if item.drill else ("打开项目" if item.project else "去练习")
            go = QPushButton(label)
            go.setProperty("role", "chip")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            go.clicked.connect(lambda: self._page.practice(stage, item))
            lay.addWidget(go)
        else:
            waiting = QLabel("制作中")
            waiting.setProperty("role", "faint")
            lay.addWidget(waiting)
        return row

    def _exam_row(self, stage: Stage, exam, progress: LearningProgress) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(8)
        dot = QLabel("●")
        dot.setProperty("role", "amber")
        dot.setFixedWidth(12)
        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel(exam.title)
        title.setProperty("role", "muted")
        criteria = QLabel(exam.criteria)
        criteria.setProperty("role", "faint")
        set_scaled_font(criteria, self._theme, 9)
        record = progress.exam_for(exam.key)
        status = QLabel(
            record.status_text if record is not None else "未参加 · 随时可以试一次"
        )
        status.setProperty(
            "role",
            "amber" if record is not None and record.passed
            else ("muted" if record is not None else "faint"),
        )
        set_scaled_font(status, self._theme, 9)
        status.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(criteria)
        text.addWidget(status)
        lay.addWidget(dot)
        lay.addLayout(text, 1)
        go = QPushButton("重新考核" if record is not None else "参加考核")
        go.setProperty("role", "chip")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        go.clicked.connect(lambda: self._page.start_exam(stage))
        lay.addWidget(go)
        return row


class CourseView(QWidget):
    def __init__(self, page: "LearningPage"):
        super().__init__()
        self._page = page
        self._theme = page.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll, self._body = scroll_area()
        outer.addWidget(scroll)
        self._stage: Stage | None = None
        self._guide: Guide | None = None
        self.item: PracticeItem | None = None
        self._step_progress: QLabel | None = None

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._stage is not None and self._guide is not None:
            self.set_course(self._stage, self._guide)

    def set_course(self, stage: Stage, guide: Guide) -> None:
        self._stage = stage
        self._guide = guide
        self._step_progress = None
        clear_layout(self._body)

        self._add_header(stage, guide)
        title = QLabel(guide.title)
        set_scaled_font(title, self._theme, 22, QFont.Weight.DemiBold)
        self._body.addWidget(title)
        self._body.addWidget(hline())

        item = self._practice_item(stage, guide)
        if item is None and not guide.is_ready():
            # Legacy placeholder pages keep the stage's first practice. A
            # finished lesson must not silently borrow an unrelated drill.
            item = stage.first_practice()
        self.item = item
        if guide.is_ready():
            self._render_ready(guide)
        else:
            self._render_planned(stage, guide, item)
        self._add_result(stage, item)
        self._add_action(stage, item, guide)
        self._body.addStretch(1)

    def _add_header(self, stage: Stage, guide: Guide) -> None:
        head = QHBoxLayout()
        back = QPushButton(f"← 阶段 {stage.index} · {stage.name}")
        back.setProperty("role", "chip")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        back.clicked.connect(lambda: self._page.open_stage(stage.index))
        head.addWidget(back)
        head.addStretch(1)
        meta = QLabel(f"指导书 · 约 {guide.minutes} 分钟")
        meta.setProperty("role", "faint")
        head.addWidget(meta)
        self._body.addLayout(head)

    @staticmethod
    def _practice_item(stage: Stage, guide: Guide) -> PracticeItem | None:
        """The lesson's own practice, never silently another lesson's."""
        if not guide.practice:
            return None
        for item in stage.items:
            if item.name == guide.practice:
                return item
        return None

    def _add_bullet(self, text: str, marker: str = "·") -> None:
        row = QHBoxLayout()
        dot = QLabel(marker)
        dot.setProperty("role", "amber")
        label = QLabel(text)
        label.setProperty("role", "muted")
        label.setWordWrap(True)
        row.addWidget(dot)
        row.addWidget(label, 1)
        self._body.addLayout(row)

    def _add_text(self, text: str, role: str = "muted") -> None:
        label = QLabel(text)
        label.setProperty("role", role)
        label.setWordWrap(True)
        self._body.addWidget(label)

    def _add_image_card(self, card: KnowledgeCard) -> None:
        path = resolve_image_asset(card.asset)
        if path is None:
            self._add_text(f"图示未找到 · {card.title}", "faint")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._add_text(f"图示载入失败 · {card.title}", "faint")
            return
        if pixmap.width() > 560:
            pixmap = pixmap.scaledToWidth(
                560, Qt.TransformationMode.SmoothTransformation
            )
        figure = QLabel()
        figure.setProperty("role", "figure")
        figure.setPixmap(pixmap)
        figure.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        figure.setAccessibleName(card.body or card.title)
        self._body.addWidget(figure)

    def _add_score_card(self, card: KnowledgeCard) -> None:
        """Draw a staff/roll snippet from the packaged score library."""
        path = resolve_score_asset(card.asset)
        if path is None:
            self._add_text(f"谱例未找到 · {card.title}", "faint")
            return
        try:
            score = parse_score(path)
        except (OSError, ValueError, ScoreError):
            self._add_text(f"谱例载入失败 · {card.title}", "faint")
            return
        snippet = excerpt_score(score, 4)
        if not snippet.notes:
            self._add_text(f"谱例没有音符 · {card.title}", "faint")
            return
        canvas = ScoreCanvas(self._theme)
        canvas.set_score(snippet)
        # A static snippet has no follow session: no next-note highlight or
        # playhead that would look like playback is running.
        canvas.set_follow_state(0.0, 0, 0, 0, False, None)
        canvas.set_mode("sheet" if card.kind == "staff" else "roll")
        canvas.setMinimumHeight(0)
        canvas.setFixedHeight(240)
        canvas.setAccessibleName(card.body or card.title)
        self._body.addWidget(canvas)

    @staticmethod
    def _guide_key(guide: Guide) -> str:
        return guide.lesson_id or guide.title

    def _add_step(self, guide: Guide, index: int, text: str) -> None:
        done = self._page.progress.guide_steps_for(
            self._stage.index, self._guide_key(guide)
        )
        checked = index in done
        box = QCheckBox(("✓ " if checked else "") + text)
        box.setProperty("stepText", text)
        box.setChecked(checked)
        box.setCursor(Qt.CursorShape.PointingHandCursor)
        box.toggled.connect(
            lambda is_checked, step_index=index, widget=box: self._on_step_toggled(
                step_index, is_checked, widget
            )
        )
        self._body.addWidget(box)

    def _on_step_toggled(self, index: int, checked: bool, box: QCheckBox) -> None:
        if self._stage is None or self._guide is None:
            return
        raw = str(box.property("stepText") or box.text())
        box.setText(("✓ " if checked else "") + raw)
        self._page.progress.set_guide_step(
            self._stage.index, self._guide_key(self._guide), index, checked
        )
        self._update_step_progress(self._guide)

    def _update_step_progress(self, guide: Guide) -> None:
        if self._step_progress is None:
            return
        done = self._page.progress.guide_steps_for(
            self._stage.index, self._guide_key(guide)
        )
        valid = {index for index in done if 0 <= index < len(guide.steps)}
        self._step_progress.setText(
            f"已勾选 {len(valid)}/{len(guide.steps)}"
        )

    def _render_ready(self, guide: Guide) -> None:
        self._body.addWidget(section(self._theme, "目标"))
        for objective in guide.objectives:
            self._add_bullet(objective)
        if guide.prereq:
            self._body.addWidget(section(self._theme, "先修"))
            prereq = "、".join(
                lesson_ref_label(part)
                for part in guide.prereq.split("、")
                if part.strip()
            )
            self._add_text(prereq, "faint")
        self._body.addWidget(section(self._theme, "知识"))
        for card in guide.cards:
            card_title = QLabel(card.title)
            set_scaled_font(card_title, self._theme, 12, QFont.Weight.DemiBold)
            card_title.setWordWrap(True)
            self._body.addWidget(card_title)
            if card.kind in ("staff", "roll"):
                self._add_score_card(card)
            elif card.kind == "image":
                self._add_image_card(card)
            elif card.body:
                self._add_text(card.body)
            if card.kind in ("staff", "roll", "image") and card.body:
                # The alt text stays visible as a small caption under the
                # figure, and is also exposed as the widget's accessible name.
                self._add_text(card.body, "faint")
            elif card.asset:
                self._add_text(f"素材 · {card.asset}", "faint")
        if guide.demonstration:
            self._body.addWidget(section(self._theme, "示范"))
            self._add_text(guide.demonstration)
            # The playable demo button is a later batch; do not show a raw
            # asset id that looks like a working control.
        if guide.steps:
            self._body.addWidget(section(self._theme, "练习"))
            for index, step in enumerate(guide.steps):
                self._add_step(guide, index, step)
            self._step_progress = QLabel()
            self._step_progress.setProperty("role", "faint")
            set_scaled_font(self._step_progress, self._theme, 9)
            self._body.addWidget(self._step_progress)
            self._update_step_progress(guide)
        if guide.mistakes:
            self._body.addWidget(section(self._theme, "常见错误"))
            for mistake in guide.mistakes:
                self._add_bullet(mistake)
        if guide.self_check:
            self._body.addWidget(section(self._theme, "检查"))
            for question in guide.self_check:
                self._add_bullet(question, marker="□")
        if guide.next_step:
            self._body.addWidget(section(self._theme, "下一步"))
            raw_next = guide.next_step
            label = lesson_ref_label(raw_next)
            if label != raw_next:
                prefix = "下一课 · " if "-l" in raw_next else "下一阶段 · "
                label = prefix + label
            self._add_text(label, "faint")

    def _render_planned(
        self, stage: Stage, guide: Guide, item: PracticeItem | None
    ) -> None:
        self._body.addWidget(section(self._theme, "这一课要做什么"))
        self._add_text(stage.goal)

        self._body.addWidget(section(self._theme, "要点"))
        for point in guide.outline:
            self._add_bullet(point)

        self._body.addSpacing(6)
        spec = drill_spec(item.drill) if item is not None and item.drill else None
        if spec is not None and spec.kind == "rhythm":
            note_text = (
                "这一课现在可以直接做节奏训练：先听 1 小节预备拍，再按任意键"
                "踩拍。完成后回到这一页，结果会写进本地学习档案。"
            )
        elif spec is not None:
            note_text = (
                "这一课现在可以直接做识谱训练：看谱 → 在光条上按下对应的音。"
                "完成后回到这一页，结果会写进本地学习档案。"
            )
        else:
            note_text = (
                "正文、图示与可试听的谱例制作中。现在可以先去演奏页跟弹，"
                "练习时顶部的「返回学习」会回到这一页。"
            )
        self._add_text(note_text, "faint")

    def _add_result(self, stage: Stage, item: PracticeItem | None) -> None:
        result = (
            self._page.progress.result_for(stage.index, item.name)
            if item is not None
            else None
        )
        line = result_line(result)
        if line is None:
            return
        text_value, role = line
        record = QLabel(f"练习记录 · {text_value}")
        record.setProperty("role", role)
        set_scaled_font(record, self._theme, 10)
        record.setWordWrap(True)
        self._body.addWidget(record)

    def _add_action(
        self, stage: Stage, item: PracticeItem | None, guide: Guide
    ) -> None:
        actions = QHBoxLayout()
        if item is not None:
            label = (
                "开始训练"
                if item.drill
                else ("打开项目" if item.project else "去练习")
            )
            go = QPushButton(f"{label} · {item.name}")
            go.setProperty("role", "action")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            go.clicked.connect(lambda: self._page.practice(stage, item))
            actions.addWidget(go)
        else:
            waiting = QLabel(
                "本课暂无对应训练 · 可先去演奏页自由练习"
                if guide.is_ready()
                else "这一阶段的练习内容制作中"
            )
            waiting.setProperty("role", "faint")
            waiting.setWordWrap(True)
            actions.addWidget(waiting)
        actions.addStretch(1)
        self._body.addLayout(actions)


class LearningPage(GlassFrame):
    practiceRequested = Signal(object)
    drillRequested = Signal(object)
    examRequested = Signal(object)
    projectRequested = Signal(object)
    message = Signal(str)

    def __init__(self, theme: Theme, progress: LearningProgress, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.progress = progress
        self._view = "overview"
        self._stage_index = progress.last_stage if progress.last_stage is not None else 0
        self._guide_title = progress.last_guide if progress.last_view == "course" else ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(0)

        self._stack = QStackedWidget()
        self._overview = OverviewView(self)
        self._stage_view = StageView(self)
        self._course_view = CourseView(self)
        self._stack.addWidget(self._overview)
        self._stack.addWidget(self._stage_view)
        self._stack.addWidget(self._course_view)
        outer.addWidget(self._stack, 1)
        self._stack.setCurrentWidget(self._overview)

    # -- navigation --------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._overview.set_theme(theme)
        self._stage_view.set_theme(theme)
        self._course_view.set_theme(theme)

    def show_overview(self, save: bool = False) -> None:
        self._view = "overview"
        self._guide_title = ""
        self._overview.render()
        self._stack.setCurrentWidget(self._overview)

    def open_stage(self, index: int, save: bool = True) -> None:
        self._stage_index = max(0, min(index, len(STAGES) - 1))
        self._view = "stage"
        self._guide_title = ""
        self._stage_view.set_stage(stage_by_index(self._stage_index))
        self._stack.setCurrentWidget(self._stage_view)
        if save:
            self.progress.touch(self._stage_index, "", "stage", "")

    def open_course(self, guide_title: str, save: bool = True) -> bool:
        stage = stage_by_index(self._stage_index)
        guide = next((g for g in stage.guides if g.title == guide_title), None)
        if guide is None:
            return False
        self._view = "course"
        self._guide_title = guide.title
        self._course_view.set_course(stage, guide)
        self._stack.setCurrentWidget(self._course_view)
        if save:
            self.progress.touch(stage.index, "", "course", guide.title)
        return True

    def continue_last(self) -> None:
        if self.progress.last_stage is None:
            self.open_stage(0)
            return
        self._stage_index = self.progress.last_stage
        if self.progress.last_view == "course" and self.progress.last_guide:
            if self.open_course(self.progress.last_guide, save=False):
                return
        self.open_stage(self.progress.last_stage, save=False)

    def return_from_practice(self) -> None:
        if self._view == "course":
            stage = stage_by_index(self._stage_index)
            guide = next(
                (g for g in stage.guides if g.title == self._guide_title), None
            )
            if guide is not None:
                self._course_view.set_course(stage, guide)
                self._stack.setCurrentWidget(self._course_view)
                return
        self._stage_view.set_stage(stage_by_index(self._stage_index))
        self._stack.setCurrentWidget(self._stage_view)

    # -- progress ----------------------------------------------------------

    def stage_done(self, stage: Stage) -> bool:
        """A stage is done when every *ready* item has been completed.

        Unready content is not part of the path yet, so it cannot block
        completion — and it is never shown as if it were playable.
        """
        ready = stage.ready_items
        if not ready:
            return False
        for item in ready:
            result = self.progress.result_for(stage.index, item.name)
            if result is None or not result.completed:
                return False
        return True

    def refresh_progress(self) -> None:
        """Re-render the visible view after a practice result was recorded."""
        self._overview.render()
        if self._view == "course":
            stage = stage_by_index(self._stage_index)
            guide = next(
                (g for g in stage.guides if g.title == self._guide_title), None
            )
            if guide is not None:
                self._course_view.set_course(stage, guide)
        elif self._view == "stage":
            self._stage_view.set_stage(stage_by_index(self._stage_index))

    # -- practice hand-off -------------------------------------------------

    def practice(self, stage: Stage, item: PracticeItem) -> None:
        if not item.ready:
            self.message.emit("这个练习还没做好 · 内容制作中")
            return
        view = "course" if self._view == "course" else "stage"
        self.progress.touch(stage.index, item.name, view, self._guide_title)
        if item.drill:
            self.drillRequested.emit(
                DrillTarget(
                    stage.index,
                    item.name,
                    item.drill,
                    view,
                    self._guide_title,
                )
            )
            return
        if item.project:
            self.projectRequested.emit(
                ProjectTarget(
                    stage.index,
                    item.name,
                    item.project,
                    item.task,
                    view,
                    self._guide_title,
                )
            )
            return
        self.practiceRequested.emit(
            PracticeTarget(
                stage.index,
                item.name,
                item.score,
                view,
                self._guide_title,
                item.accompaniment,
                item.mapping,
            )
        )

    def start_exam(self, stage: Stage) -> None:
        """Launch the optional exam, keeping the same return-to-page path."""
        spec = exam_spec(stage.index)
        if spec is None:
            self.message.emit("这个阶段还没有考核 · 内容制作中")
            return
        view = "course" if self._view == "course" else "stage"
        # An exam is not resumable and is not a practice item: touch the stage
        # only, so "继续上次" never advertises a half-finished exam.
        self.progress.touch(stage.index, "", view, self._guide_title)
        self.examRequested.emit(
            ExamTarget(
                stage.index,
                spec.key,
                view,
                self._guide_title,
            )
        )
