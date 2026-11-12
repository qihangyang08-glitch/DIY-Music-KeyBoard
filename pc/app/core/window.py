"""Automatic 32-key windows for scores wider than one mapping.

The physical keyboard is fixed: 32 bars, one mapping preset, one octave /
transpose offset. A score that spans more than that range needs the mapping to
move while the player follows it. This module plans where that move happens.

Pure logic only: it reads a parsed `Score` and a `MapPreset`, and returns
segments (phrases) with the absolute octave each one should use. It knows
nothing about Qt, the follow session or the UI.

Planning rules:

- split at measure boundaries;
- a rest of at least one beat between measures also starts a new phrase;
- keep merging measures while the phrase still fits (at most `max_measures`);
- choose the octave with the fewest unplayable notes; when several work,
  stay near the previous phrase's octave so the keyboard does not jump.

The follow session applies a segment's octave when its first note becomes the
next note; notes already sounding keep the pitch they were started with.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache

from .mapping import KEY_COUNT, MapPreset
from .note_engine import MAX_OCTAVE, MIN_OCTAVE, midi_name
from .score import Score

PHRASE_REST_BEATS = 1.0
MAX_PHRASE_MEASURES = 4


@dataclass(frozen=True)
class WindowSegment:
    index: int              # 0-based position in the plan
    first_note: int         # first Score.notes index in the phrase
    last_note: int          # last Score.notes index in the phrase
    start: float            # seconds
    end: float              # seconds
    octave: int             # absolute octave offset to apply
    lo: int                 # lowest MIDI note reachable at this octave
    hi: int                 # highest MIDI note reachable at this octave
    unplayable: int         # notes in the phrase the mapping cannot reach
    measure_first: int
    measure_last: int
    split_label: str | None = None  # two-register label; None = one span

    @property
    def range_label(self) -> str:
        if self.split_label is not None:
            return self.split_label
        return f"{midi_name(self.lo)}–{midi_name(self.hi)}"

    @property
    def note_count(self) -> int:
        return self.last_note - self.first_note + 1


@dataclass(frozen=True)
class WindowPlan:
    segments: tuple[WindowSegment, ...]

    def segment_for_note(self, index: int) -> WindowSegment | None:
        """Segment that owns a note index (clamped to the ends)."""
        if not self.segments:
            return None
        for segment in self.segments:
            if segment.first_note <= index <= segment.last_note:
                return segment
        if index < self.segments[0].first_note:
            return self.segments[0]
        return self.segments[-1]


def plan_windows(
    score: Score,
    preset: MapPreset,
    transpose: int = 0,
    current_octave: int = 0,
    max_measures: int = MAX_PHRASE_MEASURES,
) -> WindowPlan:
    """Plan phrase windows for `score` under `preset` + `transpose`."""
    notes = score.notes
    if not notes:
        return WindowPlan(())

    groups = _measure_groups(notes)
    beat_seconds = 60.0 / max(1.0, score.tempo)
    rest_gap = beat_seconds * PHRASE_REST_BEATS

    phrases: list[list[int]] = []
    for group in groups:
        if phrases:
            previous = phrases[-1]
            merged = previous + group
            gap = notes[group[0]].start - notes[previous[-1]].end
            if (
                _measure_span(notes, merged) <= max_measures
                and gap < rest_gap
                and _best_unplayable(
                    tuple(notes[i].midi for i in merged), preset, transpose
                )
                == 0
            ):
                previous.extend(group)
                continue
        phrases.append(list(group))

    segments: list[WindowSegment] = []
    octave = current_octave
    for phrase in phrases:
        midis = tuple(notes[i].midi for i in phrase)
        octave, lo, hi, unplayable = _choose_octave(
            midis, preset, transpose, octave
        )
        first = notes[phrase[0]]
        last = notes[phrase[-1]]
        if segments and segments[-1].octave == octave:
            # Same octave as the previous phrase: the keyboard does not move,
            # so this is part of the same window region.
            merged = segments[-1]
            segments[-1] = replace(
                merged,
                last_note=phrase[-1],
                end=last.end,
                unplayable=merged.unplayable + unplayable,
                measure_last=last.measure,
            )
            continue
        split_label = (
            preset.range_label(12 * octave + transpose)
            if preset.split is not None
            else None
        )
        segments.append(
            WindowSegment(
                index=len(segments),
                first_note=phrase[0],
                last_note=phrase[-1],
                start=first.start,
                end=last.end,
                octave=octave,
                lo=lo,
                hi=hi,
                unplayable=unplayable,
                measure_first=first.measure,
                measure_last=last.measure,
                split_label=split_label,
            )
        )
    return WindowPlan(tuple(segments))


def _measure_groups(notes) -> list[list[int]]:
    groups: list[list[int]] = []
    previous_measure = None
    for index, note in enumerate(notes):
        if previous_measure is None or note.measure != previous_measure:
            groups.append([index])
            previous_measure = note.measure
        else:
            groups[-1].append(index)
    return groups


def _measure_span(notes, indices) -> int:
    """Number of measure changes inside a phrase (a single measure = 1)."""
    return 1 + sum(
        1
        for left, right in zip(indices, indices[1:])
        if notes[left].measure != notes[right].measure
    )


def _candidate_octaves(preset: MapPreset, transpose: int) -> tuple[int, ...]:
    """Octaves the engine and MIDI both allow.

    The note engine clamps octave to MIN_OCTAVE..MAX_OCTAVE; staying inside
    that range means the plan never asks for an offset the engine ignores.
    The MIDI bound keeps every mapped key inside 0..127.
    """
    base_lo, base_hi = preset.key_range()
    base_lo += transpose
    base_hi += transpose
    low = max(MIN_OCTAVE, math.ceil((0 - base_lo) / 12))
    high = min(MAX_OCTAVE, math.floor((127 - base_hi) / 12))
    if low > high:
        return tuple(range(MIN_OCTAVE, MAX_OCTAVE + 1))
    return tuple(range(low, high + 1))


@lru_cache(maxsize=256)
def _reachable(preset: MapPreset, transpose: int, octave: int) -> frozenset[int]:
    return frozenset(
        preset.midi_for_key(key) + 12 * octave + transpose
        for key in preset.enabled_keys()
    )


def _cost(
    midis: tuple[int, ...], preset: MapPreset, transpose: int, octave: int
) -> int:
    reachable = _reachable(preset, transpose, octave)
    return sum(1 for midi in midis if midi not in reachable)


def _best_unplayable(
    midis: tuple[int, ...], preset: MapPreset, transpose: int
) -> int:
    return min(
        _cost(midis, preset, transpose, octave)
        for octave in _candidate_octaves(preset, transpose)
    )


def _choose_octave(
    midis: tuple[int, ...],
    preset: MapPreset,
    transpose: int,
    prefer: int,
) -> tuple[int, int, int, int]:
    """Return (octave, lo, hi, unplayable) with continuity as tie-break."""
    base_lo, base_hi = preset.key_range()
    best_key = None
    best = (prefer, 0, 0, len(midis))
    for octave in _candidate_octaves(preset, transpose):
        unplayable = _cost(midis, preset, transpose, octave)
        key = (unplayable, abs(octave - prefer), abs(octave), octave)
        if best_key is None or key < best_key:
            best_key = key
            best = (
                octave,
                base_lo + 12 * octave + transpose,
                base_hi + 12 * octave + transpose,
                unplayable,
            )
    return best
