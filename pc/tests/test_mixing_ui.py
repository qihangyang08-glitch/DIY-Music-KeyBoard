"""Headless UI tests for track mute/solo and the exported mix (H4 slice)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.note_engine import NoteEvent as RuntimeNoteEvent
from app.core.project import Layer, Project
from app.core.score import parse_score
from app.core.synth_service import NullSynth
from app.ui.main_window import MainWindow


class RecordingSynth(NullSynth):
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.programs: list[tuple[int, int]] = []
        self.volumes: list[tuple[int, float]] = []
        self.pans: list[tuple[int, float]] = []
        self.reverbs: list[float] = []

    def program_on(self, channel: int, program: int) -> None:
        self.programs.append((channel, program))

    def set_reverb(self, level: float) -> None:
        self.reverbs.append(level)

    def channel_volume(self, channel: int, volume: float) -> None:
        self.volumes.append((channel, volume))

    def channel_pan(self, channel: int, pan: float) -> None:
        self.pans.append((channel, pan))

    def note_on(self, midi: int, velocity: int, channel=None) -> None:
        self.events.append(("on", channel, midi))

    def note_off(self, midi: int, channel=None) -> None:
        self.events.append(("off", channel, midi))


def runtime_event(kind: str, midi: int, t: float) -> RuntimeNoteEvent:
    return RuntimeNoteEvent(
        t=t, kind=kind, key=1, channel=1, midi=midi, velocity=100, note="M"
    )


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def make_window(root: Path) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        prefs_path=root / "score_prefs.json",
        library_root=root / "scores",
        projects_root=root / "projects",
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(160)
    return window


class MixingWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)
        self.window._show_page(3)
        wait(120)
        self.page = self.window.compose_page
        self.page.add_track()
        self.page.add_track()
        self.page.editor.add_note(0.0, 60, 1.0)
        self.page.select_track(1)
        self.page.editor.add_note(0.0, 48, 1.0)
        self.page.select_track(0)
        wait(30)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def exported_midi(self) -> set[int]:
        self.page.export_button.click()
        wait(30)
        path = self.page.default_path().with_suffix(".mid")
        self.assertTrue(path.is_file())
        return {note.midi for note in parse_score(path).notes}

    def test_mute_button_filters_the_exported_mix(self) -> None:
        self.page.track_rows[0].mute_button.click()
        wait(30)

        self.assertTrue(self.page.session.project.tracks[0].mute)
        self.assertEqual(self.exported_midi(), {48})

    def test_solo_button_keeps_only_the_solo_track(self) -> None:
        self.page.track_rows[1].solo_button.click()
        wait(30)

        self.assertTrue(self.page.session.project.tracks[1].solo)
        self.assertEqual(self.exported_midi(), {48})

    def test_bass_template_loads_two_voices_with_pan(self) -> None:
        self.page.template_buttons[2].click()
        wait(50)

        project = self.page.session.project
        self.assertEqual(project.title, "左手贝斯 + 右手钢琴")
        self.assertEqual([track.program for track in project.tracks], [32, 0])
        self.assertLess(project.tracks[0].pan, 0)
        self.assertGreater(project.tracks[1].pan, 0)
        self.assertEqual(len(self.page.track_rows), 2)
        self.assertEqual(self.page.roll.editor.notes, [])

    def test_template_save_uses_the_default_project_path(self) -> None:
        self.page.template_buttons[0].click()
        wait(50)
        self.page.editor.add_note(0.0, 60, 1.0)
        self.assertTrue(self.page.save_project())

        saved = Project.load(self.page.default_path())
        self.assertEqual(saved.title, "钢琴独奏")
        self.assertEqual([note.midi for note in saved.tracks[0].notes], [60])

    def test_layer_button_adds_a_second_voice_to_the_export(self) -> None:
        row = self.page.track_rows[0]
        row.layer_button.click()
        wait(40)

        self.assertTrue(row.layer_button.isChecked())
        self.assertEqual(
            self.page.session.project.tracks[0].layer,
            Layer(program=48, volume=0.7),
        )

        self.page.export_button.click()
        wait(40)
        path = self.page.default_path().with_suffix(".mid")
        score = parse_score(path)
        self.assertEqual(len(score.notes), 3)
        self.assertIn(bytes([0xC2, 48]), path.read_bytes())

    def test_layer_is_auditioned_on_the_layer_channel(self) -> None:
        synth = RecordingSynth()
        self.page.instrument.synth = synth
        self.page.track_rows[0].layer_button.click()
        wait(40)

        now = 100.0
        self.page.note_event(runtime_event("on", 60, now))
        self.page.note_event(runtime_event("off", 60, now + 0.1))

        self.assertIn((13, 48), synth.programs)
        self.assertIn(("on", 13, 60), synth.events)
        self.assertIn(("off", 13, 60), synth.events)

    def test_split_routes_live_notes_to_left_and_right(self) -> None:
        synth = RecordingSynth()
        self.page.instrument.synth = synth
        row = self.page.track_rows[0]
        row.split_button.click()
        wait(40)

        split = self.page.session.project.tracks[0].split
        self.assertIsNotNone(split)
        self.assertEqual(split.midi, self.page.instrument.midi_for_key(17))
        self.assertEqual(split.left_program, 32)
        self.assertIsNone(self.page.session.project.tracks[0].layer)
        self.assertIn((0, 0.0), synth.volumes)
        self.assertIn((11, 32), synth.programs)
        self.assertIn((12, split.right_program), synth.programs)

        low = split.midi - 12
        high = split.midi + 3
        now = 100.0
        self.page.note_event(runtime_event("on", low, now))
        self.page.note_event(runtime_event("off", low, now + 0.1))
        self.page.note_event(runtime_event("on", high, now + 0.2))
        self.page.note_event(runtime_event("off", high, now + 0.3))

        self.assertIn(("on", 11, low), synth.events)
        self.assertIn(("off", 11, low), synth.events)
        self.assertIn(("on", 12, high), synth.events)
        self.assertIn(("off", 12, high), synth.events)

    def test_split_line_matches_the_split_point(self) -> None:
        self.page.track_rows[0].split_button.click()
        wait(40)

        self.assertIsNotNone(self.page.split_bar)
        self.assertEqual(
            self.page.band.project_split_bar, self.page.split_bar
        )

    def test_split_and_layer_are_mutually_exclusive(self) -> None:
        row = self.page.track_rows[0]
        row.layer_button.click()
        wait(30)
        row.split_button.click()
        wait(30)

        track = self.page.session.project.tracks[0]
        self.assertIsNotNone(track.split)
        self.assertIsNone(track.layer)
        self.assertFalse(row.layer_button.isChecked())

        row.layer_button.click()
        wait(30)
        self.assertIsNotNone(track.layer)
        self.assertIsNone(track.split)
        self.assertFalse(row.split_button.isChecked())

    def test_leaving_restores_the_base_channel_volume(self) -> None:
        synth = RecordingSynth()
        self.page.instrument.synth = synth
        self.page.track_rows[0].split_button.click()
        wait(40)
        self.assertIn((0, 0.0), synth.volumes)

        self.page.finalize()
        self.assertEqual(synth.volumes[-1], (0, 1.0))

    def test_pan_slider_updates_the_track_and_survives_refresh(self) -> None:
        row = self.page.track_rows[0]
        row.pan_slider.setValue(-50)
        wait(30)

        self.assertAlmostEqual(
            self.page.session.project.tracks[0].pan, -0.5, places=2
        )
        self.assertEqual(row.pan_label.text(), "L50")

        self.page.cycle_program(0)
        wait(30)
        row = self.page.track_rows[0]
        self.assertEqual(row.pan_slider.value(), -50)
        self.assertEqual(row.pan_label.text(), "L50")

    def test_mute_and_solo_states_survive_row_refresh(self) -> None:
        self.page.track_rows[0].mute_button.click()
        self.page.track_rows[1].solo_button.click()
        wait(30)
        self.page.select_track(1)
        self.page.cycle_program(1)
        wait(30)

        self.assertTrue(self.page.track_rows[0].mute_button.isChecked())
        self.assertTrue(self.page.track_rows[1].solo_button.isChecked())
        self.assertTrue(self.page.session.project.tracks[0].mute)
        self.assertTrue(self.page.session.project.tracks[1].solo)

    def test_reverb_slider_updates_the_project_and_the_synth(self) -> None:
        synth = RecordingSynth()
        self.page.instrument.synth = synth

        self.page.reverb_slider.setValue(40)
        wait(30)

        self.assertAlmostEqual(self.page.session.project.reverb, 0.4, places=2)
        self.assertEqual(synth.reverbs[-1], 0.4)
        self.assertEqual(self.page.reverb_label.text(), "40%")

    def test_leaving_the_page_resets_the_reverb_send(self) -> None:
        synth = RecordingSynth()
        self.page.instrument.synth = synth
        self.page.reverb_slider.setValue(60)
        wait(30)

        self.page.finalize()

        self.assertEqual(synth.reverbs[-1], 0.0)

    def test_export_marks_the_project_as_exported(self) -> None:
        self.assertFalse(self.page.session.project.exported)

        self.page.export_button.click()
        wait(30)

        self.assertTrue(self.page.session.project.exported)
        self.assertTrue(self.page.default_path().with_suffix(".mid").is_file())


if __name__ == "__main__":
    unittest.main()
