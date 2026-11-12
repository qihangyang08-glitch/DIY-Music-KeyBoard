"""Behaviour tests for the creation session (Qt-free).

ComposeSession is the seam between runtime note events (monotonic seconds) and
the project model (beats). These tests use explicit timestamps, so they check
conversion and merge semantics without any UI or audio.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.compose import ComposeSession
from app.core.project import LoopRegion, NoteEvent, Project, Track


class ComposeRecordingTest(unittest.TestCase):
    def test_seconds_become_beats_at_tempo(self) -> None:
        session = ComposeSession()
        session.start(100.0)
        session.note_on(60, 100.5)
        session.note_off(60, 101.5)

        count = session.stop(101.5)

        self.assertEqual(count, 1)
        self.assertIsNotNone(session.track)
        note = session.track.notes[0]
        self.assertEqual((note.start, note.midi, note.duration), (1.0, 60, 2.0))

    def test_notes_before_the_session_start_are_ignored(self) -> None:
        session = ComposeSession()
        session.start(1.0)
        session.note_on(60, 0.5)
        session.note_off(60, 0.6)
        session.note_on(64, 1.1)
        session.note_off(64, 1.2)
        session.stop(1.2)

        self.assertEqual([note.midi for note in session.track.notes], [64])

    def test_start_creates_the_first_track(self) -> None:
        session = ComposeSession()

        self.assertEqual(session.project.tracks, [])
        session.start(0.0)

        self.assertEqual(len(session.project.tracks), 1)
        self.assertIs(session.track, session.project.tracks[0])
        self.assertEqual(session.stop(0.0), 0)

    def test_double_start_keeps_the_first_take(self) -> None:
        session = ComposeSession()
        session.start(0.0)
        session.note_on(60, 0.0)
        session.note_off(60, 0.5)

        self.assertFalse(session.start(1.0))
        self.assertEqual(session.stop(1.0), 1)
        self.assertEqual([note.midi for note in session.track.notes], [60])

    def test_new_take_replaces_old_notes_but_empty_take_keeps_them(self) -> None:
        session = ComposeSession()
        session.start(0.0)
        session.note_on(60, 0.0)
        session.note_off(60, 0.5)
        session.stop(0.5)

        session.start(1.0)
        session.note_on(64, 1.0)
        session.note_off(64, 1.5)
        session.stop(1.5)
        self.assertEqual([note.midi for note in session.track.notes], [64])

        session.start(2.0)
        session.stop(2.5)
        self.assertEqual([note.midi for note in session.track.notes], [64])

    def test_overdub_keeps_the_previous_take(self) -> None:
        session = ComposeSession()
        session.start(0.0)
        session.note_on(60, 0.0)
        session.note_off(60, 0.5)
        session.stop(0.5)

        session.start(1.0, overdub=True)
        session.note_on(64, 2.0)
        session.note_off(64, 2.5)
        session.stop(2.5)

        self.assertEqual(
            [(note.start, note.midi) for note in session.track.notes],
            [(0.0, 60), (2.0, 64)],
        )

    def test_loop_recording_wraps_later_passes(self) -> None:
        session = ComposeSession()
        session.set_loop(True, bars=1)
        session.start(0.0)
        session.note_on(60, 2.5)
        session.note_off(60, 2.75)
        session.stop(2.75)

        note = session.track.notes[0]
        self.assertEqual((note.start, note.midi, note.duration), (1.0, 60, 0.5))

    def test_loop_cannot_change_while_recording(self) -> None:
        session = ComposeSession()
        session.start(0.0)

        self.assertFalse(session.set_loop(True, bars=1))
        self.assertIsNone(session.project.loop)


class ComposeTrackTest(unittest.TestCase):
    def test_program_and_volume_edit_the_selected_track_only(self) -> None:
        session = ComposeSession()
        first = session.add_track("钢琴")
        second = session.add_track("弦乐")
        session.select_track(1)

        self.assertEqual(session.program_index(), 0)
        self.assertEqual(session.cycle_program(), 1)
        self.assertEqual(second.program, 4)
        self.assertEqual(first.program, 0)
        self.assertEqual(session.adjust_volume(-0.1), 0.9)
        self.assertEqual(session.set_volume(2.0), 1.0)
        self.assertEqual(session.set_volume(-1.0), 0.0)
        self.assertEqual(first.volume, 1.0)

    def test_empty_project_accessors_do_not_raise(self) -> None:
        session = ComposeSession()

        self.assertIsNone(session.track)
        self.assertFalse(session.select_track(0))
        self.assertEqual(session.program_index(), 0)
        self.assertEqual(session.adjust_volume(0.1), 1.0)


class ComposeQuantizeTest(unittest.TestCase):
    def test_quantize_aligns_the_selected_track_and_records_the_grid(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("钢琴")
        track.notes = [
            NoteEvent(0.13, 60, 1.0),
            NoteEvent(0.62, 62, 1.0),
            NoteEvent(1.11, 64, 1.0),
        ]
        session = ComposeSession(project)

        count = session.quantize_track(0.5)

        self.assertEqual(count, 3)
        self.assertEqual(
            [note.start for note in track.notes], [0.0, 0.5, 1.0]
        )
        self.assertEqual(session.project.quantize_grid, 0.5)

    def test_quantize_with_no_track_or_zero_grid_does_nothing(self) -> None:
        empty = ComposeSession()
        self.assertEqual(empty.quantize_track(0.5), 0)
        self.assertEqual(empty.project.quantize_grid, 0.0)

        session = ComposeSession()
        track = session.add_track()
        track.notes = [NoteEvent(0.13, 60, 1.0)]
        self.assertEqual(session.quantize_track(0.0), 0)
        self.assertEqual(track.notes[0].start, 0.13)


class ComposePersistenceTest(unittest.TestCase):
    def test_load_replaces_the_session_project(self) -> None:
        project = Project(title="载入", tempo=90.0)
        track = project.add_track("钢琴")
        track.notes.append(NoteEvent(0.0, 60, 1.0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.json"
            project.save(path)
            session = ComposeSession()
            self.assertTrue(session.load(path))

        self.assertEqual(session.project, project)
        self.assertEqual(session.track_index, 0)

    def test_missing_file_does_not_replace_the_project(self) -> None:
        session = ComposeSession(Project(title="保留"))
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            self.assertFalse(session.load(missing))

        self.assertEqual(session.project.title, "保留")


if __name__ == "__main__":
    unittest.main()
