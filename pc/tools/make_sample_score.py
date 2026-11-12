#!/usr/bin/env python3
"""Generate the public-domain 小星星 sample as MusicXML + MIDI.

    python pc/tools/make_sample_score.py

The melody is traditional / public domain. The files are deterministic so the
parser and the follow view can be tested without external tools.
"""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources" / "scores"

TEMPO_BPM = 100
DIVISIONS = 1          # MusicXML divisions per quarter
TICKS_PER_QUARTER = 480

# (step, octave, duration in quarter notes)
MELODY = [
    [("C", 5, 1), ("C", 5, 1), ("G", 5, 1), ("G", 5, 1)],
    [("A", 5, 1), ("A", 5, 1), ("G", 5, 2)],
    [("F", 5, 1), ("F", 5, 1), ("E", 5, 1), ("E", 5, 1)],
    [("D", 5, 1), ("D", 5, 1), ("C", 5, 2)],
    [("G", 5, 1), ("G", 5, 1), ("F", 5, 1), ("F", 5, 1)],
    [("E", 5, 1), ("E", 5, 1), ("D", 5, 2)],
    [("G", 5, 1), ("G", 5, 1), ("F", 5, 1), ("F", 5, 1)],
    [("E", 5, 1), ("E", 5, 1), ("D", 5, 2)],
    [("C", 5, 1), ("C", 5, 1), ("G", 5, 1), ("G", 5, 1)],
    [("A", 5, 1), ("A", 5, 1), ("G", 5, 2)],
    [("F", 5, 1), ("F", 5, 1), ("E", 5, 1), ("E", 5, 1)],
    [("D", 5, 1), ("D", 5, 1), ("C", 5, 2)],
]

STEP_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi_for(step: str, octave: int) -> int:
    return 12 * (octave + 1) + STEP_SEMITONE[step]


def musicxml() -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">',
        '<score-partwise version="4.0">',
        "  <work><work-title>小星星（片段）</work-title></work>",
        "  <identification>",
        '    <creator type="composer">传统 / 公有领域</creator>',
        "    <rights>Public Domain</rights>",
        "    <encoding><software>KeyBorad sample generator</software></encoding>",
        "  </identification>",
        "  <part-list>",
        '    <score-part id="P1"><part-name>Piano</part-name></score-part>',
        "  </part-list>",
        '  <part id="P1">',
    ]
    for number, measure in enumerate(MELODY, start=1):
        lines.append(f'    <measure number="{number}">')
        if number == 1:
            lines.extend(
                [
                    "      <attributes>",
                    f"        <divisions>{DIVISIONS}</divisions>",
                    "        <key><fifths>0</fifths></key>",
                    "        <time><beats>4</beats><beat-type>4</beat-type></time>",
                    "        <clef><sign>G</sign><line>2</line></clef>",
                    "      </attributes>",
                    '      <direction placement="above">',
                    "        <direction-type>",
                    "          <metronome><beat-unit>quarter</beat-unit>"
                    f"<per-minute>{TEMPO_BPM}</per-minute></metronome>",
                    "        </direction-type>",
                    f'        <sound tempo="{TEMPO_BPM}"/>',
                    "      </direction>",
                ]
            )
        for step, octave, duration in measure:
            note_type = "quarter" if duration == 1 else "half"
            lines.append(
                "      <note>"
                f"<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
                f"<duration>{duration * DIVISIONS}</duration>"
                f"<type>{note_type}</type>"
                "</note>"
            )
        lines.append("    </measure>")
    lines.extend(["  </part>", "</score-partwise>", ""])
    return "\n".join(lines)


def _vlq(value: int) -> bytes:
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)


def midi() -> bytes:
    events: list[tuple[int, bytes]] = []
    tick = 0
    for measure in MELODY:
        for step, octave, duration in measure:
            note = midi_for(step, octave)
            events.append((tick, bytes([0x90, note, 100])))
            events.append(
                (tick + duration * TICKS_PER_QUARTER, bytes([0x80, note, 64]))
            )
            tick += duration * TICKS_PER_QUARTER

    track = bytearray()
    track += b"\x00\xff\x51\x03" + struct.pack(">I", 60_000_000 // TEMPO_BPM)[1:]
    track += b"\x00\xff\x58\x04\x04\x02\x18\x08"
    last = 0
    for absolute, payload in sorted(events, key=lambda item: item[0]):
        track += _vlq(absolute - last)
        track += payload
        last = absolute
    track += b"\x00\xff\x2f\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    xml_path = OUT / "xiaoxingxing.musicxml"
    mid_path = OUT / "xiaoxingxing.mid"
    xml_path.write_text(musicxml(), encoding="utf-8")
    mid_path.write_bytes(midi())
    print(f"wrote {xml_path}")
    print(f"wrote {mid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
