"""Onboarding wizard and the Help entry points on MainWindow."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton

from app.core.calibration import CalibrationProfile, KeyThreshold, load_keymap
from app.core.instrument import Instrument
from app.core.onboarding import OnboardingState
from app.core.synth_service import NullSynth
from app.ui.main_window import MainWindow
from app.ui.onboarding import OnboardingDialog
from app.ui.theme import THEMES


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def full_profile() -> CalibrationProfile:
    keys = [
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
        for channel, info in sorted(load_keymap().items())
    ]
    return CalibrationProfile(
        name="旧方案", gain=4, keys=keys,
        created_at="2026-11-13T00:00:00",
    )


class OnboardingDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calibration_path = self.root / "calibration.json"
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.dialog = OnboardingDialog(
            THEMES["studio"], self.instrument, self.calibration_path
        )
        self.dialog.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.dialog.show()
        wait(50)

    def tearDown(self) -> None:
        self.dialog.close()
        self.instrument._timer.stop()
        self.tmp.cleanup()

    def test_four_step_flow_and_finish(self) -> None:
        self.assertEqual(self.dialog.step_index, 0)
        self.assertEqual(self.dialog.title.text(), "连接与试弹")
        for expected in ("校准（可选）", "页面地图", "第一课"):
            self.dialog.next_step()
            self.assertEqual(self.dialog.title.text(), expected)
        self.assertEqual(self.dialog.next_button.text(), "完成")
        self.dialog.next_step()
        self.assertEqual(self.dialog.outcome, "completed")
        self.assertEqual(self.dialog.result(), int(QDialog.DialogCode.Accepted))

    def test_skip_and_escape_are_skipped(self) -> None:
        self.dialog.skip_button.click()
        self.assertEqual(self.dialog.outcome, "skipped")
        self.assertEqual(self.dialog.result(), int(QDialog.DialogCode.Rejected))

    def test_device_status_updates(self) -> None:
        self.assertIn("电脑键盘", self.dialog.device_label.text())
        self.instrument.set_connection(True, "COM5")
        self.instrument.modules = {
            0x5A: True, 0x5C: True, 0x5D: True
        }
        self.instrument.stateChanged.emit()
        self.assertIn("3 个模块在线", self.dialog.device_label.text())

    def test_calibration_step_shows_saved_plan_and_goes_there(self) -> None:
        full_profile().save(self.calibration_path)
        self.dialog._refresh_calibration()
        self.assertIn("已保存方案", self.dialog.calibration_label.text())

        self.dialog.next_step()
        self.assertEqual(self.dialog.step_index, 1)
        button = next(
            b for b in self.dialog.findChildren(QPushButton)
            if b.text() == "去校准"
        )
        button.click()
        self.assertEqual(self.dialog.outcome, "calibration")

    def test_page_map_lists_all_seven_pages(self) -> None:
        self.dialog.next_step()
        self.dialog.next_step()
        self.assertEqual(self.dialog.step_index, 2)
        text = "\n".join(
            label.text() for label in self.dialog.findChildren(QLabel)
        )
        for page in ("演奏", "学习", "曲库", "创作", "设备", "设置", "帮助"):
            self.assertIn(page, text)

    def test_first_lesson_button_requests_stage_zero(self) -> None:
        for _ in range(3):
            self.dialog.next_step()
        self.assertEqual(self.dialog.step_index, 3)
        button = next(
            b for b in self.dialog.findChildren(QPushButton)
            if b.text() == "打开阶段 0"
        )
        button.click()
        self.assertEqual(self.dialog.outcome, "lesson")


class FakeDialog:
    instances: list["FakeDialog"] = []
    outcome = "skipped"

    def __init__(self, *args, **kwargs) -> None:
        self.outcome = FakeDialog.outcome
        FakeDialog.instances.append(self)

    def exec(self) -> int:
        return 0


class OnboardingWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.onboarding_path = root / "onboarding.json"
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            accessibility_path=root / "accessibility.json",
            calibration_path=root / "calibration.json",
            onboarding_path=self.onboarding_path,
            auto_onboarding=False,
        )
        self.window.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.window.resize(1120, 760)
        self.window.show()
        wait(120)
        FakeDialog.instances = []
        FakeDialog.outcome = "skipped"

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.tmp.cleanup()

    def test_help_is_the_seventh_entry_and_f1_opens_it(self) -> None:
        self.assertEqual(len(self.window.nav_buttons), 7)
        self.assertIn("帮助", self.window.nav_buttons[6].text())

        self.window.nav_buttons[6].click()
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.help_page
        )

        self.window._show_page(0)
        wait(40)
        QTest.keyClick(self.window, Qt.Key.Key_F1)
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.help_page
        )

        self.window._show_page(0)
        wait(40)
        QTest.keyClick(
            self.window, Qt.Key.Key_7, Qt.KeyboardModifier.ControlModifier
        )
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.help_page
        )

    def test_top_and_settings_help_buttons_open_the_page(self) -> None:
        self.window._show_page(0)
        self.window.help_button.click()
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.help_page
        )

        self.window._show_page(0)
        self.window.settings_page.helpRequested.emit()
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.help_page
        )

    def test_help_bottom_opens_calibration_and_keys(self) -> None:
        self.window._show_page(6)
        self.window.help_page.calibrationRequested.emit()
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.calibration_page
        )
        self.assertTrue(self.window.instrument.calibration_active)
        self.window._show_page(0)

        self.window.help_page.keybindingsRequested.emit()
        wait(40)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.keybindings_page
        )

    def test_help_reopen_requests_the_wizard(self) -> None:
        self.window._show_page(6)
        with patch.object(self.window, "_show_onboarding") as mocked:
            self.window.help_page.onboardingRequested.emit()
        mocked.assert_called_once_with(force=True)

    def test_first_run_is_skipped_once_and_force_reopens(self) -> None:
        with patch(
            "app.ui.main_window.OnboardingDialog", FakeDialog
        ):
            self.window._maybe_show_onboarding()
            self.assertEqual(len(FakeDialog.instances), 1)
            state = OnboardingState.load(self.onboarding_path)
            self.assertTrue(state.skipped)
            self.assertTrue(state.done)

            # The same session and the saved state both suppress a second pop.
            self.window._maybe_show_onboarding()
            self.assertEqual(len(FakeDialog.instances), 1)

            FakeDialog.outcome = "completed"
            self.window._show_onboarding(force=True)
            self.assertEqual(len(FakeDialog.instances), 2)
            state = OnboardingState.load(self.onboarding_path)
            self.assertTrue(state.completed)
            self.assertFalse(state.skipped)

    def test_lesson_outcome_opens_stage_zero(self) -> None:
        FakeDialog.outcome = "lesson"
        with patch(
            "app.ui.main_window.OnboardingDialog", FakeDialog
        ):
            self.window._show_onboarding(force=True)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.learning_page
        )
        self.assertEqual(self.window.learning_page._stage_index, 0)

    def test_calibration_outcome_opens_calibration(self) -> None:
        FakeDialog.outcome = "calibration"
        with patch(
            "app.ui.main_window.OnboardingDialog", FakeDialog
        ):
            self.window._show_onboarding(force=True)
        self.assertIs(
            self.window.stack.currentWidget(), self.window.calibration_page
        )
        self.assertTrue(self.window.instrument.calibration_active)


if __name__ == "__main__":
    unittest.main()
