"""The 9-stage learning path: content data, not UI.

Only items with a real asset are marked ready: a MusicXML/MIDI score for
follow-along practice, or a generated drill spec for in-app training.
Everything else stays "制作中" and is never offered as a practice — the design
rule is that unready content does not pretend to be playable.

Public-domain content is wired in two batches: 小星星 (stage 0/3), 两只老虎 /
伦敦桥 / 小蜜蜂 (stage 0), 欢乐颂 / 铃儿响叮当 (stage 3), 卡农片段 / 送别
(stage 4), and 欢乐颂 · 双手版 (stage 5, two voices in one 32-key window).
Every score asset also has a same-stem MIDI for the demo/fallback. Stage 1's
note-name flashcard is the first generated drill.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path, PurePath

from .drill import drill_spec
from .lesson import Guide, overlay_lessons
from .mapping import MappingSpec, mapping_spec, split_mapping
from .project import Project
from .project_task import TASKS, ProjectTask

SCORE_DIR = Path(__file__).resolve().parents[2] / "resources" / "scores"
PROJECT_DIR = Path(__file__).resolve().parents[2] / "resources" / "projects"
LESSON_DIR = Path(__file__).resolve().parents[2] / "resources" / "lessons"

SAMPLE_SCORE = "xiaoxingxing.musicxml"


@dataclass(frozen=True)
class ProjectTemplate:
    name: str
    project: str


CREATION_TEMPLATES = (
    ProjectTemplate("钢琴独奏", "template_piano_solo"),
    ProjectTemplate("旋律 + 伴奏", "template_melody_accompaniment"),
    ProjectTemplate("左手贝斯 + 右手钢琴", "template_bass_piano"),
    ProjectTemplate("弦乐铺底", "template_strings"),
)


@lru_cache(maxsize=128)
def _score_ready(name: str) -> bool:
    """True only when the score parses, or a same-stem MIDI does.

    Readiness is not just "the string is not None": a renamed, deleted or
    corrupt asset must not keep showing 去练习. The library's MusicXML->MIDI
    fallback is mirrored here.
    """
    path = SCORE_DIR / name
    candidates = [path]
    if path.suffix.lower() in (".musicxml", ".mxl", ".xml"):
        candidates.extend(
            [path.with_suffix(".mid"), path.with_suffix(".midi")]
        )
    from .score import parse_score

    for candidate in candidates:
        try:
            if not candidate.is_file():
                continue
            parse_score(candidate)
            return True
        except Exception:
            continue
    return False


@lru_cache(maxsize=64)
def _project_ready(name: str) -> bool:
    """True only when the project template loads with a usable track.

    ``Project.load`` is tolerant and returns an empty project for a corrupt
    file, so file existence alone must never mark an item ready.
    """
    path = PROJECT_DIR / f"{name}.json"
    if not path.is_file():
        return False
    project = Project.load(path)
    return bool(project.tracks) and project.tempo > 0 and project.time_signature[0] > 0


@dataclass(frozen=True)
class PracticeItem:
    name: str
    meta: str
    score: str | None = None
    drill: str | None = None
    project: str | None = None
    task: ProjectTask | None = None
    # MusicXML part id the synth plays automatically (H7e); the learner plays
    # every other part. Empty means "practice the whole score".
    accompaniment: str = ""
    # Mapping applied for this item's practice and restored when the session
    # ends (H7f). A preset key string or a structured MappingSpec; empty means
    # "keep the user's mapping".
    mapping: str | MappingSpec = ""
    visibility: str = "public"  # public | private (private never enters a public build)

    @property
    def ready(self) -> bool:
        if self.score is not None:
            return _score_ready(self.score)
        if self.project is not None:
            # The task is part of the content: a template without acceptance
            # steps would open a blank page with no way to finish.
            return self.task is not None and _project_ready(self.project)
        # A typo'd drill id must not make an item look playable.
        return self.drill is not None and drill_spec(self.drill) is not None


@dataclass(frozen=True)
class Stage:
    index: int
    name: str
    band: str
    goal: str
    prereq: str
    guides: tuple[Guide, ...]
    trainings: tuple[PracticeItem, ...]
    pieces: tuple[PracticeItem, ...]
    pass_rule: str
    next_step: str

    @property
    def items(self) -> tuple[PracticeItem, ...]:
        return self.trainings + self.pieces

    @property
    def ready_items(self) -> tuple[PracticeItem, ...]:
        return tuple(item for item in self.items if item.ready)

    @property
    def ready_count(self) -> int:
        return len(self.ready_items)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def status(self) -> str:
        """wip | partial | ready — derived from real assets, never faked."""
        if self.ready_count == 0:
            return "wip"
        if self.ready_count == self.total_count:
            return "ready"
        return "partial"

    def first_practice(self) -> PracticeItem | None:
        items = self.ready_items
        return items[0] if items else None


BANDS = ("基础", "演奏", "创作")

STAGES: tuple[Stage, ...] = (
    Stage(
        index=0,
        name="上手",
        band="基础",
        goal="认识 32 条光条、电脑键位与延音，弹出第一段旋律。",
        prereq="无",
        guides=(
            Guide(
                "认识 32 条光条",
                3,
                (
                    "32 条槽从左到右 = 音高从低到高。",
                    "底部光条只在按下时发亮；点击不会发声。",
                ),
            ),
            Guide(
                "电脑键位与延音",
                3,
                (
                    "三行键位：Z X C… / A S D… / Q W E…。",
                    "Tab 显示键帽；按住 Shift 延音。",
                ),
            ),
            Guide(
                "弹出第一段旋律",
                3,
                (
                    "从中央 C 开始，慢速按 C–D–E。",
                    "听清每个音，再连起来。",
                ),
            ),
        ),
        trainings=(
            PracticeItem("跟弹《小星星》第一句", "跟弹 · 5 分钟 · 已就绪", SAMPLE_SCORE),
            PracticeItem(
                "找到中央 C",
                "上手 · 4 步 · 已就绪",
                drill="onboarding_middle_c",
            ),
            PracticeItem(
                "延音与全部静音",
                "上手 · 3 步 · 已就绪",
                drill="onboarding_sustain_panic",
            ),
        ),
        pieces=(
            PracticeItem("两只老虎", "★ · 已就绪", "two_tigers.musicxml"),
            PracticeItem("伦敦桥", "★ · 已就绪", "london_bridge.musicxml"),
            PracticeItem("小蜜蜂", "★ · 已就绪", "lightly_row.musicxml"),
            PracticeItem(
                "玛丽有只小羊羔",
                "★ · 已就绪",
                "mary_had_a_little_lamb.musicxml",
            ),
            PracticeItem(
                "老麦克唐纳", "★ · 已就绪", "old_macdonald.musicxml"
            ),
        ),
        pass_rule=(
            "完整跟弹《小星星》第一句或任一入门曲（两只老虎 / 伦敦桥 / "
            "小蜜蜂 / 玛丽有只小羊羔 / 老麦克唐纳），并完成「找到中央 C」与"
            "「延音与全部静音」——知道 Shift 延音和 Esc 全部静音在哪里。"
        ),
        next_step="阶段 1 · 五线谱与音名",
    ),
    Stage(
        index=1,
        name="五线谱与音名",
        band="基础",
        goal="先读出 C4–C5 的音名，再扩到 C4–C6；认识谱号、线间、八度与临时记号。",
        prereq="阶段 0 · 上手",
        guides=(
            Guide("五线谱是什么", 4, ("五条线、四个间，从下往上数。", "谱号决定音名。")),
            Guide(
                "高音谱号",
                5,
                ("五线 E G B D F；四间 F A C E。", "C4 在下方第一条加线。"),
            ),
            Guide(
                "音名与八度",
                5,
                ("音名按 C–B 循环。", "C5 是 C4 的高八度，频率 ×2。"),
            ),
            Guide(
                "低音谱号",
                5,
                ("低音谱表五线 G B D F A。", "C4 在上方第一条加线。"),
            ),
            Guide(
                "临时记号与调号",
                6,
                ("♯ 升、♭ 降、♮ 还原。", "临时记号只在本小节有效。"),
            ),
            Guide(
                "音程与视奏",
                6,
                ("二度相邻，三度隔一个音级。", "视奏先慢后快，错音不停。"),
            ),
        ),
        trainings=(
            PracticeItem(
                "音名闪卡 · C4–C5",
                "识谱 · 10 题 · 已就绪",
                drill="note_names_c4_c5",
            ),
            PracticeItem(
                "线间定位 · 高音谱号",
                "识谱 · C4–C6 · 已就绪",
                drill="note_names_c4_c6",
            ),
            PracticeItem(
                "八度上下行",
                "识谱 · 八度对应 · 已就绪",
                drill="octave_names_c4_c6",
            ),
            PracticeItem(
                "临时记号 · 升与降",
                "识谱 · ♯/♭ · 已就绪",
                drill="note_accidentals_c4_c5",
            ),
            PracticeItem(
                "低音谱号 · C3–C4",
                "识谱 · 低音谱号 · 已就绪",
                drill="note_names_bass_c3_c4",
            ),
        ),
        pieces=(),
        pass_rule=(
            "完成五条识谱训练（C4–C5、线间定位 C4–C6、八度上下行、升与降、"
            "低音谱号 C3–C4），每条 10 题全部答对；错按会重试并计入准确率。"
            "首次答对 ≥8 题是推荐目标；学习页另有可选的阶段 1 考核"
            "（20 音首答 ≥80%），不阻止普通练习完成。"
        ),
        next_step="阶段 2 · 节奏与拍号",
    ),
    Stage(
        index=2,
        name="节奏与拍号",
        band="基础",
        goal="跟节拍器拍出 4/4 与 3/4，认识时值、休止与附点；当前训练覆盖四分/二分、八分、3/4、休止与附点。",
        prereq="阶段 1 · 五线谱与音名",
        guides=(
            Guide(
                "拍与音符时值",
                4,
                ("4/4 每小节四拍。", "全 4、二分 2、四分 1、八分半拍。"),
            ),
            Guide(
                "休止符与附点",
                5,
                ("休止也占拍。", "附点延长一半。"),
            ),
            Guide(
                "2/4、3/4、4/4",
                5,
                ("上面是每小节拍数。", "3/4 强弱弱。"),
            ),
            Guide(
                "6/8 与弱起",
                6,
                ("6/8 是两组三拍。", "弱起从第一拍之前开始。"),
            ),
            Guide(
                "切分与三连音",
                6,
                ("重音移到弱拍。", "三连音三音代两音。"),
            ),
            Guide(
                "跟节拍器弹",
                5,
                ("60 → 80 → 100 BPM。", "先听一小节预备拍。"),
            ),
        ),
        trainings=(
            PracticeItem(
                "四分与二分 · 4/4",
                "节奏 · 4/4 · 已就绪",
                drill="rhythm_quarters_halves_4_4",
            ),
            PracticeItem(
                "八分音符组合",
                "节奏 · 4/4 八分 · 已就绪",
                drill="rhythm_eighths_4_4",
            ),
            PracticeItem(
                "休止与附点",
                "节奏 · 4/4 休止/附点 · 已就绪",
                drill="rhythm_rests_dots_4_4",
            ),
            PracticeItem(
                "3/4 圆舞曲型",
                "节奏 · 3/4 · 已就绪",
                drill="rhythm_waltz_3_4",
            ),
            PracticeItem(
                "6/8 复拍子",
                "节奏 · 6/8 两组三拍 · 已就绪",
                drill="rhythm_six_eight",
            ),
            PracticeItem(
                "切分节奏",
                "节奏 · 4/4 弱拍重音 · 已就绪",
                drill="rhythm_syncopation_4_4",
            ),
            PracticeItem(
                "三连音",
                "节奏 · 4/4 每拍三音 · 已就绪",
                drill="rhythm_triplets_4_4",
            ),
        ),
        pieces=(),
        pass_rule=(
            "完成四分/二分、八分、3/4 圆舞曲、休止/附点、6/8 复拍子、"
            "切分节奏与三连音七条节奏训练；每条至少完整踩准一次，"
            "漏拍与多按计入准确率。学习页另有可选的阶段 2 考核"
            "（60 BPM、平均偏差 <60 ms），不阻止普通练习完成。"
        ),
        next_step="阶段 3 · 右手旋律",
    ),
    Stage(
        index=3,
        name="右手旋律",
        band="演奏",
        goal="在 C 大调五指位置弹 8 小节旋律，认识音程、连奏与乐句。",
        prereq="阶段 2 · 节奏与拍号",
        guides=(
            Guide("五指位置 C", 4, ("1–5 指对应 C–G。", "手腕放松，手指立起来。")),
            Guide("五指位置 G/F", 4, ("整只手平移，手型不变。", "先找 1 指位置。")),
            Guide("C 大调音阶", 5, ("C 大调没有升降号。", "上行穿指，下行跨指。")),
            Guide("连奏与断奏", 5, ("连奏音与音不断开。", "断奏短促、有间隙。")),
            Guide("音程与跳进", 5, ("三度隔一个音级。", "跳进整只手移动。")),
            Guide("乐句与呼吸", 6, ("4 小节一句。", "句尾收，句头进。")),
            Guide("音域映射与移调", 6, ("映射决定键位对应的音。", "移调不改键位关系。")),
            Guide("视奏与完整曲", 6, ("先分段，再完整。", "错音不停。")),
        ),
        trainings=(
            PracticeItem(
                "五指位置 · C–G",
                "跟弹 · 《小星星》片段 · 已就绪",
                SAMPLE_SCORE,
            ),
            PracticeItem(
                "五指位置 · G/F",
                "跟弹 · 8 小节 · G/F 两个位置 · 已就绪",
                score="five_finger_gf_8bars.musicxml",
            ),
            PracticeItem(
                "C 大调音阶上下行",
                "跟弹 · 8 小节 · 已就绪",
                score="scale_c_major_updown.musicxml",
            ),
            PracticeItem(
                "二度与三度音程",
                "跟弹 · 8 小节 · 已就绪",
                score="intervals_seconds_thirds.musicxml",
            ),
            PracticeItem(
                "连奏与断奏对比",
                "跟弹 · 8 小节 · 已就绪",
                score="legato_staccato.musicxml",
            ),
        ),
        pieces=(
            PracticeItem("小星星（片段）", "★ · 已就绪", SAMPLE_SCORE),
            PracticeItem("欢乐颂", "★ · 已就绪", "ode_to_joy.musicxml"),
            PracticeItem("铃儿响叮当", "★★ · 已就绪", "jingle_bells.musicxml"),
            PracticeItem(
                "友谊地久天长", "★★ · 已就绪", "auld_lang_syne.musicxml"
            ),
            PracticeItem(
                "勃拉姆斯摇篮曲", "★★ · 已就绪", "brahms_lullaby.musicxml"
            ),
        ),
        pass_rule=(
            "完成 G/F 五指位置、C 大调音阶、二度/三度、连奏/断奏四条训练，"
            "并完整跟弹 1 首 ★ 曲目（《小星星（片段）》《欢乐颂》"
            "《铃儿响叮当》《友谊地久天长》《勃拉姆斯摇篮曲》）。"
        ),
        next_step="阶段 4 · 左手与和弦",
    ),
    Stage(
        index=4,
        name="左手与和弦",
        band="演奏",
        goal="认识低音谱号，用 I–IV–V 与分解和弦给右手配简单伴奏。",
        prereq="阶段 3 · 右手旋律",
        guides=(
            Guide("低音谱号与左手位置", 5, ("C3 在第二间。", "左手 1 指在右侧。")),
            Guide("大三和弦", 5, ("根音、三音、五音。", "C–E–G。")),
            Guide("I–IV–V", 6, ("C、F、G 三个正三和弦。", "转换找共同音。")),
            Guide("根音+五度", 5, ("空五度没有三音。", "低音留白。")),
            Guide("分解和弦", 6, ("1-5-8-5 / 1-3-5-3。", "手腕带动。")),
            Guide("3/4 华尔兹", 6, ("低音–和弦–和弦。", "强弱弱。")),
            Guide("4/4 进行曲", 5, ("低音–和弦–低音–和弦。", "速度稳定。")),
            Guide("左手与旋律的配合", 6, ("先分手，再合手。", "旋律稍突出。")),
        ),
        trainings=(
            PracticeItem(
                "低音谱号 · C3–C4",
                "识谱 · C3–C4 · 已就绪",
                drill="note_names_bass_c3_c4",
            ),
            PracticeItem(
                "C–F–G 和弦",
                "跟弹 · 8 小节 · 已就绪",
                score="chords_cfg.musicxml",
            ),
            PracticeItem(
                "分解和弦 · 4/4",
                "跟弹 · 8 小节 · 已就绪",
                score="arpeggio_4_4.musicxml",
            ),
            PracticeItem(
                "3/4 华尔兹 · 左手",
                "跟弹 · 低音–和弦–和弦 · 已就绪",
                score="minuet_3_4.musicxml",
            ),
        ),
        pieces=(
            PracticeItem("卡农片段 · 简易版", "★★ · 已就绪", "canon_easy.musicxml"),
            PracticeItem("送别", "★★ · 已就绪", "farewell.musicxml"),
        ),
        pass_rule=(
            "完成低音谱号、C–F–G 和弦、分解和弦与 3/4 华尔兹左手四条训练，"
            "并完整跟弹 1 首 ★★ 曲目（《卡农片段 · 简易版》《送别》）。"
        ),
        next_step="阶段 5 · 双手合奏",
    ),
    Stage(
        index=5,
        name="双手合奏",
        band="演奏",
        goal="把分手练习合成双手；本版双手曲在一个 32 键窗口内弹旋律与伴奏，更宽音域再启用分区映射。",
        prereq="阶段 4 · 左手与和弦",
        guides=(
            Guide("分手复习", 4, ("左右手各自稳定。", "先分手，再合手。")),
            Guide("双手同音/八度", 5, ("对齐每一拍。", "八度是同音的高八度。")),
            Guide("右手旋律 + 左手长音", 5, ("左手只按长音。", "先慢速对齐。")),
            Guide("右手旋律 + 左手和弦", 6, ("左手和弦要整齐。", "旋律稍突出。")),
            Guide("左右手分区", 6, ("低音区左手，高音区右手。", "分区映射按 16 键切。")),
            Guide("反向/平行进行", 6, ("平行同向，反向相反。", "先慢速找方向。")),
            Guide("困难小节循环", 5, ("只练 1–2 小节。", "循环到稳定再连。")),
            Guide("完整双手演奏", 6, ("分段练熟再完整。", "错音不停。")),
        ),
        trainings=(
            PracticeItem(
                "左右分区 · 8 小节",
                "合手 · 左右分区 · 已就绪",
                score="split_hands_8bars.musicxml",
                mapping=split_mapping(16, 48, 72, label="左右分区"),
            ),
            PracticeItem(
                "慢速合手 · 50%",
                "合手 · 40 BPM · 已就绪",
                score="ode_to_joy_both_slow.musicxml",
            ),
            PracticeItem(
                "固定伴奏型",
                "合手 · 固定伴奏 · 已就绪",
                score="fixed_accompaniment.musicxml",
            ),
            PracticeItem(
                "小星星 · 自动左手",
                "右手跟弹 · 左手自动伴奏 · 已就绪",
                score="twinkle_auto_accompaniment.musicxml",
                accompaniment="P2",
            ),
            PracticeItem(
                "反向与平行 · 8 小节",
                "合手 · 同向/反向 · 已就绪",
                score="contrary_parallel_8bars.musicxml",
            ),
            PracticeItem(
                "困难小节循环 · 小步舞曲",
                "合手 · 选 1–2 小节循环 · 已就绪",
                score="minuet_3_4.musicxml",
            ),
        ),
        pieces=(
            PracticeItem(
                "欢乐颂 · 双手版", "★★ · 已就绪", "ode_to_joy_both.musicxml"
            ),
            PracticeItem(
                "欢乐颂 · 自动左手",
                "★ · 右手跟弹 · 左手自动伴奏",
                score="ode_auto_accompaniment.musicxml",
                accompaniment="P2",
            ),
            PracticeItem(
                "两只老虎 · 自动左手",
                "★ · 右手跟弹 · 左手自动伴奏",
                score="two_tigers_auto_accompaniment.musicxml",
                accompaniment="P2",
            ),
            PracticeItem("小步舞曲", "★★★ · 已就绪", "minuet_3_4.musicxml"),
        ),
        pass_rule=(
            "完成左右分区、慢速合手、固定伴奏、自动左手、反向/平行与困难小节"
            "循环六条训练，完整跟弹 2 首自动左手曲目（《欢乐颂 · 自动左手》"
            "《两只老虎 · 自动左手》）与 1 首双手曲"
            "（《欢乐颂 · 双手版》《小步舞曲》）。"
        ),
        next_step="阶段 6 · 表现与完整曲目",
    ),
    Stage(
        index=6,
        name="表现与完整曲目",
        band="演奏",
        goal="用速度、时长/连奏、乐句与延音把一首曲子弹完整、弹好听。",
        prereq="阶段 5 · 双手合奏",
        guides=(
            Guide("速度与稳定", 5, ("50→100% 分档。", "稳定优先，不追速。")),
            Guide("乐句与呼吸", 5, ("4/8 小节一句。", "句尾收，句头进。")),
            Guide("连奏/断奏/重音", 5, ("三种奏法可切换。", "重音不砸键。")),
            Guide("延音踏板", 5, ("换和弦时换踏板。", "不要一直踩。")),
            Guide("弱起、收尾、反复", 5, ("弱起不抢拍。", "收尾收干净。")),
            Guide("完整曲目分段", 6, ("分段练，再连。", "困难段单独循环。")),
            Guide("录音与自评", 6, ("录一遍不回改。", "先听节奏再听错音。")),
        ),
        trainings=(
            PracticeItem(
                "乐句起落",
                "表现 · 8 小节 · 已就绪",
                score="phrasing_8bars.musicxml",
            ),
            PracticeItem(
                "速度阶梯 60→100%",
                "表现 · 当前谱面 60 BPM · 已就绪",
                score="tempo_ladder_60.musicxml",
            ),
            PracticeItem(
                "连奏/断奏/重音",
                "表现 · 8 小节 · 连奏与断奏 · 已就绪",
                score="legato_staccato.musicxml",
            ),
            PracticeItem(
                "延音踏板 · 和弦转换",
                "表现 · 8 小节 · 每小节换延音 · 已就绪",
                score="fixed_accompaniment.musicxml",
            ),
            PracticeItem(
                "弱起与反复 · 8 小节",
                "表现 · 弱起进入 · 反复段落 · 已就绪",
                score="pickup_repeat_8bars.musicxml",
            ),
            PracticeItem(
                "录音自评",
                "项目 · 录一遍并回放 · 已就绪",
                project="stage6_record_review",
                task=TASKS["stage6_record_review"],
            ),
        ),
        pieces=(
            PracticeItem(
                "致爱丽丝 · 主题",
                "★★★ · 已就绪",
                score="fur_elise_theme.musicxml",
            ),
            PracticeItem(
                "梦中的婚礼 · 片段",
                "★★★ · 私有 · 已就绪",
                score="mariage_fragment.musicxml",
                visibility="private",
            ),
        ),
        pass_rule=(
            "完成乐句起落、速度阶梯、连奏/断奏/重音、延音踏板、弱起与反复、"
            "录音自评六条训练，并完整跟弹 1 首 ★★★ 曲目。"
        ),
        next_step="阶段 7 · 录音与编曲",
    ),
    Stage(
        index=7,
        name="录音与编曲",
        band="创作",
        goal="录下自己的演奏，叠录第二声部，用循环和量化做一个小作品。",
        prereq="阶段 6 · 表现与完整曲目",
        guides=(
            Guide("录音基础", 5, ("先开节拍器/预备拍。", "录音记录音符，不是音频。")),
            Guide("叠录", 5, ("在已有轨上继续录。", "叠录不覆盖旧音符。")),
            Guide("循环与量化", 6, ("4 小节循环。", "量化只改时间。")),
            Guide("音色与音量", 5, ("每轨独立音色。", "音量/声像决定位置。")),
            Guide("结构", 6, ("8 小节 / AABA。", "重复与对比。")),
            Guide("保存/导出", 5, ("项目 JSON + MIDI。", "导出前检查静音/独奏。")),
        ),
        trainings=(
            PracticeItem(
                "录一条旋律",
                "项目 · 已就绪",
                project="stage7_melody",
                task=TASKS["stage7_melody"],
            ),
            PracticeItem(
                "叠录低音",
                "项目 · 已就绪",
                project="stage7_overdub_bass",
                task=TASKS["stage7_overdub_bass"],
            ),
            PracticeItem(
                "量化开/关对比",
                "项目 · 已就绪",
                project="stage7_quantize",
                task=TASKS["stage7_quantize"],
            ),
            PracticeItem(
                "循环 4 小节",
                "项目 · 已就绪",
                project="stage7_loop_four_bars",
                task=TASKS["stage7_loop_four_bars"],
            ),
            PracticeItem(
                "预备拍 + 节拍器",
                "项目 · 已就绪",
                project="stage7_count_in",
                task=TASKS["stage7_count_in"],
            ),
            PracticeItem(
                "导出 MIDI",
                "项目 · 已就绪",
                project="stage7_export",
                task=TASKS["stage7_export"],
            ),
        ),
        pieces=(
            PracticeItem(
                "三轨小作品",
                "项目 · 已就绪",
                project="stage7_trio",
                task=TASKS["stage7_trio"],
            ),
            PracticeItem(
                "8 小节旋律 + 伴奏",
                "项目 · 已就绪",
                project="stage7_melody_accompaniment",
                task=TASKS["stage7_melody_accompaniment"],
            ),
            PracticeItem(
                "16 小节 AABA",
                "项目 · 已就绪",
                project="stage7_aaba",
                task=TASKS["stage7_aaba"],
            ),
            PracticeItem(
                "循环小曲",
                "项目 · 已就绪",
                project="stage7_loop_piece",
                task=TASKS["stage7_loop_piece"],
            ),
            PracticeItem(
                "完整小曲录制 + 导出",
                "项目 · 已就绪",
                project="stage7_final",
                task=TASKS["stage7_final"],
            ),
        ),
        pass_rule=(
            "完成 3 个以上项目（每个至少两轨），导出 MIDI 并能在外部播放；"
            "能解释量化对演奏感的影响。"
        ),
        next_step="阶段 8 · 多乐器合成",
    ),
    Stage(
        index=8,
        name="多乐器合成",
        band="创作",
        goal="叠加音色、划分音区，做出一个多乐器的完整小作品。",
        prereq="阶段 7 · 录音与编曲",
        guides=(
            Guide("音色叠加", 5, ("同一条轨两个音色。", "注意音量平衡。")),
            Guide("键盘分区", 5, ("低区/高区不同音色。", "分区不是叠加。")),
            Guide("三轨编配", 6, ("旋律/和声/低音。", "每轨只做一件事。")),
            Guide("混音基础", 5, ("先平衡，再声像/混响。", "混响不要太多。")),
            Guide("导出与复盘", 5, ("检查静音/独奏。", "复盘只记 1–2 点。")),
        ),
        trainings=(
            PracticeItem(
                "双层音色",
                "项目 · 已就绪",
                project="stage8_layer",
                task=TASKS["stage8_layer"],
            ),
            PracticeItem(
                "左右分区",
                "项目 · 已就绪",
                project="stage8_split",
                task=TASKS["stage8_split"],
            ),
            PracticeItem(
                "三轨编配",
                "项目 · 已就绪",
                project="stage8_three_tracks",
                task=TASKS["stage8_three_tracks"],
            ),
            PracticeItem(
                "音量与声像",
                "项目 · 已就绪",
                project="stage8_mix",
                task=TASKS["stage8_mix"],
            ),
            PracticeItem(
                "混响空间",
                "项目 · 已就绪",
                project="stage8_reverb",
                task=TASKS["stage8_reverb"],
            ),
            PracticeItem(
                "导出项目",
                "项目 · 已就绪",
                project="stage8_export",
                task=TASKS["stage8_export"],
            ),
        ),
        pieces=(
            PracticeItem(
                "钢琴 + 弦乐分层",
                "项目 · 已就绪",
                project="stage8_piano_strings",
                task=TASKS["stage8_piano_strings"],
            ),
            PracticeItem(
                "左手贝斯 + 右手钢琴",
                "项目 · 已就绪",
                project="stage8_split_hands",
                task=TASKS["stage8_split_hands"],
            ),
            PracticeItem(
                "三轨小曲",
                "项目 · 已就绪",
                project="stage8_trio",
                task=TASKS["stage8_trio"],
            ),
        ),
        pass_rule=(
            "完成 3 个项目（至少 2 个有三轨），音量/声像平衡并导出 MIDI；"
            "能解释音色叠加与键盘分区的区别。"
        ),
        next_step="曲谱库 · 挑一首完整曲目",
    ),
)


# Lesson JSON overrides the hardcoded guide summaries. A missing or broken
# file leaves the placeholder guide in place; content batches can therefore
# land one lesson at a time without touching the stage table.
STAGES = tuple(
    replace(
        stage,
        guides=overlay_lessons(stage.index, stage.guides, LESSON_DIR),
    )
    for stage in STAGES
)


def stage_by_index(index: int) -> Stage:
    return STAGES[max(0, min(index, len(STAGES) - 1))]


_LESSON_REF = re.compile(r"s(\d+)-l(\d+)")
_STAGE_REF = re.compile(r"s(\d+)")


def lesson_ref_label(ref: str) -> str:
    """Turn a lesson/stage id into a human title; unknown refs stay as-is."""
    text = (ref or "").strip()
    match = _LESSON_REF.fullmatch(text)
    if match is not None:
        stage_index = int(match.group(1))
        lesson_index = int(match.group(2))
        if 0 <= stage_index < len(STAGES):
            stage = STAGES[stage_index]
            if 1 <= lesson_index <= len(stage.guides):
                return stage.guides[lesson_index - 1].title
        return text
    match = _STAGE_REF.fullmatch(text)
    if match is not None:
        stage_index = int(match.group(1))
        if 0 <= stage_index < len(STAGES):
            return STAGES[stage_index].name
    return text


def project_path(name: str | None) -> Path | None:
    """Resolve a project template name to its JSON file, if it exists."""
    if not name:
        return None
    path = PROJECT_DIR / f"{name}.json"
    return path if path.is_file() else None


def score_path(name: str | None) -> Path | None:
    if not name:
        return None
    path = SCORE_DIR / name
    return path if path.exists() else None


def mapping_for_refs(refs) -> str | MappingSpec:
    """First non-empty mapping declared by the curriculum items in refs.

    `refs` are library StageRef values (duck-typed: stage_index/item_name) so
    this module does not depend on the library.
    """
    for ref in refs:
        index = getattr(ref, "stage_index", -1)
        if not 0 <= index < len(STAGES):
            continue
        name = getattr(ref, "item_name", "")
        for item in STAGES[index].items:
            if item.name == name and item.mapping:
                return item.mapping
    return ""


def mapping_tag_for_refs(refs) -> str:
    """Short card tag for content that auto-applies a mapping (H7f)."""
    value = mapping_for_refs(refs)
    if not value:
        return ""
    spec = mapping_spec(value)
    if spec is None:
        return ""
    if isinstance(spec, MappingSpec):
        return "自动分区" if spec.split is not None else "自动映射"
    return "自动分区" if spec == "split" else "自动映射"


def mapping_for_library_path(path: str | Path) -> str | MappingSpec:
    """Mapping declaration for a library file, built-in scores only.

    Imported files are user content: a same-stem import must not inherit a
    curriculum mapping by accident.
    """
    try:
        Path(path).resolve().relative_to(SCORE_DIR.resolve())
    except ValueError:
        return ""
    return mapping_for_score(Path(path).stem)


@lru_cache(maxsize=64)
def mapping_for_score(filename: str) -> str | MappingSpec:
    """Mapping declared by the curriculum item using this score stem.

    Library cards are derived from disk and carry no content metadata. When a
    card is opened, this bridges the file back to its curriculum declaration
    (first non-empty mapping wins). Imported files simply return "".
    """
    stem = PurePath(filename).stem.casefold()
    for stage in STAGES:
        for item in stage.items:
            if not item.score or not item.mapping:
                continue
            if PurePath(item.score).stem.casefold() == stem:
                return item.mapping
    return ""
