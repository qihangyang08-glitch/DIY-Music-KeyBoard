"""Split a score into the practiced part and an auto-played accompaniment."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.accompaniment import split_accompaniment
from app.core.score import Score, ScoreNote


def duet_score() -> Score:
    notes = [
        ScoreNote(72, 0.0, 1.0, 1, 1.0, part="P1"),   # C5 melody
        ScoreNote(48, 0.0, 2.0, 1, 1.0, part="P2"),   # C3 bass
        ScoreNote(74, 1.0, 1.0, 1, 2.0, part="P1"),   # D5 melody
        ScoreNote(55, 2.0, 2.0, 1, 3.0, part="P2"),   # G3 bass
        ScoreNote(76, 2.0, 1.0, 1, 3.0, part="P1"),   # E5 melody
    ]
    return Score(
        title="duet",
        composer="test",
        rights="public",
        tempo=90.0,
        time_signature=(4, 4),
        notes=notes,
        duration=4.0,
        source="test",
        format="MusicXML",
        measure_count=1,
        key_fifths=2,
    )


class SplitAccompanimentTest(unittest.TestCase):
    def test_declared_part_leaves_the_practice_score(self) -> None:
        practice, accompaniment = split_accompaniment(duet_score(), "P2")

        self.assertEqual(
            [note.midi for note in practice.notes], [72, 74, 76]
        )
        self.assertEqual([note.midi for note in accompaniment], [48, 55])
        self.assertTrue(all(note.part == "P2" for note in accompaniment))

    def test_practice_score_keeps_the_song_metadata(self) -> None:
        source = duet_score()
        practice, _ = split_accompaniment(source, "P2")

        self.assertEqual(practice.title, source.title)
        self.assertEqual(practice.tempo, source.tempo)
        self.assertEqual(practice.time_signature, source.time_signature)
        self.assertEqual(practice.duration, source.duration)
        self.assertEqual(practice.key_fifths, source.key_fifths)
        self.assertEqual(practice.measure_count, source.measure_count)

    def test_missing_part_is_not_a_silent_song_wipe(self) -> None:
        source = duet_score()
        practice, accompaniment = split_accompaniment(source, "P9")

        self.assertIs(practice, source)
        self.assertEqual(accompaniment, ())

    def test_a_part_that_holds_every_note_is_rejected(self) -> None:
        source = duet_score()
        source = replace(
            source,
            notes=[note for note in source.notes if note.part == "P1"],
        )
        practice, accompaniment = split_accompaniment(source, "P1")

        self.assertIs(practice, source)
        self.assertEqual(accompaniment, ())

    def test_blank_declaration_keeps_the_plain_score(self) -> None:
        source = duet_score()
        practice, accompaniment = split_accompaniment(source, "")

        self.assertIs(practice, source)
        self.assertEqual(accompaniment, ())


if __name__ == "__main__":
    unittest.main()
