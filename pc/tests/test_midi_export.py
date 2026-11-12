"""Behaviour tests for project → Standard MIDI File export (no Qt).

The contract is the round trip: the app's own parser must read the exported
file back with the same notes, tempo, and time signature. Mute/solo decide
which tracks are audible in the exported mix.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.midi_export import export_midi
from app.core.project import Layer, NoteEvent, Project, SplitSpec
from app.core.score import parse_score


def two_track_project() -> Project:
    project = Project(title="导出测试", tempo=100.0, time_signature=(4, 4))
    melody = project.add_track("旋律")
    melody.program = 0
    melody.notes = [
        NoteEvent(0.0, 60, 1.0),
        NoteEvent(1.0, 64, 0.5),
    ]
    bass = project.add_track("低音")
    bass.program = 48
    bass.notes = [NoteEvent(0.0, 48, 2.0)]
    return project


class MidiRoundTripTest(unittest.TestCase):
    def test_notes_survive_export_and_reparse(self) -> None:
        project = two_track_project()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.mid"
            export_midi(project, path)
            score = parse_score(path)

        notes = sorted(
            (note.midi, round(note.start, 3), round(note.duration, 3))
            for note in score.notes
        )
        self.assertEqual(
            notes,
            [(48, 0.0, 1.2), (60, 0.0, 0.6), (64, 0.6, 0.3)],
        )
        self.assertAlmostEqual(score.tempo, 100.0, places=3)

    def test_tempo_and_time_signature_round_trip(self) -> None:
        project = Project(title="三拍", tempo=90.0, time_signature=(3, 4))
        project.add_track("旋律").notes = [NoteEvent(0.0, 60, 1.0)]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "waltz.mid"
            export_midi(project, path)
            score = parse_score(path)

        self.assertEqual(score.time_signature, (3, 4))
        self.assertAlmostEqual(score.tempo, 90.0, places=3)

    def test_mute_and_solo_filter_the_exported_mix(self) -> None:
        project = two_track_project()
        project.tracks[1].mute = True
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mute.mid"
            export_midi(project, path)
            muted = parse_score(path)

        self.assertEqual({note.midi for note in muted.notes}, {60, 64})

        project.tracks[1].mute = False
        project.tracks[1].solo = True
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "solo.mid"
            export_midi(project, path)
            soloed = parse_score(path)

        self.assertEqual({note.midi for note in soloed.notes}, {48})

    def test_program_volume_and_pan_are_written_for_each_track(self) -> None:
        project = two_track_project()
        melody = project.tracks[0]
        melody.program = 4
        melody.volume = 0.5
        melody.pan = -0.5

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.mid"
            export_midi(project, path)
            data = path.read_bytes()

        self.assertIn(bytes([0xC1, 4]), data)
        self.assertIn(bytes([0xB1, 7, 64]), data)
        self.assertIn(bytes([0xB1, 10, 32]), data)

    def test_layer_writes_a_second_track_with_the_same_notes(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("旋律")
        track.program = 0
        track.layer = Layer(48, 0.6)
        track.notes = [NoteEvent(0.0, 60, 1.0)]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layer.mid"
            export_midi(project, path)
            data = path.read_bytes()
            score = parse_score(path)

        self.assertIn(bytes([0xC2, 48]), data)
        self.assertIn(bytes([0xB2, 7, 76]), data)
        self.assertEqual(len(score.notes), 2)
        self.assertEqual({note.midi for note in score.notes}, {60})

    def test_split_writes_low_and_high_voices(self) -> None:
        project = Project(tempo=120.0)
        track = project.add_track("键盘")
        track.program = 0
        track.split = SplitSpec(
            midi=60, left_program=32, right_program=0
        )
        track.notes = [
            NoteEvent(0.0, 48, 1.0),
            NoteEvent(0.5, 72, 1.0),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "split.mid"
            export_midi(project, path)
            data = path.read_bytes()
            score = parse_score(path)

        self.assertIn(bytes([0xC1, 32]), data)
        self.assertIn(bytes([0xC2, 0]), data)
        self.assertEqual({note.midi for note in score.notes}, {48, 72})

    def test_reverb_is_written_as_a_cc91_send(self) -> None:
        project = two_track_project()
        project.reverb = 0.5

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wet.mid"
            export_midi(project, path)
            data = path.read_bytes()

        self.assertIn(bytes([0xB1, 91, 64]), data)

    def test_mute_and_solo_together_keep_only_the_solo_track(self) -> None:
        project = two_track_project()
        project.tracks[0].mute = True
        project.tracks[1].solo = True

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "both.mid"
            export_midi(project, path)
            score = parse_score(path)

        self.assertEqual({note.midi for note in score.notes}, {48})


if __name__ == "__main__":
    unittest.main()
