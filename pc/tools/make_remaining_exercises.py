#!/usr/bin/env python3
"""Generate the remaining single/two-hand exercises as MusicXML + MIDI.

    python pc/tools/make_remaining_exercises.py

These fill lessons that previously had no matching practice: G/F hand
positions, and contrary/parallel motion. Everything stays inside the default
32-key chromatic window (F4–C7), so no special mapping is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import (  # noqa: E402
    midi,
    musicxml,
    write_score,
    write_two_voice_score,
)

OUT = ROOT / "resources" / "scores"
REST = (None, None, 1)
REST_HALF = (None, None, 2)

# G position (G4–D5) then F position (F4–C5, with B♭). The same five-finger
# shape moves twice, so the learner hears the hand position as transposition.
FIVE_FINGER_G_F = (
    (("G", 4, 1), ("A", 4, 1), ("B", 4, 1), ("C", 5, 1)),
    (("D", 5, 1), ("C", 5, 1), ("B", 4, 1), ("A", 4, 1)),
    (("G", 4, 1), ("A", 4, 1), ("B", 4, 1), ("C", 5, 1)),
    (("D", 5, 2), ("G", 4, 2)),
    (("F", 4, 1), ("G", 4, 1), ("A", 4, 1), ("Bb", 4, 1)),
    (("C", 5, 1), ("Bb", 4, 1), ("A", 4, 1), ("G", 4, 1)),
    (("F", 4, 1), ("G", 4, 1), ("A", 4, 1), ("Bb", 4, 1)),
    (("C", 5, 2), ("F", 4, 2)),
)

# Bars 1–4 move both voices together (parallel). Bars 5–7 move in opposite
# directions (contrary), then land on the tonic.
PARALLEL_CONTRARY_RIGHT = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("E", 5, 1), ("F", 5, 1), ("G", 5, 1), ("A", 5, 1)),
    (("G", 5, 2), ("C", 5, 2)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("E", 5, 1), ("F", 5, 1), ("G", 5, 1), ("A", 5, 1)),
    (("G", 5, 2), ("C", 5, 2)),
)
PARALLEL_CONTRARY_LEFT = (
    (("F", 4, 1), ("G", 4, 1), ("A", 4, 1), ("B", 4, 1)),
    (("C", 5, 1), ("B", 4, 1), ("A", 4, 1), ("G", 4, 1)),
    (("A", 4, 1), ("B", 4, 1), ("C", 5, 1), ("D", 5, 1)),
    (("G", 4, 2), ("F", 4, 2)),
    (("B", 4, 1), ("A", 4, 1), ("G", 4, 1), ("F", 4, 1)),
    (("F", 4, 1), ("G", 4, 1), ("A", 4, 1), ("B", 4, 1)),
    (("C", 5, 1), ("B", 4, 1), ("A", 4, 1), ("G", 4, 1)),
    (("G", 4, 2), ("F", 4, 2)),
)


# The pickup enters on beat 4 (half rest + quarter rest + G4). Measures 2–5
# are the repeated A section; measures 6–9 close the phrase. The written score
# keeps the repeat barlines while the MIDI is written out in performance order,
# so both parsers produce the same note list.
PICKUP_REPEAT = (
    (REST_HALF, REST, ("G", 4, 1)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 1), ("E", 5, 1)),
    (("C", 5, 2), ("G", 4, 2)),
    (("G", 5, 1), ("A", 5, 1), ("G", 5, 1), ("F", 5, 1)),
    (("E", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("C", 5, 4),),
)
PICKUP_REPEAT_UNROLLED = (
    (PICKUP_REPEAT[0],)
    + PICKUP_REPEAT[1:5] * 2
    + PICKUP_REPEAT[5:]
)


def write_pickup_repeat() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    xml = musicxml(
        "弱起与反复 · 8 小节",
        "本项目练习曲",
        "本项目原创",
        80,
        PICKUP_REPEAT,
        repeats={2: (True, False), 5: (False, True)},
    )
    (OUT / "pickup_repeat_8bars.musicxml").write_text(xml, encoding="utf-8")
    (OUT / "pickup_repeat_8bars.mid").write_bytes(
        midi(PICKUP_REPEAT_UNROLLED, 80)
    )


def main() -> int:
    write_score(
        OUT,
        "five_finger_gf_8bars",
        "五指位置 · G/F",
        "本项目练习曲",
        "本项目原创",
        72,
        FIVE_FINGER_G_F,
    )
    write_two_voice_score(
        OUT,
        "contrary_parallel_8bars",
        "反向与平行 · 8 小节",
        "本项目练习曲",
        "本项目原创",
        70,
        tuple(zip(PARALLEL_CONTRARY_RIGHT, PARALLEL_CONTRARY_LEFT)),
    )
    write_pickup_repeat()
    print(
        "wrote five_finger_gf_8bars, contrary_parallel_8bars "
        "and pickup_repeat_8bars"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
