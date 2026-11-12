"""Instrument controller: serial frames + mouse input -> notes, mapping, pads.

One 20 ms timer is the single cadence. Hardware key bits and mouse-simulated
key bits are merged into one mask, fed to NoteEngine, and the resulting events
go to the synth. That means the app is fully playable with no hardware, and
the hardware path is the same code path.

This is the P1 shell's AppState. It owns the note engine, mapping, octave /
transpose, program, sustain and the four physical pads. The widgets are dumb
views over it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from .mapping import (
    KEY_COUNT,
    MapPreset,
    MappingSpec,
    PRESETS,
    PRESET_BY_KEY,
    apply_preset,
    mapping_spec,
    preset_at,
    with_split_bar,
)
from .note_engine import MAX_OCTAVE, MIN_OCTAVE, Frame, NoteEngine, midi_name

ROOT = Path(__file__).resolve().parents[3]
KEYMAP_PATH = ROOT / "mapping" / "keymap.json"

PAD_CHANNELS = {1: 33, 2: 34, 3: 35, 4: 36}
MAP_LONG_PRESS_S = 0.30
STALE_AFTER_S = 3.5


def load_keymap() -> dict[int, dict]:
    data = json.loads(KEYMAP_PATH.read_text(encoding="utf-8"))
    return {int(item["channel"]): dict(item) for item in data["keys"]}


class Instrument(QObject):
    events = Signal(list)          # list[NoteEvent] from this tick
    activeChanged = Signal(object)  # active physical keys (1..32)
    stateChanged = Signal()        # mapping / octave / program / sustain / device
    padStateChanged = Signal(object)  # pad index 1..4 -> bool
    sourceChanged = Signal()       # instrument / keyboard / sim source mix

    def __init__(self, synth, poll_ms: int = 20, parent=None):
        super().__init__(parent)
        self.synth = synth
        self.keymap = load_keymap()
        self.key_to_channel = {int(info["key"]): ch for ch, info in self.keymap.items()}

        self.engine = NoteEngine(self.keymap)
        self.preset_index = 0
        self.auto_follow = False
        self._auto_follow_octave: int | None = None
        self.program_index = 0
        self.muted = False
        self.sustain = False
        self._stale = False
        # While a generated drill is open, the mapping is a fixed chromatic
        # C4–G6 range and every mapping/octave/transpose action is locked. The
        # previous state is restored when the drill closes.
        self._drill_preset: MapPreset | None = None
        self._drill_saved: tuple[int, int, int, bool] | None = None
        # A study item may declare a mapping preset (H7f). Unlike a drill this
        # is advisory: the learner can still change the preset/octave during
        # practice, and the pre-session state returns when the item closes.
        self._content_saved: tuple[int, int, int, bool] | None = None
        # A structured content mapping (base/steps/split) is not in PRESETS;
        # it lives here and takes precedence over preset_index.
        self._content_preset: MapPreset | None = None
        # A user-dragged split boundary for the current score (H7f). The
        # derived preset is cached because paint loops read current_preset.
        self._split_bar: int | None = None
        self._split_cache: tuple[MapPreset, int, MapPreset] | None = None
        self.mapping_locked = False
        # Calibration mode: hardware keys still drive the light bar, but no
        # note reaches the synth, follow session, recorder or learning path,
        # and mapping/octave/program controls are locked.
        self.calibration_active = False
        self._calibration_saved: tuple | None = None

        self.hw_keys: set[int] = set()
        self.hw_pads: set[int] = set()
        self.sim_keys: set[int] = set()
        self.sim_pads: set[int] = set()
        self.kbd_keys: set[int] = set()
        self.modules: dict[int, bool] = {}
        self.connected = False
        self.connection_detail = ""
        self.last_frame_t: Optional[float] = None

        self._pad_down: dict[int, bool] = {i: False for i in PAD_CHANNELS}
        self._pad_press_t: dict[int, float] = {}
        self._last_active: set[int] = set()
        self._last_sources: set[str] = set()

        apply_preset(self.engine.keymap, self.current_preset)
        self.synth.program(self.program_index)

        self._timer = QTimer(self)
        self._timer.setInterval(poll_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- read side --------------------------------------------------------

    def _base_preset(self) -> MapPreset:
        return (
            self._drill_preset
            or self._content_preset
            or preset_at(self.preset_index)
        )

    @property
    def current_preset(self):
        base = self._base_preset()
        if self._split_bar is None or base.split is None:
            return base
        cache = self._split_cache
        if (
            cache is not None
            and cache[0] == base
            and cache[1] == self._split_bar
        ):
            return cache[2]
        derived = with_split_bar(base, self._split_bar)
        self._split_cache = (base, self._split_bar, derived)
        return derived

    @property
    def split_bar(self) -> int | None:
        split = self.current_preset.split
        return split.bar if split is not None else None

    def set_split_override(self, bar: int, notify: bool = True) -> bool:
        """Move the current split boundary without touching the saved preset."""
        if self._base_preset().split is None:
            return False
        value = max(1, min(KEY_COUNT - 1, int(bar)))
        if self._split_bar == value:
            return True
        self._split_bar = value
        self._split_cache = None
        apply_preset(self.engine.keymap, self.current_preset)
        if notify:
            self.stateChanged.emit()
        return True

    def clear_split_override(self, notify: bool = False) -> bool:
        if self._split_bar is None:
            return False
        self._split_bar = None
        self._split_cache = None
        apply_preset(self.engine.keymap, self.current_preset)
        if notify:
            self.stateChanged.emit()
        return True

    @property
    def offset(self) -> int:
        return self.engine.cfg.offset

    @property
    def octave(self) -> int:
        return self.engine.cfg.octave

    @property
    def transpose(self) -> int:
        return self.engine.cfg.transpose

    def range_label(self) -> str:
        return self.current_preset.range_label(self.offset)

    def midi_for_key(self, key_no: int) -> int:
        return max(
            0, min(127, self.current_preset.midi_for_key(key_no) + self.offset)
        )

    def key_enabled(self, key_no: int) -> bool:
        return self.current_preset.is_enabled(key_no)

    def note_for_key(self, key_no: int) -> str:
        if not self.key_enabled(key_no):
            return "—"
        return _midi_name(self.midi_for_key(key_no))

    def bar_for_midi(self, midi: int) -> int | None:
        """First physical bar that currently plays this MIDI note."""
        for key_no in range(1, 33):
            if not self.key_enabled(key_no):
                continue
            if self.midi_for_key(key_no) == midi:
                return key_no
        return None

    def active_keys(self) -> list[int]:
        return sorted(v.key for v in self.engine.voices.values())

    def active_notes(self) -> list[str]:
        return [v.note for v in self.engine.active_list()]

    def polyphony(self) -> int:
        return self.engine.polyphony()

    def pad_down(self, index: int) -> bool:
        return self._pad_down.get(index, False)

    def module_count(self) -> int:
        return sum(1 for ok in self.modules.values() if ok)

    def hardware_stale(self) -> bool:
        if not self.connected or self.last_frame_t is None:
            return False
        return time.monotonic() - self.last_frame_t > STALE_AFTER_S

    # -- hardware input ---------------------------------------------------

    def set_hardware_frame(self, frame: Frame) -> None:
        was_connected = self.connected
        old_keys = self.hw_keys
        old_pads = self.hw_pads
        old_modules = self.modules

        self.connected = True
        self.last_frame_t = time.monotonic()
        self.modules = dict(frame.modules)
        self.hw_keys = {
            ch for ch in frame.active if ch in self.keymap
        }
        self.hw_pads = {ch for ch in frame.active if ch in PAD_CHANNELS.values()}
        # Serial frames arrive ~50 times a second. A held key repeats the same
        # mask, and refreshing every widget for each frame is pure waste; only
        # emit when something the UI shows actually changed.
        if (
            not was_connected
            or self.hw_keys != old_keys
            or self.hw_pads != old_pads
            or self.modules != old_modules
        ):
            self.stateChanged.emit()

    def set_connection(self, connected: bool, detail: str) -> None:
        self.connected = connected
        self.connection_detail = detail
        if not connected:
            self.hw_keys.clear()
            self.hw_pads.clear()
            self.last_frame_t = None
            self._stale = False
        self.stateChanged.emit()

    # -- simulated (mouse) input -----------------------------------------

    def press_key(self, key_no: int) -> None:
        if self.calibration_active:
            return
        channel = self.key_to_channel.get(key_no)
        if channel is not None:
            self.sim_keys.add(channel)

    def release_key(self, key_no: int) -> None:
        channel = self.key_to_channel.get(key_no)
        if channel is not None:
            self.sim_keys.discard(channel)

    def press_pad(self, index: int) -> None:
        if self.calibration_active:
            return
        self.sim_pads.add(PAD_CHANNELS[index])

    def release_pad(self, index: int) -> None:
        self.sim_pads.discard(PAD_CHANNELS[index])

    # -- computer keyboard input (§7.2: same engine, same 20 ms cadence) --

    def press_keyboard(self, key_no: int) -> None:
        if self.calibration_active:
            return
        channel = self.key_to_channel.get(key_no)
        if channel is not None:
            self.kbd_keys.add(channel)

    def release_keyboard(self, key_no: int) -> None:
        channel = self.key_to_channel.get(key_no)
        if channel is not None:
            self.kbd_keys.discard(channel)

    def release_all_keyboard(self) -> None:
        self.kbd_keys.clear()

    def input_sources(self) -> set[str]:
        sources: set[str] = set()
        if self.hw_keys or self.hw_pads:
            sources.add("instrument")
        if self.kbd_keys:
            sources.add("keyboard")
        if self.sim_keys or self.sim_pads:
            sources.add("sim")
        return sources

    # -- generated-drill mapping -----------------------------------------

    def begin_drill_mapping(
        self, base_midi: int = 60, label_cn: str = "识谱训练"
    ) -> None:
        """Temporarily map bars 1–32 to a chromatic range starting at base.

        The drill needs exact pitches (C4 must be reachable even though the
        default performance mapping starts at F4). The user's preset, octave,
        transpose and auto-follow are restored by end_drill_mapping(). Calling
        begin twice keeps the original saved state, so a retry is safe.
        `label_cn` names the temporary mapping in the header chip, so a
        stage-0 step drill does not call itself a note-reading drill.
        """
        if self._drill_saved is not None:
            return
        self._drill_saved = (
            self.preset_index,
            self.engine.cfg.octave,
            self.engine.cfg.transpose,
            self.auto_follow,
        )
        self._drill_preset = MapPreset(
            key="drill",
            label="Drill",
            label_cn=label_cn,
            note=f"{midi_name(base_midi)}–{midi_name(base_midi + 31)} · {label_cn}用",
            base=max(0, min(96, int(base_midi))),
            steps=tuple(range(12)),
        )
        self.mapping_locked = True
        self.auto_follow = False
        apply_preset(self.engine.keymap, self._drill_preset)
        self.engine.set_octave(0)
        self.engine.set_transpose(0)
        self.stateChanged.emit()

    def end_drill_mapping(self) -> None:
        saved = self._drill_saved
        if saved is None:
            return
        self._drill_saved = None
        self.mapping_locked = False
        self._drill_preset = None
        self.preset_index, octave, transpose, auto_follow = saved
        apply_preset(self.engine.keymap, self.current_preset)
        self.engine.set_octave(octave)
        self.engine.set_transpose(transpose)
        self.auto_follow = auto_follow
        self.stateChanged.emit()

    # -- content-declared mapping (H7f) -----------------------------------

    def begin_content_mapping(self, key) -> bool:
        """Apply a mapping declared by the practice item, remembering the user's.

        `key` is a preset key string or a structured ``MappingSpec``
        (CONTENT_SCHEMA §6.1). Unknown declarations are ignored, never raised:
        bad metadata must not break the practice hand-off. Registered presets
        zero the octave/transpose so a split mapping's registers line up with
        the score; a structured spec may carry its own offsets. The learner may
        still change the mapping (this is not a drill-style lock) and the
        pre-session state returns in end_content_mapping().
        """
        if self.mapping_locked or self._drill_saved is not None:
            return False
        # Keep the *original* snapshot when switching study items: the state
        # visible now may already be a previous item's override.
        saved = self._content_saved
        if saved is None:
            saved = (
                self.preset_index,
                self.engine.cfg.octave,
                self.engine.cfg.transpose,
                self.auto_follow,
            )
        normalized = mapping_spec(key)
        if normalized is None:
            if self._content_saved is None:
                return False
            self._content_saved = saved
            return self.end_content_mapping()
        self._content_saved = saved
        # A new content declaration starts from its own split bar; the saved
        # per-score override is applied afterwards by the window.
        self._split_bar = None
        self._split_cache = None
        if isinstance(normalized, MappingSpec):
            self._content_preset = normalized.to_preset()
            octave = normalized.octave
            transpose = normalized.transpose
        else:
            self._content_preset = None
            self.preset_index = PRESETS.index(PRESET_BY_KEY[normalized])
            octave = 0
            transpose = 0
        apply_preset(self.engine.keymap, self.current_preset)
        self.engine.set_octave(octave)
        self.engine.set_transpose(transpose)
        self.stateChanged.emit()
        return True

    def end_content_mapping(self) -> bool:
        """Restore the preset/octave/transpose/auto-follow from before practice."""
        saved = self._content_saved
        if saved is None:
            return False
        self._content_saved = None
        self._content_preset = None
        self._split_bar = None
        self._split_cache = None
        self.preset_index, octave, transpose, auto_follow = saved
        self.auto_follow = auto_follow
        apply_preset(self.engine.keymap, self.current_preset)
        self.engine.set_octave(octave)
        self.engine.set_transpose(transpose)
        self.stateChanged.emit()
        return True

    # -- calibration mode --------------------------------------------------

    def begin_calibration(self) -> bool:
        """Silence playing notes and freeze controls while calibrating."""
        if self.calibration_active:
            return False
        self._calibration_saved = (
            self.preset_index,
            self.engine.cfg.octave,
            self.engine.cfg.transpose,
            self.program_index,
            self.muted,
            self.auto_follow,
            self.mapping_locked,
        )
        self.calibration_active = True
        self.mapping_locked = True
        self.auto_follow = False
        self.release_all_keyboard()
        self.panic()
        self.stateChanged.emit()
        return True

    def end_calibration(self) -> bool:
        """Restore the performance state saved by begin_calibration()."""
        saved = self._calibration_saved
        if saved is None:
            return False
        self._calibration_saved = None
        self.calibration_active = False
        (
            self.preset_index,
            octave,
            transpose,
            self.program_index,
            self.muted,
            self.auto_follow,
            self.mapping_locked,
        ) = saved
        apply_preset(self.engine.keymap, self.current_preset)
        self.engine.set_octave(octave)
        self.engine.set_transpose(transpose)
        self.synth.program(self.program_index)
        self.synth.set_mute(self.muted)
        self.panic()
        self.stateChanged.emit()
        return True

    # -- actions ----------------------------------------------------------

    def set_preset(self, index: int) -> None:
        if self.mapping_locked or self.calibration_active:
            return
        # An explicit preset choice wins over a custom content mapping and any
        # dragged split point; the content session's saved original still
        # comes back on exit.
        self._content_preset = None
        self._split_bar = None
        self._split_cache = None
        self.preset_index = index % len(PRESETS)
        if self.auto_follow:
            self.auto_follow = False
            self._restore_auto_follow_octave()
        apply_preset(self.engine.keymap, self.current_preset)
        self.stateChanged.emit()

    def cycle_preset(self) -> None:
        if self.mapping_locked:
            return
        self.set_preset(self.preset_index + 1)

    def toggle_auto_follow(self) -> None:
        if self.mapping_locked or self.calibration_active:
            return
        if not self.auto_follow:
            # Remember the octave the user actually chose; turning auto-follow
            # off must not leave them stranded in a score-fitted octave.
            self._auto_follow_octave = self.engine.cfg.octave
            self.auto_follow = True
        else:
            self.auto_follow = False
            self._restore_auto_follow_octave()
        self.stateChanged.emit()

    def _restore_auto_follow_octave(self) -> None:
        saved = self._auto_follow_octave
        self._auto_follow_octave = None
        if saved is not None:
            self.engine.set_octave(saved)

    def set_octave(self, delta: int) -> None:
        if self.mapping_locked or self.calibration_active:
            return
        self.engine.set_octave(self.engine.cfg.octave + delta)
        self.stateChanged.emit()

    def set_octave_absolute(self, octave: int) -> None:
        """Used by 自动跟随; does nothing when the octave is already right."""
        if self.mapping_locked or self.calibration_active:
            return
        value = max(MIN_OCTAVE, min(MAX_OCTAVE, int(octave)))
        if value == self.engine.cfg.octave:
            return
        self.engine.set_octave(value)
        self.stateChanged.emit()

    def set_transpose(self, delta: int) -> None:
        if self.mapping_locked or self.calibration_active:
            return
        self.engine.set_transpose(self.engine.cfg.transpose + delta)
        self.stateChanged.emit()

    def reset_offsets(self) -> None:
        if self.mapping_locked or self.calibration_active:
            return
        self.engine.set_octave(0)
        self.engine.set_transpose(0)
        self.stateChanged.emit()

    def set_program(self, index: int) -> None:
        if self.calibration_active:
            return
        self.program_index = index % len(self.synth_programs())
        self.synth.program(self.program_index)
        self.stateChanged.emit()

    def cycle_program(self) -> None:
        self.set_program(self.program_index + 1)

    def synth_programs(self):
        from .synth_service import PROGRAMS

        return PROGRAMS

    def toggle_mute(self) -> None:
        if self.calibration_active:
            return
        self.muted = not self.muted
        self.synth.set_mute(self.muted)
        self.stateChanged.emit()

    def hold_sustain(self, on: bool) -> None:
        """Shift / the function capsule / pad 1 all use this one path."""
        if self.calibration_active and on:
            return
        if self.sustain == on:
            return
        self.sustain = on
        self.synth.sustain(on)
        self.stateChanged.emit()

    def panic(self) -> None:
        now = time.monotonic()
        for event in self.engine.panic(now):
            if event.kind == "off":
                self.synth.note_off(event.midi)
        self.synth.panic()
        if self.sustain:
            self.sustain = False
            self.synth.sustain(False)
        self._publish_active(now)
        self.stateChanged.emit()

    def shutdown(self) -> None:
        self._timer.stop()
        self.panic()
        self.synth.close()

    # -- cadence ----------------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        stale = self.hardware_stale()
        if stale:
            self.hw_keys.clear()
            self.hw_pads.clear()
        if stale != self._stale:
            self._stale = stale
            self.stateChanged.emit()

        if self.calibration_active:
            # Feed the engine so the light bar still shows which pads are
            # pressed, but drop the events: no synth, no follow, no recorder.
            frame = Frame(t=now, active=set(self.hw_keys), modules=self.modules)
            self.engine.update(frame)
            self.engine.tick(now)
            self._publish_active(now)
            sources = self.input_sources()
            if sources != self._last_sources:
                self._last_sources = sources
                self.sourceChanged.emit()
            return

        pad_mask = {ch for ch in PAD_CHANNELS.values() if ch in self.hw_pads or ch in self.sim_pads}
        self._process_pads(pad_mask, now)

        # Pads are separate controls, not part of the note engine's channel
        # mask; feeding 33..36 to it would only mark them "unknown channels".
        live_mask = set(self.hw_keys) | set(self.sim_keys) | set(self.kbd_keys)
        frame = Frame(t=now, active=live_mask, modules=self.modules)
        new_events = self.engine.update(frame)
        new_events += self.engine.tick(now)

        for event in new_events:
            if event.kind == "on":
                self.synth.note_on(event.midi, event.velocity)
            else:
                self.synth.note_off(event.midi)

        if new_events:
            self.events.emit(new_events)
        self._publish_active(now)
        sources = self.input_sources()
        if sources != self._last_sources:
            self._last_sources = sources
            self.sourceChanged.emit()

    def _publish_active(self, now: float) -> None:
        active = set(self.active_keys())
        if active != self._last_active:
            self._last_active = active
            self.activeChanged.emit(active)

    def _process_pads(self, mask: set[int], now: float) -> None:
        changed = False
        for index, channel in PAD_CHANNELS.items():
            down = channel in mask
            if down == self._pad_down[index]:
                continue
            self._pad_down[index] = down
            changed = True
            if down:
                self._pad_press_t[index] = now
                self._on_pad_press(index)
            else:
                self._on_pad_release(index, now)
        if changed:
            self.padStateChanged.emit(dict(self._pad_down))

    def _on_pad_press(self, index: int) -> None:
        if index == 1:
            self.hold_sustain(True)
        elif index == 2:
            self.set_octave(-1)
        elif index == 3:
            self.set_octave(+1)

    def _on_pad_release(self, index: int, now: float) -> None:
        if index == 1:
            self.hold_sustain(False)
        elif index == 4:
            held = now - self._pad_press_t.get(index, now)
            if held >= MAP_LONG_PRESS_S:
                self.toggle_auto_follow()
            else:
                self.cycle_preset()


def _midi_name(midi: int) -> str:
    from .note_engine import midi_name

    return midi_name(max(0, min(127, midi)))
