"""Behaviour tests for the pure staff layout (no Qt).

The layout turns a parsed Score into systems, measures, and note positions on
the treble/bass staff. It intentionally keeps drawing out of the model, so the
same facts can feed the Qt painter, tests, and future exporters.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.score import Score, ScoreNote, excerpt_score, parse_score
from app.core.staff import build_staff_layout, spell_midi


def make_score(
    notes: list[ScoreNote],
    measures: int = 4,
    tempo: float = 120.0,
    signature: tuple[int, int] = (4, 4),
    key_fifths: int = 0,
) -> Score:
    return Score(
        title="测试",
        composer="",
        rights="",
        tempo=tempo,
        time_signature=signature,
        notes=notes,
        duration=max((note.end for note in notes), default=0.0),
        source="test",
        format="MusicXML",
        measure_count=measures,
        key_fifths=key_fifths,
    )


def note(midi: int, measure: int, beat: float = 1.0, seconds: float = 0.0) -> ScoreNote:
    return ScoreNote(
        midi=midi,
        start=seconds,
        duration=1.0,
        measure=measure,
        beat=beat,
    )


class StaffLayoutTest(unittest.TestCase):
    def test_excerpt_keeps_only_the_first_measures(self) -> None:
        score = parse_score(ROOT / "resources" / "scores" / "xiaoxingxing.musicxml")
        excerpt = excerpt_score(score, 4)

        self.assertEqual(excerpt.measure_count, 4)
        self.assertTrue(excerpt.notes)
        self.assertLessEqual(max(item.measure for item in excerpt.notes), 4)
        self.assertLess(len(excerpt.notes), len(score.notes))
        self.assertAlmostEqual(
            excerpt.duration, max(item.end for item in excerpt.notes)
        )
        self.assertIs(excerpt_score(score, 99), score)

    def test_measures_are_split_into_four_measure_systems(self) -> None:
        score = make_score(
            [note(72, measure) for measure in range(1, 6)], measures=5
        )
        layout = build_staff_layout(score, measures_per_system=4)

        self.assertEqual(len(layout.systems), 2)
        self.assertEqual([len(system.measures) for system in layout.systems], [4, 1])
        self.assertEqual(layout.measure_count, 5)

    def test_treble_steps_follow_the_staff_lines(self) -> None:
        score = make_score(
            [
                note(64, 1),  # E4 = bottom line
                note(60, 2),  # C4 = two ledger steps down
                note(72, 3),  # C5 = third space
            ]
        )
        layout = build_staff_layout(score)
        steps = [item.step for item in layout.notes]

        self.assertEqual(steps, [0, -2, 5])
        self.assertTrue(all(item.staff == "treble" for item in layout.notes))
        self.assertFalse(layout.bass)

    def test_low_notes_use_a_bass_staff(self) -> None:
        score = make_score([note(48, 1), note(72, 2)])
        layout = build_staff_layout(score, split_midi=60)

        self.assertTrue(layout.treble)
        self.assertTrue(layout.bass)
        self.assertEqual(layout.notes[0].staff, "bass")
        self.assertEqual(layout.notes[0].step, 3)  # C3 above the G2 bottom line
        self.assertEqual(layout.notes[1].staff, "treble")

    def test_accidentals_follow_the_key_signature(self) -> None:
        self.assertEqual(spell_midi(61, 0)[:2], ("C", "♯"))
        self.assertEqual(spell_midi(70, -1)[:2], ("B", "♭"))
        self.assertEqual(spell_midi(70, 0)[:2], ("A", "♯"))

        c_major = build_staff_layout(make_score([note(61, 1)], key_fifths=0))
        self.assertEqual(c_major.notes[0].accidental, "♯")

        f_major = build_staff_layout(make_score([note(70, 1)], key_fifths=-1))
        self.assertEqual(f_major.notes[0].accidental, "")  # covered by the key

    def test_playhead_maps_seconds_to_system_and_x(self) -> None:
        score = make_score(
            [note(72, measure) for measure in range(1, 6)],
            measures=5,
            tempo=120.0,
        )
        layout = build_staff_layout(score, measures_per_system=4)

        self.assertEqual(layout.playhead(0.0), (0, 0.0))
        self.assertEqual(layout.playhead(2.0), (0, 0.25))  # start of measure 2
        self.assertEqual(layout.playhead(8.0), (1, 0.0))  # start of measure 5
        self.assertEqual(layout.playhead(9.0), (1, 0.5))  # half of the last measure

    def test_musicxml_spelling_is_preserved(self) -> None:
        spelled = ScoreNote(
            midi=70,
            start=0.0,
            duration=1.0,
            measure=1,
            beat=1.0,
            step="B",
            alter=-1,
            octave=4,
        )
        c_major = build_staff_layout(make_score([spelled], key_fifths=0))
        self.assertEqual(c_major.notes[0].letter, "B")
        self.assertEqual(c_major.notes[0].accidental, "♭")
        self.assertEqual(c_major.notes[0].step, 4)

        f_major = build_staff_layout(make_score([spelled], key_fifths=-1))
        self.assertEqual(f_major.notes[0].accidental, "")  # covered by the key

        natural = ScoreNote(
            midi=71,
            start=0.0,
            duration=1.0,
            measure=1,
            beat=1.0,
            step="B",
            alter=0,
            octave=4,
        )
        f_natural = build_staff_layout(make_score([natural], key_fifths=-1))
        self.assertEqual(f_natural.notes[0].accidental, "♮")

    def test_empty_score_has_no_systems(self) -> None:
        layout = build_staff_layout(make_score([], measures=0))

        self.assertEqual(layout.systems, ())
        self.assertEqual(layout.notes, ())


class KeySignatureParseTest(unittest.TestCase):
    def test_musicxml_key_fifths_are_read(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>-1</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>B</step><alter>-1</alter><octave>4</octave></pitch>
        <duration>4</duration>
      </note>
    </measure>
  </part>
</score-partwise>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flat.musicxml"
            path.write_text(xml, encoding="utf-8")
            score = parse_score(path)

        self.assertEqual(score.key_fifths, -1)
        self.assertEqual([item.midi for item in score.notes], [70])

    def test_all_musicxml_parts_are_parsed(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Right</part-name></score-part>
    <score-part id="P2"><part-name>Left</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes><divisions>1</divisions></attributes>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "two_parts.musicxml"
            path.write_text(xml, encoding="utf-8")
            score = parse_score(path)

        self.assertEqual(sorted(item.midi for item in score.notes), [48, 72])
        self.assertEqual(
            sorted(item.part for item in score.notes), ["P1", "P2"]
        )
        self.assertEqual(score.measure_count, 1)


if __name__ == "__main__":
    unittest.main()
