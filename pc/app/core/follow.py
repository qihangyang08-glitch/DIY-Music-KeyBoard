"""Follow / practice engine for a parsed score (P2 slice).

Practice: the next score note is the expected key; a matching note-on advances
it and counts a hit, anything else counts a miss (and keeps the expected note).

Demo: Space plays the parsed score. Notes are triggered through the existing
Instrument (the "sim" source), so they sound and light the same bars; the
playhead and the next-key hint move with the score.

Auto accompaniment (H7e): a score may arrive with a separate list of notes
(one declared MusicXML part). Those notes are never judged; in practice the
learner's key press is the clock and the accompaniment plays up to the reached
score time, releasing each note at its end. Demo plays both lists.

The UI reads only this session's signals; swapping the parser or adding a
different renderer does not change the follow rules.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from .score import Score, ScoreNote
from .synth_service import ACCOMPANIMENT_CHANNEL, DEMO_CHANNEL
from .window import WindowPlan, WindowSegment, plan_windows


class FollowSession(QObject):
    scoreChanged = Signal(object)      # Score
    stateChanged = Signal()            # position / index / hits / misses
    nextChanged = Signal(object)       # ScoreNote | None
    judged = Signal(bool, object)      # hit, expected ScoreNote
    finished = Signal()
    message = Signal(str)
    demoNote = Signal(int)             # bar for the demo column effect
    windowChanged = Signal(object)     # WindowSegment | None

    def __init__(self, instrument, parent=None):
        super().__init__(parent)
        self.instrument = instrument
        self.score: Score | None = None
        # H7e: notes of the declared part are played by the synth, never
        # judged. They stay out of `score`, so totals and windows ignore them.
        self.accompaniment: tuple[ScoreNote, ...] = ()
        self.window_plan: WindowPlan | None = None
        self._active_segment: WindowSegment | None = None
        self._onset_matched: set[int] = set()
        self.index = 0
        self.position = 0.0
        self.playing = False
        self.hits = 0
        self.misses = 0
        self._last_tick = 0.0
        self._demo_cursor = 0
        self._demo_accomp_cursor = 0
        self._demo_held: set[int] = set()
        self._demo_releases: list[tuple[float, int]] = []
        self._accomp_cursor = 0
        self._accomp_held: list[tuple[float, int]] = []  # (end_time, midi)
        self._last_next = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # -- score / read side ----------------------------------------------

    def set_score(
        self,
        score: Score,
        accompaniment: tuple[ScoreNote, ...] = (),
    ) -> None:
        self._stop_demo()
        self._release_accompaniment()
        self.score = score
        self.accompaniment = tuple(accompaniment)
        self._accomp_cursor = 0
        self._demo_accomp_cursor = 0
        self.index = 0
        self.position = score.notes[0].start if score.notes else 0.0
        self.hits = 0
        self.misses = 0
        self.playing = False
        self._last_next = None
        self._reset_onset()
        self.scoreChanged.emit(score)
        self.rebuild_windows()
        self.sync_window(0)
        self._emit_next(force=True)
        self.stateChanged.emit()

    def clear_score(self) -> None:
        """Drop the current score without pretending a new one was loaded."""
        self._stop_demo()
        self._release_accompaniment()
        self.accompaniment = ()
        self._accomp_cursor = 0
        self._demo_accomp_cursor = 0
        self.score = None
        self.window_plan = None
        self._active_segment = None
        self.index = 0
        self.position = 0.0
        self.playing = False
        self.hits = 0
        self.misses = 0
        self._last_next = None
        self._reset_onset()
        self.nextChanged.emit(None)
        self.stateChanged.emit()
        self.windowChanged.emit(None)

    @property
    def next_note(self) -> ScoreNote | None:
        if self.score is None or not 0 <= self.index < len(self.score.notes):
            return None
        for index in self._onset_indices():
            if index not in self._onset_matched:
                return self.score.notes[index]
        return self.score.notes[self.index]

    @property
    def next_note_index(self) -> int | None:
        if self.score is None or not 0 <= self.index < len(self.score.notes):
            return None
        for index in self._onset_indices():
            if index not in self._onset_matched:
                return index
        return self.index

    def _onset_indices(self) -> list[int]:
        """Indices of every note sharing the current onset's start time."""
        if self.score is None or not 0 <= self.index < len(self.score.notes):
            return []
        notes = self.score.notes
        start = notes[self.index].start
        indices: list[int] = []
        for index in range(self.index, len(notes)):
            if abs(notes[index].start - start) > 1e-6:
                break  # notes are sorted by start; no later note can match
            indices.append(index)
        return indices

    def _reset_onset(self) -> None:
        self._onset_matched.clear()

    @property
    def next_bar(self) -> int | None:
        note = self.next_note
        return self.instrument.bar_for_midi(note.midi) if note is not None else None

    @property
    def progress(self) -> float:
        if self.score is None or self.score.duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.position / self.score.duration))

    # -- automatic 32-key windows ---------------------------------------

    def rebuild_windows(self) -> None:
        """Re-plan phrase windows from the instrument's current mapping."""
        if self.score is None:
            self.window_plan = None
            self._active_segment = None
            return
        self.window_plan = plan_windows(
            self.score,
            self.instrument.current_preset,
            self.instrument.transpose,
            self.instrument.octave,
        )
        self._active_segment = None

    def sync_window(self, index: int | None = None) -> WindowSegment | None:
        """Apply the segment that owns `index` (default: the next note).

        Only called when 自动跟随 is on. Staying inside the same segment does
        nothing, so a manual octave change is not yanked back mid-phrase.
        """
        if self.window_plan is None or not self.instrument.auto_follow:
            return None
        if index is None:
            index = self.index
        segment = self.window_plan.segment_for_note(index)
        if segment is None:
            return None
        if segment == self._active_segment:
            return segment
        self._active_segment = segment
        self.instrument.set_octave_absolute(segment.octave)
        self.windowChanged.emit(segment)
        return segment

    def clear_window(self) -> None:
        self._active_segment = None
        self.windowChanged.emit(None)

    @property
    def active_segment(self) -> WindowSegment | None:
        return self._active_segment

    def window_label(self) -> str | None:
        segment = self._active_segment
        if segment is None or self.window_plan is None:
            return None
        total = len(self.window_plan.segments)
        if total <= 1:
            return segment.range_label
        return f"{segment.range_label} · {segment.index + 1}/{total} 段"

    # -- practice -------------------------------------------------------

    def note_on(self, bar: int) -> None:
        """A physical bar was pressed; judge it against the current onset.

        Notes that share a start time are one onset (a chord or two hands).
        They may be pressed in any order; the score only advances after every
        note in the onset has been matched once.
        """
        if self.score is None or self.playing:
            return
        onset = self._onset_indices()
        if not onset:
            return

        reachable: dict[int, int] = {}
        for index in onset:
            expected_bar = self.instrument.bar_for_midi(
                self.score.notes[index].midi
            )
            if expected_bar is not None:
                reachable[expected_bar] = index

        if bar in reachable:
            index = reachable[bar]
            matched_note = self.score.notes[index]
            if index in self._onset_matched:
                # Re-pressing an already-matched chord note is a miss; it must
                # not silently count as progress.
                self.misses += 1
                expected = self.next_note or matched_note
                self.judged.emit(False, expected)
                self.stateChanged.emit()
                return
            # The learner's key press is the clock: the left hand plays every
            # accompaniment note whose score time has now been reached.
            self._play_accompaniment_until(self.score.notes[onset[0]].start)
            self._onset_matched.add(index)
            self.hits += 1

            if len(self._onset_matched) >= len(onset):
                self.index += len(onset)
                self._onset_matched.clear()
                following = self.next_note
                if following is None:
                    self.position = self.score.duration
                    self.judged.emit(True, matched_note)
                    self.stateChanged.emit()
                    self._emit_next(force=True)
                    self.finished.emit()
                    return
                self.position = following.start
                self.sync_window()
                self.judged.emit(True, matched_note)
                self.stateChanged.emit()
                self._emit_next(force=True)
                return

            # Partial chord: stay on the same onset and show the next note.
            self.position = self.score.notes[self.index].start
            self.sync_window()
            self.judged.emit(True, matched_note)
            self.stateChanged.emit()
            self._emit_next(force=True)
            return

        expected = self.next_note
        if expected is None:
            return
        self.misses += 1
        self.judged.emit(False, expected)
        self.stateChanged.emit()

    # -- left-hand auto accompaniment -----------------------------------

    def _play_accompaniment_until(self, position: float) -> None:
        """Play the declared part up to `position` (score seconds).

        Practice is user-paced, so the key press is the clock: accompaniment
        notes become due when the learner reaches their score time, and a held
        bass note is released once the learner advances past its end.
        """
        self._expire_accompaniment(position)
        while (
            self._accomp_cursor < len(self.accompaniment)
            and self.accompaniment[self._accomp_cursor].start
            <= position + 1e-6
        ):
            note = self.accompaniment[self._accomp_cursor]
            self.instrument.synth.note_on(
                note.midi, 100, channel=ACCOMPANIMENT_CHANNEL
            )
            self._accomp_held.append((note.end, note.midi))
            self._accomp_cursor += 1

    def _expire_accompaniment(self, position: float) -> None:
        for end, midi in list(self._accomp_held):
            if end <= position + 1e-6:
                self.instrument.synth.note_off(
                    midi, channel=ACCOMPANIMENT_CHANNEL
                )
                self._accomp_held.remove((end, midi))

    def _release_accompaniment(self) -> None:
        for _end, midi in self._accomp_held:
            self.instrument.synth.note_off(
                midi, channel=ACCOMPANIMENT_CHANNEL
            )
        self._accomp_held.clear()

    def _accomp_index_from(self, position: float) -> int:
        """First accompaniment note that is not already before `position`."""
        for index, note in enumerate(self.accompaniment):
            if note.start >= position - 1e-6:
                return index
        return len(self.accompaniment)

    def restart(self) -> None:
        if self.score is None:
            return
        self._stop_demo()
        self._release_accompaniment()
        self._accomp_cursor = 0
        self.index = 0
        self.position = self.score.notes[0].start if self.score.notes else 0.0
        self.hits = 0
        self.misses = 0
        self._last_next = None
        self._reset_onset()
        self.rebuild_windows()
        self._emit_next(force=True)
        self.stateChanged.emit()

    # -- demo playback --------------------------------------------------

    def toggle_play(self) -> None:
        if self.score is None:
            return
        if self.playing:
            self.stop()
        else:
            self.play()

    def play(self, at: float | None = None) -> None:
        if self.score is None or not self.score.notes:
            return
        if self.index >= len(self.score.notes):
            self.index = 0
            self.hits = 0
            self.misses = 0
        self._release_accompaniment()
        self.playing = True
        self._reset_onset()
        self._demo_cursor = self.index
        self._demo_accomp_cursor = 0
        self.position = self.score.notes[self.index].start
        self._demo_accomp_cursor = self._accomp_index_from(self.position)
        self._last_tick = time.monotonic() if at is None else at
        self._demo_releases.clear()
        self._demo_held.clear()
        self.sync_window(self.index)
        self._emit_next(force=True)
        self._timer.start()
        self.stateChanged.emit()
        self.message.emit("示范播放中 · 空格暂停")

    def stop(self) -> None:
        was_playing = self.playing
        self._stop_demo()
        if was_playing:
            self.message.emit("示范已暂停 · 轮到你按下一键")

    def _stop_demo(self) -> None:
        self.playing = False
        self._reset_onset()
        self._timer.stop()
        for midi in list(self._demo_held):
            self.instrument.synth.note_off(midi, channel=DEMO_CHANNEL)
        self._demo_held.clear()
        self._demo_releases.clear()
        if self.score is not None:
            following = self.next_note
            self.position = following.start if following is not None else self.score.duration
            self.sync_window()
        self.stateChanged.emit()

    def _tick(self) -> None:
        self.advance(time.monotonic())

    def advance(self, now: float) -> None:
        """Advance the demo clock; `now` is injectable for tests."""
        if not self.playing or self.score is None:
            return
        delta = max(0.0, min(0.12, now - self._last_tick))
        self._last_tick = now
        self.position += delta

        # release demo notes whose score-time end has arrived
        for release_at, midi in list(self._demo_releases):
            if now >= release_at:
                self.instrument.synth.note_off(midi, channel=DEMO_CHANNEL)
                self._demo_held.discard(midi)
                self._demo_releases.remove((release_at, midi))

        # trigger every note whose start is now reached
        changed_next = False
        while (
            self._demo_cursor < len(self.score.notes)
            and self.score.notes[self._demo_cursor].start <= self.position + 1e-6
        ):
            self.sync_window(self._demo_cursor)
            note = self.score.notes[self._demo_cursor]
            self._play_demo_note(note, now)
            bar = self.instrument.bar_for_midi(note.midi)
            if bar is not None:
                self.demoNote.emit(bar)
            self._demo_cursor += 1
            changed_next = True

        # The demo must sound complete: the auto-accompaniment part is not in
        # `score`, so play it here on the same demo channel.
        while (
            self._demo_accomp_cursor < len(self.accompaniment)
            and self.accompaniment[self._demo_accomp_cursor].start
            <= self.position + 1e-6
        ):
            self._play_demo_note(
                self.accompaniment[self._demo_accomp_cursor], now
            )
            self._demo_accomp_cursor += 1

        if changed_next or self._demo_cursor == len(self.score.notes):
            self.index = min(self._demo_cursor, len(self.score.notes))
            self._emit_next()

        if self.position >= self.score.duration + 0.05:
            self._stop_demo()
            self.finished.emit()
            self.message.emit("示范结束 · 按空格从头再听")
            return
        self.stateChanged.emit()

    def _play_demo_note(self, note: ScoreNote, now: float) -> None:
        """Sound one note on the demo channel and schedule its release."""
        self.instrument.synth.note_on(note.midi, 100, channel=DEMO_CHANNEL)
        self._demo_held.add(note.midi)
        remaining = max(0.05, note.end - self.position)
        self._demo_releases.append((now + remaining, note.midi))

    def _emit_next(self, force: bool = False) -> None:
        self.sync_window()
        note = self.next_note
        key = None if note is None else (note.midi, round(note.start, 3))
        if force or key != self._last_next:
            self._last_next = key
            self.nextChanged.emit(note)
