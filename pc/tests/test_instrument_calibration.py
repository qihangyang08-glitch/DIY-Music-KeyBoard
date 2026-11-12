"""Instrument calibration mode: no sound, no judgement, locked controls."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.instrument import Instrument
from app.core.note_engine import Frame
from app.core.synth_service import NullSynth

MODULES = {0x5A: True, 0x5C: True, 0x5D: True}


class InstrumentCalibrationModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.events: list = []
        self.active: list[set[int]] = []
        self.instrument.events.connect(lambda items: self.events.extend(items))
        self.instrument.activeChanged.connect(
            lambda keys: self.active.append(set(keys))
        )

    def frame(self, active: set[int]) -> Frame:
        return Frame(t=1.0, active=active, modules=MODULES)

    def test_normal_mode_still_emits_note_events(self) -> None:
        # Channels 1..12 are module order, not layout order: channel 12 is
        # layout key 1 on the reversed first module.
        self.instrument.set_hardware_frame(self.frame({12}))
        self.instrument._tick()

        self.assertTrue(any(event.kind == "on" for event in self.events))
        self.assertIn({1}, self.active)

    def test_calibration_swallows_notes_but_tracks_pressed_keys(self) -> None:
        self.instrument.begin_calibration()
        self.assertTrue(self.instrument.calibration_active)
        self.assertTrue(self.instrument.mapping_locked)

        self.instrument.set_hardware_frame(self.frame({12, 11}))
        self.instrument._tick()

        self.assertEqual(self.events, [])
        self.assertIn({1, 2}, self.active)

    def test_controls_are_locked_until_calibration_ends(self) -> None:
        inst = self.instrument
        inst.set_preset(1)
        inst.set_octave(1)
        inst.set_program(2)
        inst.toggle_mute()
        saved = (
            inst.preset_index,
            inst.octave,
            inst.transpose,
            inst.program_index,
            inst.muted,
            inst.auto_follow,
            inst.mapping_locked,
        )

        inst.begin_calibration()
        inst.set_preset(4)
        inst.set_octave(-1)
        inst.set_transpose(5)
        inst.set_program(0)
        inst.toggle_mute()
        inst.toggle_auto_follow()

        self.assertEqual(
            (
                inst.preset_index,
                inst.octave,
                inst.transpose,
                inst.program_index,
                inst.muted,
                inst.auto_follow,
            ),
            saved[:6],
        )

        inst.end_calibration()
        self.assertFalse(inst.calibration_active)
        self.assertEqual(
            (
                inst.preset_index,
                inst.octave,
                inst.transpose,
                inst.program_index,
                inst.muted,
                inst.auto_follow,
                inst.mapping_locked,
            ),
            saved,
        )

    def test_computer_keyboard_and_pads_are_ignored(self) -> None:
        inst = self.instrument
        inst.begin_calibration()
        inst.press_keyboard(8)
        inst.press_pad(1)
        inst._tick()

        self.assertEqual(inst.kbd_keys, set())
        self.assertFalse(inst.sustain)
        self.assertEqual(self.events, [])

    def test_end_calibration_is_idempotent(self) -> None:
        self.instrument.end_calibration()
        self.assertFalse(self.instrument.calibration_active)


if __name__ == "__main__":
    unittest.main()
