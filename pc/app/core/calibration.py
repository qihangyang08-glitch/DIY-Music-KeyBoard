"""Per-key threshold calibration (A2, slice 1).

Pure logic: CAL stream parsing, the CalibrationSession state machine, and the
calibration.json profile. No Qt, no serial port, no UI.

Signal convention: the firmware streams ``clamp(baseline - filtered, 0, 255)``
per channel. The MPR121's filtered reading *drops* when an electrode is
touched (the measured copper-foil swing is about -55 counts), so the positive
magnitude is what thresholds are compared against. A value of -1 means that
channel's module is offline.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Optional

CHANNEL_COUNT = 32
KEY_COUNT = 32
SIGNAL_MIN = -1
SIGNAL_MAX = 255

BASELINE_SECONDS = 1.5
BASELINE_TOUCH = 20        # a clear press restarts noise collection
TRIGGER_MARGIN = 8
TRIGGER_FLOOR = 10
TRIGGER_FRAMES = 2
PREROLL_SECONDS = 0.2
RELEASE_HOLD_SECONDS = 0.5
SESSION_MAX_SECONDS = 30.0
STUCK_SECONDS = 5.0
NOISE_WARN = 15
WEAK_PEAK = 12

STATE_IDLE = "idle"
STATE_BASELINE = "baseline"
STATE_MONITORING = "monitoring"
STATE_STOPPED = "stopped"

PROFILE_VERSION = 1

ROOT = Path(__file__).resolve().parents[3]
KEYMAP_PATH = ROOT / "mapping" / "keymap.json"


def default_path() -> Path:
    """User calibration file, next to learning.json in the app config dir."""
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "calibration.json"


def load_keymap(path: str | Path | None = None) -> dict[int, dict]:
    """Channel -> physical key info, read fresh from the shipped layout.

    The instrument's in-memory keymap is rewritten by mapping presets, so
    calibration must not borrow it: a key's physical note does not change
    when the user picks another preset.
    """
    target = Path(path) if path is not None else KEYMAP_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    return {int(item["channel"]): dict(item) for item in data["keys"]}


CAL_RE = re.compile(r"^\s*CAL\s+(\d+)\s+(.*?)\s*$")


@dataclass(frozen=True)
class CalibrationSample:
    t: float
    value: int


@dataclass(frozen=True)
class CalibrationFrame:
    """One ``CAL`` line: channel 1..32 -> signal, -1 when that module is out."""

    t: float
    values: dict[int, int]
    dev_ms: Optional[int] = None
    raw: str = ""


def parse_calibration_line(
    text: str, now: Optional[float] = None
) -> Optional[CalibrationFrame]:
    """Parse ``CAL <millis> <v1> ... <v32>``; anything malformed is ignored."""
    match = CAL_RE.match(text)
    if match is None:
        return None
    tokens = match.group(2).split()
    if len(tokens) != CHANNEL_COUNT:
        return None
    values: dict[int, int] = {}
    for channel, token in enumerate(tokens, start=1):
        try:
            value = int(token)
        except ValueError:
            return None
        if not SIGNAL_MIN <= value <= SIGNAL_MAX:
            return None
        values[channel] = value
    return CalibrationFrame(
        t=time.monotonic() if now is None else float(now),
        values=values,
        dev_ms=int(match.group(1)),
        raw=text,
    )


def format_thresholds(values: dict[int, tuple[int, int]]) -> str:
    """Build ``T <channel> <touch> <release> ...`` in channel order."""
    parts = ["T"]
    for channel in sorted(values):
        touch, release = values[channel]
        parts.extend((str(channel), str(int(touch)), str(int(release))))
    return " ".join(parts)


def parse_thresholds_line(
    text: str,
) -> Optional[dict[int, tuple[int, int]]]:
    """Parse a ``T ...`` table (the reply to ``Q``) back into channel values."""
    tokens = text.split()
    if not tokens or tokens[0] != "T":
        return None
    body = tokens[1:]
    if not body or len(body) % 3 != 0:
        return None
    values: dict[int, tuple[int, int]] = {}
    for index in range(0, len(body), 3):
        try:
            channel = int(body[index])
            touch = int(body[index + 1])
            release = int(body[index + 2])
        except ValueError:
            return None
        if (
            not 1 <= channel <= CHANNEL_COUNT
            or not 1 <= touch <= SIGNAL_MAX
            or not 0 <= release <= SIGNAL_MAX - 1
            or release >= touch
            or channel in values
        ):
            return None
        values[channel] = (touch, release)
    return values


def parse_threshold_reply(text: str) -> Optional[tuple[str, Optional[int]]]:
    """Parse ``OK T`` / ``ERR T <channel>``; other notices return None."""
    tokens = text.split()
    if not tokens or tokens[1:2] != ["T"]:
        return None
    if tokens[0] == "OK" and len(tokens) == 2:
        return ("ok", None)
    if tokens[0] == "ERR" and len(tokens) == 3:
        try:
            return ("error", int(tokens[2]))
        except ValueError:
            return None
    return None


@dataclass
class KeyCurve:
    """One key's captured press: samples, noise floor and derived levels."""

    key: int
    channel: int
    note: str
    samples: list[CalibrationSample] = field(default_factory=list)
    noise: int = 0
    peak: int = 0
    hold: int = 0
    triggered_at: float = 0.0
    stuck: bool = False


@dataclass(frozen=True)
class ThresholdCheck:
    """Result of checking one key's touch threshold before applying it."""

    ok: bool
    reason: str = ""
    warnings: tuple[str, ...] = ()


@dataclass
class KeyThreshold:
    """One key's applied thresholds and the measurements they came from."""

    key: int
    touch: int
    release: int
    noise: int = 0
    peak: int = 0
    hold: int = 0
    channel: int = 0
    note: str = ""
    module: str = ""
    electrode: int = -1

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "channel": self.channel,
            "note": self.note,
            "module": self.module,
            "electrode": self.electrode,
            "noise": self.noise,
            "peak": self.peak,
            "hold": self.hold,
            "touch": self.touch,
            "release": self.release,
        }


def _int_in(value, low: int, high: int, default: Optional[int] = None):
    """Only real JSON integers inside the range count; anything else is default."""
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if low <= value <= high:
        return value
    return default


@dataclass
class CalibrationProfile:
    """One saved calibration: all 32 keys must be present to be applied."""

    name: str = ""
    gain: int = 0
    keys: list[KeyThreshold] = field(default_factory=list)
    created_at: str = ""
    version: int = PROFILE_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "name": self.name,
            "created_at": self.created_at,
            "gain": self.gain,
            "keys": [
                item.to_dict() for item in sorted(self.keys, key=lambda k: k.key)
            ],
        }

    def is_complete(self) -> bool:
        """True only when keys 1..32 are all present on 32 distinct channels."""
        present = {item.key for item in self.keys}
        channels = {item.channel for item in self.keys}
        return (
            len(self.keys) == CHANNEL_COUNT
            and present == set(range(1, CHANNEL_COUNT + 1))
            and channels == set(range(1, CHANNEL_COUNT + 1))
        )

    def values_by_channel(self) -> dict[int, tuple[int, int]]:
        return {item.channel: (item.touch, item.release) for item in self.keys}

    @classmethod
    def from_dict(cls, raw) -> Optional["CalibrationProfile"]:
        if not isinstance(raw, dict) or raw.get("version") != PROFILE_VERSION:
            return None
        keys_raw = raw.get("keys")
        if not isinstance(keys_raw, list):
            return None
        name = raw.get("name") if isinstance(raw.get("name"), str) else ""
        created_at = (
            raw.get("created_at")
            if isinstance(raw.get("created_at"), str)
            else ""
        )
        gain = _int_in(raw.get("gain", 0), 0, 8, 0)
        if gain is None:
            return None
        keys: list[KeyThreshold] = []
        for item in keys_raw:
            if not isinstance(item, dict):
                return None
            key = _int_in(item.get("key"), 1, KEY_COUNT)
            channel = _int_in(item.get("channel"), 1, CHANNEL_COUNT)
            touch = _int_in(item.get("touch"), 1, SIGNAL_MAX)
            release = _int_in(item.get("release"), 0, SIGNAL_MAX - 1)
            if None in (key, channel, touch, release) or release >= touch:
                return None
            noise = _int_in(item.get("noise", 0), 0, SIGNAL_MAX, 0)
            peak = _int_in(item.get("peak", 0), 0, SIGNAL_MAX, 0)
            hold = _int_in(item.get("hold", 0), 0, SIGNAL_MAX, 0)
            electrode = _int_in(item.get("electrode", -1), -1, 11, -1)
            if None in (noise, peak, hold, electrode):
                return None
            note = item.get("note") if isinstance(item.get("note"), str) else ""
            module = (
                item.get("module") if isinstance(item.get("module"), str) else ""
            )
            keys.append(
                KeyThreshold(
                    key=key,
                    touch=touch,
                    release=release,
                    noise=noise,
                    peak=peak,
                    hold=hold,
                    channel=channel,
                    note=note,
                    module=module,
                    electrode=electrode,
                )
            )
        return cls(
            name=name,
            gain=gain,
            keys=keys,
            created_at=created_at,
            version=PROFILE_VERSION,
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".tmp-{uuid.uuid4().hex}-{target.name}")
        try:
            temp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp, target)
        finally:
            try:
                temp.unlink()
            except OSError:
                pass

    @classmethod
    def load(
        cls, path: str | Path
    ) -> tuple[Optional["CalibrationProfile"], str]:
        """Load a profile; (None, warning) when it must not be applied."""
        target = Path(path)
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return (None, "")
        except (OSError, ValueError, RecursionError):
            return (None, "校准方案文件损坏，已忽略")
        if not isinstance(raw, dict):
            return (None, "校准方案文件损坏，已忽略")
        if raw.get("version") != PROFILE_VERSION:
            return (None, "校准方案版本不兼容，已忽略")
        profile = cls.from_dict(raw)
        if profile is None:
            return (None, "校准方案含无效阈值，未应用")
        if not profile.is_complete():
            return (None, "校准方案不完整（缺少键），未应用")
        return (profile, "")


class CalibrationSession:
    """Baseline -> monitoring -> stopped, driven by 25 Hz CAL frames.

    The user is never asked to press a particular key: any key that crosses
    its trigger line twice in a row gets its own curve. The session stops by
    itself once every captured key has stayed below its release line for
    RELEASE_HOLD_SECONDS, or after SESSION_MAX_SECONDS from the first trigger.
    A key that stays high for STUCK_SECONDS is flagged and disables auto-stop
    so a stuck electrode cannot masquerade as a finished run.
    """

    def __init__(self, keymap: Optional[dict[int, dict]] = None) -> None:
        self.keymap = keymap if keymap is not None else load_keymap()
        self._channel_to_key = {
            int(channel): int(info["key"])
            for channel, info in self.keymap.items()
        }
        self.state = STATE_IDLE
        self.auto_stopped = False
        self.noise_max: dict[int, int] = {}
        self.curves: dict[int, KeyCurve] = {}
        self._noise_values: dict[int, list[int]] = {}
        self._baseline_started = 0.0
        self._first_trigger_at: float | None = None
        self._buffers: dict[int, Deque[CalibrationSample]] = {}
        self._above_count: dict[int, int] = {}
        self._below_since: dict[int, float] = {}
        self._above_since: dict[int, float] = {}

    # -- lifecycle --------------------------------------------------------

    def start(self, now: float) -> None:
        """Begin the noise-baseline collection (about 1.5 s of hands-off)."""
        self.state = STATE_BASELINE
        self.auto_stopped = False
        self.noise_max = {}
        self.curves = {}
        self._noise_values = {}
        self._baseline_started = float(now)
        self._first_trigger_at = None
        self._buffers = {}
        self._above_count = {}
        self._below_since = {}
        self._above_since = {}

    def stop(self, now: float | None = None) -> None:
        """Freeze the captured curves; the caller may raise auto_stopped."""
        if self.state in (STATE_IDLE, STATE_STOPPED):
            return
        self.state = STATE_STOPPED
        self._finalize_curves()

    # -- input ------------------------------------------------------------

    def feed(self, frame: CalibrationFrame, now: Optional[float] = None) -> None:
        """Consume one CAL frame. `now` lets tests drive time deterministically."""
        moment = frame.t if now is None else float(now)
        if self.state == STATE_BASELINE:
            self._feed_baseline(frame, moment)
        elif self.state == STATE_MONITORING:
            self._feed_monitoring(frame, moment)

    def _feed_baseline(self, frame: CalibrationFrame, now: float) -> None:
        for channel, value in frame.values.items():
            if channel not in self._channel_to_key or value < 0:
                continue
            if value > BASELINE_TOUCH:
                # A press during the hands-off capture must not be folded
                # into the noise floor; restart the window instead.
                self.start(now)
                return
            self._noise_values.setdefault(channel, []).append(value)
        if now - self._baseline_started >= BASELINE_SECONDS - 1e-9:
            self._finish_baseline(now)

    def _finish_baseline(self, now: float) -> None:
        self.noise_max = {
            channel: max(values) if values else 0
            for channel, values in self._noise_values.items()
        }
        for channel in self._channel_to_key:
            self.noise_max.setdefault(channel, 0)
        self.state = STATE_MONITORING

    def trigger_line(self, channel: int) -> int:
        """Signal level that starts a curve for `channel` (noise + margin)."""
        return max(self.noise_max.get(channel, 0) + TRIGGER_MARGIN, TRIGGER_FLOOR)

    def release_line(self, channel: int) -> int:
        """Level a captured key must fall below before auto-stop can trigger."""
        return max(1, round(self.trigger_line(channel) * 0.60))

    def _feed_monitoring(self, frame: CalibrationFrame, now: float) -> None:
        cutoff = now - PREROLL_SECONDS
        for channel, value in frame.values.items():
            if channel not in self._channel_to_key or value < 0:
                continue
            sample = CalibrationSample(now, value)
            buffer = self._buffers.setdefault(channel, deque())
            buffer.append(sample)
            while buffer and buffer[0].t < cutoff:
                buffer.popleft()

            key = self._channel_to_key[channel]
            curve = self.curves.get(key)
            if curve is not None:
                curve.samples.append(sample)
                curve.peak = max(curve.peak, value)
                if value < self.release_line(channel):
                    self._below_since.setdefault(key, now)
                    self._above_since.pop(key, None)
                else:
                    self._below_since.pop(key, None)
                    since = self._above_since.setdefault(key, now)
                    if now - since >= STUCK_SECONDS:
                        curve.stuck = True
                continue

            if value >= self.trigger_line(channel):
                count = self._above_count.get(channel, 0) + 1
                self._above_count[channel] = count
                if count >= TRIGGER_FRAMES:
                    self._open_curve(channel, now, list(buffer))
            else:
                self._above_count[channel] = 0

        if (
            self.curves
            and not any(curve.stuck for curve in self.curves.values())
            and len(self._below_since) == len(self.curves)
        ):
            released_at = min(self._below_since.values())
            if now - released_at >= RELEASE_HOLD_SECONDS:
                self.auto_stopped = True
                self.state = STATE_STOPPED
                self._finalize_curves()
                return

        if (
            self._first_trigger_at is not None
            and now - self._first_trigger_at >= SESSION_MAX_SECONDS
        ):
            self.auto_stopped = True
            self.state = STATE_STOPPED
            self._finalize_curves()

    def suggest(self, key: int) -> int:
        """Starting touch threshold for a captured key (0 if not captured).

        ``max(noise + 8, 55% of the hold, 8)`` leaves a 15% margin under the
        peak; a key whose hold is close to its peak falls back to 65% of peak.
        """
        curve = self.curves.get(key)
        if curve is None:
            return 0
        value = max(
            curve.noise + TRIGGER_MARGIN,
            round(curve.hold * 0.55),
            8,
        )
        if value > curve.peak * 0.85:
            value = round(curve.peak * 0.65)
        # The peak fallback can land under the noise floor for a weak key;
        # a suggestion the user cannot apply is worse than no suggestion.
        value = max(value, curve.noise + 5)
        return max(1, min(SIGNAL_MAX, int(value)))

    @staticmethod
    def release_for(touch: int) -> int:
        """Release threshold: 60% of touch, always strictly below it."""
        touch = max(0, min(SIGNAL_MAX, int(touch)))
        if touch <= 1:
            return 0
        return max(1, min(touch - 1, round(touch * 0.60)))

    def validate(self, key: int, touch: int) -> ThresholdCheck:
        """Check a user-chosen touch value against the captured curve.

        Rejected values would either fire on noise or miss a normal press.
        Weak / noisy / saturated keys are allowed but carry a warning.
        """
        curve = self.curves.get(key)
        if curve is None:
            return ThresholdCheck(False, "该键尚未采集")
        touch = int(touch)
        if not 1 <= touch <= SIGNAL_MAX:
            return ThresholdCheck(
                False, f"阈值必须在 1–{SIGNAL_MAX}（当前 {touch}）"
            )
        minimum = curve.noise + 5
        if touch < minimum:
            return ThresholdCheck(
                False,
                f"阈值 {touch} 离噪声 {curve.noise} 太近，会误触（至少 {minimum}）",
            )
        if curve.peak < SIGNAL_MAX and touch > curve.peak * 0.90:
            maximum = int(curve.peak * 0.90)
            return ThresholdCheck(
                False,
                f"阈值 {touch} 太高，正常按下可能识别不到"
                f"（峰值 {curve.peak} 的 90% 是 {maximum}）",
            )
        warnings: list[str] = []
        if curve.peak < WEAK_PEAK:
            warnings.append(
                f"弱键：峰值 {curve.peak} 低于 {WEAK_PEAK}，建议提高增益或检查电极"
            )
        if curve.peak >= SIGNAL_MAX:
            warnings.append("饱和：峰值已到 255，建议降低增益")
        if curve.noise > NOISE_WARN:
            warnings.append(
                f"噪声偏高：{curve.noise} 超过 {NOISE_WARN}，建议检查接地/覆膜"
            )
        return ThresholdCheck(True, "", tuple(warnings))

    def apply_values(
        self, touch_overrides: Optional[dict[int, int]] = None
    ) -> dict[int, tuple[int, int]]:
        """Channel -> (touch, release) for every captured key."""
        overrides = touch_overrides or {}
        values: dict[int, tuple[int, int]] = {}
        for key, curve in self.curves.items():
            touch = int(overrides.get(key, self.suggest(key)))
            touch = max(1, min(SIGNAL_MAX, touch))
            values[curve.channel] = (touch, self.release_for(touch))
        return values

    def profile(
        self,
        name: str = "",
        gain: int = 0,
        touch_overrides: Optional[dict[int, int]] = None,
        base: Optional[CalibrationProfile] = None,
    ) -> CalibrationProfile:
        """Build a profile from the captured keys, optionally filling the rest.

        Keys not pressed in this run are copied from `base` (the currently
        applied plan), so a partial re-calibration can still produce a
        complete 32-key profile. Without a base the result may be incomplete.
        """
        values = self.apply_values(touch_overrides)
        items: list[KeyThreshold] = []
        captured: set[int] = set()
        for key, curve in sorted(self.curves.items()):
            touch, release = values[curve.channel]
            info = self.keymap.get(curve.channel, {})
            items.append(
                KeyThreshold(
                    key=key,
                    touch=touch,
                    release=release,
                    noise=curve.noise,
                    peak=curve.peak,
                    hold=curve.hold,
                    channel=curve.channel,
                    note=curve.note,
                    module=str(info.get("address", "")),
                    electrode=int(info.get("electrode", -1)),
                )
            )
            captured.add(key)
        if base is not None:
            for item in base.keys:
                if item.key not in captured:
                    items.append(item)
        items.sort(key=lambda item: item.key)
        return CalibrationProfile(
            name=name,
            gain=int(gain),
            keys=items,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _finalize_curves(self) -> None:
        for curve in self.curves.values():
            stable = [
                sample.value
                for sample in curve.samples
                if curve.triggered_at + 0.15
                <= sample.t
                <= curve.triggered_at + 0.60
            ]
            if not stable:
                stable = [
                    sample.value
                    for sample in curve.samples
                    if sample.t >= curve.triggered_at
                ]
            curve.hold = (
                int(round(statistics.median(stable)))
                if stable
                else curve.peak
            )

    def _open_curve(
        self, channel: int, now: float, samples: list[CalibrationSample]
    ) -> None:
        key = self._channel_to_key[channel]
        info = self.keymap.get(channel, {})
        curve = KeyCurve(
            key=key,
            channel=channel,
            note=str(info.get("note", "")),
            samples=list(samples),
            noise=self.noise_max.get(channel, 0),
            peak=max((sample.value for sample in samples), default=0),
            triggered_at=now,
        )
        self.curves[key] = curve
        self._above_since[key] = now
        if self._first_trigger_at is None:
            self._first_trigger_at = now
