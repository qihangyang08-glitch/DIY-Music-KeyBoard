"""Record note-on/note-off beats into note events (no Qt, no audio).

The caller turns engine timestamps into beats and passes them here. Held notes
are tracked by MIDI number, so a repeated note-on for a key that is already
down does not start a second event.
"""

from __future__ import annotations

import math

from .project import LoopRegion, NoteEvent


def quantize(events: list[NoteEvent], grid: float) -> list[NoteEvent]:
    """Round onsets to the nearest grid; pitch and duration are untouched."""
    if grid <= 0:
        return list(events)
    return [
        NoteEvent(
            start=round(math.floor(event.start / grid + 0.5) * grid, 6),
            midi=event.midi,
            duration=event.duration,
        )
        for event in events
    ]


class Recorder:
    def __init__(self, loop: LoopRegion | None = None) -> None:
        self._loop = loop
        self._recording = False
        self._held: dict[int, float] = {}
        self._events: list[NoteEvent] = []

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        self._events.clear()
        self._held.clear()
        self._recording = True

    def note_on(self, midi: int, at: float) -> None:
        if not self._recording:
            return
        self._held.setdefault(midi, at)

    def _map_start(self, beat: float) -> float:
        if self._loop is None or self._loop.length <= 0:
            return max(0.0, beat)
        offset = (beat - self._loop.start) % self._loop.length
        return self._loop.start + offset

    def _event(self, start: float, midi: int, duration: float) -> NoteEvent:
        mapped = self._map_start(start)
        if self._loop is not None and self._loop.length > 0:
            duration = min(duration, max(0.0, self._loop.end - mapped))
        return NoteEvent(mapped, midi, max(0.0, duration))

    def note_off(self, midi: int, at: float) -> None:
        if not self._recording:
            return
        start = self._held.pop(midi, None)
        if start is None:
            return
        self._events.append(self._event(start, midi, at - start))

    def stop(self, at: float) -> list[NoteEvent]:
        self._recording = False
        for midi, start in self._held.items():
            self._events.append(self._event(start, midi, at - start))
        events = sorted(self._events, key=lambda event: event.start)
        self._events = []
        self._held.clear()
        return events
