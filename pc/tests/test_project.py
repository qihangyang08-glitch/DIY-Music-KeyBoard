"""Behaviour tests for the creative project model (no Qt).

A project is the user's work: tracks, their settings, note events, tempo, and
the loop region. These tests treat save/load as the public behaviour and never
inspect the JSON shape.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import (
    Layer,
    LoopRegion,
    NoteEvent,
    Project,
    SplitSpec,
    Track,
    default_project_dir,
)


class ProjectJsonTest(unittest.TestCase):
    def test_project_round_trips_through_json(self) -> None:
        project = Project(
            title="我的第一首",
            tempo=90.0,
            time_signature=(3, 4),
            loop=LoopRegion(0.0, 12.0),
            visibility="private",
            public_release="unknown",
        )
        piano = project.add_track("钢琴")
        piano.program = 0
        piano.notes.append(NoteEvent(0.0, 60, 1.0))
        piano.notes.append(NoteEvent(1.5, 64, 0.5))
        piano.layer = Layer(program=48, volume=0.6)
        strings = project.add_track("弦乐")
        strings.program = 48
        strings.volume = 0.7
        strings.pan = -0.25
        strings.split = SplitSpec(
            midi=60,
            left_program=32,
            right_program=48,
            left_volume=0.6,
            right_volume=0.9,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.json"
            project.save(path)
            loaded = Project.load(path)

        self.assertEqual(loaded, project)

    def test_mix_space_and_export_state_round_trip(self) -> None:
        project = Project(title="混音", reverb=0.35, exported=True)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.json"
            project.save(path)
            loaded = Project.load(path)

        self.assertAlmostEqual(loaded.reverb, 0.35, places=2)
        self.assertTrue(loaded.exported)

    def test_reverb_is_clamped_to_the_usable_range(self) -> None:
        high = Project.from_dict({"reverb": 4.2})
        low = Project.from_dict({"reverb": -1.0})
        broken = Project.from_dict({"reverb": "wet"})

        self.assertEqual(high.reverb, 1.0)
        self.assertEqual(low.reverb, 0.0)
        self.assertEqual(broken.reverb, 0.0)

    def test_recording_metadata_round_trips(self) -> None:
        project = Project(
            quantize_grid=0.5,
            count_in_used=True,
            metronome_used=True,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "take.json"
            project.save(path)
            loaded = Project.load(path)

        self.assertEqual(loaded.quantize_grid, 0.5)
        self.assertTrue(loaded.count_in_used)
        self.assertTrue(loaded.metronome_used)

    def test_negative_quantize_grid_loads_as_off(self) -> None:
        self.assertEqual(Project.from_dict({"quantize_grid": -1}).quantize_grid, 0.0)
        self.assertEqual(Project.from_dict({"quantize_grid": "x"}).quantize_grid, 0.0)


class TrackLimitTest(unittest.TestCase):
    def test_project_never_holds_more_than_eight_tracks(self) -> None:
        project = Project()
        for index in range(8):
            project.add_track(f"音轨 {index + 1}")

        with self.assertRaises(ValueError):
            project.add_track("第九轨")
        self.assertEqual(len(project.tracks), 8)

        oversized = Project(tracks=[Track(f"音轨 {index + 1}") for index in range(9)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.json"
            oversized.save(path)
            loaded = Project.load(path)
        self.assertEqual(len(loaded.tracks), 8)


class ProjectPathTest(unittest.TestCase):
    def test_default_project_dir_is_the_projects_folder(self) -> None:
        self.assertEqual(default_project_dir().name, "projects")


if __name__ == "__main__":
    unittest.main()
