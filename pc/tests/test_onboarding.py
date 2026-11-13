"""First-run onboarding state: tolerant load, atomic save, done flag."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.onboarding import OnboardingState


class OnboardingStateTest(unittest.TestCase):
    def test_missing_or_corrupt_file_is_not_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = OnboardingState.load(root / "missing.json")
            broken = root / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            corrupt = OnboardingState.load(broken)

        self.assertFalse(missing.done)
        self.assertFalse(corrupt.done)

    def test_completed_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "onboarding.json"
            state = OnboardingState(path=path)
            state.mark_completed()
            state.save()
            loaded = OnboardingState.load(path)

        self.assertTrue(loaded.done)
        self.assertTrue(loaded.completed)
        self.assertFalse(loaded.skipped)
        self.assertTrue(loaded.seen_at)

    def test_skipped_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "onboarding.json"
            state = OnboardingState(path=path)
            state.mark_skipped()
            state.save()
            loaded = OnboardingState.load(path)

        self.assertTrue(loaded.done)
        self.assertTrue(loaded.skipped)
        self.assertFalse(loaded.completed)

    def test_wrong_version_or_non_boolean_values_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong = root / "wrong.json"
            wrong.write_text(
                json.dumps({"version": 99, "completed": True}),
                encoding="utf-8",
            )
            typed = root / "typed.json"
            typed.write_text(
                json.dumps(
                    {"version": 1, "completed": "yes", "skipped": 1}
                ),
                encoding="utf-8",
            )
            wrong_state = OnboardingState.load(wrong)
            typed_state = OnboardingState.load(typed)

        self.assertFalse(wrong_state.done)
        self.assertFalse(typed_state.done)

    def test_save_leaves_no_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "onboarding.json"
            state = OnboardingState(path=path)
            state.mark_completed()
            state.save()
            names = sorted(item.name for item in root.iterdir())

        self.assertEqual(names, ["onboarding.json"])


if __name__ == "__main__":
    unittest.main()
