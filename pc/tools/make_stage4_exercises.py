#!/usr/bin/env python3
"""Generate Stage 4 left-hand/chord exercises as MusicXML + MIDI.

    python pc/tools/make_stage4_exercises.py

These are original exercises for this project. The chord exercise uses the
score writer's chord cells `(((step, octave), ...), duration)` so every chord
sounds on one onset; the follow engine judges it as a chord.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import write_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

CHORDS = {
    "C": (("C", 5), ("E", 5), ("G", 5)),
    "F": (("F", 5), ("A", 5), ("C", 6)),
    "G": (("G", 5), ("B", 5), ("D", 6)),
}

# One whole-note chord per bar: I–IV–V–I, then IV–V–I–I.
CHORDS_CFG = (
    ((CHORDS["C"], 4),),
    ((CHORDS["F"], 4),),
    ((CHORDS["G"], 4),),
    ((CHORDS["C"], 4),),
    ((CHORDS["F"], 4),),
    ((CHORDS["G"], 4),),
    ((CHORDS["C"], 4),),
    ((CHORDS["C"], 4),),
)

# Root–fifth–octave–fifth in quarter notes; C5–G6 stays inside F4–C7.
ARPEGGIO_4_4 = (
    (("C", 5, 1), ("G", 5, 1), ("C", 6, 1), ("G", 5, 1)),
    (("F", 5, 1), ("C", 6, 1), ("F", 6, 1), ("C", 6, 1)),
    (("G", 5, 1), ("D", 6, 1), ("G", 6, 1), ("D", 6, 1)),
    (("C", 5, 1), ("G", 5, 1), ("C", 6, 1), ("G", 5, 1)),
    (("F", 5, 1), ("C", 6, 1), ("F", 6, 1), ("C", 6, 1)),
    (("G", 5, 1), ("D", 6, 1), ("G", 6, 1), ("D", 6, 1)),
    (("C", 5, 1), ("G", 5, 1), ("C", 6, 1), ("G", 5, 1)),
    (("C", 5, 1), ("G", 5, 1), ("C", 6, 1), ("G", 5, 1)),
)

EXERCISES = (
    {
        "stem": "chords_cfg",
        "title": "C–F–G 和弦",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": CHORDS_CFG,
    },
    {
        "stem": "arpeggio_4_4",
        "title": "分解和弦 · 4/4",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 80,
        "measures": ARPEGGIO_4_4,
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
