"""Project model for the creative workspace (P5 slice).

A project is musical time (beats), not audio: tracks hold note events, and the
same model feeds the piano roll, playback, and MIDI export. Times are beats
from the project start so quantization and bar positions stay tempo-independent.

The JSON file is the user's work. Loading is tolerant: a corrupt or missing
file yields an empty project and unreadable notes are skipped, so one bad file
cannot block the app from opening.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_TRACKS = 8


def default_project_dir() -> Path:
    """The app-config ``projects`` folder, next to learning.json.

    QStandardPaths is imported lazily so the pure model tests never need a
    QApplication.
    """
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "projects"


@dataclass(frozen=True)
class NoteEvent:
    """One note on one track, in beats from the project start."""

    start: float
    midi: int
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "midi": self.midi,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, raw) -> "NoteEvent | None":
        if not isinstance(raw, dict):
            return None
        try:
            return cls(
                start=max(0.0, float(raw["start"])),
                midi=int(raw["midi"]),
                duration=max(0.0, float(raw["duration"])),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class LoopRegion:
    """A loop in project beats; ``end`` is exclusive."""

    start: float
    end: float

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, raw) -> "LoopRegion | None":
        if not isinstance(raw, dict):
            return None
        try:
            start = float(raw["start"])
            end = float(raw["end"])
        except (KeyError, TypeError, ValueError):
            return None
        return cls(start, end) if end > start else None


@dataclass(frozen=True)
class Layer:
    """A second timbre played by the same track (one key, two voices)."""

    program: int
    volume: float = 0.7
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "program": self.program,
            "volume": self.volume,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, raw) -> "Layer | None":
        if not isinstance(raw, dict):
            return None
        try:
            program = max(0, min(127, int(raw["program"])))
            volume = max(0.0, min(1.0, float(raw.get("volume", 0.7))))
        except (KeyError, TypeError, ValueError):
            return None
        return cls(program, volume, str(raw.get("name", "")))


@dataclass(frozen=True)
class SplitSpec:
    """Low/high keyboard zones played by different timbres."""

    midi: int = 60
    left_program: int = 32
    right_program: int = 0
    left_volume: float = 0.8
    right_volume: float = 0.8

    def to_dict(self) -> dict:
        return {
            "midi": self.midi,
            "left_program": self.left_program,
            "right_program": self.right_program,
            "left_volume": self.left_volume,
            "right_volume": self.right_volume,
        }

    @classmethod
    def from_dict(cls, raw) -> "SplitSpec | None":
        if not isinstance(raw, dict):
            return None
        try:
            midi = max(0, min(127, int(raw.get("midi", 60))))
            left_program = max(0, min(127, int(raw.get("left_program", 32))))
            right_program = max(0, min(127, int(raw.get("right_program", 0))))
            left_volume = max(
                0.0, min(1.0, float(raw.get("left_volume", 0.8)))
            )
            right_volume = max(
                0.0, min(1.0, float(raw.get("right_volume", 0.8)))
            )
        except (TypeError, ValueError):
            return None
        return cls(midi, left_program, right_program, left_volume, right_volume)


@dataclass
class Track:
    name: str
    program: int = 0
    volume: float = 1.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    layer: Layer | None = None
    split: SplitSpec | None = None
    notes: list[NoteEvent] = field(default_factory=list)

    def overdub(self, events: list[NoteEvent]) -> None:
        """Merge newly recorded events into this track, keeping the old ones."""
        self.notes.extend(events)
        self.notes.sort(key=lambda event: (event.start, event.midi))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "program": self.program,
            "volume": self.volume,
            "pan": self.pan,
            "mute": self.mute,
            "solo": self.solo,
            "layer": self.layer.to_dict() if self.layer is not None else None,
            "split": self.split.to_dict() if self.split is not None else None,
            "notes": [note.to_dict() for note in self.notes],
        }

    @classmethod
    def from_dict(cls, raw, index: int = 0) -> "Track":
        raw = raw if isinstance(raw, dict) else {}
        try:
            program = int(raw.get("program", 0))
        except (TypeError, ValueError):
            program = 0
        try:
            volume = float(raw.get("volume", 1.0))
        except (TypeError, ValueError):
            volume = 1.0
        try:
            pan = float(raw.get("pan", 0.0))
        except (TypeError, ValueError):
            pan = 0.0
        notes = []
        raw_notes = raw.get("notes", [])
        if isinstance(raw_notes, list):
            for item in raw_notes:
                note = NoteEvent.from_dict(item)
                if note is not None:
                    notes.append(note)
        return cls(
            name=str(raw.get("name", "")) or f"音轨 {index + 1}",
            program=program,
            volume=volume,
            pan=pan,
            mute=bool(raw.get("mute", False)),
            solo=bool(raw.get("solo", False)),
            layer=Layer.from_dict(raw.get("layer")),
            split=SplitSpec.from_dict(raw.get("split")),
            notes=notes,
        )


@dataclass
class Project:
    title: str = "未命名项目"
    tempo: float = 120.0
    time_signature: tuple[int, int] = (4, 4)
    tracks: list[Track] = field(default_factory=list)
    loop: LoopRegion | None = None
    version: int = 1
    visibility: str = "public"     # public | private
    public_release: str = "yes"    # yes | unknown | remove
    reverb: float = 0.0            # 0..1, project-wide spatial send
    exported: bool = False         # a MIDI file was produced from this take
    quantize_grid: float = 0.0     # beats; 0 = never quantized
    count_in_used: bool = False    # a take was started with the count-in bar
    metronome_used: bool = False   # a take was started with the click on

    def add_track(self, name: str = "") -> Track:
        if len(self.tracks) >= MAX_TRACKS:
            raise ValueError(f"一个项目最多 {MAX_TRACKS} 轨")
        track = Track(name=name or f"音轨 {len(self.tracks) + 1}")
        self.tracks.append(track)
        return track

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "title": self.title,
            "tempo": self.tempo,
            "time_signature": list(self.time_signature),
            "loop": self.loop.to_dict() if self.loop is not None else None,
            "tracks": [track.to_dict() for track in self.tracks],
            "visibility": self.visibility,
            "public_release": self.public_release,
            "reverb": self.reverb,
            "exported": self.exported,
            "quantize_grid": self.quantize_grid,
            "count_in_used": self.count_in_used,
            "metronome_used": self.metronome_used,
        }

    @classmethod
    def from_dict(cls, raw) -> "Project":
        project = cls()
        if not isinstance(raw, dict):
            return project

        title = str(raw.get("title", project.title))
        project.title = title or project.title
        try:
            tempo = float(raw.get("tempo", project.tempo))
        except (TypeError, ValueError):
            tempo = project.tempo
        project.tempo = tempo if tempo > 0 else 120.0

        signature = raw.get("time_signature")
        if isinstance(signature, (list, tuple)) and len(signature) == 2:
            try:
                beats, unit = int(signature[0]), int(signature[1])
            except (TypeError, ValueError):
                beats = unit = 0
            if beats > 0 and unit > 0:
                project.time_signature = (beats, unit)

        tracks = raw.get("tracks", [])
        if isinstance(tracks, list):
            project.tracks = [
                Track.from_dict(item, index) for index, item in enumerate(tracks)
            ][:MAX_TRACKS]
        project.loop = LoopRegion.from_dict(raw.get("loop"))
        try:
            project.version = int(raw.get("version", project.version))
        except (TypeError, ValueError):
            pass
        visibility = str(raw.get("visibility", project.visibility))
        project.visibility = visibility if visibility in ("public", "private") else "public"
        release = str(raw.get("public_release", project.public_release))
        project.public_release = (
            release if release in ("yes", "unknown", "remove") else "unknown"
        )
        try:
            reverb = float(raw.get("reverb", project.reverb))
        except (TypeError, ValueError):
            reverb = project.reverb
        project.reverb = max(0.0, min(1.0, reverb))
        project.exported = bool(raw.get("exported", project.exported))
        try:
            grid = float(raw.get("quantize_grid", project.quantize_grid))
        except (TypeError, ValueError):
            grid = project.quantize_grid
        project.quantize_grid = max(0.0, grid)
        project.count_in_used = bool(
            raw.get("count_in_used", project.count_in_used)
        )
        project.metronome_used = bool(
            raw.get("metronome_used", project.metronome_used)
        )
        return project

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | str) -> "Project":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(raw)
