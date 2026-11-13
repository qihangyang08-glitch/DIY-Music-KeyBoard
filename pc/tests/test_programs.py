"""Behaviour tests for the GM program catalog (B9a-1).

The catalog is the single source of truth for what the sound page offers and
for the Chinese labels the rest of the UI shows. These tests are deliberately
free of Qt: the page wiring is covered separately.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.programs import (
    CATALOG,
    CATEGORIES,
    fallback_notice,
    index_for_gm,
    label_for_gm,
    program_for_gm,
    resolve_gm,
)

# The seven sounds P1 shipped, in their original index order. Saved settings
# and the live instrument use list indices, so these must stay at the head.
LEGACY = (
    (0, "Piano 1"),
    (4, "E.Piano 1"),
    (16, "Drawbar Organ"),
    (24, "Nylon Guitar"),
    (48, "Strings 1"),
    (80, "Square Lead"),
    (32, "Acoustic Bass"),
)


class CatalogTest(unittest.TestCase):
    def test_catalog_is_a_complete_unique_gm_listing(self) -> None:
        self.assertGreaterEqual(len(CATALOG), 30)
        gms = [program.gm for program in CATALOG]
        self.assertEqual(len(gms), len(set(gms)), "GM numbers must be unique")

        for program in CATALOG:
            self.assertGreaterEqual(program.gm, 0)
            self.assertLessEqual(program.gm, 127)
            self.assertTrue(program.name.strip(), program.gm)
            self.assertTrue(program.label.strip(), program.gm)
            self.assertIn(program.category, CATEGORIES)

        for category in CATEGORIES:
            self.assertTrue(
                any(program.category == category for program in CATALOG),
                f"empty category: {category}",
            )

    def test_first_seven_entries_keep_the_legacy_index_order(self) -> None:
        self.assertEqual(
            tuple((program.gm, program.name) for program in CATALOG[:7]),
            LEGACY,
        )

    def test_lookup_finds_programs_by_gm_number(self) -> None:
        alto = program_for_gm(65)
        self.assertIsNotNone(alto)
        self.assertEqual(alto.name, "Alto Sax")
        self.assertEqual(alto.label, "中音萨克斯")
        self.assertEqual(index_for_gm(65), CATALOG.index(alto))
        self.assertEqual(label_for_gm(65), "中音萨克斯")

        self.assertIsNone(program_for_gm(127))
        self.assertIsNone(index_for_gm(127))

    def test_unknown_program_falls_back_to_piano(self) -> None:
        piano = CATALOG[0]
        self.assertEqual(resolve_gm(65), (program_for_gm(65), False))
        self.assertEqual(resolve_gm(127), (piano, True))
        self.assertEqual(resolve_gm(-1), (piano, True))
        self.assertEqual(
            resolve_gm(65, available={0, 4}),
            (piano, True),
            "a catalog entry missing from the loaded SoundFont falls back",
        )
        self.assertEqual(label_for_gm(127), "钢琴 1")

    def test_fallback_notice_names_the_missing_sound(self) -> None:
        self.assertEqual(fallback_notice(65), "")
        unknown = fallback_notice(127)
        self.assertIn("127", unknown)
        self.assertIn("钢琴 1", unknown)
        missing = fallback_notice(65, available={0, 4})
        self.assertIn("Alto Sax", missing)
        self.assertIn("钢琴 1", missing)


class MetronomeSoundTest(unittest.TestCase):
    """Changing the main sound must never retune the metronome (B9a-2)."""

    def _backend(self):
        from app.core.synth_service import FluidSynthBackend

        class RecordingFS:
            def __init__(self) -> None:
                self.selects: list[tuple[int, int, int]] = []

            def program_select(self, channel, sfid, bank, program) -> None:
                self.selects.append((channel, bank, program))

        backend = object.__new__(FluidSynthBackend)
        backend.fs = RecordingFS()
        backend.sfid = 7
        backend.channel = 0
        return backend

    def test_click_channel_keeps_its_own_percussion_program(self) -> None:
        from app.core.synth_service import (
            ACCOMPANIMENT_CHANNEL,
            CLICK_CHANNEL,
            CLICK_PROGRAM,
            DEMO_CHANNEL,
        )

        backend = self._backend()
        backend.program(index_for_gm(65))  # Alto Sax
        backend.program(index_for_gm(40))  # Violin

        by_channel: dict[int, list[tuple[int, int]]] = {}
        for channel, bank, program in backend.fs.selects:
            by_channel.setdefault(channel, []).append((bank, program))

        self.assertEqual(by_channel[CLICK_CHANNEL], [(0, CLICK_PROGRAM)] * 2)
        self.assertEqual(CLICK_PROGRAM, 115, "GM 115 is Woodblock")
        for channel in (0, DEMO_CHANNEL, ACCOMPANIMENT_CHANNEL):
            self.assertEqual(by_channel[channel], [(0, 65), (0, 40)])

    def test_click_notes_stay_on_the_percussion_keys(self) -> None:
        from app.core.synth_service import CLICK_ACCENT_MIDI, CLICK_MIDI

        self.assertNotEqual(CLICK_ACCENT_MIDI, CLICK_MIDI)
        self.assertEqual({CLICK_MIDI, CLICK_ACCENT_MIDI}, {76, 77})


class SynthCatalogTest(unittest.TestCase):
    """The backend and the audio-free fallback must expose the same catalog.

    A NullSynth is used deliberately: these tests must pass on CI runners
    without FluidSynth or an audio device.
    """

    def test_synth_programs_follow_the_catalog(self) -> None:
        from app.core.synth_service import PROGRAMS

        self.assertEqual(PROGRAMS, tuple((p.gm, p.name) for p in CATALOG))
        self.assertEqual(len(PROGRAMS), len(CATALOG))

    def test_chinese_labels_cover_the_extended_catalog(self) -> None:
        from app.core.synth_service import program_label_cn

        self.assertEqual(program_label_cn("Alto Sax"), "中音萨克斯")
        self.assertEqual(program_label_cn("Pan Flute"), "排箫")
        self.assertEqual(program_label_cn("Not A GM Name"), "Not A GM Name")

    def test_null_synth_wraps_indices_over_the_catalog(self) -> None:
        from app.core.synth_service import NullSynth

        synth = NullSynth()
        self.assertEqual(synth.program(1), "E.Piano 1")
        self.assertEqual(synth.program(len(CATALOG) - 1), CATALOG[-1].name)
        self.assertEqual(synth.program(len(CATALOG)), CATALOG[0].name)


if __name__ == "__main__":
    unittest.main()
