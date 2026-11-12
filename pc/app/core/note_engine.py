"""
KeyBorad PC-side note engine (absorbed from the 2026-10-24 prototype).

Turns the firmware's "keys: ..." channel mask into MIDI note-on/note-off
events: press/release edges, chords, glissando, repeats, octave/transpose,
and note-off grace timing.

This module is pure logic: no serial port, no audio, no files. Feed it Frames
and it returns NoteEvents. The prototype validated this behaviour in a
hardware session (pc/prototype/NOTES.md: 14/14 PASS); the P1 app reuses it
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
BLACK_KEY_CLASSES = frozenset({1, 3, 6, 8, 10})


def is_black_key(midi: int) -> bool:
    """True for the five black-key pitch classes (used by light-bar hints)."""
    return midi % 12 in BLACK_KEY_CLASSES


def midi_name(midi: int) -> str:
    """MIDI number -> scientific pitch name (60 = C4)."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


@dataclass
class Frame:
    """One observation of the instrument at time `t` (host monotonic seconds)."""

    t: float
    active: set[int] = field(default_factory=set)  # 1-based channels
    dev_ms: Optional[int] = None                   # firmware's own timestamp
    modules: dict[int, bool] = field(default_factory=dict)  # addr -> answering
    raw: str = ""


@dataclass
class NoteEvent:
    """A MIDI-shaped event with enough context to explain itself in a log."""

    t: float
    kind: str                 # "on" / "off"
    key: int                  # layout key, 1..32
    channel: int              # MPR121 channel, 1..36
    midi: int
    velocity: int
    note: str
    reason: str = "press"
    held_ms: Optional[float] = None
    gliss_from: Optional[int] = None
    gliss_gap_ms: Optional[float] = None
    repeat: bool = False
    short: bool = False


MIN_OCTAVE = -2
MAX_OCTAVE = 2


@dataclass
class EngineConfig:
    octave: int = 0            # in octaves, MIN_OCTAVE..MAX_OCTAVE
    transpose: int = 0         # in semitones, -12..+12
    velocity: int = 100        # firmware v1 is binary: no pressure to map yet
    release_grace_ms: float = 20.0
    gliss_window_ms: float = 120.0
    repeat_window_ms: float = 500.0
    gliss_legato: bool = False
    min_note_ms: float = 25.0

    @property
    def offset(self) -> int:
        return self.octave * 12 + self.transpose


@dataclass
class _Voice:
    key: int
    channel: int
    midi: int
    velocity: int
    note: str
    on_t: float
    release_t: Optional[float] = None
    off_deadline: Optional[float] = None


class NoteEngine:
    """Channel masks in, note events out.

    Semantics implemented (and deliberately visible in the logs):

    - A rising edge emits note-on; a falling edge emits note-off.
    - Note-off is delayed by `release_grace_ms` so a 20 ms poll gap in the
      middle of a slide does not chop the sound. Releasing and re-pressing the
      same key inside that window still produces off -> on (a repeat).
    - If a new key is pressed while an old note is still inside its grace
      window, `gliss_legato=False` sends the old off first (piano articulation)
      and `True` sends the new on first (overlap/legato).
    - Pressing several keys at once is a chord: one voice per key, no stealing.
    - The transpose/octave offset is applied at press time. Held notes are not
      retuned; the caller warns about that.
    """

    def __init__(self, keymap: dict[int, dict], config: Optional[EngineConfig] = None):
        self.keymap = keymap
        self.cfg = config or EngineConfig()
        self.voices: dict[int, _Voice] = {}
        self.mask: set[int] = set()
        self.last_off: dict[int, float] = {}
        self._recent_releases: list[tuple[float, int]] = []  # (t, key)
        self.skipped = 0
        self.unknown_channels: set[int] = set()
        self.max_polyphony = 0

    # -- observation ------------------------------------------------------

    def polyphony(self) -> int:
        return len(self.voices)

    def active_list(self) -> list[_Voice]:
        return sorted(self.voices.values(), key=lambda v: v.key)

    def offset(self) -> int:
        return self.cfg.offset

    # -- configuration ----------------------------------------------------

    def set_octave(self, octave: int) -> int:
        self.cfg.octave = max(MIN_OCTAVE, min(MAX_OCTAVE, int(octave)))
        return self.cfg.octave

    def set_transpose(self, semitones: int) -> int:
        self.cfg.transpose = max(-12, min(12, int(semitones)))
        return self.cfg.transpose

    def set_legato(self, on: bool) -> bool:
        self.cfg.gliss_legato = bool(on)
        return self.cfg.gliss_legato

    # -- frame processing -------------------------------------------------

    def update(self, frame: Frame) -> list[NoteEvent]:
        now = frame.t
        active = set(frame.active) & set(self.keymap)
        for ch in frame.active:
            if ch not in self.keymap:
                self.unknown_channels.add(ch)

        pressed = sorted(active - self.mask)
        released = sorted(self.mask - active)
        events: list[NoteEvent] = []

        # Keys leaving in this same frame. They are still in self.voices at
        # this point, so collect their layout keys before the press loop so a
        # slide where one finger lands as the other lifts can be recognised.
        released_info: list[tuple[int, int]] = []
        for ch in released:
            voice = self.voices.get(ch)
            if voice is not None and voice.off_deadline is None:
                released_info.append((ch, voice.key))

        window_s = self.cfg.gliss_window_ms / 1000.0
        self._recent_releases = [
            (t, k) for (t, k) in self._recent_releases if now - t <= window_s
        ]

        # Keys that were released but whose note-off is still inside the grace
        # window. Their off is emitted either before or after the new note-ons,
        # depending on the articulation mode.
        pending_others = [
            ch
            for ch, v in self.voices.items()
            if v.off_deadline is not None and ch not in pressed
        ]
        if pending_others and not self.cfg.gliss_legato:
            for ch in sorted(pending_others, key=lambda c: self.voices[c].key):
                events.append(self._finish_off(ch, now, "release"))

        for ch in pressed:
            info = self.keymap[ch]
            if info.get("disabled"):
                # A mapping may deliberately leave a slot silent. It still
                # enters the mask above, so re-enabling while the finger stays
                # down does not retrigger until release + press.
                continue
            voice = self.voices.get(ch)

            # Duplicate high level: the key never left the mask.
            if voice is not None and voice.off_deadline is None:
                continue

            repeat = False
            if voice is not None:
                # Released, but re-pressed inside the grace window. Articulate:
                # the old note-off must precede the new note-on.
                events.append(self._finish_off(ch, now, "re-press"))
                repeat = True
            else:
                last = self.last_off.get(ch)
                if last is not None and (now - last) * 1000.0 <= self.cfg.repeat_window_ms:
                    repeat = True

            midi = int(info["midi"]) + self.cfg.offset
            if not 0 <= midi <= 127:
                self.skipped += 1
                continue

            # A slide can look like any of three things at a 20 ms poll:
            # two keys held for one frame (land before lift), a clean gap, or
            # a same-frame swap. Consider neighbours that are still held as
            # well as ones that have just gone.
            key_no = int(info["key"])
            candidates: list[tuple[float, int]] = []
            for ch_held, held_voice in self.voices.items():
                if ch_held != ch and abs(key_no - held_voice.key) == 1:
                    candidates.append((0.0, held_voice.key))
            for _ch_rel, key_rel in released_info:
                if abs(key_no - key_rel) == 1:
                    candidates.append((0.0, key_rel))
            for rel_t, key_rel in self._recent_releases:
                gap_ms = (now - rel_t) * 1000.0
                if abs(key_no - key_rel) == 1 and gap_ms <= self.cfg.gliss_window_ms:
                    candidates.append((gap_ms, key_rel))
            candidates.sort(key=lambda c: c[0])
            gliss_gap, gliss_from = candidates[0] if candidates else (None, None)

            v = _Voice(
                key=int(info["key"]),
                channel=ch,
                midi=midi,
                velocity=self.cfg.velocity,
                note=midi_name(midi),
                on_t=now,
            )
            self.voices[ch] = v
            events.append(
                NoteEvent(
                    t=now,
                    kind="on",
                    key=v.key,
                    channel=ch,
                    midi=midi,
                    velocity=v.velocity,
                    note=v.note,
                    reason="press",
                    gliss_from=gliss_from,
                    gliss_gap_ms=gliss_gap,
                    repeat=repeat,
                )
            )

        if pending_others and self.cfg.gliss_legato:
            # Note-on already sent: the old note overlaps the new one.
            for ch in sorted(pending_others, key=lambda c: self.voices[c].key):
                events.append(self._finish_off(ch, now, "release"))

        for ch in released:
            voice = self.voices.get(ch)
            if voice is None or voice.off_deadline is not None:
                continue
            voice.release_t = now
            self._recent_releases.append((now, voice.key))
            if self.cfg.release_grace_ms <= 0:
                events.append(self._finish_off(ch, now, "release"))
            else:
                voice.off_deadline = now + self.cfg.release_grace_ms / 1000.0

        self.mask = active
        self.max_polyphony = max(self.max_polyphony, len(self.voices))
        return events

    def tick(self, now: float) -> list[NoteEvent]:
        """Expire note-off grace deadlines. Call every loop iteration."""
        due = [
            ch
            for ch, v in self.voices.items()
            if v.off_deadline is not None and v.off_deadline <= now
        ]
        return [self._finish_off(ch, now, "release") for ch in due]

    def panic(self, now: float, reason: str = "panic") -> list[NoteEvent]:
        """Silence every voice. Does NOT clear the mask: a finger still on a
        pad must not re-trigger the note until it is lifted and pressed again."""
        return [self._finish_off(ch, now, reason) for ch in list(self.voices)]

    def sync(self, active: set[int], now: float) -> list[NoteEvent]:
        """Adopt the device's current key state without emitting note-ons.

        Used at the start of a guided step. The serial buffer can contain
        frames from while the prompt was blocking; replaying those as fresh
        presses makes a note sound during a 'hands off' step. Any voice still
        sounding is turned off, and keys already active are treated as held:
        they will not retrigger until lifted and pressed again.
        """
        offs = [self._finish_off(ch, now, "sync") for ch in list(self.voices)]
        self.mask = set(active) & set(self.keymap)
        self._recent_releases.clear()
        self.last_off.clear()
        return offs

    def reset_after_reconnect(self) -> None:
        """Forget the mask when the device is re-plugged/rebooted."""
        self.mask = set()
        self._recent_releases.clear()

    # -- internals --------------------------------------------------------

    def _finish_off(self, channel: int, now: float, reason: str) -> NoteEvent:
        v = self.voices.pop(channel)
        end = v.release_t if v.release_t is not None else now
        held_ms = max(0.0, (end - v.on_t) * 1000.0)
        self.last_off[channel] = now
        return NoteEvent(
            t=now,
            kind="off",
            key=v.key,
            channel=v.channel,
            midi=v.midi,
            velocity=0,
            note=v.note,
            reason=reason,
            held_ms=held_ms,
            short=held_ms < self.cfg.min_note_ms,
        )
