"""Calibration page: detection flow, threshold picking, apply/save, leave."""

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

from app.core.calibration import (
    CalibrationFrame,
    CalibrationProfile,
    KeyThreshold,
    load_keymap,
)
from app.core.instrument import Instrument
from app.core.synth_service import NullSynth
from app.ui.calibration_page import CalibrationPage
from app.ui.main_window import MainWindow
from app.ui.theme import THEMES


def full_profile_keys() -> list[KeyThreshold]:
    keys: list[KeyThreshold] = []
    for channel, info in sorted(load_keymap().items()):
        keys.append(
            KeyThreshold(
                key=int(info["key"]),
                touch=12,
                release=6,
                noise=2,
                peak=40,
                hold=36,
                channel=channel,
                note=str(info.get("note", "")),
                module=str(info.get("address", "")),
                electrode=int(info.get("electrode", -1)),
            )
        )
    return keys


class CalibrationPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.clock_value = 100.0
        self.sent: list[str] = []
        self.send_ok = True
        self.messages: list[str] = []

        def send(text: str) -> bool:
            self.sent.append(text)
            return self.send_ok

        self.page = CalibrationPage(
            THEMES["studio"],
            self.instrument,
            send,
            profile_path=self.root / "calibration.json",
            clock=lambda: self.clock_value,
            ready=lambda: True,
        )
        self.page.message.connect(self.messages.append)
        self.page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.page.resize(900, 700)
        self.page.show()
        self.page.enter()

    def tearDown(self) -> None:
        self.page.leave()
        self.page.close()
        self.instrument._timer.stop()
        self.tmp.cleanup()

    def frame(self, t: float, values: dict[int, int] | None = None) -> CalibrationFrame:
        payload = {channel: 0 for channel in range(1, 33)}
        payload.update(values or {})
        return CalibrationFrame(t=t, values=payload)

    def reach_stopped_with_one_key(self) -> None:
        self.clock_value = 100.0
        self.assertTrue(self.page.start_detection())
        self.page.feed_frame(self.frame(100.0, {12: 2}))
        self.clock_value = 101.6
        self.page.feed_frame(self.frame(101.6, {12: 2}))
        self.assertEqual(self.page.session.state, "monitoring")

        self.clock_value = 102.0
        self.page.feed_frame(self.frame(102.0, {12: 78}))
        self.clock_value = 102.04
        self.page.feed_frame(self.frame(102.04, {12: 78}))
        self.assertIn(1, self.page.session.curves)

        self.clock_value = 102.2
        self.page.feed_frame(self.frame(102.2, {12: 0}))
        self.clock_value = 102.8
        self.page.feed_frame(self.frame(102.8, {12: 0}))
        self.assertEqual(self.page.session.state, "stopped")
        self.assertTrue(self.page.session.auto_stopped)

    # -- detection --------------------------------------------------------

    def test_start_sends_c_and_enters_baseline(self) -> None:
        self.assertTrue(self.page.start_detection())
        self.assertEqual(self.sent, ["c"])
        self.assertEqual(self.page.session.state, "baseline")
        self.assertTrue(self.page.stop_button.isEnabled())

    def test_not_ready_refuses_to_start_without_sending(self) -> None:
        page = CalibrationPage(
            THEMES["studio"],
            self.instrument,
            lambda text: self.sent.append(text) or True,
            profile_path=self.root / "other.json",
            clock=lambda: self.clock_value,
            ready=lambda: False,
        )
        page.message.connect(self.messages.append)
        self.assertFalse(page.start_detection())
        self.assertEqual(self.sent, [])
        self.assertFalse(page.start_button.isEnabled())
        page.close()

    def test_detection_builds_a_card_and_auto_stops(self) -> None:
        self.reach_stopped_with_one_key()

        self.assertIn(1, self.page._cards)
        self.assertFalse(self.page.stream_on)
        self.assertEqual(self.sent, ["c", "c"])
        self.assertTrue(self.page.apply_button.isEnabled())
        self.assertTrue(self.page.save_button.isEnabled())
        # The stop-time suggestion replaces the provisional threshold.
        self.assertEqual(self.page.threshold_for(1), self.page.session.suggest(1))

    def test_frames_are_ignored_outside_a_visit(self) -> None:
        self.page.leave()
        self.page.feed_frame(self.frame(100.0, {12: 78}))
        self.assertEqual(self.page.session.curves, {})

    # -- threshold picking ------------------------------------------------

    def test_curve_widget_maps_y_to_signal_value(self) -> None:
        self.reach_stopped_with_one_key()
        widget = self.page._cards[1].curve_widget
        rect = widget._plot_rect()
        self.assertEqual(widget.value_at_y(rect.bottom()), 1)
        self.assertEqual(widget.value_at_y(rect.top()), 255)
        middle = widget.value_at_y((rect.top() + rect.bottom()) / 2)
        self.assertTrue(120 <= middle <= 135)

    def test_manual_threshold_is_used_by_apply(self) -> None:
        self.reach_stopped_with_one_key()
        self.page.set_threshold(1, 48)

        self.assertTrue(self.page.apply_to_device())
        self.assertEqual(self.sent[-1].split()[0], "T")
        self.assertEqual(self.sent[-1], "T 12 48 29")
        self.assertFalse(self.page.applied)

        self.assertTrue(self.page.handle_reply("OK T"))
        self.assertTrue(self.page.applied)
        self.assertIn("阈值已应用到设备", self.messages)

    def test_invalid_threshold_blocks_apply(self) -> None:
        self.reach_stopped_with_one_key()
        self.page.set_threshold(1, 5)  # too close to the noise floor
        self.assertFalse(self.page.apply_to_device())
        self.assertEqual(self.sent, ["c", "c"])
        self.assertTrue(any("噪声" in message for message in self.messages))

    def test_error_reply_is_reported(self) -> None:
        self.reach_stopped_with_one_key()
        self.assertTrue(self.page.handle_reply("ERR T 12"))
        self.assertFalse(self.page.applied)
        self.assertTrue(any("12" in message for message in self.messages))

    # -- save / leave -----------------------------------------------------

    def test_save_requires_32_keys_or_a_complete_base(self) -> None:
        self.reach_stopped_with_one_key()
        self.page.set_threshold(1, 48)
        self.assertFalse(self.page.save_profile())

        self.page.profile = CalibrationProfile(
            name="旧方案",
            gain=4,
            keys=full_profile_keys(),
            created_at="2026-11-12T20:15:00",
        )
        self.assertTrue(self.page.save_profile())
        loaded, warning = CalibrationProfile.load(self.root / "calibration.json")
        self.assertEqual(warning, "")
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.is_complete())
        key1 = next(item for item in loaded.keys if item.key == 1)
        self.assertEqual(key1.touch, 48)

    def test_leave_stops_stream_and_restores_performance(self) -> None:
        self.assertTrue(self.page.start_detection())
        self.assertTrue(self.instrument.calibration_active)
        self.page.leave()

        self.assertFalse(self.instrument.calibration_active)
        self.assertFalse(self.page.active)
        self.assertEqual(self.sent, ["c", "c"])

    def test_disconnect_freezes_the_session_without_sending_c(self) -> None:
        self.clock_value = 100.0
        self.page.start_detection()
        self.page.feed_frame(self.frame(100.0, {12: 2}))
        self.clock_value = 101.6
        self.page.feed_frame(self.frame(101.6, {12: 2}))
        self.sent.clear()

        self.instrument.set_connection(False, "unplugged")
        self.page.device_disconnected()

        self.assertEqual(self.page.session.state, "stopped")
        self.assertFalse(self.page.stream_on)
        self.assertEqual(self.sent, [])  # the port is gone; do not queue c
        self.assertIn("断开", self.page.status_label.text())

    def test_apply_then_verify_marks_pass_margin_and_fail(self) -> None:
        self.reach_stopped_with_one_key()
        self.page.set_threshold(1, 48)
        self.assertTrue(self.page.apply_to_device())
        self.assertTrue(self.page.handle_reply("OK T"))
        self.assertTrue(self.page.verify_button.isEnabled())

        self.sent.clear()
        self.page.toggle_verification()
        self.assertEqual(self.sent, ["c"])
        self.assertTrue(self.page.verifying)
        self.assertTrue(self.page.verify_strip.isVisible())

        self.page.feed_frame(self.frame(110.0, {12: 70}))
        self.assertEqual(self.page.verify_strip.state_for(1), "pass")
        self.page.feed_frame(self.frame(110.04, {12: 50}))
        self.assertEqual(self.page.verify_strip.state_for(1), "margin")
        self.page.feed_frame(self.frame(110.08, {12: 40}))
        self.assertEqual(self.page.verify_strip.state_for(1), "fail")
        self.assertIn("通过", self.page.status_label.text())

        self.sent.clear()
        self.page.toggle_verification()
        self.assertEqual(self.sent, ["c"])
        self.assertFalse(self.page.verifying)
        self.assertFalse(self.page.verify_strip.isVisible())

    def test_cal_stream_reply_can_recover_a_stale_stream(self) -> None:
        self.assertTrue(self.page.start_detection())
        self.sent.clear()
        # The firmware says OFF: it was left on by a previous session. One
        # retry turns it back on rather than waiting for frames forever.
        self.assertTrue(self.page.handle_reply("CAL OFF"))
        self.assertEqual(self.sent, ["c"])
        self.assertTrue(self.page.stream_on)


class CalibrationWindowTest(unittest.TestCase):
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
            accessibility_path=root / "accessibility.json",
            calibration_path=root / "calibration.json",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        QTest.qWait(120)
        QApplication.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        QTest.qWait(60)
        self.tmp.cleanup()

    def test_device_button_opens_calibration_and_leaving_restores(self) -> None:
        self.window.device_page.calibration_button.click()
        QApplication.processEvents()

        self.assertIs(self.window.stack.currentWidget(), self.window.calibration_page)
        self.assertTrue(self.window.instrument.calibration_active)
        self.assertTrue(self.window.calibration_page.active)
        # With no serial, the page must not claim it can start.
        self.assertFalse(self.window.calibration_page.start_button.isEnabled())
        self.assertFalse(self.window._send_serial_line("c"))

        self.window._show_page(0)
        QApplication.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.perform)
        self.assertFalse(self.window.instrument.calibration_active)
        self.assertFalse(self.window.calibration_page.active)

    def test_saved_profile_is_sent_on_connect_and_reconnect(self) -> None:
        CalibrationProfile(
            name="保存方案", gain=4, keys=full_profile_keys()
        ).save(self.window.calibration_path)
        sent: list[str] = []
        self.window._send_serial_line = (
            lambda text: sent.append(text) or True
        )

        self.window._on_connection(True, "COM5")
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].startswith("T "))
        self.assertEqual(len(sent[0].split()), 97)  # T + 32 triples
        self.window._on_calibration_reply("OK T")
        self.window.calibration_page.handle_reply("OK T")
        self.assertTrue(self.window.calibration_applied)

        # An already-applied plan can be verified without re-applying.
        self.window.device_page.calibration_button.click()
        QApplication.processEvents()
        self.assertEqual(
            len(self.window.calibration_page.applied_values), 32
        )
        self.assertTrue(self.window.calibration_page.verify_button.isEnabled())
        self.window._show_page(0)
        QApplication.processEvents()

        # The firmware's RAM is lost on a power cycle; reconnect resends.
        self.window._on_connection(True, "COM5")
        self.assertEqual(len(sent), 2)

    def test_auto_apply_timeout_marks_not_applied(self) -> None:
        CalibrationProfile(
            name="超时方案", gain=4, keys=full_profile_keys()
        ).save(self.window.calibration_path)
        self.window._send_serial_line = lambda text: True

        self.window._on_connection(True, "COM5")
        self.assertTrue(self.window._calibration_apply_pending)
        self.window._on_calibration_timeout()

        self.assertFalse(self.window._calibration_apply_pending)
        self.assertFalse(self.window.calibration_applied)

    def test_corrupt_profile_is_not_sent_and_warns_once(self) -> None:
        self.window.calibration_path.write_text("{bad json", encoding="utf-8")
        sent: list[str] = []
        self.window._send_serial_line = (
            lambda text: sent.append(text) or True
        )

        self.window._on_connection(True, "COM5")
        self.window._on_connection(True, "COM5")

        self.assertEqual(sent, [])
        self.assertFalse(self.window.calibration_applied)
        self.assertTrue(self.window._calibration_warning_shown)

    def test_no_saved_profile_sends_nothing(self) -> None:
        sent: list[str] = []
        self.window._send_serial_line = (
            lambda text: sent.append(text) or True
        )
        self.window._on_connection(True, "COM5")
        self.assertEqual(sent, [])
        self.assertFalse(self.window.calibration_applied)

    def test_close_while_calibrating_restores_instrument(self) -> None:
        self.window.device_page.calibration_button.click()
        QApplication.processEvents()
        self.assertTrue(self.window.instrument.calibration_active)

        self.window.close()
        QTest.qWait(40)
        self.assertFalse(self.window.instrument.calibration_active)


if __name__ == "__main__":
    unittest.main()
