"""Library scan performance: a bounded, stat-keyed parse cache.

Tests assert operation counts, never wall-clock timings.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import app.core.library as library
import app.ui.library_page as library_page_module
from app.core.curriculum import SCORE_DIR
from app.core.library import (
    DEFAULT_PARSE_CACHE,
    MAX_SCAN_FILES,
    ScoreParseCache,
    build_registry,
)
from app.ui.library_page import LibraryPage
from app.ui.theme import STUDIO

FIXTURES = ("xiaoxingxing", "two_tigers", "london_bridge")


def copy_fixture(name: str, folder: Path, target: str | None = None) -> Path:
    destination = folder / (target or f"{name}.musicxml")
    shutil.copy2(SCORE_DIR / f"{name}.musicxml", destination)
    return destination


def force_mtime(path: Path, seconds: int) -> None:
    stamp = seconds * 1_000_000_000
    os.utime(path, ns=(stamp, stamp))


def counting_parse():
    real = library.parse_score
    calls = {"n": 0}

    def wrapper(path):
        calls["n"] += 1
        return real(path)

    return wrapper, calls


class ScoreParseCacheUnitTest(unittest.TestCase):
    def test_lru_eviction_and_hit_counters(self) -> None:
        cache = ScoreParseCache(max_entries=2)
        first = Path("a.musicxml")
        second = Path("b.musicxml")
        third = Path("c.musicxml")
        key = (1, 1, 1)
        cache.put(first, key, object(), None)
        cache.put(second, key, object(), None)
        self.assertEqual(len(cache), 2)
        self.assertIsNotNone(cache.get(first, key))  # touch a
        cache.put(third, key, object(), None)  # evict b (LRU)
        self.assertEqual(len(cache), 2)
        self.assertIsNotNone(cache.get(first, key))
        self.assertIsNone(cache.get(second, key))
        self.assertEqual(cache.hits, 2)
        self.assertEqual(cache.misses, 1)

    def test_same_stem_in_two_directories_are_distinct(self) -> None:
        cache = ScoreParseCache()
        key = (1, 1, 1)
        cache.put(Path("one/same.musicxml"), key, object(), None)
        cache.put(Path("two/same.musicxml"), key, object(), None)
        self.assertEqual(len(cache), 2)

    def test_default_cache_covers_both_scan_limits(self) -> None:
        # The built-in and import scans can each produce MAX_SCAN_FILES
        # entries; a smaller cap makes a sequential rescan evict everything.
        self.assertGreaterEqual(DEFAULT_PARSE_CACHE.max_entries, MAX_SCAN_FILES * 2)


class LibraryParseCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.imports = self.root / "imports"
        self.imports.mkdir()
        self.builtin = self.root / "builtin"
        self.builtin.mkdir()
        self.cache = ScoreParseCache()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self):
        return build_registry(
            builtin_dir=self.builtin,
            import_dir=self.imports,
            parse_cache=self.cache,
        )

    def test_second_build_parses_nothing(self) -> None:
        for name in FIXTURES:
            copy_fixture(name, self.imports)
        parser, calls = counting_parse()
        with patch.object(library, "parse_score", parser):
            self.build()
            first = calls["n"]
            self.build()
            second = calls["n"] - first
        self.assertEqual(first, 3)
        self.assertEqual(second, 0)
        self.assertEqual(self.cache.misses, 3)
        self.assertEqual(self.cache.hits, 3)
        self.assertEqual(len(self.cache), 3)

    def test_changed_file_reparses_only_that_file(self) -> None:
        paths = [copy_fixture(name, self.imports) for name in FIXTURES]
        parser, calls = counting_parse()
        with patch.object(library, "parse_score", parser):
            self.build()
            before = calls["n"]
            # Replace one valid file with another valid score, new mtime.
            shutil.copy2(
                SCORE_DIR / "two_tigers.musicxml", paths[0]
            )
            force_mtime(paths[0], 1_800_000_000)
            registry = self.build()
            after = calls["n"] - before
        self.assertEqual(after, 1)
        pieces = [
            piece
            for piece in registry.pieces
            if piece.primary is not None
            and piece.primary.path.resolve() == paths[0].resolve()
        ]
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0].title, "两只老虎")

    def test_malformed_replacement_is_not_served_from_cache(self) -> None:
        path = copy_fixture("xiaoxingxing", self.imports)
        parser, calls = counting_parse()
        with patch.object(library, "parse_score", parser):
            self.build()
            path.write_text("<broken", encoding="utf-8")
            force_mtime(path, 1_800_000_001)
            before = calls["n"]
            registry = self.build()
            after = calls["n"] - before
        pieces = [
            piece
            for piece in registry.pieces
            if piece.primary is not None
            and piece.primary.path.resolve() == path.resolve()
        ]
        self.assertEqual(len(pieces), 1)
        self.assertFalse(pieces[0].playable)
        self.assertTrue(pieces[0].error)
        self.assertGreaterEqual(after, 1)

    def test_same_stem_in_builtin_and_import_are_cached_separately(self) -> None:
        copy_fixture("xiaoxingxing", self.builtin, "same.musicxml")
        copy_fixture("two_tigers", self.imports, "same.musicxml")
        registry = self.build()
        self.assertEqual(len(self.cache), 2)
        ready = [
            piece for piece in registry.pieces if piece.status == "ready"
        ]
        self.assertEqual(len(ready), 2)

    def test_failed_parse_is_retried_without_stat_change(self) -> None:
        path = self.imports / "broken.musicxml"
        path.write_text("<broken", encoding="utf-8")
        force_mtime(path, 1_800_000_002)
        parser, calls = counting_parse()
        with patch.object(library, "parse_score", parser):
            self.build()
            first = calls["n"]
            self.build()
            second = calls["n"] - first
        self.assertEqual(first, 1)
        self.assertEqual(second, 1)  # failures are never cached
        self.assertEqual(len(self.cache), 0)

    def test_default_build_reuses_the_production_cache(self) -> None:
        for name in FIXTURES[:2]:
            copy_fixture(name, self.imports)
        DEFAULT_PARSE_CACHE.clear()
        parser, calls = counting_parse()
        try:
            with patch.object(library, "parse_score", parser):
                build_registry(self.builtin, self.imports)
                first = calls["n"]
                build_registry(self.builtin, self.imports)
                second = calls["n"] - first
        finally:
            DEFAULT_PARSE_CACHE.clear()
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)

    def test_default_cache_survives_a_sequential_rescan(self) -> None:
        # More files than the old 512-entry bound, still under MAX_SCAN_FILES.
        count = 513
        source = SCORE_DIR / "xiaoxingxing.mid"
        for index in range(count):
            shutil.copy2(source, self.imports / f"score{index:03}.mid")
        parser, calls = counting_parse()
        with patch.object(library, "parse_score", parser):
            self.build()
            first = calls["n"]
            self.build()
            second = calls["n"] - first
        self.assertEqual(first, count)
        self.assertEqual(second, 0)
        self.assertEqual(len(self.cache), count)


class LibraryPageCacheIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_second_refresh_does_not_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            imports = root / "imports"
            imports.mkdir()
            for name in FIXTURES:
                copy_fixture(name, imports)
            page = LibraryPage(
                STUDIO,
                import_dir=imports,
                builtin_dir=root / "builtin",
                meta_path=root / "library_meta.json",
                watch_enabled=False,
            )
            cache = ScoreParseCache()
            original = library_page_module.build_registry

            def cached_build(builtin_dir=None, import_dir=None):
                return original(
                    builtin_dir, import_dir, parse_cache=cache
                )

            parser, calls = counting_parse()
            with patch.object(
                library_page_module, "build_registry", cached_build
            ), patch.object(library, "parse_score", parser):
                page.refresh()
                first = calls["n"]
                cards = len(page.cards)
                page.refresh()
                second = calls["n"] - first
            page.deleteLater()
        self.assertEqual(first, 3)
        self.assertEqual(second, 0)
        self.assertGreater(cards, 0)


if __name__ == "__main__":
    unittest.main()
