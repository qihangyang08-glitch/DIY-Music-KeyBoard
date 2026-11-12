"""UI-level smoke tests for the stage 1 note drill.

These are not pixel tests; they drive MainWindow with WA_DontShowOnScreen (the
same mode as the dev screenshots, because QT_QPA_PLATFORM=offscreen has no
fonts on Windows) and assert the state transitions that are easy to break:
mapping entry/exit, one verdict per 20 ms batch, result recording, and the
mapping lock.

Run from pc/:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.curriculum import stage_by_index
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class DrillWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)
        self.stage = stage_by_index(1)
        self.item = self.stage.trainings[0]

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_drill(self, item=None, stage=None):
        stage = stage or self.stage
        self.window._show_page(1)
        self.window.learning_page.open_stage(stage.index)
        self.window.learning_page.practice(stage, item or self.item)
        wait(120)
        self.assertIs(self.window.stack.currentWidget(), self.window.drill_page)
        self.assertTrue(self.window.drill_page.is_active)
        return self.window.drill_page

    def answer_current(self, page, wait_after: int = 380) -> None:
        current = page._session.current
        self.assertIsNotNone(current)
        page.note_batch([current.midi])
        wait(wait_after)

    def test_mapping_result_and_restore(self) -> None:
        original = (
            self.window.instrument.preset_index,
            self.window.instrument.octave,
            self.window.instrument.transpose,
            self.window.instrument.auto_follow,
        )
        page = self.open_drill()
        self.assertTrue(self.window.instrument.mapping_locked)
        self.assertFalse(self.window.map_chip.isEnabled())
        self.assertEqual(self.window.instrument.current_preset.key, "drill")
        self.assertEqual(self.window.instrument.octave, 0)
        self.assertEqual(self.window.instrument.transpose, 0)
        self.assertEqual(self.window.instrument.bar_for_midi(60), 1)
        self.assertEqual(self.window.instrument.bar_for_midi(72), 13)

        for _ in range(10):
            self.answer_current(page)
        self.assertTrue(page.showing_summary)
        result = self.window.learning_progress.result_for(1, self.item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, 10)
        self.assertEqual(result.total, 10)
        # Stage 1 has five ready drills; finishing one is not the whole stage.
        self.assertFalse(self.window.learning_page.stage_done(self.stage))
        self.assertEqual(self.stage.ready_count, 5)

        page.leave()
        wait(150)
        self.assertIs(self.window.stack.currentWidget(), self.window.learning_page)
        self.assertEqual(self.window.learning_page._view, "stage")
        self.assertFalse(self.window.instrument.mapping_locked)
        self.assertTrue(self.window.map_chip.isEnabled())
        self.assertEqual(
            (
                self.window.instrument.preset_index,
                self.window.instrument.octave,
                self.window.instrument.transpose,
                self.window.instrument.auto_follow,
            ),
            original,
        )

    def test_chord_is_one_verdict(self) -> None:
        page = self.open_drill()
        current = page._session.current
        wrong = next(m for m in (60, 62, 64, 65, 67, 69, 71, 72) if m != current.midi)
        # Correct + wrong in the same 20 ms batch: one hit, no miss.
        page.note_batch([wrong, current.midi])
        self.assertEqual(page._session.hits, 1)
        self.assertEqual(page._session.misses, 0)
        self.assertEqual(page._session.index, 1)
        wait(380)
        # Two wrong notes in one batch: one miss, still the same question.
        current = page._session.current
        wrongs = [m for m in (60, 62, 64, 65, 67, 69, 71, 72) if m != current.midi][:2]
        page.note_batch(wrongs)
        self.assertEqual(page._session.misses, 1)
        self.assertEqual(page._session.index, 1)

    def test_accidental_drill_shows_flat_and_key_hint(self) -> None:
        item = next(
            item for item in self.stage.trainings
            if item.name == "临时记号 · 升与降"
        )
        page = self.open_drill(item)
        self.assertIn("升与降", page._title.text())

        saw_flat = False
        for _ in range(10):
            question = page._session.current
            self.assertIsNotNone(question)
            page.note_batch([question.midi])
            if question.accidental == "♭":
                saw_flat = True
                feedback = page._feedback.text()
                self.assertIn(question.name, feedback)
                self.assertIn("键面", feedback)
            wait(380)
        self.assertTrue(saw_flat)
        self.assertTrue(page.showing_summary)
        page.leave()
        wait(120)

    def test_bass_clef_drill_maps_c3_and_completes(self) -> None:
        stage4 = stage_by_index(4)
        item = next(
            item
            for item in stage4.trainings
            if item.name == "低音谱号 · C3–C4"
        )
        page = self.open_drill(item, stage4)
        self.assertEqual(self.window.instrument.current_preset.key, "drill")
        self.assertEqual(self.window.instrument.bar_for_midi(48), 1)
        self.assertEqual(self.window.instrument.bar_for_midi(60), 13)
        self.assertIn("C3", page._range_hint.text())
        self.assertIn("C4", page._range_hint.text())

        for _ in range(10):
            self.answer_current(page)
        self.assertTrue(page.showing_summary)
        result = self.window.learning_progress.result_for(4, item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, 10)
        page.leave()
        wait(120)

    def test_stage0_middle_c_onboarding_completes(self) -> None:
        stage0 = stage_by_index(0)
        item = next(
            item for item in stage0.trainings if item.name == "找到中央 C"
        )
        page = self.open_drill(item, stage0)
        self.assertTrue(page.is_onboarding)
        self.assertEqual(self.window.instrument.bar_for_midi(60), 1)
        self.assertEqual(self.window.instrument.bar_for_midi(64), 5)

        for midi in (60, 62, 64, 60):
            page.note_batch([midi])
            wait(380)
        self.assertTrue(page.showing_summary)
        result = self.window.learning_progress.result_for(0, item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, 4)
        self.assertEqual(result.total, 4)

        page.leave()
        wait(120)
        self.assertFalse(self.window.instrument.mapping_locked)

    def test_stage0_sustain_and_panic_onboarding(self) -> None:
        stage0 = stage_by_index(0)
        item = next(
            item
            for item in stage0.trainings
            if item.name == "延音与全部静音"
        )
        page = self.open_drill(item, stage0)
        self.assertTrue(page.is_onboarding)

        QTest.keyPress(self.window, Qt.Key.Key_Shift)
        wait(380)
        self.assertTrue(self.window.instrument.sustain)
        self.assertEqual(page._session.index, 1)

        page.note_batch([60])
        wait(380)
        self.assertEqual(page._session.index, 2)

        QTest.keyRelease(self.window, Qt.Key.Key_Shift)
        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        wait(420)
        self.assertTrue(page.showing_summary)
        self.assertFalse(self.window.instrument.sustain)

        result = self.window.learning_progress.result_for(0, item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, 3)
        self.assertEqual(result.total, 3)

        page.leave()
        wait(120)
        self.assertFalse(self.window.instrument.mapping_locked)

    def test_summary_enter_retries_without_mouse(self) -> None:
        page = self.open_drill()
        for _ in range(10):
            self.answer_current(page)
        self.assertTrue(page.showing_summary)
        QTest.keyClick(self.window, Qt.Key.Key_Return)
        wait(150)
        self.assertFalse(page.showing_summary)
        self.assertEqual(page._session.index, 0)
        self.assertEqual(page._session.hits, 0)
        page.leave()
        wait(120)

    def test_summary_escape_leaves_without_mouse(self) -> None:
        page = self.open_drill()
        for _ in range(10):
            self.answer_current(page)
        self.assertTrue(page.showing_summary)
        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        wait(150)
        self.assertIs(self.window.stack.currentWidget(), self.window.learning_page)
        self.assertFalse(self.window.instrument.mapping_locked)
        self.assertTrue(self.window.map_chip.isEnabled())

    def test_mapping_lock_and_auto_follow_restore(self) -> None:
        inst = self.window.instrument
        if not inst.auto_follow:
            inst.toggle_auto_follow()
        inst.set_octave(1)
        inst.set_transpose(1)
        wait(80)
        original = (
            inst.preset_index,
            inst.octave,
            inst.transpose,
            inst.auto_follow,
        )
        page = self.open_drill()
        self.assertFalse(inst.auto_follow)
        self.assertEqual(inst.octave, 0)
        self.assertEqual(inst.transpose, 0)
        inst.cycle_preset()
        inst.set_octave(1)
        inst.set_transpose(1)
        inst.toggle_auto_follow()
        self.assertEqual(inst.current_preset.key, "drill")
        self.assertEqual(inst.octave, 0)
        self.assertEqual(inst.transpose, 0)
        self.assertFalse(inst.auto_follow)
        page.leave()
        wait(150)
        self.assertEqual(
            (inst.preset_index, inst.octave, inst.transpose, inst.auto_follow),
            original,
        )


if __name__ == "__main__":
    unittest.main()
