"""FollowSession practices one part while the synth plays the other (H7e)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.accompaniment import split_accompaniment
from app.core.follow import FollowSession
from app.core.mapping import PRESET_BY_KEY
from app.core.score import Score, ScoreNote
from app.core.synth_service import ACCOMPANIMENT_CHANNEL, DEMO_CHANNEL


class RecordingSynth:
    def __init__(self) -> None:
        self.on: list[tuple[int, int]] = []   # (channel, midi)
        self.off: list[tuple[int, int]] = []

    def program_on(self, channel: int, program: int) -> None:
        pass

    def channel_volume(self, channel: int, volume: float) -> None:
        pass

    def note_on(self, midi: int, velocity: int, channel: int | None = None) -> None:
        self.on.append((0 if channel is None else channel, midi))

    def note_off(self, midi: int, channel: int | None = None) -> None:
        self.off.append((0 if channel is None else channel, midi))


class FakeInstrument:
    auto_follow = False
    octave = 0
    transpose = 0
    current_preset = PRESET_BY_KEY["chromatic"]

    def __init__(self) -> None:
        self.synth = RecordingSynth()

    def bar_for_midi(self, midi: int) -> int | None:
        for key in range(1, 33):
            if (
                self.current_preset.midi_for_key(key)
                + self.octave * 12
                + self.transpose
                == midi
            ):
                return key
        return None

    def set_octave_absolute(self, octave: int) -> None:
        self.octave = octave


def duet_score() -> Score:
    """Melody at 0.0/1.0; bass at 0.0 and a mid-beat 0.5."""
    notes = [
        ScoreNote(72, 0.0, 1.0, 1, 1.0, part="P1"),
        ScoreNote(48, 0.0, 2.0, 1, 1.0, part="P2"),
        ScoreNote(55, 0.5, 1.0, 1, 1.5, part="P2"),
        ScoreNote(74, 1.0, 1.0, 1, 2.0, part="P1"),
        ScoreNote(76, 3.0, 1.0, 2, 3.0, part="P1"),
    ]
    return Score(
        title="duet",
        composer="test",
        rights="public",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=2.0,
        source="test",
        format="test",
        measure_count=1,
    )


class FollowAccompanimentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = FakeInstrument()
        self.follow = FollowSession(self.instrument)
        practice, accompaniment = split_accompaniment(duet_score(), "P2")
        self.follow.set_score(practice, accompaniment)

    def bar(self, midi: int) -> int:
        bar = self.instrument.bar_for_midi(midi)
        self.assertIsNotNone(bar)
        return bar

    def test_practice_starts_the_bass_with_the_first_melody_note(self) -> None:
        self.follow.note_on(self.bar(72))

        self.assertEqual((self.follow.hits, self.follow.misses), (1, 0))
        self.assertIn((ACCOMPANIMENT_CHANNEL, 48), self.instrument.synth.on)

    def test_mid_beat_bass_waits_for_the_next_melody_note(self) -> None:
        self.follow.note_on(self.bar(72))
        self.assertNotIn((ACCOMPANIMENT_CHANNEL, 55), self.instrument.synth.on)

        self.follow.note_on(self.bar(74))
        self.assertIn((ACCOMPANIMENT_CHANNEL, 55), self.instrument.synth.on)

    def test_accompaniment_is_never_judged(self) -> None:
        self.follow.note_on(self.bar(72))
        self.follow.note_on(self.bar(74))
        self.follow.note_on(self.bar(76))

        self.assertEqual((self.follow.hits, self.follow.misses), (3, 0))
        self.assertEqual(len(self.follow.score.notes), 3)
        self.assertTrue(self.follow.playing is False)

    def test_a_wrong_note_does_not_start_the_accompaniment(self) -> None:
        self.follow.note_on(self.bar(76))  # E5 is not expected

        self.assertEqual((self.follow.hits, self.follow.misses), (0, 1))
        self.assertEqual(
            [
                midi
                for channel, midi in self.instrument.synth.on
                if channel == ACCOMPANIMENT_CHANNEL
            ],
            [],
        )

    def test_restart_replays_the_accompaniment_from_the_start(self) -> None:
        self.follow.note_on(self.bar(72))
        self.follow.restart()
        self.instrument.synth.on.clear()

        self.follow.note_on(self.bar(72))
        self.assertIn((ACCOMPANIMENT_CHANNEL, 48), self.instrument.synth.on)

    def test_leaving_the_score_releases_held_bass_notes(self) -> None:
        self.follow.note_on(self.bar(72))
        self.follow.clear_score()

        self.assertIn((ACCOMPANIMENT_CHANNEL, 48), self.instrument.synth.off)
        self.assertEqual(self.follow.score, None)

    def test_bass_notes_release_when_the_learner_moves_past_them(self) -> None:
        self.follow.note_on(self.bar(72))
        self.follow.note_on(self.bar(74))
        self.assertNotIn(
            (ACCOMPANIMENT_CHANNEL, 48), self.instrument.synth.off
        )

        self.follow.note_on(self.bar(76))  # score time 3.0 > both bass ends
        self.assertIn((ACCOMPANIMENT_CHANNEL, 48), self.instrument.synth.off)
        self.assertIn((ACCOMPANIMENT_CHANNEL, 55), self.instrument.synth.off)

    def test_demo_plays_both_hands_on_the_demo_channel(self) -> None:
        self.follow.play(at=0.0)
        self.follow.advance(0.0)

        demo = [
            midi
            for channel, midi in self.instrument.synth.on
            if channel == DEMO_CHANNEL
        ]
        self.assertIn(72, demo)
        self.assertIn(48, demo)


if __name__ == "__main__":
    unittest.main()
