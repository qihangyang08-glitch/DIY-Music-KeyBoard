"""Behaviour tests for note-event recording (no Qt).

The recorder answers one question: given note-on/note-off beats from the 32-key
input, what note events were played? Times are musical beats, so a later
piano-roll or MIDI export does not need a tempo to understand them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import LoopRegion, NoteEvent, Project
from app.core.recorder import Recorder, quantize


class RecordOneNoteTest(unittest.TestCase):
    def test_note_on_and_off_become_one_event(self) -> None:
        recorder = Recorder()
        recorder.start()
        recorder.note_on(60, 0.0)
        recorder.note_off(60, 1.0)

        events = recorder.stop(1.0)

        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].start, events[0].midi, events[0].duration),
                         (0.0, 60, 1.0))

    def test_stop_closes_notes_still_held(self) -> None:
        recorder = Recorder()
        recorder.start()
        recorder.note_on(64, 2.0)

        events = recorder.stop(3.5)

        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].start, events[0].midi, events[0].duration),
                         (2.0, 64, 1.5))


class LoopRecordingTest(unittest.TestCase):
    def test_later_loop_pass_lands_inside_the_loop(self) -> None:
        recorder = Recorder(loop=LoopRegion(0.0, 4.0))
        recorder.start()
        recorder.note_on(60, 5.0)
        recorder.note_off(60, 5.5)

        events = recorder.stop(5.5)

        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].start, events[0].midi, events[0].duration),
                         (1.0, 60, 0.5))

    def test_note_crossing_loop_end_is_clipped(self) -> None:
        recorder = Recorder(loop=LoopRegion(0.0, 4.0))
        recorder.start()
        recorder.note_on(60, 3.5)
        recorder.note_off(60, 5.0)

        events = recorder.stop(5.0)

        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].start, events[0].midi, events[0].duration),
                         (3.5, 60, 0.5))


class QuantizeTest(unittest.TestCase):
    def test_quantize_moves_onsets_but_keeps_pitch_and_duration(self) -> None:
        events = [
            NoteEvent(0.1, 60, 0.75),
            NoteEvent(1.4, 64, 0.5),
        ]

        moved = quantize(events, grid=1.0)

        self.assertEqual(
            [(event.start, event.midi, event.duration) for event in moved],
            [(0.0, 60, 0.75), (1.0, 64, 0.5)],
        )


class OverdubTest(unittest.TestCase):
    def test_overdub_keeps_existing_notes_and_merges_in_time_order(self) -> None:
        project = Project()
        track = project.add_track("钢琴")
        track.notes.append(NoteEvent(4.0, 60, 1.0))

        recorder = Recorder()
        recorder.start()
        recorder.note_on(64, 1.0)
        recorder.note_off(64, 2.0)
        recorder.note_on(67, 6.0)
        recorder.note_off(67, 7.0)

        track.overdub(recorder.stop(7.0))

        self.assertEqual(
            [(event.start, event.midi) for event in track.notes],
            [(1.0, 64), (4.0, 60), (6.0, 67)],
        )


if __name__ == "__main__":
    unittest.main()
