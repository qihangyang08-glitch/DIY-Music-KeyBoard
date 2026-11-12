"""UI smoke tests for the stage 2 metronome rhythm drill."""

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


class RhythmWindowTest(unittest.TestCase):
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
        self.stage = stage_by_index(2)
        self.item = self.stage.trainings[0]

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_drill(self, item=None):
        self.window._show_page(1)
        self.window.learning_page.open_stage(2)
        self.window.learning_page.practice(self.stage, item or self.item)
        wait(150)
        page = self.window.drill_page
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertTrue(page.is_rhythm)
        return page

    def finish_cleanly(self, page) -> None:
        page.start_rhythm()
        page._rhythm_timer.stop()  # drive the pure session with exact times
        session = page._session
        for event in session.spec.note_events:
            when = session.started_at + (
                session.spec.count_in_beats + event.beat
            ) * session.spec.beat_seconds
            session.tick(when)
            result = session.press(when)
            self.assertIsNotNone(result)
            self.assertTrue(result.hit)
        end = session.started_at + (
            session.spec.count_in_beats + session.spec.total_beats
        ) * session.spec.beat_seconds + 1.0
        session.tick(end)
        page._rhythm_tick()
        wait(50)

    def test_stage2_has_seven_ready_rhythm_items(self) -> None:
        ready = [item for item in self.stage.trainings if item.ready]
        self.assertEqual(len(ready), 7)
        self.assertFalse(self.window.learning_page.stage_done(self.stage))

    def test_six_eight_item_shows_its_meter_and_runs_cleanly(self) -> None:
        item = next(
            item for item in self.stage.trainings if item.name == "6/8 复拍子"
        )
        page = self.open_drill(item)
        self.assertIn("6/8", page._title.text())
        self.finish_cleanly(page)
        self.assertTrue(page.showing_summary)
        detail = page._summary_detail.text()
        self.assertIn("6/8", detail)
        self.assertNotIn("6/4", detail)
        result = self.window.learning_progress.result_for(2, item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, result.total)

    def test_rests_and_dots_item_runs_cleanly(self) -> None:
        item = next(
            item for item in self.stage.trainings if item.name == "休止与附点"
        )
        page = self.open_drill(item)
        self.assertIn("休止与附点", page._title.text())
        self.finish_cleanly(page)
        self.assertTrue(page.showing_summary)

        result = self.window.learning_progress.result_for(2, item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(result.hits, 9)
        self.assertEqual(result.total, 9)

    def test_rhythm_page_and_clean_run(self) -> None:
        original_preset = self.window.instrument.preset_index
        page = self.open_drill()
        self.assertTrue(page.is_rhythm)
        self.assertTrue(self.window.instrument.mapping_locked)
        self.assertIn("节奏", self.window.next_status_value.text())
        self.assertEqual(self.window.instrument.preset_index, original_preset)
        self.assertFalse(self.window.map_chip.isEnabled())
        self.assertIs(
            page._body_stack.currentWidget(), page._rhythm_view
        )
        self.finish_cleanly(page)
        self.assertTrue(page.showing_summary)
        result = self.window.learning_progress.result_for(2, self.item.name)
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertGreater(result.avg_ms, 0)
        self.assertGreater(result.best_streak, 0)

        page.leave()
        wait(120)
        self.assertIs(self.window.stack.currentWidget(), self.window.learning_page)
        self.assertTrue(self.window.map_chip.isEnabled())
        self.assertFalse(self.window.instrument.mapping_locked)
        self.assertNotIn("节奏", self.window.next_status_value.text())
        self.assertEqual(self.window.instrument.preset_index, original_preset)

    def test_course_action_opens_rhythm(self) -> None:
        self.window._show_page(1)
        self.window.learning_page.open_stage(2)
        self.assertTrue(
            self.window.learning_page.open_course(self.stage.guides[0].title)
        )
        self.window.learning_page.practice(self.stage, self.stage.first_practice())
        wait(120)
        self.assertTrue(self.window.drill_page.is_rhythm)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.drill_page
        )
        self.window.drill_page.leave()
        wait(100)
        self.assertEqual(self.window.learning_page._view, "course")

    def test_enter_starts_and_stops(self) -> None:
        page = self.open_drill()
        QTest.keyClick(self.window, Qt.Key.Key_Return)
        wait(80)
        self.assertTrue(page.rhythm_running)
        QTest.keyClick(self.window, Qt.Key.Key_Return)
        wait(80)
        self.assertFalse(page.rhythm_running)
        page.leave()
        wait(80)

    def test_stop_then_leave_records_partial(self) -> None:
        page = self.open_drill()
        page.start_rhythm()
        page._rhythm_timer.stop()
        session = page._session
        first = session.spec.events[0]
        when = session.started_at + (
            session.spec.count_in_beats + first.beat
        ) * session.spec.beat_seconds
        session.tick(when)
        self.assertTrue(session.press(when).hit)
        page.stop_rhythm()
        page.leave()
        wait(100)
        result = self.window.learning_progress.result_for(2, self.item.name)
        self.assertIsNotNone(result)
        self.assertFalse(result.completed)
        self.assertEqual(result.hits, 1)


if __name__ == "__main__":
    unittest.main()
