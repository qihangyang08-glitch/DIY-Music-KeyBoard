"""UI wiring for font scaling: settings chips, persistence, theme propagation."""

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

from collections import Counter
from unittest.mock import patch

from PySide6.QtGui import QFont

import app.ui.score_view as score_view_module
import app.ui.theme as theme_module
from app.core.accessibility import AccessibilityPrefs
from app.core.drill import NoteQuestion
from app.core.rhythm import RhythmSpec
from app.ui.drill_page import StaffView
from app.ui.main_window import MainWindow
from app.ui.rhythm_view import RhythmCanvas
from app.ui.theme import Theme


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def make_window(root: Path, accessibility_path: Path) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        prefs_path=root / "score_prefs.json",
        library_root=root / "scores",
        accessibility_path=accessibility_path,
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(140)
    return window


class FontScaleUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.accessibility_path = self.root / "accessibility.json"
        self.window = make_window(self.root, self.accessibility_path)

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.tmp.cleanup()

    def test_settings_font_chip_updates_pref_theme_and_saves(self) -> None:
        seen: list[float] = []
        self.window.settings_page.fontScaleChanged.connect(seen.append)
        self.window.settings_page.font_scale_buttons[1.2].click()
        self.assertEqual(seen, [1.2])
        self.assertEqual(self.window.accessibility.font_scale, 1.2)
        self.assertEqual(
            AccessibilityPrefs.load(self.accessibility_path).font_scale, 1.2
        )
        self.assertEqual(self.window.theme.font_scale, 1.2)
        self.assertIn("font-size: 18px", self.window.styleSheet())
        self.assertIn("font-size: 19px", self.window.styleSheet())
        self.assertTrue(
            self.window.settings_page.font_scale_buttons[1.2].isChecked()
        )

    def test_font_scale_restored_on_startup(self) -> None:
        prefs = AccessibilityPrefs(self.accessibility_path)
        prefs.font_scale = 1.2
        prefs.save()
        other = make_window(self.root, self.accessibility_path)
        try:
            self.assertEqual(other.theme.font_scale, 1.2)
            self.assertTrue(
                other.settings_page.font_scale_buttons[1.2].isChecked()
            )
            self.assertIn("font-size: 18px", other.styleSheet())
        finally:
            other.close()
            wait(60)

    def test_theme_switch_preserves_font_scale(self) -> None:
        self.window.settings_page.font_scale_buttons[1.2].click()
        self.window.apply_theme("stage")
        self.assertEqual(self.window.theme.name, "stage")
        self.assertEqual(self.window.theme.font_scale, 1.2)
        self.assertIn("font-size: 18px", self.window.styleSheet())
        self.assertTrue(
            self.window.settings_page.font_scale_buttons[1.2].isChecked()
        )

    def test_scaled_theme_propagates_to_pages_and_custom_widgets(self) -> None:
        self.window.settings_page.font_scale_buttons[1.2].click()
        self.assertIs(self.window.perform.band._theme, self.window.theme)
        self.assertIs(self.window.compose_page._theme, self.window.theme)
        self.assertIs(self.window.settings_page._theme, self.window.theme)
        self.assertEqual(
            self.window.perform.band._theme.font(8).pixelSize(), 10
        )

    def record_theme_fonts(self, widget) -> list[int]:
        """Design pixel sizes requested through Theme.font() during a paint."""
        sizes: list[int] = []
        original = Theme.font

        def recorder(theme_self, px, weight=QFont.Weight.Normal, mono=False):
            sizes.append(px)
            return original(theme_self, px, weight, mono)

        with patch.object(Theme, "font", recorder):
            widget.grab()
        return sizes

    def test_band_custom_painter_fonts_use_scaled_theme(self) -> None:
        self.window.settings_page.font_scale_buttons[1.2].click()
        band = self.window.perform.band
        band.set_labels(True)
        band.set_active({3})
        band.set_next_key(4)
        band.flash_hit(5)
        sizes = self.record_theme_fonts(band)
        self.assertEqual(
            Counter(sizes), Counter({7: 32, 8: 38, 13: 1}), sorted(sizes)
        )

    def test_every_custom_canvas_scales_its_fonts(self) -> None:
        self.window.settings_page.font_scale_buttons[1.2].click()
        score_sizes = self.record_theme_fonts(self.window.perform.score.canvas)
        self.assertIn(8, score_sizes)  # measure numbers, 8 -> 10
        self.assertIn(7, score_sizes)  # note names on the roll, 7 -> 8
        self.assertIn(9, score_sizes)  # hit/miss caption, 9 -> 11
        roll_sizes = self.record_theme_fonts(self.window.compose_page.roll)
        self.assertIn(8, roll_sizes)  # bar numbers, 8 -> 10
        strip_sizes = self.record_theme_fonts(self.window.drill_page._strip)
        self.assertIn(7, strip_sizes)  # keycaps, 7 -> 8
        self.assertIn(9, strip_sizes)  # note names, 9 -> 11
        spec = RhythmSpec(
            "test", "test", "", 80, 4, 1, ((1.0, 1.0, 1.0, 1.0),)
        )
        rhythm = RhythmCanvas(self.window.theme)
        rhythm.set_spec(spec)
        rhythm.resize(640, 220)
        rhythm_sizes = self.record_theme_fonts(rhythm)
        self.assertIn(8, rhythm_sizes)
        self.assertIn(10, rhythm_sizes)

    def test_staff_notation_stays_on_staff_geometry(self) -> None:
        self.window.settings_page.font_scale_buttons[1.2].click()
        staff = StaffView(self.window.theme)
        staff.set_question(
            NoteQuestion(midi=60, name="C4", staff_step=0)
        )
        staff.resize(640, 220)
        self.assertEqual(self.record_theme_fonts(staff), [])
        # The key/time signature glyphs use the module-level font(), not the
        # UI text scale; keep them on staff geometry.
        canvas = self.window.perform.score.canvas
        canvas.set_mode("sheet")
        with patch.object(
            score_view_module, "font", wraps=score_view_module.font
        ) as raw_font:
            canvas.grab()
        self.assertGreater(raw_font.call_count, 0)

    def test_zero_nine_preset_scales_down(self) -> None:
        button = self.window.settings_page.font_scale_buttons[0.9]
        button.click()
        self.assertEqual(self.window.theme.font_scale, 0.9)
        self.assertTrue(button.isChecked())
        self.assertEqual(self.window.root.font().pixelSize(), 11)
        self.assertEqual(self.window.drill_page._title.font().pixelSize(), 18)
        self.assertEqual(
            self.window.drill_page._summary_score.font().pixelSize(), 41
        )
        self.assertIn("font-size: 10px", self.window.styleSheet())

    def test_non_preset_chip_is_not_misreported(self) -> None:
        prefs = AccessibilityPrefs(self.accessibility_path)
        prefs.font_scale = 1.15
        prefs.save()
        other = make_window(self.root, self.accessibility_path)
        try:
            self.assertEqual(other.theme.font_scale, 1.15)
            self.assertFalse(
                any(
                    button.isChecked()
                    for button in other.settings_page.font_scale_buttons.values()
                )
            )
        finally:
            other.close()
            wait(60)

    def test_runtime_scale_values_are_normalized(self) -> None:
        self.window.settings_page.fontScaleChanged.emit(5.0)
        self.assertEqual(self.window.accessibility.font_scale, 1.3)
        self.assertEqual(
            AccessibilityPrefs.load(self.accessibility_path).font_scale, 1.3
        )
        self.assertFalse(
            self.window.settings_page.font_scale_buttons[1.2].isChecked()
        )
        self.window._set_font_scale(float("nan"))
        self.assertEqual(self.window.accessibility.font_scale, 1.0)
        self.assertTrue(
            self.window.settings_page.font_scale_buttons[1.0].isChecked()
        )
        self.window._set_font_scale(True)
        self.assertEqual(self.window.accessibility.font_scale, 1.0)

    def test_rendered_label_hierarchy_scales(self) -> None:
        self.assertEqual(self.window.root.font().pixelSize(), 12)
        self.assertEqual(self.window.drill_page._title.font().pixelSize(), 20)
        self.assertEqual(
            self.window.drill_page._summary_score.font().pixelSize(), 46
        )
        self.window.settings_page.font_scale_buttons[1.2].click()
        self.assertEqual(self.window.root.font().pixelSize(), 14)
        self.assertEqual(self.window.drill_page._title.font().pixelSize(), 24)
        self.assertEqual(
            self.window.drill_page._summary_score.font().pixelSize(), 55
        )
        # The compact keybinding chips were fixed at 22 px; they must be able
        # to grow when the chip font grows.
        compact = [
            button
            for button in self.window.keybindings_page.findChildren(QPushButton)
            if button.minimumHeight() == 22
        ]
        self.assertTrue(compact)
        for button in compact:
            self.assertGreater(button.maximumHeight(), 22)

    def test_inline_qss_uses_scaled_sizes(self) -> None:
        self.assertIn("font-size: 12px", self.window.library_page.search.styleSheet())
        self.assertIn(
            "font-size: 11px",
            self.window.calibration_page._badge_label.styleSheet(),
        )
        self.window.settings_page.font_scale_buttons[1.2].click()
        self.assertIn("font-size: 14px", self.window.library_page.search.styleSheet())
        self.assertIn(
            "font-size: 13px",
            self.window.calibration_page._badge_label.styleSheet(),
        )


if __name__ == "__main__":
    unittest.main()
