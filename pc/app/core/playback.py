"""Project → playback plan (no Qt, no audio).

The planner turns project beats into scheduler seconds, applies mute/solo, and
normalizes an active loop so its start becomes time 0. Playback channels are
1–8 (channel 0 stays the live keyboard, 14 the metronome, 15 the demo).
"""

from __future__ import annotations

from dataclasses import dataclass

from .project import Project

VELOCITY = 100
FIRST_CHANNEL = 1
LOOP_EPS = 1e-9
MAX_VOICES = 14  # channels 1–8 and 10–15; channel 9 is the GM drum channel


@dataclass(frozen=True)
class PlaybackNote:
    start: float
    end: float
    midi: int
    velocity: int = VELOCITY


@dataclass(frozen=True)
class PlaybackTrack:
    channel: int
    program: int
    volume: float
    pan: float
    notes: tuple[PlaybackNote, ...]


@dataclass(frozen=True)
class PlaybackPlan:
    tracks: tuple[PlaybackTrack, ...]
    duration: float
    tempo: float
    loop: bool = False

    @property
    def empty(self) -> bool:
        return not any(track.notes for track in self.tracks)

    def beats_at(self, seconds: float) -> float:
        return max(0.0, seconds) * self.tempo / 60.0


def _channel_for(index: int) -> int:
    return FIRST_CHANNEL + index if index < 8 else FIRST_CHANNEL + index + 1


def _notes_for(
    note_events,
    seconds_per_beat: float,
    loop_start: float,
    loop_length: float,
    has_loop: bool,
) -> tuple[tuple[PlaybackNote, ...], float]:
    notes: list[PlaybackNote] = []
    longest = 0.0
    for note in note_events:
        start = note.start * seconds_per_beat
        end = note.end * seconds_per_beat
        if has_loop:
            loop_end = loop_start + loop_length
            if start >= loop_end - LOOP_EPS or end <= loop_start + LOOP_EPS:
                continue
            start = max(start, loop_start) - loop_start
            end = min(end, loop_end) - loop_start
        if end <= start:
            end = start + 0.001
        notes.append(PlaybackNote(start, end, max(0, min(127, note.midi))))
        longest = max(longest, end)
    notes.sort(key=lambda item: (item.start, item.midi))
    return tuple(notes), longest


def build_playback(project: Project) -> PlaybackPlan:
    tempo = project.tempo if project.tempo > 0 else 120.0
    seconds_per_beat = 60.0 / tempo
    loop = project.loop
    loop_start = loop.start * seconds_per_beat if loop is not None else 0.0
    loop_length = loop.length * seconds_per_beat if loop is not None else 0.0

    solo = any(track.solo for track in project.tracks)
    audible = [
        track
        for track in project.tracks
        if not track.mute and (not solo or track.solo)
    ]

    voices: list[tuple] = []
    for track in audible:
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

    tracks: list[PlaybackTrack] = []
    longest = 0.0
    for index, (track, program, volume, pan, note_events) in enumerate(
        voices[:MAX_VOICES]
    ):
        notes, voice_longest = _notes_for(
            note_events,
            seconds_per_beat,
            loop_start,
            loop_length,
            loop is not None,
        )
        longest = max(longest, voice_longest)
        tracks.append(
            PlaybackTrack(
                channel=_channel_for(index),
                program=max(0, min(127, program)),
                volume=max(0.0, min(1.0, volume)),
                pan=max(-1.0, min(1.0, pan)),
                notes=notes,
            )
        )

    duration = loop_length if loop is not None else longest
    return PlaybackPlan(tuple(tracks), max(0.0, duration), tempo, loop is not None)
