"""Fingering, articulation, slur and pedal markings (B5)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.score import parse_score
from app.core.staff import build_staff_layout

MARKED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <work><work-title>Markings</work-title></work>
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <direction placement="below">
        <direction-type><pedal type="start"/></direction-type>
      </direction>
      <note>
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>1</duration><type>quarter</type>
        <notations>
          <technical><fingering>1</fingering></technical>
          <articulations><staccato/></articulations>
          <slur type="start" number="1"/>
        </notations>
      </note>
      <note>
        <pitch><step>D</step><octave>5</octave></pitch>
        <duration>1</duration><type>quarter</type>
        <notations>
          <technical><fingering>2</fingering></technical>
          <slur type="stop" number="1"/>
        </notations>
      </note>
      <note>
        <pitch><step>E</step><octave>5</octave></pitch>
        <duration>1</duration><type>quarter</type>
        <notations><articulations><accent/></articulations></notations>
      </note>
      <direction placement="below">
        <direction-type><pedal type="stop"/></direction-type>
      </direction>
      <note>
        <pitch><step>F</step><octave>5</octave></pitch>
        <duration>1</duration><type>quarter</type>
        <notations><articulations><tenuto/></articulations></notations>
      </note>
    </measure>
  </part>
</score-partwise>
"""


class ScoreMarkingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "marked.musicxml"
        self.path.write_text(MARKED_XML, encoding="utf-8")
        self.score = parse_score(self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fingering_articulation_and_slur_are_parsed(self) -> None:
        notes = self.score.notes
        self.assertEqual([note.finger for note in notes], [1, 2, 0, 0])
        self.assertEqual(notes[0].articulation, "staccato")
        self.assertEqual(notes[2].articulation, "accent")
        self.assertEqual(notes[3].articulation, "tenuto")
        self.assertTrue(notes[0].slur_start)
        self.assertTrue(notes[1].slur_end)
        self.assertFalse(notes[1].slur_start)

    def test_pedal_span_is_recorded_in_seconds(self) -> None:
        self.assertEqual(len(self.score.pedals), 1)
        start, stop = self.score.pedals[0]
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(stop, 1.5)  # 3 beats at 120 BPM

    def test_staff_layout_keeps_the_note_markings(self) -> None:
        layout = build_staff_layout(self.score)
        notes = [item.note for item in layout.notes]
        self.assertEqual(notes[0].finger, 1)
        self.assertEqual(notes[0].articulation, "staccato")
        self.assertEqual(notes[2].articulation, "accent")

    def test_rendering_and_toggle_do_not_crash(self) -> None:
        from app.ui.score_view import ScoreView
        from app.ui.theme import THEMES

        app = QApplication.instance() or QApplication([])
        view = ScoreView(THEMES["studio"])
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        view.resize(900, 560)
        view.show()
        view.set_score(self.score)
        app.processEvents()

        self.assertTrue(view.markers_button.isChecked())
        self.assertTrue(view.canvas._show_markings)
        self.assertFalse(view.canvas.grab().isNull())

        view.markers_button.click()
        self.assertFalse(view.canvas._show_markings)
        self.assertFalse(view.canvas.grab().isNull())

        view.close()
        view.deleteLater()


TEMPO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <direction><direction-type><sound tempo="120"/></direction-type></direction>
      <direction><direction-type><pedal type="start"/></direction-type></direction>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="2">
      <direction><direction-type><sound tempo="60"/></direction-type></direction>
      <note><pitch><step>D</step><octave>5</octave></pitch><duration>4</duration></note>
      <direction><direction-type><pedal type="stop"/></direction-type></direction>
    </measure>
  </part>
</score-partwise>
"""


class PedalBeatAndSlurPairingTest(unittest.TestCase):
    def test_pedal_keeps_beats_across_tempo_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tempo.musicxml"
            path.write_text(TEMPO_XML, encoding="utf-8")
            score = parse_score(path)

        self.assertEqual(score.pedal_beats, ((0.0, 8.0),))
        start, stop = score.pedals[0]
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(stop, 6.0)  # 4 beats @120 + 4 beats @60

    def test_slur_pairs_cross_barlines_and_keep_hands_apart(self) -> None:
        from app.ui.score_view import _slur_pairs

        class Note:
            def __init__(self, start=False, end=False, voice=""):
                self.slur_start = start
                self.slur_end = end
                self.voice = voice

        class Item:
            def __init__(self, note, staff):
                self.note = note
                self.staff = staff

        # Cross-bar: start on the last note of bar 1, stop in bar 2.
        self.assertEqual(_slur_pairs([Item(Note(start=True), "treble"),
                                      Item(Note(end=True), "treble")]), [(0, 1)])

        # Left hand start sorted before right hand start: each keeps its stop.
        items = [
            Item(Note(start=True), "bass"),
            Item(Note(start=True), "treble"),
            Item(Note(end=True), "treble"),
            Item(Note(end=True), "bass"),
        ]
        self.assertEqual(_slur_pairs(items), [(0, 3), (1, 2)])


if __name__ == "__main__":
    unittest.main()
