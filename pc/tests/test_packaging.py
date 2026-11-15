"""Windows bundle: frozen path resolution, data plan and dependency check (A4)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import packaging  # noqa: E402
from app.core.paths import (  # noqa: E402
    bundle_root,
    mapping_path,
    resource_path,
    vendor_path,
)


class BundleRootTest(unittest.TestCase):
    def test_source_tree_root_is_pc(self) -> None:
        self.assertEqual(bundle_root(), ROOT)
        self.assertEqual(resource_path("scores"), ROOT / "resources" / "scores")
        self.assertEqual(
            vendor_path("soundfont"), ROOT / "prototype" / "vendor" / "soundfont"
        )
        self.assertEqual(
            mapping_path("keymap.json"), ROOT.parent / "mapping" / "keymap.json"
        )

    def test_frozen_root_prefers_the_pyinstaller_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "_MEIPASS", tmp, create=True):
                self.assertEqual(bundle_root(), Path(tmp))
                self.assertEqual(
                    resource_path("scores"),
                    Path(tmp) / "resources" / "scores",
                )
                self.assertEqual(
                    vendor_path(),
                    Path(tmp) / "prototype" / "vendor",
                )
                self.assertEqual(
                    mapping_path("keymap.json"),
                    Path(tmp) / "mapping" / "keymap.json",
                )

    def test_frozen_without_meipass_falls_back_to_pc(self) -> None:
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "_MEIPASS", "", create=True):
            self.assertEqual(bundle_root(), ROOT)


class DataPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "resources" / "scores").mkdir(parents=True)
        (self.root / "resources" / "scores" / "a.musicxml").write_text(
            "<score/>", encoding="utf-8"
        )
        (self.root / "resources" / "lessons").mkdir(parents=True)
        (self.root / "resources" / "lessons" / "a.json").write_text(
            '{"visibility": "public", "public_release": "yes"}',
            encoding="utf-8",
        )
        dll = (
            self.root / "prototype" / "vendor" / "fluidsynth-9.9" / "bin"
        )
        dll.mkdir(parents=True)
        (dll / "libfluidsynth-3.dll").write_bytes(b"MZ")
        (dll / "SDL3.dll").write_bytes(b"MZ")
        (dll / "fluidsynth.exe").write_bytes(b"MZ")
        (self.root / "prototype" / "vendor" / "soundfont").mkdir(
            parents=True
        )
        (
            self.root
            / "prototype"
            / "vendor"
            / "soundfont"
            / "TimGM6mb.sf2"
        ).write_bytes(b"RIFF")
        # User data must never be picked up even if it sits nearby.
        (self.root / "learning.json").write_text("{}", encoding="utf-8")
        self.plan = packaging.collect_data_files(self.root)

    def test_resources_and_vendor_assets_are_bundled(self) -> None:
        sources = {source for source, _dest in self.plan}
        self.assertIn(
            self.root / "resources" / "scores" / "a.musicxml", sources
        )
        self.assertIn(self.root / "resources" / "lessons" / "a.json", sources)
        self.assertIn(
            self.root / "prototype" / "vendor" / "soundfont" / "TimGM6mb.sf2",
            sources,
        )
        self.assertIn(
            self.root
            / "prototype"
            / "vendor"
            / "fluidsynth-9.9"
            / "bin"
            / "libfluidsynth-3.dll",
            sources,
        )

    def test_destinations_keep_the_tree_shape(self) -> None:
        destinations = {source.name: dest for source, dest in self.plan}
        self.assertEqual(destinations["a.musicxml"], "resources/scores")
        self.assertEqual(destinations["a.json"], "resources/lessons")
        self.assertEqual(
            destinations["TimGM6mb.sf2"], "prototype/vendor/soundfont"
        )
        self.assertEqual(
            destinations["libfluidsynth-3.dll"],
            "prototype/vendor/fluidsynth-9.9/bin",
        )

    def test_user_data_and_executables_are_not_bundled(self) -> None:
        names = {source.name for source, _dest in self.plan}
        self.assertNotIn("learning.json", names)
        self.assertNotIn("fluidsynth.exe", names)

    def test_pyinstaller_datas_are_string_pairs(self) -> None:
        datas = packaging.pyinstaller_datas(self.root)
        self.assertTrue(datas)
        for source, destination in datas:
            self.assertIsInstance(source, str)
            self.assertIsInstance(destination, str)
        self.assertIn(
            (
                str(self.root / "resources" / "scores" / "a.musicxml"),
                "resources/scores",
            ),
            datas,
        )

    def test_private_or_unlisted_content_is_not_bundled(self) -> None:
        bad = self.root / "resources" / "lessons" / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        datas = packaging.pyinstaller_datas(self.root, self.root)
        bundled = {source for source, _dest in datas}
        self.assertNotIn(str(bad), bundled)
        self.assertIn(
            str(self.root / "resources" / "lessons" / "a.json"), bundled
        )

    def test_repo_mapping_table_is_bundled_under_mapping(self) -> None:
        mapping = self.root / "mapping"
        mapping.mkdir()
        (mapping / "keymap.json").write_text("{}", encoding="utf-8")
        datas = packaging.pyinstaller_datas(self.root, self.root)
        self.assertIn(
            (str(mapping / "keymap.json"), "mapping"),
            datas,
        )

    def test_missing_roots_are_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            self.assertEqual(packaging.collect_data_files(empty), [])
            self.assertEqual(packaging.pyinstaller_datas(empty), [])


class DependencyCheckTest(unittest.TestCase):
    def test_missing_pyinstaller_reports_the_pip_command(self) -> None:
        with mock.patch.object(
            packaging.importlib.util, "find_spec", return_value=None
        ):
            problem = packaging.pyinstaller_problem()
        self.assertIsNotNone(problem)
        self.assertIn("pip install", problem)
        self.assertIn("pyinstaller", problem.lower())

    def test_installed_pyinstaller_passes(self) -> None:
        with mock.patch.object(
            packaging.importlib.util, "find_spec", return_value=object()
        ):
            self.assertIsNone(packaging.pyinstaller_problem())


class SpecTest(unittest.TestCase):
    def test_spec_bundles_data_and_the_app_entry(self) -> None:
        spec = (ROOT / "packaging" / "keyborad.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("app/main.py", spec)
        self.assertIn("pyinstaller_datas", spec)
        self.assertIn("pyinstaller_datas", spec)
        self.assertIn("console=False", spec)
        self.assertIn("KeyBorad", spec)


if __name__ == "__main__":
    unittest.main()
