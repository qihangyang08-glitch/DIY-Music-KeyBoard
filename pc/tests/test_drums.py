"""GM drum kits and the 32-key pad map (B9b, no Qt).

Bank 128 holds the GM drum kits and they play on MIDI channel 10 (index 9).
The pad map is fixed: key 1..32 -> GM percussion notes 35..66, so the light
bar can show real drum-part names instead of melody note names.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.drums import (
    DRUM_CHANNEL,
    DRUM_KITS,
    DRUM_PADS,
    drum_for_key,
    drum_label,
)
from app.core.synth_service import NullSynth


class DrumCatalogTest(unittest.TestCase):
    def test_kits_cover_the_eight_gm_bank_128_presets(self) -> None:
        self.assertEqual(DRUM_CHANNEL, 9)
        self.assertEqual(len(DRUM_KITS), 8)
        self.assertEqual(
            [kit.program for kit in DRUM_KITS],
            [0, 8, 16, 24, 25, 32, 40, 48],
        )
        for kit in DRUM_KITS:
            self.assertTrue(kit.name.strip(), kit.program)
            self.assertTrue(kit.label.strip(), kit.program)

    def test_pads_map_all_32_keys_to_distinct_gm_drums(self) -> None:
        self.assertEqual([pad.key for pad in DRUM_PADS], list(range(1, 33)))
        self.assertEqual([pad.midi for pad in DRUM_PADS], list(range(35, 67)))

        labels = [pad.label for pad in DRUM_PADS]
        self.assertEqual(len(labels), len(set(labels)))
        for pad in DRUM_PADS:
            self.assertTrue(pad.name.strip(), pad.key)
            self.assertTrue(pad.label.strip(), pad.key)

    def test_lookup_by_key_and_midi(self) -> None:
        self.assertEqual(drum_for_key(1).label, "低音鼓")
        self.assertEqual(drum_for_key(4).midi, 38)  # acoustic snare
        self.assertEqual(drum_for_key(32).midi, 66)
        self.assertIsNone(drum_for_key(0))
        self.assertIsNone(drum_for_key(33))

        self.assertEqual(drum_label(38), "军鼓")
        self.assertEqual(drum_label(42), "闭镲")
        self.assertIn("999", drum_label(999))


class RecordingSynth(NullSynth):
    """Silent synth that records notes and kit changes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.kits: list[int] = []

    def note_on(self, midi, velocity, channel=None) -> None:
        self.events.append(("on", channel, midi))

    def note_off(self, midi, channel=None) -> None:
        self.events.append(("off", channel, midi))

    def set_drum_kit(self, program: int) -> None:
        self.kits.append(program)


class DrumInstrumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from app.core.instrument import Instrument

        self.synth = RecordingSynth()
        self.instrument = Instrument(self.synth)
        self.instrument._timer.stop()
        # Deterministic note-offs: no 20 ms release grace in these ticks.
        self.instrument.engine.cfg.release_grace_ms = 0.0
        self.emitted: list = []
        self.instrument.events.connect(self.emitted.extend)

    def tearDown(self) -> None:
        self.instrument._timer.stop()

    def test_enabling_drums_selects_the_kit_and_names_pads(self) -> None:
        self.instrument.set_drums(True)

        self.assertTrue(self.instrument.drums_enabled)
        self.assertEqual(self.synth.kits, [0])
        self.assertEqual(self.instrument.note_for_key(1), "低音鼓")
        self.assertEqual(self.instrument.note_for_key(32), "低音天巴")
        self.assertTrue(self.instrument.key_enabled(1))
        self.assertEqual(self.instrument.display_midi(1), 35)
        self.assertEqual(self.instrument.drum_kit_label(), "标准鼓组")

    def test_pad_press_sounds_on_channel_9_without_learning_events(self) -> None:
        self.instrument.set_drums(True)
        self.instrument.press_key(4)
        self.instrument._tick()

        self.assertIn(("on", DRUM_CHANNEL, 38), self.synth.events)
        self.assertEqual(self.emitted, [], "drums are not melody events")

        self.instrument.release_key(4)
        self.instrument._tick()
        self.assertIn(("off", DRUM_CHANNEL, 38), self.synth.events)
        self.assertEqual(self.emitted, [])

    def test_kit_selection_wraps_and_applies_immediately(self) -> None:
        self.instrument.set_drums(True)
        self.instrument.set_drum_kit(4)

        self.assertEqual(self.synth.kits[-1], 25)
        self.assertEqual(self.instrument.drum_kit_label(), "TR-808 鼓组")

        self.instrument.set_drum_kit(len(DRUM_KITS))
        self.assertEqual(self.instrument.drum_kit_index, 0)
        self.assertEqual(self.synth.kits[-1], 0)

    def test_disabling_drums_restores_the_melody_mapping(self) -> None:
        self.instrument.set_drums(True)
        self.instrument.set_drums(False)

        self.assertFalse(self.instrument.drums_enabled)
        self.assertEqual(self.instrument.note_for_key(1), "F4")
        self.instrument.press_key(1)
        self.instrument._tick()
        self.assertEqual(self.synth.events[-1][1], None)
        self.assertTrue(self.emitted)


class DrumUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import tempfile

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        from app.ui.main_window import MainWindow

        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            projects_root=root / "projects",
            accessibility_path=root / "accessibility.json",
        )
        self.window.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen, True
        )
        self.window.resize(1120, 760)
        self.window.show()
        QApplication.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.window.instrument._timer.stop()
        self.tmp.cleanup()

    def test_sound_page_toggles_drums_and_selects_a_kit(self) -> None:
        page = self.window.sound_page
        self.assertEqual(len(page.kit_buttons), len(DRUM_KITS))

        page.drum_switch.setChecked(True)
        self.assertTrue(self.window.instrument.drums_enabled)
        self.assertTrue(page.drum_switch.isChecked())
        self.assertEqual(
            self.window.perform.next_value.text(), "鼓垫模式"
        )
        self.assertIn(
            "不参与判定", self.window.perform.follow_label.text()
        )
        self.assertIn("鼓垫", self.window.map_chip.text())
        self.assertTrue(self.window.perform.score.canvas._drums)

        page.kit_buttons[4].click()
        self.assertEqual(self.window.instrument.drum_kit_index, 4)
        self.assertEqual(
            self.window.perform.sound_value.text(), "TR-808 鼓组"
        )
        self.assertEqual(self.window.perform.map_name.text(), "鼓垫 · 32 键")

        page.drum_switch.setChecked(False)
        self.assertFalse(self.window.instrument.drums_enabled)
        self.assertEqual(
            self.window.perform.sound_value.text(), "钢琴 1"
        )
        self.assertNotEqual(
            self.window.perform.next_value.text(), "鼓垫模式"
        )
        self.assertIn("半音阶", self.window.map_chip.text())
        self.assertFalse(self.window.perform.score.canvas._drums)

    def test_light_bar_shows_drum_names_and_drum_colours(self) -> None:
        band = self.window.perform.band
        self.window.instrument.set_drums(True)

        self.assertEqual(band._note(1), "低音鼓")
        self.assertEqual(band._note(4), "军鼓")
        self.assertEqual(band._note(32), "低音天巴")
        self.assertEqual(band._midi(1), 35)
        self.assertEqual(band._midi(4), 38)

        self.window.instrument.set_drums(False)
        self.assertEqual(band._note(1), "F4")
        self.assertEqual(band._midi(1), 65)


class DrumSynthTest(unittest.TestCase):
    def test_drum_kit_selects_bank_128_on_channel_9(self) -> None:
        from app.core.synth_service import FluidSynthBackend

        class RecordingFS:
            def __init__(self) -> None:
                self.selects: list[tuple[int, int, int]] = []

            def program_select(self, channel, sfid, bank, program) -> None:
                self.selects.append((channel, bank, program))

        backend = object.__new__(FluidSynthBackend)
        backend.fs = RecordingFS()
        backend.sfid = 7

        backend.set_drum_kit(40)

        self.assertEqual(backend.fs.selects, [(DRUM_CHANNEL, 128, 40)])

    def test_silent_backend_accepts_a_kit(self) -> None:
        from app.core.synth_service import NullSynth

        NullSynth().set_drum_kit(24)  # must not raise


if __name__ == "__main__":
    unittest.main()
