"""Transport metronome with an explicit clock (no Qt).

The caller drives ``advance(now)``; each returned click carries its beat index
and whether it starts a bar. This keeps count-in and recording tests
deterministic without timers or audio.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_CATCH_UP = 64


@dataclass(frozen=True)
class Click:
    index: int
    accent: bool


class Metronome:
    def __init__(self, bpm: float = 120.0, beats_per_bar: int = 4) -> None:
        self.bpm = bpm if bpm > 0 else 120.0
        self.beats_per_bar = max(1, beats_per_bar)
        self._started: float | None = None
        self._next = 0

    @property
    def interval(self) -> float:
        return 60.0 / self.bpm

    @property
    def running(self) -> bool:
        return self._started is not None

    @property
    def next_beat_time(self) -> float | None:
        if self._started is None:
            return None
        return self._started + self._next * self.interval

    def start(self, at: float) -> None:
        self._started = at
        self._next = 0

    def stop(self) -> None:
        self._started = None
        self._next = 0

    def advance(self, now: float) -> list[Click]:
        if self._started is None:
            return []
        clicks: list[Click] = []
        while len(clicks) < MAX_CATCH_UP:
            due = self._started + self._next * self.interval
            if due > now + 1e-9:
                break
            clicks.append(
                Click(self._next, self._next % self.beats_per_bar == 0)
            )
            self._next += 1
        return clicks
