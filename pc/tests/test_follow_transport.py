"""Transport controls for the performance page: loop, speed, click, count-in."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.follow import FollowSession
from app.core.instrument import Instrument
from app.core.score import Score, ScoreNote
from app.core.synth_service import ACCOMPANIMENT_CHANNEL, NullSynth


def score_4bars() -> Score:
    """Four 4/4 bars at 120 BPM, one quarter note each second."""
    notes = [
        ScoreNote(
            midi=65 + index,
            start=float(index),
            duration=1.0,
            measure=index // 4 + 1,
            beat=index % 4 + 1.0,
        )
        for index in range(16)
    ]
    return Score(
        title="transport",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=16.0,
        source="test",
        format="midi",
        measure_count=4,
    )


class RecordingSynth(NullSynth):
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def note_on(self, midi, velocity, channel=None) -> None:
        self.events.append(("on", channel, midi))

    def note_off(self, midi, channel=None) -> None:
        self.events.append(("off", channel, midi))


class FollowTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.synth = RecordingSynth()
        self.instrument = Instrument(self.synth)
        self.instrument._timer.stop()
        self.follow = FollowSession(self.instrument)
        self.follow.set_score(score_4bars())
        self.beats: list[bool] = []
        self.follow.beat.connect(self.beats.append)

    def tearDown(self) -> None:
        self.instrument._timer.stop()

    def run_to(self, target: float, step: float = 0.1) -> None:
        now = self.follow._last_tick
        while now < target - 1e-9:
            now = min(target, now + step)
            self.follow.advance(now)

    def test_speed_scales_the_demo_clock(self) -> None:
        self.follow.play(at=0.0)
        self.follow.set_speed(0.5)
        self.run_to(2.0)  # 2 s wall time at 50% = 1 s of score

        self.assertAlmostEqual(self.follow.position, 1.0, places=3)
        self.assertEqual(self.follow.speed, 0.5)

    def test_loop_wraps_and_retriggers_notes(self) -> None:
        self.assertTrue(self.follow.set_loop(2, 2))  # bar 2 = 4.0 .. 8.0 s
        self.assertTrue(self.follow.loop_enabled)
        self.assertAlmostEqual(self.follow.loop_start, 4.0)
        self.assertAlmostEqual(self.follow.loop_end, 8.0)

        self.follow.play(at=0.0)
        self.run_to(4.5)
        before = len(self.synth.events)
        self.run_to(8.1)  # crosses the loop end and wraps

        self.assertLess(self.follow.position, 4.2)
        self.assertTrue(self.follow.playing)
        self.assertGreater(len(self.synth.events), before)

    def test_metronome_emits_one_click_per_beat_with_bar_accents(self) -> None:
        self.follow.set_metronome(True)
        self.follow.play(at=0.0)
        self.run_to(2.01)

        # Beats at 0, 0.5, 1.0, 1.5, 2.0 s: 120 BPM in 4/4.
        self.assertEqual(len(self.beats), 5)
        self.assertEqual(self.beats[0], True)
        self.assertEqual(self.beats[1:4], [False, False, False])
        self.assertEqual(self.beats[4], True)

    def test_count_in_clicks_a_full_bar_before_the_notes(self) -> None:
        self.follow.set_count_in(True)
        self.follow.play(at=0.0)
        self.run_to(1.9)

        # One bar of 4/4 = 2.0 s at 120 BPM; no demo notes before it ends.
        self.assertEqual(self.synth.events, [])
        self.assertEqual(self.beats, [True, False, False, False])

        self.run_to(2.05)
        self.assertLess(self.follow.position, 0.2)
        self.assertTrue(self.synth.events)

    def test_speed_also_scales_demo_note_durations(self) -> None:
        self.follow.play(at=0.0)
        self.follow.set_speed(0.5)
        self.follow.advance(0.05)

        self.assertTrue(self.follow._demo_releases)
        release_at, _midi = self.follow._demo_releases[0]
        self.assertAlmostEqual(release_at - 0.05, 1.95, places=2)

    def test_enabling_the_click_mid_play_does_not_burst(self) -> None:
        self.follow.play(at=0.0)
        self.run_to(5.25)
        self.assertEqual(self.beats, [])

        self.follow.set_metronome(True)
        self.run_to(5.3)
        self.assertEqual(self.beats, [])

        self.run_to(5.55)
        self.assertEqual(len(self.beats), 1)

    def test_practice_loop_rewinds_the_accompaniment(self) -> None:
        notes = [
            ScoreNote(65, 0.0, 1.0, 1, 1.0),
            ScoreNote(65, 4.0, 1.0, 2, 1.0),
            ScoreNote(65, 8.0, 1.0, 3, 1.0),
        ]
        score = Score(
            title="duet",
            composer="",
            rights="",
            tempo=120.0,
            time_signature=(4, 4),
            notes=notes,
            duration=12.0,
            source="test",
            format="MusicXML",
            measure_count=3,
        )
        accompaniment = (
            ScoreNote(48, 4.0, 4.0, 2, 1.0),
            ScoreNote(55, 8.0, 1.0, 3, 1.0),
        )
        self.follow.set_score(score, accompaniment)
        self.follow.set_loop(2, 2)

        onsets = (0.0, 4.0, 8.0, 4.0)
        for start in onsets:
            note = next(item for item in notes if item.start == start)
            self.follow.note_on(self.instrument.bar_for_midi(note.midi))

        playing = [
            event
            for event in self.synth.events
            if event[0] == "on"
            and event[1] == ACCOMPANIMENT_CHANNEL
            and event[2] == 48
        ]
        self.assertGreaterEqual(len(playing), 2)

    def test_practice_loop_wraps_the_expected_note(self) -> None:
        self.follow.set_loop(1, 1)  # bar 1 = 0.0 .. 4.0 s
        for _ in range(4):
            note = self.follow.next_note
            self.follow.note_on(self.instrument.bar_for_midi(note.midi))

        self.assertLess(self.follow.position, 0.1)
        self.assertEqual(self.follow.next_note.measure, 1)


if __name__ == "__main__":
    unittest.main()
