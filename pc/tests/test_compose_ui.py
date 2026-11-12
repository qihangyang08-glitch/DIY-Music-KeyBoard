"""Headless UI tests for the 创作 page and its MainWindow wiring.

These drive the real MainWindow with WA_DontShowOnScreen (the same mode as the
dev screenshots). Timings use explicit timestamps where the take clock matters;
keyboard tests insert at least three 20 ms engine ticks between press/release.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.note_engine import NoteEvent as RuntimeNoteEvent
from app.core.project import LoopRegion, NoteEvent, Project
from app.core.score import parse_score
from app.core.synth_service import CLICK_CHANNEL, NullSynth
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def make_window(root: Path, projects_root: Path | None = None) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        prefs_path=root / "score_prefs.json",
        library_root=root / "scores",
        projects_root=projects_root if projects_root is not None else root / "projects",
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(160)
    return window


class RecordingSynth(NullSynth):
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def note_on(self, midi: int, velocity: int, channel=None) -> None:
        self.events.append(("on", channel, midi))

    def note_off(self, midi: int, channel=None) -> None:
        self.events.append(("off", channel, midi))


def runtime_event(kind: str, midi: int, t: float, key: int = 1) -> RuntimeNoteEvent:
    return RuntimeNoteEvent(
        t=t,
        kind=kind,
        key=key,
        channel=key,
        midi=midi,
        velocity=100,
        note=f"M{midi}",
    )


class ComposeWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_compose(self):
        self.window._show_page(3)
        wait(120)
        page = self.window.compose_page
        self.assertIs(self.window.stack.currentWidget(), page)
        return page

    def test_nav_index_3_is_the_creation_page(self) -> None:
        self.assertIs(self.window.pages[3], self.window.compose_page)
        self.assertIs(self.window.stack.widget(3), self.window.compose_page)
        self.assertIn("创作", self.window.nav_buttons[3].text())

        self.open_compose()
        QTest.keyClick(
            self.window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier
        )
        wait(80)
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)

        QTest.keyClick(
            self.window, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier
        )
        wait(80)
        self.assertIs(self.window.stack.currentWidget(), self.window.compose_page)


    def test_record_and_stop_transport(self) -> None:
        page = self.open_compose()
        page.record_button.click()
        wait(30)

        self.assertTrue(page.is_recording)
        self.assertFalse(page.record_button.isEnabled())
        self.assertFalse(page.overdub_button.isEnabled())
        self.assertTrue(page.stop_button.isEnabled())

        page.stop_button.click()
        wait(30)
        self.assertFalse(page.is_recording)
        self.assertTrue(page.record_button.isEnabled())

    def test_top_bar_shows_red_dot_and_duration_while_recording(self) -> None:
        page = self.open_compose()
        page.record_button.click()
        wait(180)

        self.assertTrue(self.window.record_dot.isVisible())
        self.assertRegex(self.window.record_dot.text(), r"^● \d{2}:\d{2}$")

        page.stop_button.click()
        wait(30)
        self.assertFalse(self.window.record_dot.isVisible())

    def test_loop_button_toggles_four_bar_loop(self) -> None:
        page = self.open_compose()
        page.loop_button.click()

        self.assertEqual(page.session.project.loop, LoopRegion(0.0, 16.0))
        page.loop_button.click()
        self.assertIsNone(page.session.project.loop)

    def test_keyboard_note_is_recorded_on_creation_page(self) -> None:
        page = self.open_compose()
        page.record_button.click()
        QTest.keyPress(self.window, Qt.Key.Key_Z)
        wait(80)
        QTest.keyRelease(self.window, Qt.Key.Key_Z)
        wait(80)
        page.stop_button.click()
        wait(30)

        self.assertEqual(len(page.session.track.notes), 1)
        self.assertEqual(
            page.session.track.notes[0].midi, self.window.instrument.midi_for_key(1)
        )

    def test_recording_does_not_hit_the_loaded_score(self) -> None:
        page = self.open_compose()
        hits, misses = self.window.follow.hits, self.window.follow.misses
        page.record_button.click()
        QTest.keyPress(self.window, Qt.Key.Key_Z)
        wait(80)
        QTest.keyRelease(self.window, Qt.Key.Key_Z)
        wait(80)
        page.stop_button.click()
        wait(30)

        self.assertEqual((self.window.follow.hits, self.window.follow.misses),
                         (hits, misses))

    def test_loop_overdub_second_take_keeps_both_takes(self) -> None:
        page = self.open_compose()
        page.set_loop(True, bars=1)

        page.start_recording(now=100.0)
        self.window._on_events([runtime_event("on", 60, 100.0)])
        self.window._on_events([runtime_event("off", 60, 100.5)])
        page.stop_recording(now=101.0)

        page.start_recording(overdub=True, now=200.0)
        self.window._on_events([runtime_event("on", 64, 202.5)])
        self.window._on_events([runtime_event("off", 64, 202.75)])
        page.stop_recording(now=203.0)

        self.assertEqual(
            [(note.start, note.midi) for note in page.session.track.notes],
            [(0.0, 60), (1.0, 64)],
        )

    def test_save_then_reopen_keeps_notes(self) -> None:
        page = self.open_compose()
        page.start_recording(now=0.0)
        self.window._on_events([runtime_event("on", 60, 0.0)])
        self.window._on_events([runtime_event("off", 60, 0.5)])
        page.stop_recording(now=1.0)

        self.assertTrue(page.save_project())
        self.assertTrue(page.default_path().is_file())

        self.window.close()
        wait(80)
        second = make_window(self.root)
        try:
            second._show_page(3)
            wait(120)
            notes = second.compose_page.session.track.notes
            self.assertEqual(
                [(note.start, note.midi, note.duration) for note in notes],
                [(0.0, 60, 1.0)],
            )
        finally:
            second.close()
            wait(80)

    def test_load_button_reports_missing_file_and_loads_existing(self) -> None:
        page = self.open_compose()
        page.load_button.click()
        wait(30)
        self.assertIn("还没有可载入", self.window.toast.text())

        project = Project(title="载入")
        project.add_track("钢琴").notes.append(NoteEvent(0.0, 67, 1.0))
        project.save(page.default_path())

        page.load_button.click()
        wait(30)
        self.assertEqual([note.midi for note in page.session.track.notes], [67])

    def test_export_button_writes_a_replayable_midi(self) -> None:
        page = self.open_compose()
        page.add_track()

        page.export_button.click()
        wait(30)
        self.assertIn("还没有可导出的音符", self.window.toast.text())
        self.assertFalse(page.default_path().with_suffix(".mid").exists())

        page.editor.add_note(0.0, 60, 1.0)
        page.export_button.click()
        wait(30)

        path = page.default_path().with_suffix(".mid")
        self.assertTrue(path.is_file())
        notes = parse_score(path).notes
        self.assertEqual([note.midi for note in notes], [60])
        self.assertIn("已导出 MIDI", self.window.toast.text())

    def test_light_bar_slot_click_does_not_play_or_record(self) -> None:
        page = self.open_compose()
        page.start_recording(now=time.monotonic())

        rect = page.band.slot_rect(3)
        self.assertIsNotNone(rect)
        QTest.mouseClick(
            page.band,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            rect.center().toPoint(),
        )
        wait(80)
        page.stop_recording()

        self.assertEqual(page.session.track.notes, [])
        self.assertEqual(self.window.instrument.active_notes(), [])

    def test_add_track_stops_at_eight(self) -> None:
        page = self.open_compose()
        for _ in range(8):
            page.add_track_button.click()

        self.assertEqual(len(page.session.project.tracks), 8)
        self.assertFalse(page.add_track_button.isEnabled())

        page.add_track_button.click()
        self.assertEqual(len(page.session.project.tracks), 8)

    def test_program_and_volume_edit_the_selected_track_only(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.add_track()
        page.select_track(1)
        row = page.track_rows[1]

        row.program_button.click()
        self.assertEqual(page.session.project.tracks[1].program, 4)
        self.assertEqual(
            self.window.instrument.program_index, page.session.program_index()
        )

        row.volume_down.click()
        self.assertEqual(page.session.project.tracks[1].volume, 0.9)
        self.assertEqual(page.session.project.tracks[0].volume, 1.0)

    def test_leaving_creation_page_finalizes_a_take(self) -> None:
        page = self.open_compose()
        page.start_recording()
        t0 = time.monotonic()
        self.window._on_events([runtime_event("on", 60, t0)])

        self.window._show_page(0)
        wait(40)

        self.assertFalse(page.is_recording)
        self.assertEqual(len(page.session.track.notes), 1)
        self.assertFalse(self.window.record_dot.isVisible())

    def test_esc_panics_and_space_controls_project_playback(self) -> None:
        page = self.open_compose()
        page.start_recording(now=time.monotonic())

        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        wait(60)
        self.assertTrue(page.is_recording)
        self.assertIn("全部静音", self.window.toast.text())

        QTest.keyClick(self.window, Qt.Key.Key_Space)
        wait(60)
        self.assertIn("先停止录音", self.window.toast.text())
        self.assertFalse(self.window.follow.playing)
        page.stop_recording()

        page.editor.add_note(0.0, 60, 4.0)
        QTest.keyClick(self.window, Qt.Key.Key_Space)
        wait(150)
        self.assertTrue(page.is_playing)
        self.assertGreater(page.roll.position, 0.0)
        self.assertFalse(self.window.follow.playing)

        QTest.keyClick(self.window, Qt.Key.Key_Space)
        wait(60)
        self.assertFalse(page.is_playing)
        self.assertEqual(page.roll.position, 0.0)

    def test_play_button_moves_the_playhead_and_stops(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.editor.add_note(0.0, 60, 4.0)

        page.play_button.click()
        wait(150)
        self.assertTrue(page.is_playing)
        self.assertGreater(page.roll.position, 0.0)
        self.assertEqual(page.play_button.text(), "⏸ 暂停")

        page.play_button.click()
        wait(40)
        self.assertFalse(page.is_playing)
        self.assertEqual(page.roll.position, 0.0)
        self.assertEqual(page.play_button.text(), "▶ 播放")

    def test_metronome_toggle_starts_and_stops(self) -> None:
        page = self.open_compose()

        page.metronome_button.click()
        self.assertTrue(page.metronome.running)

        page.metronome_button.click()
        self.assertFalse(page.metronome.running)

    def test_metronome_clicks_use_the_click_channel(self) -> None:
        page = self.open_compose()
        synth = RecordingSynth()
        page.instrument.synth = synth

        page.start_metronome(at=100.0)
        page.tick_metronome(100.01)
        page.tick_metronome(100.6)

        self.assertIn(("on", CLICK_CHANNEL, 96), synth.events)
        self.assertIn(("on", CLICK_CHANNEL, 84), synth.events)

        page.stop_metronome()
        self.assertFalse(page.metronome.running)
        self.assertIn(("off", CLICK_CHANNEL, 84), synth.events)

    def test_count_in_ignores_notes_before_the_bar(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.count_in_button.click()
        page.start_recording(now=100.0)

        page.note_event(runtime_event("on", 60, 100.1))
        page.note_event(runtime_event("off", 60, 100.2))
        page.note_event(runtime_event("on", 64, 102.1))
        page.note_event(runtime_event("off", 64, 102.2))
        page.stop_recording(now=102.3)

        self.assertEqual(
            [note.midi for note in page.session.track.notes], [64]
        )

    def test_quantize_button_aligns_the_current_track(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.editor.add_note(0.13, 60, 1.0)
        page.editor.add_note(0.62, 62, 1.0)

        page.quantize_button.click()
        wait(40)

        self.assertEqual(
            [note.start for note in page.session.track.notes], [0.0, 0.5]
        )
        self.assertEqual(page.session.project.quantize_grid, 0.5)
        self.assertIn("已量化", self.window.toast.text())

    def test_count_in_recording_marks_the_practice_flags(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.count_in_button.click()
        page.start_recording(now=100.0)

        page.note_event(runtime_event("on", 60, 102.1))
        page.note_event(runtime_event("off", 60, 102.3))
        page.stop_recording(now=102.4)

        self.assertTrue(page.session.project.count_in_used)
        self.assertTrue(page.session.project.metronome_used)

    def test_play_without_notes_reports_message(self) -> None:
        page = self.open_compose()
        page.play_button.click()
        wait(30)

        self.assertFalse(page.is_playing)
        self.assertIn("还没有可播放", self.window.toast.text())

    def test_starting_recording_stops_playback(self) -> None:
        page = self.open_compose()
        page.add_track()
        page.editor.add_note(0.0, 60, 4.0)
        page.play_button.click()
        wait(80)
        self.assertTrue(page.is_playing)

        page.record_button.click()
        wait(40)

        self.assertFalse(page.is_playing)
        self.assertTrue(page.is_recording)
        page.stop_recording()

    def test_ctrl_tab_shows_labels_on_the_creation_band(self) -> None:
        page = self.open_compose()
        QTest.keyClick(self.window, Qt.Key.Key_Tab)
        wait(40)
        self.assertFalse(page.band.labels_on)  # Tab is focus traversal now

        QTest.keyClick(
            self.window,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.ControlModifier,
        )
        wait(40)
        self.assertTrue(page.band.labels_on)

    def test_theme_switch_repaints_creation_page(self) -> None:
        page = self.open_compose()
        self.window.apply_theme("stage")
        wait(40)

        self.assertEqual(self.window.theme_name, "stage")
        self.assertIs(page._theme, self.window.theme)
        self.assertIs(page.band._theme, self.window.theme)

    def test_layout_at_minimum_size_keeps_transport_and_band_visible(self) -> None:
        page = self.open_compose()
        self.assertTrue(page.record_button.isVisible())
        self.assertTrue(page.add_track_button.isVisible())
        self.assertTrue(page.band.isVisible())
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(), 0)


if __name__ == "__main__":
    unittest.main()
