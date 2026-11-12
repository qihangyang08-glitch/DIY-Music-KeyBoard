"""Theme font scaling: one scale carrier for QSS and custom painters."""

from __future__ import annotations

import re
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.ui.theme import STAGE, STUDIO
from app.ui.theme import font as module_font

BASELINE = [
    11, 10, 10, 15, 16, 12, 12, 12, 14, 13, 11, 13, 14, 12, 12, 12, 11, 11, 12
]
SCALED_120 = [
    13, 12, 12, 18, 19, 14, 14, 14, 17, 16, 13, 16, 17, 14, 14, 14, 13, 13, 14
]


def sizes(qss: str) -> list[int]:
    return [int(value) for value in re.findall(r"font-size:\s*(\d+)px", qss)]


class FontCacheTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_font_helper_reuses_identical_fonts(self) -> None:
        first = module_font(12)
        self.assertIs(first, module_font(12))
        self.assertIsNot(first, module_font(13))
        self.assertIsNot(first, module_font(12, QFont.Weight.Bold))
        self.assertIsNot(first, module_font(12, mono=True))
        # The cached object still carries the requested properties.
        self.assertEqual(module_font(14, QFont.Weight.DemiBold).pixelSize(), 14)


class ThemeScaleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_default_scale_keeps_the_existing_qss(self) -> None:
        self.assertEqual(STUDIO.font_scale, 1.0)
        self.assertEqual(sizes(STUDIO.qss()), BASELINE)
        self.assertEqual(sizes(STAGE.qss()), BASELINE)
        self.assertEqual(replace(STUDIO, font_scale=1.0).qss(), STUDIO.qss())

    def test_qss_font_sizes_scale_half_up(self) -> None:
        scaled = replace(STUDIO, font_scale=1.2)
        self.assertEqual(sizes(scaled.qss()), SCALED_120)
        self.assertNotEqual(scaled.qss(), STUDIO.qss())

    def test_theme_font_scales_pixel_size_and_keeps_weight(self) -> None:
        theme = replace(STUDIO, font_scale=1.25)
        font = theme.font(9, QFont.Weight.DemiBold)
        self.assertEqual(font.pixelSize(), 11)
        self.assertEqual(font.weight(), QFont.Weight.DemiBold)
        self.assertEqual(replace(STUDIO, font_scale=1.2).font(8).pixelSize(), 10)
        # The module-level helper stays unscaled for callers that opt out.
        self.assertEqual(module_font(9).pixelSize(), 9)

    def test_scaling_never_mutates_singletons_and_floors_at_one(self) -> None:
        scaled = replace(STUDIO, font_scale=1.3)
        self.assertEqual(scaled.px(10), 13)
        self.assertEqual(STUDIO.font_scale, 1.0)
        self.assertIn("font-size: 12px", STUDIO.qss())
        self.assertEqual(replace(STUDIO, font_scale=0.01).px(10), 1)
        # 10 * 1.25 = 12.5: half-up must give 13, unlike round()'s 12.
        self.assertEqual(replace(STUDIO, font_scale=1.25).px(10), 13)


if __name__ == "__main__":
    unittest.main()
