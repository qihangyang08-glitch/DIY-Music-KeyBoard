"""Behaviour tests for the project playback plan (no Qt)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.playback import build_playback
from app.core.project import (
    Layer,
    LoopRegion,
    NoteEvent,
    Project,
    SplitSpec,
)


def project_120() -> Project:
    project = Project(tempo=120.0, time_signature=(4, 4))
    melody = project.add_track("旋律")
    melody.program = 0
    melody.volume = 0.8
    melody.notes = [NoteEvent(0.0, 60, 1.0), NoteEvent(1.0, 64, 0.5)]
    bass = project.add_track("低音")
    bass.program = 48
    bass.pan = -0.5
    bass.notes = [NoteEvent(0.0, 48, 2.0)]
    return project


class PlaybackPlanTest(unittest.TestCase):
    def test_beats_become_seconds_and_tracks_get_channels(self) -> None:
        plan = build_playback(project_120())

        self.assertEqual([track.channel for track in plan.tracks], [1, 2])
        self.assertEqual([track.program for track in plan.tracks], [0, 48])
        melody = plan.tracks[0]
        self.assertEqual(
            [(round(note.start, 3), round(note.end, 3), note.midi) for note in melody.notes],
            [(0.0, 0.5, 60), (0.5, 0.75, 64)],
        )
        self.assertAlmostEqual(plan.duration, 1.0, places=3)

    def test_mute_and_solo_filter_the_plan(self) -> None:
        project = project_120()
        project.tracks[1].mute = True
        self.assertEqual([track.program for track in build_playback(project).tracks], [0])

        project.tracks[1].mute = False
        project.tracks[1].solo = True
        self.assertEqual([track.program for track in build_playback(project).tracks], [48])

    def test_loop_clips_notes_and_sets_duration(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("旋律")
        track.notes = [
            NoteEvent(3.5, 60, 1.0),   # crosses the loop end (4 beats = 2 s)
            NoteEvent(5.0, 64, 1.0),   # outside the loop
        ]
        project.loop = LoopRegion(0.0, 4.0)

        plan = build_playback(project)

        notes = plan.tracks[0].notes
        self.assertEqual(len(notes), 1)
        self.assertAlmostEqual(notes[0].start, 1.75, places=3)
        self.assertAlmostEqual(notes[0].end, 2.0, places=3)
        self.assertAlmostEqual(plan.duration, 2.0, places=3)
        self.assertTrue(plan.loop)

    def test_layer_adds_a_second_voice_on_a_new_channel(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("旋律")
        track.program = 0
        track.volume = 0.9
        track.layer = Layer(48, 0.6)
        track.notes = [NoteEvent(0.0, 60, 1.0)]

        plan = build_playback(project)

        self.assertEqual(len(plan.tracks), 2)
        self.assertEqual([item.program for item in plan.tracks], [0, 48])
        self.assertEqual([item.channel for item in plan.tracks], [1, 2])
        self.assertEqual(plan.tracks[1].notes[0].midi, 60)
        self.assertAlmostEqual(plan.tracks[1].volume, 0.6, places=3)

    def test_split_routes_low_and_high_notes_to_two_voices(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("键盘")
        track.program = 0
        track.split = SplitSpec(
            midi=60, left_program=32, right_program=0,
            left_volume=0.7, right_volume=0.9,
        )
        track.notes = [NoteEvent(0.0, 48, 1.0), NoteEvent(0.5, 72, 1.0)]

        plan = build_playback(project)

        self.assertEqual(len(plan.tracks), 2)
        self.assertEqual([item.program for item in plan.tracks], [32, 0])
        self.assertEqual([item.channel for item in plan.tracks], [1, 2])
        self.assertEqual(
            [note.midi for note in plan.tracks[0].notes], [48]
        )
        self.assertEqual(
            [note.midi for note in plan.tracks[1].notes], [72]
        )
        self.assertAlmostEqual(plan.tracks[0].volume, 0.7, places=3)
        self.assertAlmostEqual(plan.tracks[1].volume, 0.9, places=3)

    def test_channels_skip_the_drum_channel_9(self) -> None:
        project = Project(tempo=120.0)
        for index in range(5):
            track = project.add_track(f"轨 {index}")
            track.layer = Layer(48, 0.5)
            track.notes = [NoteEvent(0.0, 60 + index, 1.0)]

        plan = build_playback(project)

        self.assertEqual(
            [item.channel for item in plan.tracks],
            [1, 2, 3, 4, 5, 6, 7, 8, 10, 11],
        )

    def test_empty_project_has_an_empty_plan(self) -> None:
        plan = build_playback(Project())
        self.assertTrue(plan.empty)
        self.assertEqual(plan.duration, 0.0)


if __name__ == "__main__":
    unittest.main()
