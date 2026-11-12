"""Content tests for the four creation templates (no Qt)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import CREATION_TEMPLATES, project_path
from app.core.project import Project


class CreationTemplateTest(unittest.TestCase):
    def test_every_template_loads_with_a_real_track(self) -> None:
        for template in CREATION_TEMPLATES:
            path = project_path(template.project)
            self.assertIsNotNone(path, template.name)
            project = Project.load(path)
            self.assertTrue(project.tracks, template.name)
            self.assertGreater(project.tempo, 0, template.name)
            for track in project.tracks:
                self.assertGreater(track.volume, 0.0, template.name)
                self.assertEqual(track.notes, [], template.name)

    def test_bass_template_has_two_voices_and_pan(self) -> None:
        project = Project.load(project_path("template_bass_piano"))

        self.assertEqual(project.title, "左手贝斯 + 右手钢琴")
        self.assertEqual([track.program for track in project.tracks], [32, 0])
        self.assertLess(project.tracks[0].pan, 0)
        self.assertGreater(project.tracks[1].pan, 0)


if __name__ == "__main__":
    unittest.main()
