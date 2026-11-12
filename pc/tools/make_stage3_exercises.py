#!/usr/bin/env python3
"""Generate Stage 3 right-hand exercises as MusicXML + MIDI.

    python pc/tools/make_stage3_exercises.py

These are original exercises for this project, not transcriptions. Output is
deterministic so the content tests can rely on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import write_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

# C major scale up and back down, then the tonic triad in half notes.
# C5–C6 keeps every note inside the default chromatic mapping (F4–C7).
SCALE_C_MAJOR_UPDOWN = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("A", 5, 1), ("B", 5, 1), ("C", 6, 1)),
    (("C", 6, 1), ("B", 5, 1), ("A", 5, 1), ("G", 5, 1)),
    (("F", 5, 1), ("E", 5, 1), ("D", 5, 1), ("C", 5, 1)),
    (("C", 5, 2), ("E", 5, 2)),
    (("G", 5, 2), ("C", 6, 2)),
    (("C", 6, 2), ("G", 5, 2)),
    (("E", 5, 2), ("C", 5, 2)),
)

# Alternating seconds and thirds, up and back down inside C5–C6.
INTERVALS_SECONDS_THIRDS = (
    (("C", 5, 1), ("D", 5, 1), ("C", 5, 1), ("D", 5, 1)),
    (("E", 5, 1), ("F", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("D", 5, 1), ("F", 5, 1)),
    (("E", 5, 1), ("G", 5, 1), ("F", 5, 1), ("A", 5, 1)),
    (("G", 5, 1), ("E", 5, 1), ("F", 5, 1), ("D", 5, 1)),
    (("C", 6, 1), ("A", 5, 1), ("B", 5, 1), ("G", 5, 1)),
    (("A", 5, 1), ("B", 5, 1), ("A", 5, 1), ("B", 5, 1)),
    (("C", 6, 2), ("C", 5, 2)),
)

# Legato (contiguous quarter notes) then staccato (eighth notes separated by
# eighth rests). Rests use (None, None, duration).
LEGATO_STACCATO = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 1), ("E", 5, 1)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("C", 5, 1)),
    (
        ("C", 5, 0.5), (None, None, 0.5),
        ("D", 5, 0.5), (None, None, 0.5),
        ("E", 5, 0.5), (None, None, 0.5),
        ("F", 5, 0.5), (None, None, 0.5),
    ),
    (
        ("G", 5, 0.5), (None, None, 0.5),
        ("F", 5, 0.5), (None, None, 0.5),
        ("E", 5, 0.5), (None, None, 0.5),
        ("D", 5, 0.5), (None, None, 0.5),
    ),
    (
        ("C", 5, 0.5), (None, None, 0.5),
        ("E", 5, 0.5), (None, None, 0.5),
        ("G", 5, 0.5), (None, None, 0.5),
        ("E", 5, 0.5), (None, None, 0.5),
    ),
    (
        ("C", 5, 0.5), (None, None, 0.5),
        ("D", 5, 0.5), (None, None, 0.5),
        ("E", 5, 1), (None, None, 1),
    ),
)

EXERCISES = (
    {
        "stem": "scale_c_major_updown",
        "title": "C 大调音阶上下行",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": SCALE_C_MAJOR_UPDOWN,
    },
    {
        "stem": "intervals_seconds_thirds",
        "title": "二度与三度音程",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": INTERVALS_SECONDS_THIRDS,
    },
    {
        "stem": "legato_staccato",
        "title": "连奏与断奏对比",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": LEGATO_STACCATO,
    },
)


def main() -> int:
    for exercise in EXERCISES:
        write_score(
            OUT,
            exercise["stem"],
            exercise["title"],
            exercise["composer"],
            exercise["rights"],
            exercise["tempo"],
            exercise["measures"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
