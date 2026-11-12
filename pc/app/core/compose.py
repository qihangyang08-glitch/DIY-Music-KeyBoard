"""Creation session: runtime note timing meets the project model (no Qt).

The instrument reports monotonic seconds; the project stores beats. This class
owns that conversion, the selected track, and the take lifecycle so the UI page
stays a thin view. A take replaces the track by default; overdub merges into it.
"""

from __future__ import annotations

from pathlib import Path

from .project import LoopRegion, Project, Track
from .recorder import Recorder, quantize
from .synth_service import PROGRAMS


class ComposeSession:
    def __init__(self, project: Project | None = None) -> None:
        self.project = project if project is not None else Project()
        self.track_index = 0
        self._recorder: Recorder | None = None
        self._recording = False
        self._overdub = False
        self._start_time = 0.0

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def track(self) -> Track | None:
        if 0 <= self.track_index < len(self.project.tracks):
            return self.project.tracks[self.track_index]
        return None

    @property
    def beats_per_bar(self) -> float:
        return float(self.project.time_signature[0])

    @property
    def loop_enabled(self) -> bool:
        return self.project.loop is not None

    def set_loop(self, enabled: bool, bars: int = 4) -> bool:
        if self._recording:
            return False
        if enabled:
            end = max(1, bars) * self.beats_per_bar
            self.project.loop = LoopRegion(0.0, end)
        else:
            self.project.loop = None
        return True

    def add_track(self, name: str = "") -> Track:
        return self.project.add_track(name)

    def select_track(self, index: int) -> bool:
        if 0 <= index < len(self.project.tracks):
            self.track_index = index
            return True
        return False

    def start(self, now: float, overdub: bool = False) -> bool:
        if self._recording:
            return False
        if not self.project.tracks:
            self.project.add_track()
        self.track_index = min(self.track_index, len(self.project.tracks) - 1)
        self._recorder = Recorder(loop=self.project.loop)
        self._recorder.start()
        self._start_time = now
        self._overdub = overdub
        self._recording = True
        return True

    def _beat(self, at: float) -> float | None:
        if at < self._start_time - 1e-9:
            return None
        return max(0.0, (at - self._start_time) * self.project.tempo / 60.0)

    def note_on(self, midi: int, at: float) -> None:
        beat = self._beat(at)
        if self._recording and self._recorder is not None and beat is not None:
            self._recorder.note_on(midi, beat)

    def note_off(self, midi: int, at: float) -> None:
        beat = self._beat(at)
        if self._recording and self._recorder is not None and beat is not None:
            self._recorder.note_off(midi, beat)

    def stop(self, now: float) -> int:
        if not self._recording or self._recorder is None:
            return 0
        events = self._recorder.stop(self._beat(now) or 0.0)
        self._recording = False
        self._recorder = None
        track = self.track
        if track is not None and events:
            if self._overdub:
                track.overdub(events)
            else:
                track.notes = list(events)
        return len(events)

    def elapsed_seconds(self, now: float) -> float:
        if not self._recording:
            return 0.0
        return max(0.0, now - self._start_time)

    # -- live track settings ---------------------------------------------

    def program_index(self) -> int:
        track = self.track
        if track is None:
            return 0
        for index, (program, _name) in enumerate(PROGRAMS):
            if program == track.program:
                return index
        return 0

    def cycle_program(self) -> int:
        track = self.track
        if track is None:
            return 0
        index = (self.program_index() + 1) % len(PROGRAMS)
        track.program = PROGRAMS[index][0]
        return index

    def adjust_volume(self, delta: float) -> float:
        track = self.track
        if track is None:
            return 1.0
        return self.set_volume(track.volume + delta)

    def set_volume(self, value: float) -> float:
        track = self.track
        if track is None:
            return 1.0
        track.volume = round(max(0.0, min(1.0, value)), 2)
        return track.volume

    def quantize_track(self, grid: float) -> int:
        """Snap the selected track's onsets; the project records the grid."""
        track = self.track
        if track is None or grid <= 0 or self._recording:
            return 0
        track.notes = quantize(track.notes, grid)
        self.project.quantize_grid = round(float(grid), 6)
        return len(track.notes)

    # -- persistence ------------------------------------------------------

    def load(self, path: Path | str) -> bool:
        path = Path(path)
        if not path.is_file():
            return False
        self.set_project(Project.load(path))
        return True

    def set_project(self, project: Project) -> None:
        self._recording = False
        self._recorder = None
        self.project = project
        self.track_index = 0
