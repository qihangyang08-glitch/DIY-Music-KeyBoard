"""Pure-logic tests for the metronome rhythm drill."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import stage_by_index
from app.core.drill import drill_spec
from app.core.rhythm import RhythmSession, RhythmSpec, rest


class RhythmRestSpecTest(unittest.TestCase):
    def _spec(self) -> RhythmSpec:
        return RhythmSpec(
            key="rests",
            title="rests",
            subtitle="test",
            bpm=80,
            beats_per_bar=4,
            bars=1,
            cells=((1, rest(1), 1.5, 0.5),),
        )

    def test_rest_cells_become_silent_events(self) -> None:
        spec = self._spec()
        self.assertEqual(spec.total_beats, 4)
        self.assertEqual(
            [event.rest for event in spec.events],
            [False, True, False, False],
        )
        self.assertEqual(spec.events[1].beat, 1)
        self.assertAlmostEqual(spec.events[2].beat, 2)
        self.assertAlmostEqual(spec.events[2].duration, 1.5)
        self.assertEqual(len(spec.note_events), 3)

    def test_rests_are_not_missed_and_do_not_count_as_total(self) -> None:
        spec = self._spec()
        session = RhythmSession(spec)
        session.start(now=0.0)
        first = spec.count_in_beats * spec.beat_seconds
        session.tick(first)
        self.assertTrue(session.press(first).hit)

        # Past the rest (beat 1) and the next note (beat 2).
        late = (
            (spec.count_in_beats + 2.0) * spec.beat_seconds
            + spec.tolerance
            + 0.01
        )
        session.tick(late)
        self.assertEqual(session.total, 3)
        self.assertEqual(session.misses, 1)  # only the note at beat 2

    def test_press_during_a_rest_is_an_extra(self) -> None:
        spec = self._spec()
        session = RhythmSession(spec)
        session.start(now=0.0)
        rest_time = (spec.count_in_beats + 1.0) * spec.beat_seconds
        session.tick(rest_time)
        result = session.press(rest_time)
        self.assertFalse(result.hit)
        self.assertEqual(session.extras, 1)


class RhythmSpecTest(unittest.TestCase):
    def test_bars_must_add_up(self) -> None:
        with self.assertRaises(ValueError):
            RhythmSpec(
                key="bad",
                title="bad",
                subtitle="bad",
                bpm=80,
                beats_per_bar=4,
                bars=1,
                cells=((1, 1),),
            )

    def test_all_registered_rhythms_finish_cleanly(self) -> None:
        for key in (
            "rhythm_quarters_halves_4_4",
            "rhythm_eighths_4_4",
            "rhythm_waltz_3_4",
            "rhythm_rests_dots_4_4",
            "rhythm_six_eight",
            "rhythm_syncopation_4_4",
            "rhythm_triplets_4_4",
        ):
            with self.subTest(key=key):
                drill = drill_spec(key)
                self.assertIsNotNone(drill)
                self.assertEqual(drill.kind, "rhythm")
                spec = drill.rhythm
                session = RhythmSession(spec)
                session.start(now=0.0)
                for event in spec.note_events:
                    when = (
                        spec.count_in_beats + event.beat
                    ) * spec.beat_seconds
                    session.tick(when)
                    self.assertTrue(session.press(when).hit)
                session.tick(
                    (spec.count_in_beats + spec.total_beats)
                    * spec.beat_seconds
                    + 1.0
                )
                out = session.outcome()
                self.assertTrue(out.finished)
                self.assertEqual(out.hits, out.total)
                self.assertEqual(out.misses, 0)
                self.assertEqual(out.extras, 0)

    def test_events_and_total(self) -> None:
        spec = drill_spec("rhythm_quarters_halves_4_4").rhythm
        self.assertEqual(spec.total_beats, 16)
        self.assertEqual(len(spec.events), 12)
        self.assertEqual(spec.events[0].beat, 0)
        self.assertEqual(spec.events[-1].beat, 15)  # last bar: 2 + 1 + 1
        self.assertEqual(spec.count_in_beats, 4)
        self.assertAlmostEqual(spec.beat_seconds, 0.75)


class RestDrillWiringTest(unittest.TestCase):
    def test_rests_and_dots_drill_is_registered_and_wired(self) -> None:
        drill = drill_spec("rhythm_rests_dots_4_4")
        self.assertIsNotNone(drill)
        self.assertEqual(drill.kind, "rhythm")
        spec = drill.rhythm
        self.assertEqual(spec.total_beats, 16)
        self.assertEqual(len(spec.note_events), 9)
        self.assertEqual(
            [event.index for event in spec.events if event.rest], [1, 8]
        )

        stage2 = stage_by_index(2)
        item = next(
            item for item in stage2.trainings if item.name == "休止与附点"
        )
        self.assertEqual(item.drill, "rhythm_rests_dots_4_4")
        self.assertTrue(item.ready)


class CompoundMeterTest(unittest.TestCase):
    def test_six_eight_counts_six_units_and_accents_one_and_four(self) -> None:
        drill = drill_spec("rhythm_six_eight")
        self.assertIsNotNone(drill)
        spec = drill.rhythm
        self.assertEqual(drill.kind, "rhythm")
        self.assertEqual(spec.beats_per_bar, 6)
        self.assertEqual(spec.meter_label, "6/8")
        self.assertEqual(spec.accent_beats, (0, 3))
        self.assertEqual(spec.bars, 4)
        self.assertEqual(len(spec.events), 16)  # 6 + 2 + 4 + 4

        session = RhythmSession(spec)
        session.start(now=0.0)
        end = (spec.count_in_beats + spec.total_beats) * spec.beat_seconds
        clicks = session.tick(end + 0.01)
        pattern = [click for click in clicks if not click.count_in]
        accented = [
            click.pattern_beat % spec.beats_per_bar
            for click in pattern
            if click.accent
        ]
        self.assertEqual(accented, [0, 3] * spec.bars)

    def test_six_eight_is_wired_to_its_lesson(self) -> None:
        stage2 = stage_by_index(2)
        item = next(
            item for item in stage2.trainings if item.name == "6/8 复拍子"
        )
        self.assertEqual(item.drill, "rhythm_six_eight")
        self.assertTrue(item.ready)
        guide = next(
            guide for guide in stage2.guides if guide.title == "6/8 与弱起"
        )
        self.assertEqual(guide.practice, "6/8 复拍子")

    def test_syncopation_has_offbeat_onsets_and_is_wired(self) -> None:
        spec = drill_spec("rhythm_syncopation_4_4").rhythm
        self.assertEqual(spec.meter_label, "4/4")
        offbeats = [
            event.beat % spec.beats_per_bar
            for event in spec.note_events
            if abs(event.beat % spec.beats_per_bar % 1.0) > 1e-6
        ]
        self.assertTrue(offbeats)
        stage2 = stage_by_index(2)
        item = next(
            item for item in stage2.trainings if item.name == "切分节奏"
        )
        self.assertEqual(item.drill, "rhythm_syncopation_4_4")
        self.assertTrue(item.ready)
        guide = next(
            guide
            for guide in stage2.guides
            if guide.title == "切分与三连音"
        )
        self.assertEqual(guide.practice, "切分节奏")

    def test_triplets_place_three_onsets_per_beat(self) -> None:
        spec = drill_spec("rhythm_triplets_4_4").rhythm
        self.assertEqual(spec.meter_label, "4/4")
        self.assertEqual(len(spec.note_events), 24)
        self.assertAlmostEqual(spec.note_events[1].beat, 1 / 3)
        self.assertAlmostEqual(spec.note_events[2].beat, 2 / 3)
        item = next(
            item
            for item in stage_by_index(2).trainings
            if item.name == "三连音"
        )
        self.assertEqual(item.drill, "rhythm_triplets_4_4")
        self.assertTrue(item.ready)


class RhythmSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = drill_spec("rhythm_quarters_halves_4_4").rhythm
        self.beat = self.spec.beat_seconds
        self.count_in = self.spec.count_in_beats

    def _time(self, event_beat: float) -> float:
        return (self.count_in + event_beat) * self.beat

    def test_count_in_clicks(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        clicks = session.tick(0.01)
        self.assertEqual(len(clicks), 1)
        self.assertTrue(clicks[0].count_in)
        self.assertTrue(clicks[0].accent)
        # no pattern event is judged yet
        self.assertEqual(session.misses, 0)

    def test_perfect_run(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        for event in self.spec.events:
            now = self._time(event.beat)
            session.tick(now)
            result = session.press(now)
            self.assertIsNotNone(result)
            self.assertTrue(result.hit, event)
        session.tick(self._time(self.spec.total_beats) + 1.0)
        out = session.outcome()
        self.assertTrue(out.finished)
        self.assertEqual(out.hits, out.total)
        self.assertEqual(out.misses, 0)
        self.assertEqual(out.extras, 0)
        self.assertEqual(out.accuracy, 100)
        self.assertEqual(out.best_streak, out.total)

    def test_missed_beat(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        first = self.spec.events[0]
        self.assertTrue(session.press(self._time(first.beat) + 0.01).hit)
        session.tick(self._time(self.spec.events[1].beat) + self.spec.tolerance + 0.1)
        self.assertEqual(session.misses, 1)
        self.assertEqual(session.streak, 0)

    def test_extra_press(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        # between onsets, outside every tolerance window
        session.tick(self._time(0.5))
        result = session.press(self._time(0.5))
        self.assertFalse(result.hit)
        self.assertEqual(session.extras, 1)
        self.assertEqual(session.streak, 0)

    def test_early_press_within_tolerance_is_a_hit(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        event = self.spec.events[0]
        early = self._time(event.beat) - self.spec.tolerance / 2
        session.tick(early)
        result = session.press(early)
        self.assertTrue(result.hit)
        self.assertLess(result.error_ms, 0)

    def test_count_in_press_is_ignored(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        session.tick(0.01)
        self.assertIsNone(session.press(0.01))
        self.assertEqual(session.extras, 0)

    def test_stop_keeps_partial_counts(self) -> None:
        session = RhythmSession(self.spec)
        session.start(now=0.0)
        session.press(self._time(0.0))
        session.stop()
        out = session.outcome()
        self.assertEqual(out.hits, 1)
        self.assertFalse(out.finished)


if __name__ == "__main__":
    unittest.main()
