"""Public-build guardrails: private content must never enter a public package."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import SCORE_DIR, STAGES, PracticeItem, Stage
from app.core.project import Project
from app.core.release import (
    PublicBuildError,
    audit_package,
    build_public_archive,
    content_manifest,
    forbidden_package_path,
    plan_public_build,
)
from app.core.score import parse_score


class ForbiddenPackagePathTest(unittest.TestCase):
    def test_user_data_and_build_artifacts_are_forbidden(self) -> None:
        for path in (
            "user-data/learning.json",
            "learning.json",
            "score_prefs.json",
            "keybindings.json",
            "accessibility.json",
            "library_meta.json",
            "logs/run.log",
            "mockups/p1_shell_studio.png",
            ".pio/build/firmware.bin",
            "__pycache__/release.cpython-311.pyc",
            "resources/scores/xiaoxingxing.musicxml.tmp",
            "resources\\scores\\__pycache__\\score.pyc",
        ):
            with self.subTest(path=path):
                self.assertTrue(forbidden_package_path(path), path)

    def test_content_files_are_allowed(self) -> None:
        for path in (
            "resources/scores/xiaoxingxing.musicxml",
            "resources/scores/mariage_fragment.mid",
            "resources/projects/stage7_melody.json",
            "app/core/release.py",
        ):
            with self.subTest(path=path):
                self.assertFalse(forbidden_package_path(path), path)


class ContentManifestTest(unittest.TestCase):
    def test_private_curriculum_item_is_removed(self) -> None:
        entries = content_manifest()
        matches = [e for e in entries if e.title == "梦中的婚礼 · 片段"]
        self.assertEqual(len(matches), 1)
        entry = matches[0]
        self.assertEqual(entry.content_id, "stage6:梦中的婚礼 · 片段")
        self.assertEqual(entry.visibility, "private")
        self.assertEqual(entry.action, "remove")
        self.assertIn("resources/scores/mariage_fragment.musicxml", entry.files)
        self.assertIn("resources/scores/mariage_fragment.mid", entry.files)

    def test_manifest_covers_every_curriculum_item_once(self) -> None:
        entries = content_manifest()
        expected = sum(stage.total_count for stage in STAGES)
        self.assertEqual(len(entries), expected)
        ids = [entry.content_id for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_public_items_are_included(self) -> None:
        entries = {e.content_id: e for e in content_manifest()}
        entry = entries["stage0:两只老虎"]
        self.assertEqual(entry.visibility, "public")
        self.assertEqual(entry.action, "include")
        self.assertIn("resources/scores/two_tigers.musicxml", entry.files)
        project = entries["stage7:三轨小作品"]
        self.assertIn("resources/projects/stage7_trio.json", project.files)


class LessonReleaseTest(unittest.TestCase):
    def _root(self, tmp: str, data, name: str = "stage0_01.json") -> Path:
        root = Path(tmp)
        lessons = root / "resources" / "lessons"
        lessons.mkdir(parents=True)
        if isinstance(data, str):
            (lessons / name).write_text(data, encoding="utf-8")
        else:
            (lessons / name).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        return root

    def test_private_or_unreleased_lesson_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(
                tmp,
                {
                    "title": "私有课",
                    "visibility": "private",
                    "public_release": "yes",
                    "status": "ready",
                },
            )
            plan = plan_public_build(stages=(), project_root=root)
        excluded = dict(plan.excluded_files)
        self.assertIn("resources/lessons/stage0_01.json", excluded)
        self.assertIn("visibility=private", excluded["resources/lessons/stage0_01.json"])
        self.assertNotIn(
            "resources/lessons/stage0_01.json", plan.included_files
        )

    def test_public_released_lesson_is_included(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(
                tmp,
                {
                    "title": "公开课",
                    "visibility": "public",
                    "public_release": "yes",
                    "status": "ready",
                },
            )
            plan = plan_public_build(stages=(), project_root=root)
        self.assertIn("resources/lessons/stage0_01.json", plan.included_files)
        self.assertNotIn("resources/lessons/stage0_01.json", dict(plan.excluded_files))

    def test_unreadable_lesson_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "{bad json")
            plan = plan_public_build(stages=(), project_root=root)
        excluded = dict(plan.excluded_files)
        self.assertIn("resources/lessons/stage0_01.json", excluded)
        self.assertEqual(excluded["resources/lessons/stage0_01.json"], "unreadable lesson")


def _stage(*items: PracticeItem) -> Stage:
    return Stage(
        index=0,
        name="测试",
        band="基础",
        goal="",
        prereq="",
        guides=(),
        trainings=items,
        pieces=(),
        pass_rule="",
        next_step="",
    )


class PublicBuildPlanTest(unittest.TestCase):
    def test_private_assets_are_excluded_public_assets_included(self) -> None:
        plan = plan_public_build()
        self.assertTrue(plan.ok, plan.problems)
        excluded = dict(plan.excluded_files)
        self.assertIn("resources/scores/mariage_fragment.musicxml", excluded)
        self.assertIn("resources/scores/mariage_fragment.mid", excluded)
        self.assertNotIn("resources/scores/mariage_fragment.musicxml", plan.included_files)
        self.assertNotIn("resources/scores/mariage_fragment.mid", plan.included_files)
        self.assertIn("resources/scores/xiaoxingxing.musicxml", plan.included_files)
        self.assertIn("resources/scores/LICENSE.md", plan.included_files)
        self.assertIn("resources/projects/template_piano_solo.json", plan.included_files)
        self.assertEqual(
            [path for path in plan.included_files if forbidden_package_path(path)], []
        )

    def test_project_metadata_can_exclude_a_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "resources" / "projects"
            projects.mkdir(parents=True)
            Project(title="私有", visibility="private").save(projects / "secret.json")
            Project(title="未知", public_release="unknown").save(projects / "unknown.json")
            Project(title="公开").save(projects / "public.json")
            plan = plan_public_build(stages=(), project_root=root)
        excluded = dict(plan.excluded_files)
        self.assertIn("resources/projects/secret.json", excluded)
        self.assertIn("resources/projects/unknown.json", excluded)
        self.assertIn("resources/projects/public.json", plan.included_files)

    def test_private_score_companion_variants_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scores = root / "resources" / "scores"
            scores.mkdir(parents=True)
            for name in ("secret.musicxml", "secret.mid", "secret.midi"):
                (scores / name).write_text("x", encoding="utf-8")
            stages = (
                _stage(
                    PracticeItem(
                        "私有", "", score="secret.musicxml", visibility="private"
                    )
                ),
            )
            plan = plan_public_build(stages=stages, project_root=root)
        excluded = dict(plan.excluded_files)
        for name in ("secret.musicxml", "secret.mid", "secret.midi"):
            with self.subTest(name=name):
                self.assertIn(f"resources/scores/{name}", excluded)
                self.assertNotIn(f"resources/scores/{name}", plan.included_files)

    def test_missing_referenced_asset_is_a_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "resources" / "scores").mkdir(parents=True)
            stages = (_stage(PracticeItem("缺谱", "", score="missing.musicxml")),)
            plan = plan_public_build(stages=stages, project_root=root)
        self.assertFalse(plan.ok)
        self.assertTrue(
            any("missing.musicxml" in problem for problem in plan.problems),
            plan.problems,
        )


class PackageAuditTest(unittest.TestCase):
    def test_audit_rejects_private_and_user_data_members(self) -> None:
        plan = plan_public_build()
        violations = audit_package(
            plan,
            (
                "PUBLIC_CONTENT.md",
                "resources/scores/xiaoxingxing.musicxml",
                "resources/scores/mariage_fragment.musicxml",
                "user-data/learning.json",
                "onboarding.json",
                "calibration.json",
                "mockups/p1_shell_studio.png",
                "../outside.txt",
            ),
        )
        joined = "\n".join(violations)
        self.assertIn("mariage_fragment.musicxml", joined)
        self.assertIn("user-data/learning.json", joined)
        self.assertIn("onboarding.json", joined)
        self.assertIn("calibration.json", joined)
        self.assertIn("mockups/p1_shell_studio.png", joined)
        self.assertIn("../outside.txt", joined)
        self.assertNotIn("xiaoxingxing", joined)

    def test_clean_members_pass(self) -> None:
        plan = plan_public_build()
        members = plan.included_files + ("PUBLIC_CONTENT.md", "public_exclusions.json")
        self.assertEqual(audit_package(plan, members), ())


class PublicArchiveTest(unittest.TestCase):
    def test_archive_contains_only_public_content_and_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public.zip"
            plan = build_public_archive(out, generated_at="2026-11-09")
            self.assertTrue(out.is_file())
            self.assertTrue(plan.ok)
            with zipfile.ZipFile(out) as archive:
                names = archive.namelist()
                exclusions = json.loads(archive.read("public_exclusions.json"))
                content = archive.read("PUBLIC_CONTENT.md").decode("utf-8")
        self.assertIn("resources/scores/xiaoxingxing.musicxml", names)
        self.assertIn("PUBLIC_CONTENT.md", names)
        self.assertNotIn("resources/scores/mariage_fragment.musicxml", names)
        self.assertNotIn("resources/scores/mariage_fragment.mid", names)
        self.assertEqual(audit_package(plan, names), ())
        self.assertEqual(exclusions["generated_at"], "2026-11-09")
        ids = [item["content_id"] for item in exclusions["items"]]
        self.assertIn("stage6:梦中的婚礼 · 片段", ids)
        self.assertIn("梦中的婚礼 · 片段", content)
        # The private score is untouched and still parses locally; a public
        # checkout omits it, in which case only the exclusion entry remains.
        private = SCORE_DIR / "mariage_fragment.musicxml"
        if private.is_file():
            score = parse_score(private)
            self.assertEqual(len(score.notes), 26)

    def test_failed_plan_writes_no_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "resources" / "scores").mkdir(parents=True)
            stages = (_stage(PracticeItem("缺谱", "", score="missing.musicxml")),)
            out = root / "public.zip"
            with self.assertRaises(PublicBuildError):
                build_public_archive(out, project_root=root, stages=stages)
            self.assertFalse(out.exists())


class BuildScriptTest(unittest.TestCase):
    def test_cli_writes_archive_and_returns_zero(self) -> None:
        sys.path.insert(0, str(ROOT / "tools"))
        from build_public import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public.zip"
            self.assertEqual(main([str(out)]), 0)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
