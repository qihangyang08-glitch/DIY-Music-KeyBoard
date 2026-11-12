"""Headless test for the parsed-score staff view (H7a).

The staff is drawn by ScoreCanvas; this test loads a real bundled score,
switches to 谱面, and forces a paint so a missing layout or painter error
cannot hide behind the 落键 tab default.
"""

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

from app.core.score import Score, ScoreNote
from app.ui.main_window import MainWindow


def long_score(measures: int = 40) -> Score:
    notes = [
        ScoreNote(
            72 + index % 5,
            float(index * 2),
            1.0,
            index + 1,
            1.0,
        )
        for index in range(measures)
    ]
    return Score(
        title="长谱",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=measures * 2.0,
        source="test",
        format="test",
        measure_count=measures,
    )


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class ScoreSheetWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=self.root / "learning.json",
            bindings_path=self.root / "keybindings.json",
            prefs_path=self.root / "score_prefs.json",
            library_root=self.root / "scores",
            projects_root=self.root / "projects",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def test_sheet_tab_renders_a_parsed_score(self) -> None:
        path = ROOT / "resources" / "scores" / "ode_to_joy.musicxml"
        self.assertTrue(self.window._load_score_file(str(path)))
        self.window._show_page(0)
        wait(100)

        view = self.window.perform.score
        self.assertTrue(view.has_score)
        view._tab_buttons["sheet"].click()
        wait(60)

        canvas = view.canvas
        self.assertEqual(canvas._mode, "sheet")
        self.assertIsNotNone(canvas._layout)
        self.assertGreater(len(canvas._layout.systems), 0)
        self.assertGreater(len(canvas._layout.notes), 0)

        # Force a real paint: a layout/painter regression must fail the test.
        pixmap = canvas.grab()
        self.assertFalse(pixmap.isNull())

    def test_playhead_state_is_ready_for_the_sheet(self) -> None:
        path = ROOT / "resources" / "scores" / "ode_to_joy.musicxml"
        self.assertTrue(self.window._load_score_file(str(path)))
        self.window._show_page(0)
        wait(100)

        view = self.window.perform.score
        view._tab_buttons["sheet"].click()
        wait(40)
        canvas = view.canvas

        canvas.set_follow_state(2.0, 1, 0, 0, True, None)
        system, x = canvas._layout.playhead(2.0)

        self.assertGreaterEqual(system, 0)
        self.assertGreaterEqual(x, 0.0)
        self.assertLessEqual(x, 1.0)
        self.assertFalse(canvas.grab().isNull())

    def test_long_score_is_paged_two_systems_at_a_time(self) -> None:
        view = self.window.perform.score
        view.set_score(long_score(40))
        view._tab_buttons["sheet"].click()
        wait(40)
        canvas = view.canvas

        self.assertEqual(len(canvas._layout.systems), 5)
        self.assertEqual(canvas.page_count, 3)
        self.assertEqual(canvas.page, 0)
        self.assertEqual(view._page_label.text(), "1/3")

        view._page_next.click()
        self.assertEqual(canvas.page, 1)
        self.assertEqual(view._page_label.text(), "2/3")

        view._page_prev.click()
        self.assertEqual(canvas.page, 0)
        self.assertFalse(canvas.grab().isNull())

    def test_short_score_has_one_page_and_hidden_controls(self) -> None:
        view = self.window.perform.score
        view.set_score(long_score(8))
        view._tab_buttons["sheet"].click()
        wait(40)

        self.assertEqual(view.canvas.page_count, 1)
        self.assertFalse(view._page_prev.isVisible())
        self.assertFalse(view._page_next.isVisible())

    def test_follow_playhead_flips_to_its_page(self) -> None:
        view = self.window.perform.score
        view.set_score(long_score(40))
        view._tab_buttons["sheet"].click()
        wait(40)
        canvas = view.canvas
        position = 30 * 2.0  # measure 31

        system, _ = canvas._layout.playhead(position)
        canvas.set_follow_state(position, 0, 0, 0, True, None)

        self.assertEqual(canvas.page, system // 2)
        self.assertEqual(view._page_label.text(), f"{canvas.page + 1}/3")


if __name__ == "__main__":
    unittest.main()
