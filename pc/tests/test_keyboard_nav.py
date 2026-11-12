"""Keyboard reachability: Tab traversal, nav/settings activation, focus rings."""

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
from PySide6.QtWidgets import QApplication, QPushButton

from app.ui.keybindings import MOD_CTRL, KeyBindings
from app.ui.learning_page import ClickFrame, StageCard
from app.ui.main_window import MainWindow

TAB = int(Qt.Key.Key_Tab)
CTRL = MOD_CTRL


class KeyBindingTabMigrationTest(unittest.TestCase):
    def test_defaults_use_ctrl_tab_for_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindings = KeyBindings(Path(tmp) / "keybindings.json")
        labels = bindings.function_chord("labels")
        self.assertIsNotNone(labels)
        self.assertEqual(labels.key, TAB)
        self.assertEqual(labels.mods, CTRL)
        self.assertEqual(labels.text, "Ctrl+Tab")

    def test_version_one_tab_migrates_to_ctrl_tab(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keybindings.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "functions": {"labels": {"key": TAB, "mods": 0}},
                    }
                ),
                encoding="utf-8",
            )
            bindings = KeyBindings(path)
        labels = bindings.function_chord("labels")
        self.assertEqual((labels.key, labels.mods), (TAB, CTRL))

    def test_version_two_explicit_tab_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keybindings.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "functions": {"labels": {"key": TAB, "mods": 0}},
                    }
                ),
                encoding="utf-8",
            )
            bindings = KeyBindings(path)
        labels = bindings.function_chord("labels")
        self.assertEqual((labels.key, labels.mods), (TAB, 0))


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class KeyboardNavigationUiTest(unittest.TestCase):
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
            accessibility_path=self.root / "accessibility.json",
        )
        self.window.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)
        self.activate()

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.tmp.cleanup()

    def activate(self) -> None:
        self.window.activateWindow()
        QApplication.setActiveWindow(self.window)
        self.window.setFocus()
        wait(40)

    def test_tab_moves_focus_without_toggling_labels(self) -> None:
        nav = self.window.nav_buttons[0]
        nav.setFocus()
        wait(20)
        self.assertIs(QApplication.focusWidget(), nav)
        QTest.keyClick(nav, Qt.Key.Key_Tab)
        wait(30)
        self.assertIsNot(QApplication.focusWidget(), nav)
        self.assertFalse(self.window.perform.band.labels_on)

    def test_ctrl_tab_still_toggles_labels_on_perform(self) -> None:
        self.window._show_page(0)
        wait(30)
        QTest.keyClick(
            self.window,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.ControlModifier,
        )
        wait(30)
        self.assertTrue(self.window.perform.band.labels_on)

    def test_nav_arrow_home_end_move_focus(self) -> None:
        nav = self.window.nav_buttons
        nav[0].setFocus()
        wait(20)
        QTest.keyClick(nav[0], Qt.Key.Key_Down)
        self.assertIs(QApplication.focusWidget(), nav[1])
        QTest.keyClick(nav[1], Qt.Key.Key_End)
        self.assertIs(QApplication.focusWidget(), nav[5])
        QTest.keyClick(nav[5], Qt.Key.Key_Home)
        self.assertIs(QApplication.focusWidget(), nav[0])
        QTest.keyClick(nav[0], Qt.Key.Key_Up)
        self.assertIs(QApplication.focusWidget(), nav[5])

    def test_return_activates_focused_nav_button(self) -> None:
        nav = self.window.nav_buttons[5]
        nav.setFocus()
        wait(20)
        QTest.keyClick(nav, Qt.Key.Key_Return)
        wait(30)
        self.assertIs(self.window.stack.currentWidget(), self.window.settings_page)

    def test_space_activates_button_instead_of_starting_playback(self) -> None:
        self.window._show_page(0)
        wait(30)
        nav = self.window.nav_buttons[5]
        nav.setFocus()
        wait(20)
        QTest.keyClick(nav, Qt.Key.Key_Space)
        wait(30)
        self.assertIs(self.window.stack.currentWidget(), self.window.settings_page)
        self.assertFalse(self.window.follow.playing)

    def test_settings_chips_are_focusable_and_arrow_navigable(self) -> None:
        self.window._show_page(5)
        wait(30)
        chips = list(self.window.settings_page._theme_buttons.values())
        for button in chips:
            self.assertEqual(
                button.focusPolicy(), Qt.FocusPolicy.StrongFocus
            )
        chips[0].setFocus()
        wait(20)
        QTest.keyClick(chips[0], Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), chips[1])
        QTest.keyClick(chips[1], Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), chips[0])

    def test_settings_chip_activates_with_return_and_space(self) -> None:
        self.window._show_page(5)
        wait(30)
        chips = self.window.settings_page._theme_buttons
        chips["stage"].setFocus()
        wait(20)
        QTest.keyClick(chips["stage"], Qt.Key.Key_Return)
        wait(30)
        self.assertEqual(self.window.theme.name, "stage")
        chips["studio"].setFocus()
        wait(20)
        QTest.keyClick(chips["studio"], Qt.Key.Key_Space)
        wait(30)
        self.assertEqual(self.window.theme.name, "studio")

    def test_settings_toggle_is_focusable_and_activatable(self) -> None:
        self.window._show_page(5)
        wait(30)
        switch = self.window.settings_page.reduce_motion_switch
        self.assertEqual(switch.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        switch.setFocus()
        wait(20)
        QTest.keyClick(switch, Qt.Key.Key_Space)
        wait(30)
        self.assertTrue(self.window.accessibility.reduce_motion)
        QTest.keyClick(switch, Qt.Key.Key_Return)
        wait(30)
        self.assertFalse(self.window.accessibility.reduce_motion)

    def test_creation_transport_is_keyboard_activatable(self) -> None:
        self.window._show_page(3)
        wait(80)
        page = self.window.compose_page
        page.add_track()
        page.editor.add_note(0.0, 60, 4.0)
        play = page.play_button
        self.assertEqual(play.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        play.setFocus()
        wait(20)
        QTest.keyClick(play, Qt.Key.Key_Space)
        wait(100)
        self.assertTrue(page.is_playing)
        QTest.keyClick(play, Qt.Key.Key_Return)
        wait(60)
        self.assertFalse(page.is_playing)

    def test_sound_and_device_controls_are_focusable(self) -> None:
        for button in self.window.sound_page._buttons:
            self.assertEqual(
                button.focusPolicy(), Qt.FocusPolicy.StrongFocus
            )
        self.assertEqual(
            self.window.sound_page.mute_switch.focusPolicy(),
            Qt.FocusPolicy.StrongFocus,
        )
        self.assertEqual(
            self.window.device_page.calibration_button.focusPolicy(),
            Qt.FocusPolicy.StrongFocus,
        )

    def test_focus_styles_are_defined(self) -> None:
        qss = self.window.styleSheet()
        self.assertIn('QPushButton[role="nav"]:focus', qss)
        self.assertIn('QPushButton[role="chip"]:focus', qss)

    def test_track_row_controls_are_focusable(self) -> None:
        page = self.window.compose_page
        page.add_track()
        row = page.track_rows[0]
        for name in (
            "select_button",
            "program_button",
            "volume_down",
            "volume_up",
            "pan_slider",
            "layer_button",
            "split_button",
            "mute_button",
            "solo_button",
        ):
            control = getattr(row, name)
            self.assertEqual(
                control.focusPolicy(),
                Qt.FocusPolicy.StrongFocus,
                f"{name} must be reachable with Tab",
            )

    def test_track_row_controls_activate_with_enter_and_space(self) -> None:
        page = self.window.compose_page
        self.window._show_page(3)
        wait(80)
        page.add_track()
        row = page.track_rows[0]

        row.mute_button.setFocus()
        wait(20)
        QTest.keyClick(row.mute_button, Qt.Key.Key_Return)
        wait(30)
        self.assertTrue(page.session.project.tracks[0].mute)

        QTest.keyClick(row.mute_button, Qt.Key.Key_Space)
        wait(30)
        self.assertFalse(page.session.project.tracks[0].mute)

        before = page.session.project.tracks[0].volume
        row.volume_down.setFocus()
        wait(20)
        QTest.keyClick(row.volume_down, Qt.Key.Key_Return)
        wait(30)
        self.assertLess(page.session.project.tracks[0].volume, before)

    def test_track_row_arrow_keys_cycle_focus(self) -> None:
        page = self.window.compose_page
        self.window._show_page(3)
        wait(80)
        page.add_track()
        row = page.track_rows[0]

        row.select_button.setFocus()
        wait(20)
        QTest.keyClick(row.select_button, Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), row.program_button)
        QTest.keyClick(row.program_button, Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), row.volume_down)
        QTest.keyClick(row.volume_down, Qt.Key.Key_Left)
        self.assertIs(QApplication.focusWidget(), row.program_button)

        row.solo_button.setFocus()
        wait(20)
        QTest.keyClick(row.solo_button, Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), row.select_button)
        QTest.keyClick(row.select_button, Qt.Key.Key_Left)
        self.assertIs(QApplication.focusWidget(), row.solo_button)

    def test_track_row_pan_slider_keeps_arrows_and_leaves_with_up_down(self) -> None:
        page = self.window.compose_page
        self.window._show_page(3)
        wait(80)
        page.add_track()
        row = page.track_rows[0]
        row.pan_slider.setFocus()
        wait(20)
        before = row.pan_slider.value()
        QTest.keyClick(row.pan_slider, Qt.Key.Key_Right)
        wait(20)
        self.assertIs(QApplication.focusWidget(), row.pan_slider)
        self.assertGreater(row.pan_slider.value(), before)
        QTest.keyClick(row.pan_slider, Qt.Key.Key_Down)
        self.assertIs(QApplication.focusWidget(), row.layer_button)

    def test_keybinding_capture_buttons_are_focusable_and_start_capture(self) -> None:
        page = self.window.keybindings_page
        self.window._show_subpage(page, 5)
        wait(60)

        edit = page.note_edit_buttons[1]
        self.assertEqual(edit.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        edit.setFocus()
        wait(20)
        QTest.keyClick(edit, Qt.Key.Key_Return)
        wait(30)
        self.assertTrue(page.is_capturing())
        self.assertIn("光条 1", page.status.text())

        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        wait(30)
        self.assertFalse(page.is_capturing())

        function_edit = page.function_edit_buttons["sustain"]
        function_edit.setFocus()
        wait(20)
        QTest.keyClick(function_edit, Qt.Key.Key_Space)
        wait(30)
        self.assertTrue(page.is_capturing())
        self.assertIn("延音", page.status.text())

    def test_keybinding_tabs_are_focusable_and_arrow_navigable(self) -> None:
        page = self.window.keybindings_page
        self.window._show_subpage(page, 5)
        wait(60)
        tabs = page._tab_buttons
        for tab in tabs:
            self.assertEqual(tab.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        tabs[0].setFocus()
        wait(20)
        QTest.keyClick(tabs[0], Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), tabs[1])
        QTest.keyClick(tabs[1], Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), tabs[0])

        tabs[1].setFocus()
        wait(20)
        QTest.keyClick(tabs[1], Qt.Key.Key_Return)
        wait(20)
        self.assertEqual(page._stack.currentIndex(), 1)
        tabs[0].setFocus()
        wait(20)
        QTest.keyClick(tabs[0], Qt.Key.Key_Space)
        wait(20)
        self.assertEqual(page._stack.currentIndex(), 0)

    def test_learning_stage_cards_focus_and_open_with_enter(self) -> None:
        page = self.window.learning_page
        self.window._show_page(1)
        wait(80)
        cards = [
            card
            for card in page._overview.findChildren(StageCard)
            if card.isVisible()
        ]
        card = next(card for card in cards if card.stage.index == 0)
        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        card.setFocus()
        wait(20)
        QTest.keyClick(card, Qt.Key.Key_Return)
        wait(40)
        self.assertEqual(page._view, "stage")
        self.assertEqual(page._stage_index, 0)

    def test_learning_stage_card_space_opens_stage(self) -> None:
        page = self.window.learning_page
        self.window._show_page(1)
        wait(80)
        cards = [
            card
            for card in page._overview.findChildren(StageCard)
            if card.isVisible()
        ]
        card = next(card for card in cards if card.stage.index == 3)
        card.setFocus()
        wait(20)
        QTest.keyClick(card, Qt.Key.Key_Space)
        wait(40)
        self.assertEqual(page._view, "stage")
        self.assertEqual(page._stage_index, 3)

    def test_learning_guide_cards_open_course_with_enter(self) -> None:
        page = self.window.learning_page
        self.window._show_page(1)
        wait(80)
        page.open_stage(0)
        wait(60)
        guides = [
            widget
            for widget in page._stage_view.findChildren(ClickFrame)
            if widget.isVisible()
        ]
        self.assertTrue(guides)
        guide = guides[0]
        guide_title = page._stage_view._stage.guides[0].title
        self.assertEqual(guide.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        guide.setFocus()
        wait(20)
        QTest.keyClick(guide, Qt.Key.Key_Return)
        wait(40)
        self.assertEqual(page._view, "course")
        self.assertEqual(page._guide_title, guide_title)

    def test_learning_action_buttons_are_focusable(self) -> None:
        page = self.window.learning_page

        def check(view) -> int:
            buttons = [
                button
                for button in view.findChildren(QPushButton)
                if button.isVisible()
            ]
            for button in buttons:
                self.assertEqual(
                    button.focusPolicy(),
                    Qt.FocusPolicy.StrongFocus,
                    button.text(),
                )
            return len(buttons)

        self.window._show_page(1)
        wait(80)
        checked = check(page._overview)
        page.open_stage(0)
        wait(60)
        checked += check(page._stage_view)
        page.open_course(page._stage_view._stage.guides[0].title)
        wait(60)
        checked += check(page._course_view)
        self.assertGreater(checked, 3)

    def test_card_focus_style_is_defined(self) -> None:
        qss = self.window.styleSheet()
        self.assertIn('QFrame[card="true"]:focus', qss)


if __name__ == "__main__":
    unittest.main()
