"""Per-score split-bar preferences: tolerant load, scoped keys, atomic save."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import SCORE_DIR
from app.core.score_prefs import ScorePrefs, score_key


class ScoreKeyTest(unittest.TestCase):
    def test_builtin_scores_use_the_stem(self) -> None:
        key = score_key(SCORE_DIR / "split_hands_8bars.musicxml", SCORE_DIR)
        self.assertEqual(key, "builtin:split_hands_8bars")

    def test_imported_same_stem_uses_its_own_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imported = Path(tmp) / "split_hands_8bars.musicxml"
            imported.write_text("<score/>", encoding="utf-8")
            key = score_key(imported, SCORE_DIR)
        self.assertTrue(key.startswith("file:"))
        self.assertNotEqual(key, "builtin:split_hands_8bars")


class ScorePrefsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "score_prefs.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_load_round_trip(self) -> None:
        prefs = ScorePrefs(self.path)
        self.assertEqual(prefs.set_split_bar("builtin:a", 20), 20)

        loaded = ScorePrefs.load(self.path)
        self.assertEqual(loaded.split_bar("builtin:a"), 20)
        self.assertIsNone(loaded.split_bar("builtin:b"))

    def test_clear_split_bar_saves_the_removal(self) -> None:
        prefs = ScorePrefs(self.path)
        prefs.set_split_bar("builtin:a", 20)

        self.assertTrue(prefs.clear_split_bar("builtin:a"))
        self.assertFalse(prefs.clear_split_bar("builtin:a"))
        self.assertIsNone(ScorePrefs.load(self.path).split_bar("builtin:a"))

    def test_values_are_clamped(self) -> None:
        prefs = ScorePrefs(self.path)
        self.assertEqual(prefs.set_split_bar("builtin:a", 0), 1)
        self.assertEqual(prefs.set_split_bar("builtin:b", 99), 31)

    def test_bad_values_are_ignored(self) -> None:
        self.path.write_text(
            '{"version": 1, "split_bars": '
            '{"ok": 20, "big": 99, "text": "x", "bool": true, "zero": 0}}',
            encoding="utf-8",
        )
        prefs = ScorePrefs.load(self.path)
        self.assertEqual(prefs.split_bar("ok"), 20)
        self.assertIsNone(prefs.split_bar("big"))
        self.assertIsNone(prefs.split_bar("text"))
        self.assertIsNone(prefs.split_bar("bool"))
        self.assertIsNone(prefs.split_bar("zero"))

    def test_corrupt_file_loads_empty(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        prefs = ScorePrefs.load(self.path)
        self.assertEqual(prefs.split_bars, {})


if __name__ == "__main__":
    unittest.main()
