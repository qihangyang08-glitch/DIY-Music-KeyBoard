"""Behaviour tests for stage-7 project acceptance rules (no Qt).

A task turns the design's step list into checkable facts about the project:
notes in a track, a second low voice, a four-bar loop. The tests construct
projects directly and never inspect how a step is stored.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import project_path, stage_by_index
from app.core.project import LoopRegion, NoteEvent, Project
from app.core.project_task import TASKS


class MelodyTaskTest(unittest.TestCase):
    def test_melody_needs_four_c_major_notes(self) -> None:
        task = TASKS["stage7_melody"]
        project = Project()
        track = project.add_track("旋律")
        track.notes = [NoteEvent(i, 60 + 2 * i, 1.0) for i in range(3)]

        self.assertEqual(task.evaluate(project), [False, True])
        self.assertFalse(task.done(project))

        track.notes.append(NoteEvent(3.0, 64, 1.0))
        self.assertEqual(task.evaluate(project), [True, True])
        self.assertTrue(task.done(project))

        track.notes[1] = NoteEvent(1.0, 61, 1.0)
        self.assertEqual(task.evaluate(project), [True, False])
        self.assertFalse(task.done(project))


class RecordReviewTaskTest(unittest.TestCase):
    def test_recording_review_needs_eight_notes_over_two_bars(self) -> None:
        task = TASKS["stage6_record_review"]
        project = Project()
        track = project.add_track("录音")
        track.notes = [NoteEvent(i, 65 + i % 8, 1.0) for i in range(7)]

        self.assertEqual(task.evaluate(project), [False, True])
        self.assertFalse(task.done(project))

        track.notes.append(NoteEvent(7.0, 72, 1.0))
        self.assertEqual(task.evaluate(project), [True, True])
        self.assertTrue(task.done(project))

    def test_recording_review_is_wired_into_stage6(self) -> None:
        stage6 = stage_by_index(6)
        item = next(item for item in stage6.trainings if item.name == "录音自评")
        self.assertEqual(item.project, "stage6_record_review")
        self.assertIs(item.task, TASKS["stage6_record_review"])
        self.assertTrue(item.ready)
        self.assertIsNotNone(project_path(item.project))


class OverdubTaskTest(unittest.TestCase):
    def test_overdub_needs_a_second_low_voice(self) -> None:
        task = TASKS["stage7_overdub_bass"]
        project = Project()
        melody = project.add_track("旋律")
        bass = project.add_track("低音")
        melody.notes = [NoteEvent(i, 60 + i, 1.0) for i in range(4)]

        self.assertEqual(task.evaluate(project), [True, False, True])
        bass.notes = [NoteEvent(0.0, 48, 1.0), NoteEvent(1.0, 50, 1.0)]
        self.assertEqual(task.evaluate(project), [True, True, True])
        self.assertTrue(task.done(project))


class LoopTaskTest(unittest.TestCase):
    def test_loop_needs_four_bars_and_notes_inside(self) -> None:
        task = TASKS["stage7_loop_four_bars"]
        project = Project()
        track = project.add_track("循环")

        self.assertEqual(task.evaluate(project), [False, False])

        project.loop = LoopRegion(0.0, 12.0)
        track.notes = [NoteEvent(i, 60, 1.0) for i in range(4)]
        self.assertEqual(task.evaluate(project), [False, True])

        project.loop = LoopRegion(0.0, 16.0)
        self.assertEqual(task.evaluate(project), [True, True])

        track.notes.append(NoteEvent(20.0, 64, 1.0))
        self.assertEqual(task.evaluate(project), [True, False])


class TrioTaskTest(unittest.TestCase):
    def test_trio_needs_three_voices_notes_and_two_timbres(self) -> None:
        task = TASKS["stage7_trio"]
        project = Project()
        for index, program in enumerate((0, 48, 32)):
            track = project.add_track(f"轨 {index + 1}")
            track.program = program
            track.notes = [
                NoteEvent(0.0, 48 + index, 1.0),
                NoteEvent(1.0, 50 + index, 1.0),
            ]

        self.assertEqual(task.evaluate(project), [True, True, True])
        self.assertTrue(task.done(project))

        project.tracks[2].notes.pop()
        self.assertEqual(task.evaluate(project), [True, False, True])

        project.tracks[2].notes.append(NoteEvent(2.0, 52, 1.0))
        for track in project.tracks:
            track.program = 0
        self.assertEqual(task.evaluate(project), [True, True, False])


class QuantizeTaskTest(unittest.TestCase):
    def test_quantize_training_needs_notes_and_an_applied_grid(self) -> None:
        task = TASKS["stage7_quantize"]
        project = Project()
        track = project.add_track("旋律")
        track.notes = [NoteEvent(float(i), 60 + i, 0.5) for i in range(4)]

        self.assertEqual(task.evaluate(project), [True, False])

        project.quantize_grid = 0.5
        self.assertEqual(task.evaluate(project), [True, True])


class CountInTaskTest(unittest.TestCase):
    def test_count_in_training_needs_a_take_with_count_in_and_click(self) -> None:
        task = TASKS["stage7_count_in"]
        project = Project()
        track = project.add_track("旋律")
        track.notes = [NoteEvent(float(i), 60 + i, 0.5) for i in range(4)]

        self.assertEqual(task.evaluate(project), [True, False, False])

        project.count_in_used = True
        self.assertEqual(task.evaluate(project), [True, True, False])

        project.metronome_used = True
        self.assertTrue(task.done(project))


class ExportTaskTest(unittest.TestCase):
    def test_export_training_needs_notes_and_a_midi_file(self) -> None:
        task = TASKS["stage7_export"]
        project = Project()
        track = project.add_track("旋律")
        track.notes = [NoteEvent(float(i), 60 + i, 0.5) for i in range(4)]

        self.assertEqual(task.evaluate(project), [True, False])

        project.exported = True
        self.assertTrue(task.done(project))


class MelodyAccompanimentTaskTest(unittest.TestCase):
    def test_project_needs_eight_bars_and_a_second_voice(self) -> None:
        task = TASKS["stage7_melody_accompaniment"]
        project = Project()
        melody = project.add_track("旋律")
        melody.program = 0
        melody.notes = [
            NoteEvent(float(i * 4), 60 + i, 2.0) for i in range(8)
        ]
        accompaniment = project.add_track("伴奏")
        accompaniment.program = 48

        self.assertEqual(
            task.evaluate(project), [True, True, False, False, True]
        )

        accompaniment.notes = [
            NoteEvent(float(i * 4), 48, 4.0) for i in range(4)
        ]
        self.assertTrue(task.done(project))


class AabaTaskTest(unittest.TestCase):
    def test_project_needs_sixteen_bars_and_four_filled_sections(self) -> None:
        task = TASKS["stage7_aaba"]
        project = Project()
        melody = project.add_track("旋律")
        bass = project.add_track("低音")
        melody.notes = [
            NoteEvent(float(start), 60, 2.0)
            for start in (0, 4, 8, 12, 16, 20, 24, 28, 48, 52, 56, 60)
        ]
        bass.notes = [
            NoteEvent(float(start), 48, 4.0)
            for start in (0, 8, 16, 24, 48, 56)
        ]

        self.assertEqual(task.evaluate(project), [True, False, True, True])

        melody.notes.append(NoteEvent(32.0, 62, 2.0))
        self.assertTrue(task.done(project))


class LoopPieceTaskTest(unittest.TestCase):
    def test_project_needs_a_four_bar_loop_with_notes_inside(self) -> None:
        task = TASKS["stage7_loop_piece"]
        project = Project()
        melody = project.add_track("旋律")
        bass = project.add_track("低音")
        melody.notes = [NoteEvent(float(i * 2), 60 + i, 1.0) for i in range(8)]
        bass.notes = [NoteEvent(float(i * 4), 48, 2.0) for i in range(4)]

        self.assertEqual(task.evaluate(project), [False, False, True])

        project.loop = LoopRegion(0.0, 16.0)
        self.assertTrue(task.done(project))

        bass.notes.append(NoteEvent(20.0, 48, 1.0))
        self.assertEqual(task.evaluate(project), [True, False, True])


class FinalPieceTaskTest(unittest.TestCase):
    def test_project_needs_two_full_voices_and_an_export(self) -> None:
        task = TASKS["stage7_final"]
        project = Project()
        melody = project.add_track("旋律")
        bass = project.add_track("低音")
        melody.notes = [NoteEvent(float(i), 60 + i, 0.5) for i in range(8)]
        bass.notes = [NoteEvent(float(i), 48, 0.5) for i in range(8)]

        self.assertEqual(task.evaluate(project), [True, True, False])

        project.exported = True
        self.assertTrue(task.done(project))


class CurriculumProjectWiringTest(unittest.TestCase):
    def test_stage7_is_fully_ready(self) -> None:
        stage = stage_by_index(7)

        self.assertEqual(stage.ready_count, 11)
        self.assertEqual(stage.total_count, 11)
        for item in stage.items:
            self.assertTrue(item.ready)
            self.assertIsNotNone(item.task)
            self.assertIsNotNone(project_path(item.project))

    def test_stage7_trio_piece_is_wired(self) -> None:
        piece = stage_by_index(7).pieces[0]
        self.assertEqual(piece.name, "三轨小作品")
        self.assertTrue(piece.ready)
        self.assertEqual(piece.task, TASKS["stage7_trio"])

    def test_new_stage7_assets_are_wired(self) -> None:
        stage = stage_by_index(7)
        self.assertEqual(
            tuple(item.project for item in stage.trainings),
            (
                "stage7_melody",
                "stage7_overdub_bass",
                "stage7_quantize",
                "stage7_loop_four_bars",
                "stage7_count_in",
                "stage7_export",
            ),
        )
        self.assertEqual(
            tuple(item.project for item in stage.pieces),
            (
                "stage7_trio",
                "stage7_melody_accompaniment",
                "stage7_aaba",
                "stage7_loop_piece",
                "stage7_final",
            ),
        )


if __name__ == "__main__":
    unittest.main()
