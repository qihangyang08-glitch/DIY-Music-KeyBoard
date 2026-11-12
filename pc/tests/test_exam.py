"""Optional stage exams: specs, pass rules and local best records.

The exam is deliberately separate from ordinary practice: a failed exam never
marks a stage item incomplete, and a passed exam never replaces a practice
result. Stage 1 asks 20 staff notes and needs 16 first-try answers; stage 2
asks for a clean 60 BPM run with an average timing error below 60 ms.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.drill import DrillOutcome
from app.core.exam import (
    STAGE1_EXAM,
    STAGE2_EXAM,
    evaluate,
    exam_by_key,
    exam_spec,
)
from app.core.progress import ExamRecord, LearningProgress
from app.core.rhythm import RhythmOutcome, RhythmSession


def notes_outcome(
    *,
    total: int = 20,
    first_try: int = 16,
    hits: int | None = None,
    misses: int = 0,
    finished: bool = True,
) -> DrillOutcome:
    hits = total if hits is None else hits
    attempts = hits + misses
    return DrillOutcome(
        hits=hits,
        misses=misses,
        total=total,
        attempts=attempts,
        first_try=first_try,
        accuracy=round(100 * hits / attempts) if attempts else 0,
        avg_ms=1200,
        best_streak=first_try,
        finished=finished,
    )


def rhythm_outcome(
    *,
    total: int = 16,
    hits: int = 16,
    misses: int = 0,
    extras: int = 0,
    avg_ms: int = 42,
    finished: bool = True,
) -> RhythmOutcome:
    return RhythmOutcome(
        hits=hits,
        misses=misses,
        extras=extras,
        total=total,
        attempts=hits + misses + extras,
        first_try=0,
        accuracy=round(100 * hits / (hits + misses + extras))
        if hits + misses + extras
        else 0,
        avg_ms=avg_ms,
        best_streak=hits,
        finished=finished,
    )


class ExamSpecTest(unittest.TestCase):
    def test_only_stages_1_and_2_have_exams(self) -> None:
        self.assertIs(exam_spec(1), STAGE1_EXAM)
        self.assertIs(exam_spec(2), STAGE2_EXAM)
        self.assertIsNone(exam_spec(0))
        self.assertIsNone(exam_spec(3))
        self.assertIsNone(exam_by_key("missing"))

    def test_stage_1_exam_asks_20_distinct_staff_notes(self) -> None:
        spec = STAGE1_EXAM
        self.assertEqual(spec.kind, "notes")
        self.assertEqual(spec.drill.question_count, 20)
        self.assertEqual(spec.total, 20)
        self.assertEqual(spec.min_first_try, 16)
        prompts = spec.drill.prompt_pool
        self.assertGreaterEqual(len(prompts), 20)
        keys = {(p.midi, p.name, p.accidental) for p in prompts}
        self.assertEqual(len(keys), len(prompts), "exam pool has duplicates")
        # The pool covers the stage: C4–C6 naturals plus accidentals.
        midis = {p.midi for p in prompts}
        self.assertIn(60, midis)
        self.assertIn(84, midis)
        self.assertTrue(any(p.accidental for p in prompts))
        # The answer strip and range hint read DrillSpec.midis, not prompts.
        self.assertEqual(set(spec.drill.midis), midis)

    def test_stage_2_exam_is_a_60_bpm_clean_run(self) -> None:
        spec = STAGE2_EXAM
        self.assertEqual(spec.kind, "rhythm")
        self.assertEqual(spec.rhythm.bpm, 60)
        self.assertEqual(spec.rhythm.beats_per_bar, 4)
        self.assertEqual(spec.rhythm.bars, 4)
        self.assertEqual(spec.total, 16)
        self.assertEqual(spec.max_avg_ms, 60)


class NotesExamTest(unittest.TestCase):
    def test_eighty_percent_first_try_passes(self) -> None:
        result = evaluate(STAGE1_EXAM, notes_outcome(first_try=16))
        self.assertTrue(result.passed)
        self.assertEqual(result.first_try, 16)
        self.assertEqual(result.total, 20)

    def test_fifteen_of_twenty_fails(self) -> None:
        result = evaluate(STAGE1_EXAM, notes_outcome(first_try=15))
        self.assertFalse(result.passed)

    def test_unfinished_run_never_passes(self) -> None:
        result = evaluate(
            STAGE1_EXAM, notes_outcome(first_try=16, finished=False)
        )
        self.assertFalse(result.passed)

    def test_wrong_total_fails_even_above_threshold(self) -> None:
        result = evaluate(STAGE1_EXAM, notes_outcome(total=10, first_try=10))
        self.assertFalse(result.passed)

    def test_unanswered_notes_fail_even_if_finished_is_reported(self) -> None:
        result = evaluate(
            STAGE1_EXAM, notes_outcome(hits=19, first_try=16, finished=True)
        )
        self.assertFalse(result.passed)


class RhythmExamTest(unittest.TestCase):
    def test_average_below_60_passes(self) -> None:
        result = evaluate(STAGE2_EXAM, rhythm_outcome(avg_ms=59))
        self.assertTrue(result.passed)

    def test_average_exactly_60_fails(self) -> None:
        result = evaluate(STAGE2_EXAM, rhythm_outcome(avg_ms=60))
        self.assertFalse(result.passed)

    def test_missed_beat_fails(self) -> None:
        result = evaluate(
            STAGE2_EXAM, rhythm_outcome(hits=15, misses=1, avg_ms=20)
        )
        self.assertFalse(result.passed)

    def test_extra_press_fails(self) -> None:
        result = evaluate(STAGE2_EXAM, rhythm_outcome(extras=1, avg_ms=20))
        self.assertFalse(result.passed)

    def test_empty_run_does_not_claim_zero_deviation(self) -> None:
        result = evaluate(
            STAGE2_EXAM, rhythm_outcome(hits=0, misses=16, avg_ms=0)
        )
        self.assertFalse(result.passed)
        self.assertIn("平均偏差 —", result.summary)

    def test_unfinished_or_wrong_length_fails(self) -> None:
        self.assertFalse(
            evaluate(STAGE2_EXAM, rhythm_outcome(finished=False)).passed
        )
        self.assertFalse(
            evaluate(STAGE2_EXAM, rhythm_outcome(total=8, hits=8)).passed
        )


class RhythmExamSessionTest(unittest.TestCase):
    """The session, not just the outcome, decides when a run is complete."""

    def _started(self) -> RhythmSession:
        session = RhythmSession(STAGE2_EXAM.rhythm)
        session.start(100.0)
        return session

    def _hit_all(self, session: RhythmSession) -> None:
        spec = session.spec
        for event in spec.note_events:
            when = 100.0 + (
                spec.count_in_beats + event.beat
            ) * spec.beat_seconds
            session.tick(when)
            self.assertIsNotNone(session.press(when))

    def test_stopping_after_the_last_beat_finishes_the_run(self) -> None:
        session = self._started()
        self._hit_all(session)
        session.stop()
        self.assertTrue(session.finished)
        self.assertTrue(evaluate(STAGE2_EXAM, session.outcome()).passed)

    def test_stopping_mid_run_does_not_finish_it(self) -> None:
        session = self._started()
        spec = session.spec
        for event in spec.note_events[:5]:
            when = 100.0 + (
                spec.count_in_beats + event.beat
            ) * spec.beat_seconds
            session.tick(when)
            session.press(when)
        session.stop()
        self.assertFalse(session.finished)

    def test_average_uses_floor_not_rounding(self) -> None:
        session = self._started()
        spec = session.spec
        for event, error_ms in zip(spec.note_events[:2], (59, 60)):
            when = (
                100.0
                + (spec.count_in_beats + event.beat) * spec.beat_seconds
                + error_ms / 1000.0
            )
            session.tick(when)
            session.press(when)
        # True mean 59.5 ms meets "<60 ms"; rounding to 60 would fail it.
        self.assertEqual(session.outcome().avg_ms, 59)


class ExamProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "learning.json"
        self.progress = LearningProgress(path=self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_round_trips_through_disk(self) -> None:
        result = evaluate(STAGE1_EXAM, notes_outcome(first_try=18))
        record = self.progress.record_exam(result)
        self.assertIsInstance(record, ExamRecord)
        self.assertTrue(record.passed)
        self.assertEqual(record.first_try, 18)
        self.assertEqual(record.attempts, 1)

        loaded = LearningProgress.load(self.path)
        stored = loaded.exam_for(STAGE1_EXAM.key)
        self.assertIsNotNone(stored)
        self.assertTrue(stored.passed)
        self.assertEqual(stored.first_try, 18)
        self.assertEqual(stored.attempts, 1)

    def test_passed_result_beats_a_later_failure(self) -> None:
        good = evaluate(STAGE1_EXAM, notes_outcome(first_try=17))
        bad = evaluate(STAGE1_EXAM, notes_outcome(first_try=15))
        self.progress.record_exam(good)
        record = self.progress.record_exam(bad)
        self.assertTrue(record.passed)
        self.assertEqual(record.first_try, 17)
        self.assertEqual(record.attempts, 2)

    def test_better_notes_score_replaces_previous_best(self) -> None:
        self.progress.record_exam(
            evaluate(STAGE1_EXAM, notes_outcome(first_try=16))
        )
        record = self.progress.record_exam(
            evaluate(STAGE1_EXAM, notes_outcome(first_try=19))
        )
        self.assertEqual(record.first_try, 19)
        self.assertEqual(record.attempts, 2)

    def test_better_rhythm_average_replaces_previous_best(self) -> None:
        self.progress.record_exam(
            evaluate(STAGE2_EXAM, rhythm_outcome(avg_ms=55))
        )
        record = self.progress.record_exam(
            evaluate(STAGE2_EXAM, rhythm_outcome(avg_ms=31))
        )
        self.assertEqual(record.avg_ms, 31)
        self.assertEqual(record.attempts, 2)

    def test_rhythm_failed_run_with_more_hits_wins(self) -> None:
        # A nearly-empty run can show a tiny average from one lucky hit; the
        # displayed "best" must still be the run with more hit beats.
        self.progress.record_exam(
            evaluate(
                STAGE2_EXAM,
                rhythm_outcome(hits=1, misses=15, avg_ms=1),
            )
        )
        record = self.progress.record_exam(
            evaluate(
                STAGE2_EXAM,
                rhythm_outcome(hits=15, misses=1, avg_ms=80),
            )
        )
        self.assertFalse(record.passed)
        self.assertEqual(record.hits, 15)
        self.assertEqual(record.attempts, 2)

    def test_failed_exam_does_not_touch_practice_results(self) -> None:
        self.progress.record_practice(1, "音名闪卡 · C4–C5", 10, 0, 10)
        self.progress.record_exam(
            evaluate(STAGE1_EXAM, notes_outcome(first_try=4))
        )
        result = self.progress.result_for(1, "音名闪卡 · C4–C5")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_malformed_exam_entries_are_ignored_on_load(self) -> None:
        self.path.write_text(
            '{"version": 5, "exams": {"x": "nope", "y": {"passed": 1}, '
            '"z": {"kind": "notes", "total": 1e400, "stage_index": 1}}}',
            encoding="utf-8",
        )
        loaded = LearningProgress.load(self.path)
        self.assertEqual(loaded.exams, {})
        self.assertIsNone(loaded.exam_for("x"))

    def test_string_booleans_are_not_trusted(self) -> None:
        self.path.write_text(
            '{"version": 5, "exams": {"exam_stage1_notes": '
            '{"kind": "notes", "total": 20, "stage_index": 1, '
            '"passed": "false", "finished": "false", "first_try": 5, '
            '"attempts": 1}}}',
            encoding="utf-8",
        )
        loaded = LearningProgress.load(self.path)
        record = loaded.exam_for(STAGE1_EXAM.key)
        self.assertIsNotNone(record)
        self.assertFalse(record.passed)


if __name__ == "__main__":
    unittest.main()
