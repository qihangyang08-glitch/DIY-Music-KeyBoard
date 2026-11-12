"""Minimal MusicXML / Standard MIDI File parser for the P2 follow slice.

No third-party parser is installed on this machine, so this module implements
the subset the app needs today:

- MusicXML partwise: every part's divisions, time, key, tempo
  (`<sound tempo>`), notes, rests, chords, backup/forward; ties are merged
  into one note, and repeats/endings are unrolled into performance order.
- MIDI format 0/1 with PPQ timing: note on/off, set_tempo, time signature,
  key signature. SMPTE time division is rejected.

Both produce the same `Score` of absolute-time notes. The piano-roll and the
follow engine only depend on that model, so a later music21/mido swap can
replace the parsers without touching the UI.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path

from .note_engine import midi_name


class ScoreError(Exception):
    """A user-facing parse error (Chinese message)."""


@dataclass(frozen=True)
class ScoreNote:
    midi: int
    start: float          # seconds
    duration: float       # seconds
    measure: int
    beat: float           # 1-based beat inside the measure
    part: str = "P1"
    voice: str = ""
    # Exact MusicXML spelling when available (MIDI leaves these empty).
    step: str = ""
    alter: int = 0
    octave: int = 0

    @property
    def end(self) -> float:
        return self.start + self.duration

    @property
    def name(self) -> str:
        return midi_name(self.midi)


@dataclass
class Score:
    title: str
    composer: str
    rights: str
    tempo: float
    time_signature: tuple[int, int]
    notes: list[ScoreNote]
    duration: float
    source: str
    format: str
    measure_count: int = 0     # authoritative for MusicXML; 0 -> derive
    key_fifths: int = 0        # negative = flats, positive = sharps

    @property
    def min_midi(self) -> int:
        return min(note.midi for note in self.notes) if self.notes else 60

    @property
    def max_midi(self) -> int:
        return max(note.midi for note in self.notes) if self.notes else 72

    @property
    def bars_per_measure(self) -> float:
        return float(self.time_signature[0])

    def first_note_after(self, seconds: float) -> ScoreNote | None:
        for note in self.notes:
            if note.start >= seconds - 1e-6:
                return note
        return None


def excerpt_score(score: Score, measures: int = 4) -> Score:
    """The first ``measures`` measures, for a short visual snippet.

    Returns the original score unchanged when nothing would be cut, so
    callers can use it without copying long pieces needlessly.
    """
    count = max(1, int(measures))
    notes = [note for note in score.notes if note.measure <= count]
    if len(notes) == len(score.notes):
        return score
    duration = max((note.end for note in notes), default=0.0)
    return replace(score, notes=notes, duration=duration, measure_count=count)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element, name: str):
    return [child for child in element if _local(child.tag) == name]


def _first(element, name: str):
    for child in element.iter():
        if _local(child.tag) == name:
            return child
    return None


def _text(element, name: str, default: str = "") -> str:
    child = _first(element, name)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _step_semitone(step: str) -> int:
    return {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(
        step.upper(), 0
    )


def _seconds_from_beats(beat: float, tempo_events: list[tuple[float, float]]) -> float:
    events = sorted(tempo_events) or [(0.0, 120.0)]
    if events[0][0] > 0:
        events.insert(0, (0.0, events[0][1]))
    seconds = 0.0
    previous = 0.0
    bpm = events[0][1]
    for position, value in events:
        if position > beat:
            break
        seconds += (position - previous) * 60.0 / bpm
        previous = position
        bpm = value
    seconds += (beat - previous) * 60.0 / bpm
    return seconds


def _tie_marks(note_element) -> tuple[set[str], set[str]]:
    """Return (start_numbers, stop_numbers) for one MusicXML note.

    The sounding ``<tie>`` wins when present; notation-only exporters use
    ``<notations><tied>`` instead. Numbers default to "1" so ordinary ties do
    not need the attribute.
    """
    direct = [
        child
        for child in note_element
        if _local(child.tag) == "tie"
        and (child.get("type") or "").lower()
        in ("start", "stop", "continue")
    ]
    markers = direct
    if not markers:
        for child in note_element:
            if _local(child.tag) != "notations":
                continue
            markers.extend(
                item for item in child.iter() if _local(item.tag) == "tied"
            )
    starts: set[str] = set()
    stops: set[str] = set()
    for item in markers:
        kind = (item.get("type") or "").lower()
        number = (item.get("number") or "1").strip() or "1"
        if kind in ("start", "continue"):
            starts.add(number)
        if kind in ("stop", "continue"):
            stops.add(number)
    return starts, stops


def _merge_ties(
    specs: list[tuple],
    marks: list[tuple[set[str], set[str]]],
    segments: list[int],
) -> list[tuple]:
    """Fold each tie chain into one note with the summed beat duration.

    Ties never cross a repeat jump: ``segments`` separates each pass of a
    repeated section, so a dangling start before the jump cannot fuse with an
    unrelated stop after it. A tie leaving the final pass may still continue
    into the following measure, which is normal notation.
    """
    open_ties: dict[tuple[str, str, int, str, int], int] = {}
    alive = [True] * len(specs)
    for index, spec in enumerate(specs):
        midi, start, duration = spec[0], spec[1], spec[2]
        part, voice = spec[5], spec[6]
        segment = segments[index] if index < len(segments) else 0
        starts, stops = marks[index] if index < len(marks) else (set(), set())
        head = None
        for number in sorted(stops):
            pending = open_ties.pop(
                (part, voice, midi, number, segment), None
            )
            if pending is None:
                continue
            first = specs[pending]
            if abs(start - (first[1] + first[2])) > 1e-6:
                continue  # a rest/forward broke the tie; keep both notes
            specs[pending] = first[:2] + (first[2] + duration,) + first[3:]
            alive[index] = False
            if head is None:
                head = pending
        if head is None:
            head = index
        for number in sorted(starts):
            open_ties[(part, voice, midi, number, segment)] = head
    return [spec for spec, keep in zip(specs, alive) if keep]


def _repeat_times(element) -> int:
    text = element.get("times")
    if text is None:
        return 2
    try:
        value = int(text)
    except (TypeError, ValueError):
        return 2
    if value <= 0:
        return 2
    return min(32, value)


def _ending_numbers(element) -> set[int]:
    raw = element.get("number") or ""
    numbers: set[int] = set()
    for token in raw.replace(",", " ").split():
        try:
            numbers.add(int(token))
        except ValueError:
            continue
    return numbers


def _measure_markers(
    measure,
) -> tuple[list[str], tuple[int, str] | None, list[tuple[str, set[int]]]]:
    """Return (forward locations, (backward_times, location), endings).

    ``barline location`` matters on both sides: a forward repeat on a right
    barline starts at the following measure, and a backward repeat on a left
    barline ends before this measure. The empty location means the marker was
    written directly under the measure (tests/legacy files).
    """
    forwards: list[str] = []
    backward: tuple[int, str] | None = None
    endings: list[tuple[str, set[int]]] = []

    def eat(item, location: str) -> None:
        nonlocal backward
        tag = _local(item.tag)
        if tag == "repeat":
            direction = (item.get("direction") or "").lower()
            if direction == "forward":
                forwards.append(location)
            elif direction == "backward":
                backward = (_repeat_times(item), location)
        elif tag == "ending":
            kind = (item.get("type") or "").lower()
            numbers = _ending_numbers(item)
            if kind == "start":
                endings.append(("start", numbers or {1}))
            elif kind in ("stop", "discontinue"):
                endings.append(("stop", numbers))

    for barline in _children(measure, "barline"):
        location = (barline.get("location") or "").lower()
        for item in barline.iter():
            eat(item, location)
    # Be liberal with files that omit <barline> around repeat/ending.
    for item in _children(measure, "repeat"):
        eat(item, "")
    for item in _children(measure, "ending"):
        eat(item, "")
    return forwards, backward, endings


@dataclass(frozen=True)
class _RepeatSection:
    id: int
    start: int
    end: int
    times: int


@dataclass(frozen=True)
class _EndingSpan:
    start: int
    end: int
    numbers: frozenset[int]
    section: int | None


def _repeat_sections(
    markers: list[
        tuple[list[str], tuple[int, str] | None, list[tuple[str, set[int]]]]
    ],
) -> list[_RepeatSection]:
    sections: list[_RepeatSection] = []
    stack: list[int] = []
    for index, (forwards, backward, _endings) in enumerate(markers):
        left = [
            location
            for location in forwards
            if location == "left" or (not location and backward is None)
        ]
        right = [
            location
            for location in forwards
            if location == "right" or (not location and backward is not None)
        ]
        # |: ... :| in one measure opens on its left barline first.
        for _location in left:
            stack.append(index)
        if backward is not None:
            times, location = backward
            start = stack.pop() if stack else 0
            end = index - 1 if location == "left" else index
            if times > 1 and start <= end:
                sections.append(
                    _RepeatSection(len(sections) + 1, start, end, times)
                )
        # A :||: joint barline opens the next section after this measure.
        for _location in right:
            stack.append(index + 1)
    return sections


def _ending_spans(
    markers: list[
        tuple[list[str], tuple[int, str] | None, list[tuple[str, set[int]]]]
    ],
    sections: list[_RepeatSection],
) -> list[_EndingSpan]:
    open_spans: list[tuple[int, set[int]]] = []
    raw_spans: list[tuple[int, int, set[int]]] = []
    last = max(0, len(markers) - 1)
    for index, (_forward, _backward, endings) in enumerate(markers):
        for kind, numbers in endings:
            if kind == "start":
                open_spans.append((index, numbers))
            elif open_spans:
                position = len(open_spans) - 1
                if numbers:
                    for candidate in range(len(open_spans) - 1, -1, -1):
                        if open_spans[candidate][1] & numbers:
                            position = candidate
                            break
                start, span_numbers = open_spans.pop(position)
                raw_spans.append((start, index, span_numbers))
    for start, numbers in open_spans:
        raw_spans.append((start, last, numbers))

    spans: list[_EndingSpan] = []
    for start, end, numbers in raw_spans:
        # A second ending lies after its repeat's backward barline; attach it
        # to the nearest section that has already ended, not to an enclosing
        # repeat. This keeps nested alternatives on the inner pass counter.
        candidates = [
            section
            for section in sections
            if section.start <= start and section.end <= end
        ]
        owner = (
            max(candidates, key=lambda section: (section.end, section.start)).id
            if candidates
            else None
        )
        spans.append(_EndingSpan(start, end, frozenset(numbers), owner))
    return spans


def _active_spans(
    owned: list[_EndingSpan], pass_no: int
) -> set[int]:
    """Ending spans that sound on this pass (numbered passes only)."""
    return {id(span) for span in owned if pass_no in span.numbers}


def _measure_play_order(
    measures,
) -> tuple[list[int], list[int]]:
    """Unroll repeats into (measure order, tie segment per occurrence).

    A new segment starts at every repeat-section entry/pass, so tie merging
    cannot cross a backward jump. Measures after a section keep its last
    segment, allowing a final-pass tie to continue into the following bar.
    """
    count = len(measures)
    if count == 0:
        return ([], [])
    markers = [_measure_markers(measure) for measure in measures]
    if not any(
        forwards or backward is not None or endings
        for forwards, backward, endings in markers
    ):
        return (list(range(count)), [0] * count)

    sections = _repeat_sections(markers)
    if not sections:
        return (list(range(count)), [0] * count)
    spans = _ending_spans(markers, sections)

    effective_end = {
        section.id: max(
            [section.end]
            + [
                span.end
                for span in spans
                if span.section == section.id
            ]
        )
        for section in sections
    }

    children: dict[int, list[_RepeatSection]] = {
        section.id: [] for section in sections
    }
    roots: list[_RepeatSection] = []
    for section in sections:
        parents = [
            candidate
            for candidate in sections
            if candidate.id != section.id
            and candidate.start <= section.start
            and effective_end[section.id] <= candidate.end
        ]
        if parents:
            parent = max(
                parents, key=lambda candidate: (candidate.start, candidate.end)
            )
            children[parent.id].append(section)
        else:
            roots.append(section)

    child_at = {
        section_id: {child.start: child for child in kids}
        for section_id, kids in children.items()
    }
    root_at = {}
    for section in sorted(roots, key=lambda item: item.start):
        root_at.setdefault(section.start, section)
    spans_by_section = {
        section.id: [span for span in spans if span.section == section.id]
        for section in sections
    }

    order: list[int] = []
    segments: list[int] = []
    segment = 0
    limit = max(4096, 256 * count)

    def new_segment() -> None:
        nonlocal segment
        segment += 1

    def emit(index: int) -> None:
        order.append(index)
        segments.append(segment)
        if len(order) > limit:
            raise ScoreError("反复记号过多，无法展开（可能存在循环）。")

    def expand_section(section: _RepeatSection, depth: int = 0) -> None:
        if depth > 64:
            raise ScoreError("反复嵌套过深，无法展开。")
        end = effective_end[section.id]
        owned = spans_by_section.get(section.id, [])
        covering: dict[int, list[_EndingSpan]] = {}
        for span in owned:
            for index in range(span.start, span.end + 1):
                covering.setdefault(index, []).append(span)
        kids = child_at.get(section.id, {})
        for pass_no in range(1, section.times + 1):
            if pass_no > 1:
                new_segment()  # a backward jump breaks any open tie
            active = _active_spans(owned, pass_no)
            index = section.start
            while index <= end:
                child = kids.get(index)
                if (
                    child is not None
                    and effective_end[child.id] <= end
                ):
                    expand_section(child, depth + 1)
                    index = effective_end[child.id] + 1
                    continue
                at_measure = covering.get(index)
                if at_measure and not any(
                    id(span) in active for span in at_measure
                ):
                    index += 1
                    continue
                emit(index)
                index += 1

    def expand_range(start: int, stop: int) -> None:
        index = start
        while index <= stop:
            child = root_at.get(index)
            if child is not None:
                expand_section(child)
                index = effective_end[child.id] + 1
            else:
                emit(index)
                index += 1

    expand_range(0, count - 1)
    return (order, segments)


def _make_score(
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    time_signature: tuple[int, int],
    specs: list[tuple[int, float, float, int, float, str, str, str, int, int]],
    tempo_events: list[tuple[float, float]],
    source: Path,
    fmt: str,
    measure_count: int = 0,
    key_fifths: int = 0,
) -> Score:
    notes: list[ScoreNote] = []
    for (
        midi,
        start_beat,
        duration_beat,
        measure,
        beat,
        part,
        voice,
        step,
        alter,
        octave,
    ) in specs:
        start = _seconds_from_beats(start_beat, tempo_events)
        end = _seconds_from_beats(start_beat + duration_beat, tempo_events)
        notes.append(
            ScoreNote(
                midi=midi,
                start=start,
                duration=max(0.01, end - start),
                measure=measure,
                beat=beat,
                part=part,
                voice=voice,
                step=step,
                alter=alter,
                octave=octave,
            )
        )
    notes.sort(key=lambda note: (note.start, note.midi))
    duration = max((note.end for note in notes), default=0.0)
    if not notes:
        raise ScoreError("谱子里没有可播放的音符。")
    return Score(
        title=title or source.stem,
        composer=composer or "—",
        rights=rights or "未标注",
        tempo=tempo,
        time_signature=time_signature,
        notes=notes,
        duration=duration,
        source=str(source),
        format=fmt,
        measure_count=measure_count,
        key_fifths=key_fifths,
    )


# ---------------------------------------------------------------------------
# MusicXML
# ---------------------------------------------------------------------------


def _musicxml_root(path: Path):
    import xml.etree.ElementTree as ET
    import zipfile

    try:
        if path.suffix.lower() == ".mxl":
            with zipfile.ZipFile(path) as archive:
                names = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".xml")
                    and not name.upper().startswith("META-INF/")
                ]
                if not names:
                    raise ScoreError("MXL 压缩包里没有 MusicXML。")
                name = max(names, key=lambda item: archive.getinfo(item).file_size)
                return ET.fromstring(archive.read(name))
        return ET.parse(path).getroot()
    except ScoreError:
        raise
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise ScoreError(f"无法读取 MusicXML：{exc}") from exc


def parse_musicxml(path: Path) -> Score:
    root = _musicxml_root(path)

    title = _text(root, "work-title") or _text(root, "movement-title")
    composer = ""
    rights = _text(root, "rights")
    for element in root.iter():
        if _local(element.tag) == "creator" and element.get("type") == "composer":
            composer = (element.text or "").strip()
            break

    parts = _children(root, "part")
    if not parts:
        raise ScoreError("MusicXML 里没有 part。")
    divisions = 1
    time_signature = (4, 4)
    key_fifths = 0
    specs: list[
        tuple[int, float, float, int, float, str, str, str, int, int]
    ] = []
    tempo_events: list[tuple[float, float]] = []
    default_tempo = 120.0
    measure_count = 0
    marks: list[tuple[set[str], set[str]]] = []
    spec_segments: list[int] = []

    # Every part starts at beat 0. The first part supplies the global time
    # signature/key; later parts contribute notes and any tempo marks.
    for part_index, part in enumerate(parts):
        part_id = part.get("id", f"P{part_index + 1}")
        divisions = 1
        position = 0.0             # in beats, across this part
        last_note_start = 0.0
        measure_elements = _children(part, "measure")
        play_order, play_segments = _measure_play_order(measure_elements)
        expanded = len(play_order) != len(measure_elements)
        measure_count = max(measure_count, len(play_order))

        for occurrence, (source_index, segment) in enumerate(
            zip(play_order, play_segments), start=1
        ):
            measure = measure_elements[source_index]
            measure_start = position
            if expanded:
                number = occurrence
            else:
                try:
                    number = int(
                        measure.get("number", source_index + 1)
                    )
                except ValueError:
                    number = source_index + 1

            for child in measure:
                name = _local(child.tag)
                if name == "attributes":
                    div_text = _text(child, "divisions")
                    if div_text:
                        try:
                            divisions = max(1, int(div_text))
                        except ValueError:
                            pass
                    if part_index:
                        continue
                    time = _first(child, "time")
                    if time is not None:
                        beats = _text(time, "beats", "4")
                        beat_type = _text(time, "beat-type", "4")
                        try:
                            time_signature = (int(beats), int(beat_type))
                        except ValueError:
                            pass
                    key = _first(child, "key")
                    if key is not None:
                        fifths_text = _text(key, "fifths", "")
                        if fifths_text:
                            try:
                                key_fifths = max(
                                    -7, min(7, int(fifths_text))
                                )
                            except ValueError:
                                pass
                elif name in ("direction", "sound"):
                    # Tempo is carried by <sound tempo="..."> at this position;
                    # fall back to a metronome mark when only <per-minute>
                    # exists.
                    found_tempo = False
                    for element in child.iter():
                        if _local(element.tag) != "sound":
                            continue
                        tempo_text = element.get("tempo")
                        if tempo_text:
                            try:
                                bpm = float(tempo_text)
                            except ValueError:
                                continue
                            default_tempo = bpm
                            tempo_events.append((position, bpm))
                            found_tempo = True
                    if not found_tempo:
                        per_minute = _first(child, "per-minute")
                        if per_minute is not None and per_minute.text:
                            try:
                                bpm = float(per_minute.text)
                            except ValueError:
                                bpm = 0.0
                            if bpm > 0:
                                default_tempo = bpm
                                tempo_events.append((position, bpm))
                elif name == "backup":
                    try:
                        position -= (
                            int(_text(child, "duration", "0")) / divisions
                        )
                    except ValueError:
                        pass
                elif name == "forward":
                    try:
                        position += (
                            int(_text(child, "duration", "0")) / divisions
                        )
                    except ValueError:
                        pass
                elif name == "note":
                    duration_text = _text(child, "duration", "0")
                    try:
                        duration = int(duration_text) / divisions
                    except ValueError:
                        duration = 0.0
                    if _first(child, "grace") is not None:
                        continue
                    is_chord = _first(child, "chord") is not None
                    is_rest = _first(child, "rest") is not None
                    start = last_note_start if is_chord else position
                    if not is_chord:
                        position += duration
                    if is_rest or duration <= 0:
                        continue
                    pitch = _first(child, "pitch")
                    if pitch is None:
                        continue
                    step = _text(pitch, "step", "C")
                    octave_text = _text(pitch, "octave", "4")
                    try:
                        octave = int(octave_text)
                    except ValueError:
                        octave = 4
                    alter_text = _text(pitch, "alter", "0")
                    try:
                        alter = int(float(alter_text))
                    except ValueError:
                        alter = 0
                    midi = 12 * (octave + 1) + _step_semitone(step) + alter
                    voice = _text(child, "voice", "")
                    specs.append(
                        (
                            midi,
                            start,
                            duration,
                            number,
                            start - measure_start + 1.0,
                            part_id,
                            voice,
                            step,
                            alter,
                            octave,
                        )
                    )
                    marks.append(_tie_marks(child))
                    spec_segments.append(segment)
                    if not is_chord:
                        last_note_start = start

    specs = _merge_ties(specs, marks, spec_segments)
    if not tempo_events:
        tempo_events = [(0.0, default_tempo)]
    tempo = sorted(tempo_events)[0][1]
    return _make_score(
        title=title,
        composer=composer,
        rights=rights,
        tempo=tempo,
        time_signature=time_signature,
        specs=specs,
        tempo_events=tempo_events,
        source=path,
        fmt="MusicXML",
        measure_count=measure_count,
        key_fifths=key_fifths,
    )


# ---------------------------------------------------------------------------
# Standard MIDI File
# ---------------------------------------------------------------------------


def _vlq(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, index


def parse_midi(path: Path) -> Score:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ScoreError(f"无法读取 MIDI：{exc}") from exc
    if len(data) < 14 or data[:4] != b"MThd":
        raise ScoreError("不是标准 MIDI 文件。")
    header_len = struct.unpack(">I", data[4:8])[0]
    fmt, tracks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise ScoreError("暂不支持 SMPTE 时间格式的 MIDI。")
    if division == 0:
        raise ScoreError("MIDI 的 PPQ 为 0。")

    index = 8 + header_len
    tempo_events: list[tuple[int, float]] = []
    time_signature = (4, 4)
    key_fifths = 0
    note_spans: list[tuple[int, int, int]] = []  # start tick, end tick, midi
    title = path.stem
    end_tick = 0

    for _ in range(tracks):
        if index + 8 > len(data) or data[index:index + 4] != b"MTrk":
            break
        length = struct.unpack(">I", data[index + 4:index + 8])[0]
        track = data[index + 8:index + 8 + length]
        index += 8 + length
        cursor = 0
        tick = 0
        running = None
        active: dict[tuple[int, int], int] = {}

        while cursor < len(track):
            delta, cursor = _vlq(track, cursor)
            tick += delta
            end_tick = max(end_tick, tick)
            if cursor >= len(track):
                break
            status = track[cursor]
            if status < 0x80:
                if running is None:
                    raise ScoreError("MIDI running status 没有前置状态。")
                status = running
            else:
                cursor += 1
                running = status

            if status == 0xFF:
                running = None
                meta = track[cursor]
                cursor += 1
                meta_len, cursor = _vlq(track, cursor)
                payload = track[cursor:cursor + meta_len]
                cursor += meta_len
                if meta == 0x51 and meta_len == 3:
                    microseconds = int.from_bytes(payload, "big")
                    if microseconds:
                        tempo_events.append((tick, 60_000_000 / microseconds))
                elif meta == 0x58 and meta_len >= 2:
                    time_signature = (payload[0], 2 ** payload[1])
                elif meta == 0x59 and meta_len >= 1:
                    sf = payload[0]
                    key_fifths = sf - 256 if sf >= 128 else sf
                    key_fifths = max(-7, min(7, key_fifths))
                elif meta == 0x03 and payload:
                    try:
                        title = payload.decode("utf-8")
                    except UnicodeDecodeError:
                        pass
                elif meta == 0x2F:
                    break
                continue

            if status in (0xF0, 0xF7):
                running = None
                meta_len, cursor = _vlq(track, cursor)
                cursor += meta_len
                continue
            if status >= 0xF0:
                # System common/realtime: not used in files.
                continue

            event = status & 0xF0
            channel = status & 0x0F
            if event in (0x80, 0x90):
                note = track[cursor]
                velocity = track[cursor + 1]
                cursor += 2
                key = (channel, note)
                if event == 0x90 and velocity > 0:
                    if key in active:
                        note_spans.append((active.pop(key), tick, note))
                    active[key] = tick
                else:
                    start = active.pop(key, None)
                    if start is not None:
                        note_spans.append((start, tick, note))
            elif event in (0xA0, 0xB0, 0xE0):
                cursor += 2
            elif event in (0xC0, 0xD0):
                cursor += 1
            else:
                break
        for (channel, note), start in active.items():
            note_spans.append((start, end_tick, note))

    if not note_spans:
        raise ScoreError("MIDI 里没有音符。")
    if not tempo_events:
        tempo_events = [(0, 120.0)]
    beats_per_measure = max(1, time_signature[0])
    specs: list[
        tuple[int, float, float, int, float, str, str, str, int, int]
    ] = []
    for start_tick, stop_tick, midi in note_spans:
        start_beat = start_tick / division
        stop_beat = stop_tick / division
        measure = int(start_beat // beats_per_measure) + 1
        beat = start_beat % beats_per_measure + 1.0
        specs.append(
            (
                midi,
                start_beat,
                stop_beat - start_beat,
                measure,
                beat,
                "P1",
                "",
                "",
                0,
                0,
            )
        )
    tempo = sorted(tempo_events)[0][1]
    return _make_score(
        title=title,
        composer="—",
        rights="未标注",
        tempo=tempo,
        time_signature=time_signature,
        specs=specs,
        tempo_events=[(tick / division, bpm) for tick, bpm in tempo_events],
        source=path,
        fmt="MIDI",
        measure_count=max((spec[3] for spec in specs), default=0),
        key_fifths=key_fifths,
    )


def parse_score(path: str | Path) -> Score:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".musicxml", ".mxl", ".xml"):
        return parse_musicxml(path)
    if suffix in (".mid", ".midi"):
        return parse_midi(path)
    raise ScoreError(f"暂不支持 {suffix or '该文件'}；请使用 MusicXML 或 MIDI。")
