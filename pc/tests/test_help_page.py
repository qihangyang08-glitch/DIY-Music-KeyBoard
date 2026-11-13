"""Help page: seven page sections, live key map, actions."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.instrument import Instrument
from app.core.synth_service import NullSynth
from app.ui.help_page import HelpPage
from app.ui.keybindings import Chord, KeyBindings
from app.ui.theme import THEMES


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class HelpPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.bindings = KeyBindings(root / "keybindings.json")
        self.page = HelpPage(
            THEMES["studio"], self.instrument, self.bindings
        )
        self.page.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.page.resize(1120, 760)
        self.page.show()
        wait(80)

    def tearDown(self) -> None:
        self.page.close()
        self.instrument._timer.stop()
        self.tmp.cleanup()

    def test_seven_page_sections_are_present(self) -> None:
        self.assertEqual(len(self.page.page_titles), 7)
        self.assertEqual(
            self.page.page_titles,
            ("演奏", "学习", "曲库", "创作", "设备", "设置", "帮助"),
        )

    def test_key_map_has_32_keys_and_follows_bindings(self) -> None:
        self.assertEqual(len(self.page.key_labels), 32)
        self.assertIn("C5", self.page.key_labels[8].text())
        self.assertIn(",", self.page.key_labels[8].text())

        self.bindings.notes[8] = Chord(int(Qt.Key.Key_Q))
        self.page.refresh()
        self.assertIn("Q", self.page.key_labels[8].text())
        self.assertIn("C5", self.page.key_labels[8].text())

    def test_function_keys_show_f1_help_and_update(self) -> None:
        self.assertIn("F1", self.page.function_labels["help"].text())

        self.bindings.functions["help"] = Chord(int(Qt.Key.Key_F2), 0)
        self.page.refresh()
        self.assertIn("F2", self.page.function_labels["help"].text())

    def test_bottom_actions_emit_their_signals(self) -> None:
        calls: list[str] = []
        self.page.onboardingRequested.connect(lambda: calls.append("onboard"))
        self.page.calibrationRequested.connect(lambda: calls.append("cal"))
        self.page.keybindingsRequested.connect(lambda: calls.append("keys"))

        for text in ("重新打开首启向导", "去校准", "键位设置"):
            button = next(
                b for b in self.page.findChildren(QPushButton)
                if b.text() == text
            )
            button.click()
        self.assertEqual(calls, ["onboard", "cal", "keys"])

    def test_theme_switch_is_safe(self) -> None:
        self.page.set_theme(THEMES["stage"])
        self.assertIs(self.page._theme, THEMES["stage"])
        self.bindings.notes[8] = Chord(int(Qt.Key.Key_Q))
        self.page.refresh()
        self.assertIn("Q", self.page.key_labels[8].text())


if __name__ == "__main__":
    unittest.main()
