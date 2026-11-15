"""Performance-page transport controls (B1)."""

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

from app.core.synth_service import (
    CLICK_ACCENT_MIDI,
    CLICK_CHANNEL,
    NullSynth,
)
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class RecordingSynth(NullSynth):
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def note_on(self, midi, velocity, channel=None) -> None:
        self.events.append(("on", channel, midi))

    def note_off(self, midi, channel=None) -> None:
        self.events.append(("off", channel, midi))


class PerformTransportUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            projects_root=root / "projects",
            accessibility_path=root / "accessibility.json",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(150)
        self.perform = self.window.perform

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.window.instrument._timer.stop()
        self.tmp.cleanup()

    def test_speed_buttons_step_and_clamp(self) -> None:
        self.assertEqual(self.perform.speed_value.text(), "100%")
        self.perform.speed_plus.click()
        self.assertAlmostEqual(self.window.follow.speed, 1.1)
        self.assertEqual(self.perform.speed_value.text(), "110%")

        for _ in range(5):
            self.perform.speed_plus.click()
        self.assertEqual(self.window.follow.speed, 1.2)
        self.assertEqual(self.perform.speed_value.text(), "120%")

    def test_loop_ab_buttons_create_and_enable_a_range(self) -> None:
        self.perform.loop_a_button.click()
        self.perform.loop_b_button.click()

        follow = self.window.follow
        self.assertTrue(follow.loop_enabled)
        self.assertTrue(follow.loop_end > follow.loop_start)
        self.assertIn("循环", self.perform.loop_label.text())
        self.assertTrue(self.perform.loop_switch.isChecked())

        self.perform.loop_switch.setChecked(False)
        self.assertFalse(follow.loop_enabled)

    def test_click_and_count_in_switches_drive_the_session(self) -> None:
        self.perform.metronome_switch.setChecked(True)
        self.assertTrue(self.window.follow.metronome_enabled)

        self.perform.count_in_switch.setChecked(True)
        self.assertTrue(self.window.follow.count_in_enabled)

    def test_beat_signal_plays_the_woodblock_click(self) -> None:
        synth = RecordingSynth()
        self.window.instrument.synth = synth

        self.window._play_click(True)
        self.assertIn(("on", CLICK_CHANNEL, CLICK_ACCENT_MIDI), synth.events)

        wait(100)  # the 70 ms note-off timer fires
        self.assertIn(("off", CLICK_CHANNEL, CLICK_ACCENT_MIDI), synth.events)


if __name__ == "__main__":
    unittest.main()
