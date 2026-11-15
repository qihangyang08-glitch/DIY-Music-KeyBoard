"""Accessibility: high-contrast theme, accessible names, prefs (A7)."""

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
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QWidget,
)

from app.core.accessibility import AccessibilityPrefs
from app.ui.a11y import ensure_accessible_names, meaningful_text
from app.ui.i18n_ui import set_language
from app.ui.main_window import MainWindow
from app.ui.theme import THEMES, high_contrast_theme


def luminance(color) -> float:
    values = []
    for channel in (color.redF(), color.greenF(), color.blueF()):
        values.append(
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast(foreground, background) -> float:
    first, second = luminance(foreground), luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


class HighContrastThemeTest(unittest.TestCase):
    def test_all_text_roles_reach_aa_in_high_contrast(self) -> None:
        for name, theme in THEMES.items():
            high = high_contrast_theme(theme)
            for role in ("ink", "muted", "faint", "amber", "danger"):
                with self.subTest(theme=name, role=role):
                    ratio = contrast(
                        getattr(high, role), high.bg
                    )
                    self.assertGreaterEqual(
                        ratio, 4.5, f"{name}/{role} = {ratio:.2f}"
                    )

    def test_high_contrast_keeps_the_theme_identity(self) -> None:
        studio = high_contrast_theme(THEMES["studio"])
        self.assertEqual(studio.name, "studio")
        self.assertFalse(studio.dark)
        self.assertNotEqual(studio.faint.name(), THEMES["studio"].faint.name())
        self.assertEqual(studio.font_scale, THEMES["studio"].font_scale)


class HighContrastPrefsTest(unittest.TestCase):
    def test_default_is_off(self) -> None:
        self.assertFalse(AccessibilityPrefs().high_contrast)

    def test_round_trip_and_type_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            prefs = AccessibilityPrefs(path)
            prefs.high_contrast = True
            prefs.save()
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = AccessibilityPrefs.load(path)
        self.assertTrue(payload["high_contrast"])
        self.assertTrue(loaded.high_contrast)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            path.write_text(
                '{"high_contrast": "yes"}', encoding="utf-8"
            )
            self.assertFalse(AccessibilityPrefs.load(path).high_contrast)


class MeaningfulTextTest(unittest.TestCase):
    def test_symbols_alone_are_not_descriptive(self) -> None:
        self.assertFalse(meaningful_text("?"))
        self.assertFalse(meaningful_text("−"))
        self.assertFalse(meaningful_text("↺"))
        self.assertFalse(meaningful_text("   "))
        self.assertTrue(meaningful_text("演奏"))
        self.assertTrue(meaningful_text("Play"))
        self.assertTrue(meaningful_text("A–B"))


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class AccessibleNameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=self.root / "learning.json",
            bindings_path=self.root / "keybindings.json",
            prefs_path=self.root / "score_prefs.json",
            library_root=self.root / "scores",
            accessibility_path=self.root / "accessibility.json",
        )
        self.window.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.window.resize(1120, 760)
        self.window.show()
        wait(200)

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        set_language("zh-CN")
        self.tmp.cleanup()

    def _interactive(self, page: QWidget) -> list[QWidget]:
        found = []
        for widget in page.findChildren(QWidget):
            if not widget.isVisible():
                continue
            if isinstance(
                widget, (QAbstractButton, QLineEdit, QComboBox)
            ):
                found.append(widget)
            elif (
                widget.focusPolicy() != Qt.FocusPolicy.NoFocus
                and not isinstance(widget, QScrollArea)
            ):
                found.append(widget)
        return found

    def test_every_interactive_widget_has_an_accessible_name(self) -> None:
        for index in range(7):
            self.window._show_page(index)
            wait(90)
            page = self.window.pages[index]
            for widget in self._interactive(page):
                with self.subTest(
                    page=index, widget=type(widget).__name__
                ):
                    self.assertTrue(
                        widget.accessibleName().strip(),
                        f"{type(widget).__name__} on page {index}",
                    )

    def test_symbol_buttons_use_their_tooltip(self) -> None:
        self.window._show_page(0)
        wait(80)
        names = {
            button.text(): button.accessibleName()
            for button in self.window.findChildren(QAbstractButton)
            if button.isVisible()
        }
        self.assertIn("演奏", names["▶   演奏"])
        self.assertIn("设置", names["⋯"])
        self.assertGreater(len(names["?"]), 1)

    def test_custom_painted_widgets_are_named(self) -> None:
        band = self.window.perform.band
        self.assertIn("光条", band.accessibleName())
        self.assertTrue(band.accessibleDescription())
        score = self.window.perform.score.canvas
        self.assertTrue(score.accessibleName())
        self.assertTrue(self.window.volume_btn.accessibleName())

    def test_toggles_expose_a_name(self) -> None:
        for toggle in self.window.perform.findChildren(QAbstractButton):
            if type(toggle).__name__ == "ToggleSwitch":
                self.assertTrue(toggle.accessibleName().strip())
                break
        else:
            self.fail("perform page has no toggle switch")

    def test_helper_is_idempotent(self) -> None:
        label = QLineEdit()
        label.setPlaceholderText("搜索")
        ensure_accessible_names(label)
        first = label.accessibleName()
        label.setAccessibleName("自定义")
        ensure_accessible_names(label)
        self.assertEqual(label.accessibleName(), "自定义")
        self.assertEqual(first, "搜索")


class HighContrastUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_toggle_applies_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "accessibility.json"
            window = MainWindow(
                serial_enabled=False,
                audio_enabled=False,
                progress_path=root / "learning.json",
                bindings_path=root / "keybindings.json",
                prefs_path=root / "score_prefs.json",
                library_root=root / "scores",
                accessibility_path=path,
            )
            window.setAttribute(
                Qt.WidgetAttribute.WA_DontShowOnScreen, True
            )
            window.show()
            wait(180)
            try:
                switch = window.settings_page.high_contrast_switch
                self.assertTrue(switch.accessibleName().strip())
                switch.setChecked(True)
                wait(80)
                self.assertTrue(window.accessibility.high_contrast)
                self.assertEqual(
                    window.theme.faint.name(),
                    high_contrast_theme(THEMES["studio"]).faint.name(),
                )
                self.assertTrue(path.is_file())
                self.assertTrue(
                    AccessibilityPrefs.load(path).high_contrast
                )
            finally:
                window.close()
                wait(60)


if __name__ == "__main__":
    unittest.main()
