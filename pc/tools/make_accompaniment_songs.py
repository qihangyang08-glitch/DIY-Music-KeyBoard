#!/usr/bin/env python3
"""Generate the H7e wide-range song: melody + auto-played left hand.

    python pc/tools/make_accompaniment_songs.py

The MusicXML uses two parts: P1 is the right-hand melody the learner plays
(C5–A5, inside the default 32-key map); P2 is the left-hand accompaniment the
app plays automatically (C3–D4, deliberately below the default map). The
same-stem MIDI carries both parts so the library's MusicXML→MIDI fallback and
the content tests stay note-for-note equal.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from make_beginner_pieces import ODE_MELODY, TWO_TIGERS  # noqa: E402
from score_writer import write_duet_score  # noqa: E402

OUT = ROOT / "resources" / "scores"

HALF = 2
QUARTER = 1

# Reusable two-beat bass cells: root + fifth.
C_BASS = (("C", 3, HALF), ("G", 3, HALF))
G_BASS = (("G", 3, HALF), ("D", 4, HALF))

# 欢乐颂: I–V alternation under the public-domain Beethoven melody.
ODE_LEFT = (
    C_BASS,
    G_BASS,
    C_BASS,
    G_BASS,
    C_BASS,
    G_BASS,
    C_BASS,
    C_BASS,
)

# 两只老虎: the melody stays on the tonic, so a tonic pedal is enough.
TIGERS_LEFT = (C_BASS,) * 8

# 小星星 (Twinkle, Twinkle, Little Star), 12 bars, right hand C5–A5.
TWINKLE_MELODY = (
    (("C", 5, QUARTER), ("C", 5, QUARTER), ("G", 5, QUARTER), ("G", 5, QUARTER)),
    (("A", 5, QUARTER), ("A", 5, QUARTER), ("G", 5, HALF)),
    (("F", 5, QUARTER), ("F", 5, QUARTER), ("E", 5, QUARTER), ("E", 5, QUARTER)),
    (("D", 5, QUARTER), ("D", 5, QUARTER), ("C", 5, HALF)),
    (("G", 5, QUARTER), ("G", 5, QUARTER), ("F", 5, QUARTER), ("F", 5, QUARTER)),
    (("E", 5, QUARTER), ("E", 5, QUARTER), ("D", 5, HALF)),
    (("G", 5, QUARTER), ("G", 5, QUARTER), ("F", 5, QUARTER), ("F", 5, QUARTER)),
    (("E", 5, QUARTER), ("E", 5, QUARTER), ("D", 5, HALF)),
    (("C", 5, QUARTER), ("C", 5, QUARTER), ("G", 5, QUARTER), ("G", 5, QUARTER)),
    (("A", 5, QUARTER), ("A", 5, QUARTER), ("G", 5, HALF)),
    (("F", 5, QUARTER), ("F", 5, QUARTER), ("E", 5, QUARTER), ("E", 5, QUARTER)),
    (("D", 5, QUARTER), ("D", 5, QUARTER), ("C", 5, HALF)),
)

# Fixed two-beat bass under the melody: I–I–IV–I–V–I–V–I–I–I–IV–I.
TWINKLE_LEFT = (
    (("C", 3, HALF), ("G", 3, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("F", 3, HALF), ("C", 4, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("G", 3, HALF), ("D", 4, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("G", 3, HALF), ("D", 4, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
    (("F", 3, HALF), ("C", 4, HALF)),
    (("C", 3, HALF), ("G", 3, HALF)),
)


def main() -> int:
    write_duet_score(
        OUT,
        "twinkle_auto_accompaniment",
        "小星星 · 自动左手",
        "法国传统童谣 / 本项目编配",
        "Public Domain (melody) / original accompaniment",
        80,
        TWINKLE_MELODY,
        TWINKLE_LEFT,
    )
    write_duet_score(
        OUT,
        "ode_auto_accompaniment",
        "欢乐颂 · 自动左手",
        "贝多芬 / 公有领域；本项目编配",
        "Public Domain (melody) / original accompaniment",
        80,
        ODE_MELODY,
        ODE_LEFT,
    )
    write_duet_score(
        OUT,
        "two_tigers_auto_accompaniment",
        "两只老虎 · 自动左手",
        "法国传统 / 公有领域；本项目编配",
        "Public Domain (melody) / original accompaniment",
        90,
        TWO_TIGERS,
        TIGERS_LEFT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
