"""UI smoke tests for the optional stage 1/2 exams.

The exam reuses the drill page, but its result is stored separately from the
ordinary practice archive. These tests cover the hand-off, both pass paths,
the failure path, and the promise that an exam never completes stage items.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.core.curriculum import stage_by_index
from app.core.drill import note_prompt
from app.core.exam import STAGE1_EXAM, STAGE2_EXAM
from app.ui.drill_page import staff_note_y
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class ExamWindowTest(unittest.TestCase):
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
        self.stage1 = stage_by_index(1)
        self.stage2 = stage_by_index(2)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def visible_texts(self) -> list[str]:
        return [
            label.text()
            for label in self.window.findChildren(QLabel)
            if label.isVisible()
        ]

    def button_texts(self) -> list[str]:
        return [
            button.text()
            for button in self.window.findChildren(QPushButton)
            if button.isVisible()
        ]

    def open_exam(self, stage):
        self.window._show_page(1)
        self.window.learning_page.open_stage(stage.index)
        self.window.learning_page.start_exam(stage)
        wait(120)
        page = self.window.drill_page
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertTrue(page.is_active)
        return page

    def answer_correct(self, page) -> None:
        question = page._session.current
        self.assertIsNotNone(question)
        page.note_batch([question.midi])
        page._advance_timer.stop()
        page._after_correct()

    def answer_wrong_then_correct(self, page) -> None:
        question = page._session.current
        self.assertIsNotNone(question)
        page.note_batch([question.midi + 1])
        self.assertTrue(page._session.revealed)
        page.note_batch([question.midi])
        page._advance_timer.stop()
        page._after_correct()

    def test_stage_view_offers_exam_only_where_one_exists(self) -> None:
        self.window._show_page(1)
        self.window.learning_page.open_stage(1)
        wait(80)
        self.assertIn("参加考核", self.button_texts())
        self.assertIn("考核 · 可选，不影响普通练习", self.visible_texts())

        self.window.learning_page.open_stage(0)
        wait(80)
        self.assertNotIn("参加考核", self.button_texts())

    def test_starting_exam_opens_20_question_drill_without_practice_record(self) -> None:
        page = self.open_exam(self.stage1)
        self.assertIsNotNone(page._exam)
        self.assertEqual(page._exam.key, STAGE1_EXAM.key)
        self.assertEqual(page._session.total, 20)
        self.assertIn("考核", page._meta.text())
        self.assertIsNone(
            self.window.learning_progress.result_for(1, STAGE1_EXAM.title)
        )
        page.leave()
        wait(80)

    def test_high_exam_notes_fit_inside_the_staff_canvas(self) -> None:
        # StaffView is 190 px high and its paint area is 178 px; the note head
        # of E6/G6 used to land above the widget and was clipped entirely.
        area = QRectF(0, 0, 600, 178)
        for midi in (84, 88, 91):
            step = note_prompt(midi).staff_step_for("treble")
            y = staff_note_y(area, step)
            self.assertGreaterEqual(y, area.top() + 5.0, midi)
            self.assertLessEqual(y, area.bottom() - 5.0, midi)

    def test_exam_rejects_a_whole_range_chord_as_first_try(self) -> None:
        page = self.open_exam(self.stage1)
        question = page._session.current
        page.note_batch(list(range(60, 92)))
        self.assertEqual(page._session.first_try, 0)
        self.assertEqual(page._session.misses, 1)
        self.assertTrue(page._session.revealed)
        # A later single correct press solves it but still is not first-try.
        page.note_batch([question.midi])
        page._advance_timer.stop()
        page._after_correct()
        self.assertEqual(page._session.first_try, 0)
        page.leave()
        wait(80)

    def test_first_try_pass_is_recorded_separately(self) -> None:
        page = self.open_exam(self.stage1)
        for _ in range(20):
            self.answer_correct(page)
        self.assertTrue(page.showing_summary)
        self.assertIn("通过", page._summary_note.text())
        self.assertEqual(page._summary_score.text(), "20/20")

        record = self.window.learning_progress.exam_for(STAGE1_EXAM.key)
        self.assertIsNotNone(record)
        self.assertTrue(record.passed)
        self.assertEqual(record.first_try, 20)
        self.assertEqual(record.attempts, 1)

        # Passing the exam does not pretend that the practice items are done.
        self.assertIsNone(
            self.window.learning_progress.result_for(
                1, self.stage1.trainings[0].name
            )
        )
        self.assertFalse(self.window.learning_page.stage_done(self.stage1))

    def test_failing_exam_keeps_a_best_effort_record(self) -> None:
        page = self.open_exam(self.stage1)
        for _ in range(5):
            self.answer_wrong_then_correct(page)
        for _ in range(15):
            self.answer_correct(page)
        self.assertTrue(page.showing_summary)
        self.assertIn("未通过", page._summary_note.text())
        self.assertEqual(page._summary_score.text(), "15/20")

        record = self.window.learning_progress.exam_for(STAGE1_EXAM.key)
        self.assertIsNotNone(record)
        self.assertFalse(record.passed)
        self.assertEqual(record.first_try, 15)
        self.assertEqual(record.attempts, 1)

    def test_abandoned_exam_is_not_an_attempt(self) -> None:
        page = self.open_exam(self.stage1)
        self.answer_correct(page)
        page.leave()
        wait(80)
        self.assertEqual(self.window.learning_progress.exams, {})

    def test_stage_2_clean_60_bpm_run_passes(self) -> None:
        page = self.open_exam(self.stage2)
        self.assertIsNotNone(page._exam)
        self.assertEqual(page._exam.key, STAGE2_EXAM.key)
        page.start_rhythm()
        page._rhythm_timer.stop()
        session = page._session
        self.assertEqual(session.spec.bpm, 60)
        for event in session.spec.note_events:
            when = session.started_at + (
                session.spec.count_in_beats + event.beat
            ) * session.spec.beat_seconds
            session.tick(when)
            self.assertTrue(session.press(when).hit)
        end = session.started_at + (
            session.spec.count_in_beats + session.spec.total_beats
        ) * session.spec.beat_seconds + 1.0
        session.tick(end)
        page._rhythm_tick()
        wait(50)

        self.assertTrue(page.showing_summary)
        self.assertIn("通过", page._summary_note.text())
        record = self.window.learning_progress.exam_for(STAGE2_EXAM.key)
        self.assertIsNotNone(record)
        self.assertTrue(record.passed)
        self.assertEqual(record.hits, 16)
        self.assertLess(record.avg_ms, 60)

    def test_stopping_right_after_last_beat_records_pass(self) -> None:
        page = self.open_exam(self.stage2)
        page.start_rhythm()
        page._rhythm_timer.stop()
        session = page._session
        for event in session.spec.note_events:
            when = session.started_at + (
                session.spec.count_in_beats + event.beat
            ) * session.spec.beat_seconds
            session.tick(when)
            self.assertTrue(session.press(when).hit)
        # Stop during the post-roll instead of waiting for the timer to end it.
        page.stop_rhythm()
        wait(50)
        self.assertTrue(page.showing_summary)
        record = self.window.learning_progress.exam_for(STAGE2_EXAM.key)
        self.assertIsNotNone(record)
        self.assertTrue(record.passed)

    def test_stage_view_shows_passed_status_after_exam(self) -> None:
        page = self.open_exam(self.stage1)
        for _ in range(20):
            self.answer_correct(page)
        page.leave()
        wait(120)
        self.window.learning_page.open_stage(1)
        wait(80)
        self.assertTrue(
            any("已通过" in text for text in self.visible_texts()),
            self.visible_texts(),
        )
        self.assertIn("重新考核", self.button_texts())


if __name__ == "__main__":
    unittest.main()
