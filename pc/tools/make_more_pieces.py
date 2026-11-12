#!/usr/bin/env python3
"""Generate four more public-domain beginner pieces (P2 content batch).

    python pc/tools/make_more_pieces.py

All melodies stay inside the default 32-key chromatic window (F4–C7) and use
the deterministic score writer, so MusicXML and MIDI stay in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from score_writer import write_score  # noqa: E402

OUT = ROOT / "resources" / "scores"
REST = (None, None, 1)

MARY = (
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 1), ("D", 5, 1)),
    (("E", 5, 1), ("E", 5, 1), ("E", 5, 1), REST),
    (("D", 5, 1), ("D", 5, 1), ("D", 5, 1), REST),
    (("E", 5, 1), ("G", 5, 1), ("G", 5, 1), REST),
    (("E", 5, 1), ("D", 5, 1), ("C", 5, 1), ("D", 5, 1)),
    (("E", 5, 1), ("E", 5, 1), ("E", 5, 1), ("E", 5, 1)),
    (("D", 5, 1), ("D", 5, 1), ("E", 5, 1), ("D", 5, 1)),
    (("C", 5, 4),),
)

OLD_MACDONALD = (
    (("G", 4, 1), ("G", 4, 1), ("G", 4, 1), ("D", 5, 1)),
    (("E", 5, 1), ("E", 5, 1), ("D", 5, 2)),
    (("B", 4, 1), ("B", 4, 1), ("A", 4, 1), ("A", 4, 1)),
    (("G", 4, 2), (None, None, 2)),
    (("G", 4, 1), ("G", 4, 1), ("G", 4, 1), ("D", 5, 1)),
    (("E", 5, 1), ("E", 5, 1), ("D", 5, 2)),
    (("B", 4, 1), ("B", 4, 1), ("A", 4, 1), ("A", 4, 1)),
    (("G", 4, 4),),
)

AULD_LANG_SYNE = (
    (("C", 5, 1), ("F", 5, 1), ("F", 5, 1), ("F", 5, 1)),
    (("A", 5, 1), ("G", 5, 1), ("F", 5, 1), ("G", 5, 1)),
    (("A", 5, 1), ("F", 5, 1), ("F", 5, 1), ("G", 5, 1)),
    (("A", 5, 2), ("F", 5, 2)),
    (("A", 5, 1), ("A", 5, 1), ("G", 5, 1), ("F", 5, 1)),
    (("G", 5, 1), ("F", 5, 1), ("D", 5, 1), ("F", 5, 1)),
    (("A", 5, 1), ("G", 5, 1), ("F", 5, 1), ("G", 5, 1)),
    (("F", 5, 4),),
)

BRAHMS = (
    (("E", 5, 1), ("E", 5, 1), ("G", 5, 1)),
    (("E", 5, 1), ("E", 5, 1), ("G", 5, 1)),
    (("E", 5, 1), ("G", 5, 1), ("C", 6, 1)),
    (("B", 5, 1), ("A", 5, 1), ("A", 5, 1)),
    (("G", 5, 1), ("D", 5, 1), ("E", 5, 1)),
    (("F", 5, 1), ("D", 5, 1), ("D", 5, 1)),
    (("C", 5, 1), ("E", 5, 1), ("G", 5, 1)),
    (("C", 5, 2), REST),
)

PIECES = (
    {
        "stem": "mary_had_a_little_lamb",
        "title": "玛丽有只小羊羔",
        "composer": "美国传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 100,
        "measures": MARY,
        "beats": 4,
    },
    {
        "stem": "old_macdonald",
        "title": "老麦克唐纳",
        "composer": "美国传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 100,
        "measures": OLD_MACDONALD,
        "beats": 4,
    },
    {
        "stem": "auld_lang_syne",
        "title": "友谊地久天长",
        "composer": "苏格兰传统 / 公有领域",
        "rights": "Public Domain",
        "tempo": 80,
        "measures": AULD_LANG_SYNE,
        "beats": 4,
    },
    {
        "stem": "brahms_lullaby",
        "title": "勃拉姆斯摇篮曲",
        "composer": "Johannes Brahms / 公有领域",
        "rights": "Public Domain",
        "tempo": 76,
        "measures": BRAHMS,
        "beats": 3,
    },
)


def main() -> int:
    for piece in PIECES:
        write_score(
            OUT,
            piece["stem"],
            piece["title"],
            piece["composer"],
            piece["rights"],
            piece["tempo"],
            piece["measures"],
            beats_per_measure=piece["beats"],
        )
    print(f"wrote {len(PIECES)} pieces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
