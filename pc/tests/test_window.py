"""Pure tests for the automatic 32-key window planner."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.mapping import PRESET_BY_KEY
from app.core.score import Score, ScoreNote
from app.core.window import plan_windows


def make_score(events, tempo: float = 120.0, time_signature=(4, 4)) -> Score:
    """events: [(midi, start, duration, measure)] in seconds."""
    notes = [
        ScoreNote(
            midi=midi,
            start=start,
            duration=duration,
            measure=measure,
            beat=1.0,
        )
        for midi, start, duration, measure in events
    ]
    duration = max((note.end for note in notes), default=0.0)
    return Score(
        title="test",
        composer="",
        rights="",
        tempo=tempo,
        time_signature=time_signature,
        notes=notes,
        duration=duration,
        source="test",
        format="test",
    )


def four_bar_piece(first_midi: int, second_midi: int) -> Score:
    """Eight full-measure notes: four low then four high (no rests)."""
    events = [
        (first_midi, measure * 2.0, 2.0, measure + 1) for measure in range(4)
    ]
    events += [
        (second_midi, measure * 2.0, 2.0, measure + 1) for measure in range(4, 8)
    ]
    return make_score(events)


class WindowPlanTest(unittest.TestCase):
    def test_white_key_preset_never_reaches_black_keys(self) -> None:
        plan = plan_windows(
            make_score([(61, 0.0, 1.0, 1)]), PRESET_BY_KEY["white19"]
        )
        self.assertEqual(
            sum(segment.unplayable for segment in plan.segments), 1
        )

    def test_white_key_preset_fits_its_declared_range(self) -> None:
        events = [
            (midi, index * 1.0, 1.0, index + 1)
            for index, midi in enumerate((60, 64, 67, 72, 76, 79, 84, 88, 91))
        ]
        plan = plan_windows(make_score(events), PRESET_BY_KEY["white19"])
        self.assertEqual(
            sum(segment.unplayable for segment in plan.segments), 0
        )

    def test_empty_score(self) -> None:
        plan = plan_windows(make_score([]), PRESET_BY_KEY["chromatic"])
        self.assertEqual(plan.segments, ())
        self.assertIsNone(plan.segment_for_note(0))

    def test_fitting_piece_is_one_window(self) -> None:
        score = make_score(
            [(72, measure * 2.0, 2.0, measure + 1) for measure in range(8)]
        )
        plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertEqual(len(plan.segments), 1)
        segment = plan.segments[0]
        self.assertEqual((segment.measure_first, segment.measure_last), (1, 8))
        self.assertEqual((segment.first_note, segment.last_note), (0, 7))

    def test_rest_boundary_can_place_a_switch(self) -> None:
        score = make_score(
            [
                (48, 0.0, 2.0, 1),
                (48, 2.0, 2.0, 2),
                (85, 5.0, 2.0, 3),  # one-second rest after measure 2
                (85, 7.0, 2.0, 4),
            ]
        )
        plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertEqual(
            [(s.measure_first, s.measure_last) for s in plan.segments],
            [(1, 2), (3, 4)],
        )
        self.assertNotEqual(plan.segments[0].octave, plan.segments[1].octave)

    def test_octave_moves_for_wide_score(self) -> None:
        score = four_bar_piece(48, 85)  # C3 then C#6
        plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertEqual(len(plan.segments), 2)
        low, high = plan.segments
        self.assertEqual(low.unplayable, 0)
        self.assertEqual(high.unplayable, 0)
        self.assertEqual(low.octave, -2)
        self.assertEqual(high.octave, 0)
        self.assertLessEqual(low.lo, 48)
        self.assertGreaterEqual(low.hi, 48)
        self.assertLessEqual(high.lo, 85)
        self.assertGreaterEqual(high.hi, 85)
        self.assertNotEqual(low.octave, high.octave)

    def test_current_octave_is_kept_when_it_fits(self) -> None:
        score = make_score(
            [(72, measure * 2.0, 2.0, measure + 1) for measure in range(4)]
        )
        plan = plan_windows(
            score, PRESET_BY_KEY["chromatic"], current_octave=-1
        )
        self.assertEqual(plan.segments[0].octave, -1)

    def test_diatonic_preset_reports_unplayable_notes(self) -> None:
        score = make_score([(73, 0.0, 2.0, 1)])  # C#5 is outside C major
        plan = plan_windows(score, PRESET_BY_KEY["cmajor"])
        self.assertEqual(plan.segments[0].unplayable, 1)

    def test_segment_for_note_clamps_to_ends(self) -> None:
        score = four_bar_piece(48, 85)
        plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertEqual(plan.segment_for_note(0).index, 0)
        self.assertEqual(plan.segment_for_note(3).index, 0)
        self.assertEqual(plan.segment_for_note(4).index, 1)
        self.assertEqual(plan.segment_for_note(999).index, 1)
        self.assertEqual(plan.segment_for_note(-3).index, 0)

    def test_long_fitting_piece_stays_one_window(self) -> None:
        score = make_score(
            [(72, measure * 2.0, 2.0, measure + 1) for measure in range(10)]
        )
        plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertEqual(len(plan.segments), 1)
        self.assertEqual(
            (plan.segments[0].measure_first, plan.segments[0].measure_last),
            (1, 10),
        )

    def test_split_preset_fits_two_hands_in_one_window(self) -> None:
        # Bass C3 and melody C6 sound together. No single octave of a
        # contiguous 32-key mapping can reach both; the split mapping can.
        score = make_score(
            [
                (48, 0.0, 2.0, 1),
                (84, 0.0, 2.0, 1),
                (50, 2.0, 2.0, 2),
                (86, 2.0, 2.0, 2),
            ]
        )
        plan = plan_windows(score, PRESET_BY_KEY["split"])
        self.assertEqual(len(plan.segments), 1)
        segment = plan.segments[0]
        self.assertEqual(segment.octave, 0)
        self.assertEqual(segment.unplayable, 0)
        self.assertLessEqual(segment.lo, 48)
        self.assertGreaterEqual(segment.hi, 84)

        contiguous = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertGreater(sum(s.unplayable for s in contiguous.segments), 0)

    def test_split_window_label_keeps_both_registers(self) -> None:
        score = make_score(
            [
                (48, 0.0, 2.0, 1),
                (84, 0.0, 2.0, 1),
                (50, 2.0, 2.0, 2),
                (86, 2.0, 2.0, 2),
            ]
        )
        plan = plan_windows(score, PRESET_BY_KEY["split"])
        # The window spans the gap, but the label must show the two sides, not
        # the misleading C3–D#6 span.
        self.assertEqual(plan.segments[0].range_label, "C3–D#4 + C5–D#6")

    def test_switch_waits_for_a_phrase_boundary(self) -> None:
        # Low for six measures, high for the last two. The switch must happen
        # at the measure-7 phrase boundary, not in the middle of measure 5-6.
        events = [(48, measure * 2.0, 2.0, measure + 1) for measure in range(6)]
        events += [(85, (measure + 6) * 2.0, 2.0, measure + 7) for measure in range(2)]
        plan = plan_windows(make_score(events), PRESET_BY_KEY["chromatic"])
        self.assertEqual(
            [(s.measure_first, s.measure_last) for s in plan.segments],
            [(1, 6), (7, 8)],
        )


if __name__ == "__main__":
    unittest.main()
