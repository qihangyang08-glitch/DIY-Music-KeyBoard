"""Content mapping: curriculum/library opens apply a preset and restore it."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.curriculum import SCORE_DIR, stage_by_index
from app.core.mapping import MappingSpec
from app.ui.main_window import MainWindow

SPLIT_ITEM = "左右分区 · 8 小节"


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def make_window(root: Path) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        library_root=root / "scores",
        projects_root=root / "projects",
        prefs_path=root / "score_prefs.json",
        library_watch=False,
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(160)
    return window


class ContentMappingWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)
        self.stage = stage_by_index(5)
        self.item = next(
            item for item in self.stage.trainings if item.name == SPLIT_ITEM
        )

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def user_mapping(self) -> tuple:
        inst = self.window.instrument
        return (
            inst.preset_index,
            inst.octave,
            inst.transpose,
            inst.auto_follow,
        )

    def set_user_mapping(self) -> tuple:
        inst = self.window.instrument
        inst.set_preset(1)      # C 大调, not the split preset
        inst.set_octave(1)
        inst.set_transpose(1)
        wait(40)
        return self.user_mapping()

    def open_item(self, item=None):
        self.window._show_page(1)
        self.window.learning_page.open_stage(5)
        wait(100)
        self.window.learning_page.practice(self.stage, item or self.item)
        wait(120)
        return self.window.follow

    def test_split_item_applies_its_declared_mapping(self) -> None:
        self.set_user_mapping()
        follow = self.open_item()

        inst = self.window.instrument
        self.assertTrue(self.window._study_active)
        self.assertEqual(inst.current_preset.key, "content")
        self.assertEqual(inst.current_preset.label_cn, "左右分区")
        self.assertEqual(
            inst.current_preset.range_label(0), "C3–D#4 + C5–D#6"
        )
        self.assertEqual((inst.octave, inst.transpose), (0, 0))
        self.assertEqual(inst.midi_for_key(1), 48)    # C3, left half
        self.assertEqual(inst.midi_for_key(17), 72)   # C5, right half
        self.assertIn("左右分区", self.window.map_chip.text())
        self.assertIsNotNone(follow.window_plan)
        self.assertEqual(
            sum(s.unplayable for s in follow.window_plan.segments), 0
        )

    def test_returning_restores_the_user_mapping(self) -> None:
        before = self.set_user_mapping()
        self.open_item()

        self.window._return_to_study()
        wait(120)

        self.assertFalse(self.window._study_active)
        self.assertEqual(self.user_mapping(), before)
        self.assertEqual(self.window.instrument.current_preset.key, "cmajor")
        self.assertTrue(
            self.window.perform._preset_buttons[1].isChecked()
        )

    def test_loading_another_score_restores_the_user_mapping(self) -> None:
        before = self.set_user_mapping()
        self.open_item()

        self.window._load_score_file(
            str(SCORE_DIR / "xiaoxingxing.musicxml"), announce=False
        )
        wait(120)

        self.assertFalse(self.window._study_active)
        self.assertEqual(self.user_mapping(), before)

    def test_item_without_mapping_leaves_the_user_mapping_alone(self) -> None:
        before = self.set_user_mapping()
        item = next(
            item
            for item in self.stage.trainings
            if item.name == "慢速合手 · 50%"
        )

        self.open_item(item)
        self.window._return_to_study()
        wait(120)

        self.assertEqual(self.user_mapping(), before)
        self.assertEqual(
            self.window.instrument.current_preset.key, "cmajor"
        )

    def open_library_card(self, title: str):
        self.window._show_page(2)
        wait(120)
        card = next(
            card
            for card in self.window.library_page.cards
            if card.piece.title == title
        )
        card.activate()
        wait(120)
        return card

    def test_library_card_applies_the_curriculum_mapping(self) -> None:
        self.set_user_mapping()

        card = self.open_library_card("左右分区 · 8 小节")

        inst = self.window.instrument
        self.assertFalse(self.window._study_active)
        self.assertEqual(inst.current_preset.key, "content")
        self.assertEqual(inst.current_preset.label_cn, "左右分区")
        self.assertEqual(
            inst.current_preset.range_label(0), "C3–D#4 + C5–D#6"
        )
        self.assertEqual((inst.octave, inst.transpose), (0, 0))
        self.assertEqual(inst.midi_for_key(1), 48)
        self.assertEqual(inst.midi_for_key(17), 72)
        self.assertIsNotNone(card.mapping_label)
        self.assertIn("自动分区", card.mapping_label.text())
        self.assertFalse(self.window.perform.split_hint.isHidden())
        self.assertIn("分区 16", self.window.perform.split_hint.text())
        self.assertIn("拖动", self.window.perform.split_hint.text())
        self.assertIn("乐句", self.window.perform.auto_switch.toolTip())
        # A content mapping has no chip of its own; the old preset must not
        # stay highlighted and contradict the displayed mapping name.
        self.assertFalse(
            any(
                btn.isChecked()
                for btn in self.window.perform._preset_buttons
            )
        )

    def test_library_switch_restores_the_user_mapping(self) -> None:
        before = self.set_user_mapping()

        self.open_library_card("左右分区 · 8 小节")
        card = self.open_library_card("小星星（片段）")
        wait(120)
        self.assertIsNone(card.mapping_label)
        self.assertTrue(self.window.perform.split_hint.isHidden())

        self.assertEqual(self.user_mapping(), before)
        self.assertEqual(
            self.window.instrument.current_preset.key, "cmajor"
        )

    def drag_split_to(self, bar: int) -> None:
        band = self.window.perform.band
        line = band.split_line_x()
        self.assertIsNotNone(line)
        y = band.height() - 20
        QTest.mousePress(
            band,
            Qt.MouseButton.LeftButton,
            pos=QPoint(int(line), y),
        )
        rect = band._slot_rects()[bar - 1]
        x = int(rect.center().x()) - 1
        QTest.mouseMove(band, QPoint(x, y))
        QTest.mouseRelease(
            band,
            Qt.MouseButton.LeftButton,
            pos=QPoint(x, y),
        )
        wait(80)

    def test_dragging_the_split_line_moves_and_saves_it(self) -> None:
        self.open_library_card("左右分区 · 8 小节")
        self.assertEqual(self.window.instrument.split_bar, 16)

        self.drag_split_to(20)

        self.assertEqual(self.window.instrument.split_bar, 20)
        self.assertEqual(
            self.window.score_prefs.split_bar("builtin:split_hands_8bars"),
            20,
        )
        self.assertIn("键 20 / 21 之间", self.window.toast.text())

    def test_reset_restores_the_declared_split_and_clears_the_pref(self) -> None:
        self.open_library_card("左右分区 · 8 小节")
        self.drag_split_to(20)
        self.assertEqual(self.window.instrument.split_bar, 20)
        self.assertFalse(self.window.perform.split_reset.isHidden())

        self.window.perform.split_reset.click()
        wait(80)

        self.assertEqual(self.window.instrument.split_bar, 16)
        self.assertIsNone(
            self.window.score_prefs.split_bar("builtin:split_hands_8bars")
        )
        self.assertIn("默认分区", self.window.toast.text())

        self.open_library_card("小星星（片段）")
        self.open_library_card("左右分区 · 8 小节")
        self.assertEqual(self.window.instrument.split_bar, 16)

    def test_dragged_split_bar_is_restored_per_score(self) -> None:
        self.open_library_card("左右分区 · 8 小节")
        self.drag_split_to(20)

        self.open_library_card("小星星（片段）")
        self.assertIsNone(self.window.instrument.split_bar)

        self.open_library_card("左右分区 · 8 小节")
        self.assertEqual(self.window.instrument.split_bar, 20)

    def test_structured_mapping_offsets_apply_and_restore(self) -> None:
        before = self.set_user_mapping()
        spec = MappingSpec(
            base=60,
            steps=(0, 2, 4, 5, 7, 9, 11),
            octave=1,
            transpose=2,
            label="测试映射",
        )

        inst = self.window.instrument
        self.assertTrue(inst.begin_content_mapping(spec))
        wait(60)
        self.assertEqual(inst.current_preset.key, "content")
        self.assertEqual(inst.current_preset.label_cn, "测试映射")
        self.assertEqual((inst.octave, inst.transpose), (1, 2))

        self.assertTrue(inst.end_content_mapping())
        wait(60)
        self.assertEqual(self.user_mapping(), before)

    def test_user_preset_change_wins_during_a_content_session(self) -> None:
        before = self.set_user_mapping()
        inst = self.window.instrument
        inst.begin_content_mapping(
            MappingSpec(base=60, steps=(0, 2, 4, 5, 7, 9, 11), label="测试")
        )
        wait(60)

        inst.set_preset(0)
        wait(60)
        self.assertEqual(inst.current_preset.key, "chromatic")

        inst.end_content_mapping()
        wait(60)
        self.assertEqual(self.user_mapping(), before)

    def test_unknown_mapping_key_is_ignored(self) -> None:
        before = self.set_user_mapping()

        self.assertFalse(
            self.window.instrument.begin_content_mapping("not-a-preset")
        )
        self.assertEqual(self.user_mapping(), before)
        self.assertFalse(self.window.instrument.end_content_mapping())

    def test_switching_mapped_items_keeps_the_original_snapshot(self) -> None:
        before = self.set_user_mapping()
        self.open_item()

        # Opening another mapped item reuses the pre-session snapshot instead
        # of saving the already-overridden state as "the user's mapping".
        self.window.learning_page.practice(self.stage, self.item)
        wait(120)
        self.window._return_to_study()
        wait(120)

        self.assertEqual(self.user_mapping(), before)

    def test_auto_follow_restores_and_temporary_changes_are_discarded(self) -> None:
        inst = self.window.instrument
        inst.set_preset(1)
        if not inst.auto_follow:
            inst.toggle_auto_follow()
        before = self.user_mapping()

        self.open_item()
        # The learner is allowed to change the mapping mid-practice; the
        # original snapshot must still win when the session ends.
        inst.set_preset(0)
        inst.set_octave(2)
        wait(40)
        self.window._return_to_study()
        wait(120)

        self.assertEqual(inst.preset_index, before[0])
        self.assertEqual(inst.transpose, before[2])
        self.assertEqual(inst.auto_follow, before[3])
        self.assertEqual(inst.current_preset.key, "cmajor")

    def test_split_practice_is_fully_reachable_and_records_40_notes(self) -> None:
        follow = self.open_item()
        for note in list(follow.score.notes):
            bar = self.window.instrument.bar_for_midi(note.midi)
            self.assertIsNotNone(bar, note.name)
            follow.note_on(bar)

        self.assertEqual((follow.hits, follow.misses), (40, 0))
        self.window._return_to_study()
        wait(120)

        result = self.window.learning_progress.result_for(5, SPLIT_ITEM)
        self.assertIsNotNone(result)
        self.assertEqual((result.hits, result.total), (40, 40))
        self.assertTrue(result.completed)


if __name__ == "__main__":
    unittest.main()
