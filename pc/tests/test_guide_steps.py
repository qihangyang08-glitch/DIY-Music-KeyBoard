"""Guide step checklists: per-lesson checkboxes persisted in learning.json."""

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
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from app.core.curriculum import stage_by_index
from app.core.progress import LearningProgress
from app.ui.main_window import MainWindow


class GuideStepProgressTest(unittest.TestCase):
    def test_steps_round_trip_and_uncheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning.json"
            progress = LearningProgress.load(path)
            progress.set_guide_step(0, "s0-l1", 0, True)
            progress.set_guide_step(0, "s0-l1", 2, True)
            progress.set_guide_step(0, "s0-l2", 1, True)
            self.assertEqual(
                progress.guide_steps_for(0, "s0-l1"), frozenset({0, 2})
            )
            self.assertEqual(
                progress.guide_steps_for(0, "s0-l2"), frozenset({1})
            )
            progress.set_guide_step(0, "s0-l1", 0, False)
            self.assertEqual(
                progress.guide_steps_for(0, "s0-l1"), frozenset({2})
            )
            reloaded = LearningProgress.load(path)
            self.assertEqual(
                reloaded.guide_steps_for(0, "s0-l1"), frozenset({2})
            )
            self.assertEqual(
                reloaded.guide_steps_for(0, "s0-l2"), frozenset({1})
            )

    def test_corrupt_steps_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 6,
                        "guide_steps": {
                            "0:s0-l1": [0, -1, "2", True, 2],
                            "bad": "not a list",
                            "1:s1-l1": [1],
                        },
                    }
                ),
                encoding="utf-8",
            )
            progress = LearningProgress.load(path)
        self.assertEqual(progress.guide_steps_for(0, "s0-l1"), frozenset({0, 2}))
        self.assertEqual(progress.guide_steps_for(1, "s1-l1"), frozenset({1}))
        self.assertEqual(progress.guide_steps_for(0, "bad"), frozenset())

    def test_reading_steps_does_not_create_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning.json"
            progress = LearningProgress.load(path)
            self.assertEqual(progress.guide_steps_for(0, "s0-l1"), frozenset())
            self.assertFalse(path.exists())


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class GuideStepUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.progress_path = self.root / "learning.json"
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=self.progress_path,
            bindings_path=self.root / "keybindings.json",
            prefs_path=self.root / "score_prefs.json",
            library_root=self.root / "scores",
            accessibility_path=self.root / "accessibility.json",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)
        self.window._show_page(1)
        wait(80)

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.tmp.cleanup()

    def open_lesson(self, stage_index: int, guide_index: int):
        page = self.window.learning_page
        page.open_stage(stage_index)
        wait(60)
        guide = stage_by_index(stage_index).guides[guide_index]
        self.assertTrue(page.open_course(guide.title))
        wait(60)
        return page, guide

    def checkboxes(self) -> list[QCheckBox]:
        return [
            box
            for box in self.window.learning_page._course_view.findChildren(QCheckBox)
            if box.isVisible()
        ]

    def texts(self) -> list[str]:
        return [
            label.text()
            for label in self.window.learning_page._course_view.findChildren(QLabel)
        ]

    def test_checking_a_step_persists_and_updates_progress(self) -> None:
        _, guide = self.open_lesson(0, 0)
        boxes = self.checkboxes()
        self.assertEqual(len(boxes), len(guide.steps))
        self.assertFalse(boxes[0].isChecked())
        boxes[0].click()
        wait(40)
        self.assertTrue(boxes[0].isChecked())
        self.assertTrue(boxes[0].text().startswith("✓ "))
        self.assertIn("已勾选 1/3", self.texts())
        self.assertEqual(
            self.window.learning_progress.guide_steps_for(0, guide.lesson_id),
            frozenset({0}),
        )
        reloaded = LearningProgress.load(self.progress_path)
        self.assertEqual(
            reloaded.guide_steps_for(0, guide.lesson_id), frozenset({0})
        )

    def test_reopening_restores_checks_and_uncheck_clears_them(self) -> None:
        page, guide = self.open_lesson(0, 0)
        self.checkboxes()[1].click()
        wait(40)
        page.open_stage(0)
        wait(60)
        self.assertTrue(page.open_course(guide.title))
        wait(60)
        boxes = self.checkboxes()
        self.assertTrue(boxes[1].isChecked())
        self.assertFalse(boxes[0].isChecked())
        boxes[1].click()
        wait(40)
        self.assertFalse(boxes[1].isChecked())
        self.assertFalse(boxes[1].text().startswith("✓ "))
        self.assertEqual(
            self.window.learning_progress.guide_steps_for(0, guide.lesson_id),
            frozenset(),
        )
        self.assertIn("已勾选 0/3", self.texts())

    def test_steps_are_isolated_per_lesson(self) -> None:
        page, first = self.open_lesson(0, 0)
        self.checkboxes()[0].click()
        wait(40)
        page.open_stage(0)
        wait(60)
        second = stage_by_index(0).guides[1]
        self.assertTrue(page.open_course(second.title))
        wait(60)
        self.assertFalse(any(box.isChecked() for box in self.checkboxes()))
        self.assertIn("已勾选 0/3", self.texts())
        self.assertGreater(first.lesson_id, "")
        self.assertNotEqual(first.lesson_id, second.lesson_id)

    def test_checkbox_style_is_defined(self) -> None:
        qss = self.window.styleSheet()
        self.assertIn("QCheckBox::indicator:checked", qss)


if __name__ == "__main__":
    unittest.main()
