"""Behaviour tests for the transport metronome (no Qt, explicit clock)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.metronome import Metronome


class MetronomeTest(unittest.TestCase):
    def test_clicks_every_beat_and_accents_the_bar(self) -> None:
        metronome = Metronome(bpm=120, beats_per_bar=4)
        metronome.start(100.0)

        self.assertEqual(
            [(click.index, click.accent) for click in metronome.advance(100.01)],
            [(0, True)],
        )
        self.assertEqual(
            [(click.index, click.accent) for click in metronome.advance(100.6)],
            [(1, False)],
        )
        self.assertEqual(
            [(click.index, click.accent) for click in metronome.advance(102.1)],
            [(2, False), (3, False), (4, True)],
        )

    def test_stop_and_restart_reset_the_beat_counter(self) -> None:
        metronome = Metronome(bpm=120, beats_per_bar=4)
        metronome.start(100.0)
        metronome.advance(100.6)
        metronome.stop()

        self.assertFalse(metronome.running)
        self.assertEqual(metronome.advance(101.0), [])

        metronome.start(200.0)
        self.assertEqual(
            [click.index for click in metronome.advance(200.01)], [0]
        )

    def test_tempo_controls_the_interval(self) -> None:
        metronome = Metronome(bpm=60, beats_per_bar=3)
        metronome.start(0.0)

        self.assertEqual([c.index for c in metronome.advance(0.9)], [0])
        self.assertEqual([c.index for c in metronome.advance(1.1)], [1])
        self.assertAlmostEqual(metronome.interval, 1.0)


if __name__ == "__main__":
    unittest.main()
