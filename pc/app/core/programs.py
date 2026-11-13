"""GM program catalog shared by the sound page, the creation page and MIDI.

TimGM6mb already contains every GM melodic preset, so B9 only needs a catalog
and a wider chooser — no new SoundFont. The first seven entries keep the
legacy ``PROGRAMS`` order from P1 so ``program_index`` values stored in user
settings, tests and the live instrument do not shift when the list grows.

Chinese labels stay here (the English GM name remains the tooltip) because
the rest of the UI is Chinese-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Optional, Tuple

# Display order for category chips (B9a-2). Every program belongs to exactly
# one of these.
CATEGORIES = (
    "钢琴/键盘",
    "吉他/贝斯",
    "弦乐/合奏",
    "管乐",
    "合成/打击",
)


@dataclass(frozen=True)
class Program:
    gm: int
    name: str
    label: str
    category: str


CATALOG = (
    # Legacy P1 order first: these indices are persisted in user settings and
    # held by the live instrument, so they may never move.
    Program(0, "Piano 1", "钢琴 1", "钢琴/键盘"),
    Program(4, "E.Piano 1", "电钢琴 1", "钢琴/键盘"),
    Program(16, "Drawbar Organ", "拉杆风琴", "钢琴/键盘"),
    Program(24, "Nylon Guitar", "尼龙吉他", "吉他/贝斯"),
    Program(48, "Strings 1", "弦乐合奏 1", "弦乐/合奏"),
    Program(80, "Square Lead", "方波主音", "合成/打击"),
    Program(32, "Acoustic Bass", "低音贝斯", "吉他/贝斯"),
    # Everything below is appended in GM number order.
    Program(1, "Bright Piano", "明亮钢琴", "钢琴/键盘"),
    Program(6, "Harpsichord", "大键琴", "钢琴/键盘"),
    Program(11, "Vibraphone", "颤音琴", "钢琴/键盘"),
    Program(12, "Marimba", "马林巴", "钢琴/键盘"),
    Program(19, "Church Organ", "教堂风琴", "钢琴/键盘"),
    Program(21, "Accordion", "手风琴", "钢琴/键盘"),
    Program(22, "Harmonica", "口琴", "钢琴/键盘"),
    Program(25, "Steel Guitar", "钢弦吉他", "吉他/贝斯"),
    Program(27, "Clean Electric", "清音电吉他", "吉他/贝斯"),
    Program(29, "Overdrive", "过载吉他", "吉他/贝斯"),
    Program(30, "Distortion", "失真吉他", "吉他/贝斯"),
    Program(33, "Finger Bass", "指弹贝斯", "吉他/贝斯"),
    Program(36, "Slap Bass", "击弦贝斯", "吉他/贝斯"),
    Program(40, "Violin", "小提琴", "弦乐/合奏"),
    Program(42, "Cello", "大提琴", "弦乐/合奏"),
    Program(43, "Contrabass", "低音提琴", "弦乐/合奏"),
    Program(45, "Pizzicato", "拨弦弦乐", "弦乐/合奏"),
    Program(46, "Harp", "竖琴", "弦乐/合奏"),
    Program(52, "Choir Aahs", "人声合唱 · 啊", "弦乐/合奏"),
    Program(53, "Voice Oohs", "人声合唱 · 呜", "弦乐/合奏"),
    Program(56, "Trumpet", "小号", "管乐"),
    Program(57, "Trombone", "长号", "管乐"),
    Program(60, "French Horn", "圆号", "管乐"),
    Program(61, "Brass Section", "铜管组", "管乐"),
    Program(64, "Soprano Sax", "高音萨克斯", "管乐"),
    Program(65, "Alto Sax", "中音萨克斯", "管乐"),
    Program(66, "Tenor Sax", "次中音萨克斯", "管乐"),
    Program(67, "Baritone Sax", "上低音萨克斯", "管乐"),
    Program(68, "Oboe", "双簧管", "管乐"),
    Program(71, "Clarinet", "单簧管", "管乐"),
    Program(73, "Flute", "长笛", "管乐"),
    Program(74, "Recorder", "竖笛", "管乐"),
    Program(75, "Pan Flute", "排箫", "管乐"),
    Program(79, "Ocarina", "陶笛", "管乐"),
    Program(81, "Saw Lead", "锯齿主音", "合成/打击"),
    Program(89, "Warm Pad", "温暖铺底", "合成/打击"),
    Program(90, "Poly Synth", "复音合成", "合成/打击"),
    Program(115, "Woodblock", "木鱼", "合成/打击"),
    Program(116, "Taiko", "太鼓", "合成/打击"),
    Program(117, "Melodic Tom", "旋律嗵鼓", "合成/打击"),
    Program(118, "Synth Drum", "合成鼓", "合成/打击"),
)


# Legacy P1 shape: (GM number, English name). Kept so existing imports keep
# working while the catalog is the source of truth.
PROGRAMS = tuple((program.gm, program.name) for program in CATALOG)

_BY_GM = {program.gm: program for program in CATALOG}
FALLBACK = CATALOG[0]


def program_for_gm(gm: int) -> Optional[Program]:
    """The catalog entry for a GM number, or None when it is not offered."""
    return _BY_GM.get(gm)


def index_for_gm(gm: int) -> Optional[int]:
    """Position in the catalog, or None. Project files store GM, not index."""
    program = _BY_GM.get(gm)
    return None if program is None else CATALOG.index(program)


def resolve_gm(
    gm: int, available: Optional[Collection[int]] = None
) -> Tuple[Program, bool]:
    """Pick the playable program for a GM number.

    Returns ``(program, fell_back)``. An unknown GM number, or a known one the
    loaded SoundFont does not provide (``available``), falls back to piano so
    the UI always has a playable, nameable substitute.
    """
    program = _BY_GM.get(gm)
    if program is None:
        return FALLBACK, True
    if available is not None and gm not in available:
        return FALLBACK, True
    return program, False


def label_for_gm(gm: int) -> str:
    """Chinese label for display; unknown numbers show the fallback piano."""
    program, _fell_back = resolve_gm(gm)
    return program.label


def fallback_notice(gm: int, available: Optional[Collection[int]] = None) -> str:
    """One-line notice for a missing sound, or "" when the program is fine."""
    _program, fell_back = resolve_gm(gm, available)
    if not fell_back:
        return ""
    known = _BY_GM.get(gm)
    if known is None:
        return f"音色 GM {gm} 不在音色库中，已回退钢琴 1"
    available_note = "" if available is None else "（当前 SoundFont 未提供）"
    return f"音色 {known.name}{available_note}，已回退钢琴 1"
