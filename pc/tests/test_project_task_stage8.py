"""Behaviour tests for stage-8 project acceptance rules (no Qt).

Stage 8 turns the mixing controls into checkable facts: a second timbre on one
track, a split keyboard, a three-voice arrangement, balanced volume/pan, a
reverb send, and an exported MIDI file. The tests build projects directly and
only assert what each step means musically.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import project_path, stage_by_index
from app.core.project import Layer, NoteEvent, Project, SplitSpec
from app.core.project_task import TASKS


def melody(track, count: int = 4, start: int = 60) -> None:
    track.notes = [NoteEvent(float(i), start + i, 1.0) for i in range(count)]


class LayerTaskTest(unittest.TestCase):
    def test_layer_training_needs_a_balanced_second_timbre(self) -> None:
        task = TASKS["stage8_layer"]
        project = Project()
        track = project.add_track("钢琴")
        melody(track)

        self.assertEqual(task.evaluate(project), [True, False, False, False])

        track.layer = Layer(48, 0.6)
        self.assertEqual(task.evaluate(project), [True, True, True, True])

        track.layer = Layer(0, 0.6)
        self.assertEqual(task.evaluate(project), [True, True, False, True])

        track.layer = Layer(48, 1.2)
        self.assertEqual(task.evaluate(project), [True, True, True, False])


class SplitTaskTest(unittest.TestCase):
    def test_split_training_needs_notes_on_both_sides(self) -> None:
        task = TASKS["stage8_split"]
        project = Project()
        track = project.add_track("键盘")
        track.notes = [
            NoteEvent(0.0, 48, 1.0),
            NoteEvent(1.0, 52, 1.0),
            NoteEvent(2.0, 84, 1.0),
            NoteEvent(3.0, 88, 1.0),
        ]

        self.assertEqual(task.evaluate(project), [False, False, False])

        track.split = SplitSpec(midi=60, left_program=32, right_program=0)
        self.assertEqual(task.evaluate(project), [True, True, True])

        track.notes.pop()
        track.notes.pop()
        self.assertEqual(task.evaluate(project), [True, False, True])


class ThreeTrackTaskTest(unittest.TestCase):
    def test_three_track_training_needs_notes_and_three_timbres(self) -> None:
        task = TASKS["stage8_three_tracks"]
        project = Project()
        for index, program in enumerate((0, 48, 32)):
            track = project.add_track(f"轨 {index + 1}")
            track.program = program
            melody(track, 2, 48 + index)

        self.assertEqual(task.evaluate(project), [True, True, True])

        project.tracks[2].notes.pop()
        self.assertEqual(task.evaluate(project), [True, False, True])

        project.tracks[2].notes.append(NoteEvent(2.0, 50, 1.0))
        for track in project.tracks:
            track.program = 0
        self.assertEqual(task.evaluate(project), [True, True, False])


class MixTaskTest(unittest.TestCase):
    def test_mix_training_needs_volume_shape_and_pan_spread(self) -> None:
        task = TASKS["stage8_mix"]
        project = Project()
        for index in range(3):
            track = project.add_track(f"轨 {index + 1}")
            melody(track, 4, 60 + index)

        self.assertEqual(task.evaluate(project), [True, False, False])

        project.tracks[0].volume = 0.9
        project.tracks[1].volume = 0.5
        project.tracks[0].pan = -0.4
        project.tracks[2].pan = 0.4
        self.assertEqual(task.evaluate(project), [True, True, True])

        project.tracks[0].mute = True
        project.tracks[1].mute = True
        self.assertEqual(task.evaluate(project), [False, True, True])


class ReverbTaskTest(unittest.TestCase):
    def test_reverb_training_needs_notes_and_a_wet_send(self) -> None:
        task = TASKS["stage8_reverb"]
        project = Project()
        melody(project.add_track("钢琴"))

        self.assertEqual(task.evaluate(project), [True, False])

        project.reverb = 0.3
        self.assertEqual(task.evaluate(project), [True, True])

        project.reverb = 0.1
        self.assertEqual(task.evaluate(project), [True, False])


class ExportTaskTest(unittest.TestCase):
    def test_export_training_needs_an_exported_two_voice_take(self) -> None:
        task = TASKS["stage8_export"]
        project = Project()
        melody(project.add_track("旋律"), 4, 60)
        melody(project.add_track("低音"), 4, 48)

        self.assertEqual(task.evaluate(project), [True, False, True])

        project.exported = True
        self.assertEqual(task.evaluate(project), [True, True, True])

        project.tracks[1].notes = []
        self.assertEqual(task.evaluate(project), [False, True, False])


class Stage8ProjectTest(unittest.TestCase):
    def test_piano_strings_piece_needs_a_strings_layer(self) -> None:
        task = TASKS["stage8_piano_strings"]
        project = Project()
        piano = project.add_track("钢琴")
        piano.volume = 0.85
        melody(piano, 4, 60)
        strings = project.add_track("弦乐")
        strings.program = 48
        melody(strings, 4, 48)

        self.assertEqual(
            task.evaluate(project), [True, False, False, True, True]
        )

        piano.layer = Layer(48, 0.6)
        self.assertTrue(task.done(project))

        piano.layer = Layer(48, 0.95)
        self.assertEqual(
            task.evaluate(project), [True, True, False, True, True]
        )

    def test_split_hands_piece_needs_bass_and_piano_zones(self) -> None:
        task = TASKS["stage8_split_hands"]
        project = Project()
        track = project.add_track("键盘")
        track.notes = [
            NoteEvent(float(i), midi, 1.0)
            for i, midi in enumerate((48, 52, 55, 60, 84, 88, 91, 96))
        ]

        self.assertEqual(task.evaluate(project), [False, False, False, True])

        track.split = SplitSpec(midi=72, left_program=32, right_program=0)
        self.assertTrue(task.done(project))

        track.split = SplitSpec(midi=72, left_program=48, right_program=0)
        self.assertEqual(task.evaluate(project), [True, True, False, True])

    def test_trio_piece_needs_three_balanced_exported_voices(self) -> None:
        task = TASKS["stage8_trio"]
        project = Project(reverb=0.2)
        for index, (program, volume, pan) in enumerate(
            ((0, 0.85, 0.2), (48, 0.55, -0.2), (32, 0.7, -0.35))
        ):
            track = project.add_track(f"轨 {index + 1}")
            track.program = program
            track.volume = volume
            track.pan = pan
            melody(track, 4, 48 + index)

        self.assertEqual(
            task.evaluate(project), [True, True, True, True, True, False]
        )

        project.exported = True
        self.assertTrue(task.done(project))


class Stage8CurriculumWiringTest(unittest.TestCase):
    def test_stage8_is_fully_ready(self) -> None:
        stage = stage_by_index(8)

        self.assertEqual(stage.ready_count, 9)
        self.assertEqual(stage.total_count, 9)
        for item in stage.items:
            self.assertTrue(item.ready)
            self.assertIsNotNone(item.task)
            self.assertIsNotNone(project_path(item.project))

    def test_stage8_training_ids_are_wired(self) -> None:
        stage = stage_by_index(8)
        expected = (
            "stage8_layer",
            "stage8_split",
            "stage8_three_tracks",
            "stage8_mix",
            "stage8_reverb",
            "stage8_export",
        )
        self.assertEqual(
            tuple(item.project for item in stage.trainings), expected
        )
        self.assertEqual(
            tuple(item.project for item in stage.pieces),
            (
                "stage8_piano_strings",
                "stage8_split_hands",
                "stage8_trio",
            ),
        )


if __name__ == "__main__":
    unittest.main()
