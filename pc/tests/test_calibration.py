"""Per-key calibration: protocol parsing, session state machine, profile JSON."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.calibration import (
    CalibrationFrame,
    CalibrationProfile,
    CalibrationSession,
    KeyThreshold,
    format_thresholds,
    load_keymap,
    parse_calibration_line,
    parse_threshold_reply,
    parse_thresholds_line,
)


def full_thresholds() -> list[KeyThreshold]:
    return [
        KeyThreshold(
            key=key,
            touch=48,
            release=29,
            noise=2,
            peak=78,
            hold=71,
            channel=key,
            note=f"N{key}",
            module=("0x5A" if key <= 12 else "0x5C" if key <= 24 else "0x5D"),
            electrode=(key - 1) % 12,
        )
        for key in range(1, 33)
    ]


def identity_keymap() -> dict[int, dict]:
    return {
        channel: {
            "key": channel,
            "channel": channel,
            "note": f"N{channel}",
            "midi": 60 + channel,
            "module": 1,
            "address": "0x5A",
            "electrode": channel - 1,
        }
        for channel in range(1, 33)
    }


class CalibrationProtocolTest(unittest.TestCase):
    def test_parse_calibration_line_reads_32_channels_and_timestamp(self) -> None:
        # Firmware streams channels 1..32 in module order; the PC maps each
        # channel back to a layout key. -1 means that module is offline.
        payload = [str(value) for value in range(1, 33)]
        payload[13] = "-1"  # channel 14
        line = "CAL 12345 " + " ".join(payload)

        frame = parse_calibration_line(line, now=7.5)

        self.assertIsNotNone(frame)
        self.assertEqual(frame.dev_ms, 12345)
        self.assertEqual(frame.t, 7.5)
        self.assertEqual(len(frame.values), 32)
        self.assertEqual(frame.values[1], 1)
        self.assertEqual(frame.values[14], -1)
        self.assertEqual(frame.values[32], 32)

    def test_format_thresholds_writes_channel_triples_in_channel_order(self) -> None:
        # The wire format is channel-based because the firmware has no
        # key->channel table; the PC owns the layout mapping.
        values = {2: (41, 24), 1: (48, 29), 32: (60, 36)}

        line = format_thresholds(values)

        self.assertEqual(line, "T 1 48 29 2 41 24 32 60 36")

    def test_threshold_table_round_trips_through_format(self) -> None:
        # Q returns the current table in the same shape T accepts, so a
        # reconnect can verify what the firmware actually holds.
        values = {1: (48, 29), 2: (41, 24), 32: (60, 36)}
        self.assertEqual(parse_thresholds_line(format_thresholds(values)), values)
        self.assertIsNone(parse_thresholds_line("T 1 48"))
        self.assertIsNone(parse_thresholds_line("T 1 48 29 2"))
        self.assertIsNone(parse_thresholds_line("OK T"))

    def test_parse_threshold_reply_reports_ok_or_the_failed_channel(self) -> None:
        self.assertEqual(parse_threshold_reply("OK T"), ("ok", None))
        self.assertEqual(parse_threshold_reply("ERR T 7"), ("error", 7))
        self.assertEqual(parse_threshold_reply("  ERR T 32  "), ("error", 32))
        # Unrelated notices must not be mistaken for a write acknowledgement.
        self.assertIsNone(parse_threshold_reply("OK s"))
        self.assertIsNone(parse_threshold_reply("ERR T"))
        self.assertIsNone(parse_threshold_reply("garbage"))


    def test_shipped_keymap_maps_channels_back_to_layout_keys(self) -> None:
        keymap = load_keymap()
        # Module 1 is wired in reverse: layout key 1 is channel 12 / ELE11.
        self.assertEqual(keymap[12]["key"], 1)
        self.assertEqual(keymap[12]["note"], "F4")
        self.assertEqual(keymap[32]["key"], 32)
        self.assertEqual(keymap[32]["note"], "C7")
        # A session with no explicit map uses the shipped physical layout.
        self.assertEqual(CalibrationSession().keymap[12]["key"], 1)

    def test_parse_calibration_line_ignores_malformed_lines(self) -> None:
        good = " ".join(["1"] * 32)
        lines = [
            f"CAL 1 {good} 2",                       # 33 values
            f"CAL 1 {' '.join(['1'] * 31)}",         # 31 values
            f"CAL 1 {' '.join(['x'] * 32)}",         # not integers
            f"CAL 1 {' '.join(['256'] * 32)}",       # above 255
            f"CAL 1 {' '.join(['-2'] * 32)}",        # below -1
            "CAL 1",                                 # no values
            f"stray CAL 1 {good}",                   # not at line start
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertIsNone(parse_calibration_line(line))


class CalibrationSessionTest(unittest.TestCase):
    def make_session(self) -> CalibrationSession:
        return CalibrationSession(identity_keymap())

    def frame(self, t: float, values: dict[int, int] | None = None) -> CalibrationFrame:
        payload = {channel: 0 for channel in range(1, 33)}
        payload.update(values or {})
        return CalibrationFrame(t=t, values=payload)

    def monitoring_session(
        self,
        noise: int = 0,
        keymap: dict[int, dict] | None = None,
    ) -> CalibrationSession:
        session = CalibrationSession(keymap or identity_keymap())
        session.start(0.0)
        session.feed(
            self.frame(0.0, {channel: noise for channel in range(1, 33)}),
            now=0.0,
        )
        session.feed(self.frame(1.5), now=1.5)
        self.assertEqual(session.state, "monitoring")
        return session

    def test_two_consecutive_frames_create_one_curve_with_preroll(self) -> None:
        session = self.monitoring_session()
        # Idle samples build the 200 ms pre-roll ring buffer.
        for step in range(6):
            now = 2.0 + step * 0.04
            session.feed(self.frame(now, {1: 2}), now=now)

        session.feed(self.frame(2.24, {1: 25}), now=2.24)
        self.assertEqual(session.curves, {})  # one frame is a glitch

        session.feed(self.frame(2.28, {1: 30}), now=2.28)
        curve = session.curves[1]
        self.assertEqual(curve.key, 1)
        self.assertEqual(curve.channel, 1)
        self.assertEqual(curve.note, "N1")
        self.assertEqual(curve.triggered_at, 2.28)
        self.assertEqual(curve.peak, 30)
        # The curve keeps the rise from before the trigger (>= 2.08 s).
        self.assertLessEqual(curve.samples[0].t, 2.08)
        self.assertEqual(curve.samples[-1].t, 2.28)
        self.assertEqual(curve.samples[-1].value, 30)

    def test_simultaneous_presses_keep_independent_curves(self) -> None:
        session = self.monitoring_session()
        for step in range(3):
            now = 2.0 + step * 0.04
            session.feed(self.frame(now, {1: 1, 17: 1}), now=now)

        session.feed(self.frame(2.12, {1: 40, 17: 18}), now=2.12)
        session.feed(self.frame(2.16, {1: 42, 17: 20}), now=2.16)

        self.assertEqual(set(session.curves), {1, 17})
        self.assertEqual(session.curves[1].peak, 42)
        self.assertEqual(session.curves[17].peak, 20)
        self.assertEqual(session.curves[17].channel, 17)

    def test_release_hold_auto_stops_and_freezes_curves(self) -> None:
        session = self.monitoring_session()
        session.feed(self.frame(2.00, {1: 40}), now=2.00)
        session.feed(self.frame(2.04, {1: 42}), now=2.04)
        self.assertIn(1, session.curves)
        self.assertEqual(session.release_line(1), 6)  # max(1, 10 * 0.6)

        session.feed(self.frame(2.10, {1: 5}), now=2.10)
        session.feed(self.frame(2.40, {1: 4}), now=2.40)
        self.assertEqual(session.state, "monitoring")

        session.feed(self.frame(2.61), now=2.61)  # 510 ms below the line
        self.assertEqual(session.state, "stopped")
        self.assertTrue(session.auto_stopped)

        frozen = len(session.curves[1].samples)
        session.feed(self.frame(2.80, {1: 99}), now=2.80)
        self.assertEqual(len(session.curves[1].samples), frozen)

    def test_waiting_without_a_trigger_never_stops(self) -> None:
        session = self.monitoring_session()
        for step in range(40):
            now = 2.0 + step
            session.feed(self.frame(now), now=now)

        self.assertEqual(session.state, "monitoring")
        self.assertEqual(session.curves, {})

    def test_a_held_key_hits_the_30_second_hard_limit(self) -> None:
        session = self.monitoring_session()
        session.feed(self.frame(2.00, {1: 40}), now=2.00)
        session.feed(self.frame(2.04, {1: 40}), now=2.04)

        session.feed(self.frame(32.03, {1: 40}), now=32.03)  # 29.99 s later
        self.assertEqual(session.state, "monitoring")
        self.assertTrue(session.curves[1].stuck)

        session.feed(self.frame(32.05, {1: 40}), now=32.05)  # 30.01 s later
        self.assertEqual(session.state, "stopped")
        self.assertTrue(session.auto_stopped)

    def test_suggested_touch_uses_hold_and_release_follows(self) -> None:
        session = self.monitoring_session(noise=2)
        session.feed(self.frame(2.00, {1: 78}), now=2.00)
        session.feed(self.frame(2.04, {1: 78}), now=2.04)
        for step in range(11):
            now = 2.20 + step * 0.04
            session.feed(self.frame(now, {1: 71}), now=now)
        session.stop(now=2.70)

        curve = session.curves[1]
        self.assertEqual(curve.noise, 2)
        self.assertEqual(curve.peak, 78)
        self.assertEqual(curve.hold, 71)
        # max(2 + 8, round(71 * 0.55), 8) = 39, below peak * 0.85.
        self.assertEqual(session.suggest(1), 39)
        self.assertEqual(session.release_for(39), 23)

    def test_validate_rejects_noise_and_peak_violations(self) -> None:
        session = self.monitoring_session(noise=2)
        session.feed(self.frame(2.00, {1: 78}), now=2.00)
        session.feed(self.frame(2.04, {1: 78}), now=2.04)
        session.feed(self.frame(2.20, {1: 71}), now=2.20)
        session.stop(now=2.70)

        too_low = session.validate(1, 5)
        self.assertFalse(too_low.ok)
        self.assertIn("噪声", too_low.reason)

        too_high = session.validate(1, 71)
        self.assertFalse(too_high.ok)
        self.assertIn("太高", too_high.reason)

        good = session.validate(1, 70)
        self.assertTrue(good.ok)
        self.assertEqual(good.reason, "")
        self.assertEqual(good.warnings, ())

    def test_validate_flags_a_weak_key_but_still_allows_it(self) -> None:
        session = self.monitoring_session(noise=2)
        session.feed(self.frame(2.00, {1: 10}), now=2.00)
        session.feed(self.frame(2.04, {1: 10}), now=2.04)
        session.stop(now=2.20)

        check = session.validate(1, 7)
        self.assertTrue(check.ok)
        self.assertTrue(any("弱" in warning for warning in check.warnings))

    def test_suggestion_never_drops_below_the_noise_margin(self) -> None:
        session = self.monitoring_session(noise=2)
        session.feed(self.frame(2.00, {1: 10}), now=2.00)
        session.feed(self.frame(2.04, {1: 10}), now=2.04)
        session.stop(now=2.20)

        suggested = session.suggest(1)
        # 65% of peak would be 6, below the noise + 5 floor.
        self.assertEqual(suggested, 7)
        self.assertTrue(session.validate(1, suggested).ok)

    def test_apply_values_is_keyed_by_channel_and_accepts_overrides(self) -> None:
        keymap = identity_keymap()
        # Module 1 is wired in reverse: layout key 1 is channel 12.
        keymap[12]["key"] = 1
        keymap[1]["key"] = 12
        session = self.monitoring_session(keymap=keymap)

        session.feed(self.frame(2.00, {12: 78}), now=2.00)
        session.feed(self.frame(2.04, {12: 78}), now=2.04)
        session.stop(now=2.20)

        suggested = session.suggest(1)
        values = session.apply_values()
        self.assertEqual(set(values), {12})
        self.assertEqual(values[12], (suggested, session.release_for(suggested)))

        overridden = session.apply_values({1: 48})
        self.assertEqual(overridden[12], (48, session.release_for(48)))

    def test_profile_merges_measured_keys_over_a_previous_profile(self) -> None:
        session = self.monitoring_session(noise=2)
        session.feed(self.frame(2.00, {1: 78}), now=2.00)
        session.feed(self.frame(2.04, {1: 78}), now=2.04)
        session.feed(self.frame(2.20, {1: 71}), now=2.20)
        session.stop(now=2.70)

        previous = CalibrationProfile(
            name="旧方案", gain=4, keys=full_thresholds()
        )
        merged = session.profile("新方案", gain=4, base=previous)

        self.assertTrue(merged.is_complete())
        self.assertEqual(merged.name, "新方案")
        self.assertTrue(merged.created_at)
        key1 = next(item for item in merged.keys if item.key == 1)
        self.assertEqual(key1.touch, session.suggest(1))
        self.assertEqual(key1.release, session.release_for(key1.touch))
        self.assertEqual(key1.peak, 78)
        self.assertEqual(key1.note, "N1")
        key2 = next(item for item in merged.keys if item.key == 2)
        self.assertEqual(key2.touch, 48)  # untouched, kept from the old plan

    def test_press_during_baseline_restarts_the_noise_window(self) -> None:
        session = self.make_session()
        session.start(0.0)

        session.feed(self.frame(0.4, {1: 3}), now=0.4)
        session.feed(self.frame(0.8, {1: 30}), now=0.8)  # clear press
        self.assertEqual(session.state, "baseline")

        session.feed(self.frame(1.6, {1: 2}), now=1.6)  # old end, too early
        self.assertEqual(session.state, "baseline")

        session.feed(self.frame(2.3, {1: 2}), now=2.3)  # 1.5 s after restart
        self.assertEqual(session.state, "monitoring")
        self.assertEqual(session.noise_max[1], 2)  # the press never counted

    def test_stuck_key_prevents_release_based_auto_stop(self) -> None:
        session = self.monitoring_session()
        session.feed(self.frame(2.00, {1: 40}), now=2.00)
        session.feed(self.frame(2.04, {1: 40}), now=2.04)
        session.feed(self.frame(8.00, {1: 40}), now=8.00)
        self.assertTrue(session.curves[1].stuck)

        session.feed(self.frame(8.20, {1: 0}), now=8.20)
        session.feed(self.frame(8.80, {1: 0}), now=8.80)
        self.assertEqual(session.state, "monitoring")

        session.stop(now=8.80)
        self.assertFalse(session.auto_stopped)

    def test_offline_channels_never_open_a_curve(self) -> None:
        session = self.monitoring_session()
        for step in range(3):
            now = 2.0 + step * 0.04
            session.feed(self.frame(now, {1: -1}), now=now)

        self.assertEqual(session.curves, {})

    def test_validate_rejects_out_of_range_and_uncaptured_keys(self) -> None:
        session = self.monitoring_session()
        session.feed(self.frame(2.00, {1: 40}), now=2.00)
        session.feed(self.frame(2.04, {1: 40}), now=2.04)
        session.stop(now=2.20)

        self.assertFalse(session.validate(1, 0).ok)
        self.assertFalse(session.validate(1, 256).ok)
        self.assertFalse(session.validate(2, 48).ok)

    def test_noise_baseline_records_peaks_and_opens_monitoring(self) -> None:
        session = self.make_session()
        session.start(0.0)
        self.assertEqual(session.state, "baseline")

        session.feed(self.frame(0.0, {1: 3, 2: 1}), now=0.0)
        session.feed(self.frame(0.5, {1: 2, 2: 4}), now=0.5)
        session.feed(self.frame(1.6, {1: 1, 2: 0}), now=1.6)

        self.assertEqual(session.state, "monitoring")
        self.assertEqual(session.noise_max[1], 3)
        self.assertEqual(session.noise_max[2], 4)
        self.assertEqual(session.trigger_line(1), 11)  # max(3 + 8, 10)
        self.assertEqual(session.trigger_line(2), 12)  # max(4 + 8, 10)
        self.assertEqual(session.trigger_line(3), 10)  # floor


class CalibrationProfileTest(unittest.TestCase):
    def full_keys(self) -> list[KeyThreshold]:
        return full_thresholds()

    def test_profile_round_trips_through_json(self) -> None:
        profile = CalibrationProfile(
            name="裸铜 · 桌面 A",
            gain=4,
            keys=self.full_keys(),
            created_at="2026-11-12T20:15:00",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            profile.save(path)
            loaded, warning = CalibrationProfile.load(path)

        self.assertEqual(warning, "")
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.is_complete())
        self.assertEqual(loaded.to_dict(), profile.to_dict())

    def test_incomplete_or_corrupt_profiles_are_not_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            partial = root / "partial.json"
            CalibrationProfile(
                name="partial",
                gain=4,
                keys=self.full_keys()[:31],
            ).save(partial)
            loaded, warning = CalibrationProfile.load(partial)
            self.assertIsNone(loaded)
            self.assertIn("不完整", warning)

            broken = root / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            loaded, warning = CalibrationProfile.load(broken)
            self.assertIsNone(loaded)
            self.assertIn("损坏", warning)

            missing, warning = CalibrationProfile.load(root / "missing.json")
            self.assertIsNone(missing)
            self.assertEqual(warning, "")

            wrong_version = root / "wrong.json"
            wrong_version.write_text(
                '{"version": 99, "keys": []}', encoding="utf-8"
            )
            loaded, warning = CalibrationProfile.load(wrong_version)
            self.assertIsNone(loaded)
            self.assertIn("版本", warning)


if __name__ == "__main__":
    unittest.main()
