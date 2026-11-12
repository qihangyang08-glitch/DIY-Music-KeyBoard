"""UI-string localisation: catalogue, fallback, and the English shell."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from app.ui.i18n_ui import (
    EN,
    apply_language,
    language,
    normalize_language,
    set_language,
    tr,
)
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class TranslatorTest(unittest.TestCase):
    def tearDown(self) -> None:
        set_language("zh-CN")

    def test_english_translates_known_strings_and_falls_back(self) -> None:
        set_language("en")
        self.assertEqual(tr("演奏"), "Perform")
        self.assertEqual(tr("这句还没翻译"), "这句还没翻译")
        set_language("zh-CN")
        self.assertEqual(tr("演奏"), "演奏")

    def test_unknown_language_is_chinese(self) -> None:
        self.assertEqual(normalize_language("fr"), "zh-CN")
        set_language("fr")
        self.assertEqual(language(), "zh-CN")

    def test_catalog_has_no_empty_translations(self) -> None:
        for source, target in EN.items():
            self.assertTrue(source.strip())
            self.assertTrue(target.strip(), source)


class EnglishShellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        prefs = root / "accessibility.json"
        prefs.write_text(
            json.dumps({"language": "en", "font_scale": 1.0}),
            encoding="utf-8",
        )
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            accessibility_path=prefs,
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        set_language("zh-CN")
        self.tmp.cleanup()

    def test_shell_and_settings_are_english(self) -> None:
        nav = [button.text() for button in self.window.nav_buttons]
        self.assertEqual(
            [text.split()[-1] for text in nav[:5]],
            ["Perform", "Learn", "Library", "Create", "Device"],
        )
        settings = self.window.settings_page
        texts = [
            label.text() for label in settings.findChildren(QLabel)
        ]
        self.assertIn("Settings", texts)
        self.assertIn("Language", texts)
        self.assertIn("Accessibility", texts)

    def test_perform_controls_and_library_heading_are_english(self) -> None:
        buttons = [
            button.text()
            for button in self.window.perform.findChildren(QPushButton)
            if button.isVisible()
        ]
        self.assertIn("● Record", buttons)
        self.assertIn("Mute all", buttons)
        self.assertIn("Sheet", buttons)

        self.window._show_page(2)
        wait(120)
        labels = [
            label.text()
            for label in self.window.library_page.findChildren(QLabel)
            if label.isVisible()
        ]
        self.assertIn("Library", labels)

    def test_language_chip_persists_english(self) -> None:
        settings = self.window.settings_page
        settings._language_buttons[1].click()
        wait(80)
        payload = json.loads(
            (Path(self.tmp.name) / "accessibility.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(payload["language"], "en")


class TranslateTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        set_language("zh-CN")

    def test_widget_text_and_placeholder_are_translated(self) -> None:
        set_language("en")
        root = QWidget()
        label = QLabel("演奏", root)
        button = QPushButton("谱面", root)
        apply_language(root)
        self.assertEqual(label.text(), "Perform")
        self.assertEqual(button.text(), "Sheet")


if __name__ == "__main__":
    unittest.main()
