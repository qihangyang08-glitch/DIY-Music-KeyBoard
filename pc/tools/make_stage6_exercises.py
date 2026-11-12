#!/usr/bin/env python3
"""Generate Stage 6 expression/complete-piece content.

    python pc/tools/make_stage6_exercises.py

The phrasing and tempo-ladder exercises are original. The Für Elise theme is
public domain; the Mariage d'Amour fragment is privately used and must be
excluded from public builds (marked in the curriculum and LICENSE).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import write_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

# Two four-bar phrases; the half rest at bar 4 is the breath between them.
PHRASING = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
    (("G", 5, 2), ("E", 5, 2)),
    (("F", 5, 1), ("G", 5, 1), ("A", 5, 1), ("G", 5, 1)),
    (("G", 5, 2), (None, None, 2)),
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 1), ("D", 5, 1)),
    (("E", 5, 2), ("G", 5, 2)),
    (("A", 5, 1), ("G", 5, 1), ("F", 5, 1), ("E", 5, 1)),
    (("C", 5, 4),),
)

# Stable 8-bar melody used for the 60 → 100% tempo ladder.
TEMPO_LADDER = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 1), ("E", 5, 1)),
    (("F", 5, 1), ("E", 5, 1), ("D", 5, 1), ("C", 5, 1)),
    (("D", 5, 4),),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 1), ("E", 5, 1)),
    (("F", 5, 1), ("E", 5, 1), ("D", 5, 1), ("C", 5, 1)),
    (("C", 5, 4),),
)

# Simplified 3/4 theme (public domain); D#/G# are written as accidentals.
FUR_ELISE = (
    (("E", 5, 1), ("D#", 5, 1), ("E", 5, 1)),
    (("D#", 5, 1), ("E", 5, 1), ("B", 4, 1)),
    (("D", 5, 1), ("C", 5, 1), ("A", 4, 1)),
    (("C", 5, 1), ("E", 5, 1), ("A", 5, 1)),
    (("B", 5, 1), ("E", 5, 1), ("G#", 5, 1)),
    (("B", 5, 1), ("C", 6, 1), ("A", 5, 1)),
    (("E", 5, 1), ("D#", 5, 1), ("E", 5, 1)),
    (("D#", 5, 1), ("E", 5, 1), ("B", 4, 1)),
)

# Private-use fragment: copyrighted source, excluded from public builds.
MARIAGE = (
    (("F", 5, 1), ("Ab", 5, 1), ("C", 6, 1), ("Ab", 5, 1)),
    (("Bb", 5, 1), ("Ab", 5, 1), ("F", 5, 2)),
    (("Eb", 5, 1), ("G", 5, 1), ("Bb", 5, 1), ("G", 5, 1)),
    (("F", 5, 1), ("Eb", 5, 1), ("C", 5, 2)),
    (("F", 5, 1), ("Ab", 5, 1), ("C", 6, 1), ("Ab", 5, 1)),
    (("Db", 6, 1), ("C", 6, 1), ("Ab", 5, 2)),
    (("Bb", 5, 1), ("Ab", 5, 1), ("F", 5, 1), ("Eb", 5, 1)),
    (("F", 5, 4),),
)

EXERCISES = (
    {
        "stem": "phrasing_8bars",
        "title": "乐句起落",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 70,
        "measures": PHRASING,
        "beats_per_measure": 4,
    },
    {
        "stem": "tempo_ladder_60",
        "title": "速度阶梯 60→100%",
        "composer": "本项目练习曲",
        "rights": "本项目原创",
        "tempo": 60,
        "measures": TEMPO_LADDER,
        "beats_per_measure": 4,
    },
    {
        "stem": "fur_elise_theme",
        "title": "致爱丽丝 · 主题",
        "composer": "贝多芬 / 公有领域",
        "rights": "Public Domain",
        "tempo": 60,
        "measures": FUR_ELISE,
        "beats_per_measure": 3,
    },
    {
        "stem": "mariage_fragment",
        "title": "梦中的婚礼 · 片段",
        "composer": "Paul de Senneville / 版权保护（仅私有）",
        "rights": "Copyrighted — private use only",
        "tempo": 60,
        "measures": MARIAGE,
        "beats_per_measure": 4,
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
            beats_per_measure=exercise["beats_per_measure"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
