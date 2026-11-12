"""SerialService dispatch: CAL frames vs status lines vs notices."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.serial_service import SerialService


class FakeSerial:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.flush_count = 0
        self.fail = False

    def write(self, data: bytes) -> int:
        if self.fail:
            raise OSError("port closed")
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        self.flush_count += 1


class SerialWriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_send_line_is_refused_until_connected(self) -> None:
        service = SerialService()
        self.assertFalse(service.send_line("c"))

        fake = FakeSerial()
        service._serial = fake
        service._set_state(True, "COM5")
        self.assertTrue(service.send_line("c"))
        self.assertEqual(fake.writes, [b"c\n"])
        self.assertEqual(fake.flush_count, 1)

        service._set_state(False, "unplugged")
        self.assertFalse(service.send_line("Q"))
        self.assertEqual(fake.writes, [b"c\n"])

    def test_write_failure_is_reported_not_raised(self) -> None:
        service = SerialService()
        fake = FakeSerial()
        fake.fail = True
        service._serial = fake
        service._set_state(True, "COM5")
        self.assertFalse(service.send_line("T 1 12 6"))

    def test_trailing_newline_is_not_doubled(self) -> None:
        service = SerialService()
        fake = FakeSerial()
        service._serial = fake
        service._set_state(True, "COM5")
        self.assertTrue(service.send_line("T 1 12 6\r\n"))
        self.assertEqual(fake.writes, [b"T 1 12 6\n"])


class SerialCalibrationDispatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.service = SerialService()
        self.frames: list = []
        self.calibration: list = []
        self.notices: list[str] = []
        self.service.frameReady.connect(self.frames.append)
        self.service.calibrationFrame.connect(self.calibration.append)
        self.service.notice.connect(self.notices.append)

    def test_calibration_line_emits_calibration_frame_only(self) -> None:
        payload = " ".join(str(value) for value in range(1, 33))

        self.service.dispatch_line(f"CAL 500 {payload}")

        self.assertEqual(len(self.calibration), 1)
        self.assertEqual(self.calibration[0].dev_ms, 500)
        self.assertEqual(self.calibration[0].values[32], 32)
        self.assertEqual(self.frames, [])
        self.assertEqual(self.notices, [])

    def test_status_line_still_emits_a_normal_frame(self) -> None:
        line = "[  10972 ms]  0x5A OK  0x5C OK  0x5D OK   keys: 12"

        self.service.dispatch_line(line)

        self.assertEqual(len(self.frames), 1)
        self.assertEqual(self.calibration, [])
        self.assertEqual(self.notices, [])

    def test_malformed_calibration_line_is_a_notice(self) -> None:
        self.service.dispatch_line("CAL 500 1 2 3")

        self.assertEqual(self.frames, [])
        self.assertEqual(self.calibration, [])
        self.assertEqual(self.notices, ["CAL 500 1 2 3"])


if __name__ == "__main__":
    unittest.main()
