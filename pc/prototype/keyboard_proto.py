"""
THROWAWAY PROTOTYPE - KeyBorad PC-side software core.

One program, three ways to run:

  python keyboard_proto.py sim              replay a scripted session, no hardware
  python keyboard_proto.py live  --port COM5   play the real instrument
  python keyboard_proto.py test  --port COM5   guided one-shot test session
  python keyboard_proto.py ports            list serial ports

It reads the firmware's status line

  [  10972 ms]  0x5A OK  0x5C OK  0x5D OK   keys: 12

turns the channel mask into MIDI note events (edge handling, chords,
glissando, repeats, octave/transpose, note-off grace), and plays them through
an embedded FluidSynth with the TimGM6mb SoundFont.

The prototype's question is in NOTES.md. Everything here is meant to be
deleted or absorbed once the behaviour is agreed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEYMAP_PATH = ROOT / "mapping" / "keymap.json"
VENDOR = HERE / "vendor"
LOGS = HERE / "logs"

from note_engine import EngineConfig, Frame, NoteEngine, NoteEvent, midi_name  # noqa: E402


# ---------------------------------------------------------------------------
# Output and session logs
# ---------------------------------------------------------------------------


class Out:
    """print() plus an optional text transcript for the guided test."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.file = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.file = open(path, "w", encoding="utf-8")

    def __call__(self, text: str = "") -> None:
        print(text, flush=True)
        if self.file is not None:
            self.file.write(str(text) + "\n")
            self.file.flush()

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None


class Jsonl:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "w", encoding="utf-8")

    def add(self, record_type: str, **fields) -> None:
        record = {"type": record_type, **fields}
        self.file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()


# ---------------------------------------------------------------------------
# Key map
# ---------------------------------------------------------------------------


def load_keymap() -> tuple[dict, dict[int, dict]]:
    data = json.loads(KEYMAP_PATH.read_text(encoding="utf-8"))
    by_channel = {int(item["channel"]): item for item in data["keys"]}
    return data, by_channel


def by_key(channels: dict[int, dict]) -> dict[int, dict]:
    return {int(item["key"]): item for item in channels.values()}


def expected_name(key: int, offset: int, keys: dict[int, dict]) -> str:
    return midi_name(int(keys[key]["midi"]) + offset)


# ---------------------------------------------------------------------------
# Serial input
# ---------------------------------------------------------------------------


@dataclass
class Notice:
    text: str
    t: float = field(default_factory=time.monotonic)


STATUS_RE = re.compile(r"^\[\s*(\d+)\s*ms\]\s*(.*)$")
MODULE_RE = re.compile(r"0x([0-9A-Fa-f]{2})\s+(OK|--)")
KEYS_RE = re.compile(r"keys:\s*(.*)$")


def parse_line(text: str):
    match = STATUS_RE.match(text)
    if match is None:
        return Notice(text=text)
    dev_ms = int(match.group(1))
    rest = match.group(2)
    keys_match = KEYS_RE.search(rest)
    if keys_match is None:
        return Notice(text=text)
    modules = {int(addr, 16): (state == "OK") for addr, state in MODULE_RE.findall(rest)}
    active = {int(n) for n in re.findall(r"\d+", keys_match.group(1))}
    return Frame(t=time.monotonic(), active=active, dev_ms=dev_ms, modules=modules, raw=text)


class SerialSource:
    def __init__(self, port: str):
        try:
            import serial
        except ImportError:
            raise SystemExit("pyserial is missing. Run: python -m pip install pyserial")
        self.port = port
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = 115200
        self.ser.timeout = 0.02
        self.ser.write_timeout = 0.2
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        # Anything already queued is history from before this tool started;
        # replaying it would sound notes that were never just played.
        self.ser.reset_input_buffer()
        self.buf = b""

    def poll(self):
        data = self.ser.read(4096)
        if data:
            self.buf += data
        if b"\n" not in self.buf:
            return None
        line, self.buf = self.buf.split(b"\n", 1)
        text = line.decode("utf-8", "replace").strip()
        if not text:
            return None
        return parse_line(text)

    def drain(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.ser.read(4096)
            time.sleep(0.005)

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass


def pick_port(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    try:
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial is missing. Run: python -m pip install pyserial")
    candidates = [p for p in list_ports.comports() if p.vid == 0x303A]
    if not candidates:
        raise SystemExit("No Espressif USB serial device found. Use 'ports' or pass --port COMx.")
    return candidates[0].device


PROJECT_MODULES = {0x5A: (1, 1, 12), 0x5C: (2, 13, 24), 0x5D: (3, 25, 36)}
MODULE_NOTICE_RE = re.compile(r"module\s+(\d+)\s+@\s+0x([0-9A-Fa-f]{2})")


# ---------------------------------------------------------------------------
# Device response check
# ---------------------------------------------------------------------------


class DeviceMonitor:
    def __init__(self, out: Out):
        self.out = out
        self.modules: dict[int, bool] = {}
        self.transitions: list[tuple[float, int, bool]] = []
        self.last_status_t: Optional[float] = None
        self.last_silent_warn = 0.0

    def observe(self, frame: Frame) -> None:
        self.last_status_t = frame.t
        for addr, ok in frame.modules.items():
            if addr not in PROJECT_MODULES:
                continue
            previous = self.modules.get(addr)
            self.modules[addr] = ok
            if previous is None:
                if not ok:
                    self.out(
                        f"!! device: module {PROJECT_MODULES[addr][0]} (0x{addr:02X}) is not answering"
                    )
            elif previous != ok:
                self.transitions.append((frame.t, addr, ok))
                tag = "++" if ok else "!!"
                self.out(
                    f"{tag} device: module {PROJECT_MODULES[addr][0]} (0x{addr:02X}) -> "
                    f"{'OK' if ok else '--'}"
                )

    def observe_notice(self, text: str, now: float) -> None:
        """The firmware's health-check lines are the only evidence of a fast
        module dropout: the 2 s status line can miss a brief unplug entirely.
        Parse them so the dropout step is not reported as 'skipped'."""
        match = MODULE_NOTICE_RE.search(text)
        if match is None:
            return
        addr = int(match.group(2), 16)
        if addr not in PROJECT_MODULES:
            return
        lower = text.lower()
        if "lost its config" in lower:
            self.transitions.append((now, addr, False))
            if "re-initialised" in lower:
                self.transitions.append((now, addr, True))
                self.modules[addr] = True
            else:
                self.modules[addr] = False
        elif "appeared" in lower:
            if "failed" in lower:
                self.transitions.append((now, addr, False))
                self.modules[addr] = False
            else:
                self.transitions.append((now, addr, True))
                self.modules[addr] = True
        elif "stopped answering" in lower or "init failed" in lower:
            self.transitions.append((now, addr, False))
            self.modules[addr] = False

    def watchdog(self, now: float) -> None:
        if self.last_status_t is None:
            return
        missing = now - self.last_status_t
        if missing > 3.5 and now - self.last_silent_warn > 3.5:
            self.last_silent_warn = now
            self.out(f"!! device: no status line for {missing:.1f} s (device silent?)")

    def summary_line(self) -> str:
        parts = []
        for addr in PROJECT_MODULES:
            state = self.modules.get(addr)
            label = "OK" if state else ("--" if state is False else "?")
            parts.append(f"0x{addr:02X} {label}")
        return "  ".join(parts)


# ---------------------------------------------------------------------------
# Synth backends (FluidSynth, or log only)
# ---------------------------------------------------------------------------


PROGRAMS = [
    (0, "Piano 1"),
    (4, "E.Piano 1"),
    (16, "Drawbar Organ"),
    (24, "Nylon Guitar"),
    (48, "Strings 1"),
    (80, "Square Lead"),
]


class NullSynth:
    name = "none"

    def program(self, index: int) -> str:
        return PROGRAMS[index % len(PROGRAMS)][1]

    def note_on(self, midi: int, velocity: int) -> None:
        pass

    def note_off(self, midi: int) -> None:
        pass

    def panic(self) -> None:
        pass

    def close(self) -> None:
        pass


def find_dll_dir() -> Optional[Path]:
    for candidate in sorted(VENDOR.glob("fluidsynth-*/bin")):
        if any(candidate.glob("libfluidsynth-*.dll")):
            return candidate
    return None


def find_soundfont() -> Optional[Path]:
    for candidate in sorted((VENDOR / "soundfont").glob("*.sf2")):
        return candidate
    for candidate in sorted(VENDOR.rglob("*.sf2")):
        return candidate
    return None


class FluidSynthBackend:
    def __init__(self, gain: float = 0.6):
        dll_dir = find_dll_dir()
        soundfont = find_soundfont()
        if dll_dir is None:
            raise RuntimeError("FluidSynth DLL not found under pc/prototype/vendor")
        if soundfont is None:
            raise RuntimeError("no .sf2 found under pc/prototype/vendor/soundfont")
        os.add_dll_directory(str(dll_dir))
        os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
        import fluidsynth

        self.soundfont = soundfont
        self.channel = 0
        self.fs = fluidsynth.Synth(gain=gain)
        self.sfid = self.fs.sfload(str(soundfont))
        if self.sfid < 0:
            raise RuntimeError(f"FluidSynth could not load {soundfont.name}")
        self.program(0)
        # Create only the audio driver. Synth.start() also opens a MIDI input
        # driver, which this build cannot satisfy ('none' is not a valid
        # driver) and which we do not need: the serial port is our MIDI source.
        self.fs.audio_driver = fluidsynth.new_fluid_audio_driver(
            self.fs.settings, self.fs.synth
        )
        if not self.fs.audio_driver:
            raise RuntimeError("FluidSynth could not open an audio output device")

    @property
    def name(self) -> str:
        return "fluidsynth"

    def program(self, index: int) -> str:
        program, name = PROGRAMS[index % len(PROGRAMS)]
        self.fs.program_select(self.channel, self.sfid, 0, program)
        return name

    def note_on(self, midi: int, velocity: int) -> None:
        self.fs.noteon(self.channel, midi, velocity)

    def note_off(self, midi: int) -> None:
        self.fs.noteoff(self.channel, midi)

    def panic(self) -> None:
        self.fs.all_notes_off(self.channel)
        self.fs.all_sounds_off(self.channel)

    def close(self) -> None:
        self.panic()
        self.fs.delete()


def make_synth(args, out: Out):
    if getattr(args, "no_audio", False):
        out("audio: disabled (--no-audio), MIDI events are logged only")
        return NullSynth()
    try:
        synth = FluidSynthBackend(gain=getattr(args, "gain", 0.6))
        name = synth.program(0)
        out(f"audio: FluidSynth + {synth.soundfont.name}, program 0 ({name})")
        return synth
    except Exception as exc:
        out(f"!! audio: FluidSynth unavailable ({exc}); logging MIDI only")
        return NullSynth()


# ---------------------------------------------------------------------------
# Event printing
# ---------------------------------------------------------------------------


def fmt_event(event: NoteEvent, origin: float) -> str:
    rel = event.t - origin
    if event.kind == "on":
        extra = f"midi{event.midi:<3} v{event.velocity}"
        if event.gliss_from is not None:
            extra += f"  GLISS<-key{event.gliss_from}"
            if event.gliss_gap_ms:
                extra += f" gap={event.gliss_gap_ms:.0f}ms"
        if event.repeat:
            extra += "  REPEAT"
        return f"[{rel:8.3f}] ON  {event.key:2d} {event.note:<4} ch{event.channel:<2} {extra}"
    extra = f"midi{event.midi:<3} held={event.held_ms or 0:6.0f}ms"
    if event.reason != "release":
        extra += f" ({event.reason})"
    if event.short:
        extra += " SHORT"
    return f"[{rel:8.3f}] OFF {event.key:2d} {event.note:<4} ch{event.channel:<2} {extra}"


def event_dict(event: NoteEvent) -> dict:
    return {
        "t": round(event.t, 4),
        "kind": event.kind,
        "key": event.key,
        "channel": event.channel,
        "midi": event.midi,
        "note": event.note,
        "velocity": event.velocity,
        "held_ms": None if event.held_ms is None else round(event.held_ms, 1),
        "reason": event.reason,
        "gliss_from": event.gliss_from,
        "gliss_gap_ms": None if event.gliss_gap_ms is None else round(event.gliss_gap_ms, 1),
        "repeat": event.repeat,
        "short": event.short,
    }


def send_event(event: NoteEvent, synth) -> None:
    if event.kind == "on":
        synth.note_on(event.midi, event.velocity)
    else:
        synth.note_off(event.midi)


def state_line(engine: NoteEngine) -> str:
    voices = engine.active_list()
    notes = " ".join(f"{v.key}:{v.note}" for v in voices) or "none"
    return (
        f"    state: {notes}  poly={len(voices)}  "
        f"oct={engine.cfg.octave:+d} tr={engine.cfg.transpose:+d} "
        f"legato={'on' if engine.cfg.gliss_legato else 'off'}"
    )


def settle_source(
    source: SerialSource,
    seconds: float,
    monitor: DeviceMonitor,
    out: Out,
    jsonl: Jsonl,
) -> Optional[set[int]]:
    """Consume the serial backlog without playing anything.

    While input() blocks, the firmware keeps emitting status lines. Those
    frames are history, not fresh plays: feeding them through the note engine
    made a note sound during a 'hands off' step. Read them only to learn the
    device's current key state; the caller then calls NoteEngine.sync().

    Returns the latest active-channel set, or None if no frame arrived.
    """
    last_active: Optional[set[int]] = None
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        item = source.poll()
        if isinstance(item, Frame):
            monitor.observe(item)
            last_active = set(item.active)
            jsonl.add(
                "frame",
                t=round(item.t, 4),
                dev_ms=item.dev_ms,
                active=sorted(item.active),
                modules={f"0x{a:02X}": ok for a, ok in item.modules.items()},
            )
        elif isinstance(item, Notice):
            monitor.observe_notice(item.text, item.t)
            out(f"  dev: {item.text}")
            jsonl.add("notice", t=round(item.t, 4), text=item.text)
    return last_active


# ---------------------------------------------------------------------------
# Statistics and checks
# ---------------------------------------------------------------------------


BLIP_MS = 60.0  # extras shorter than this are treated as sensor blips


@dataclass
class Stats:
    ons: int = 0
    offs: int = 0
    on_keys: Counter = field(default_factory=Counter)
    off_keys: Counter = field(default_factory=Counter)
    held: list[float] = field(default_factory=list)
    on_midis: list[int] = field(default_factory=list)
    on_key_seq: list[int] = field(default_factory=list)
    maxpoly: int = 0
    latencies_us: list[float] = field(default_factory=list)
    on_events: list[NoteEvent] = field(default_factory=list)
    off_events: list[NoteEvent] = field(default_factory=list)
    held_by_key: dict[int, list[float]] = field(default_factory=dict)


def compute_stats(events: list[NoteEvent], maxpoly: int, latencies: list[float]) -> Stats:
    stats = Stats(maxpoly=maxpoly, latencies_us=list(latencies))
    for event in events:
        if event.kind == "on":
            stats.ons += 1
            stats.on_keys[event.key] += 1
            stats.on_midis.append(event.midi)
            stats.on_key_seq.append(event.key)
            stats.on_events.append(event)
        else:
            stats.offs += 1
            stats.off_keys[event.key] += 1
            stats.off_events.append(event)
            if event.held_ms is not None:
                stats.held.append(event.held_ms)
                stats.held_by_key.setdefault(event.key, []).append(event.held_ms)
    return stats


def split_extras(stats: Stats, target_keys: list[int]) -> tuple[list[int], list[int]]:
    """Keys outside the step's target that produced notes.

    Returns (short_blips, long_notes). A key counts as a long note if any of
    its holds reached BLIP_MS; otherwise it is ignored as a blip. On this
    hardware a 30-50 ms blip on a neighbouring/high pad is electrical noise,
    while a real accidental touch lasts much longer.
    """
    targets = set(target_keys)
    short: list[int] = []
    long: list[int] = []
    for key, count in sorted(stats.on_keys.items()):
        if key in targets:
            continue
        holds = stats.held_by_key.get(key, [])
        if len(holds) < count or (holds and max(holds) >= BLIP_MS):
            long.append(key)
        else:
            short.append(key)
    return short, long


def key_list(keys: list[int]) -> str:
    return " ".join(f"key {k}" for k in sorted(set(keys)))


def extras_note(short: list[int], long: list[int]) -> str:
    parts = []
    if short:
        parts.append(f"ignored blip(s) on {key_list(short)}")
    if long:
        parts.append(f"extra long note(s) on {key_list(long)}")
    return "; ".join(parts)


def find_section(sections, t: float):
    for section in sections:
        if section.start <= t < section.end:
            return section
    return None


def latency_text(stats: Stats) -> str:
    if not stats.latencies_us:
        return "pc latency n/a"
    values = stats.latencies_us
    return f"pc latency avg {sum(values)/len(values):.0f}us max {max(values):.0f}us"


def keys_text(counter: Counter) -> str:
    return " ".join(f"k{k}x{n}" for k, n in sorted(counter.items())) or "-"


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


SIM_EVENTS = [
    (0, []),
    # tap key 8 (channel 5) three times
    (500, [5]), (620, []),
    (700, [5]), (820, []),
    (900, [5]), (1020, []),
    # long hold key 1 (channel 12)
    (1200, [1]), (2200, []),
    # chord keys 1 + 8 + 12 (channels 12, 5, 1)
    (2400, [12, 5, 1]), (2900, []),
    # slide key 1 -> key 12: one frame of overlap per key
    (3100, [12]), (3140, [12, 11]), (3160, [11]),
    (3180, [11, 10]), (3200, [10]),
    (3220, [10, 9]), (3240, [9]),
    (3260, [9, 8]), (3280, [8]),
    (3300, [8, 7]), (3320, [7]),
    (3340, [7, 6]), (3360, [6]),
    (3380, [6, 5]), (3400, [5]),
    (3420, [5, 4]), (3440, [4]),
    (3460, [4, 3]), (3480, [3]),
    (3500, [3, 2]), (3520, [2]),
    (3540, [2, 1]), (3560, [1]),
    (3660, []),
    # repeats key 9 (channel 4)
    (4000, [4]), (4080, []),
    (4160, [4]), (4240, []),
    (4320, [4]), (4400, []),
    (4480, [4]), (4560, []),
    (4640, [4]), (4720, []),
    # octave +1, then transpose +2 (presses at 5000 and 5400)
    (5000, [5]), (5150, []),
    (5400, [5]), (5550, []),
    (5800, []),
]

SIM_ACTIONS = [
    (4850, "octave", 1),
    (5200, "octave", 0),
    (5300, "transpose", 2),
    (5600, "transpose", 0),
]


@dataclass
class Section:
    name: str
    start: float
    end: float
    check: str
    events: list[NoteEvent] = field(default_factory=list)
    maxpoly: int = 0


def make_sim_sections() -> list[Section]:
    return [
        Section("S1 idle", 0.00, 0.25, "silence"),
        Section("S2 tap key 8 x3", 0.45, 1.15, "taps"),
        Section("S3 hold key 1", 1.15, 2.35, "hold"),
        Section("S4 chord 1+8+12", 2.35, 3.05, "chord"),
        Section("S5 gliss 1->12", 3.05, 3.75, "gliss_up"),
        Section("S6 repeats key 9", 3.95, 4.85, "repeats"),
        Section("S7 octave +1", 4.95, 5.25, "octave"),
        Section("S8 transpose +2", 5.30, 5.70, "transpose"),
    ]


def sim_frames():
    index = 0
    current: set[int] = set()
    for t_ms in range(0, 5820, 20):
        while index < len(SIM_EVENTS) and SIM_EVENTS[index][0] <= t_ms:
            current = set(SIM_EVENTS[index][1])
            index += 1
        modules = {
            0x5A: True,
            0x5C: True,
            0x5D: not (4800 <= t_ms < 5200),  # module 3 unplugged
        }
        yield Frame(
            t=t_ms / 1000.0,
            active=set(current),
            dev_ms=t_ms,
            modules=modules,
        )


def check_sim_section(section: Section, stats: Stats) -> tuple[str, str]:
    check = section.check
    if check == "silence":
        if stats.ons == 0:
            return "PASS", "no notes"
        return "WARN", f"{stats.ons} unexpected note-on(s)"
    if check == "taps":
        if stats.ons == 3 and stats.offs == 3 and set(stats.on_keys) == {8}:
            return "PASS", "3 taps, 3 releases"
        return "WARN", f"on={stats.ons} off={stats.offs} keys={keys_text(stats.on_keys)}"
    if check == "hold":
        held = max(stats.held) if stats.held else 0.0
        if stats.ons == 1 and stats.offs == 1 and held >= 900:
            return "PASS", f"one note held {held:.0f} ms"
        return "WARN", f"on={stats.ons} off={stats.offs} held={held:.0f}ms"
    if check == "chord":
        if stats.maxpoly >= 3 and stats.ons >= 3 and stats.offs >= stats.ons:
            return "PASS", f"3 simultaneous notes (max poly {stats.maxpoly})"
        return "WARN", f"max poly={stats.maxpoly} on={stats.ons} off={stats.offs}"
    if check == "gliss_up":
        seq = stats.on_key_seq
        rising = all(b > a for a, b in zip(seq, seq[1:]))
        if len(seq) == 12 and rising and stats.offs == 12:
            return "PASS", "12 keys, ascending, no stuck note"
        return "WARN", f"on={stats.ons} off={stats.offs} seq={seq}"
    if check == "repeats":
        if stats.ons == 5 and stats.offs == 5:
            return "PASS", "5 separate notes"
        return "WARN", f"on={stats.ons} off={stats.offs}"
    if check == "octave":
        if stats.ons >= 1 and all(midi == 84 for midi in stats.on_midis):
            return "PASS", "key 8 -> C6 (MIDI 84)"
        return "WARN", f"midi={stats.on_midis}"
    if check == "transpose":
        if stats.ons >= 1 and all(midi == 74 for midi in stats.on_midis):
            return "PASS", "key 8 -> D5 (MIDI 74)"
        return "WARN", f"midi={stats.on_midis}"
    return "INFO", ""


def cmd_sim(args) -> int:
    out = Out()
    _data, channels = load_keymap()
    engine = NoteEngine(
        channels,
        EngineConfig(
            velocity=args.velocity,
            release_grace_ms=args.grace,
            gliss_legato=args.legato,
        ),
    )
    synth = NullSynth()
    if args.audio:
        synth = make_synth(args, out)

    out("=== KeyBorad note-engine SIMULATION (no hardware) ===")
    out(
        f"keymap={KEYMAP_PATH.relative_to(ROOT)}  channels={len(channels)}  "
        f"grace={args.grace:.0f}ms  legato={'on' if args.legato else 'off'}"
    )
    out("")
    monitor = DeviceMonitor(out)
    sections = make_sim_sections()
    action_index = 0
    last_t = 0.0

    try:
        for frame in sim_frames():
            while action_index < len(SIM_ACTIONS) and SIM_ACTIONS[action_index][0] <= (frame.dev_ms or 0):
                _t_ms, what, value = SIM_ACTIONS[action_index]
                action_index += 1
                if what == "octave":
                    engine.set_octave(value)
                else:
                    engine.set_transpose(value)
                out(f"[{frame.t:8.3f}] CFG {what} -> {value:+d}")

            if args.audio:
                delay = frame.t - last_t
                if delay > 0:
                    time.sleep(delay / max(args.speed, 0.01))
            last_t = frame.t

            monitor.observe(frame)
            events = engine.update(frame)
            events += engine.tick(frame.t)
            for event in events:
                send_event(event, synth)
                out(fmt_event(event, 0.0))
                section = find_section(sections, event.t)
                if section is not None:
                    section.events.append(event)

            poly = engine.polyphony()
            for section in sections:
                if section.start <= frame.t < section.end:
                    section.maxpoly = max(section.maxpoly, poly)

        out("")
        out("=== SELF-CHECK ===")
        overall_ok = True
        for section in sections:
            stats = compute_stats(section.events, section.maxpoly, [])
            verdict, detail = check_sim_section(section, stats)
            if verdict != "PASS":
                overall_ok = False
            out(
                f"{section.name:<20} on={stats.ons:<3} off={stats.offs:<3} "
                f"poly={stats.maxpoly}  {verdict}: {detail}"
            )

        dropout_down = any(addr == 0x5D and not ok for _t, addr, ok in monitor.transitions)
        dropout_up = any(addr == 0x5D and ok for _t, addr, ok in monitor.transitions)
        dropout_ok = dropout_down and dropout_up
        if not dropout_ok:
            overall_ok = False
        out(
            f"{'module 0x5D dropout':<20} {len(monitor.transitions)} transition(s)  "
            f"{'PASS' if dropout_ok else 'WARN'}: unplug seen={dropout_down} replug seen={dropout_up}"
        )
        out("")
        out("VERDICT: " + ("PASS - every simulated case behaved as intended" if overall_ok else "WARN - see the lines above"))
        return 0 if overall_ok else 1
    finally:
        synth.close()


# ---------------------------------------------------------------------------
# Guided test session
# ---------------------------------------------------------------------------


@dataclass
class TestStep:
    sid: str
    title: str
    keys: list[int]
    instruction: str
    check: str
    expect: dict = field(default_factory=dict)
    octave: int = 0
    transpose: int = 0
    optional: bool = False


def make_plan() -> list[TestStep]:
    """No step has a time limit: it records until the operator presses Enter.

    That is deliberate. Reading the instruction and finding the physical keys
    takes as long as it takes, and key detection is unambiguous, so a fixed
    window only adds pressure and cuts off slow steps.
    """
    return [
        TestStep(
            sid="S1", title="Baseline - hands off", keys=[],
            instruction="Do not touch the keyboard. Wait a moment, then press Enter.",
            check="silence",
        ),
        TestStep(
            sid="S2", title="Light taps on key 8", keys=[8],
            instruction="Tap key 8 (C5) three times, lightly.",
            check="taps", expect={"count": 3},
        ),
        TestStep(
            sid="S3", title="Firm press on key 8", keys=[8],
            instruction="Press key 8 firmly, hold about 1 s, then release.",
            check="tap_hold",
        ),
        TestStep(
            sid="S4", title="Long hold on key 1", keys=[1],
            instruction="Press key 1 (F4), hold about 3 s, then release.",
            check="hold", expect={"min_held_ms": 2000},
        ),
        TestStep(
            sid="S5", title="Chord 1 + 16 + 28", keys=[1, 16, 28],
            instruction="Press keys 1, 16 and 28 together (one key from each "
                        "module), hold about 1 s, then release all three.",
            check="chord",
        ),
        TestStep(
            sid="S6", title="Glissando up", keys=list(range(1, 13)),
            instruction="Slide one finger slowly from key 1 to key 12 (left to right).",
            check="gliss_up",
        ),
        TestStep(
            sid="S7", title="Glissando down", keys=list(range(12, 0, -1)),
            instruction="Slide back from key 12 to key 1 at the same speed.",
            check="gliss_down",
        ),
        TestStep(
            sid="S8", title="Repeats on key 28", keys=[28],
            instruction="Tap key 28 (G#6, module 3) five times, as fast as comfortable.",
            check="repeats", expect={"count": 5},
        ),
        TestStep(
            sid="S9", title="Neighbour isolation", keys=[7, 8, 9],
            instruction="Tap keys 7, 8 and 9 one at a time. Only one note should "
                        "sound at a time.",
            check="neighbours",
        ),
        TestStep(
            sid="S10", title="Octave +1", keys=[8],
            instruction="The tool shifted the octave up by one. Tap key 8 twice. "
                        "Expect C6 (MIDI 84).",
            check="fixed_midi", expect={"midi": 84}, octave=1,
        ),
        TestStep(
            sid="S11", title="Octave -1", keys=[8],
            instruction="The tool shifted the octave down by one. Tap key 8 twice. "
                        "Expect C4 (MIDI 60).",
            check="fixed_midi", expect={"midi": 60}, octave=-1,
        ),
        TestStep(
            sid="S12", title="Transpose +2", keys=[8],
            instruction="The tool transposed up two semitones. Tap key 8 twice. "
                        "Expect D5 (MIDI 74).",
            check="fixed_midi", expect={"midi": 74}, transpose=2,
        ),
        TestStep(
            sid="S13", title="Module dropout (optional)", keys=[],
            instruction="OPTIONAL: unplug module 3's 3V3, wait about 2 s, then "
                        "reconnect it. 0x5D should go -- and come back OK.",
            check="dropout", optional=True,
        ),
        TestStep(
            sid="S14", title="Final silence", keys=[],
            instruction="Hands off. Check that no note is stuck.",
            check="silence",
        ),
    ]


def check_step(step: TestStep, stats: Stats, transitions: list[tuple[float, int, bool]]) -> tuple[str, str]:
    check = step.check

    if check == "silence":
        if stats.ons == 0:
            return "PASS", "no note events"
        return "WARN", f"{stats.ons} unexpected note-on(s): {keys_text(stats.on_keys)}"

    # Everything below is judged on the step's target keys. A short blip on a
    # neighbouring/high pad is electrical noise, not the operator's action;
    # a long note on a non-target key is reported as an unintended touch.
    short, long = split_extras(stats, step.keys)

    def with_extra(detail: str) -> str:
        extra = extras_note(short, long)
        return f"{detail}; {extra}" if extra else detail

    if check == "taps":
        count = int(step.expect.get("count", 3))
        key = step.keys[0]
        ons = stats.on_keys.get(key, 0)
        offs = stats.off_keys.get(key, 0)
        ok = ons == count and offs == count and not long
        return ("PASS" if ok else "WARN"), with_extra(f"key {key}: {ons} on / {offs} off")

    if check == "tap_hold":
        key = step.keys[0]
        ons = stats.on_keys.get(key, 0)
        offs = stats.off_keys.get(key, 0)
        held = max(stats.held_by_key.get(key, [0]))
        ok = ons >= 1 and offs >= 1 and not long
        return ("PASS" if ok else "WARN"), with_extra(
            f"key {key}: {ons} press(es), longest {held:.0f} ms"
        )

    if check == "hold":
        minimum = float(step.expect.get("min_held_ms", 2000))
        key = step.keys[0]
        ons = stats.on_keys.get(key, 0)
        offs = stats.off_keys.get(key, 0)
        held = max(stats.held_by_key.get(key, [0]))
        ok = ons == 1 and offs == 1 and held >= minimum and not long
        return ("PASS" if ok else "WARN"), with_extra(
            f"key {key}: {ons} on / {offs} off, held {held:.0f} ms"
        )

    if check == "chord":
        needed = len(step.keys)
        missing = [k for k in step.keys if stats.on_keys.get(k, 0) == 0]
        target_ons = sum(stats.on_keys.get(k, 0) for k in step.keys)
        target_offs = sum(stats.off_keys.get(k, 0) for k in step.keys)
        ok = not missing and stats.maxpoly >= needed and target_offs >= target_ons
        detail = f"{target_ons} target notes, max poly {stats.maxpoly}"
        if missing:
            detail += f", missing {key_list(missing)}"
        return ("PASS" if ok else "WARN"), with_extra(detail)

    if check in ("gliss_up", "gliss_down"):
        targets = set(step.keys)
        sequence: list[int] = []
        duplicates: list[int] = []
        for event in stats.on_events:
            if event.key not in targets:
                continue
            if sequence and event.key == sequence[-1]:
                duplicates.append(event.key)
                continue
            sequence.append(event.key)
        rising = all(b > a for a, b in zip(sequence, sequence[1:]))
        falling = all(b < a for a, b in zip(sequence, sequence[1:]))
        monotonic = rising if check == "gliss_up" else falling
        target_offs = sum(stats.off_keys.get(k, 0) for k in step.keys)
        ok = len(sequence) >= 8 and monotonic and target_offs >= len(sequence) - 1 and not long
        direction = "ascending" if check == "gliss_up" else "descending"
        detail = f"{len(sequence)} keys, {direction if monotonic else 'not monotonic'}"
        if duplicates:
            detail += f", duplicate key(s) {key_list(duplicates)}"
        return ("PASS" if ok else "WARN"), with_extra(detail)

    if check == "repeats":
        count = int(step.expect.get("count", 5))
        key = step.keys[0]
        ons = stats.on_keys.get(key, 0)
        offs = stats.off_keys.get(key, 0)
        ok = ons >= count and offs >= ons - 1 and not long
        return ("PASS" if ok else "WARN"), with_extra(
            f"{ons} notes on key {key} (requested {count})"
        )

    if check == "neighbours":
        seen = [k for k in step.keys if stats.on_keys.get(k, 0)]
        ok = len(seen) >= 2 and stats.maxpoly == 1 and not long
        return ("PASS" if ok else "WARN"), with_extra(
            f"{keys_text(stats.on_keys)}, max poly {stats.maxpoly}"
        )

    if check == "fixed_midi":
        expected = int(step.expect["midi"])
        key = step.keys[0]
        midis = [e.midi for e in stats.on_events if e.key == key]
        ok = bool(midis) and all(m == expected for m in midis) and not long
        shown = ", ".join(midi_name(m) for m in midis) or "no notes"
        return ("PASS" if ok else "WARN"), with_extra(
            f"key {key}: {shown} (expected {midi_name(expected)})"
        )

    if check == "dropout":
        down = any(addr == 0x5D and not ok for _t, addr, ok in transitions)
        up = any(addr == 0x5D and ok for _t, addr, ok in transitions)
        if down and up:
            return "PASS", "module 3 dropped and recovered"
        if not down and not up:
            return "INFO", "no module transition seen"
        return "WARN", f"dropout seen={down} recovery seen={up}"

    return "INFO", ""


def cmd_test(args) -> int:
    if not sys.stdin.isatty():
        print("!! the guided test needs an interactive terminal: it waits for")
        print("   Enter to end each step. Run it from the VS Code terminal.")
        return 2
    port = pick_port(args.port)
    _data, channels = load_keymap()
    keys = by_key(channels)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    LOGS.mkdir(parents=True, exist_ok=True)
    jsonl_path = LOGS / f"session_{stamp}.jsonl"
    text_path = LOGS / f"session_{stamp}.txt"
    jsonl = Jsonl(jsonl_path)
    out = Out(text_path)

    out("=== KeyBorad PC core - GUIDED TEST SESSION (PROTOTYPE) ===")
    out(f"port={port}  keymap={KEYMAP_PATH.relative_to(ROOT)}  "
        f"grace={args.grace:.0f}ms  legato={'on' if args.legato else 'off'}")
    out(f"logs: {jsonl_path.relative_to(ROOT)}  +  {text_path.relative_to(ROOT)}")
    synth = make_synth(args, out)
    engine = NoteEngine(
        channels,
        EngineConfig(
            velocity=args.velocity,
            release_grace_ms=args.grace,
            gliss_legato=args.legato,
        ),
    )
    monitor = DeviceMonitor(out)
    try:
        source = SerialSource(port)
    except Exception as exc:
        out(f"!! cannot open {port}: {exc}")
        out("   (is another program, or another copy of this one, using the port?)")
        synth.close()
        out.close()
        jsonl.close()
        return 2

    jsonl.add(
        "session_start",
        stamp=stamp,
        port=port,
        grace_ms=args.grace,
        legato=args.legato,
        velocity=args.velocity,
        synth=synth.name,
    )

    # First status line: proves the device is talking before we start.
    first = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        item = source.poll()
        if isinstance(item, Frame):
            first = item
            break
        if isinstance(item, Notice):
            monitor.observe_notice(item.text, item.t)
            out(f"dev: {item.text}")
    if first is None:
        out("!! no status line within 5 s. Is the wiring-test firmware running?")
        out("   Expected: [  1234 ms]  0x5A OK ... keys: ...")
        source.close()
        synth.close()
        out.close()
        jsonl.close()
        return 2
    monitor.observe(first)
    out(f"device: uptime {first.dev_ms/1000.0:.1f} s   modules: {monitor.summary_line()}")
    out("")

    plan = make_plan()
    results = []
    overall_ok = True

    try:
        for index, step in enumerate(plan, 1):
            offset = step.octave * 12 + step.transpose
            engine.set_octave(step.octave)
            engine.set_transpose(step.transpose)
            engine.max_polyphony = 0

            # Adopt the device's current state before recording. Anything that
            # happened while the previous result was being read is history,
            # not a fresh press.
            step_origin = time.monotonic()
            settled = settle_source(source, 0.3, monitor, out, jsonl)
            sync_active = settled if settled is not None else set(engine.mask)
            for event in engine.sync(sync_active, time.monotonic()):
                send_event(event, synth)
                out("  sync-off: " + fmt_event(event, step_origin))
                jsonl.add("event", **event_dict(event))

            out("")
            out("-" * 72)
            out(f"{step.sid} ({index}/{len(plan)})  {step.title}")
            out(f"  {step.instruction}")
            if step.keys:
                shown = ", ".join(
                    f"key {k} ({expected_name(k, offset, keys)})" for k in step.keys[:8]
                )
                if len(step.keys) > 8:
                    shown += f", ... key {step.keys[-1]}"
                out(f"  keys: {shown}")
            if step.octave or step.transpose:
                out(f"  offset for this step: octave {step.octave:+d}, transpose {step.transpose:+d}")
            if sync_active:
                held = ", ".join(
                    f"ch{ch}" for ch in sorted(sync_active) if ch in channels
                )
                out(f"  note: already active ({held}); release before starting")
            read_hotkeys()  # drop anything typed during step setup
            out("  recording starts now -- no time limit.")
            if step.optional:
                out("  type s + Enter to skip, or do the action and press Enter when done.")
            else:
                out("  release all keys, then press Enter when done.")

            jsonl.add(
                "step_start",
                sid=step.sid,
                title=step.title,
                instruction=step.instruction,
                until_enter=True,
                octave=step.octave,
                transpose=step.transpose,
            )

            events: list[NoteEvent] = []
            latencies: list[float] = []
            maxpoly = 0
            frames = 0
            transition_start = len(monitor.transitions)
            stop_at: Optional[float] = None
            skipped = False

            while True:
                now = time.monotonic()
                if stop_at is not None and (engine.polyphony() == 0 or now >= stop_at):
                    break

                item = source.poll()
                now = time.monotonic()
                fresh: list[NoteEvent] = []
                if isinstance(item, Frame):
                    monitor.observe(item)
                    frames += 1
                    jsonl.add(
                        "frame",
                        t=round(item.t, 4),
                        dev_ms=item.dev_ms,
                        active=sorted(item.active),
                        modules={f"0x{a:02X}": ok for a, ok in item.modules.items()},
                    )
                    fresh += engine.update(item)
                elif isinstance(item, Notice):
                    monitor.observe_notice(item.text, item.t)
                    out(f"  dev: {item.text}")
                    jsonl.add("notice", t=round(item.t, 4), text=item.text)
                fresh += engine.tick(now)

                for event in fresh:
                    latency = (time.monotonic() - event.t) * 1e6
                    send_event(event, synth)
                    events.append(event)
                    latencies.append(latency)
                    out("  " + fmt_event(event, step_origin))
                    jsonl.add("event", **event_dict(event))

                maxpoly = max(maxpoly, engine.polyphony())
                monitor.watchdog(now)

                if stop_at is None:
                    typed = read_hotkeys()
                    if step.optional and any(ch in ("s", "S") for ch in typed):
                        skipped = True
                        break
                    if any(ch in ("\r", "\n") for ch in typed):
                        stop_at = time.monotonic() + 2.0
                        jsonl.add("operator_done", sid=step.sid)
                        out("  done -- waiting for keys still down (up to 2 s)...")

            # Consume a stray Enter so it cannot end the next step instantly.
            time.sleep(0.1)
            read_hotkeys()

            if skipped:
                out("  SKIPPED")
                results.append((step, None, "SKIP", "operator skipped"))
                jsonl.add("step_skipped", sid=step.sid)
                continue

            if engine.polyphony() > 0:
                stuck = engine.polyphony()
                out(f"  !! {stuck} note(s) still held; panicking")
                panic_events = engine.panic(time.monotonic())
                for event in panic_events:
                    send_event(event, synth)
                    events.append(event)
                    out("  " + fmt_event(event, step_origin))
                    jsonl.add("event", **event_dict(event))

            stats = compute_stats(events, maxpoly, latencies)
            verdict, detail = check_step(
                step, stats, monitor.transitions[transition_start:]
            )
            if verdict == "WARN":
                overall_ok = False
            results.append((step, stats, verdict, detail))

            out(
                f"  on={stats.ons} off={stats.offs} keys={keys_text(stats.on_keys)} "
                f"maxpoly={stats.maxpoly} frames={frames}"
            )
            if stats.held:
                out(f"  held {min(stats.held):.0f}-{max(stats.held):.0f} ms   {latency_text(stats)}")
            out(f"  RESULT: {verdict} - {detail}")
            jsonl.add(
                "step_result",
                sid=step.sid,
                ons=stats.ons,
                offs=stats.offs,
                maxpoly=stats.maxpoly,
                on_keys={str(k): v for k, v in stats.on_keys.items()},
                on_midis=stats.on_midis,
                held_ms=[round(h, 1) for h in stats.held],
                verdict=verdict,
                detail=detail,
            )

        out("")
        out("================ TEST SUMMARY ================")
        for step, stats, verdict, detail in results:
            if stats is None:
                line = f"  on=-   off=-   poly=-   {verdict}"
            else:
                line = (
                    f"  on={stats.ons:<3} off={stats.offs:<3} poly={stats.maxpoly:<2} "
                    f"{verdict}"
                )
            out(f"{step.sid:<4} {step.title:<26} {line}")
            out(f"     {detail}")

        passed = sum(1 for _s, _st, v, _d in results if v == "PASS")
        warned = sum(1 for _s, _st, v, _d in results if v == "WARN")
        skipped = sum(1 for _s, _st, v, _d in results if v in ("SKIP", "INFO"))
        out("")
        out(f"steps: {passed} PASS, {warned} WARN, {skipped} SKIP/INFO")
        out(f"module transitions: {len(monitor.transitions)}")
        out(f"log: {jsonl_path.relative_to(ROOT)}")
        out(f"text: {text_path.relative_to(ROOT)}")
        out("VERDICT: " + ("PASS - all scripted cases behaved" if overall_ok else "WARN - inspect the lines above"))
        jsonl.add(
            "session_end",
            passed=passed,
            warned=warned,
            skipped=skipped,
            transitions=len(monitor.transitions),
            overall="PASS" if overall_ok else "WARN",
        )
        return 0 if overall_ok else 1
    except KeyboardInterrupt:
        out("")
        out("!! interrupted; silencing all notes")
        return 130
    finally:
        for event in engine.panic(time.monotonic()):
            send_event(event, synth)
        synth.panic()
        source.close()
        synth.close()
        out.close()
        jsonl.close()


# ---------------------------------------------------------------------------
# Live play
# ---------------------------------------------------------------------------


def read_hotkeys() -> list[str]:
    if not sys.stdin.isatty():
        return []
    if os.name == "nt":
        try:
            import msvcrt
        except ImportError:
            return []
        pressed = []
        try:
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue
                pressed.append(char)
        except Exception:
            return []
        return pressed
    import select

    pressed = []
    while select.select([sys.stdin], [], [], 0)[0]:
        pressed.append(sys.stdin.read(1))
    return pressed


HELP_LIVE = """
controls:
  [ ]      octave -1 / +1
  - +      transpose -1 / +1 semitone
  p        cycle synth program
  l        toggle glissando legato
  k        panic (all notes off)
  h        show this help
  q        quit
""".strip("\n")

PROGRAM_INDEX = 0


def handle_hotkeys(keys: list[str], engine: NoteEngine, synth, out: Out, origin: float) -> bool:
    global PROGRAM_INDEX
    for char in keys:
        if char in ("q", "Q"):
            return False
        if char in ("h", "?"):
            out(HELP_LIVE)
        elif char in ("k", "K"):
            events = engine.panic(time.monotonic())
            synth.panic()
            for event in events:
                out(fmt_event(event, origin))
            out("panic: all notes off")
            out(state_line(engine))
        elif char == "]":
            value = engine.set_octave(engine.cfg.octave + 1)
            out(f"octave -> {value:+d}")
            if engine.polyphony():
                out("  !! held notes keep their old pitch; release and re-press")
            out(state_line(engine))
        elif char == "[":
            value = engine.set_octave(engine.cfg.octave - 1)
            out(f"octave -> {value:+d}")
            if engine.polyphony():
                out("  !! held notes keep their old pitch; release and re-press")
            out(state_line(engine))
        elif char in ("+", "="):
            value = engine.set_transpose(engine.cfg.transpose + 1)
            out(f"transpose -> {value:+d}")
            if engine.polyphony():
                out("  !! held notes keep their old pitch; release and re-press")
            out(state_line(engine))
        elif char in ("-", "_"):
            value = engine.set_transpose(engine.cfg.transpose - 1)
            out(f"transpose -> {value:+d}")
            if engine.polyphony():
                out("  !! held notes keep their old pitch; release and re-press")
            out(state_line(engine))
        elif char in ("p", "P"):
            PROGRAM_INDEX = (PROGRAM_INDEX + 1) % len(PROGRAMS)
            name = synth.program(PROGRAM_INDEX)
            out(f"program {PROGRAM_INDEX + 1}/{len(PROGRAMS)} -> {name}")
        elif char in ("l", "L"):
            legato = engine.set_legato(not engine.cfg.gliss_legato)
            out(f"glissando legato -> {'on' if legato else 'off'}")
            out(state_line(engine))
    return True


def cmd_live(args) -> int:
    port = pick_port(args.port)
    _data, channels = load_keymap()
    out = Out()
    out("=== KeyBorad PC core - LIVE (PROTOTYPE) ===")
    out(
        f"port={port}  keymap 32 keys over 36 channels  "
        f"grace={args.grace:.0f}ms  legato={'on' if args.legato else 'off'}"
    )
    synth = make_synth(args, out)
    engine = NoteEngine(
        channels,
        EngineConfig(
            octave=args.octave,
            transpose=args.transpose,
            velocity=args.velocity,
            release_grace_ms=args.grace,
            gliss_legato=args.legato,
        ),
    )
    monitor = DeviceMonitor(out)
    try:
        source = SerialSource(port)
    except Exception as exc:
        out(f"!! cannot open {port}: {exc}")
        out("   (is another program, or another copy of this one, using the port?)")
        synth.close()
        return 2
    origin = time.monotonic()

    first = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        item = source.poll()
        if isinstance(item, Frame):
            first = item
            break
        if isinstance(item, Notice):
            monitor.observe_notice(item.text, item.t)
            out(f"dev: {item.text}")
    if first is not None:
        monitor.observe(first)
        out(
            f"device: uptime {first.dev_ms/1000.0:.1f} s   modules: {monitor.summary_line()}"
        )
        for event in engine.update(first):
            send_event(event, synth)
            out(fmt_event(event, origin))
    else:
        out("!! no status line within 5 s; still listening (is the firmware running?)")
    out("audio velocity is fixed at %d (firmware v1 sends binary touch bits)" % args.velocity)
    out(HELP_LIVE)
    out("")
    last_sig = None
    note_count = 0
    stop_at = origin + args.duration if args.duration > 0 else None

    try:
        running = True
        while running:
            if stop_at is not None and time.monotonic() >= stop_at:
                break
            item = source.poll()
            now = time.monotonic()
            fresh: list[NoteEvent] = []
            if isinstance(item, Frame):
                monitor.observe(item)
                fresh += engine.update(item)
            elif isinstance(item, Notice):
                monitor.observe_notice(item.text, item.t)
                out(f"dev: {item.text}")
            fresh += engine.tick(now)

            for event in fresh:
                send_event(event, synth)
                note_count += 1
                out(fmt_event(event, origin))

            sig = tuple((v.channel, v.midi) for v in engine.active_list())
            if fresh or sig != last_sig:
                out(state_line(engine))
                last_sig = sig

            monitor.watchdog(now)
            running = handle_hotkeys(read_hotkeys(), engine, synth, out, origin)
            if not running:
                break
    except KeyboardInterrupt:
        out("")
        out("interrupted")
    finally:
        panic_events = engine.panic(time.monotonic())
        for event in panic_events:
            send_event(event, synth)
        synth.panic()
        source.close()
        synth.close()

    out("")
    out(
        f"session: {note_count} MIDI events, max polyphony {engine.max_polyphony}, "
        f"{len(monitor.transitions)} module transition(s)"
    )
    return 0


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


def cmd_ports(_args) -> int:
    try:
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial is missing. Run: python -m pip install pyserial")
    ports = list(list_ports.comports())
    if not ports:
        print("no serial ports")
        return 1
    for port in ports:
        marker = "  <- Espressif" if port.vid == 0x303A else ""
        print(f"{port.device:<8} {port.description}{marker}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def add_audio_args(parser, default_no_audio: bool) -> None:
    parser.add_argument("--no-audio", action="store_true", default=default_no_audio,
                        help="log MIDI events but do not open the synth")
    parser.add_argument("--gain", type=float, default=0.6, help="FluidSynth output gain")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="KeyBorad PC-side core (throwaway prototype)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("sim", help="replay a scripted session with no hardware")
    sim.add_argument("--audio", action="store_true", help="play the simulated session")
    sim.add_argument("--speed", type=float, default=1.0, help="playback speed with --audio")
    sim.add_argument("--legato", action="store_true")
    sim.add_argument("--grace", type=float, default=20.0)
    sim.add_argument("--velocity", type=int, default=100)
    add_audio_args(sim, default_no_audio=False)

    live = sub.add_parser("live", help="play from the real instrument")
    live.add_argument("--port")
    live.add_argument("--octave", type=int, default=0)
    live.add_argument("--transpose", type=int, default=0)
    live.add_argument("--legato", action="store_true")
    live.add_argument("--grace", type=float, default=20.0)
    live.add_argument("--velocity", type=int, default=100)
    live.add_argument("--duration", type=float, default=0.0,
                      help="stop after N seconds (0 = run until q/Ctrl+C)")
    add_audio_args(live, default_no_audio=False)

    test = sub.add_parser("test", help="guided one-shot test session")
    test.add_argument("--port")
    test.add_argument("--legato", action="store_true")
    test.add_argument("--grace", type=float, default=20.0)
    test.add_argument("--velocity", type=int, default=100)
    add_audio_args(test, default_no_audio=False)

    sub.add_parser("ports", help="list serial ports")

    args = parser.parse_args(argv)
    if args.command == "sim":
        return cmd_sim(args)
    if args.command == "live":
        return cmd_live(args)
    if args.command == "test":
        return cmd_test(args)
    if args.command == "ports":
        return cmd_ports(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
