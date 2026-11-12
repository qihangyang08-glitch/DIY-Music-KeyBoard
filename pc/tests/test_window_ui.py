"""UI smoke tests for 自动跟随 phrase windows in MainWindow."""

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

from app.core.mapping import PRESETS
from app.core.score import Score, ScoreNote
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def wide_score() -> Score:
    """Four measures low (C3), four measures high (C#6), no rests."""
    notes = []
    for measure in range(8):
        midi = 48 if measure < 4 else 85
        notes.append(
            ScoreNote(
                midi=midi,
                start=measure * 2.0,
                duration=2.0,
                measure=measure + 1,
                beat=1.0,
            )
        )
    return Score(
        title="wide",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=16.0,
        source="test",
        format="test",
    )


def two_window_score() -> Score:
    """First phrase fits octave 0; the second needs octave +1."""
    notes = []
    for measure in range(8):
        midi = 72 if measure < 4 else 100
        notes.append(
            ScoreNote(
                midi=midi,
                start=measure * 2.0,
                duration=2.0,
                measure=measure + 1,
                beat=1.0,
            )
        )
    return Score(
        title="two windows",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        notes=notes,
        duration=16.0,
        source="test",
        format="test",
    )


class WindowUiTest(unittest.TestCase):
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
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def load_wide(self, auto: bool) -> None:
        if self.window.instrument.auto_follow != auto:
            self.window.instrument.toggle_auto_follow()
        self.window.follow.set_score(wide_score())
        wait(80)

    def test_white_key_preset_disables_the_upper_slots(self) -> None:
        inst = self.window.instrument
        index = next(
            index
            for index, preset in enumerate(PRESETS)
            if preset.key == "white19"
        )
        inst.set_preset(index)
        wait(80)

        self.assertEqual(inst.current_preset.key, "white19")
        self.assertIn("白键 19 键", self.window.map_chip.text())
        self.assertIn("C4–G6", self.window.perform.map_range.text())
        self.assertEqual(inst.note_for_key(19), "G6")
        self.assertEqual(inst.note_for_key(20), "—")
        self.assertFalse(inst.key_enabled(20))
        self.assertTrue(
            self.window.perform._preset_buttons[index].isChecked()
        )

    def test_auto_follow_switches_window_mid_piece(self) -> None:
        self.load_wide(auto=True)
        inst = self.window.instrument
        follow = self.window.follow

        self.assertEqual(len(follow.window_plan.segments), 2)
        self.assertEqual(inst.octave, -2)
        self.assertIn("1/2 段", self.window.perform.map_range.text())

        first_bar = inst.bar_for_midi(48)
        self.assertIsNotNone(first_bar)
        for _ in range(4):
            follow.note_on(first_bar)

        self.assertEqual(inst.octave, 0)
        self.assertIn("2/2 段", self.window.perform.map_range.text())
        self.assertIsNotNone(inst.bar_for_midi(85))
        self.assertEqual(follow.hits, 4)

    def test_manual_octave_survives_within_a_phrase(self) -> None:
        self.load_wide(auto=True)
        inst = self.window.instrument
        start = inst.octave
        inst.set_octave(+1)
        wait(30)
        self.assertEqual(inst.octave, start + 1)

    def test_auto_follow_off_keeps_the_users_octave(self) -> None:
        self.load_wide(auto=False)
        inst = self.window.instrument
        self.assertEqual(inst.octave, 0)
        self.assertNotIn("段", self.window.perform.map_range.text())

    def test_turning_follow_off_clears_window_info(self) -> None:
        self.load_wide(auto=True)
        self.assertIn("段", self.window.perform.map_range.text())
        self.window.instrument.toggle_auto_follow()
        wait(30)
        self.assertNotIn("段", self.window.perform.map_range.text())

    def test_turning_follow_off_restores_the_users_octave(self) -> None:
        inst = self.window.instrument
        inst.set_octave(+1)
        user_octave = inst.octave
        inst.toggle_auto_follow()
        self.window.follow.set_score(wide_score())
        wait(60)
        self.assertEqual(inst.octave, -2)
        inst.toggle_auto_follow()
        wait(30)
        self.assertEqual(inst.octave, user_octave)

    def test_split_preset_is_selectable_and_marks_the_boundary(self) -> None:
        inst = self.window.instrument
        index = next(
            i for i, preset in enumerate(PRESETS) if preset.key == "split"
        )
        inst.set_preset(index)
        wait(40)

        self.assertEqual(inst.current_preset.key, "split")
        self.assertIn("C3–D#4 + C5–D#6", self.window.perform.map_range.text())
        self.assertEqual(self.window.perform.band.split_boundary_bar(), 16)

    def test_auto_follow_split_shows_both_registers(self) -> None:
        inst = self.window.instrument
        index = next(
            i for i, preset in enumerate(PRESETS) if preset.key == "split"
        )
        inst.set_preset(index)
        if not inst.auto_follow:
            inst.toggle_auto_follow()
        self.window.follow.set_score(wide_score())
        wait(80)

        self.assertIn(
            "C3–D#4 + C5–D#6", self.window.perform.map_range.text()
        )
        self.assertIn("C3–D#4 + C5–D#6", self.window.map_chip.text())

    def test_header_chip_updates_on_new_score_with_same_first_octave(self) -> None:
        inst = self.window.instrument
        if not inst.auto_follow:
            inst.toggle_auto_follow()
        wait(40)
        self.assertNotIn("段", self.window.map_chip.text())
        self.window.follow.set_score(two_window_score())
        wait(60)
        self.assertIn("1/2 段", self.window.perform.map_range.text())
        self.assertIn("1/2 段", self.window.map_chip.text())


if __name__ == "__main__":
    unittest.main()
