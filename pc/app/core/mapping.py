"""Map presets for the 32 physical keys.

The physical layout is fixed (keys 1..32, F4..C7 in equal temperament). A map
preset decides which MIDI note each physical key sends. Octave and transpose
are applied *after* the preset, at press time, by NoteEngine.

Pure data + pure functions: no Qt, no I/O. The app applies the selected
preset to the note engine's keymap; held voices keep the pitch they were
started with because the engine stores the MIDI number on the voice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .note_engine import midi_name

KEY_COUNT = 32


def _clamp_midi(value: int) -> int:
    return max(0, min(127, value))


def _midi_for_index(base: int, steps: tuple[int, ...], index: int) -> int:
    steps = steps or (0,)
    octave, degree = divmod(index, len(steps))
    return base + 12 * octave + steps[degree]


@dataclass(frozen=True)
class SplitMap:
    """Two mapping sides: bars 1..bar left, bars bar+1..32 right.

    Each side repeats its `steps` template up the keyboard exactly like a
    normal preset. The split is a register jump, not a chromatic seam: notes
    in the gap between the two sides are unreachable, which is the point --
    both hands can play far-apart registers at the same time.
    """

    bar: int
    left_base: int
    left_steps: tuple[int, ...]
    right_base: int
    right_steps: tuple[int, ...]

    def midi_for_key(self, key_no: int) -> int:
        key_no = max(1, min(KEY_COUNT, key_no))
        if key_no <= self.bar:
            return _midi_for_index(self.left_base, self.left_steps, key_no - 1)
        return _midi_for_index(
            self.right_base, self.right_steps, key_no - self.bar - 1
        )


@dataclass(frozen=True)
class MapPreset:
    key: str
    label: str
    label_cn: str
    note: str
    base: int              # MIDI note for key 1 (ignored when split is set)
    steps: tuple[int, ...]  # repeating semitones (ignored when split is set)
    split: SplitMap | None = None
    # 1-based physical keys that are deliberately silent under this preset
    # (the white-key preset uses them for the notes it does not cover).
    # A frozenset keeps MapPreset hashable for window._reachable's cache.
    disabled: frozenset[int] = frozenset()

    def is_enabled(self, key_no: int) -> bool:
        return max(1, min(KEY_COUNT, key_no)) not in self.disabled

    def enabled_keys(self) -> tuple[int, ...]:
        return tuple(
            key for key in range(1, KEY_COUNT + 1) if key not in self.disabled
        )

    def midi_for_key(self, key_no: int) -> int:
        """1-based physical key -> MIDI note (before octave/transpose).

        Disabled keys still return their underlying scale pitch; callers must
        check is_enabled() before treating it as playable.
        """
        if self.split is not None:
            return self.split.midi_for_key(key_no)
        i = max(1, min(KEY_COUNT, key_no)) - 1
        return _midi_for_index(self.base, self.steps, i)

    def key_range(self) -> tuple[int, int]:
        """Lowest and highest playable MIDI note (before offset).

        A split's two sides need not be ordered, so take the real min/max
        instead of trusting key 1 and key 32. Disabled keys are excluded.
        """
        values = [
            self.midi_for_key(key) for key in self.enabled_keys()
        ]
        if not values:
            return self.base, self.base
        return min(values), max(values)

    def range_with_offset(self, offset: int) -> tuple[int, int]:
        """Lowest and highest playable note after a semitone offset."""
        lo, hi = self.key_range()
        return _clamp_midi(lo + offset), _clamp_midi(hi + offset)

    def range_label(self, offset: int) -> str:
        """Human range label; split mappings show both registers."""
        if self.split is not None:
            return self._split_range_label(self.split, offset)
        if not self.enabled_keys():
            return "—"
        lo, hi = self.range_with_offset(offset)
        return f"{midi_name(lo)}–{midi_name(hi)}"

    def _split_range_label(self, split: SplitMap, offset: int) -> str:
        """Show both sides, never the misleading span across the gap."""
        sides: list[tuple[int, int]] = []
        if split.bar >= 1:
            left = self._side_range(1, min(split.bar, KEY_COUNT))
            if left is not None:
                sides.append(left)
        if split.bar < KEY_COUNT:
            right = self._side_range(max(1, split.bar + 1), KEY_COUNT)
            if right is not None:
                sides.append(right)
        if not sides:
            return "—"
        return " + ".join(
            f"{midi_name(_clamp_midi(lo + offset))}–"
            f"{midi_name(_clamp_midi(hi + offset))}"
            for lo, hi in sides
        )

    def _side_range(
        self, first_key: int, last_key: int
    ) -> tuple[int, int] | None:
        """Real min/max of one side's enabled keys; steps need not ascend."""
        values = [
            self.midi_for_key(key)
            for key in range(first_key, last_key + 1)
            if key not in self.disabled
        ]
        if not values:
            return None
        return min(values), max(values)


PRESETS: tuple[MapPreset, ...] = (
    MapPreset(
        key="chromatic",
        label="Chromatic",
        label_cn="半音阶",
        note="半音阶 · 每个物理键一个半音",
        base=65,
        steps=tuple(range(12)),
    ),
    MapPreset(
        key="cmajor",
        label="C Major",
        label_cn="C 大调",
        note="C 大调音阶铺满 32 键（更宽的音域）",
        base=48,
        steps=(0, 2, 4, 5, 7, 9, 11),
    ),
    MapPreset(
        key="aminor",
        label="A Minor",
        label_cn="A 小调",
        note="A 自然小调音阶铺满 32 键",
        base=57,
        steps=(0, 2, 3, 5, 7, 8, 10),
    ),
    MapPreset(
        key="pentatonic",
        label="Pentatonic",
        label_cn="五声音阶",
        note="C 大调五声音阶，适合即兴",
        base=36,
        steps=(0, 2, 4, 7, 9),
    ),
    MapPreset(
        key="split",
        label="Split 16/16",
        label_cn="左右分区",
        note="左手 1–16 低音区 C3–D#4，右手 17–32 高音区 C5–D#6",
        base=48,
        steps=tuple(range(12)),
        split=SplitMap(
            bar=16,
            left_base=48,
            left_steps=tuple(range(12)),
            right_base=72,
            right_steps=tuple(range(12)),
        ),
    ),
    MapPreset(
        key="white19",
        label="White keys C4–G6",
        label_cn="白键 19 键",
        note="C4–G6 白键 · 键 1–19 可弹，20–32 禁用（适合识谱入门）",
        base=60,
        steps=(0, 2, 4, 5, 7, 9, 11),
        disabled=frozenset(range(20, KEY_COUNT + 1)),
    ),
)

PRESET_BY_KEY = {preset.key: preset for preset in PRESETS}


def preset_at(index: int) -> MapPreset:
    return PRESETS[index % len(PRESETS)]


def apply_preset(keymap: dict[int, dict], preset: MapPreset) -> None:
    """Rewrite the MIDI note of every mapped channel in place.

    `keymap` is channel -> {"key", "channel", "midi", "note", ...}. Only
    future presses read this; voices already sounding are left alone.
    """
    for info in keymap.values():
        key_no = int(info["key"])
        midi = preset.midi_for_key(key_no)
        info["midi"] = midi
        info["note"] = midi_name(midi)
        info["disabled"] = not preset.is_enabled(key_no)


# ---------------------------------------------------------------------------
# Structured content mapping (CONTENT_SCHEMA §6.1)
# ---------------------------------------------------------------------------


def _spec_int(value, low: int, high: int, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _spec_steps(value, default: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        return default
    steps: list[int] = []
    for item in value[:12]:
        if isinstance(item, bool):
            return default
        try:
            steps.append(max(-12, min(12, int(item))))
        except (TypeError, ValueError):
            return default
    return tuple(steps) if steps else default


@dataclass(frozen=True)
class MappingSide:
    base: int
    steps: tuple[int, ...] = tuple(range(12))

    @classmethod
    def from_dict(cls, raw, fallback_base: int) -> "MappingSide":
        if not isinstance(raw, dict):
            return cls(fallback_base)
        return cls(
            _spec_int(raw.get("base", fallback_base), 0, 127, fallback_base),
            _spec_steps(raw.get("steps", ()), tuple(range(12))),
        )


@dataclass(frozen=True)
class MappingSplitSpec:
    bar: int
    left: MappingSide
    right: MappingSide


@dataclass(frozen=True)
class MappingSpec:
    """A content-declared mapping (CONTENT_SCHEMA §6.1), tolerant of bad JSON."""

    base: int = 60
    steps: tuple[int, ...] = tuple(range(12))
    octave: int = 0
    transpose: int = 0
    split: MappingSplitSpec | None = None
    label: str = "内容映射"

    @classmethod
    def from_dict(cls, raw) -> "MappingSpec | None":
        if not isinstance(raw, dict):
            return None
        recognized = (
            "base", "steps", "octave", "transpose", "split",
        )
        if not any(name in raw for name in recognized):
            return None
        base = _spec_int(raw.get("base", 60), 0, 127, 60)
        steps = _spec_steps(raw.get("steps", ()), tuple(range(12)))
        split = None
        split_raw = raw.get("split")
        if isinstance(split_raw, dict):
            left = split_raw.get("left")
            right = split_raw.get("right")
            if isinstance(left, dict) and isinstance(right, dict):
                split = MappingSplitSpec(
                    bar=_spec_int(split_raw.get("bar", 16), 1, 32, 16),
                    left=MappingSide.from_dict(left, base),
                    right=MappingSide.from_dict(right, base + 12),
                )
        return cls(
            base=base,
            steps=steps,
            octave=_spec_int(raw.get("octave", 0), -2, 2, 0),
            transpose=_spec_int(raw.get("transpose", 0), -12, 12, 0),
            split=split,
            label=str(raw.get("label") or "内容映射"),
        )

    def to_preset(self) -> MapPreset:
        split = None
        if self.split is not None:
            split = SplitMap(
                bar=self.split.bar,
                left_base=self.split.left.base,
                left_steps=self.split.left.steps,
                right_base=self.split.right.base,
                right_steps=self.split.right.steps,
            )
        return MapPreset(
            key="content",
            label="Content",
            label_cn=self.label,
            note=f"{self.label} · 内容映射",
            base=self.base,
            steps=self.steps,
            split=split,
        )

    def out_of_range_keys(self) -> tuple[int, ...]:
        """Physical keys whose MIDI (with spec offset) falls outside 0..127."""
        preset = self.to_preset()
        offset = 12 * self.octave + self.transpose
        return tuple(
            key
            for key in preset.enabled_keys()
            if not 0 <= preset.midi_for_key(key) + offset <= 127
        )


def mapping_spec(value) -> str | MappingSpec | None:
    """Normalize a content declaration to a preset key or a MappingSpec."""
    if isinstance(value, MappingSpec):
        return value
    if isinstance(value, str):
        return value if value in PRESET_BY_KEY else None
    if isinstance(value, dict):
        preset = value.get("preset")
        custom = any(
            name in value
            for name in ("base", "steps", "octave", "transpose", "split")
        )
        if (
            isinstance(preset, str)
            and preset in PRESET_BY_KEY
            and not custom
        ):
            return preset
        return MappingSpec.from_dict(value)
    return None


def with_split_bar(preset: MapPreset, bar: int) -> MapPreset:
    """Return `preset` with its split boundary moved, clamped to 1..31.

    A boundary needs at least one key on each side. Presets without a split
    are returned unchanged.
    """
    if preset.split is None:
        return preset
    value = max(1, min(KEY_COUNT - 1, int(bar)))
    if value == preset.split.bar:
        return preset
    return replace(preset, split=replace(preset.split, bar=value))


def split_mapping(
    bar: int,
    left_base: int,
    right_base: int,
    left_steps: tuple[int, ...] = tuple(range(12)),
    right_steps: tuple[int, ...] = tuple(range(12)),
    label: str = "左右分区",
    octave: int = 0,
    transpose: int = 0,
) -> MappingSpec:
    """Convenience constructor for split content declarations."""
    return MappingSpec(
        base=left_base,
        steps=tuple(left_steps),
        octave=octave,
        transpose=transpose,
        split=MappingSplitSpec(
            bar=max(1, min(32, int(bar))),
            left=MappingSide(
                max(0, min(127, int(left_base))), tuple(left_steps)
            ),
            right=MappingSide(
                max(0, min(127, int(right_base))), tuple(right_steps)
            ),
        ),
        label=label,
    )
