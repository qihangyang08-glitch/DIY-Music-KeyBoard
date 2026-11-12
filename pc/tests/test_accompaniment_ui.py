"""MainWindow hand-off for a right-hand practice item with auto left hand."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.curriculum import SCORE_DIR, stage_by_index
from app.ui.main_window import MainWindow

ITEM_NAME = "小星星 · 自动左手"


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


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


class AccompanimentStudyWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = make_window(self.root)
        self.stage = stage_by_index(5)
        self.item = next(
            item for item in self.stage.trainings if item.name == ITEM_NAME
        )

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def open_item(self):
        self.window._show_page(1)
        self.window.learning_page.open_stage(5)
        wait(100)
        self.window.learning_page.practice(self.stage, self.item)
        wait(120)
        return self.window.follow

    def test_study_practice_loads_only_the_right_hand(self) -> None:
        follow = self.open_item()

        self.assertTrue(self.window._study_active)
        self.assertEqual(follow.score.title, ITEM_NAME)
        self.assertEqual(len(follow.score.notes), 42)
        self.assertTrue(all(note.part == "P1" for note in follow.score.notes))
        self.assertEqual(len(follow.accompaniment), 24)
        self.assertTrue(
            all(note.part == "P2" for note in follow.accompaniment)
        )

    def test_a_plain_library_load_plays_the_whole_score(self) -> None:
        path = SCORE_DIR / "twinkle_auto_accompaniment.musicxml"
        self.window._load_score_file(str(path), announce=False)

        follow = self.window.follow
        self.assertEqual(len(follow.score.notes), 66)
        self.assertEqual(follow.accompaniment, ())

    def test_mapping_is_untouched_by_auto_accompaniment(self) -> None:
        instrument = self.window.instrument
        before = (
            instrument.current_preset.key,
            instrument.octave,
            instrument.transpose,
        )

        follow = self.open_item()
        for note in list(follow.score.notes):
            follow.note_on(instrument.bar_for_midi(note.midi))
        self.window._return_to_study()
        wait(60)

        self.assertEqual(
            (
                instrument.current_preset.key,
                instrument.octave,
                instrument.transpose,
            ),
            before,
        )

    def test_completing_the_right_hand_records_42_notes(self) -> None:
        follow = self.open_item()
        for note in list(follow.score.notes):
            bar = self.window.instrument.bar_for_midi(note.midi)
            self.assertIsNotNone(bar)
            follow.note_on(bar)

        self.assertEqual((follow.hits, follow.misses), (42, 0))
        self.window._return_to_study()
        wait(80)

        result = self.window.learning_progress.result_for(5, ITEM_NAME)
        self.assertIsNotNone(result)
        self.assertEqual((result.hits, result.total), (42, 42))
        self.assertTrue(result.completed)
        self.assertFalse(self.window._study_active)


if __name__ == "__main__":
    unittest.main()
