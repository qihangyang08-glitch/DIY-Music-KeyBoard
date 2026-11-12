"""曲谱库: disk-derived cards, honest readiness, local import.

The page is presentation only. Scanning, parsing, grouping, import and removal
live in `app.core.library`; this module never guesses whether a file is
playable from its extension.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import (
    QFileSystemWatcher,
    QSignalBlocker,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.curriculum import SCORE_DIR, mapping_tag_for_refs
from ..core.library import (
    DEFAULT_VIEW,
    VIEW_ALL,
    VIEW_FAVORITES,
    VIEW_IMPORTED,
    VIEW_ORDER,
    VIEW_PLANNED,
    VIEW_READY,
    VIEW_RECENT,
    ImportResult,
    LibraryMeta,
    LibraryPiece,
    LibraryRegistry,
    RemoveResult,
    build_registry,
    default_import_dir,
    default_meta_path,
    import_score,
    remove_imports,
)
from .theme import Theme, rgba, set_scaled_font
from .widgets import CardFrame, GlassFrame

CARD_COLUMNS = 2


class ElidedLabel(QLabel):
    """One-line label that keeps the full string in its tooltip."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text or ""
        self.setToolTip(self._full)
        self._apply_elide()

    def fullText(self) -> str:
        return self._full

    def _apply_elide(self) -> None:
        width = max(0, self.width() - 2)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        super().setText(
            self.fontMetrics().elidedText(
                self._full, Qt.TextElideMode.ElideRight, width
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elide()


class PieceCard(CardFrame):
    """One library card. Playable cards are focusable; planned/failed are not."""

    activated = Signal(object)
    infoRequested = Signal(object)
    removeRequested = Signal(object)
    favoriteToggled = Signal(object, bool)
    tagsRequested = Signal(object)
    displayRequested = Signal(object)
    focused = Signal(object)

    def __init__(
        self,
        theme: Theme,
        piece: LibraryPiece,
        favorite: bool = False,
        tags: tuple[str, ...] = (),
        parent=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.piece = piece
        self.favorite = favorite
        self.tags = tags
        self.badge_text = piece.badge
        self.setObjectName("LibraryCard")
        # Planned/failed cards are also keyboard-reachable; activating them
        # only shows an informational message, never navigates.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{piece.title} · {piece.badge}")
        self.setToolTip(self._tooltip())
        self.setAccessibleDescription(self._tooltip())
        self._build()

    # -- construction -----------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title_label = ElidedLabel(self.piece.title)
        set_scaled_font(self.title_label, self.theme, 13, QFont.Weight.DemiBold)
        title_row.addWidget(self.title_label, 1)
        self.favorite_button = QPushButton("★" if self.favorite else "☆")
        self.favorite_button.setProperty("role", "icon")
        self.favorite_button.setCheckable(True)
        self.favorite_button.setChecked(self.favorite)
        self.favorite_button.setFixedSize(26, 26)
        self.favorite_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.favorite_button.setToolTip("收藏 / 取消收藏")
        self.favorite_button.setAccessibleName(
            f"{'取消收藏' if self.favorite else '收藏'}{self.piece.title}"
        )
        self.favorite_button.toggled.connect(
            lambda on: self._on_favorite_toggled(on)
        )
        title_row.addWidget(self.favorite_button, 0)
        self.badge_label = QLabel(self.piece.badge)
        set_scaled_font(self.badge_label, self.theme, 9, QFont.Weight.DemiBold)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self.badge_label, 0)
        layout.addLayout(title_row)

        self.source_label = ElidedLabel(self._source_text())
        self.source_label.setProperty("role", "muted")
        set_scaled_font(self.source_label, self.theme, 11)
        layout.addWidget(self.source_label)

        facts = self.piece.facts
        if facts is not None:
            self.facts_label = QLabel(
                f"{facts.range_label} · {facts.measures} 小节 · "
                f"{facts.duration:.1f} s · {facts.tempo:.0f} BPM · "
                f"{facts.note_count} 音 · {facts.time_signature[0]}/{facts.time_signature[1]}"
            )
            self.facts_label.setProperty("role", "faint")
            set_scaled_font(self.facts_label, self.theme, 10, mono=True)
            self.facts_label.setWordWrap(True)
            layout.addWidget(self.facts_label)
        else:
            self.facts_label = None

        license_text = self._license_text()
        if license_text:
            self.license_label = QLabel(license_text)
            self.license_label.setProperty("role", "faint")
            set_scaled_font(self.license_label, self.theme, 9)
            self.license_label.setWordWrap(True)
            layout.addWidget(self.license_label)
        else:
            self.license_label = None

        stages = self._stages_text()
        if stages:
            self.stages_label = QLabel(stages)
            self.stages_label.setProperty("role", "faint")
            set_scaled_font(self.stages_label, self.theme, 9)
            self.stages_label.setWordWrap(True)
            layout.addWidget(self.stages_label)
        else:
            self.stages_label = None

        mapping_tag = mapping_tag_for_refs(self.piece.stage_refs)
        self.mapping_label: QLabel | None = None
        if mapping_tag:
            self.mapping_label = QLabel(
                f"{mapping_tag} · 打开时自动切换映射"
            )
            set_scaled_font(self.mapping_label, self.theme, 9, QFont.Weight.DemiBold)
            self.mapping_label.setStyleSheet(
                f"color: {rgba(self.theme.amber)};"
            )
            self.mapping_label.setWordWrap(True)
            layout.addWidget(self.mapping_label)

        self.tags_label: QLabel | None = None
        if self.tags:
            self.tags_label = QLabel("标签 · " + " · ".join(self.tags))
            self.tags_label.setProperty("role", "faint")
            set_scaled_font(self.tags_label, self.theme, 9)
            self.tags_label.setWordWrap(True)
            layout.addWidget(self.tags_label)

        self.detail_label = None
        if self.piece.status == "failed":
            self.detail_label = QLabel(f"解析失败 · {self.piece.error or '无法解析曲谱'}")
            self.detail_label.setProperty("role", "danger")
            self.detail_label.setWordWrap(True)
            layout.addWidget(self.detail_label)
        elif self.piece.status == "planned":
            self.detail_label = QLabel(self.piece.item_meta)
            self.detail_label.setProperty("role", "faint")
            set_scaled_font(self.detail_label, self.theme, 9)
            layout.addWidget(self.detail_label)
        if self.piece.warnings:
            warning = QLabel("注意 · " + "；".join(self.piece.warnings))
            warning.setProperty("role", "faint")
            set_scaled_font(warning, self.theme, 9)
            warning.setWordWrap(True)
            layout.addWidget(warning)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addStretch(1)
        self.remove_button: QPushButton | None = None
        if self.piece.playable:
            open_label = QLabel("打开 ›")
            open_label.setProperty("role", "faint")
            set_scaled_font(open_label, self.theme, 10, QFont.Weight.DemiBold)
            action_row.addWidget(open_label)
        elif self.piece.status == "display":
            open_label = QLabel("查看 ›" if self._is_image() else "仅显示")
            open_label.setProperty("role", "faint")
            set_scaled_font(open_label, self.theme, 10, QFont.Weight.DemiBold)
            action_row.addWidget(open_label)
        if self.piece.status != "planned":
            self.tag_button = QPushButton("标签")
            self.tag_button.setProperty("role", "flat")
            self.tag_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tag_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.tag_button.setToolTip("给这首曲谱加标签")
            self.tag_button.clicked.connect(
                lambda checked=False: self.tagsRequested.emit(self.piece)
            )
            action_row.addWidget(self.tag_button)
        else:
            self.tag_button = None
        if self.piece.origin == "imported" and self.piece.import_paths:
            self.remove_button = QPushButton("移除")
            self.remove_button.setProperty("role", "danger")
            self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.remove_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.remove_button.setAccessibleName(f"移除导入的{self.piece.title}")
            self.remove_button.setToolTip("只删除曲谱库里的副本，不影响源文件")
            self.remove_button.clicked.connect(
                lambda checked=False: self.removeRequested.emit(self.piece)
            )
            action_row.addWidget(self.remove_button)
        if action_row.count() > 1:
            layout.addLayout(action_row)

        self.set_theme(self.theme)

    # -- text helpers -----------------------------------------------------

    def _is_image(self) -> bool:
        primary = self.piece.primary
        return primary is not None and primary.family == "image"

    def _on_favorite_toggled(self, on: bool) -> None:
        self.favorite = on
        self.favorite_button.setText("★" if on else "☆")
        self.favoriteToggled.emit(self.piece, on)

    def _source_text(self) -> str:
        if self.piece.status == "display":
            primary = self.piece.primary.path.name if self.piece.primary else ""
            return f"仅显示 · 不跟谱 · {primary}"
        facts = self.piece.facts
        composer = facts.composer if facts is not None else ""
        if not composer or composer == "—":
            composer = "未标注作曲"
        primary = self.piece.primary.path.name if self.piece.primary else ""
        if self.piece.origin == "planned":
            ref = self.piece.stage_refs[0] if self.piece.stage_refs else None
            if ref is not None:
                return f"课程规划 · 阶段 {ref.stage_index} {ref.stage_name}"
            return "课程规划"
        if self.piece.origin == "builtin":
            text = f"{composer or '未标注作曲'} · 内置样曲 · {primary}"
            has_xml = any(file.family == "xml" for file in self.piece.files)
            has_midi = any(file.family == "midi" for file in self.piece.files)
            if has_xml and has_midi:
                text += " · 同源 MIDI 示例"
            return text
        text = f"{composer or '未标注作曲'} · 我的导入 · {primary}"
        if len(self.piece.paths) > 1:
            text += f" · {len(self.piece.paths)} 个文件"
        return text

    def _license_text(self) -> str:
        if self.piece.origin == "planned":
            return ""
        if self.piece.status == "display":
            return "本地导入 · 仅显示 · 不跟谱 · 不上传"
        if self.piece.origin == "imported":
            return "本地导入 · 许可未核验 · 不上传"
        facts = self.piece.facts
        if facts is not None and facts.rights and facts.rights != "未标注":
            return f"许可 · {facts.rights}"
        return ""

    def _stages_text(self) -> str:
        if self.piece.status == "planned":
            return ""
        names: list[str] = []
        for ref in self.piece.stage_refs:
            label = f"阶段 {ref.stage_index} {ref.stage_name}"
            if label not in names:
                names.append(label)
        if not names:
            return (
                "课程 · 未引用"
                if self.piece.origin == "builtin"
                else "课程 · 未用于课程"
            )
        return "课程 · " + " · ".join(names)

    def _tooltip(self) -> str:
        lines = [f"{self.piece.title} · {self.piece.badge}"]
        if self.piece.facts is not None:
            lines.append(self.piece.facts.range_label)
            lines.append(f"{self.piece.facts.note_count} 个音")
        if self.piece.error:
            lines.append(f"解析失败：{self.piece.error}")
        for file in self.piece.files:
            if file.family in ("image", "pdf"):
                detail = "仅显示 · 不跟谱"
            else:
                detail = (
                    "可解析"
                    if file.parsed
                    else f"失败：{file.error or '无法解析'}"
                )
            lines.append(f"{file.path.name} · {detail}")
        for ref in self.piece.stage_refs:
            lines.append(f"阶段 {ref.stage_index} · {ref.item_name}")
        for warning in self.piece.warnings:
            lines.append(f"注意：{warning}")
        return "\n".join(lines)

    # -- theme / interaction ---------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        if self.piece.status == "ready":
            color = theme.amber
        elif self.piece.status == "failed":
            color = theme.danger
        else:
            color = theme.faint
        self.badge_label.setStyleSheet(f"color: {rgba(color)};")
        if self.detail_label is not None and self.piece.status == "failed":
            self.detail_label.setStyleSheet(f"color: {rgba(theme.danger)};")
        if self.remove_button is not None:
            self.remove_button.setStyleSheet(f"color: {rgba(theme.danger)};")
        self.update()

    def activate(self) -> None:
        if self.piece.playable:
            self.activated.emit(self.piece)
        elif self.piece.status == "display" and self._is_image():
            self.displayRequested.emit(self.piece)
        else:
            self.infoRequested.emit(self.piece)

    def mouseReleaseEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focused.emit(self.piece)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.hasFocus():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.theme.amber, 2))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 12, 12)


class LibraryPage(GlassFrame):
    """曲谱库 page. Builds its registry lazily and refreshes on page show."""

    scoreRequested = Signal(str)
    displayRequested = Signal(str)
    message = Signal(str)

    def __init__(
        self,
        theme: Theme,
        import_dir: str | Path | None = None,
        builtin_dir: str | Path | None = None,
        meta_path: str | Path | None = None,
        watch_enabled: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.watch_enabled = watch_enabled
        self.import_dir = (
            Path(import_dir) if import_dir is not None else default_import_dir()
        )
        self.builtin_dir = (
            Path(builtin_dir) if builtin_dir is not None else SCORE_DIR
        )
        self.meta_path = (
            Path(meta_path)
            if meta_path is not None
            else default_meta_path(self.import_dir)
        )
        self.meta = LibraryMeta.load(self.meta_path)
        self.registry: LibraryRegistry | None = None
        self.cards: tuple[PieceCard, ...] = ()
        self.view = DEFAULT_VIEW
        self.query = ""
        self.empty_text = ""
        self.empty_action: QPushButton | None = None
        self._import_notice = ""
        self._notice_dismissed = False
        self._watch = QFileSystemWatcher(self)
        if self.watch_enabled:
            self._watch.directoryChanged.connect(self._on_watch_changed)
            self._watch.fileChanged.connect(self._on_watch_changed)
        self._watch_timer = QTimer(self)
        self._watch_timer.setSingleShot(True)
        self._watch_timer.setInterval(300)
        self._watch_timer.timeout.connect(self.refresh)
        self._build_chrome()

    # -- chrome -----------------------------------------------------------

    def _build_chrome(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 26)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        heading_col = QVBoxLayout()
        heading_col.setSpacing(2)
        badge = QLabel("曲谱库")
        set_scaled_font(badge, self.theme, 11, QFont.Weight.DemiBold)
        badge.setStyleSheet(f"color: {rgba(self.theme.amber)};")
        self._badge_label = badge
        title = QLabel("曲谱")
        set_scaled_font(title, self.theme, 24, QFont.Weight.DemiBold)
        subtitle = QLabel(
            "只把能解析的 MusicXML / MIDI 标为可跟随。导入只保存在本机，不上传。"
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        heading_col.addWidget(badge)
        heading_col.addWidget(title)
        heading_col.addWidget(subtitle)
        header.addLayout(heading_col, 1)

        self.import_button = QPushButton("导入曲谱")
        self.import_button.setProperty("role", "action")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.import_button.setAccessibleName("导入曲谱")
        self.import_button.clicked.connect(self._choose_files)
        header.addWidget(self.import_button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        counts_row = QHBoxLayout()
        counts_row.setSpacing(8)
        self.counts_label = QLabel()
        self.counts_label.setProperty("role", "faint")
        set_scaled_font(self.counts_label, self.theme, 10)
        counts_row.addWidget(self.counts_label)
        self.failed_label = QLabel()
        self.failed_label.setProperty("role", "danger")
        set_scaled_font(self.failed_label, self.theme, 10)
        self.failed_label.hide()
        counts_row.addWidget(self.failed_label)
        counts_row.addStretch(1)
        self.roadmap_button = QPushButton("查看制作中 →")
        self.roadmap_button.setProperty("role", "flat")
        self.roadmap_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.roadmap_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.roadmap_button.setAccessibleName("查看制作中的曲目")
        self.roadmap_button.clicked.connect(
            lambda checked=False: self.set_view(VIEW_PLANNED)
        )
        self.roadmap_button.hide()
        counts_row.addWidget(self.roadmap_button)
        outer.addLayout(counts_row)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        filter_caption = QLabel("筛选")
        filter_caption.setProperty("role", "faint")
        filters.addWidget(filter_caption)
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        self._filter_buttons: dict[str, QPushButton] = {}
        for key, label in VIEW_ORDER:
            button = QPushButton(label)
            button.setProperty("role", "tab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setAccessibleName(f"筛选 · {label}")
            button.clicked.connect(
                lambda checked=False, view=key: self.set_view(view)
            )
            self._filter_group.addButton(button)
            self._filter_buttons[key] = button
            filters.addWidget(button)
        self._filter_buttons[DEFAULT_VIEW].setChecked(True)
        filters.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标题 / 作曲家 / 阶段")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(180)
        self.search.setMaximumWidth(280)
        self.search.setAccessibleName("搜索曲谱")
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search)
        self.search.textChanged.connect(self._queue_search)
        filters.addWidget(self.search)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setProperty("role", "flat")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.refresh_button.setToolTip("重新扫描曲谱文件夹")
        self.refresh_button.setAccessibleName("刷新曲库")
        self.refresh_button.clicked.connect(lambda checked=False: self.refresh())
        filters.addWidget(self.refresh_button)
        outer.addLayout(filters)

        self.notice_frame = CardFrame()
        notice_layout = QHBoxLayout(self.notice_frame)
        notice_layout.setContentsMargins(12, 8, 12, 8)
        notice_layout.setSpacing(8)
        self.notice_label = QLabel()
        self.notice_label.setProperty("role", "muted")
        self.notice_label.setWordWrap(True)
        notice_layout.addWidget(self.notice_label, 1)
        self.notice_close = QPushButton("关闭")
        self.notice_close.setProperty("role", "flat")
        self.notice_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notice_close.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.notice_close.clicked.connect(self._dismiss_notice)
        notice_layout.addWidget(self.notice_close, 0, Qt.AlignmentFlag.AlignTop)
        self.notice_frame.hide()
        outer.addWidget(self.notice_frame)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        content = QWidget()
        content.setObjectName("ScrollContent")
        content.setAutoFillBackground(False)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(2, 2, 6, 8)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(10)
        for column in range(CARD_COLUMNS):
            self._grid.setColumnStretch(column, 1)
        content_layout.addLayout(self._grid)
        content_layout.addStretch(1)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)

        self.set_theme(self.theme)

    # -- public state -----------------------------------------------------

    @property
    def counts_text(self) -> str:
        if self.registry is None:
            return "可跟谱 0 · 我的导入 0 · 制作中 0"
        counts = self.registry.counts()
        return (
            f"可跟谱 {counts['ready']} · 我的导入 {counts['imported']} · "
            f"制作中 {counts['planned']}"
        )

    @property
    def notice_text(self) -> str:
        return self.notice_label.text()

    # -- scan / render ----------------------------------------------------

    def refresh(self) -> None:
        position = self.scroll.verticalScrollBar().value()
        focus = QApplication.focusWidget()
        focused_key = focus.piece.key if isinstance(focus, PieceCard) else None
        self._notice_dismissed = False
        self.registry = build_registry(self.builtin_dir, self.import_dir)
        self._refresh_watch()
        self.render()
        self.scroll.verticalScrollBar().setValue(position)
        if focused_key is not None:
            for card in self.cards:
                if card.piece.key == focused_key:
                    card.setFocus()
                    break

    def render(self) -> None:
        self._clear_grid()
        self.cards = ()
        self.empty_text = ""
        self.empty_action = None
        counts = (
            self.registry.counts()
            if self.registry is not None
            else {"ready": 0, "imported": 0, "planned": 0, "failed": 0, "all": 0}
        )
        self.counts_label.setText(self.counts_text)
        self.failed_label.setText(f"· 解析失败 {counts['failed']}")
        self.failed_label.setVisible(counts["failed"] > 0)
        self.roadmap_button.setVisible(counts["planned"] > 0)
        self._update_notice()

        pieces = (
            self.registry.select(self.view, self.query, self.meta)
            if self.registry is not None
            else ()
        )
        if pieces:
            cards: list[PieceCard] = []
            for index, piece in enumerate(pieces):
                card = PieceCard(
                    self.theme,
                    piece,
                    favorite=self.meta.is_favorite(piece.key),
                    tags=self.meta.tags_for(piece.key),
                )
                card.activated.connect(self._on_card_activated)
                card.infoRequested.connect(self._on_card_activated)
                card.removeRequested.connect(self.remove_piece)
                card.favoriteToggled.connect(self.toggle_favorite)
                card.tagsRequested.connect(self.edit_tags)
                card.displayRequested.connect(self._on_display_requested)
                card.focused.connect(self._on_card_focused)
                self._grid.addWidget(card, index // CARD_COLUMNS, index % CARD_COLUMNS)
                cards.append(card)
            self.cards = tuple(cards)
        else:
            self._add_empty_state()

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _add_empty_state(self) -> None:
        title_text, body_text = self._empty_copy()
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        title = QLabel(title_text)
        set_scaled_font(title, self.theme, 14, QFont.Weight.DemiBold)
        body = QLabel(body_text)
        body.setProperty("role", "muted")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        self.empty_text = f"{title_text}\n{body_text}"

        if (
            self.query
            and self.registry is not None
            and self.view != VIEW_ALL
            and self.registry.select(VIEW_ALL, self.query, self.meta)
        ):
            action = QPushButton("在全部中搜索")
            action.setProperty("role", "flat")
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            action.clicked.connect(lambda checked=False: self.set_view(VIEW_ALL))
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignLeft)
            self.empty_action = action

        self._grid.addWidget(card, 0, 0, 1, CARD_COLUMNS)
        self.cards = ()

    def _empty_copy(self) -> tuple[str, str]:
        if self.query:
            return (
                "没有匹配的曲目",
                f"没有匹配「{self.query}」的曲目。试试更短的关键词，或清空搜索。",
            )
        if self.view == VIEW_FAVORITES:
            return ("还没有收藏", "点曲谱卡右上角的 ☆ 收藏，之后会出现在这里。")
        if self.view == VIEW_RECENT:
            return ("还没有最近打开", "打开一首可跟谱曲目后，这里会保留最近记录。")
        if self.view == VIEW_IMPORTED:
            return (
                "还没有导入",
                "MusicXML / MIDI 可跟随；图片/PDF 仅显示，只保存在本机。",
            )
        if self.view == VIEW_PLANNED:
            return ("没有制作中的曲目", "所有课程曲目都已有可跟谱面。")
        return (
            "还没有可跟谱的曲目",
            "导入 MusicXML / MIDI，或切到「制作中」查看课程规划。",
        )

    # -- filters / search -------------------------------------------------

    def set_view(self, view: str) -> None:
        if view not in self._filter_buttons:
            return
        self.view = view
        button = self._filter_buttons[view]
        with QSignalBlocker(button):
            button.setChecked(True)
        self.render()
        self.scroll.verticalScrollBar().setValue(0)

    def _queue_search(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_search(self) -> None:
        self.set_query(self.search.text())

    def set_query(self, text: str | None) -> None:
        self._search_timer.stop()
        self.query = (text or "").strip()
        with QSignalBlocker(self.search):
            self.search.setText(self.query)
        self.render()
        self.scroll.verticalScrollBar().setValue(0)

    # -- favorites / tags / recent / watch --------------------------------

    def toggle_favorite(self, piece: LibraryPiece, on: bool) -> None:
        if on:
            self.meta.favorites.add(piece.key)
        else:
            self.meta.favorites.discard(piece.key)
        self._save_meta()
        self.message.emit(
            f"{'已收藏' if on else '已取消收藏'} · {piece.title}"
        )
        if self.view == VIEW_FAVORITES:
            self.render()

    def edit_tags(self, piece: LibraryPiece) -> None:
        current = ", ".join(self.meta.tags_for(piece.key))
        text, accepted = QInputDialog.getText(
            self,
            "曲谱标签",
            "标签（用逗号分隔，最多 8 个）：",
            text=current,
        )
        if accepted:
            self.set_piece_tags(
                piece, [part for part in text.replace("，", ",").split(",")]
            )

    def set_piece_tags(self, piece: LibraryPiece, tags: Iterable[str]) -> None:
        cleaned = self.meta.set_tags(piece.key, tags)
        self._save_meta()
        self.render()
        if cleaned:
            self.message.emit(f"标签已更新 · {piece.title} · {' / '.join(cleaned)}")
        else:
            self.message.emit(f"已清除标签 · {piece.title}")

    def record_recent(self, piece: LibraryPiece) -> None:
        self.meta.touch_recent(piece.key)
        self._save_meta()

    def record_recent_path(self, path: str | Path) -> None:
        target = Path(path).resolve()
        if self.registry is None:
            return
        for piece in self.registry.pieces:
            primary = piece.primary
            if primary is None:
                continue
            try:
                if primary.path.resolve() == target:
                    self.record_recent(piece)
                    return
            except OSError:
                continue

    def _save_meta(self) -> None:
        try:
            self.meta.save(self.meta_path)
        except OSError as exc:
            self.message.emit(f"曲库元数据保存失败：{exc}")

    def _on_watch_changed(self, _path: str) -> None:
        self._watch_timer.start()

    def _refresh_watch(self) -> None:
        if not self.watch_enabled:
            return
        roots: list[Path] = []
        watch_root = self.import_dir
        while not watch_root.exists() and watch_root != watch_root.parent:
            watch_root = watch_root.parent
        if watch_root.exists():
            roots.append(watch_root)
        if self.import_dir.exists():
            try:
                for path in self.import_dir.rglob("*"):
                    if len(roots) >= 256:
                        break
                    if path.is_dir() and not path.is_symlink():
                        roots.append(path)
            except OSError:
                pass
        existing = set(self._watch.directories())
        wanted = {str(path) for path in roots if path.is_dir()}
        for path in existing - wanted:
            self._watch.removePath(path)
        for path in sorted(wanted - existing):
            self._watch.addPath(path)

    def watch_now(self) -> None:
        """Test/dev hook: treat the import folder as changed."""
        self._on_watch_changed(str(self.import_dir))

    # -- import / remove --------------------------------------------------

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "导入曲谱",
            "",
            "曲谱 (*.musicxml *.mxl *.xml *.mid *.midi);;"
            "MusicXML (*.musicxml *.mxl *.xml);;"
            "MIDI (*.mid *.midi);;"
            "图片/PDF（仅显示） (*.png *.jpg *.jpeg *.bmp *.webp *.pdf);;"
            "所有文件 (*)",
        )
        if files:
            self.import_files(files)

    def import_files(self, paths: Iterable[str | Path]) -> list[ImportResult]:
        results = [import_score(path, self.import_dir) for path in paths]
        if not results:
            return results
        if any(result.kind == "imported" for result in results):
            self.view = VIEW_IMPORTED
            with QSignalBlocker(self._filter_buttons[VIEW_IMPORTED]):
                self._filter_buttons[VIEW_IMPORTED].setChecked(True)
        self.query = ""
        with QSignalBlocker(self.search):
            self.search.clear()
        self.refresh()
        # refresh() deliberately restores the old scroll offset; after an
        # import, show the newly added cards from the top instead.
        self.scroll.verticalScrollBar().setValue(0)
        summary, details = self._import_copy(results)
        self._import_notice = summary + ("\n" + details if details else "")
        self._notice_dismissed = False
        self._update_notice()
        self.message.emit(summary)
        return results

    def _import_copy(self, results: list[ImportResult]) -> tuple[str, str]:
        imported = [r for r in results if r.kind == "imported"]
        duplicates = [r for r in results if r.kind == "duplicate"]
        rejected = [r for r in results if r.kind == "rejected"]
        details: list[str] = []
        for result in imported:
            if result.error:
                details.append(
                    f"已导入但无法解析：{result.path.name if result.path else result.title}"
                    f" · 请在「我的导入」移除"
                )
        for result in duplicates:
            details.append(f"已在曲库：{result.path.name if result.path else result.title}")
        for result in rejected:
            details.append(f"导入失败：{result.title} · {result.error or '未知原因'}")

        parse_failed = [result for result in imported if result.error]
        if len(results) == 1:
            result = results[0]
            if result.kind == "imported":
                if result.error:
                    return "已导入但无法解析 · 请在「我的导入」移除", "\n".join(details)
                return f"已导入 · {result.title}", ""
            if result.kind == "duplicate":
                name = result.path.name if result.path else result.title
                return f"已在曲库 · {name}", ""
            return f"导入失败 · {result.title}：{result.error or '未知原因'}", ""
        summary = (
            f"已导入 {len(imported)} · 重复 {len(duplicates)} · 失败 {len(rejected)}"
        )
        if parse_failed:
            summary += f" · 无法解析 {len(parse_failed)}"
        return summary, "\n".join(details)

    def remove_piece(self, piece: LibraryPiece, confirm: bool = True) -> RemoveResult:
        if piece.origin != "imported" or not piece.import_paths:
            return RemoveResult(errors=("只能移除导入的曲谱。",))
        if confirm:
            answer = QMessageBox.question(
                self,
                "移除导入",
                f"删除导入的《{piece.title}》？\n"
                f"将删除本机副本 {len(piece.import_paths)} 个文件，"
                "不影响源文件、内置曲目或当前练习。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return RemoveResult()
        result = remove_imports(piece.import_paths, self.import_dir)
        if result.ok:
            self._import_notice = ""
            self.meta.favorites.discard(piece.key)
            self.meta.tags.pop(piece.key, None)
            self.meta.recent = [
                key for key in self.meta.recent if key != piece.key
            ]
            self._save_meta()
        self.refresh()
        if result.ok:
            self.message.emit(f"已移除导入 · {piece.title}")
        else:
            self.message.emit("移除失败 · " + "；".join(result.errors))
        return result

    # -- signals ----------------------------------------------------------

    def _on_card_activated(self, piece: LibraryPiece) -> None:
        if piece.playable and piece.primary is not None:
            self.scoreRequested.emit(str(piece.primary.path))
        elif piece.status == "display":
            self.message.emit(
                f"《{piece.title}》仅显示 · 不进入跟弹判定"
            )
        elif piece.status == "planned":
            self.message.emit(f"《{piece.title}》还在制作中 · 暂不可跟弹")
        else:
            self.message.emit(f"解析失败 · {piece.error or piece.title}")

    def _on_display_requested(self, piece: LibraryPiece) -> None:
        if piece.primary is None:
            return
        self.displayRequested.emit(str(piece.primary.path))

    def _on_card_focused(self, piece: LibraryPiece) -> None:
        for card in self.cards:
            if card.piece is piece:
                self.scroll.ensureWidgetVisible(card)
                break

    # -- notice / theme ---------------------------------------------------

    def _update_notice(self) -> None:
        parts: list[str] = []
        if self._import_notice:
            parts.append(self._import_notice)
        if self.registry is not None and not self._notice_dismissed:
            parts.extend(self.registry.warnings)
        text = "\n".join(parts)
        self.notice_label.setText(text)
        self.notice_frame.setVisible(bool(text))

    def _dismiss_notice(self) -> None:
        self._import_notice = ""
        self._notice_dismissed = True
        self._update_notice()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._badge_label.setStyleSheet(f"color: {rgba(theme.amber)};")
        self.search.setStyleSheet(
            "QLineEdit {"
            f"background: {rgba(theme.card)};"
            f"color: {rgba(theme.ink)};"
            f"border: 1px solid {rgba(theme.hair)};"
            f"border-radius: 9px; padding: 6px 10px; font-size: {theme.px(12)}px;"
            "}"
        )
        self.notice_label.setStyleSheet(f"color: {rgba(theme.muted)};")
        if self.registry is not None:
            self.render()
        else:
            for card in self.cards:
                card.set_theme(theme)
