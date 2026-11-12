"""CONTENT_SCHEMA §6.1 structured mapping: parse, clamp, convert."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.mapping import (
    MappingSpec,
    PRESET_BY_KEY,
    mapping_spec,
    split_mapping,
    with_split_bar,
)


class MappingSpecParseTest(unittest.TestCase):
    def test_plain_preset_key_stays_a_key(self) -> None:
        self.assertEqual(mapping_spec("split"), "split")
        self.assertIsNone(mapping_spec("not-a-preset"))

    def test_custom_base_and_steps_parse(self) -> None:
        spec = mapping_spec(
            {
                "preset": "custom",
                "base": 60,
                "steps": [0, 2, 4, 5, 7, 9, 11],
                "octave": 1,
                "transpose": 2,
            }
        )
        self.assertIsInstance(spec, MappingSpec)
        self.assertEqual(spec.base, 60)
        self.assertEqual(spec.steps, (0, 2, 4, 5, 7, 9, 11))
        self.assertEqual((spec.octave, spec.transpose), (1, 2))

        preset = spec.to_preset()
        self.assertEqual(preset.key, "content")
        self.assertEqual(preset.midi_for_key(1), 60)
        self.assertEqual(preset.midi_for_key(8), 72)

    def test_split_mapping_parses_both_sides(self) -> None:
        spec = mapping_spec(
            {
                "split": {
                    "bar": 20,
                    "left": {"base": 48, "steps": list(range(12))},
                    "right": {"base": 72, "steps": list(range(12))},
                }
            }
        )
        self.assertIsNotNone(spec.split)
        self.assertEqual(spec.split.bar, 20)
        preset = spec.to_preset()
        self.assertEqual(preset.midi_for_key(1), 48)
        self.assertEqual(preset.midi_for_key(20), 67)
        self.assertEqual(preset.midi_for_key(21), 72)
        self.assertEqual(preset.range_label(0), "C3–G4 + C5–B5")

    def test_bad_values_are_clamped_or_ignored(self) -> None:
        spec = mapping_spec(
            {
                "base": 999,
                "steps": "not-a-list",
                "octave": 99,
                "transpose": -99,
                "split": {"bar": 0},
            }
        )
        self.assertEqual(spec.base, 127)
        self.assertEqual(spec.steps, tuple(range(12)))
        self.assertEqual((spec.octave, spec.transpose), (2, -12))
        self.assertIsNone(spec.split)

    def test_booleans_are_not_numbers(self) -> None:
        spec = mapping_spec({"base": True, "octave": False, "steps": [True]})
        self.assertEqual(spec.base, 60)
        self.assertEqual(spec.octave, 0)
        self.assertEqual(spec.steps, tuple(range(12)))

    def test_unknown_dict_without_mapping_fields_is_rejected(self) -> None:
        self.assertIsNone(mapping_spec({"label": "空"}))
        self.assertIsNone(mapping_spec(42))
        self.assertIsNone(mapping_spec(None))

    def test_out_of_range_keys_reports_unplayable_slots(self) -> None:
        spec = MappingSpec(base=110, steps=tuple(range(12)), octave=1)
        keys = spec.out_of_range_keys()
        self.assertIn(7, keys)   # 110 + 6 + 12 = 128
        self.assertNotIn(1, keys)  # 122

    def test_split_bar_can_move_and_is_clamped(self) -> None:
        preset = PRESET_BY_KEY["split"]
        moved = with_split_bar(preset, 20)
        self.assertEqual(moved.split.bar, 20)
        self.assertEqual(moved.midi_for_key(20), 67)
        self.assertEqual(moved.midi_for_key(21), 72)
        self.assertEqual(with_split_bar(preset, 0).split.bar, 1)
        self.assertEqual(with_split_bar(preset, 99).split.bar, 31)
        self.assertIs(
            with_split_bar(PRESET_BY_KEY["chromatic"], 10),
            PRESET_BY_KEY["chromatic"],
        )

    def test_split_helper_matches_the_builtin_split_preset(self) -> None:
        spec = split_mapping(16, 48, 72, label="左右分区")
        preset = spec.to_preset()
        builtin = PRESET_BY_KEY["split"]
        for key in range(1, 33):
            self.assertEqual(preset.midi_for_key(key), builtin.midi_for_key(key))
        self.assertEqual(preset.range_label(0), builtin.range_label(0))
        self.assertEqual(preset.label_cn, "左右分区")


if __name__ == "__main__":
    unittest.main()
