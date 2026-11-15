"""Firmware handshake, adaptive/NVS/stuck-key guards (C2/C3/C4).

The firmware itself is checked by compiling it; these assertions keep the
serial contract and the PC-side parser in step.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.serial_service import SerialService

FIRMWARE = ROOT.parent / "src" / "main.cpp"
OTA = ROOT.parent / "src" / "ota.cpp"


class ProtocolDispatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_proto_line_emits_the_version_and_nothing_else(self) -> None:
        service = SerialService()
        versions: list[int] = []
        notices: list[str] = []
        service.protocolVersion.connect(versions.append)
        service.notice.connect(notices.append)

        service.dispatch_line("PROTO 2")
        self.assertEqual(versions, [2])
        self.assertEqual(notices, [])

    def test_non_protocol_lines_are_not_mistaken_for_versions(self) -> None:
        service = SerialService()
        versions: list[int] = []
        service.protocolVersion.connect(versions.append)
        service.dispatch_line("PROTO v2")
        service.dispatch_line("PROTO 2 extra")
        service.dispatch_line("[  100 ms]  0x5A OK  0x5C OK  0x5D OK   keys: none")
        self.assertEqual(versions, [])

    def test_stuck_notice_is_forwarded_to_the_ui(self) -> None:
        service = SerialService()
        notices: list[str] = []
        service.notice.connect(notices.append)
        service.dispatch_line("STUCK 7")
        service.dispatch_line("UNSTUCK 7")
        self.assertEqual(notices, ["STUCK 7", "UNSTUCK 7"])


class FirmwareContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = FIRMWARE.read_text(encoding="utf-8")

    def test_protocol_version_and_commands(self) -> None:
        self.assertIn("PROTOCOL_VERSION = 2", self.source)
        self.assertIn('printVersion()', self.source)
        self.assertIn('Serial.printf("PROTO %u\\n"', self.source)
        self.assertIn("case 'V': printVersion();", self.source)
        self.assertIn("case 'A': toggleAdaptive();", self.source)

    def test_nvs_persists_thresholds_gain_and_adaptive(self) -> None:
        for fragment in (
            'prefs.begin("keyborad"',
            "CONFIG_MAGIC",
            'putBytes("touch"',
            'putBytes("release"',
            'putUChar("gain"',
            'putBool("adapt"',
        ):
            self.assertIn(fragment, self.source)
        self.assertIn("saveConfig();\n  resetBaselineReference();\n  Serial.println(F(\"OK T\"))",
                      self.source)

    def test_adaptive_stuck_recovery_and_watchdog_exist(self) -> None:
        for fragment in (
            "adaptiveTick(now)",
            "ADAPT %s",
            "STUCK_MS = 3000",
            "updateStuckKeys",
            "recoverBus",
            "esp_task_wdt_add(NULL)",
            "esp_task_wdt_reset()",
        ):
            self.assertIn(fragment, self.source)

    def test_ota_is_opt_in_and_has_stubs(self) -> None:
        source = OTA.read_text(encoding="utf-8")
        self.assertIn("#ifdef KEYBORAD_ENABLE_OTA", source)
        self.assertIn("ArduinoOTA.begin()", source)
        self.assertIn("void otaSetup() {}", source)
        self.assertIn("KEYBORAD_WIFI_SSID", source)


if __name__ == "__main__":
    unittest.main()
