"""Instrument hardware-frame signal throttling (H9b-P2)."""

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


class HardwareFrameSignalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.emits: list[bool] = []
        self.instrument.stateChanged.connect(lambda: self.emits.append(True))

    def frame(self, t: float, active: set[int]) -> Frame:
        return Frame(t=t, active=active, modules={0x5A: True, 0x5C: True})

    def test_unchanged_frames_do_not_emit_state_changed(self) -> None:
        self.instrument.set_hardware_frame(self.frame(0.0, {1}))
        self.assertEqual(len(self.emits), 1)

        # 50 Hz serial frames with the same touch mask are common while a
        # key is held; repainting the whole window for each one is wasted.
        for index in range(1, 6):
            self.instrument.set_hardware_frame(
                self.frame(float(index), {1})
            )
        self.assertEqual(len(self.emits), 1)
        self.assertIsNotNone(self.instrument.last_frame_t)

    def test_changed_keys_or_modules_emit_once(self) -> None:
        self.instrument.set_hardware_frame(self.frame(0.0, {1}))
        self.emits.clear()

        self.instrument.set_hardware_frame(self.frame(1.0, {1, 2}))
        self.assertEqual(len(self.emits), 1)

        changed_modules = Frame(
            t=2.0, active={1, 2}, modules={0x5A: True, 0x5C: False}
        )
        self.instrument.set_hardware_frame(changed_modules)
        self.assertEqual(len(self.emits), 2)

    def test_disconnect_followed_by_same_frame_emits_again(self) -> None:
        frame = self.frame(0.0, {1})
        self.instrument.set_hardware_frame(frame)
        self.instrument.set_connection(False, "waiting")
        self.emits.clear()

        # Reconnecting with the same touch mask is a real state change.
        self.instrument.set_hardware_frame(frame)
        self.assertEqual(len(self.emits), 1)


if __name__ == "__main__":
    unittest.main()
