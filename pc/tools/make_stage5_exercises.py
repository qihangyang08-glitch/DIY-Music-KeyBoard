#!/usr/bin/env python3
"""Generate Stage 5 two-hand exercises as MusicXML + MIDI.

    python pc/tools/make_stage5_exercises.py

The split exercise is intentionally wider than one chromatic octave; play it
with the 左右分区 mapping. The slow/fixed pieces reuse the public-domain
欢乐颂 melody with a project-written left hand. The minuet is original.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from make_beginner_pieces import ODE_BASS, ODE_MELODY  # noqa: E402
from score_writer import write_two_voice_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

REST = (None, None, 1)

# Wide two-hand exercise: left C3–C4 (split left side), right C5–A5 (right side).
SPLIT_RIGHT = (
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 2)),
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 2)),
    (("F", 5, 1), ("A", 5, 1), ("G", 5, 2)),
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 2)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 2)),
    (("A", 5, 1), ("G", 5, 1), ("E", 5, 2)),
    (("D", 5, 1), ("E", 5, 1), ("F", 5, 2)),
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 2)),
)
SPLIT_LEFT = (
    (("C", 3, 2), ("G", 3, 2)),
    (("G", 3, 2), ("G", 3, 2)),
    (("F", 3, 2), ("C", 4, 2)),
    (("G", 3, 2), ("G", 3, 2)),
    (("C", 3, 2), ("G", 3, 2)),
    (("A", 3, 2), ("E", 3, 2)),
    (("F", 3, 2), ("C", 4, 2)),
    (("G", 3, 2), ("C", 3, 2)),
)

# Fixed left hand under the 欢乐颂 melody; G4/B4 never collide with the melody.
FIXED_BASS = ((("G", 4, 2), ("B", 4, 2)),) * 8

# Original 3/4 minuet: right melody C5–G5, left G/B and F/A accompaniment.
MINUET_RIGHT = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
    (("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 2), ("E", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1)),
    (("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("E", 5, 2), ("D", 5, 1)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
    (("C", 5, 2), REST),
)
MINUET_LEFT = (
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
    (("F", 4, 1), ("A", 4, 1), ("F", 4, 1)),
    (("F", 4, 1), ("A", 4, 1), ("F", 4, 1)),
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
    (("G", 4, 1), ("B", 4, 1), ("G", 4, 1)),
)

EXERCISES = (
    {
        "stem": "split_hands_8bars",
        "title": "左右分区 · 8 小节",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": tuple(zip(SPLIT_RIGHT, SPLIT_LEFT)),
        "beats_per_measure": 4,
    },
    {
        "stem": "ode_to_joy_both_slow",
        "title": "慢速合手 · 50%",
        "composer": "贝多芬 / 公有领域；本项目编配",
        "rights": "Public Domain (melody) / original arrangement",
        "tempo": 40,
        "measures": tuple(zip(ODE_MELODY, ODE_BASS)),
        "beats_per_measure": 4,
    },
    {
        "stem": "fixed_accompaniment",
        "title": "固定伴奏型",
        "composer": "贝多芬旋律 / 本项目伴奏",
        "rights": "Public Domain (melody) / original accompaniment",
        "tempo": 80,
        "measures": tuple(zip(ODE_MELODY, FIXED_BASS)),
        "beats_per_measure": 4,
    },
    {
        "stem": "minuet_3_4",
        "title": "小步舞曲",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": tuple(zip(MINUET_RIGHT, MINUET_LEFT)),
        "beats_per_measure": 3,
    },
)


def main() -> int:
    for exercise in EXERCISES:
        write_two_voice_score(
            OUT,
            exercise["stem"],
            exercise["title"],
            exercise["composer"],
            exercise["rights"],
            exercise["tempo"],
            exercise["measures"],
            beats_per_measure=exercise["beats_per_measure"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
