"""Metronome rhythm drills: patterns, timing and judging, no UI.

A rhythm spec is a sequence of bars made of note durations in beats. The
session schedules a one-bar count-in plus a metronome click on every beat, and
judges the first press near each onset. This is deliberately a *timing* drill,
not a pitch drill: any key answers.

The window is ±tolerance around each onset. A press outside every unjudged
window is an extra; an onset whose window closes without a press is a missed
beat. This keeps the rules simple and testable with a fake clock.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable


def rest(beats: float) -> float:
    """Mark a cell as a silent rest; negative durations are rests."""
    return -abs(float(beats))


@dataclass(frozen=True)
class RhythmEvent:
    index: int
    beat: float       # offset from the first pattern bar
    duration: float   # beats
    rest: bool = False


@dataclass(frozen=True)
class RhythmSpec:
    key: str
    title: str
    subtitle: str
    bpm: int
    beats_per_bar: int
    bars: int
    cells: tuple[tuple[float, ...], ...]
    count_in_bars: int = 1
    tolerance_ms: int = 150
    # Beat positions inside one bar that get the strong metronome click.
    # 4/4 accents beat 1 only; 6/8 accents beats 1 and 4.
    accent_beats: tuple[int, ...] = (0,)
    # Display label for compound meters ("6/8"); empty derives "<n>/4".
    meter: str = ""

    def __post_init__(self) -> None:
        if self.bpm <= 0 or self.beats_per_bar <= 0 or self.bars <= 0:
            raise ValueError("rhythm spec needs positive bpm/beats/bars")
        if len(self.cells) != self.bars:
            raise ValueError("rhythm spec needs one cell list per bar")
        if any(
            beat < 0 or beat >= self.beats_per_bar
            for beat in self.accent_beats
        ):
            raise ValueError("accent beats must fall inside the bar")
        for bar in self.cells:
            if any(abs(value) < 1e-9 for value in bar):
                raise ValueError("rhythm cells need a non-zero duration")
            if abs(sum(abs(value) for value in bar) - self.beats_per_bar) > 1e-6:
                raise ValueError("each rhythm bar must add up to beats_per_bar")

    @property
    def meter_label(self) -> str:
        return self.meter or f"{self.beats_per_bar}/4"

    @property
    def beat_seconds(self) -> float:
        return 60.0 / self.bpm

    @property
    def total_beats(self) -> float:
        return float(self.bars * self.beats_per_bar)

    @property
    def count_in_beats(self) -> int:
        return self.count_in_bars * self.beats_per_bar

    @property
    def tolerance(self) -> float:
        return self.tolerance_ms / 1000.0

    @property
    def events(self) -> tuple[RhythmEvent, ...]:
        out: list[RhythmEvent] = []
        beat = 0.0
        for bar in self.cells:
            for duration in bar:
                is_rest = duration < 0
                beats = -duration if is_rest else duration
                out.append(RhythmEvent(len(out), beat, beats, is_rest))
                beat += beats
        return tuple(out)

    @property
    def note_events(self) -> tuple[RhythmEvent, ...]:
        """Events the player must actually press; rests are silent gaps."""
        return tuple(event for event in self.events if not event.rest)


@dataclass(frozen=True)
class RhythmClick:
    index: int
    pattern_beat: int  # negative during count-in
    count_in: bool
    accent: bool


@dataclass(frozen=True)
class RhythmPress:
    hit: bool
    index: int | None
    error_ms: int


@dataclass(frozen=True)
class RhythmOutcome:
    hits: int
    misses: int
    extras: int
    total: int
    attempts: int
    first_try: int
    accuracy: int
    avg_ms: int
    best_streak: int
    finished: bool


class RhythmSession:
    """One run of a rhythm pattern."""

    def __init__(self, spec: RhythmSpec, clock: Callable[[], float] | None = None):
        self.spec = spec
        self.events = spec.events
        self.note_events = tuple(
            event for event in self.events if not event.rest
        )
        self.started_at: float | None = None
        self.running = False
        self._finished = False
        self.hit = [False] * len(self.events)
        self.missed = [False] * len(self.events)
        self.errors_ms: list[int] = []
        self.extras = 0
        self.streak = 0
        self.best_streak = 0
        self.last_click_at: float | None = None
        self.last_click_accent = False
        self.last_press: RhythmPress | None = None
        self._next_click = 0
        self._clock = clock or time.monotonic

    # -- read side ------------------------------------------------------

    @property
    def total(self) -> int:
        """Onsets the player must press; rests are silent gaps."""
        return len(self.note_events)

    @property
    def hits(self) -> int:
        return sum(1 for value in self.hit if value)

    @property
    def misses(self) -> int:
        return sum(1 for value in self.missed if value)

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def total_clicks(self) -> int:
        return self.spec.count_in_beats + int(self.spec.total_beats)

    def position_beats(self, now: float | None = None) -> float:
        """Pattern-relative position in beats; negative during count-in."""
        if self.started_at is None:
            return -self.spec.count_in_beats
        now = self._clock() if now is None else now
        return (now - self.started_at) / self.spec.beat_seconds - self.spec.count_in_beats

    def count_in_remaining(self, now: float | None = None) -> int:
        if not self.running or self.started_at is None:
            return 0
        now = self._clock() if now is None else now
        elapsed = (now - self.started_at) / self.spec.beat_seconds
        if elapsed >= self.spec.count_in_beats - 1e-9:
            return 0
        return int(math.ceil(self.spec.count_in_beats - elapsed))

    # -- lifecycle ------------------------------------------------------

    def start(self, now: float | None = None) -> None:
        self.started_at = self._clock() if now is None else now
        self.running = True
        self._finished = False
        self.hit = [False] * len(self.events)
        self.missed = [False] * len(self.events)
        self.errors_ms.clear()
        self.extras = 0
        self.streak = 0
        self.best_streak = 0
        self.last_click_at = None
        self.last_click_accent = False
        self.last_press = None
        self._next_click = 0

    def stop(self) -> None:
        self.running = False
        # Once every onset has been hit or missed, the run is complete even
        # if the fixed post-roll tail has not elapsed yet. Without this, a
        # perfect 16/16 run stopped right after the last beat looked unfinished
        # and the optional exam discarded it.
        if self.started_at is not None and all(
            self.hit[event.index] or self.missed[event.index]
            for event in self.note_events
        ):
            self._finished = True

    # -- judging --------------------------------------------------------

    def tick(self, now: float | None = None) -> list[RhythmClick]:
        if not self.running or self.started_at is None:
            return []
        now = self._clock() if now is None else now
        clicks: list[RhythmClick] = []
        while self._next_click < self.total_clicks:
            due = self.started_at + self._next_click * self.spec.beat_seconds
            if now + 1e-9 < due:
                break
            index = self._next_click
            self._next_click += 1
            count_in = index < self.spec.count_in_beats
            pattern_beat = index - self.spec.count_in_beats
            beat_in_bar = pattern_beat % self.spec.beats_per_bar
            accent = beat_in_bar in self.spec.accent_beats
            clicks.append(RhythmClick(index, pattern_beat, count_in, accent))
            self.last_click_at = due
            self.last_click_accent = accent

        tolerance = self.spec.tolerance
        count_in_seconds = self.spec.count_in_beats * self.spec.beat_seconds
        for event in self.note_events:
            if self.hit[event.index] or self.missed[event.index]:
                continue
            due = (
                self.started_at
                + count_in_seconds
                + event.beat * self.spec.beat_seconds
            )
            if now > due + tolerance:
                self.missed[event.index] = True
                self.streak = 0

        end = (
            self.started_at
            + count_in_seconds
            + self.spec.total_beats * self.spec.beat_seconds
            + tolerance
            + 0.25
        )
        if now >= end:
            self.running = False
            self._finished = True
        return clicks

    def press(self, now: float | None = None) -> RhythmPress | None:
        if not self.running or self.started_at is None:
            return None
        now = self._clock() if now is None else now
        count_in_seconds = self.spec.count_in_beats * self.spec.beat_seconds
        pattern_time = now - self.started_at - count_in_seconds
        if pattern_time < -self.spec.tolerance:
            return None  # count-in presses are not answers

        tolerance = self.spec.tolerance
        best: tuple[int, float] | None = None
        for event in self.note_events:
            if self.hit[event.index] or self.missed[event.index]:
                continue
            error = pattern_time - event.beat * self.spec.beat_seconds
            if abs(error) <= tolerance:
                if best is None or abs(error) < abs(best[1]):
                    best = (event.index, error)
        if best is None:
            self.extras += 1
            self.streak = 0
            result = RhythmPress(False, None, 0)
            self.last_press = result
            return result

        index, error = best
        self.hit[index] = True
        error_ms = round(error * 1000)
        self.errors_ms.append(abs(error_ms))
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        result = RhythmPress(True, index, error_ms)
        self.last_press = result
        return result

    # -- summary --------------------------------------------------------

    def outcome(self) -> RhythmOutcome:
        attempts = self.hits + self.misses + self.extras
        avg_ms = (
            # Floor, not round: a true mean of 59.5 ms is still below the
            # 60 ms exam bar, and rounding it up would fail a passing run.
            max(1, int(sum(self.errors_ms) / len(self.errors_ms)))
            if self.errors_ms
            else 0
        )
        return RhythmOutcome(
            hits=self.hits,
            misses=self.misses,
            extras=self.extras,
            total=self.total,
            attempts=attempts,
            first_try=0,
            accuracy=round(100 * self.hits / attempts) if attempts else 0,
            avg_ms=avg_ms,
            best_streak=self.best_streak,
            finished=self.finished,
        )
