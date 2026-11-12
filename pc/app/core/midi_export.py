"""Project → Standard MIDI File (format 1, PPQ 480), no Qt.

One conductor track carries tempo/time signature/title; each audible project
track becomes one MIDI track with its GM program, volume (CC7), and pan (CC10).
Mute hides a track; any solo hides every non-solo track. The app's own parser
merges all tracks again, so the exported file is the round-trip contract.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .project import Project

PPQ = 480
VELOCITY = 100


def _vlq(value: int) -> bytes:
    value = max(0, int(value))
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def _meta(kind: int, payload: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(payload)) + payload


def _tick(beats: float) -> int:
    return max(0, int(round(beats * PPQ)))


def _chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    body = bytearray()
    cursor = 0
    for tick, _order, data in sorted(events, key=lambda item: (item[0], item[1])):
        body += _vlq(tick - cursor)
        body += data
        cursor = tick
    body += _vlq(0) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _audible_tracks(project: Project):
    solo = any(track.solo for track in project.tracks)
    return [
        track
        for track in project.tracks
        if not track.mute and (not solo or track.solo)
    ]


def _pan_value(pan: float) -> int:
    return max(0, min(127, round((max(-1.0, min(1.0, pan)) + 1) * 63.5)))


def _volume_value(volume: float) -> int:
    return max(0, min(127, round(max(0.0, min(1.0, volume)) * 127)))


def export_midi(project: Project, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conductor: list[tuple[int, int, bytes]] = [
        (0, -3, _meta(0x03, project.title.encode("utf-8")[:127])),
    ]
    tempo = project.tempo if project.tempo > 0 else 120.0
    microseconds = max(1, min(0xFFFFFF, round(60_000_000 / tempo)))
    conductor.append(
        (0, -2, _meta(0x51, microseconds.to_bytes(3, "big")))
    )
    beats, unit = project.time_signature
    exponent = 0
    denominator = max(1, unit)
    while denominator > 1 and denominator % 2 == 0:
        denominator //= 2
        exponent += 1
    conductor.append(
        (
            0,
            -2,
            _meta(
                0x58,
                bytes([max(1, min(255, beats)), exponent & 0xFF, 24, 8]),
            ),
        )
    )

    voices: list[tuple] = []
    for track in _audible_tracks(project):
        if track.split is not None:
            split = track.split
            voices.append(
                (
                    track,
                    split.left_program,
                    split.left_volume,
                    track.pan,
                    [note for note in track.notes if note.midi < split.midi],
                )
            )
            voices.append(
                (
                    track,
                    split.right_program,
                    split.right_volume,
                    track.pan,
                    [note for note in track.notes if note.midi >= split.midi],
                )
            )
            continue
        voices.append(
            (track, track.program, track.volume, track.pan, track.notes)
        )
        if track.layer is not None:
            voices.append(
                (
                    track,
                    track.layer.program,
                    track.layer.volume,
                    track.pan,
                    track.notes,
                )
            )

    chunks = [_chunk(conductor)]
    for index, (track, program, volume, pan, note_events) in enumerate(
        voices[:14]
    ):
        channel = 1 + index if index < 8 else 1 + index + 1  # skip channel 9
        events: list[tuple[int, int, bytes]] = [
            (0, -3, _meta(0x03, track.name.encode("utf-8")[:127])),
            (0, -2, bytes([0xC0 | channel, max(0, min(127, program))])),
            (0, -2, bytes([0xB0 | channel, 7, _volume_value(volume)])),
            (0, -2, bytes([0xB0 | channel, 10, _pan_value(pan)])),
            (0, -2, bytes([0xB0 | channel, 91, _volume_value(project.reverb)])),
        ]
        for note in note_events:
            midi = max(0, min(127, note.midi))
            start = _tick(note.start)
            end = max(start + 1, _tick(note.end))
            events.append((start, 1, bytes([0x90 | channel, midi, VELOCITY])))
            events.append((end, 0, bytes([0x80 | channel, midi, 0])))
        chunks.append(_chunk(events))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ)
    path.write_bytes(header + b"".join(chunks))
    return path
