"""Stage-7/8 project acceptance rules (no Qt, no UI).

A project task is the teaching content's step list made checkable against the
live Project model. Each step is a small, documented rule; the creation page
shows the same labels as a checklist, and the learning page records completion
only when every step passes.

These are deliberately narrow checks. They validate the musical shape the
stage teaches (a melody, a low second voice, a four-bar loop, a layered or
split timbre, a balanced mix), not notation, velocity, or audio quality.
"""

from __future__ import annotations

from dataclasses import dataclass

from .project import Project

C_MAJOR = {0, 2, 4, 5, 7, 9, 11}


def _audible(project: Project):
    """Tracks a mix would actually hear (mute/solo, same as export)."""
    solo = any(track.solo for track in project.tracks)
    return [
        track
        for track in project.tracks
        if not track.mute and (not solo or track.solo)
    ]


def _with_notes(project: Project):
    return [track for track in project.tracks if track.notes]


@dataclass(frozen=True)
class ProjectStep:
    label: str
    rule: str
    value: float = 1.0
    track: int = 0

    def _track(self, project: Project):
        if not 0 <= self.track < len(project.tracks):
            return None
        return project.tracks[self.track]

    def done(self, project: Project) -> bool:
        notes = [note for item in project.tracks for note in item.notes]
        if self.rule == "notes":
            return len(notes) >= int(self.value)
        if self.rule == "track_notes":
            track = self._track(project)
            return track is not None and len(track.notes) >= int(self.value)
        if self.rule == "tracks":
            return len(project.tracks) >= int(self.value)
        if self.rule == "all_tracks_notes":
            return bool(project.tracks) and all(
                len(track.notes) >= int(self.value) for track in project.tracks
            )
        if self.rule == "programs":
            used = {
                track.program for track in project.tracks if track.notes
            }
            return len(used) >= int(self.value)
        if self.rule == "c_major":
            return bool(notes) and all(note.midi % 12 in C_MAJOR for note in notes)
        if self.rule == "low_notes":
            track = self._track(project)
            return track is not None and (
                sum(1 for note in track.notes if note.midi <= 59)
                >= int(self.value)
            )
        if self.rule == "loop_bars":
            loop = project.loop
            if loop is None:
                return False
            return loop.length + 1e-6 >= self.value * project.time_signature[0]
        if self.rule == "notes_in_loop":
            loop = project.loop
            if loop is None or len(notes) < int(self.value):
                return False
            return all(
                note.start >= loop.start - 1e-6 and note.end <= loop.end + 1e-6
                for note in notes
            )
        if self.rule == "audible_tracks":
            return (
                len([track for track in _audible(project) if track.notes])
                >= int(self.value)
            )
        if self.rule == "layer":
            track = self._track(project)
            return track is not None and track.layer is not None
        if self.rule == "layer_distinct":
            track = self._track(project)
            return (
                track is not None
                and track.layer is not None
                and track.layer.program != track.program
            )
        if self.rule == "layer_program":
            track = self._track(project)
            return (
                track is not None
                and track.layer is not None
                and track.layer.program == int(self.value)
            )
        if self.rule == "layer_balance":
            track = self._track(project)
            return (
                track is not None
                and track.layer is not None
                and track.layer.volume <= track.volume + 1e-6
            )
        if self.rule == "split":
            track = self._track(project)
            return track is not None and track.split is not None
        if self.rule == "split_bass":
            track = self._track(project)
            return (
                track is not None
                and track.split is not None
                and track.split.left_program == 32
            )
        if self.rule == "split_sides":
            track = self._track(project)
            if track is None or track.split is None:
                return False
            low = sum(
                1 for note in track.notes if note.midi < track.split.midi
            )
            high = sum(
                1 for note in track.notes if note.midi >= track.split.midi
            )
            return low >= int(self.value) and high >= int(self.value)
        if self.rule == "distinct_volumes":
            volumes = [track.volume for track in _with_notes(project)]
            return (
                len(volumes) >= 2
                and max(volumes) - min(volumes) + 1e-6 >= self.value
            )
        if self.rule == "pan_spread":
            pans = [track.pan for track in _with_notes(project)]
            return (
                len(pans) >= 2
                and max(pans) - min(pans) + 1e-6 >= self.value
            )
        if self.rule == "reverb":
            return project.reverb + 1e-6 >= self.value
        if self.rule == "exported":
            return project.exported
        if self.rule == "quantized":
            return project.quantize_grid > 0
        if self.rule == "count_in":
            return project.count_in_used
        if self.rule == "metronome":
            return project.metronome_used
        if self.rule == "bars":
            beats = project.time_signature[0]
            last_bar = max(
                int(note.start // beats) + 1 for note in notes
            ) if notes else 0
            return last_bar >= int(self.value)
        if self.rule == "sections":
            section = 4 * project.time_signature[0]
            for index in range(int(self.value)):
                start = index * section
                end = start + section
                if not any(start <= note.start < end for note in notes):
                    return False
            return True
        return False


@dataclass(frozen=True)
class ProjectTask:
    name: str
    steps: tuple[ProjectStep, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(step.label for step in self.steps)

    def evaluate(self, project: Project) -> list[bool]:
        return [step.done(project) for step in self.steps]

    def done(self, project: Project) -> bool:
        return all(self.evaluate(project))


TASKS = {
    "stage6_record_review": ProjectTask(
        "录音自评",
        (
            ProjectStep("第一轨至少录下 8 个音", "track_notes", 8, 0),
            ProjectStep("录音至少覆盖 2 小节", "bars", 2),
        ),
    ),
    "stage7_melody": ProjectTask(
        "录一条旋律",
        (
            ProjectStep("第一轨至少录下 4 个音", "track_notes", 4, 0),
            ProjectStep("旋律只使用 C 大调自然音", "c_major"),
        ),
    ),
    "stage7_overdub_bass": ProjectTask(
        "叠录低音",
        (
            ProjectStep("第一轨已有至少 4 个音的旋律", "track_notes", 4, 0),
            ProjectStep("第二轨至少叠入 2 个低音（C4 以下）", "low_notes", 2, 1),
            ProjectStep("项目里有两轨", "tracks", 2),
        ),
    ),
    "stage7_loop_four_bars": ProjectTask(
        "循环 4 小节",
        (
            ProjectStep("把循环设为 4 小节", "loop_bars", 4),
            ProjectStep("循环区里至少录下 4 个音", "notes_in_loop", 4),
        ),
    ),
    "stage7_trio": ProjectTask(
        "三轨小作品",
        (
            ProjectStep("项目里至少有三轨", "tracks", 3),
            ProjectStep("每一轨至少 2 个音", "all_tracks_notes", 2),
            ProjectStep("至少使用 2 种不同音色", "programs", 2),
        ),
    ),
    "stage7_quantize": ProjectTask(
        "量化开/关对比",
        (
            ProjectStep("第一轨至少 4 个音", "track_notes", 4, 0),
            ProjectStep("点「量化 1/8」对齐音符", "quantized"),
        ),
    ),
    "stage7_count_in": ProjectTask(
        "预备拍 + 节拍器",
        (
            ProjectStep("第一轨至少录下 4 个音", "track_notes", 4, 0),
            ProjectStep("录音时打开预备拍", "count_in"),
            ProjectStep("录音时开着节拍器", "metronome"),
        ),
    ),
    "stage7_export": ProjectTask(
        "导出 MIDI",
        (
            ProjectStep("第一轨至少 4 个音", "track_notes", 4, 0),
            ProjectStep("点击「导出 MIDI」生成文件", "exported"),
        ),
    ),
    "stage7_melody_accompaniment": ProjectTask(
        "8 小节旋律 + 伴奏",
        (
            ProjectStep("项目里至少两轨", "tracks", 2),
            ProjectStep("旋律轨至少 8 个音", "track_notes", 8, 0),
            ProjectStep("伴奏轨至少 4 个音", "track_notes", 4, 1),
            ProjectStep("至少使用 2 种音色", "programs", 2),
            ProjectStep("旋律至少铺满 8 小节", "bars", 8),
        ),
    ),
    "stage7_aaba": ProjectTask(
        "16 小节 AABA",
        (
            ProjectStep("全曲至少 16 小节", "bars", 16),
            ProjectStep("四个 4 小节段落都有音符", "sections", 4),
            ProjectStep("旋律轨至少 12 个音", "track_notes", 12, 0),
            ProjectStep("项目里至少两轨", "tracks", 2),
        ),
    ),
    "stage7_loop_piece": ProjectTask(
        "循环小曲",
        (
            ProjectStep("把循环设为 4 小节", "loop_bars", 4),
            ProjectStep("循环区里至少 8 个音", "notes_in_loop", 8),
            ProjectStep("项目里至少两轨", "tracks", 2),
        ),
    ),
    "stage7_final": ProjectTask(
        "完整小曲录制 + 导出",
        (
            ProjectStep("项目里至少两轨", "tracks", 2),
            ProjectStep("每一轨至少 8 个音", "all_tracks_notes", 8),
            ProjectStep("导出 MIDI 后再检查", "exported"),
        ),
    ),
    "stage8_layer": ProjectTask(
        "双层音色",
        (
            ProjectStep("第一轨至少 4 个音", "track_notes", 4, 0),
            ProjectStep("给第一轨打开音色叠加", "layer", 1, 0),
            ProjectStep("叠加音色与主音色不同", "layer_distinct", 1, 0),
            ProjectStep("叠加音量不超过主音色", "layer_balance", 1, 0),
        ),
    ),
    "stage8_split": ProjectTask(
        "左右分区",
        (
            ProjectStep("给第一轨打开键盘分区", "split", 1, 0),
            ProjectStep("低音区与高音区都有音符", "split_sides", 1, 0),
            ProjectStep("低音区使用贝斯音色", "split_bass", 1, 0),
        ),
    ),
    "stage8_three_tracks": ProjectTask(
        "三轨编配",
        (
            ProjectStep("项目里至少有三轨", "tracks", 3),
            ProjectStep("每一轨至少 2 个音", "all_tracks_notes", 2),
            ProjectStep("至少使用 3 种不同音色", "programs", 3),
        ),
    ),
    "stage8_mix": ProjectTask(
        "音量与声像",
        (
            ProjectStep("至少两轨有音符", "audible_tracks", 2),
            ProjectStep("两轨音量不同（伴奏更轻）", "distinct_volumes", 0.05),
            ProjectStep("左右声像拉开至少 30", "pan_spread", 0.3),
        ),
    ),
    "stage8_reverb": ProjectTask(
        "混响空间",
        (
            ProjectStep("第一轨至少 4 个音", "track_notes", 4, 0),
            ProjectStep("把混响调到至少 30%", "reverb", 0.3),
        ),
    ),
    "stage8_export": ProjectTask(
        "导出项目",
        (
            ProjectStep("至少两轨有音符", "audible_tracks", 2),
            ProjectStep("点击「导出 MIDI」生成文件", "exported"),
            ProjectStep("项目里至少有 8 个音", "notes", 8),
        ),
    ),
    "stage8_piano_strings": ProjectTask(
        "钢琴 + 弦乐分层",
        (
            ProjectStep("钢琴轨至少 4 个音", "track_notes", 4, 0),
            ProjectStep("钢琴轨叠加弦乐音色", "layer_program", 48, 0),
            ProjectStep("叠加音量低于钢琴", "layer_balance", 1, 0),
            ProjectStep("弦乐轨至少 4 个音", "track_notes", 4, 1),
            ProjectStep("项目里至少两轨", "tracks", 2),
        ),
    ),
    "stage8_split_hands": ProjectTask(
        "左手贝斯 + 右手钢琴",
        (
            ProjectStep("给第一轨打开键盘分区", "split", 1, 0),
            ProjectStep("分区两侧各至少 2 个音", "split_sides", 2, 0),
            ProjectStep("低音区使用贝斯音色", "split_bass", 1, 0),
            ProjectStep("整个项目至少 8 个音", "track_notes", 8, 0),
        ),
    ),
    "stage8_trio": ProjectTask(
        "三轨小曲",
        (
            ProjectStep("项目里至少有三轨", "tracks", 3),
            ProjectStep("每一轨至少 4 个音", "all_tracks_notes", 4),
            ProjectStep("至少使用 3 种不同音色", "programs", 3),
            ProjectStep("音轨音量有层次", "distinct_volumes", 0.05),
            ProjectStep("左右声像拉开至少 30", "pan_spread", 0.3),
            ProjectStep("导出 MIDI 后再检查", "exported"),
        ),
    ),
}
