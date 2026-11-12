"""Disabled physical keys: a white-key preset must stay silent and unmapped."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.core.instrument import Instrument
from app.core.mapping import PRESETS
from app.core.note_engine import Frame, NoteEngine, is_black_key
from app.core.synth_service import NullSynth


def white_keymap() -> dict[int, dict]:
    return {
        1: {"key": 1, "channel": 1, "midi": 60, "note": "C4", "disabled": False},
        2: {"key": 2, "channel": 2, "midi": 62, "note": "D4", "disabled": False},
        20: {
            "key": 20,
            "channel": 20,
            "midi": 93,
            "note": "A6",
            "disabled": True,
        },
    }


class BlackKeyTest(unittest.TestCase):
    def test_black_key_pitch_classes(self) -> None:
        for midi in (61, 63, 66, 68, 70):  # C# D# F# G# A#
            self.assertTrue(is_black_key(midi))
        for midi in (60, 62, 64, 65, 67, 69, 71):  # C D E F G A B
            self.assertFalse(is_black_key(midi))


class DisabledKeyEnginetest(unittest.TestCase):
    def test_disabled_channel_emits_no_note(self) -> None:
        engine = NoteEngine(white_keymap())
        events = engine.update(Frame(t=0.0, active={1, 20}))

        self.assertEqual([event.midi for event in events], [60])
        self.assertEqual(engine.polyphony(), 1)

    def test_disabled_channel_is_silent_across_offset(self) -> None:
        engine = NoteEngine(white_keymap())
        engine.set_octave(2)
        engine.set_transpose(12)
        events = engine.update(Frame(t=0.0, active={20}))

        self.assertEqual(events, [])
        self.assertEqual(engine.skipped, 0)


class DisabledKeyInstrumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.instrument = Instrument(NullSynth())
        index = next(
            index
            for index, preset in enumerate(PRESETS)
            if preset.key == "white19"
        )
        self.instrument.set_preset(index)

    def tearDown(self) -> None:
        self.instrument._timer.stop()

    def test_notes_in_the_enabled_half_are_playable(self) -> None:
        self.assertEqual(self.instrument.note_for_key(1), "C4")
        self.assertEqual(self.instrument.note_for_key(19), "G6")
        self.assertEqual(self.instrument.bar_for_midi(91), 19)

    def test_disabled_slots_are_not_reachable(self) -> None:
        self.assertEqual(self.instrument.note_for_key(20), "—")
        self.assertFalse(self.instrument.key_enabled(20))
        self.assertTrue(self.instrument.key_enabled(19))
        self.assertIsNone(self.instrument.bar_for_midi(93))  # only bar 20
        self.assertIsNone(self.instrument.bar_for_midi(61))  # black key

    def test_disabled_key_press_does_not_sound(self) -> None:
        events = self.instrument.engine.update(Frame(t=0.0, active={20}))
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
