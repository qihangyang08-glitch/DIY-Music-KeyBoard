"""Generated learning drills: question order + judging rules, no UI.

The first drill is the stage 1 note-name flashcard. It shows one note on the
treble staff and asks the user to press that pitch on the 32-key instrument.
The module owns everything that can be tested without Qt:

- the question deck (a reshuffled bag, so every note appears and no note is
  asked twice in a row);
- the judging rule (exact MIDI pitch — octave matters);
- the counters used by the learning archive: solved questions, wrong presses,
  first-try answers, streak, response time.

A wrong press reveals the correct note and does not advance. The user can
retry; the retry is counted in accuracy, but it never blocks completion the
way a wrong note blocks a score follow. That is deliberately gentler than the
score drill and matches the v3 note-reading spec ("答错：显示正确位置 + 音名，
不扣分；可重试").
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from .note_engine import midi_name
from .rhythm import RhythmSpec, rest

# Diatonic index of E4, the bottom line of the treble staff. A staff step is
# half a line/space; C4 is step -2 (one ledger line below), C5 is step 5.
_TREBLE_E4 = 4 * 7 + 2
# Bass staff bottom line is G2. C3 is step 3 (second space), C4 step 10
# (first ledger line above), so middle C meets the treble staff at step -2.
_BASS_G2 = 2 * 7 + 4
_NATURAL_STEPS = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def _split_name(name: str) -> tuple[str, int]:
    letter = name[0].upper()
    digits = "".join(ch for ch in name[1:] if ch.isdigit() or ch == "-")
    return letter, int(digits)


@dataclass(frozen=True)
class NotePrompt:
    """One question, including its spelled name and staff accidental."""

    midi: int
    name: str
    letter: str
    octave: int
    accidental: str = ""  # "♯" / "♭" for the staff glyph; "" = natural

    def staff_step_for(self, clef: str) -> int:
        bottom = _BASS_G2 if clef == "bass" else _TREBLE_E4
        return self.octave * 7 + _NATURAL_STEPS.get(self.letter, 0) - bottom

    @property
    def staff_step(self) -> int:
        return self.staff_step_for("treble")


def note_prompt(midi: int) -> NotePrompt:
    """Prompt for a natural note, using the sharp-only MIDI name."""
    name = midi_name(midi)
    letter, octave = _split_name(name)
    return NotePrompt(int(midi), name, letter, octave)


def spelled_prompt(midi: int, name: str, accidental: str) -> NotePrompt:
    """Prompt with an explicit spelling, e.g. B♭4 = A#4 but on the B line."""
    letter, octave = _split_name(name)
    return NotePrompt(int(midi), name, letter, octave, accidental)


def staff_step(midi: int) -> int:
    """Treble-staff step for a natural note; 0 = bottom line (E4)."""
    return note_prompt(midi).staff_step


def bass_staff_step(midi: int) -> int:
    """Bass-staff step for a natural note; 0 = bottom line (G2)."""
    return note_prompt(midi).staff_step_for("bass")


@dataclass(frozen=True)
class NoteQuestion:
    midi: int
    name: str
    staff_step: int
    accidental: str = ""  # "♯" / "♭" for the staff glyph; "" = natural
    clef: str = "treble"  # treble | bass


@dataclass(frozen=True)
class OnboardingStep:
    """One guided action in a stage-0 onboarding drill.

    action is "press" (a MIDI note), "sustain" (Shift down) or "panic"
    (全部静音). require_sustain makes a press only count while sustain is
    held, so the learner actually hears the note ring after releasing the key.
    """

    action: str  # press | sustain | panic
    title: str
    detail: str
    midi: int | None = None
    require_sustain: bool = False


@dataclass(frozen=True)
class DrillSpec:
    key: str
    title: str
    subtitle: str
    midis: tuple[int, ...] = ()
    prompts: tuple[NotePrompt, ...] = ()
    question_count: int = 10
    mapping_base: int = 60  # MIDI for bar 1 while a note drill is open
    staff_caption: str = "高音谱号 · C4–C5"
    clef: str = "treble"  # treble | bass
    kind: str = "note"  # note | rhythm | onboarding
    rhythm: RhythmSpec | None = None
    steps: tuple[OnboardingStep, ...] = ()

    @property
    def prompt_pool(self) -> tuple[NotePrompt, ...]:
        if self.prompts:
            return self.prompts
        return tuple(note_prompt(midi) for midi in self.midis)

    @property
    def range_label(self) -> str:
        if not self.midis and not self.steps:
            return ""
        return f"{midi_name(self.mapping_base)}–{midi_name(self.mapping_base + 31)}"

    @property
    def question_range_label(self) -> str:
        if not self.midis:
            return ""
        return f"{midi_name(min(self.midis))}–{midi_name(max(self.midis))}"


# Stage 1, D1-01/02/05/06: C4–C5, C4–C6, octave correspondence and accidentals.
NOTE_NAMES_C4_C5 = (60, 62, 64, 65, 67, 69, 71, 72)
NOTE_NAMES_C4_C6 = (
    60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84,
)
NOTE_NAMES_C3_C4 = (48, 50, 52, 53, 55, 57, 59, 60)

# C/E/G/A across three octaves: the same letter at C4/C5/C6 is a different
# key, and G6 is the top of the temporary C4–G6 drill mapping (base 60).
OCTAVE_PROMPTS = tuple(
    note_prompt(midi)
    for midi in (60, 72, 84, 64, 76, 88, 67, 79, 91, 69, 81)
)

# D1-06: both spellings of the same key are asked. The staff glyph keeps the
# spelling (B♭ on the B line), while the MIDI number decides the answer.
ACCIDENTAL_PROMPTS = (
    spelled_prompt(61, "C#4", "♯"),
    spelled_prompt(63, "D#4", "♯"),
    spelled_prompt(66, "F#4", "♯"),
    spelled_prompt(68, "G#4", "♯"),
    spelled_prompt(70, "A#4", "♯"),
    spelled_prompt(61, "D♭4", "♭"),
    spelled_prompt(63, "E♭4", "♭"),
    spelled_prompt(66, "G♭4", "♭"),
    spelled_prompt(68, "A♭4", "♭"),
    spelled_prompt(70, "B♭4", "♭"),
)

RHYTHM_QUARTERS_HALVES = RhythmSpec(
    key="rhythm_quarters_halves_4_4",
    title="四分与二分 · 4/4",
    subtitle="4/4 · 4 小节 · 80 BPM",
    bpm=80,
    beats_per_bar=4,
    bars=4,
    cells=((1, 1, 2), (2, 1, 1), (1, 1, 2), (2, 1, 1)),
    tolerance_ms=150,
)

RHYTHM_EIGHTHS = RhythmSpec(
    key="rhythm_eighths_4_4",
    title="八分音符组合",
    subtitle="4/4 · 2 小节 · 八分音符 · 80 BPM",
    bpm=80,
    beats_per_bar=4,
    bars=2,
    cells=((0.5,) * 8, (0.5,) * 8),
    tolerance_ms=100,
)

RHYTHM_WALTZ = RhythmSpec(
    key="rhythm_waltz_3_4",
    title="3/4 圆舞曲型",
    subtitle="3/4 · 4 小节 · 80 BPM",
    bpm=80,
    beats_per_bar=3,
    bars=4,
    cells=((1, 1, 1),) * 4,
    tolerance_ms=150,
)

RHYTHM_SIX_EIGHT = RhythmSpec(
    key="rhythm_six_eight",
    title="6/8 复拍子",
    subtitle="6/8 · 4 小节 · 两组三拍 · 120 BPM",
    bpm=120,
    beats_per_bar=6,
    bars=4,
    cells=(
        (1, 1, 1, 1, 1, 1),
        (3, 3),
        (2, 1, 2, 1),
        (1, 1, 1, 3),
    ),
    tolerance_ms=130,
    accent_beats=(0, 3),
    meter="6/8",
)

RHYTHM_SYNCOPATION = RhythmSpec(
    key="rhythm_syncopation_4_4",
    title="切分节奏",
    subtitle="4/4 · 4 小节 · 重音在弱拍 · 80 BPM",
    bpm=80,
    beats_per_bar=4,
    bars=4,
    cells=(
        (1.5, 0.5, 1, 1),
        (0.5, 1, 0.5, 2),
        (1, 1.5, 0.5, 1),
        (2, 0.5, 0.5, 1),
    ),
    tolerance_ms=120,
)

RHYTHM_TRIPLETS = RhythmSpec(
    key="rhythm_triplets_4_4",
    title="三连音",
    subtitle="4/4 · 2 小节 · 每拍三音 · 60 BPM",
    bpm=60,
    beats_per_bar=4,
    bars=2,
    cells=((1 / 3,) * 12,) * 2,
    tolerance_ms=90,
)

RHYTHM_RESTS_DOTS = RhythmSpec(
    key="rhythm_rests_dots_4_4",
    title="休止与附点",
    subtitle="4/4 · 4 小节 · 休止与附点 · 80 BPM",
    bpm=80,
    beats_per_bar=4,
    bars=4,
    cells=(
        (1, rest(1), 1, 1),      # quarter rest
        (1.5, 0.5, 2),           # dotted quarter + eighth + half
        (2, rest(2)),            # half note + half rest
        (3, 1),                  # dotted half + quarter
    ),
    tolerance_ms=150,
)

# Stage 0, D0-02/D0-04/D0-05: the two interactions that cannot be a staff
# question. The drill temporarily maps bar 1 to C4, so middle C is reachable
# even though the default performance mapping starts at F4.
ONBOARD_MIDDLE_C = DrillSpec(
    key="onboarding_middle_c",
    title="找到中央 C",
    subtitle="C4 → D4 → E4 → C4",
    kind="onboarding",
    mapping_base=60,
    steps=(
        OnboardingStep(
            "press",
            "找到中央 C",
            "在 32 条光条上找到标着 C4 的那一条（现在就是第 1 条），"
            "按下去。",
            60,
        ),
        OnboardingStep(
            "press",
            "往右是 D",
            "D4 在 C4 右边两条：按一下，听它比 C4 高一点。",
            62,
        ),
        OnboardingStep(
            "press",
            "再往右是 E",
            "E4 在 D4 右边两条：按一下。",
            64,
        ),
        OnboardingStep(
            "press",
            "回到中央 C",
            "再按一次 C4。C–D–E–C，这就是你的第一段小旋律。",
            60,
        ),
    ),
)

ONBOARD_SUSTAIN_PANIC = DrillSpec(
    key="onboarding_sustain_panic",
    title="延音与全部静音",
    subtitle="延音 Shift · 全部静音 Esc",
    kind="onboarding",
    mapping_base=60,
    steps=(
        OnboardingStep(
            "sustain",
            "按住延音",
            "按住 Shift（延音）。先不要松开。",
        ),
        OnboardingStep(
            "press",
            "按住延音弹一个音",
            "保持按住 Shift，按一下 C4，再松开 C4：音会继续响。",
            60,
            require_sustain=True,
        ),
        OnboardingStep(
            "panic",
            "全部静音",
            "按 Esc（全部静音），所有声音立刻停止。",
        ),
    ),
)


DRILL_SPECS: dict[str, DrillSpec] = {
    "onboarding_middle_c": ONBOARD_MIDDLE_C,
    "onboarding_sustain_panic": ONBOARD_SUSTAIN_PANIC,
    "note_names_c4_c5": DrillSpec(
        key="note_names_c4_c5",
        title="音名闪卡 · C4–C5",
        subtitle="高音谱号 · 自然音 8 个 · 10 题",
        midis=NOTE_NAMES_C4_C5,
        question_count=10,
        mapping_base=60,
        staff_caption="高音谱号 · C4–C5 自然音",
    ),
    "note_names_c4_c6": DrillSpec(
        key="note_names_c4_c6",
        title="线间定位 · 高音谱号",
        subtitle="高音谱号 · C4–C6 自然音 15 个 · 10 题",
        midis=NOTE_NAMES_C4_C6,
        question_count=10,
        mapping_base=60,
        staff_caption="高音谱号 · C4–C6 自然音",
    ),
    "octave_names_c4_c6": DrillSpec(
        key="octave_names_c4_c6",
        title="八度上下行",
        subtitle="高音谱号 · C/E/G/A 跨 C4–G6 · 10 题",
        midis=tuple(sorted({prompt.midi for prompt in OCTAVE_PROMPTS})),
        prompts=OCTAVE_PROMPTS,
        question_count=10,
        mapping_base=60,
        staff_caption="高音谱号 · 八度对应",
    ),
    "note_accidentals_c4_c5": DrillSpec(
        key="note_accidentals_c4_c5",
        title="临时记号 · 升与降",
        subtitle="高音谱号 · ♯ / ♭ · 10 题",
        midis=tuple(sorted({prompt.midi for prompt in ACCIDENTAL_PROMPTS})),
        prompts=ACCIDENTAL_PROMPTS,
        question_count=10,
        mapping_base=60,
        staff_caption="高音谱号 · 升与降",
    ),
    "note_names_bass_c3_c4": DrillSpec(
        key="note_names_bass_c3_c4",
        title="低音谱号 · C3–C4",
        subtitle="低音谱号 · 自然音 8 个 · 10 题",
        midis=NOTE_NAMES_C3_C4,
        question_count=10,
        mapping_base=48,
        staff_caption="低音谱号 · C3–C4 自然音",
        clef="bass",
    ),
    "rhythm_quarters_halves_4_4": DrillSpec(
        key="rhythm_quarters_halves_4_4",
        title=RHYTHM_QUARTERS_HALVES.title,
        subtitle=RHYTHM_QUARTERS_HALVES.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_QUARTERS_HALVES,
    ),
    "rhythm_eighths_4_4": DrillSpec(
        key="rhythm_eighths_4_4",
        title=RHYTHM_EIGHTHS.title,
        subtitle=RHYTHM_EIGHTHS.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_EIGHTHS,
    ),
    "rhythm_waltz_3_4": DrillSpec(
        key="rhythm_waltz_3_4",
        title=RHYTHM_WALTZ.title,
        subtitle=RHYTHM_WALTZ.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_WALTZ,
    ),
    "rhythm_rests_dots_4_4": DrillSpec(
        key="rhythm_rests_dots_4_4",
        title=RHYTHM_RESTS_DOTS.title,
        subtitle=RHYTHM_RESTS_DOTS.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_RESTS_DOTS,
    ),
    "rhythm_six_eight": DrillSpec(
        key="rhythm_six_eight",
        title=RHYTHM_SIX_EIGHT.title,
        subtitle=RHYTHM_SIX_EIGHT.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_SIX_EIGHT,
    ),
    "rhythm_syncopation_4_4": DrillSpec(
        key="rhythm_syncopation_4_4",
        title=RHYTHM_SYNCOPATION.title,
        subtitle=RHYTHM_SYNCOPATION.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_SYNCOPATION,
    ),
    "rhythm_triplets_4_4": DrillSpec(
        key="rhythm_triplets_4_4",
        title=RHYTHM_TRIPLETS.title,
        subtitle=RHYTHM_TRIPLETS.subtitle,
        kind="rhythm",
        rhythm=RHYTHM_TRIPLETS,
    ),
}


def drill_spec(key: str | None) -> DrillSpec | None:
    return DRILL_SPECS.get(key or "")


@dataclass(frozen=True)
class DrillTarget:
    stage_index: int
    item_name: str
    drill: str
    origin_view: str
    guide_title: str = ""


@dataclass(frozen=True)
class AnswerResult:
    correct: bool
    expected: NoteQuestion
    pressed_midi: int
    pressed_name: str
    first_try: bool
    advanced: bool
    finished: bool
    revealed: bool


@dataclass(frozen=True)
class StepResult:
    """One judged onboarding action; mirrors AnswerResult for the UI."""

    correct: bool
    step: OnboardingStep
    pressed_midi: int | None = None
    pressed_name: str = ""
    first_try: bool = False
    advanced: bool = False
    finished: bool = False
    revealed: bool = False
    sustain_required: bool = False  # wrong because sustain was not held


@dataclass(frozen=True)
class DrillOutcome:
    """What the learning archive needs, independent of the UI."""

    hits: int          # solved questions
    misses: int        # wrong presses
    total: int         # question count
    attempts: int
    first_try: int
    accuracy: int
    avg_ms: int
    best_streak: int
    finished: bool


def _build_questions(
    spec: DrillSpec, rng: random.Random
) -> list[NoteQuestion]:
    """Reshuffled bag: every prompt appears, with no immediate MIDI repeat."""
    prompts = spec.prompt_pool
    if not prompts:
        return []
    pool: list[NotePrompt] = []
    questions: list[NoteQuestion] = []
    last: int | None = None

    while len(questions) < spec.question_count:
        if not pool:
            pool = list(prompts)
            rng.shuffle(pool)
            if len(pool) > 1 and pool[0].midi == last:
                pool.append(pool.pop(0))
        prompt = pool.pop(0)
        if prompt.midi == last and pool:
            pool.append(prompt)
            prompt = pool.pop(0)
        questions.append(
            NoteQuestion(
                midi=prompt.midi,
                name=prompt.name,
                staff_step=prompt.staff_step_for(spec.clef),
                accidental=prompt.accidental,
                clef=spec.clef,
            )
        )
        last = prompt.midi
    return questions


def _build_outcome(
    hits: int,
    misses: int,
    total: int,
    response_ms: list[float],
    first_try: int,
    best_streak: int,
    finished: bool,
) -> DrillOutcome:
    attempts = hits + misses
    avg_ms = (
        round(sum(response_ms) / len(response_ms)) if response_ms else 0
    )
    return DrillOutcome(
        hits=hits,
        misses=misses,
        total=total,
        attempts=attempts,
        first_try=first_try,
        accuracy=round(100 * hits / attempts) if attempts else 0,
        avg_ms=avg_ms,
        best_streak=best_streak,
        finished=finished,
    )


class NoteNameSession:
    """One run of the note-name flashcard drill."""

    def __init__(
        self,
        spec: DrillSpec,
        rng: random.Random | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.spec = spec
        self.questions = _build_questions(spec, rng or random.Random())
        self.index = 0
        self.hits = 0
        self.misses = 0
        self.attempts = 0
        self.first_try = 0
        self.streak = 0
        self.best_streak = 0
        self.last_result: AnswerResult | None = None
        self._response_ms: list[float] = []
        self._response_recorded = False
        self._wrong_this_question = False
        self._clock = clock or time.monotonic
        self._question_started = self._clock()

    # -- read side ------------------------------------------------------

    def mark_shown(self, now: float | None = None) -> None:
        """Start the response clock when the question is actually visible.

        The page calls this after the staff is repainted. Without it the
        340 ms correct-answer dwell would be charged to the next question and
        the average would measure time-to-solve rather than first response.
        """
        self._question_started = self._clock() if now is None else now
        self._response_recorded = False

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def finished(self) -> bool:
        return self.index >= len(self.questions)

    @property
    def current(self) -> NoteQuestion | None:
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None

    @property
    def revealed(self) -> bool:
        """True after a wrong press, until the question is solved."""
        return self._wrong_this_question

    @property
    def accuracy(self) -> int:
        attempts = self.hits + self.misses
        return round(100 * self.hits / attempts) if attempts else 0

    # -- judging --------------------------------------------------------

    def answer(self, midi: int) -> AnswerResult | None:
        question = self.current
        if question is None:
            return None
        now = self._clock()
        self.attempts += 1
        if not self._response_recorded:
            self._response_ms.append(max(0.0, (now - self._question_started) * 1000.0))
            self._response_recorded = True
        correct = int(midi) == question.midi
        first_try = False
        advanced = False
        finished = False

        if correct:
            self.hits += 1
            if self._wrong_this_question:
                # The retry solved it, but this was not a first-try answer;
                # the streak was already reset by the wrong press.
                self.streak = 0
            else:
                self.first_try += 1
                self.streak += 1
                first_try = True
            self.best_streak = max(self.best_streak, self.streak)
            self.index += 1
            advanced = True
            finished = self.finished
            self._wrong_this_question = False
            # Provisional; the page calls mark_shown() when the next question
            # is actually painted, which removes the feedback dwell.
            self._question_started = self._clock()
            self._response_recorded = False
        else:
            self.misses += 1
            self.streak = 0
            self._wrong_this_question = True

        result = AnswerResult(
            correct=correct,
            expected=question,
            pressed_midi=int(midi),
            pressed_name=midi_name(int(midi)),
            first_try=first_try,
            advanced=advanced,
            finished=finished,
            revealed=self._wrong_this_question,
        )
        self.last_result = result
        return result

    # -- summary --------------------------------------------------------

    def outcome(self) -> DrillOutcome:
        return _build_outcome(
            self.hits,
            self.misses,
            self.total,
            self._response_ms,
            self.first_try,
            self.best_streak,
            self.finished,
        )


class OnboardingSession:
    """One run of a stage-0 guided drill (press / sustain / panic steps).

    Wrong presses reveal the target and count toward accuracy, but only the
    step's own action advances it: holding a note during the sustain step is
    not an answer, and the panic step ignores key presses entirely.
    """

    def __init__(
        self,
        spec: DrillSpec,
        clock: Callable[[], float] | None = None,
    ):
        self.spec = spec
        self.steps = spec.steps
        self.index = 0
        self.hits = 0
        self.misses = 0
        self.attempts = 0
        self.first_try = 0
        self.streak = 0
        self.best_streak = 0
        self.last_result: StepResult | None = None
        self._response_ms: list[float] = []
        self._response_recorded = False
        self._wrong_this_step = False
        self._clock = clock or time.monotonic
        self._step_started = self._clock()

    # -- read side ------------------------------------------------------

    def mark_shown(self, now: float | None = None) -> None:
        """Start the response clock once the step is visible."""
        self._step_started = self._clock() if now is None else now
        self._response_recorded = False

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def finished(self) -> bool:
        return self.index >= len(self.steps)

    @property
    def current(self) -> OnboardingStep | None:
        if 0 <= self.index < len(self.steps):
            return self.steps[self.index]
        return None

    @property
    def revealed(self) -> bool:
        return self._wrong_this_step

    @property
    def accuracy(self) -> int:
        attempts = self.hits + self.misses
        return round(100 * self.hits / attempts) if attempts else 0

    # -- judging --------------------------------------------------------

    def press(self, midi: int, sustain: bool = False) -> StepResult | None:
        step = self.current
        if step is None or step.action != "press":
            return None
        self._note_attempt()
        pressed = int(midi)
        if step.require_sustain and not sustain:
            self.misses += 1
            self.streak = 0
            self._wrong_this_step = True
            result = StepResult(
                correct=False,
                step=step,
                pressed_midi=pressed,
                pressed_name=midi_name(pressed),
                revealed=True,
                sustain_required=True,
            )
        elif pressed != step.midi:
            self.misses += 1
            self.streak = 0
            self._wrong_this_step = True
            result = StepResult(
                correct=False,
                step=step,
                pressed_midi=pressed,
                pressed_name=midi_name(pressed),
                revealed=True,
            )
        else:
            first_try = self._complete_step()
            result = StepResult(
                correct=True,
                step=step,
                pressed_midi=pressed,
                pressed_name=midi_name(pressed),
                first_try=first_try,
                advanced=True,
                finished=self.finished,
            )
        self.last_result = result
        return result

    def sustain(self, on: bool) -> StepResult | None:
        if not on:
            return None
        step = self.current
        if step is None or step.action != "sustain":
            return None
        self._note_attempt()
        first_try = self._complete_step()
        result = StepResult(
            correct=True,
            step=step,
            pressed_name="延音",
            first_try=first_try,
            advanced=True,
            finished=self.finished,
        )
        self.last_result = result
        return result

    def panic(self) -> StepResult | None:
        step = self.current
        if step is None or step.action != "panic":
            return None
        self._note_attempt()
        first_try = self._complete_step()
        result = StepResult(
            correct=True,
            step=step,
            pressed_name="全部静音",
            first_try=first_try,
            advanced=True,
            finished=self.finished,
        )
        self.last_result = result
        return result

    # -- internals ------------------------------------------------------

    def _note_attempt(self) -> None:
        self.attempts += 1
        if self._response_recorded:
            return
        now = self._clock()
        self._response_ms.append(
            max(0.0, (now - self._step_started) * 1000.0)
        )
        self._response_recorded = True

    def _complete_step(self) -> bool:
        first_try = False
        self.hits += 1
        if self._wrong_this_step:
            # Solved on a retry; the wrong press already ended the streak.
            self.streak = 0
        else:
            self.first_try += 1
            self.streak += 1
            first_try = True
        self.best_streak = max(self.best_streak, self.streak)
        self.index += 1
        self._wrong_this_step = False
        self._step_started = self._clock()
        self._response_recorded = False
        return first_try

    # -- summary --------------------------------------------------------

    def outcome(self) -> DrillOutcome:
        return _build_outcome(
            self.hits,
            self.misses,
            self.total,
            self._response_ms,
            self.first_try,
            self.best_streak,
            self.finished,
        )
