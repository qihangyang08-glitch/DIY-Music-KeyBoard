"""Pure tests for the 32-key mapping presets.

A mapping preset answers one question: which MIDI note does each physical bar
play? These tests stay on that public interface and never inspect how the
mapping is stored internally.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.mapping import (
    MapPreset,
    PRESET_BY_KEY,
    SplitMap,
    apply_preset,
)


class WhiteKeyPresetTest(unittest.TestCase):
    def test_white_preset_maps_nineteen_keys_and_disables_the_rest(self) -> None:
        preset = PRESET_BY_KEY["white19"]
        self.assertEqual(
            [preset.midi_for_key(key) for key in range(1, 20)],
            [
                60, 62, 64, 65, 67, 69, 71,   # C4–B4
                72, 74, 76, 77, 79, 81, 83,   # C5–B5
                84, 86, 88, 89, 91,           # C6–G6
            ],
        )
        self.assertTrue(all(preset.is_enabled(key) for key in range(1, 20)))
        self.assertTrue(
            all(not preset.is_enabled(key) for key in range(20, 33))
        )

    def test_white_preset_range_excludes_disabled_slots(self) -> None:
        preset = PRESET_BY_KEY["white19"]
        self.assertEqual(preset.key_range(), (60, 91))
        self.assertEqual(preset.range_label(0), "C4–G6")
        self.assertEqual(preset.enabled_keys(), tuple(range(1, 20)))

    def test_apply_preset_writes_the_disabled_flag(self) -> None:
        keymap = {
            key: {"key": key, "channel": key, "midi": 0, "note": ""}
            for key in range(1, 33)
        }
        apply_preset(keymap, PRESET_BY_KEY["white19"])

        self.assertFalse(keymap[1]["disabled"])
        self.assertFalse(keymap[19]["disabled"])
        self.assertTrue(keymap[20]["disabled"])
        self.assertTrue(keymap[32]["disabled"])


class SplitPresetTest(unittest.TestCase):
    def test_split_preset_maps_low_and_high_halves(self) -> None:
        preset = PRESET_BY_KEY["split"]
        self.assertEqual(preset.midi_for_key(1), 48)   # C3
        self.assertEqual(preset.midi_for_key(16), 63)  # D#4
        self.assertEqual(preset.midi_for_key(17), 72)  # C5
        self.assertEqual(preset.midi_for_key(32), 87)  # D#6

    def test_split_range_label_reports_both_registers(self) -> None:
        preset = PRESET_BY_KEY["split"]
        self.assertEqual(preset.range_label(0), "C3–D#4 + C5–D#6")
        self.assertEqual(preset.range_label(-12), "C2–D#3 + C4–D#5")

    def test_split_range_label_uses_real_side_extremes(self) -> None:
        # Custom steps need not be ascending. Key 1 is B3 and key 32 is D7,
        # but the left side really runs C3–B5 and the right C5–D7.
        preset = MapPreset(
            key="descending",
            label="Descending",
            label_cn="下行测试",
            note="",
            base=48,
            steps=(11, 9, 7, 5, 4, 2, 0),
            split=SplitMap(
                bar=16,
                left_base=48,
                left_steps=(11, 9, 7, 5, 4, 2, 0),
                right_base=72,
                right_steps=(0, 2, 4, 5, 7, 9, 11),
            ),
        )
        self.assertEqual(preset.range_label(0), "C3–B5 + C5–D7")


if __name__ == "__main__":
    unittest.main()
