"""Audio output for the P1 shell.

FluidSynth + the vendored TimGM6mb SoundFont when available; otherwise a
silent backend with the same method surface, so the UI and the note engine
keep working and the status line says audio is unavailable.

The FluidSynth build lives under pc/prototype/vendor today (the prototype
brought it in). Packaging moves it to pc/resources in P4; both locations are
searched here so nothing breaks in between.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .drums import DRUM_CHANNEL
from .programs import CATALOG, PROGRAMS

PC = Path(__file__).resolve().parents[2]

# The demo player uses its own MIDI channel so a demo note-off can never stop
# a note the user is holding on channel 0.
DEMO_CHANNEL = 15

# The rhythm drill's metronome uses a third channel so its short note-offs do
# not cut a learner's held note. It keeps its own GM program: switching the
# main sound must never turn the click into a saxophone.
CLICK_CHANNEL = 14
CLICK_PROGRAM = 115  # GM 115 Woodblock
CLICK_MIDI = 76      # low woodblock
CLICK_ACCENT_MIDI = 77  # high woodblock (bar accent)

# Live layer/split auditions use their own channel so the base key (channel 0)
# and the demo/metronome channels never cut each other.
LAYER_CHANNEL = 13
SPLIT_LEFT_CHANNEL = 11
SPLIT_RIGHT_CHANNEL = 12

# Left-hand auto-accompaniment (H7e): a separate channel so its note-offs can
# never cut a note the learner holds, and so stopping practice can silence the
# accompaniment without touching the live keyboard.
ACCOMPANIMENT_CHANNEL = 10

# Chinese-first labels; the English GM name stays in the tooltip.
PROGRAM_CN = {program.name: program.label for program in CATALOG}


def program_label_cn(name: str) -> str:
    return PROGRAM_CN.get(name, name)


def _find_dll_dir() -> Optional[Path]:
    for base in (PC / "vendor", PC / "prototype" / "vendor", PC / "resources"):
        for candidate in sorted(base.glob("fluidsynth-*/bin")):
            if any(candidate.glob("libfluidsynth-*.dll")):
                return candidate
    return None


def _find_soundfont() -> Optional[Path]:
    for base in (PC / "vendor", PC / "prototype" / "vendor", PC / "resources"):
        for candidate in sorted((base / "soundfont").glob("*.sf2")):
            return candidate
        for candidate in sorted(base.rglob("*.sf2")):
            return candidate
    return None


class NullSynth:
    name = "none"
    available = False
    samplerate = 0

    def program(self, index: int) -> str:
        return PROGRAMS[index % len(PROGRAMS)][1]

    def program_on(self, channel: int, program: int) -> None:
        pass

    def set_drum_kit(self, program: int) -> None:
        pass

    def channel_volume(self, channel: int, volume: float) -> None:
        pass

    def channel_pan(self, channel: int, pan: float) -> None:
        pass

    def set_reverb(self, level: float) -> None:
        pass

    def note_on(self, midi: int, velocity: int, channel: int | None = None) -> None:
        pass

    def note_off(self, midi: int, channel: int | None = None) -> None:
        pass

    def sustain(self, on: bool) -> None:
        pass

    def set_mute(self, muted: bool) -> None:
        pass

    def panic(self) -> None:
        pass

    def close(self) -> None:
        pass


class FluidSynthBackend:
    name = "fluidsynth"
    available = True

    def __init__(self, gain: float = 0.6):
        dll_dir = _find_dll_dir()
        soundfont = _find_soundfont()
        if dll_dir is None:
            raise RuntimeError("FluidSynth DLL not found under pc/vendor")
        if soundfont is None:
            raise RuntimeError("no .sf2 found under pc/vendor/soundfont")

        os.add_dll_directory(str(dll_dir))
        os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
        import fluidsynth

        self.soundfont = soundfont
        self.channel = 0
        self.samplerate = 48000
        self.fs = fluidsynth.Synth(gain=gain, samplerate=self.samplerate)
        self.sfid = self.fs.sfload(str(soundfont))
        if self.sfid < 0:
            raise RuntimeError(f"FluidSynth could not load {soundfont.name}")
        self.program(0)

        # Only the audio driver: this build has no usable MIDI input driver,
        # and the serial port is our MIDI source.
        self.fs.audio_driver = fluidsynth.new_fluid_audio_driver(
            self.fs.settings, self.fs.synth
        )
        if not self.fs.audio_driver:
            raise RuntimeError("FluidSynth could not open an audio output device")

    def program(self, index: int) -> str:
        program, name = PROGRAMS[index % len(PROGRAMS)]
        for channel in (
            self.channel,
            DEMO_CHANNEL,
            ACCOMPANIMENT_CHANNEL,
        ):
            self.fs.program_select(channel, self.sfid, 0, program)
        self.fs.program_select(CLICK_CHANNEL, self.sfid, 0, CLICK_PROGRAM)
        return name

    def program_on(self, channel: int, program: int) -> None:
        self.fs.program_select(
            channel, self.sfid, 0, max(0, min(127, int(program)))
        )

    def set_drum_kit(self, program: int) -> None:
        """GM drum kits live in bank 128 on MIDI channel 10."""
        self.fs.program_select(
            DRUM_CHANNEL, self.sfid, 128, max(0, min(127, int(program)))
        )

    def channel_volume(self, channel: int, volume: float) -> None:
        value = round(max(0.0, min(1.0, volume)) * 127)
        self.fs.cc(channel, 7, max(0, min(127, value)))

    def channel_pan(self, channel: int, pan: float) -> None:
        value = round((max(-1.0, min(1.0, pan)) + 1) * 63.5)
        self.fs.cc(channel, 10, max(0, min(127, value)))

    def set_reverb(self, level: float) -> None:
        # A project-wide send: one room for every voice, matching the model.
        amount = max(0.0, min(1.0, level))
        self.fs.set_reverb(0.4 + 0.5 * amount, 0.2, 0.6, amount)

    def note_on(self, midi: int, velocity: int, channel: int | None = None) -> None:
        self.fs.noteon(self.channel if channel is None else channel, midi, velocity)

    def note_off(self, midi: int, channel: int | None = None) -> None:
        self.fs.noteoff(self.channel if channel is None else channel, midi)

    def sustain(self, on: bool) -> None:
        self.fs.cc(self.channel, 64, 127 if on else 0)

    def set_mute(self, muted: bool) -> None:
        # Channel volume is the runtime-safe way to silence this pyfluidsynth
        # build (it exposes no fluid_synth_set_gain wrapper). All channels:
        # playback, split, and layer voices must obey the same volume button.
        for channel in range(16):
            self.fs.cc(channel, 7, 0 if muted else 127)

    def panic(self) -> None:
        for channel in range(16):
            self.fs.all_notes_off(channel)
            self.fs.all_sounds_off(channel)

    def close(self) -> None:
        try:
            self.panic()
        finally:
            self.fs.delete()


def make_synth(enabled: bool = True, gain: float = 0.6):
    """Return (synth, message). Falls back to silence rather than failing."""
    if not enabled:
        return NullSynth(), "音频已关闭（--no-audio）"
    try:
        synth = FluidSynthBackend(gain=gain)
        return synth, f"FluidSynth · {synth.soundfont.name}"
    except Exception as exc:  # missing DLL/SF2/audio device: keep the UI alive
        return NullSynth(), f"音频不可用（{exc}）"
