"""Deterministic beginner-score writer: MusicXML + MIDI from note lists.

Melodies are lists of measures; each measure is a list of
`(step, octave, duration_in_quarters)`. This module only writes the file
format the app parses, so generated content is reproducible and testable.
"""

from __future__ import annotations

import struct
from pathlib import Path

STEP_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
TICKS_PER_QUARTER = 480
DIVISIONS = 2  # MusicXML divisions per quarter; eighth = 1, quarter = 2


def _step_semitone(step: str) -> int:
    letter = step[0].upper()
    value = STEP_SEMITONE[letter]
    if step.endswith("#"):
        value += 1
    elif step.endswith("b"):
        value -= 1
    return value


def midi_for(step: str, octave: int) -> int:
    return 12 * (octave + 1) + _step_semitone(step)


def _pitch_xml(step: str, octave: int) -> str:
    letter = step[0].upper()
    alter = 0
    if step.endswith("#"):
        alter = 1
    elif step.endswith("b"):
        alter = -1
    alter_xml = f"<alter>{alter}</alter>" if alter else ""
    return (
        f"<pitch><step>{letter}</step>{alter_xml}"
        f"<octave>{octave}</octave></pitch>"
    )


def _note_type(duration: float) -> str:
    try:
        return {0.5: "eighth", 1: "quarter", 2: "half", 4: "whole"}[duration]
    except KeyError as exc:
        raise ValueError(f"unsupported note duration: {duration}") from exc


def _cell_notes(cell):
    """Return ((step, octave), ...), duration for a note/rest/chord cell.

    A single note or rest is a 3-tuple `(step, octave, duration)`; a chord is
    a 2-tuple `(((step, octave), ...), duration)`. A rest has no notes.
    """
    if len(cell) == 3:
        step, octave, duration = cell
        return (() if step is None else ((step, octave),)), duration
    notes, duration = cell
    return tuple(notes), duration


def validate_measures(measures, beats_per_measure: int = 4) -> None:
    for number, measure in enumerate(measures, start=1):
        beats = sum(_cell_notes(cell)[1] for cell in measure)
        if beats != beats_per_measure:
            raise ValueError(
                f"measure {number}: {beats} quarter beats, "
                f"expected {beats_per_measure}"
            )


def musicxml(
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    measures,
    beats_per_measure: int = 4,
    beat_type: int = 4,
    repeats: dict[int, tuple[bool, bool]] | None = None,
) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">',
        '<score-partwise version="4.0">',
        f"  <work><work-title>{_xml_escape(title)}</work-title></work>",
        "  <identification>",
        f'    <creator type="composer">{_xml_escape(composer)}</creator>',
        f"    <rights>{_xml_escape(rights)}</rights>",
        "    <encoding><software>KeyBorad beginner score generator</software></encoding>",
        "  </identification>",
        "  <part-list>",
        '    <score-part id="P1"><part-name>Piano</part-name></score-part>',
        "  </part-list>",
        '  <part id="P1">',
    ]
    for number, measure in enumerate(measures, start=1):
        lines.append(f'    <measure number="{number}">')
        if number == 1:
            lines.extend(
                [
                    "      <attributes>",
                    f"        <divisions>{DIVISIONS}</divisions>",
                    "        <key><fifths>0</fifths></key>",
                    f"        <time><beats>{beats_per_measure}</beats>"
                    f"<beat-type>{beat_type}</beat-type></time>",
                    "        <clef><sign>G</sign><line>2</line></clef>",
                    "      </attributes>",
                    '      <direction placement="above">',
                    "        <direction-type>",
                    "          <metronome><beat-unit>quarter</beat-unit>"
                    f"<per-minute>{tempo:g}</per-minute></metronome>",
                    "        </direction-type>",
                    f'        <sound tempo="{tempo:g}"/>',
                    "      </direction>",
                ]
            )
        for cell in measure:
            notes, duration = _cell_notes(cell)
            if not notes:
                lines.append(_note_line(None, None, duration))
            else:
                for index, (step, octave) in enumerate(notes):
                    lines.append(
                        _note_line(step, octave, duration, chord=index > 0)
                    )
        forward, backward = (repeats or {}).get(number, (False, False))
        if forward or backward:
            marks = []
            if forward:
                marks.append('<repeat direction="forward"/>')
            if backward:
                marks.append('<repeat direction="backward"/>')
            lines.append("      <barline>" + "".join(marks) + "</barline>")
        lines.append("    </measure>")
    lines.extend(["  </part>", "</score-partwise>", ""])
    return "\n".join(lines)


def midi(
    measures,
    tempo: float,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> bytes:
    events: list[tuple[int, bytes]] = []
    tick = 0
    for measure in measures:
        for cell in measure:
            notes, duration = _cell_notes(cell)
            step_ticks = int(round(duration * TICKS_PER_QUARTER))
            for step, octave in notes:
                note = midi_for(step, octave)
                events.append((tick, bytes([0x90, note, 100])))
                events.append(
                    (tick + step_ticks, bytes([0x80, note, 64]))
                )
            tick += step_ticks

    track = bytearray()
    micros = int(60_000_000 / tempo)
    track += b"\x00\xff\x51\x03" + struct.pack(">I", micros)[1:]
    denominator_power = {2: 1, 4: 2, 8: 3, 16: 4}.get(beat_type, 2)
    track += b"\x00\xff\x58\x04" + bytes(
        [beats_per_measure, denominator_power, 24, 8]
    )
    last = 0
    for absolute, payload in sorted(events, key=lambda item: item[0]):
        track += _vlq(absolute - last)
        track += payload
        last = absolute
    track += b"\x00\xff\x2f\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def validate_two_voice_measures(
    measures, beats_per_measure: int = 4
) -> None:
    for number, (voice1, voice2) in enumerate(measures, start=1):
        for label, voice in (("1", voice1), ("2", voice2)):
            beats = sum(_cell_notes(cell)[1] for cell in voice)
            if beats != beats_per_measure:
                raise ValueError(
                    f"measure {number} voice {label}: {beats} quarter beats, "
                    f"expected {beats_per_measure}"
                )


def _musicxml_head(title: str, composer: str, rights: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">',
        '<score-partwise version="4.0">',
        f"  <work><work-title>{_xml_escape(title)}</work-title></work>",
        "  <identification>",
        f'    <creator type="composer">{_xml_escape(composer)}</creator>',
        f"    <rights>{_xml_escape(rights)}</rights>",
        "    <encoding><software>KeyBorad beginner score generator</software></encoding>",
        "  </identification>",
        "  <part-list>",
        '    <score-part id="P1"><part-name>Piano</part-name></score-part>',
        "  </part-list>",
        '  <part id="P1">',
    ]


def _musicxml_first_measure(
    tempo: float,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> list[str]:
    return [
        "      <attributes>",
        f"        <divisions>{DIVISIONS}</divisions>",
        "        <key><fifths>0</fifths></key>",
        f"        <time><beats>{beats_per_measure}</beats>"
        f"<beat-type>{beat_type}</beat-type></time>",
        "        <clef><sign>G</sign><line>2</line></clef>",
        "      </attributes>",
        '      <direction placement="above">',
        "        <direction-type>",
        "          <metronome><beat-unit>quarter</beat-unit>"
        f"<per-minute>{tempo:g}</per-minute></metronome>",
        "        </direction-type>",
        f'        <sound tempo="{tempo:g}"/>',
        "      </direction>",
    ]


def _note_line(
    step: str | None,
    octave: int | None,
    duration: float,
    voice: str | None = None,
    chord: bool = False,
) -> str:
    voice_xml = f"<voice>{voice}</voice>" if voice else ""
    chord_xml = "<chord/>" if chord else ""
    pitch = (
        "<rest/>"
        if step is None
        else _pitch_xml(step, octave)
    )
    return (
        "      <note>"
        f"{chord_xml}{pitch}"
        f"<duration>{duration * DIVISIONS:g}</duration>"
        f"{voice_xml}"
        f"<type>{_note_type(duration)}</type>"
        "</note>"
    )


def two_voice_musicxml(
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    measures,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> str:
    lines = _musicxml_head(title, composer, rights)
    for number, (voice1, voice2) in enumerate(measures, start=1):
        lines.append(f'    <measure number="{number}">')
        if number == 1:
            lines.extend(
                _musicxml_first_measure(
                    tempo, beats_per_measure, beat_type
                )
            )
        for cell in voice1:
            notes, duration = _cell_notes(cell)
            if not notes:
                lines.append(_note_line(None, None, duration, "1"))
            else:
                for index, (step, octave) in enumerate(notes):
                    lines.append(
                        _note_line(
                            step, octave, duration, "1", chord=index > 0
                        )
                    )
        lines.append(
            f"      <backup><duration>"
            f"{beats_per_measure * DIVISIONS}</duration></backup>"
        )
        for cell in voice2:
            notes, duration = _cell_notes(cell)
            if not notes:
                lines.append(_note_line(None, None, duration, "2"))
            else:
                for index, (step, octave) in enumerate(notes):
                    lines.append(
                        _note_line(
                            step, octave, duration, "2", chord=index > 0
                        )
                    )
        lines.append("    </measure>")
    lines.extend(["  </part>", "</score-partwise>", ""])
    return "\n".join(lines)


def two_voice_midi(
    measures,
    tempo: float,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> bytes:
    events: list[tuple[int, bytes]] = []
    measure_tick = 0
    for voice1, voice2 in measures:
        for voice in (voice1, voice2):
            local = 0
            for cell in voice:
                notes, duration = _cell_notes(cell)
                step_ticks = int(round(duration * TICKS_PER_QUARTER))
                for step, octave in notes:
                    note = midi_for(step, octave)
                    start = measure_tick + local
                    events.append((start, bytes([0x90, note, 100])))
                    events.append(
                        (start + step_ticks, bytes([0x80, note, 64]))
                    )
                local += step_ticks
        measure_tick += beats_per_measure * TICKS_PER_QUARTER

    track = bytearray()
    micros = int(60_000_000 / tempo)
    track += b"\x00\xff\x51\x03" + struct.pack(">I", micros)[1:]
    denominator_power = {2: 1, 4: 2, 8: 3, 16: 4}.get(beat_type, 2)
    track += b"\x00\xff\x58\x04" + bytes(
        [beats_per_measure, denominator_power, 24, 8]
    )
    last = 0
    for absolute, payload in sorted(events, key=lambda item: item[0]):
        track += _vlq(absolute - last)
        track += payload
        last = absolute
    track += b"\x00\xff\x2f\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def write_two_voice_score(
    out_dir: Path,
    stem: str,
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    measures,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> tuple[Path, Path]:
    validate_two_voice_measures(measures, beats_per_measure)
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = out_dir / f"{stem}.musicxml"
    mid_path = out_dir / f"{stem}.mid"
    xml_path.write_text(
        two_voice_musicxml(
            title,
            composer,
            rights,
            tempo,
            measures,
            beats_per_measure,
            beat_type,
        ),
        encoding="utf-8",
    )
    mid_path.write_bytes(
        two_voice_midi(measures, tempo, beats_per_measure, beat_type)
    )
    return xml_path, mid_path


def duet_musicxml(
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    melody,
    accompaniment,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> str:
    """Two separate MusicXML parts: P1 melody (treble), P2 left hand (bass).

    Separate parts (not voices) let the app declare ``accompaniment="P2"`` and
    auto-play exactly that part. Both parts declare their own divisions.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">',
        '<score-partwise version="4.0">',
        f"  <work><work-title>{_xml_escape(title)}</work-title></work>",
        "  <identification>",
        f'    <creator type="composer">{_xml_escape(composer)}</creator>',
        f"    <rights>{_xml_escape(rights)}</rights>",
        "    <encoding><software>KeyBorad beginner score generator</software></encoding>",
        "  </identification>",
        "  <part-list>",
        '    <score-part id="P1"><part-name>Right Hand</part-name></score-part>',
        '    <score-part id="P2"><part-name>Left Hand</part-name></score-part>',
        "  </part-list>",
    ]
    for part_id, measures, clef in (
        ("P1", melody, ("G", 2)),
        ("P2", accompaniment, ("F", 4)),
    ):
        lines.append(f'  <part id="{part_id}">')
        for number, measure in enumerate(measures, start=1):
            lines.append(f'    <measure number="{number}">')
            if number == 1:
                lines.extend(
                    [
                        "      <attributes>",
                        f"        <divisions>{DIVISIONS}</divisions>",
                        "        <key><fifths>0</fifths></key>",
                        f"        <time><beats>{beats_per_measure}</beats>"
                        f"<beat-type>{beat_type}</beat-type></time>",
                        f"        <clef><sign>{clef[0]}</sign>"
                        f"<line>{clef[1]}</line></clef>",
                        "      </attributes>",
                    ]
                )
                if part_id == "P1":
                    lines.extend(
                        [
                            '      <direction placement="above">',
                            "        <direction-type>",
                            "          <metronome><beat-unit>quarter</beat-unit>"
                            f"<per-minute>{tempo:g}</per-minute></metronome>",
                            "        </direction-type>",
                            f'        <sound tempo="{tempo:g}"/>',
                            "      </direction>",
                        ]
                    )
            for cell in measure:
                notes, duration = _cell_notes(cell)
                if not notes:
                    lines.append(_note_line(None, None, duration))
                else:
                    for index, (step, octave) in enumerate(notes):
                        lines.append(
                            _note_line(step, octave, duration, chord=index > 0)
                        )
            lines.append("    </measure>")
        lines.append("  </part>")
    lines.extend(["</score-partwise>", ""])
    return "\n".join(lines)


def write_duet_score(
    out_dir: Path,
    stem: str,
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    melody,
    accompaniment,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> tuple[Path, Path]:
    validate_measures(melody, beats_per_measure)
    validate_measures(accompaniment, beats_per_measure)
    if len(melody) != len(accompaniment):
        raise ValueError("melody and accompaniment must have equal measures")
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = out_dir / f"{stem}.musicxml"
    mid_path = out_dir / f"{stem}.mid"
    xml_path.write_text(
        duet_musicxml(
            title,
            composer,
            rights,
            tempo,
            melody,
            accompaniment,
            beats_per_measure,
            beat_type,
        ),
        encoding="utf-8",
    )
    mid_path.write_bytes(
        two_voice_midi(
            tuple(zip(melody, accompaniment)),
            tempo,
            beats_per_measure,
            beat_type,
        )
    )
    return xml_path, mid_path


def write_score(
    out_dir: Path,
    stem: str,
    title: str,
    composer: str,
    rights: str,
    tempo: float,
    measures,
    beats_per_measure: int = 4,
    beat_type: int = 4,
) -> tuple[Path, Path]:
    validate_measures(measures, beats_per_measure)
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = out_dir / f"{stem}.musicxml"
    mid_path = out_dir / f"{stem}.mid"
    xml_path.write_text(
        musicxml(
            title,
            composer,
            rights,
            tempo,
            measures,
            beats_per_measure,
            beat_type,
        ),
        encoding="utf-8",
    )
    mid_path.write_bytes(
        midi(measures, tempo, beats_per_measure, beat_type)
    )
    return xml_path, mid_path


def _vlq(value: int) -> bytes:
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
