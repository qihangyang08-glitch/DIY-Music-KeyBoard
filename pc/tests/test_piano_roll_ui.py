"""Headless UI tests for piano-roll editing (H3).

Edits go through the real canvas, so hit-testing, drag gestures, and the
creation-page wiring are exercised together. Nothing here should sound a note:
auditioning stays on the 32-key band.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.piano_roll import HEADER_H, HEIGHT, ROW_H


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


class PianoRollWindowTest(unittest.TestCase):
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
        wait(40)
        self.roll = self.page.roll

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def click_note(self, beat: float, midi: int) -> None:
        pos = QPoint(
            int(self.roll.x_for_beat(beat)) + 2,
            int(self.roll.y_for_midi(midi)) + 2,
        )
        QTest.mouseClick(
            self.roll,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            pos,
        )
        wait(30)

    def test_click_draws_a_note_without_sound(self) -> None:
        self.click_note(0.5, 60)

        notes = self.page.session.project.tracks[0].notes
        self.assertEqual(len(notes), 1)
        self.assertEqual((notes[0].start, notes[0].midi), (0.5, 60))
        self.assertEqual(self.window.instrument.active_notes(), [])

    def test_right_click_erases_a_note(self) -> None:
        self.click_note(0.5, 60)
        rect = self.roll.note_rect(0)

        QTest.mouseClick(
            self.roll,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            rect.center().toPoint(),
        )
        wait(30)

        self.assertEqual(self.page.session.project.tracks[0].notes, [])

    def test_drag_moves_the_note_in_time_and_pitch(self) -> None:
        self.click_note(0.5, 60)
        rect = self.roll.note_rect(0)
        start = rect.center().toPoint()
        end = QPoint(
            start.x() + int(2 * self.roll.pixels_per_beat),
            start.y() - 2 * ROW_H,
        )

        QTest.mousePress(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, start,
        )
        QTest.mouseMove(self.roll, end)
        wait(20)
        QTest.mouseRelease(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, end,
        )
        wait(30)

        notes = self.page.session.project.tracks[0].notes
        self.assertEqual(len(notes), 1)
        self.assertEqual((notes[0].start, notes[0].midi), (2.5, 62))

    def test_ctrl_drag_copies_instead_of_moving(self) -> None:
        self.click_note(0.5, 60)
        rect = self.roll.note_rect(0)
        start = rect.center().toPoint()
        end = QPoint(start.x() + int(self.roll.pixels_per_beat), start.y())

        QTest.mousePress(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier, start,
        )
        QTest.mouseMove(self.roll, end)
        wait(20)
        QTest.mouseRelease(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier, end,
        )
        wait(30)

        notes = self.page.session.project.tracks[0].notes
        self.assertEqual(
            [(note.start, note.midi) for note in notes],
            [(0.5, 60), (1.5, 60)],
        )

    def test_dragging_the_right_edge_resizes(self) -> None:
        self.click_note(0.5, 60)
        rect = self.roll.note_rect(0)
        start = QPoint(int(rect.right()) - 3, int(rect.center().y()))
        end = QPoint(start.x() + int(self.roll.pixels_per_beat), start.y())

        QTest.mousePress(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, start,
        )
        QTest.mouseMove(self.roll, end)
        wait(20)
        QTest.mouseRelease(
            self.roll, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, end,
        )
        wait(30)

        notes = self.page.session.project.tracks[0].notes
        self.assertEqual(notes[0].duration, 2.0)

    def test_undo_button_restores_the_previous_notes(self) -> None:
        self.click_note(0.5, 60)
        self.assertTrue(self.page.undo_button.isEnabled())

        self.page.undo_button.click()
        wait(30)

        self.assertEqual(self.page.session.project.tracks[0].notes, [])
        self.assertFalse(self.page.undo_button.isEnabled())

    def test_zoom_buttons_change_pixels_per_beat(self) -> None:
        before = self.roll.pixels_per_beat

        self.page.zoom_in_button.click()
        self.assertGreater(self.roll.pixels_per_beat, before)

        self.page.zoom_out_button.click()
        self.assertAlmostEqual(self.roll.pixels_per_beat, before, places=3)

    def test_loop_region_matches_the_project_loop(self) -> None:
        self.page.set_loop(True, bars=1)
        rect = self.roll.loop_rect()

        self.assertIsNotNone(rect)
        self.assertAlmostEqual(
            rect.width(), 4 * self.roll.pixels_per_beat, places=3
        )
        self.assertAlmostEqual(rect.height(), HEIGHT - HEADER_H, places=3)

    def test_track_switch_shows_that_tracks_notes(self) -> None:
        self.click_note(0.5, 60)
        self.page.add_track()
        wait(30)

        self.assertTrue(self.page.select_track(1))
        self.assertEqual(self.roll.editor.notes, [])
        self.click_note(0.5, 72)
        self.assertEqual(len(self.page.session.project.tracks[1].notes), 1)

        self.page.select_track(0)
        self.assertEqual(len(self.page.session.project.tracks[0].notes), 1)
        self.assertEqual(len(self.roll.editor.notes), 1)

    def test_editing_does_not_touch_the_loaded_score(self) -> None:
        hits, misses = self.window.follow.hits, self.window.follow.misses
        self.click_note(0.5, 60)
        self.page.undo_button.click()
        wait(30)

        self.assertEqual(
            (self.window.follow.hits, self.window.follow.misses),
            (hits, misses),
        )


if __name__ == "__main__":
    unittest.main()
