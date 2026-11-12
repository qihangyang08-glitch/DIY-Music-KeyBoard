"""Piano-roll editing rules (no Qt).

The editor owns one track at a time. It snapshots before every user gesture so
a drag, resize, or duplicate is exactly one undo step. Values are clamped here,
not in the view, so mouse coordinates can never create invalid notes.
"""

from __future__ import annotations

from .project import NoteEvent, Project, Track

MIN_DURATION = 0.25  # 1/16 note in 4/4
MAX_UNDO = 50


class NoteEditor:
    def __init__(self, project: Project, track_index: int = 0) -> None:
        self._undo: list[tuple[int, list[NoteEvent]]] = []
        self._gesture: tuple[int, list[NoteEvent]] | None = None
        self.set_project(project, track_index)

    def set_project(self, project: Project, track_index: int = 0) -> None:
        self.project = project
        self.track_index = track_index if 0 <= track_index < len(project.tracks) else 0
        self._undo.clear()
        self._gesture = None

    @property
    def track(self) -> Track | None:
        if 0 <= self.track_index < len(self.project.tracks):
            return self.project.tracks[self.track_index]
        return None

    @property
    def notes(self) -> list[NoteEvent]:
        track = self.track
        return track.notes if track is not None else []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    def select_track(self, index: int) -> bool:
        if 0 <= index < len(self.project.tracks):
            self.track_index = index
            return True
        return False

    # -- gestures ---------------------------------------------------------

    def _snapshot(self) -> tuple[int, list[NoteEvent]] | None:
        track = self.track
        if track is None:
            return None
        return (self.track_index, list(track.notes))

    def _push(self, snapshot: tuple[int, list[NoteEvent]] | None) -> None:
        if snapshot is None:
            return
        self._undo.append(snapshot)
        del self._undo[:-MAX_UNDO]

    def begin_gesture(self) -> None:
        if self._gesture is None:
            self._gesture = self._snapshot()

    def end_gesture(self) -> None:
        snapshot = self._gesture
        self._gesture = None
        track = self.track
        if snapshot is None or track is None:
            return
        if snapshot[0] == self.track_index and list(track.notes) == snapshot[1]:
            return
        self._push(snapshot)
        track.notes.sort(key=lambda note: (note.start, note.midi))

    def cancel_gesture(self) -> None:
        snapshot = self._gesture
        self._gesture = None
        if snapshot is None:
            return
        index, notes = snapshot
        if 0 <= index < len(self.project.tracks):
            self.project.tracks[index].notes = list(notes)
            self.track_index = index

    # -- editing ----------------------------------------------------------

    @staticmethod
    def _clamp(start: float, midi: float, duration: float) -> tuple[float, int, float]:
        return (
            max(0.0, start),
            max(0, min(127, int(round(midi)))),
            max(MIN_DURATION, duration),
        )

    def insert_note(self, start: float, midi: float, duration: float = 1.0) -> int:
        """Append without snapshot/sort; used inside a gesture."""
        track = self.track
        if track is None:
            return -1
        start, midi, duration = self._clamp(start, midi, duration)
        track.notes.append(NoteEvent(start, midi, duration))
        return len(track.notes) - 1

    def update_note(
        self,
        index: int,
        *,
        start: float | None = None,
        midi: float | None = None,
        duration: float | None = None,
    ) -> bool:
        """Replace fields without snapshot/sort; used inside a gesture."""
        track = self.track
        if track is None or not 0 <= index < len(track.notes):
            return False
        old = track.notes[index]
        new_start, new_midi, new_duration = self._clamp(
            old.start if start is None else start,
            old.midi if midi is None else midi,
            old.duration if duration is None else duration,
        )
        track.notes[index] = NoteEvent(new_start, new_midi, new_duration)
        return True

    @staticmethod
    def _index_of(track: Track, note: NoteEvent) -> int:
        for index, candidate in enumerate(track.notes):
            if candidate is note:
                return index
        return -1

    def add_note(self, start: float, midi: float, duration: float = 1.0) -> int:
        track = self.track
        if track is None:
            return -1
        self.begin_gesture()
        start, midi, duration = self._clamp(start, midi, duration)
        note = NoteEvent(start, midi, duration)
        track.notes.append(note)
        self.end_gesture()
        return self._index_of(track, note)

    def erase_note(self, index: int) -> bool:
        track = self.track
        if track is None or not 0 <= index < len(track.notes):
            return False
        self._push(self._snapshot())
        del track.notes[index]
        return True

    def move_note(self, index: int, delta_start: float, delta_midi: float) -> bool:
        track = self.track
        if track is None or not 0 <= index < len(track.notes):
            return False
        old = track.notes[index]
        self.begin_gesture()
        ok = self.update_note(
            index, start=old.start + delta_start, midi=old.midi + delta_midi
        )
        self.end_gesture()
        return ok

    def resize_note(self, index: int, delta_duration: float) -> bool:
        track = self.track
        if track is None or not 0 <= index < len(track.notes):
            return False
        old = track.notes[index]
        self.begin_gesture()
        ok = self.update_note(index, duration=old.duration + delta_duration)
        self.end_gesture()
        return ok

    def duplicate_note(self, index: int) -> int:
        track = self.track
        if track is None or not 0 <= index < len(track.notes):
            return -1
        old = track.notes[index]
        self.begin_gesture()
        start, midi, duration = self._clamp(
            old.start + old.duration, old.midi, old.duration
        )
        note = NoteEvent(start, midi, duration)
        track.notes.append(note)
        self.end_gesture()
        return self._index_of(track, note)

    def undo(self) -> bool:
        if not self._undo:
            return False
        index, notes = self._undo.pop()
        if 0 <= index < len(self.project.tracks):
            self.project.tracks[index].notes = list(notes)
            self.track_index = index
        return True
