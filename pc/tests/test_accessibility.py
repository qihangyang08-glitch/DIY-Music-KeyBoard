"""Accessibility preferences: reduce motion, tolerant load, atomic save."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.accessibility import (
    FONT_SCALE_MAX,
    FONT_SCALE_MIN,
    AccessibilityPrefs,
)


class AccessibilityPrefsTest(unittest.TestCase):
    def test_defaults_keep_motion(self) -> None:
        prefs = AccessibilityPrefs()
        self.assertFalse(prefs.reduce_motion)

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            prefs = AccessibilityPrefs()
            prefs.reduce_motion = True
            prefs.save(path)
            loaded = AccessibilityPrefs.load(path)
        self.assertTrue(loaded.reduce_motion)

    def test_missing_or_corrupt_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = AccessibilityPrefs.load(root / "missing.json")
            broken = root / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            corrupt = AccessibilityPrefs.load(broken)
        self.assertFalse(missing.reduce_motion)
        self.assertFalse(corrupt.reduce_motion)

    def test_non_boolean_value_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "accessibility.json"
            path.write_text(
                '{"version": 1, "reduce_motion": "yes"}', encoding="utf-8"
            )
            loaded = AccessibilityPrefs.load(path)
        self.assertFalse(loaded.reduce_motion)

    def test_language_defaults_to_chinese_and_round_trips(self) -> None:
        self.assertEqual(AccessibilityPrefs().language, "zh-CN")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            prefs = AccessibilityPrefs()
            prefs.language = "en"
            prefs.save(path)
            loaded = AccessibilityPrefs.load(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded.language, "en")
        self.assertEqual(payload["language"], "en")

    def test_unknown_language_falls_back_to_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            path.write_text(
                '{"language": "fr", "font_scale": 1.2}', encoding="utf-8"
            )
            loaded = AccessibilityPrefs.load(path)
        self.assertEqual(loaded.language, "zh-CN")

    def test_font_scale_defaults_to_one(self) -> None:
        self.assertEqual(AccessibilityPrefs().font_scale, 1.0)

    def test_font_scale_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessibility.json"
            prefs = AccessibilityPrefs()
            prefs.font_scale = 1.15
            prefs.save(path)
            loaded = AccessibilityPrefs.load(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertAlmostEqual(loaded.font_scale, 1.15)
        self.assertAlmostEqual(payload["font_scale"], 1.15)

    def test_font_scale_invalid_values_fall_back_to_one(self) -> None:
        invalid = ("big", True, None, [1.2], float("nan"), float("inf"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, value in enumerate(invalid):
                with self.subTest(value=value):
                    path = root / f"bad{index}.json"
                    path.write_text(
                        json.dumps({"font_scale": value}), encoding="utf-8"
                    )
                    self.assertEqual(
                        AccessibilityPrefs.load(path).font_scale, 1.0
                    )

    def test_huge_integer_and_deep_nesting_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            huge = root / "huge.json"
            huge.write_text(
                '{"font_scale": ' + "9" * 400 + "}", encoding="utf-8"
            )
            nested = root / "nested.json"
            nested.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
            huge_prefs = AccessibilityPrefs.load(huge)
            nested_prefs = AccessibilityPrefs.load(nested)
        self.assertEqual(huge_prefs.font_scale, 1.0)
        self.assertEqual(nested_prefs.font_scale, 1.0)

    def test_font_scale_out_of_range_clamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (
                (0.2, FONT_SCALE_MIN),
                (9.0, FONT_SCALE_MAX),
                (FONT_SCALE_MIN, FONT_SCALE_MIN),
                (FONT_SCALE_MAX, FONT_SCALE_MAX),
            )
            for index, (value, expected) in enumerate(cases):
                with self.subTest(value=value):
                    path = root / f"range{index}.json"
                    path.write_text(
                        json.dumps({"font_scale": value}), encoding="utf-8"
                    )
                    self.assertEqual(
                        AccessibilityPrefs.load(path).font_scale, expected
                    )

    def test_old_pref_file_without_font_scale_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.json"
            old.write_text(
                '{"version": 1, "reduce_motion": true}', encoding="utf-8"
            )
            loaded = AccessibilityPrefs.load(old)
            both = root / "both.json"
            both.write_text(
                '{"version": 1, "reduce_motion": true, "font_scale": 1.2}',
                encoding="utf-8",
            )
            loaded_both = AccessibilityPrefs.load(both)
        self.assertTrue(loaded.reduce_motion)
        self.assertEqual(loaded.font_scale, 1.0)
        self.assertTrue(loaded_both.reduce_motion)
        self.assertEqual(loaded_both.font_scale, 1.2)


if __name__ == "__main__":
    unittest.main()
