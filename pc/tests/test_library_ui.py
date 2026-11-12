"""Headless UI tests for the 曲谱库 page and MainWindow wiring."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.curriculum import stage_by_index
from app.core.library import (
    VIEW_ALL,
    VIEW_FAVORITES,
    VIEW_IMPORTED,
    VIEW_PLANNED,
    VIEW_READY,
    VIEW_RECENT,
    LibraryMeta,
)
from app.ui.main_window import MainWindow
from test_library import (
    write_broken_midi,
    write_broken_musicxml,
    write_musicxml,
)

SAMPLE = ROOT / "resources" / "scores" / "xiaoxingxing.musicxml"


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def make_window(root: Path, library_root: Path | None = None) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        prefs_path=root / "score_prefs.json",
        library_root=library_root if library_root is not None else root / "scores",
        library_watch=False,
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(160)
    return window


class LibraryWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_library(self):
        self.window._show_page(2)
        wait(120)
        page = self.window.library_page
        self.assertIs(self.window.stack.currentWidget(), page)
        return page

    def test_search_typing_is_debounced_and_applied(self) -> None:
        page = self.open_library()
        page.search.setText("欢乐")
        # Typing should not rebuild the card grid on every keystroke.
        self.assertNotEqual(page.query, "欢乐")
        wait(220)
        self.assertEqual(page.query, "欢乐")

    def test_nav_index_2_is_library_page(self) -> None:
        page = self.open_library()
        self.assertIs(self.window.pages[2], page)
        self.assertIs(self.window.stack.widget(2), page)
        self.assertIn("曲谱", self.window.nav_buttons[2].text())
        self.assertEqual(page.view, VIEW_READY)
        counts = page.registry.counts()
        self.assertEqual(len(page.cards), counts["ready"])
        titles = {card.piece.title for card in page.cards}
        self.assertIn("小星星（片段）", titles)
        self.assertIn("欢乐颂", titles)
        self.assertIn("铃儿响叮当（片段）", titles)
        self.assertIn("两只老虎", titles)
        self.assertTrue(all(card.piece.playable for card in page.cards))
        self.assertIn(f"可跟谱 {counts['ready']}", page.counts_text)
        self.assertIn(f"制作中 {counts['planned']}", page.counts_text)
        self.assertTrue(page.roadmap_button.isVisible())

    def test_ready_card_mouse_click_loads_perform(self) -> None:
        page = self.open_library()
        self.window.follow.index = 3
        self.window.follow.hits = 2
        card = next(c for c in page.cards if c.piece.title == "小星星（片段）")
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        self.assertEqual(self.window.follow.score.title, "小星星（片段）")
        self.assertEqual(
            Path(self.window.follow.score.source).resolve(),
            card.piece.primary.path.resolve(),
        )
        self.assertEqual(self.window.follow.index, 0)
        self.assertEqual(self.window.follow.hits, 0)
        self.assertEqual(self.window.follow.misses, 0)
        self.assertFalse(self.window.study_return.isVisible())

    def test_keyboard_enter_and_space_activate_ready_card(self) -> None:
        page = self.open_library()
        card = page.cards[0]
        card.setFocus()
        QTest.keyClick(card, Qt.Key.Key_Return)
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)

        page = self.open_library()
        card = page.cards[0]
        card.setFocus()
        QTest.keyClick(card, Qt.Key.Key_Space)
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)

    def test_import_files_then_play_imported_copy(self) -> None:
        source = self.root / "incoming" / "mysong.musicxml"
        write_musicxml(source, title="我的测试曲")
        page = self.open_library()
        results = page.import_files([source])
        self.assertEqual([r.kind for r in results], ["imported"])
        self.assertEqual(page.view, VIEW_IMPORTED)
        self.assertEqual(len(page.cards), 1)
        card = page.cards[0]
        # Resolve both: Windows may hand out an 8.3 short temp path
        # (RUNNER~1) while the library stores the long form.
        self.assertEqual(
            card.piece.primary.path.parent.resolve(),
            (self.root / "scores").resolve(),
        )
        card.activate()
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        self.assertEqual(self.window.follow.score.title, "我的测试曲")
        self.assertEqual(
            Path(self.window.follow.score.source).resolve(),
            card.piece.primary.path.resolve(),
        )
        self.assertEqual(self.window.follow.index, 0)

    def test_duplicate_import_is_single_card(self) -> None:
        source = self.root / "incoming" / "mysong.musicxml"
        write_musicxml(source, title="我的测试曲")
        page = self.open_library()
        page.import_files([source])
        results = page.import_files([source])
        self.assertEqual(results[0].kind, "duplicate")
        self.assertEqual(len(page.cards), 1)
        self.assertIn("已在曲库", self.window.toast.text())

    def test_failed_import_card_is_visible_and_removable(self) -> None:
        source = self.root / "incoming" / "broken.musicxml"
        write_broken_musicxml(source)
        page = self.open_library()
        results = page.import_files([source])
        self.assertEqual(results[0].kind, "imported")
        self.assertTrue(results[0].error)
        self.assertEqual(len(page.cards), 1)
        card = page.cards[0]
        self.assertFalse(card.piece.playable)
        self.assertIsNotNone(card.remove_button)
        self.assertEqual(card.badge_text, "解析失败")

        result = page.remove_piece(card.piece, confirm=False)
        self.assertTrue(result.ok)
        self.assertEqual(page.cards, ())
        self.assertIn("还没有导入", page.empty_text)
        self.assertNotIn("已导入", page.notice_text)
        self.assertFalse(page.notice_frame.isVisible())
        counts = page.registry.counts()
        self.assertEqual(counts["imported"], 0)
        self.assertEqual(counts["failed"], 0)

    def test_planned_card_does_not_navigate(self) -> None:
        page = self.open_library()
        page.set_view(VIEW_PLANNED)
        card = next(c for c in page.cards if c.piece.title == "三轨小作品")
        before = self.window.follow.score
        card.activate()
        wait(80)
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIs(self.window.follow.score, before)
        self.assertIn("制作中", self.window.toast.text())

    def test_planned_card_keyboard_shows_info_only(self) -> None:
        page = self.open_library()
        page.set_view(VIEW_PLANNED)
        card = next(c for c in page.cards if c.piece.title == "三轨小作品")
        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        card.setFocus()
        QTest.keyClick(card, Qt.Key.Key_Return)
        wait(80)
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIn("制作中", self.window.toast.text())

    def test_failed_card_keyboard_shows_error_only(self) -> None:
        source = self.root / "incoming" / "broken.musicxml"
        write_broken_musicxml(source)
        page = self.open_library()
        page.import_files([source])
        card = page.cards[0]
        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        card.setFocus()
        before = self.window.follow.score
        QTest.keyClick(card, Qt.Key.Key_Return)
        wait(80)
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIs(self.window.follow.score, before)
        self.assertIn("解析失败", self.window.toast.text())

    def test_corrupt_midi_and_zero_tempo_are_reported(self) -> None:
        broken_midi = self.root / "incoming" / "broken.mid"
        zero_tempo = self.root / "incoming" / "zero.musicxml"
        write_broken_midi(broken_midi)
        write_musicxml(zero_tempo, title="Zero", tempo=0)
        before = self.window.follow.score
        for path in (broken_midi, zero_tempo):
            loaded = self.window._load_score_file(str(path), announce=False)
            wait(30)
            self.assertFalse(loaded)
            self.assertIn("谱面载入失败", self.window.toast.text())
            self.assertIs(self.window.follow.score, before)

    def test_mixed_import_summary_counts_parse_failures(self) -> None:
        good = self.root / "incoming" / "good.musicxml"
        bad = self.root / "incoming" / "bad.musicxml"
        write_musicxml(good, title="Good")
        write_broken_musicxml(bad)
        page = self.open_library()
        page.import_files([good, bad])
        self.assertIn("无法解析 1", self.window.toast.text())

    def test_import_scrolls_to_top(self) -> None:
        page = self.open_library()
        fillers = []
        for index in range(12):
            path = self.root / "incoming" / f"fill{index:02d}.musicxml"
            write_musicxml(path, title=f"Fill {index:02d}")
            fillers.append(path)
        page.import_files(fillers)
        wait(80)
        bar = page.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        wait(20)

        new = self.root / "incoming" / "aaa.musicxml"
        write_musicxml(new, title="AAA")
        page.import_files([new])
        wait(80)
        self.assertEqual(page.scroll.verticalScrollBar().value(), 0)
        self.assertIn("AAA", [card.piece.title for card in page.cards])

    def test_close_hides_warning_banner_until_refresh(self) -> None:
        page = self.open_library()
        page.builtin_dir = self.root / "missing_builtin"
        page.refresh()
        wait(60)
        self.assertTrue(page.notice_frame.isVisible())
        self.assertIn("不存在", page.notice_text)
        page.notice_close.click()
        wait(40)
        self.assertFalse(page.notice_frame.isVisible())
        page.refresh()
        wait(60)
        self.assertTrue(page.notice_frame.isVisible())

    def test_filters_and_search_in_ui(self) -> None:
        page = self.open_library()
        page.set_query("三轨小作品")
        self.assertEqual(page.cards, ())
        self.assertIn("没有匹配", page.empty_text)
        self.assertIsNotNone(page.empty_action)
        page.empty_action.click()
        wait(80)
        self.assertEqual(page.view, VIEW_ALL)
        self.assertEqual(page.query, "三轨小作品")
        self.assertTrue(page.cards)
        self.assertTrue(all("三轨小作品" in c.piece.title for c in page.cards))

        page.set_query("__no_such__")
        self.assertEqual(page.cards, ())
        self.assertIsNone(page.empty_action)

        page.set_query("")
        page.set_view(VIEW_PLANNED)
        self.assertEqual(len(page.cards), page.registry.counts()["planned"])
        self.assertTrue(all(not c.piece.playable for c in page.cards))

        page.set_view(VIEW_IMPORTED)
        self.assertIn("还没有导入", page.empty_text)

    def test_theme_switch_preserves_filter_and_query(self) -> None:
        page = self.open_library()
        page.set_view(VIEW_PLANNED)
        page.set_query("欢乐")
        count = len(page.cards)
        registry = page.registry
        self.window.apply_theme("stage")
        wait(120)
        self.assertEqual(page.view, VIEW_PLANNED)
        self.assertEqual(page.query, "欢乐")
        self.assertEqual(len(page.cards), count)
        self.assertIs(page.registry, registry)
        self.assertEqual(page.theme.name, "stage")
        self.assertIs(self.window.stack.currentWidget(), page)
        self.window.apply_theme("studio")

    def test_refresh_on_page_show_picks_up_external_file(self) -> None:
        page = self.open_library()
        import_dir = self.root / "scores"
        external = import_dir / "external.musicxml"
        write_musicxml(external, title="外部曲谱")
        self.window._show_page(0)
        self.window._show_page(2)
        wait(120)
        page = self.window.library_page
        matches = [
            card
            for card in page.cards
            if card.piece.primary is not None
            and card.piece.primary.path.resolve() == external.resolve()
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].piece.playable)

    def test_1120x760_has_no_horizontal_overflow(self) -> None:
        page = self.open_library()
        page.set_view(VIEW_PLANNED)
        wait(120)
        # A 1 px rounding difference from another font/DPI is invisible and
        # the horizontal bar is disabled; anything larger is a real overflow.
        self.assertLessEqual(page.scroll.horizontalScrollBar().maximum(), 1)
        self.assertTrue(all(card.width() > 0 for card in page.cards))
        self.assertTrue(page.search.isVisible())
        self.assertTrue(page._filter_buttons[VIEW_READY].isVisible())

    def test_stale_card_path_is_guarded(self) -> None:
        source = self.root / "incoming" / "gone.musicxml"
        write_musicxml(source, title="会消失的曲子")
        page = self.open_library()
        page.import_files([source])
        card = page.cards[0]
        card.piece.primary.path.unlink()
        before = self.window.follow.score
        card.activate()
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIn("谱面已不在", self.window.toast.text())
        self.assertEqual(page.cards, ())
        self.assertIs(self.window.follow.score, before)

    def test_library_click_while_study_active_clears_study(self) -> None:
        self.window._show_page(1)
        learning = self.window.learning_page
        learning.open_stage(3)
        stage = stage_by_index(3)
        item = stage.pieces[0]
        learning.practice(stage, item)
        wait(120)
        self.assertTrue(self.window._study_active)
        self.assertTrue(self.window.study_return.isVisible())

        page = self.open_library()
        self.assertTrue(self.window.study_return.isVisible())
        card = next(c for c in page.cards if c.piece.title == "小星星（片段）")
        card.activate()
        wait(120)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        self.assertFalse(self.window._study_active)
        self.assertFalse(self.window.study_return.isVisible())
        self.assertEqual(self.window.follow.score.title, "小星星（片段）")
        self.assertEqual(self.window.follow.index, 0)

    def test_new_piece_learning_handoff_loads_its_score(self) -> None:
        self.window._show_page(1)
        learning = self.window.learning_page
        learning.open_stage(3)
        stage = stage_by_index(3)
        item = next(i for i in stage.pieces if i.name == "欢乐颂")
        learning.practice(stage, item)
        wait(120)
        self.assertTrue(self.window._study_active)
        self.assertEqual(self.window.follow.score.title, "欢乐颂")
        self.assertTrue(self.window.study_return.isVisible())

    def test_two_hand_card_loads_and_first_chord_judges(self) -> None:
        page = self.open_library()
        card = next(
            c for c in page.cards if c.piece.title == "欢乐颂 · 双手版"
        )
        self.assertTrue(card.piece.playable)
        card.activate()
        wait(100)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        follow = self.window.follow
        self.assertEqual(follow.score.title, "欢乐颂 · 双手版")
        self.assertEqual(len(follow._onset_indices()), 2)
        inst = self.window.instrument
        follow.note_on(inst.bar_for_midi(76))
        follow.note_on(inst.bar_for_midi(67))
        self.assertEqual((follow.hits, follow.misses), (2, 0))
        self.assertEqual(follow.index, 2)
        self.assertEqual(follow.next_note.midi, 76)

    def test_failed_load_does_not_end_study_session(self) -> None:
        self.window._show_page(1)
        learning = self.window.learning_page
        learning.open_stage(3)
        stage = stage_by_index(3)
        learning.practice(stage, stage.pieces[0])
        wait(120)
        before = self.window.follow.score
        broken = self.root / "broken.musicxml"
        write_broken_musicxml(broken)
        loaded = self.window._load_score_file(str(broken), announce=False)
        wait(60)
        self.assertFalse(loaded)
        self.assertTrue(self.window._study_active)
        self.assertTrue(self.window.study_return.isVisible())
        self.assertIs(self.window.follow.score, before)
        self.assertIn("谱面载入失败", self.window.toast.text())

    def test_missing_library_root_does_not_break_startup(self) -> None:
        self.window.close()
        wait(80)
        missing = self.root / "missing" / "scores"
        self.window = make_window(self.root, library_root=missing)
        page = self.open_library()
        self.assertEqual(len(page.cards), page.registry.counts()["ready"])
        self.assertIn("小星星（片段）", [c.piece.title for c in page.cards])
        self.assertTrue(all(c.piece.playable for c in page.cards))
        self.assertFalse(missing.exists())


    def test_favorite_toggle_and_favorites_view(self) -> None:
        page = self.open_library()
        card = page.cards[0]

        card.favorite_button.click()
        wait(40)

        self.assertTrue(card.favorite)
        self.assertTrue(page.meta.is_favorite(card.piece.key))
        saved = LibraryMeta.load(page.meta_path)
        self.assertTrue(saved.is_favorite(card.piece.key))

        page.set_view(VIEW_FAVORITES)
        wait(40)
        self.assertEqual([c.piece.key for c in page.cards], [card.piece.key])

    def test_tags_persist_and_join_search(self) -> None:
        page = self.open_library()
        piece = page.cards[0].piece

        page.set_piece_tags(piece, ["演出", "入门"])
        wait(40)
        self.assertEqual(page.meta.tags_for(piece.key), ("演出", "入门"))
        self.assertEqual(
            LibraryMeta.load(page.meta_path).tags_for(piece.key),
            ("演出", "入门"),
        )

        page.set_query("演出")
        wait(40)
        self.assertIn(piece.key, [card.piece.key for card in page.cards])

        page.set_query("没有这个标签")
        wait(40)
        self.assertEqual(page.cards, ())

    def test_recent_view_records_an_opened_score(self) -> None:
        page = self.open_library()
        card = page.cards[0]

        card.activate()
        wait(80)
        page.set_view(VIEW_RECENT)
        wait(40)

        self.assertEqual([c.piece.key for c in page.cards], [card.piece.key])

    def test_image_card_opens_display_only_sheet(self) -> None:
        imports = self.root / "scores"
        imports.mkdir(parents=True, exist_ok=True)
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(QColor("#ffffff"))
        self.assertTrue(image.save(str(imports / "cover.png")))
        page = self.open_library()
        page.refresh()
        page.set_view(VIEW_IMPORTED)
        wait(60)

        card = next(c for c in page.cards if c.piece.status == "display")
        card.activate()
        wait(100)

        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        self.assertTrue(self.window.perform.score.canvas.has_image)
        self.assertIn(card.piece.key, page.meta.recent)

    def test_pdf_card_is_not_playable(self) -> None:
        imports = self.root / "scores"
        imports.mkdir(parents=True, exist_ok=True)
        (imports / "notes.pdf").write_bytes(b"%PDF-1.4\n")
        page = self.open_library()
        page.refresh()
        page.set_view(VIEW_IMPORTED)
        wait(60)

        card = next(c for c in page.cards if c.piece.status == "display")
        card.activate()
        wait(40)

        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIn("仅显示", self.window.toast.text())

    def test_removing_an_import_clears_its_metadata(self) -> None:
        page = self.open_library()
        imports = self.root / "scores"
        write_musicxml(imports / "song.musicxml", title="Song")
        page.refresh()
        page.set_view(VIEW_IMPORTED)
        wait(60)
        card = page.cards[0]

        page.toggle_favorite(card.piece, True)
        page.set_piece_tags(card.piece, ["演出"])
        page.record_recent(card.piece)
        page.remove_piece(card.piece, confirm=False)
        wait(60)

        self.assertNotIn(card.piece.key, page.meta.favorites)
        self.assertEqual(page.meta.tags_for(card.piece.key), ())
        self.assertNotIn(card.piece.key, page.meta.recent)
        self.assertFalse((imports / "song.musicxml").exists())

    def test_invalid_image_keeps_the_current_score(self) -> None:
        page = self.open_library()
        before = self.window.follow.score
        self.assertIsNotNone(before)

        imports = self.root / "scores"
        imports.mkdir(parents=True, exist_ok=True)
        (imports / "broken.png").write_bytes(b"not an image")
        page.refresh()
        page.set_view(VIEW_IMPORTED)
        wait(60)
        card = next(c for c in page.cards if c.piece.status == "display")

        card.activate()
        wait(60)

        self.assertIs(self.window.follow.score, before)
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertIn("无法读取", self.window.toast.text())

    def test_watch_refreshes_when_a_new_file_appears(self) -> None:
        page = self.open_library()
        write_musicxml(self.root / "scores" / "nested" / "new.musicxml")
        page.watch_now()
        wait(500)
        page.set_view(VIEW_IMPORTED)
        wait(40)

        self.assertIn("Test", [card.piece.title for card in page.cards])


if __name__ == "__main__":
    unittest.main()
