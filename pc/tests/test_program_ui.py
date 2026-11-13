"""Sound page offers the whole catalog, not a hand-written list (B9a-1)."""

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

from app.core.instrument import Instrument
from app.core.programs import CATALOG, index_for_gm
from app.core.project import Project
from app.core.synth_service import NullSynth
from app.ui.main_window import MainWindow
from app.ui.pages import SoundPage
from app.ui.theme import THEMES


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class SoundPageCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = Instrument(NullSynth())
        self.instrument._timer.stop()
        self.page = SoundPage(THEMES["studio"], self.instrument)

    def tearDown(self) -> None:
        self.page.close()
        self.page.deleteLater()
        self.instrument._timer.stop()
        self.instrument.deleteLater()

    def test_every_catalog_program_gets_a_chip(self) -> None:
        self.assertEqual(len(self.page._buttons), len(CATALOG))
        self.assertEqual(
            [button.text() for button in self.page._buttons],
            [program.label for program in CATALOG],
        )

    def visible_labels(self) -> list[str]:
        return [
            button.text()
            for button in self.page._buttons
            if not button.isHidden()
        ]

    def test_category_chip_filters_the_grid(self) -> None:
        from app.core.programs import CATEGORIES

        self.assertEqual(self.visible_labels(), [p.label for p in CATALOG])

        self.page.category_buttons["管乐"].click()
        self.assertEqual(
            self.visible_labels(),
            [p.label for p in CATALOG if p.category == "管乐"],
        )

        self.page.category_buttons["弦乐/合奏"].click()
        self.assertTrue(self.page.category_buttons["弦乐/合奏"].isChecked())
        self.assertFalse(self.page.category_buttons["管乐"].isChecked())

        self.page.category_buttons["全部"].click()
        self.assertEqual(self.visible_labels(), [p.label for p in CATALOG])
        self.assertEqual(len(self.page.category_buttons), len(CATEGORIES) + 1)

    def test_catalog_scrolls_when_it_does_not_fit(self) -> None:
        self.page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.page.resize(900, 500)
        self.page.show()
        wait(80)

        self.assertGreater(self.page.scroll.verticalScrollBar().maximum(), 0)
        self.assertIs(
            self.page.scroll.widget(), self.page._buttons[-1].parentWidget()
        )

    def test_search_filters_by_label_name_and_gm_number(self) -> None:
        self.page.search_edit.setText("萨克斯")
        labels = self.visible_labels()
        self.assertEqual(len(labels), 4)
        self.assertIn("中音萨克斯", labels)

        self.page.search_edit.setText("Alto")
        self.assertEqual(self.visible_labels(), ["中音萨克斯"])

        self.page.search_edit.setText("65")
        self.assertEqual(self.visible_labels(), ["中音萨克斯"])

        self.page.search_edit.setText("  ")
        self.assertEqual(self.visible_labels(), [p.label for p in CATALOG])

    def test_search_and_category_filter_together(self) -> None:
        self.page.category_buttons["弦乐/合奏"].click()
        self.page.search_edit.setText("sax")
        self.assertEqual(self.visible_labels(), [])

        self.page.category_buttons["管乐"].click()
        self.assertEqual(len(self.visible_labels()), 4)

        self.page.category_buttons["全部"].click()
        self.page.search_edit.setText("")
        self.assertEqual(self.visible_labels(), [p.label for p in CATALOG])

    def test_clicking_an_appended_program_selects_its_catalog_index(self) -> None:
        index = index_for_gm(65)
        self.assertIsNotNone(index)
        self.assertGreater(index, 6, "Alto Sax is an appended entry")

        self.page._buttons[index].click()

        self.assertEqual(self.instrument.program_index, index)
        self.assertEqual(self.instrument.synth_programs()[index][0], 65)
        self.page.refresh()
        self.assertTrue(self.page._buttons[index].isChecked())

    def test_selecting_a_filtered_program_still_updates_the_instrument(self) -> None:
        self.page.search_edit.setText("Alto")
        index = index_for_gm(65)

        self.page._buttons[index].click()
        self.page.refresh()

        self.assertEqual(self.instrument.program_index, index)
        self.assertTrue(self.page._buttons[index].isChecked())


class ProjectProgramFallbackTest(unittest.TestCase):
    """A project may name a GM program the catalog does not offer.

    It must still open, show piano (what the live instrument falls back to),
    and say once that the sound was substituted.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=self.root / "learning.json",
            bindings_path=self.root / "keybindings.json",
            prefs_path=self.root / "score_prefs.json",
            library_root=self.root / "scores",
            projects_root=self.root / "projects",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)
        self.page = self.window.compose_page

    def tearDown(self) -> None:
        self.window.close()
        wait(80)
        self.tmp.cleanup()

    def test_unlisted_program_opens_as_piano_with_a_notice(self) -> None:
        project = Project(title="导入项目")
        track = project.add_track()
        track.program = 127
        path = self.root / "imported.json"
        project.save(path)

        messages: list[str] = []
        self.page.message.connect(messages.append)

        self.assertTrue(self.page.load_project(path))
        self.assertIn("钢琴 1", self.page.track_rows[0].program_button.text())
        joined = "\n".join(messages)
        self.assertIn("127", joined)
        self.assertIn("钢琴 1", joined)


if __name__ == "__main__":
    unittest.main()
