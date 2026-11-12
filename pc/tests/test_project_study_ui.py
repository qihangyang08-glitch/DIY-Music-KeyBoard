"""End-to-end tests for stage-7 project hand-off (学习 → 创作 → 学习).

The learning page owns the content and the write-back; the creation page owns
the project. These tests drive the real MainWindow so the return chip, the
take lifecycle, and learning.json are all exercised together.
"""

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

from app.core.curriculum import stage_by_index
from app.core.note_engine import NoteEvent as RuntimeNoteEvent
from app.core.project import NoteEvent, Project
from app.ui.main_window import MainWindow


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


def runtime_event(kind: str, midi: int, t: float) -> RuntimeNoteEvent:
    return RuntimeNoteEvent(
        t=t, kind=kind, key=1, channel=1, midi=midi, velocity=100, note="M"
    )


def make_window(root: Path) -> MainWindow:
    window = MainWindow(
        serial_enabled=False,
        audio_enabled=False,
        progress_path=root / "learning.json",
        bindings_path=root / "keybindings.json",
        prefs_path=root / "score_prefs.json",
        library_root=root / "scores",
        projects_root=root / "projects",
    )
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 760)
    window.show()
    wait(160)
    return window


class ProjectStudyWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)
        self.stage = stage_by_index(7)

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_stage7(self) -> None:
        self.window._show_page(1)
        self.window.learning_page.open_stage(7)
        wait(100)

    def open_melody_project(self):
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[0]
        )
        wait(120)
        page = self.window.compose_page
        self.assertIs(self.window.stack.currentWidget(), page)
        return page

    def test_ready_project_opens_the_creation_page_with_steps(self) -> None:
        page = self.open_melody_project()

        self.assertTrue(self.window.study_return.isVisible())
        self.assertFalse(page.is_recording)
        self.assertEqual(page.session.project.title, "录一条旋律")
        self.assertTrue(page.learning_card.isVisible())
        self.assertFalse(page.templates_row.isEnabled())
        self.assertEqual(len(page._step_labels), 2)

        self.window._show_page(1)
        wait(60)
        buttons = [
            button.text()
            for button in self.window.learning_page.findChildren(QPushButton)
        ]
        self.assertIn("打开项目", buttons)

    def test_completing_melody_steps_records_the_result(self) -> None:
        page = self.open_melody_project()
        page.session.project.tracks[0].notes = [
            NoteEvent(0.0, 60, 1.0),
            NoteEvent(1.0, 62, 1.0),
            NoteEvent(2.0, 64, 1.0),
            NoteEvent(3.0, 65, 1.0),
        ]

        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "录一条旋律")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual((result.hits, result.total), (2, 2))
        self.assertTrue(page._step_labels[0].text().startswith("●"))
        self.assertTrue(page._step_labels[1].text().startswith("●"))

    def test_overdub_project_completes_with_two_tracks(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[1]
        )
        wait(120)
        page = self.window.compose_page
        self.assertEqual(len(page.session.project.tracks), 2)

        page.session.project.tracks[0].notes = [
            NoteEvent(0.0, 60, 1.0),
            NoteEvent(1.0, 62, 1.0),
            NoteEvent(2.0, 64, 1.0),
            NoteEvent(3.0, 65, 1.0),
        ]
        page.session.project.tracks[1].notes = [
            NoteEvent(0.0, 48, 1.0),
            NoteEvent(1.0, 50, 1.0),
        ]

        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "叠录低音")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_quantize_project_completes_from_the_roll_button(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[2]
        )
        wait(120)
        page = self.window.compose_page
        self.assertEqual(page.session.project.title, "量化开/关对比")

        page.quantize_button.click()
        wait(40)
        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "量化开/关对比")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertEqual(page.session.project.quantize_grid, 0.5)

    def test_count_in_project_completes_after_a_count_in_take(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[4]
        )
        wait(120)
        page = self.window.compose_page
        self.assertEqual(page.session.project.title, "预备拍 + 节拍器")

        page.count_in_button.click()
        page.start_recording(now=100.0)
        for index, midi in enumerate((60, 62, 64, 65)):
            at = 102.8 + index * 0.1
            page.note_event(runtime_event("on", midi, at))
            page.note_event(runtime_event("off", midi, at + 0.05))
        page.stop_recording(now=103.3)
        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "预备拍 + 节拍器")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_export_project_completes_after_a_midi_export(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[5]
        )
        wait(120)
        page = self.window.compose_page
        self.assertEqual(page.session.project.title, "导出 MIDI")

        page.export_button.click()
        wait(40)
        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "导出 MIDI")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_loop_project_completes_with_four_bars(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(
            self.stage, self.stage.trainings[3]
        )
        wait(120)
        page = self.window.compose_page

        page.set_loop(True, bars=4)
        page.session.project.tracks[0].notes = [
            NoteEvent(0.0, 60, 1.0),
            NoteEvent(1.0, 62, 1.0),
            NoteEvent(2.0, 64, 1.0),
            NoteEvent(3.0, 65, 1.0),
        ]

        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "循环 4 小节")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_saving_a_learning_project_does_not_overwrite_the_users_project(
        self,
    ) -> None:
        projects = self.root / "projects"
        projects.mkdir(parents=True, exist_ok=True)
        mine = Project(title="我的项目")
        mine.add_track("我的轨道").notes.append(NoteEvent(0.0, 72, 1.0))
        mine.save(projects / "project.json")

        page = self.open_melody_project()
        page.session.project.tracks[0].notes = [
            NoteEvent(0.0, 60, 1.0),
            NoteEvent(1.0, 62, 1.0),
            NoteEvent(2.0, 64, 1.0),
            NoteEvent(3.0, 65, 1.0),
        ]
        self.assertTrue(page.save_project())

        self.assertEqual(
            Project.load(projects / "project.json").title, "我的项目"
        )
        saved = Project.load(projects / "stage7_melody.json")
        self.assertEqual(
            [note.midi for note in saved.tracks[0].notes],
            [60, 62, 64, 65],
        )

    def test_incomplete_steps_do_not_record_a_result(self) -> None:
        page = self.open_melody_project()
        page.session.project.tracks[0].notes = [NoteEvent(0.0, 60, 1.0)]

        page.check_button.click()
        wait(60)

        self.assertIsNone(self.window.learning_progress.result_for(7, "录一条旋律"))
        self.assertIn("还差", self.window.toast.text())

    def test_return_chip_restores_stage7_in_the_learning_page(self) -> None:
        page = self.open_melody_project()

        self.window.study_return.click()
        wait(100)

        self.assertIs(self.window.stack.currentWidget(), self.window.learning_page)
        self.assertEqual(self.window.learning_page._view, "stage")
        self.assertEqual(self.window.learning_page._stage_index, 7)
        self.assertTrue(page.learning_card.isHidden())
        self.assertTrue(page.templates_row.isEnabled())
        self.assertFalse(self.window.study_return.isVisible())

    def open_stage8_training(self, index: int):
        stage = stage_by_index(8)
        self.window._show_page(1)
        self.window.learning_page.open_stage(8)
        wait(100)
        self.window.learning_page.practice(stage, stage.trainings[index])
        wait(120)
        page = self.window.compose_page
        self.assertIs(self.window.stack.currentWidget(), page)
        return page

    def test_reverb_project_completes_from_the_mixer_slider(self) -> None:
        page = self.open_stage8_training(4)
        self.assertEqual(page.session.project.title, "混响空间")

        page.reverb_slider.setValue(40)
        wait(40)
        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(8, "混响空间")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)

    def test_export_project_completes_after_a_midi_export(self) -> None:
        page = self.open_stage8_training(5)
        self.assertEqual(page.session.project.title, "导出项目")

        page.export_button.click()
        wait(40)
        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(8, "导出项目")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)
        self.assertTrue(page.session.project.exported)

    def test_trio_piece_completes_with_three_tracks(self) -> None:
        self.open_stage7()
        self.window.learning_page.practice(self.stage, self.stage.pieces[0])
        wait(120)
        page = self.window.compose_page
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertEqual(len(page.session.project.tracks), 3)

        for index, midi in enumerate((60, 48, 36)):
            page.session.project.tracks[index].notes = [
                NoteEvent(0.0, midi, 1.0),
                NoteEvent(1.0, midi + 2, 1.0),
            ]

        page.check_button.click()
        wait(60)

        result = self.window.learning_progress.result_for(7, "三轨小作品")
        self.assertIsNotNone(result)
        self.assertTrue(result.completed)


if __name__ == "__main__":
    unittest.main()
