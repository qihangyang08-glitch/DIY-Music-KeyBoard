"""Local learning progress — where the user last was and how practice went.

The file is created only after the user actually opens a stage/course or starts
a practice. If they never touch 学习, no file appears and no other feature sees
this module.

Practice results are keyed by stage + item name. A later run only replaces the
stored result when it is better: completing the piece wins, then more hits,
then fewer misses, then more first-try answers, then a longer streak, then a
faster first response. That way a quick abandoned run cannot erase a completed
one.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .exam import ExamResult


def default_path() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "learning.json"


def item_key(stage: int, item_name: str) -> str:
    return f"{stage}:{item_name}"


def _strict_bool(value, default: bool = False) -> bool:
    """Only real JSON booleans count; a string like "false" is not true."""
    return value if isinstance(value, bool) else default


@dataclass(frozen=True)
class PracticeResult:
    hits: int = 0
    misses: int = 0
    total: int = 0
    completed: bool = False
    updated_at: float = 0.0
    avg_ms: int = 0
    best_streak: int = 0
    first_try: int = 0

    @property
    def accuracy(self) -> int:
        attempts = self.hits + self.misses
        return round(100 * self.hits / attempts) if attempts else 0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": self.total,
            "completed": self.completed,
            "updated_at": self.updated_at,
            "avg_ms": self.avg_ms,
            "best_streak": self.best_streak,
            "first_try": self.first_try,
        }

    @classmethod
    def from_dict(cls, raw) -> "PracticeResult | None":
        if not isinstance(raw, dict):
            return None
        try:
            return cls(
                hits=max(0, int(raw.get("hits", 0))),
                misses=max(0, int(raw.get("misses", 0))),
                total=max(0, int(raw.get("total", 0))),
                completed=bool(raw.get("completed", False)),
                updated_at=float(raw.get("updated_at", 0.0)),
                avg_ms=max(0, int(raw.get("avg_ms", 0))),
                best_streak=max(0, int(raw.get("best_streak", 0))),
                first_try=max(0, int(raw.get("first_try", 0))),
            )
        except (TypeError, ValueError, OverflowError):
            return None


@dataclass(frozen=True)
class ExamRecord:
    """Best optional-exam attempt, plus how many times it was attempted.

    Exams are keyed by exam id, not by a stage item: a passed exam stays passed
    even if the learner later practices the same notes again.
    """

    key: str
    stage_index: int
    kind: str
    passed: bool
    total: int
    hits: int = 0
    misses: int = 0
    extras: int = 0
    first_try: int = 0
    avg_ms: int = 0
    finished: bool = True
    attempts: int = 1
    updated_at: float = 0.0

    @property
    def summary(self) -> str:
        if self.kind == "rhythm":
            avg = f"{self.avg_ms} ms" if self.avg_ms else "—"
            return f"踩准 {self.hits}/{self.total} · 平均偏差 {avg}"
        return f"首答 {self.first_try}/{self.total}"

    @property
    def status_text(self) -> str:
        head = "已通过" if self.passed and self.finished else "未通过"
        return f"{head} · {self.summary} · 共 {self.attempts} 次"

    def to_dict(self) -> dict:
        return {
            "stage_index": self.stage_index,
            "kind": self.kind,
            "passed": self.passed,
            "total": self.total,
            "hits": self.hits,
            "misses": self.misses,
            "extras": self.extras,
            "first_try": self.first_try,
            "avg_ms": self.avg_ms,
            "finished": self.finished,
            "attempts": self.attempts,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, key: str, raw) -> "ExamRecord | None":
        if not isinstance(raw, dict):
            return None
        kind = raw.get("kind")
        if kind not in ("notes", "rhythm"):
            return None
        try:
            total = int(raw.get("total", 0))
            stage_index = int(raw.get("stage_index", -1))
            attempts = int(raw.get("attempts", 1))
            if total <= 0 or stage_index < 0:
                return None
            return cls(
                key=key,
                stage_index=stage_index,
                kind=kind,
                passed=_strict_bool(raw.get("passed"), False),
                total=total,
                hits=max(0, int(raw.get("hits", 0))),
                misses=max(0, int(raw.get("misses", 0))),
                extras=max(0, int(raw.get("extras", 0))),
                first_try=max(0, int(raw.get("first_try", 0))),
                avg_ms=max(0, int(raw.get("avg_ms", 0))),
                finished=_strict_bool(raw.get("finished"), True),
                attempts=max(1, attempts),
                updated_at=float(raw.get("updated_at", 0.0)),
            )
        except (TypeError, ValueError, OverflowError):
            return None


def _exam_better(candidate: ExamRecord, old: ExamRecord) -> bool:
    if candidate.passed != old.passed:
        return candidate.passed
    if candidate.kind == "rhythm":
        # A nearly-empty run can have a tiny average error from one lucky hit;
        # more hit beats must win before the timing average is compared.
        if candidate.hits != old.hits:
            return candidate.hits > old.hits
        candidate_avg = candidate.avg_ms if candidate.avg_ms > 0 else 10**9
        old_avg = old.avg_ms if old.avg_ms > 0 else 10**9
        if candidate_avg != old_avg:
            return candidate_avg < old_avg
    elif candidate.first_try != old.first_try:
        return candidate.first_try > old.first_try
    if candidate.misses != old.misses:
        return candidate.misses < old.misses
    if candidate.extras != old.extras:
        return candidate.extras < old.extras
    if candidate.hits != old.hits:
        return candidate.hits > old.hits
    return False


def _better(candidate: PracticeResult, old: PracticeResult) -> bool:
    if candidate.completed != old.completed:
        return candidate.completed
    if candidate.hits != old.hits:
        return candidate.hits > old.hits
    if candidate.misses != old.misses:
        return candidate.misses < old.misses
    if candidate.first_try != old.first_try:
        return candidate.first_try > old.first_try
    if candidate.best_streak != old.best_streak:
        return candidate.best_streak > old.best_streak
    if candidate.avg_ms > 0 and old.avg_ms > 0:
        return candidate.avg_ms < old.avg_ms
    return False


@dataclass
class LearningProgress:
    path: Path = field(default_factory=default_path)
    last_stage: int | None = None
    last_item: str = ""
    last_view: str = "stage"  # stage | course
    last_guide: str = ""
    updated_at: float = 0.0
    results: dict[str, PracticeResult] = field(default_factory=dict)
    exams: dict[str, ExamRecord] = field(default_factory=dict)
    # Guide step checklists, keyed by "stage:lesson-id" (or lesson title).
    guide_steps: dict[str, tuple[int, ...]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "LearningProgress":
        progress = cls(path=Path(path) if path else default_path())
        try:
            raw = json.loads(progress.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return progress
        if not isinstance(raw, dict):
            return progress
        stage = raw.get("last_stage")
        progress.last_stage = stage if isinstance(stage, int) else None
        progress.last_item = str(raw.get("last_item", ""))
        view = raw.get("last_view", "stage")
        progress.last_view = view if view in ("stage", "course") else "stage"
        progress.last_guide = str(raw.get("last_guide", ""))
        updated = raw.get("updated_at", 0)
        progress.updated_at = float(updated) if isinstance(updated, (int, float)) else 0.0
        results = raw.get("results", {})
        if isinstance(results, dict):
            for key, value in results.items():
                parsed = PracticeResult.from_dict(value)
                if parsed is not None and isinstance(key, str):
                    progress.results[key] = parsed
        exams = raw.get("exams", {})
        if isinstance(exams, dict):
            for key, value in exams.items():
                if not isinstance(key, str):
                    continue
                parsed_exam = ExamRecord.from_dict(key, value)
                if parsed_exam is not None:
                    progress.exams[key] = parsed_exam
        steps = raw.get("guide_steps", {})
        if isinstance(steps, dict):
            for key, value in steps.items():
                if not isinstance(key, str) or not isinstance(value, (list, tuple)):
                    continue
                cleaned = sorted(
                    {
                        int(item)
                        for item in value
                        if isinstance(item, int)
                        and not isinstance(item, bool)
                        and item >= 0
                    }
                )
                if cleaned:
                    progress.guide_steps[key] = tuple(cleaned)
        return progress

    def to_dict(self) -> dict:
        return {
            "version": 6,
            "last_stage": self.last_stage,
            "last_item": self.last_item,
            "last_view": self.last_view,
            "last_guide": self.last_guide,
            "updated_at": self.updated_at,
            "results": {key: value.to_dict() for key, value in self.results.items()},
            "exams": {key: value.to_dict() for key, value in self.exams.items()},
            "guide_steps": {
                key: list(value) for key, value in self.guide_steps.items()
            },
        }

    def save(self) -> None:
        # Write a sibling temp file and replace the target, so a failed write
        # can never truncate a good archive into invalid JSON. Disk errors are
        # still swallowed: losing the newest result must not take down the UI.
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

    def touch(self, stage: int, item: str = "", view: str = "stage", guide: str = "") -> None:
        self.last_stage = stage
        self.last_item = item
        self.last_view = view if view in ("stage", "course") else "stage"
        self.last_guide = guide
        self.updated_at = time.time()
        self.save()

    # -- practice results --------------------------------------------------

    def result_for(self, stage: int, item_name: str) -> PracticeResult | None:
        return self.results.get(item_key(stage, item_name))

    def record_practice(
        self,
        stage: int,
        item_name: str,
        hits: int,
        misses: int,
        total: int,
        avg_ms: int = 0,
        best_streak: int = 0,
        first_try: int = 0,
    ) -> PracticeResult:
        candidate = PracticeResult(
            hits=max(0, hits),
            misses=max(0, misses),
            total=max(0, total),
            completed=total > 0 and hits >= total,
            updated_at=time.time(),
            avg_ms=max(0, avg_ms),
            best_streak=max(0, best_streak),
            first_try=max(0, first_try),
        )
        old = self.result_for(stage, item_name)
        if old is None or _better(candidate, old):
            self.results[item_key(stage, item_name)] = candidate
        # Even a worse run is an activity: keep the best score, but move the
        # "last active" clock and persist the file.
        self.updated_at = candidate.updated_at
        self.save()
        return self.results.get(item_key(stage, item_name), candidate)

    # -- guide step checklists --------------------------------------------

    @staticmethod
    def _step_key(stage: int, guide_key: str) -> str:
        return f"{stage}:{guide_key}"

    def guide_steps_for(self, stage: int, guide_key: str) -> frozenset[int]:
        """Checked step indices for one lesson; reads never create the file."""
        return frozenset(self.guide_steps.get(self._step_key(stage, guide_key), ()))

    def set_guide_step(
        self, stage: int, guide_key: str, index: int, checked: bool
    ) -> frozenset[int]:
        """Check/uncheck one step and persist immediately."""
        key = self._step_key(stage, guide_key)
        done = set(self.guide_steps.get(key, ()))
        if checked:
            done.add(max(0, int(index)))
        else:
            done.discard(int(index))
        if done:
            self.guide_steps[key] = tuple(sorted(done))
        else:
            self.guide_steps.pop(key, None)
        self.updated_at = time.time()
        self.save()
        return frozenset(done)

    # -- optional exams ----------------------------------------------------

    def exam_for(self, key: str) -> ExamRecord | None:
        return self.exams.get(key)

    def record_exam(self, result: ExamResult) -> ExamRecord:
        """Keep the best exam attempt; every attempt still bumps the counter."""
        now = time.time()
        old = self.exams.get(result.key)
        candidate = ExamRecord(
            key=result.key,
            stage_index=result.stage_index,
            kind=result.kind,
            passed=result.passed,
            total=result.total,
            hits=result.hits,
            misses=result.misses,
            extras=result.extras,
            first_try=result.first_try,
            avg_ms=result.avg_ms,
            finished=result.finished,
            attempts=(old.attempts if old is not None else 0) + 1,
            updated_at=now,
        )
        if old is None or _exam_better(candidate, old):
            self.exams[result.key] = candidate
        else:
            self.exams[result.key] = replace(
                old, attempts=candidate.attempts, updated_at=now
            )
        self.updated_at = now
        self.save()
        return self.exams[result.key]

    def relative_time(self) -> str:
        if self.updated_at <= 0:
            return ""
        seconds = max(0, int(time.time() - self.updated_at))
        if seconds < 60:
            return "刚刚"
        if seconds < 3600:
            return f"{seconds // 60} 分钟前"
        if seconds < 86400:
            return f"{seconds // 3600} 小时前"
        return f"{seconds // 86400} 天前"
