"""Pure staff layout: Score -> systems, measures, and note positions.

Drawing stays in the Qt widget. This module only answers musical questions:
which staff a note belongs to, how many staff steps above the bottom line it
sits, whether its accidental is already covered by the key signature, and
where the playhead falls. That keeps the renderer testable without a screen.

Spelling is derived from MIDI plus the key signature (sharps for sharp keys,
flats for flat keys). MusicXML's exact spelling is not preserved by the parser
yet; H7b adds that without changing this interface.
"""

from __future__ import annotations

from dataclasses import dataclass

from .score import Score, ScoreNote

LETTERS = "CDEFGAB"
LETTER_STEP = {letter: index for index, letter in enumerate(LETTERS)}
SHARP_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
FLAT_NAMES = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")
SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")

# The bottom line of each staff, counted in diatonic steps from C0.
TREBLE_BOTTOM = 4 * 7 + LETTER_STEP["E"]   # E4
BASS_BOTTOM = 2 * 7 + LETTER_STEP["G"]     # G2


def spell_midi(midi: int, key_fifths: int = 0) -> tuple[str, str, int]:
    """Return (letter, accidental, octave), using sharps or flats by key."""
    names = FLAT_NAMES if key_fifths < 0 else SHARP_NAMES
    name = names[midi % 12]
    letter = name[0]
    accidental = name[1] if len(name) > 1 else ""
    octave = midi // 12 - 1
    return letter, accidental, octave


def _covered_by_key(letter: str, accidental: str, key_fifths: int) -> bool:
    if accidental == "♯" and key_fifths > 0:
        return letter in SHARP_ORDER[:key_fifths]
    if accidental == "♭" and key_fifths < 0:
        return letter in FLAT_ORDER[: abs(key_fifths)]
    return False


def note_spelling(note: ScoreNote, key_fifths: int) -> tuple[str, str, int]:
    """Return (letter, accidental, octave) for a note.

    MusicXML spelling wins when present; MIDI notes fall back to the key's
    sharp/flat convention. A natural sign is emitted when the key signature
    would otherwise apply to the written letter.
    """
    if note.step:
        letter = note.step.upper()
        octave = note.octave
        in_sharp = key_fifths > 0 and letter in SHARP_ORDER[:key_fifths]
        in_flat = key_fifths < 0 and letter in FLAT_ORDER[: abs(key_fifths)]
        if note.alter > 0:
            accidental = "" if in_sharp else "♯" * min(note.alter, 2)
        elif note.alter < 0:
            accidental = "" if in_flat else "♭" * min(-note.alter, 2)
        else:
            accidental = "♮" if (in_sharp or in_flat) else ""
        return letter, accidental, octave

    letter, accidental, octave = spell_midi(note.midi, key_fifths)
    if _covered_by_key(letter, accidental, key_fifths):
        accidental = ""
    return letter, accidental, octave


def staff_step(letter: str, octave: int, staff: str) -> int:
    """Diatonic steps above the staff's bottom line (can be negative)."""
    bottom = BASS_BOTTOM if staff == "bass" else TREBLE_BOTTOM
    return octave * 7 + LETTER_STEP[letter] - bottom


@dataclass(frozen=True)
class StaffNote:
    note: ScoreNote
    staff: str              # "treble" | "bass"
    step: int               # staff steps above the bottom line
    letter: str
    accidental: str         # "" when the key signature already covers it
    octave: int


@dataclass(frozen=True)
class StaffMeasure:
    index: int              # 0-based global measure index
    number: int             # 1-based display number
    notes: tuple[StaffNote, ...]
    beats: float


@dataclass(frozen=True)
class StaffSystem:
    index: int
    measures: tuple[StaffMeasure, ...]
    treble: bool
    bass: bool


@dataclass(frozen=True)
class StaffLayout:
    systems: tuple[StaffSystem, ...]
    notes: tuple[StaffNote, ...]
    measures_per_system: int
    measure_count: int
    beats_per_measure: float
    time_signature: tuple[int, int]
    tempo: float
    key_fifths: int
    treble: bool
    bass: bool

    def playhead(self, seconds: float) -> tuple[int, float]:
        """Map playback seconds to (system index, x fraction within system)."""
        if not self.systems or self.measure_count <= 0:
            return (0, 0.0)
        beats = max(0.0, seconds) * self.tempo / 60.0
        beats = min(beats, self.measure_count * self.beats_per_measure)
        measure = min(
            int(beats // self.beats_per_measure), self.measure_count - 1
        )
        system = measure // self.measures_per_system
        within_measure = (
            beats - measure * self.beats_per_measure
        ) / self.beats_per_measure
        system_measures = max(1, len(self.systems[system].measures))
        x = (
            measure % self.measures_per_system + within_measure
        ) / system_measures
        return (system, max(0.0, min(1.0, x)))


def build_staff_layout(
    score: Score,
    measures_per_system: int = 4,
    split_midi: int = 60,
) -> StaffLayout:
    """Lay a score out as systems of measures on one or two staves."""
    measure_count = max(
        score.measure_count,
        max((note.measure for note in score.notes), default=0),
        0,
    )
    if measure_count <= 0:
        return StaffLayout(
            systems=(),
            notes=(),
            measures_per_system=max(1, measures_per_system),
            measure_count=0,
            beats_per_measure=float(score.time_signature[0]),
            time_signature=score.time_signature,
            tempo=score.tempo,
            key_fifths=score.key_fifths,
            treble=True,
            bass=False,
        )

    bass = any(note.midi < split_midi for note in score.notes)
    treble = any(note.midi >= split_midi for note in score.notes) or not bass
    staff_notes: list[StaffNote] = []
    grouped: dict[int, list[StaffNote]] = {}
    for note in score.notes:
        staff = "bass" if bass and note.midi < split_midi else "treble"
        letter, accidental, octave = note_spelling(note, score.key_fifths)
        item = StaffNote(
            note=note,
            staff=staff,
            step=staff_step(letter, octave, staff),
            letter=letter,
            accidental=accidental,
            octave=octave,
        )
        staff_notes.append(item)
        measure = min(max(note.measure, 1), measure_count)
        grouped.setdefault(measure, []).append(item)

    beats = float(score.time_signature[0])
    measures = [
        StaffMeasure(
            index=index,
            number=index + 1,
            notes=tuple(
                sorted(
                    grouped.get(index + 1, []),
                    key=lambda item: (item.note.beat, item.note.midi),
                )
            ),
            beats=beats,
        )
        for index in range(measure_count)
    ]
    per_system = max(1, int(measures_per_system))
    systems = tuple(
        StaffSystem(
            index=index,
            measures=tuple(measures[start:start + per_system]),
            treble=treble,
            bass=bass,
        )
        for index, start in enumerate(range(0, measure_count, per_system))
    )
    return StaffLayout(
        systems=systems,
        notes=tuple(staff_notes),
        measures_per_system=per_system,
        measure_count=measure_count,
        beats_per_measure=beats,
        time_signature=score.time_signature,
        tempo=score.tempo,
        key_fifths=score.key_fifths,
        treble=treble,
        bass=bass,
    )
