"""Behaviour tests for piano-roll note editing (no Qt).

The editor owns one track at a time. Every gesture (click, drag, resize,
duplicate) is one undo step; coordinates are clamped so a drag cannot create
negative starts or out-of-range MIDI notes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.editor import MIN_DURATION, NoteEditor
from app.core.project import NoteEvent, Project


def editor_with_notes(*notes: NoteEvent) -> tuple[NoteEditor, Project]:
    project = Project()
    project.add_track("旋律").notes.extend(notes)
    project.add_track("低音")
    return NoteEditor(project), project


class AddEraseTest(unittest.TestCase):
    def test_add_note_sorts_and_returns_its_index(self) -> None:
        editor, project = editor_with_notes()

        editor.add_note(4.0, 64, 1.0)
        index = editor.add_note(0.0, 60, 0.5)

        self.assertEqual(index, 0)
        self.assertEqual(
            [(note.start, note.midi) for note in project.tracks[0].notes],
            [(0.0, 60), (4.0, 64)],
        )

    def test_erase_removes_only_the_given_note(self) -> None:
        editor, project = editor_with_notes(
            NoteEvent(0.0, 60, 1.0), NoteEvent(4.0, 64, 1.0)
        )

        self.assertTrue(editor.erase_note(0))
        self.assertEqual([note.midi for note in project.tracks[0].notes], [64])
        self.assertFalse(editor.erase_note(5))


class MoveResizeTest(unittest.TestCase):
    def test_move_clamps_start_and_midi(self) -> None:
        editor, project = editor_with_notes(NoteEvent(0.5, 60, 1.0))

        editor.move_note(0, -4.0, -100)

        note = project.tracks[0].notes[0]
        self.assertEqual((note.start, note.midi), (0.0, 0))

        editor.move_note(0, 2.0, 5)
        note = project.tracks[0].notes[0]
        self.assertEqual((note.start, note.midi), (2.0, 5))

    def test_resize_never_goes_below_the_grid_minimum(self) -> None:
        editor, project = editor_with_notes(NoteEvent(0.0, 60, 0.5))

        editor.resize_note(0, -10.0)
        self.assertEqual(project.tracks[0].notes[0].duration, MIN_DURATION)

        editor.resize_note(0, 2.0)
        self.assertEqual(project.tracks[0].notes[0].duration, 2.25)

    def test_duplicate_places_a_copy_after_the_note(self) -> None:
        editor, project = editor_with_notes(NoteEvent(1.0, 60, 1.0))

        index = editor.duplicate_note(0)

        self.assertEqual(index, 1)
        self.assertEqual(
            [(note.start, note.midi) for note in project.tracks[0].notes],
            [(1.0, 60), (2.0, 60)],
        )


class UndoTest(unittest.TestCase):
    def test_each_edit_is_one_undo_step(self) -> None:
        editor, project = editor_with_notes()

        editor.add_note(0.0, 60)
        editor.add_note(1.0, 62)
        self.assertEqual(len(project.tracks[0].notes), 2)

        self.assertTrue(editor.undo())
        self.assertEqual([note.midi for note in project.tracks[0].notes], [60])
        self.assertTrue(editor.undo())
        self.assertEqual(project.tracks[0].notes, [])
        self.assertFalse(editor.undo())

    def test_a_drag_gesture_is_one_undo_step(self) -> None:
        editor, project = editor_with_notes(NoteEvent(0.0, 60, 1.0))

        editor.begin_gesture()
        editor.update_note(0, start=1.0)
        editor.update_note(0, start=2.0)
        editor.end_gesture()
        self.assertEqual(project.tracks[0].notes[0].start, 2.0)

        editor.undo()
        self.assertEqual(
            [(note.start, note.midi, note.duration) for note in project.tracks[0].notes],
            [(0.0, 60, 1.0)],
        )

    def test_a_click_without_change_adds_no_undo_step(self) -> None:
        editor, project = editor_with_notes(NoteEvent(0.0, 60, 1.0))

        editor.begin_gesture()
        editor.end_gesture()

        self.assertFalse(editor.undo())

    def test_undo_targets_the_track_that_was_edited(self) -> None:
        editor, project = editor_with_notes()
        editor.select_track(1)
        editor.add_note(2.0, 48)

        editor.select_track(0)
        self.assertTrue(editor.undo())

        self.assertEqual(project.tracks[1].notes, [])
        self.assertEqual(editor.track_index, 1)


class ProjectSwapTest(unittest.TestCase):
    def test_set_project_resets_history_and_edits_the_new_track(self) -> None:
        editor, _old = editor_with_notes(NoteEvent(0.0, 60, 1.0))
        editor.add_note(1.0, 62)

        new_project = Project()
        new_project.add_track("新轨")
        editor.set_project(new_project, 0)

        self.assertFalse(editor.undo())
        editor.add_note(0.0, 67)
        self.assertEqual([n.midi for n in new_project.tracks[0].notes], [67])


if __name__ == "__main__":
    unittest.main()
