"""QTimer wrapper that plays a PlaybackPlan through the synth (H4 slice).

Scheduling is kept in ``advance(now)`` so tests can drive an explicit clock;
the 20 ms timer only supplies ``time.monotonic()`` in the real app.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.playback import PlaybackPlan, build_playback
from ..core.project import Project


class ProjectPlayer(QObject):
    positionChanged = Signal(float)  # beats inside the plan
    stateChanged = Signal()
    finished = Signal()
    message = Signal(str)

    def __init__(self, synth, auto_timer: bool = True, parent=None):
        super().__init__(parent)
        self.synth = synth
        self.plan: PlaybackPlan | None = None
        self.playing = False
        self._auto_timer = auto_timer
        self._position = 0.0
        self._last = 0.0
        self._cursors: list[int] = []
        self._held: list[tuple[float, int, int]] = []
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._tick)

    @property
    def position(self) -> float:
        return self._position

    def set_project(self, project: Project) -> None:
        self.stop()
        self.plan = build_playback(project)
        self.positionChanged.emit(0.0)

    def play(self, at: float | None = None) -> bool:
        if self.plan is None or self.plan.empty:
            self.message.emit("项目里还没有可播放的音符 · 先录一段或画一个音")
            return False
        if self.playing:
            return True
        self._prepare()
        self._position = 0.0
        self._cursors = [0] * len(self.plan.tracks)
        self._held = []
        self._last = time.monotonic() if at is None else at
        self.playing = True
        if self._auto_timer:
            self._timer.start()
        self.positionChanged.emit(0.0)
        self.stateChanged.emit()
        self.message.emit("项目播放中 · 空格暂停")
        return True

    def toggle(self, at: float | None = None) -> bool:
        if self.playing:
            self.stop()
            return False
        return self.play(at)

    def stop(self) -> None:
        was_playing = self.playing
        self.playing = False
        self._timer.stop()
        self._release_held()
        self._position = 0.0
        if was_playing:
            self.stateChanged.emit()
            self.positionChanged.emit(0.0)
            self.message.emit("项目播放已停止")

    def advance(self, now: float) -> None:
        if not self.playing or self.plan is None:
            return
        delta = max(0.0, min(0.5, now - self._last))
        self._last = now
        self._position += delta

        if self.plan.duration > 0 and self._position >= self.plan.duration:
            if self.plan.loop:
                self._position %= self.plan.duration
                self._release_held()
                self._cursors = [0] * len(self.plan.tracks)
            else:
                self._finish()
                return

        self._trigger_due()
        self._release_due()
        self.positionChanged.emit(self.plan.beats_at(self._position))

    # -- scheduling -------------------------------------------------------

    def _prepare(self) -> None:
        for track in self.plan.tracks if self.plan is not None else ():
            self.synth.program_on(track.channel, track.program)
            self.synth.channel_volume(track.channel, track.volume)
            self.synth.channel_pan(track.channel, track.pan)

    def _trigger_due(self) -> None:
        if self.plan is None:
            return
        for index, track in enumerate(self.plan.tracks):
            notes = track.notes
            cursor = self._cursors[index]
            while (
                cursor < len(notes)
                and notes[cursor].start <= self._position + 1e-6
            ):
                note = notes[cursor]
                self.synth.note_on(
                    note.midi, note.velocity, channel=track.channel
                )
                self._held.append((note.end, track.channel, note.midi))
                cursor += 1
            self._cursors[index] = cursor

    def _release_due(self) -> None:
        for item in list(self._held):
            end, channel, midi = item
            if end <= self._position + 1e-6:
                self.synth.note_off(midi, channel=channel)
                self._held.remove(item)

    def _release_held(self) -> None:
        for _end, channel, midi in self._held:
            self.synth.note_off(midi, channel=channel)
        self._held.clear()

    def _finish(self) -> None:
        self._release_held()
        self.playing = False
        self._timer.stop()
        self._position = 0.0
        self.stateChanged.emit()
        self.positionChanged.emit(0.0)
        self.finished.emit()
        self.message.emit("项目播放结束")

    def _tick(self) -> None:
        self.advance(time.monotonic())
