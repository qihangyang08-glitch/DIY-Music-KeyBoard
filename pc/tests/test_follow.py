"""Chord / two-hand onset judgment for FollowSession (no MainWindow)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.curriculum import SCORE_DIR
from app.core.follow import FollowSession
from app.core.mapping import PRESET_BY_KEY
from app.core.score import Score, ScoreNote, parse_score


class FakeInstrument:
    auto_follow = False
    octave = 0
    transpose = 0
    current_preset = PRESET_BY_KEY["chromatic"]

    def bar_for_midi(self, midi: int) -> int | None:
        for key in range(1, 33):
            if self.current_preset.midi_for_key(key) + self.octave * 12 + self.transpose == midi:
                return key
        return None

    def set_octave_absolute(self, octave: int) -> None:
        self.octave = octave


def chord_score() -> Score:
    notes = [
        ScoreNote(72, 0.0, 1.0, 1, 1.0),  # C5
        ScoreNote(76, 0.0, 1.0, 1, 1.0),  # E5, same onset
        ScoreNote(79, 1.0, 1.0, 1, 2.0),  # G5
    ]
    return Score(
        title="chord",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=2.0,
        source="test",
        format="test",
        measure_count=1,
    )


def cross_register_score() -> Score:
    notes = [
        ScoreNote(48, 0.0, 1.0, 1, 1.0),  # C3, left half
        ScoreNote(84, 0.0, 1.0, 1, 1.0),  # C6, right half, same onset
        ScoreNote(50, 1.0, 1.0, 1, 2.0),  # D3
    ]
    return Score(
        title="cross register",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=2.0,
        source="test",
        format="test",
        measure_count=1,
    )


class CountingNotes(list):
    """List that records which indices a scan actually reads."""

    def __init__(self, items):
        super().__init__(items)
        self.reads: list[int] = []

    def __getitem__(self, index):
        self.reads.append(index)
        return super().__getitem__(index)


class FollowOnsetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = FakeInstrument()
        self.follow = FollowSession(self.instrument)
        self.finished: list[bool] = []
        self.follow.finished.connect(lambda: self.finished.append(True))
        self.follow.set_score(chord_score())

    def bar(self, midi: int) -> int:
        bar = self.instrument.bar_for_midi(midi)
        self.assertIsNotNone(bar)
        return bar

    def test_onset_scan_stops_after_the_current_chord(self) -> None:
        notes = CountingNotes(
            [
                ScoreNote(72, 0.0, 1.0, 1, 1.0),
                ScoreNote(76, 0.0, 1.0, 1, 1.0),
                *(
                    ScoreNote(60 + index % 12, float(index), 1.0, 1, 1.0)
                    for index in range(1, 200)
                ),
            ]
        )
        score = chord_score()
        score.notes = notes
        self.follow.set_score(score)
        notes.reads.clear()

        indices = self.follow._onset_indices()

        self.assertEqual(indices, [0, 1])
        # Read indices up to the first different onset and stop; the old
        # full-list scan touched all 201 notes on every state change.
        self.assertLessEqual(max(notes.reads), 2)

    def test_chord_matches_in_any_order_and_advances_once(self) -> None:
        follow = self.follow
        self.assertEqual(follow.next_note.midi, 72)
        follow.note_on(self.bar(76))  # E5 first
        self.assertEqual((follow.hits, follow.misses), (1, 0))
        self.assertEqual(follow.index, 0)
        self.assertEqual(follow.next_note.midi, 72)
        follow.note_on(self.bar(72))  # C5 second
        self.assertEqual((follow.hits, follow.misses), (2, 0))
        self.assertEqual(follow.index, 2)
        self.assertEqual(follow.next_note.midi, 79)
        follow.note_on(self.bar(79))
        self.assertEqual(follow.hits, 3)
        self.assertTrue(self.finished)

    def test_chord_accepts_bass_first_then_melody(self) -> None:
        follow = self.follow
        follow.note_on(self.bar(72))
        self.assertEqual(follow.next_note.midi, 76)
        follow.note_on(self.bar(76))
        self.assertEqual(follow.index, 2)
        self.assertEqual(follow.next_note.midi, 79)

    def test_wrong_note_costs_one_miss_and_keeps_the_chord(self) -> None:
        follow = self.follow
        follow.note_on(self.bar(72))
        follow.note_on(self.bar(74))  # D5 is not in the onset
        self.assertEqual((follow.hits, follow.misses), (1, 1))
        self.assertEqual(follow.next_note.midi, 76)
        follow.note_on(self.bar(76))
        self.assertEqual((follow.hits, follow.misses), (2, 1))
        self.assertEqual(follow.index, 2)

    def test_repressing_a_matched_chord_note_is_a_miss(self) -> None:
        follow = self.follow
        follow.note_on(self.bar(72))
        follow.note_on(self.bar(72))
        self.assertEqual((follow.hits, follow.misses), (1, 1))
        self.assertEqual(follow.next_note.midi, 76)

    def test_split_mapping_judges_a_cross_register_chord(self) -> None:
        instrument = FakeInstrument()
        instrument.current_preset = PRESET_BY_KEY["split"]
        follow = FollowSession(instrument)
        follow.set_score(cross_register_score())

        low = instrument.bar_for_midi(48)   # C3, bar 1
        high = instrument.bar_for_midi(84)  # C6, bar 29
        self.assertEqual((low, high), (1, 29))

        follow.note_on(high)
        self.assertEqual((follow.hits, follow.misses), (1, 0))
        self.assertEqual(follow.index, 0)
        follow.note_on(low)
        self.assertEqual((follow.hits, follow.misses), (2, 0))
        self.assertEqual(follow.index, 2)
        self.assertEqual(follow.next_note.midi, 50)

    def test_real_two_hand_piece_first_onset(self) -> None:
        score = parse_score(SCORE_DIR / "ode_to_joy_both.musicxml")
        self.follow.set_score(score)
        first = self.follow._onset_indices()
        self.assertEqual(len(first), 2)
        midis = {score.notes[index].midi for index in first}
        self.assertEqual(midis, {67, 76})  # G4 bass + E5 melody
        self.follow.note_on(self.bar(76))
        self.assertEqual((self.follow.hits, self.follow.misses), (1, 0))
        self.follow.note_on(self.bar(67))
        self.assertEqual((self.follow.hits, self.follow.misses), (2, 0))
        self.assertEqual(self.follow.index, 2)
        self.assertEqual(self.follow.next_note.midi, 76)  # next melody note


if __name__ == "__main__":
    unittest.main()
