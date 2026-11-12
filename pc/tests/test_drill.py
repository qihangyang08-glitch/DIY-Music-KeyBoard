"""Pure-logic tests for the generated drills (no Qt window needed).

Run from pc/:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import STAGES, project_path, score_path
from app.core.drill import (
    DRILL_SPECS,
    NOTE_NAMES_C3_C4,
    NOTE_NAMES_C4_C5,
    NOTE_NAMES_C4_C6,
    DrillSpec,
    NoteNameSession,
    OnboardingSession,
    bass_staff_step,
    drill_spec,
    spelled_prompt,
    staff_step,
)
from app.core.progress import LearningProgress


class StaffStepTest(unittest.TestCase):
    def test_natural_c4_c5_positions(self) -> None:
        expected = {
            60: -2,  # C4 ledger line below
            62: -1,
            64: 0,   # E4 bottom line
            65: 1,
            67: 2,
            69: 3,
            71: 4,
            72: 5,   # C5 third space
        }
        for midi, step in expected.items():
            self.assertEqual(staff_step(midi), step, midi)


class PromptTest(unittest.TestCase):
    def test_flat_prompt_keeps_spelling_and_staff_position(self) -> None:
        prompt = spelled_prompt(70, "B♭4", "♭")
        self.assertEqual(prompt.midi, 70)
        self.assertEqual(prompt.name, "B♭4")
        self.assertEqual(prompt.accidental, "♭")
        self.assertEqual(prompt.staff_step, 4)  # B4 sits on the middle line

        spec = DrillSpec(
            key="flat",
            title="flat",
            subtitle="",
            prompts=(prompt,),
            question_count=1,
        )
        session = NoteNameSession(spec, rng=random.Random(0))
        question = session.current
        self.assertEqual(question.midi, 70)
        self.assertEqual(question.name, "B♭4")
        self.assertEqual(question.accidental, "♭")
        self.assertEqual(question.staff_step, 4)
        result = session.answer(70)
        self.assertTrue(result.correct)
        # The MIDI name is sharp-only; the question keeps the flat spelling.
        self.assertEqual(result.pressed_name, "A#4")


class BassClefTest(unittest.TestCase):
    def test_bass_c3_c4_positions(self) -> None:
        expected = {
            48: 3,   # C3 second space
            50: 4,   # D3 middle line
            52: 5,   # E3 third space
            53: 6,   # F3 fourth line
            55: 7,   # G3 fourth space
            57: 8,   # A3 top line
            59: 9,   # B3 space above staff
            60: 10,  # C4 first ledger line above
        }
        for midi, step in expected.items():
            self.assertEqual(bass_staff_step(midi), step, midi)

    def test_bass_clef_drill_uses_bass_steps_and_mapping(self) -> None:
        spec = drill_spec("note_names_bass_c3_c4")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.clef, "bass")
        self.assertEqual(spec.mapping_base, 48)
        session = NoteNameSession(spec, rng=random.Random(2))
        self.assertEqual(
            {q.midi for q in session.questions}, set(NOTE_NAMES_C3_C4)
        )
        self.assertTrue(all(q.clef == "bass" for q in session.questions))
        c3 = next(q for q in session.questions if q.midi == 48)
        self.assertEqual(c3.staff_step, 3)

    def test_stage4_bass_item_is_ready(self) -> None:
        stage = STAGES[4]
        item = next(
            item
            for item in stage.trainings
            if item.name == "低音谱号 · C3–C4"
        )
        self.assertEqual(item.drill, "note_names_bass_c3_c4")
        self.assertTrue(item.ready)


class SessionTest(unittest.TestCase):
    def setUp(self) -> None:
        spec = drill_spec("note_names_c4_c5")
        self.assertIsNotNone(spec)
        self.spec = spec

    def test_deck_covers_pool_without_immediate_repeat(self) -> None:
        for seed in range(20):
            session = NoteNameSession(self.spec, rng=random.Random(seed))
            self.assertEqual(len(session.questions), 10)
            self.assertEqual(
                {q.midi for q in session.questions}, set(NOTE_NAMES_C4_C5)
            )
            for left, right in zip(session.questions, session.questions[1:]):
                self.assertNotEqual(left.midi, right.midi, f"seed {seed}")

    def test_wrong_reveals_and_does_not_advance(self) -> None:
        session = NoteNameSession(self.spec, rng=random.Random(3))
        question = session.current
        wrong = next(m for m in NOTE_NAMES_C4_C5 if m != question.midi)
        result = session.answer(wrong)
        self.assertFalse(result.correct)
        self.assertTrue(result.revealed)
        self.assertEqual(session.index, 0)
        self.assertEqual(session.misses, 1)
        self.assertEqual(session.first_try, 0)
        self.assertEqual(session.streak, 0)

        result = session.answer(question.midi)
        self.assertTrue(result.correct)
        self.assertEqual(session.index, 1)
        self.assertEqual(session.hits, 1)
        self.assertEqual(session.first_try, 0)
        self.assertEqual(session.streak, 0)
        self.assertEqual(session.outcome().accuracy, 50)

    def test_perfect_run(self) -> None:
        session = NoteNameSession(self.spec, rng=random.Random(4))
        while not session.finished:
            session.answer(session.current.midi)
        outcome = session.outcome()
        self.assertTrue(outcome.finished)
        self.assertEqual(outcome.hits, 10)
        self.assertEqual(outcome.total, 10)
        self.assertEqual(outcome.misses, 0)
        self.assertEqual(outcome.first_try, 10)
        self.assertEqual(outcome.best_streak, 10)
        self.assertEqual(outcome.accuracy, 100)
        self.assertIsNone(session.answer(60))

    def test_first_response_latency_excludes_retries_and_dwell(self) -> None:
        # clock calls: init, wrong press, correct press, provisional reset,
        # next question press, provisional reset.
        ticks = iter([0.0, 0.5, 2.0, 2.0, 2.4, 3.0])
        session = NoteNameSession(
            self.spec, rng=random.Random(5), clock=lambda: next(ticks)
        )
        session.mark_shown(now=0.0)
        first = session.current
        wrong = next(m for m in NOTE_NAMES_C4_C5 if m != first.midi)
        session.answer(wrong)       # first response at 0.5 s
        session.answer(first.midi)  # solved at 2.0 s; not a new measurement
        session.mark_shown(now=2.0)
        session.answer(session.current.midi)  # first response at 2.4 s
        outcome = session.outcome()
        self.assertEqual(outcome.avg_ms, 450)  # (500 + 400) / 2
        self.assertEqual(outcome.first_try, 1)


class OnboardingSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        spec = drill_spec("onboarding_middle_c")
        self.assertIsNotNone(spec)
        self.spec = spec

    def test_middle_c_steps_walk_c4_d4_e4_back_to_c4(self) -> None:
        self.assertEqual(self.spec.kind, "onboarding")
        self.assertEqual(self.spec.mapping_base, 60)
        self.assertEqual(
            [step.midi for step in self.spec.steps], [60, 62, 64, 60]
        )
        session = OnboardingSession(self.spec)
        for midi in (60, 62, 64, 60):
            result = session.press(midi)
            self.assertIsNotNone(result)
            self.assertTrue(result.correct)
            self.assertTrue(result.advanced)
        self.assertTrue(session.finished)
        outcome = session.outcome()
        self.assertEqual(outcome.hits, 4)
        self.assertEqual(outcome.total, 4)
        self.assertEqual(outcome.misses, 0)
        self.assertEqual(outcome.first_try, 4)
        self.assertTrue(outcome.finished)
        self.assertIsNone(session.press(60))

    def test_wrong_press_reveals_and_does_not_advance(self) -> None:
        session = OnboardingSession(self.spec)
        result = session.press(62)
        self.assertFalse(result.correct)
        self.assertTrue(result.revealed)
        self.assertEqual(result.pressed_name, "D4")
        self.assertEqual(session.index, 0)
        self.assertEqual(session.misses, 1)
        self.assertEqual(session.first_try, 0)

        result = session.press(60)
        self.assertTrue(result.correct)
        self.assertEqual(session.index, 1)
        self.assertEqual(session.hits, 1)
        self.assertEqual(session.first_try, 0)  # solved, but not first try
        self.assertEqual(session.outcome().accuracy, 50)

    def test_sustain_then_press_then_panic(self) -> None:
        spec = drill_spec("onboarding_sustain_panic")
        self.assertIsNotNone(spec)
        session = OnboardingSession(spec)
        self.assertEqual(session.current.action, "sustain")
        # A note press while the sustain step is current is not an answer and
        # must not be counted as a miss.
        self.assertIsNone(session.press(60))
        self.assertEqual(session.misses, 0)

        result = session.sustain(True)
        self.assertIsNotNone(result)
        self.assertTrue(result.correct)
        self.assertEqual(session.current.action, "press")
        self.assertTrue(session.current.require_sustain)

        without = session.press(60, sustain=False)
        self.assertFalse(without.correct)
        self.assertTrue(without.sustain_required)
        self.assertEqual(session.index, 1)
        self.assertEqual(session.misses, 1)

        pressed = session.press(60, sustain=True)
        self.assertTrue(pressed.correct)
        self.assertEqual(session.current.action, "panic")
        self.assertIsNone(session.press(60))  # the panic step ignores notes

        done = session.panic()
        self.assertIsNotNone(done)
        self.assertTrue(done.correct)
        self.assertTrue(session.finished)
        outcome = session.outcome()
        self.assertEqual(outcome.hits, 3)
        self.assertEqual(outcome.total, 3)
        self.assertEqual(outcome.misses, 1)
        self.assertEqual(outcome.first_try, 2)


class ProgressTest(unittest.TestCase):
    def test_first_try_fields_and_best_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning.json"
            progress = LearningProgress(path=path)
            first = progress.record_practice(
                stage=1,
                item_name="音名闪卡 · C4–C5",
                hits=10,
                misses=1,
                total=10,
                avg_ms=900,
                best_streak=9,
                first_try=9,
            )
            self.assertTrue(first.completed)
            self.assertEqual(first.first_try, 9)

            worse = progress.record_practice(
                stage=1,
                item_name="音名闪卡 · C4–C5",
                hits=10,
                misses=2,
                total=10,
                avg_ms=500,
                best_streak=8,
                first_try=9,
            )
            self.assertEqual(worse.misses, 1)  # old best kept
            better = progress.record_practice(
                stage=1,
                item_name="音名闪卡 · C4–C5",
                hits=10,
                misses=1,
                total=10,
                avg_ms=900,
                best_streak=10,
                first_try=10,
            )
            self.assertEqual(better.first_try, 10)
            self.assertEqual(better.best_streak, 10)

            loaded = LearningProgress.load(path)
            result = loaded.result_for(1, "音名闪卡 · C4–C5")
            self.assertIsNotNone(result)
            self.assertEqual(result.first_try, 10)
            self.assertEqual(result.avg_ms, 900)

    def test_partial_run_is_not_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = LearningProgress(path=Path(tmp) / "learning.json")
            result = progress.record_practice(
                1, "音名闪卡 · C4–C5", hits=3, misses=1, total=10,
                avg_ms=800, best_streak=2, first_try=2,
            )
            self.assertFalse(result.completed)
            self.assertEqual(result.accuracy, 75)


class CurriculumTest(unittest.TestCase):
    def test_every_ready_item_has_a_real_asset(self) -> None:
        for stage in STAGES:
            for item in stage.items:
                if item.score is not None:
                    found = score_path(item.score) is not None
                    if item.visibility != "public":
                        # Private assets are intentionally absent from a
                        # public checkout; readiness must follow the file.
                        self.assertEqual(
                            item.ready, found, f"{stage.index}:{item.name}"
                        )
                        continue
                    self.assertTrue(found, f"{stage.index}:{item.name}")
                    self.assertTrue(item.ready)
                if item.drill is not None:
                    self.assertIn(item.drill, DRILL_SPECS)
                    self.assertTrue(item.ready)
                if item.project is not None:
                    self.assertIsNotNone(
                        project_path(item.project), f"{stage.index}:{item.name}"
                    )
                    self.assertIsNotNone(item.task, f"{stage.index}:{item.name}")
                    self.assertTrue(item.ready)
                if (
                    item.score is None
                    and item.drill is None
                    and item.project is None
                ):
                    self.assertFalse(item.ready, f"{stage.index}:{item.name}")

    def test_stage0_onboarding_drills_are_ready(self) -> None:
        stage = STAGES[0]
        self.assertEqual(stage.ready_count, 8)
        self.assertEqual(stage.total_count, 8)
        by_name = {item.name: item for item in stage.trainings}
        self.assertEqual(
            by_name["找到中央 C"].drill, "onboarding_middle_c"
        )
        self.assertEqual(
            by_name["延音与全部静音"].drill, "onboarding_sustain_panic"
        )
        for item in stage.trainings:
            self.assertTrue(item.ready, item.name)

    def test_stage1_note_drill_is_the_implemented_slice(self) -> None:
        stage = STAGES[1]
        item = stage.trainings[0]
        self.assertEqual(item.name, "音名闪卡 · C4–C5")
        self.assertEqual(item.drill, "note_names_c4_c5")
        self.assertTrue(item.ready)
        self.assertIn("C4–C5", stage.pass_rule)

    def test_stage1_has_five_ready_drills(self) -> None:
        stage = STAGES[1]
        self.assertEqual(stage.ready_count, 5)
        expected = {
            "音名闪卡 · C4–C5": "note_names_c4_c5",
            "线间定位 · 高音谱号": "note_names_c4_c6",
            "八度上下行": "octave_names_c4_c6",
            "临时记号 · 升与降": "note_accidentals_c4_c5",
            "低音谱号 · C3–C4": "note_names_bass_c3_c4",
        }
        by_name = {item.name: item for item in stage.trainings}
        for name, drill in expected.items():
            item = by_name[name]
            self.assertEqual(item.drill, drill)
            self.assertTrue(item.ready, name)

    def test_line_space_and_octave_pools(self) -> None:
        line = drill_spec("note_names_c4_c6")
        self.assertIsNotNone(line)
        self.assertEqual(set(line.midis), set(NOTE_NAMES_C4_C6))
        self.assertEqual(len(line.prompt_pool), len(NOTE_NAMES_C4_C6))

        octave = drill_spec("octave_names_c4_c6")
        self.assertIsNotNone(octave)
        midis = {prompt.midi for prompt in octave.prompt_pool}
        self.assertEqual(midis, set(octave.midis))
        self.assertTrue({60, 72, 84}.issubset(midis))  # C4/C5/C6

    def test_accidental_drill_has_sharps_and_flats(self) -> None:
        spec = drill_spec("note_accidentals_c4_c5")
        self.assertIsNotNone(spec)
        names = {prompt.name for prompt in spec.prompt_pool}
        self.assertIn("C#4", names)
        self.assertIn("B♭4", names)
        self.assertEqual(
            len([p for p in spec.prompt_pool if p.accidental == "♭"]), 5
        )

        session = NoteNameSession(spec, rng=random.Random(1))
        self.assertEqual(len(session.questions), 10)
        self.assertEqual({q.midi for q in session.questions}, set(spec.midis))
        flat = next(q for q in session.questions if q.name == "B♭4")
        self.assertEqual(flat.midi, 70)
        self.assertEqual(flat.accidental, "♭")
        self.assertEqual(flat.staff_step, 4)  # B4 line, not A4 space

    def test_missing_or_corrupt_score_is_not_ready(self) -> None:
        import app.core.curriculum as curriculum

        old = curriculum.SCORE_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                curriculum.SCORE_DIR = root
                curriculum._score_ready.cache_clear()
                self.assertFalse(
                    curriculum.PracticeItem("x", "x", "missing.musicxml").ready
                )
                (root / "bad.musicxml").write_text(
                    "<not-musicxml/>", encoding="utf-8"
                )
                curriculum._score_ready.cache_clear()
                self.assertFalse(
                    curriculum.PracticeItem("x", "x", "bad.musicxml").ready
                )
                shutil.copyfile(
                    ROOT / "resources" / "scores" / "xiaoxingxing.mid",
                    root / "fallback.mid",
                )
                curriculum._score_ready.cache_clear()
                self.assertTrue(
                    curriculum.PracticeItem("x", "x", "fallback.musicxml").ready
                )
        finally:
            curriculum.SCORE_DIR = old
            curriculum._score_ready.cache_clear()


if __name__ == "__main__":
    unittest.main()
