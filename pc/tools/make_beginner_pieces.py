#!/usr/bin/env python3
"""Generate beginner content as MusicXML + MIDI.

    python pc/tools/make_beginner_pieces.py

All melodies are public domain. The arrangements are simple one-line beginner
versions for this project, not authoritative editions. Output is deterministic
so the library/learning tests can rely on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import write_score, write_two_voice_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

# (step, octave, duration in quarter notes)
ODE_MELODY = (
    (("E", 5, 1), ("E", 5, 1), ("F", 5, 1), ("G", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
    (("E", 5, 1), ("D", 5, 1), ("D", 5, 2)),
    (("E", 5, 1), ("E", 5, 1), ("F", 5, 1), ("G", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
    (("D", 5, 1), ("C", 5, 1), ("C", 5, 2)),
)

# A simple left-hand line that stays inside the default F4–C7 window.
ODE_BASS = (
    (("G", 4, 2), ("G", 4, 2)),
    (("G", 4, 2), ("G", 4, 2)),
    (("A", 4, 2), ("A", 4, 2)),
    (("F", 4, 2), ("G", 4, 2)),
    (("G", 4, 2), ("G", 4, 2)),
    (("G", 4, 2), ("G", 4, 2)),
    (("A", 4, 2), ("A", 4, 2)),
    (("F", 4, 2), ("G", 4, 2)),
)

TWO_TIGERS = (
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("C", 5, 1)),
    (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("C", 5, 1)),
    (("E", 5, 1), ("F", 5, 1), ("G", 5, 2)),
    (("E", 5, 1), ("F", 5, 1), ("G", 5, 2)),
    (("G", 5, 1), ("A", 5, 1), ("G", 5, 1), ("F", 5, 1)),
    (("E", 5, 1), ("C", 5, 1), ("C", 5, 2)),
    (("C", 5, 1), ("G", 5, 1), ("C", 5, 2)),
    (("C", 5, 1), ("G", 5, 1), ("C", 5, 2)),
)

TWO_VOICE_PIECES = (
    {
        "stem": "ode_to_joy_both",
        "title": "欢乐颂 · 双手版",
        "composer": "贝多芬 / 公有领域",
        "rights": "Public Domain",
        "tempo": 80,
        "measures": tuple(zip(ODE_MELODY, ODE_BASS)),
    },
)

PIECES = (
    {
        "stem": "ode_to_joy",
        "title": "欢乐颂",
        "composer": "贝多芬 / 公有领域",
        "rights": "Public Domain",
        "tempo": 80,
        "measures": ODE_MELODY,
    },
    {
        "stem": "jingle_bells",
        "title": "铃儿响叮当（片段）",
        "composer": "皮尔彭特 / 公有领域",
        "rights": "Public Domain",
        "tempo": 100,
        "measures": (
            (("E", 5, 1), ("E", 5, 1), ("E", 5, 2)),
            (("E", 5, 1), ("E", 5, 1), ("E", 5, 2)),
            (("E", 5, 1), ("G", 5, 1), ("C", 5, 1), ("D", 5, 1)),
            (("E", 5, 4),),
            (("F", 5, 1), ("F", 5, 1), ("F", 5, 1), ("F", 5, 1)),
            (("F", 5, 1), ("E", 5, 1), ("E", 5, 1), ("E", 5, 1)),
            (("E", 5, 1), ("D", 5, 1), ("D", 5, 1), ("E", 5, 1)),
            (("D", 5, 2), ("G", 5, 2)),
        ),
    },
    {
        "stem": "two_tigers",
        "title": "两只老虎",
        "composer": "法国传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 90,
        "measures": TWO_TIGERS,
    },
    {
        "stem": "london_bridge",
        "title": "伦敦桥",
        "composer": "英国传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 100,
        "measures": (
            (("G", 5, 1), ("A", 5, 1), ("G", 5, 1), ("F", 5, 1)),
            (("E", 5, 1), ("F", 5, 1), ("G", 5, 2)),
            (("D", 5, 1), ("E", 5, 1), ("F", 5, 2)),
            (("E", 5, 1), ("F", 5, 1), ("G", 5, 2)),
            (("G", 5, 1), ("A", 5, 1), ("G", 5, 1), ("F", 5, 1)),
            (("E", 5, 1), ("F", 5, 1), ("G", 5, 2)),
            (("D", 5, 1), ("G", 5, 1), ("E", 5, 1), ("C", 5, 1)),
            (("C", 5, 4),),
        ),
    },
    {
        "stem": "lightly_row",
        "title": "小蜜蜂",
        "composer": "德国传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 100,
        "measures": (
            (("G", 5, 1), ("E", 5, 1), ("E", 5, 2)),
            (("D", 5, 1), ("C", 5, 1), ("C", 5, 2)),
            (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("F", 5, 1)),
            (("G", 5, 1), ("G", 5, 1), ("G", 5, 2)),
            (("G", 5, 1), ("E", 5, 1), ("E", 5, 2)),
            (("D", 5, 1), ("C", 5, 1), ("C", 5, 2)),
            (("C", 5, 1), ("E", 5, 1), ("G", 5, 1), ("G", 5, 1)),
            (("C", 5, 4),),
        ),
    },
    {
        "stem": "farewell",
        "title": "送别",
        "composer": "奥德威 / 公有领域",
        "rights": "Public Domain",
        "tempo": 70,
        "measures": (
            (("G", 5, 1), ("E", 5, 1), ("G", 5, 1), ("C", 6, 1)),
            (("A", 5, 1), ("C", 6, 1), ("G", 5, 2)),
            (("G", 5, 1), ("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
            (("D", 5, 1), ("E", 5, 1), ("D", 5, 2)),
            (("C", 5, 1), ("D", 5, 1), ("E", 5, 1), ("G", 5, 1)),
            (("E", 5, 1), ("D", 5, 1), ("C", 5, 2)),
            (("A", 5, 1), ("G", 5, 1), ("A", 5, 1), ("C", 6, 1)),
            (("G", 5, 4),),
        ),
    },
    {
        "stem": "canon_easy",
        "title": "卡农片段 · 简易版",
        "composer": "帕赫贝尔 / 公有领域",
        "rights": "Public Domain",
        "tempo": 70,
        "measures": (
            (("E", 5, 1), ("D", 5, 1), ("C", 5, 1), ("B", 4, 1)),
            (("A", 4, 1), ("G", 4, 1), ("A", 4, 1), ("B", 4, 1)),
            (("C", 5, 1), ("B", 4, 1), ("A", 4, 1), ("G", 4, 1)),
            (("A", 4, 4),),
            (("E", 5, 1), ("D", 5, 1), ("C", 5, 1), ("B", 4, 1)),
            (("A", 4, 1), ("G", 4, 1), ("A", 4, 1), ("B", 4, 1)),
            (("C", 5, 1), ("B", 4, 1), ("A", 4, 1), ("B", 4, 1)),
            (("C", 5, 4),),
        ),
    },
)


def main() -> int:
    for piece in PIECES:
        xml_path, mid_path = write_score(
            OUT,
            piece["stem"],
            piece["title"],
            piece["composer"],
            piece["rights"],
            piece["tempo"],
            piece["measures"],
        )
        print(f"wrote {xml_path}")
        print(f"wrote {mid_path}")
    for piece in TWO_VOICE_PIECES:
        xml_path, mid_path = write_two_voice_score(
            OUT,
            piece["stem"],
            piece["title"],
            piece["composer"],
            piece["rights"],
            piece["tempo"],
            piece["measures"],
        )
        print(f"wrote {xml_path}")
        print(f"wrote {mid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
