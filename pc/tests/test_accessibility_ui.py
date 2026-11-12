"""UI wiring for accessibility cues: shape markers and reduced motion."""

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

from app.core.accessibility import AccessibilityPrefs
from app.core.score import ScoreNote
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class AccessibilityUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.accessibility_path = root / "accessibility.json"
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            accessibility_path=self.accessibility_path,
        )
        self.window.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def test_wrong_and_hit_markers_are_shapes(self) -> None:
        band = self.window.perform.band
        band.flash_wrong(3)
        self.assertEqual(band.feedback_marker(3), "×")
        self.assertEqual(band.feedback_marker(2), "")
        band.flash_hit(3)
        self.assertEqual(band.feedback_marker(3), "✓")
        self.assertEqual(band.feedback_marker(2), "")

    def test_judged_signal_uses_non_color_markers_and_text(self) -> None:
        note = ScoreNote(
            midi=72, start=0.0, duration=1.0, measure=1, beat=1.0
        )
        bar = self.window.instrument.bar_for_midi(72)
        self.assertIsNotNone(bar)
        self.window.follow.judged.emit(True, note)
        self.assertEqual(self.window.perform.band.feedback_marker(bar), "✓")
        self.assertIn("命中", self.window.last_label.text())
        self.window.follow.judged.emit(False, note)
        self.assertEqual(self.window.perform.band.feedback_marker(bar), "×")
        self.assertIn("未中", self.window.last_label.text())

    def test_reduce_motion_stops_waves_and_persists(self) -> None:
        effects = self.window.perform.effects
        effects.spawn(3)
        self.assertGreaterEqual(effects.active_columns, 1)
        self.window.settings_page.reduce_motion_switch.setChecked(True)
        self.assertTrue(self.window.accessibility.reduce_motion)
        self.assertTrue(self.window.perform.band.reduce_motion)
        self.assertEqual(effects.active_columns, 0)
        effects.spawn(4)
        self.assertEqual(effects.active_columns, 0)
        self.assertTrue(self.accessibility_path.is_file())
        loaded = AccessibilityPrefs.load(self.accessibility_path)
        self.assertTrue(loaded.reduce_motion)

    def test_saved_preference_applies_on_startup(self) -> None:
        prefs = AccessibilityPrefs(self.accessibility_path)
        prefs.reduce_motion = True
        prefs.save()
        other = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=Path(self.tmp.name) / "learning2.json",
            bindings_path=Path(self.tmp.name) / "keybindings2.json",
            prefs_path=Path(self.tmp.name) / "score_prefs2.json",
            library_root=Path(self.tmp.name) / "scores2",
            accessibility_path=self.accessibility_path,
        )
        try:
            other.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            other.show()
            wait(120)
            self.assertTrue(other.perform.band.reduce_motion)
            self.assertTrue(other.settings_page.reduce_motion_switch.isChecked())
        finally:
            other.close()
            wait(60)


if __name__ == "__main__":
    unittest.main()
