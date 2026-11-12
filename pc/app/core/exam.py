"""Optional stage exams: fixed specs, pass rules and result shape, no UI.

An exam is a *self-check*, not a gate: ordinary practice still decides stage
completion, and a failed exam never clears or blocks a practice result. The
two exams mirror the promises the curriculum makes to a learner:

- stage 1: 20 staff notes, at least 16 (80%) answered correctly on the first
  press;
- stage 2: a clean 4/4 run at 60 BPM — every one of the 16 beats pressed, no
  missed or extra presses, and an average absolute timing error below 60 ms.

Specs are data so the UI only has to launch the drill and show the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from .drill import (
    ACCIDENTAL_PROMPTS,
    NOTE_NAMES_C4_C6,
    OCTAVE_PROMPTS,
    DrillSpec,
    NotePrompt,
    note_prompt,
)
from .rhythm import RhythmSpec

STAGE1_QUESTION_COUNT = 20
STAGE1_MIN_FIRST_TRY = 16  # 80% of 20
STAGE2_BPM = 60
STAGE2_BARS = 4
STAGE2_TOTAL_BEATS = STAGE2_BARS * 4
STAGE2_MAX_AVG_MS = 60


def _unique_prompts(prompts: tuple[NotePrompt, ...]) -> tuple[NotePrompt, ...]:
    """One of each written note; C4 asked once, but C♯4 and D♭4 both stay."""
    seen: set[tuple[int, str, str]] = set()
    out: list[NotePrompt] = []
    for prompt in prompts:
        key = (prompt.midi, prompt.name, prompt.accidental)
        if key in seen:
            continue
        seen.add(key)
        out.append(prompt)
    return tuple(out)


# Stage 1 covers naturals C4–C6, the octave drill's C/E/G/A across C4–G6,
# and the sharp/flat spellings from the accidental drill.
STAGE1_PROMPTS = _unique_prompts(
    tuple(note_prompt(midi) for midi in NOTE_NAMES_C4_C6)
    + OCTAVE_PROMPTS
    + ACCIDENTAL_PROMPTS
)

STAGE1_EXAM_DRILL = DrillSpec(
    key="exam_stage1_notes",
    title="阶段 1 考核 · 识谱 20 音",
    subtitle="高音谱号 C4–G6 · 含临时记号 · 20 题",
    prompts=STAGE1_PROMPTS,
    midis=tuple(sorted({prompt.midi for prompt in STAGE1_PROMPTS})),
    question_count=STAGE1_QUESTION_COUNT,
    mapping_base=60,
    staff_caption="考核 · 高音谱号 C4–G6",
)

STAGE2_RHYTHM = RhythmSpec(
    key="exam_stage2_rhythm",
    title="阶段 2 考核 · 60 BPM 稳定拍",
    subtitle="4/4 · 4 小节 · 60 BPM",
    bpm=STAGE2_BPM,
    beats_per_bar=4,
    bars=STAGE2_BARS,
    cells=((1, 1, 1, 1),) * STAGE2_BARS,
    tolerance_ms=150,
)

STAGE2_EXAM_DRILL = DrillSpec(
    key="exam_stage2_rhythm",
    title=STAGE2_RHYTHM.title,
    subtitle=STAGE2_RHYTHM.subtitle,
    kind="rhythm",
    rhythm=STAGE2_RHYTHM,
)


@dataclass(frozen=True)
class ExamSpec:
    key: str
    stage_index: int
    title: str
    criteria: str
    kind: str  # notes | rhythm
    drill: DrillSpec
    rhythm: RhythmSpec | None = None
    total: int = 0
    min_first_try: int = 0
    max_avg_ms: int = 0

    @property
    def range_label(self) -> str:
        return self.drill.range_label


STAGE1_EXAM = ExamSpec(
    key=STAGE1_EXAM_DRILL.key,
    stage_index=1,
    title="阶段 1 出师考 · 识谱 20 音",
    criteria="20 题 · 首答 ≥16 题（80%）",
    kind="notes",
    drill=STAGE1_EXAM_DRILL,
    total=STAGE1_QUESTION_COUNT,
    min_first_try=STAGE1_MIN_FIRST_TRY,
)

STAGE2_EXAM = ExamSpec(
    key=STAGE2_EXAM_DRILL.key,
    stage_index=2,
    title="阶段 2 出师考 · 60 BPM 稳定拍",
    criteria="16 拍全部踩准 · 无漏拍/多按 · 平均偏差 <60 ms",
    kind="rhythm",
    drill=STAGE2_EXAM_DRILL,
    rhythm=STAGE2_RHYTHM,
    total=STAGE2_TOTAL_BEATS,
    max_avg_ms=STAGE2_MAX_AVG_MS,
)

EXAMS: dict[int, ExamSpec] = {
    STAGE1_EXAM.stage_index: STAGE1_EXAM,
    STAGE2_EXAM.stage_index: STAGE2_EXAM,
}


def exam_spec(stage_index: int) -> ExamSpec | None:
    return EXAMS.get(stage_index)


def exam_by_key(key: str | None) -> ExamSpec | None:
    for spec in EXAMS.values():
        if spec.key == key:
            return spec
    return None


@dataclass(frozen=True)
class ExamResult:
    key: str
    stage_index: int
    kind: str
    passed: bool
    total: int
    hits: int
    misses: int
    extras: int
    first_try: int
    avg_ms: int
    finished: bool

    @property
    def summary(self) -> str:
        if self.kind == "rhythm":
            avg = f"{self.avg_ms} ms" if self.avg_ms else "—"
            return f"踩准 {self.hits}/{self.total} · 平均偏差 {avg}"
        return f"首答 {self.first_try}/{self.total}"

    @property
    def verdict(self) -> str:
        return "通过" if self.passed else "未通过"


def evaluate(spec: ExamSpec, outcome) -> ExamResult:
    """Apply the exam's pass rule to a finished (or partial) session outcome."""
    total = max(0, int(getattr(outcome, "total", 0) or 0))
    hits = max(0, int(getattr(outcome, "hits", 0) or 0))
    misses = max(0, int(getattr(outcome, "misses", 0) or 0))
    extras = max(0, int(getattr(outcome, "extras", 0) or 0))
    first_try = max(0, int(getattr(outcome, "first_try", 0) or 0))
    avg_ms = max(0, int(getattr(outcome, "avg_ms", 0) or 0))
    finished = bool(getattr(outcome, "finished", False))

    if spec.kind == "rhythm":
        passed = (
            finished
            and total == spec.total
            and hits == spec.total
            and misses == 0
            and extras == 0
            and 0 < avg_ms < spec.max_avg_ms
        )
    else:
        passed = (
            finished
            and total == spec.total
            and hits == spec.total
            and first_try >= spec.min_first_try
        )
    return ExamResult(
        key=spec.key,
        stage_index=spec.stage_index,
        kind=spec.kind,
        passed=passed,
        total=total,
        hits=hits,
        misses=misses,
        extras=extras,
        first_try=first_try,
        avg_ms=avg_ms,
        finished=finished,
    )


__all__ = [
    "EXAMS",
    "STAGE1_EXAM",
    "STAGE2_EXAM",
    "ExamResult",
    "ExamSpec",
    "evaluate",
    "exam_by_key",
    "exam_spec",
]
