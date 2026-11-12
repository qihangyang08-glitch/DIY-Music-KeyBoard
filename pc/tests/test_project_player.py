"""Clock-driven tests for ProjectPlayer (no audio, no event loop needed)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.project import LoopRegion, NoteEvent, Project
from app.ui.project_player import ProjectPlayer


class FakeSynth:
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.programs: list[tuple[int, int]] = []
        self.volumes: list[tuple[int, float]] = []
        self.pans: list[tuple[int, float]] = []

    def program_on(self, channel: int, program: int) -> None:
        self.programs.append((channel, program))

    def channel_volume(self, channel: int, volume: float) -> None:
        self.volumes.append((channel, volume))

    def channel_pan(self, channel: int, pan: float) -> None:
        self.pans.append((channel, pan))

    def note_on(self, midi: int, velocity: int, channel=None) -> None:
        self.events.append(("on", channel, midi, velocity))

    def note_off(self, midi: int, channel=None) -> None:
        self.events.append(("off", channel, midi))


def one_note_project(loop: bool = False) -> Project:
    project = Project(tempo=120.0)
    track = project.add_track("旋律")
    track.program = 0
    track.notes = [NoteEvent(0.0, 60, 1.0)]
    if loop:
        project.loop = LoopRegion(0.0, 1.0)
    return project


class ProjectPlayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def make_player(self, project: Project) -> tuple[ProjectPlayer, FakeSynth]:
        synth = FakeSynth()
        player = ProjectPlayer(synth, auto_timer=False)
        player.set_project(project)
        return player, synth

    def test_play_prepares_mix_and_schedules_notes(self) -> None:
        player, synth = self.make_player(one_note_project())
        finished: list[bool] = []
        player.finished.connect(lambda: finished.append(True))

        self.assertTrue(player.play(at=100.0))
        self.assertEqual(synth.programs, [(1, 0)])
        self.assertEqual(synth.volumes, [(1, 1.0)])
        self.assertEqual(synth.pans, [(1, 0.0)])

        player.advance(100.01)
        self.assertIn(("on", 1, 60, 100), synth.events)

        player.advance(100.6)
        self.assertIn(("off", 1, 60), synth.events)
        self.assertFalse(player.playing)
        self.assertTrue(finished)

    def test_loop_wraps_and_retriggers_notes(self) -> None:
        player, synth = self.make_player(one_note_project(loop=True))
        player.play(at=100.0)

        player.advance(100.01)
        player.advance(100.3)
        player.advance(100.6)

        ons = [event for event in synth.events if event[0] == "on"]
        offs = [event for event in synth.events if event[0] == "off"]
        self.assertEqual(len(ons), 2)
        self.assertGreaterEqual(len(offs), 1)
        self.assertTrue(player.playing)

    def test_stop_releases_held_notes_and_resets_position(self) -> None:
        player, synth = self.make_player(one_note_project())
        positions: list[float] = []
        player.positionChanged.connect(positions.append)
        player.play(at=100.0)
        player.advance(100.01)

        player.stop()

        self.assertIn(("off", 1, 60), synth.events)
        self.assertFalse(player.playing)
        self.assertEqual(player.position, 0.0)
        self.assertEqual(positions[-1], 0.0)

    def test_empty_project_does_not_start(self) -> None:
        player, synth = self.make_player(Project())
        messages: list[str] = []
        player.message.connect(messages.append)

        self.assertFalse(player.play(at=100.0))
        self.assertFalse(player.playing)
        self.assertEqual(synth.events, [])
        self.assertIn("还没有可播放", messages[-1])


if __name__ == "__main__":
    unittest.main()
