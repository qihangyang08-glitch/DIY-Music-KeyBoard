"""Minimal UI-string localisation (H9c first slice).

The app is written in Chinese and lesson content is a content asset, not a UI
string, so this module translates the *chrome*: navigation, headers, settings,
perform controls, library and learning headings. Source strings are the keys;
an unknown string falls back to Chinese, which keeps mixed states readable
while the catalogue grows.

Language is applied once at startup and after a page switch. Switching the
preference in Settings takes effect after a restart (the Settings page says
so); rebuilding every live widget in place is deliberately out of scope.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QWidget,
)

LANGUAGE_ZH = "zh-CN"
LANGUAGE_EN = "en"
LANGUAGE_NAMES = ((LANGUAGE_ZH, "中文"), (LANGUAGE_EN, "English"))
LANGUAGE_CODES = tuple(code for code, _name in LANGUAGE_NAMES)

_current = LANGUAGE_ZH

EN: dict[str, str] = {
    # Navigation / shell
    "演奏": "Perform",
    "学习": "Learn",
    "曲谱": "Library",
    "创作": "Create",
    "设备": "Device",
    "设置": "Settings",
    "导航": "Navigation",
    "32 键电子琴": "32-key instrument",
    "等待设备": "Waiting for device",
    "电脑键盘 · 未连接设备": "Computer keyboard · no device",
    "设备无心跳": "Device not responding",
    "设备在线 · 等待模块": "Device online · waiting for modules",
    "等待设备 · 可电脑键盘弹": "Waiting for device · computer keyboard works",
    "电脑键盘": "Computer keyboard",
    "← 返回学习": "← Back to Learn",
    "方案 · 裸铜": "Profile · bare copper",
    "当前": "Current",
    "下一键": "Next",
    "最近": "Recent",
    "输入 · 无": "Input · none",
    # Perform
    "无跟随 · 手动翻页": "No follow · manual page",
    "范围": "Range",
    "跟弹 · 按对前进": "Follow · press the next key",
    "跟弹 · 当前音域不够": "Follow · out of range",
    "超出音域": "out of range",
    "延音": "Sustain",
    "八度−": "Octave−",
    "八度+": "Octave+",
    "命中": "Hits",
    "未中": "Misses",
    "光条": "bar",
    "无音频": "No audio",
    "音": "notes",
    "节奏 · 按任意键踩拍": "Rhythm · press any key on the beat",
    "训练 · 按步骤操作": "Training · follow the steps",
    "训练 · 看谱找音": "Training · read the staff and find the note",
    "示范播放中": "demo playing",
    "已完成 · 按“重来”或空格示范":
        "Finished · press Restart or Space for the demo",
    "自动跟随": "Auto follow",
    "C 大调": "C major",
    "A 小调": "A minor",
    "五声音阶": "Pentatonic",
    "左右分区": "Split",
    "白键 19 键": "White keys 19",
    "音色": "Sound",
    "钢琴 1": "Piano 1",
    "映射": "Mapping",
    "半音阶": "Chromatic",
    "重置": "Reset",
    "自动跟随乐谱": "Follow score",
    "● 录音": "● Record",
    "全部静音": "Mute all",
    "未校准 · 后续版本": "Uncalibrated · later version",
    "八度": "Octave",
    "移调": "Transpose",
    "谱面": "Sheet",
    "落键": "Keys",
    "专注": "Focus",
    "重来": "Restart",
    # Settings
    "主题、语言、辅助功能、键位与音色；更多设置在后续版本。":
        "Theme, language, accessibility, key bindings and sounds; "
        "more settings are coming later.",
    "主题": "Theme",
    "纸白（Studio）": "Paper (Studio)",
    "暗场（Stage）": "Dark (Stage)",
    "语言": "Language",
    "中文": "Chinese",
    "辅助功能": "Accessibility",
    "减少动效": "Reduce motion",
    "字号": "Text size",
    "小": "Small",
    "标准": "Normal",
    "大": "Large",
    "对错反馈不只靠颜色：× / ✓ 与文字同时显示。":
        "Feedback never relies on colour alone: × / ✓ and text appear together.",
    "高级（只读）": "Advanced (read-only)",
    "松开宽限 20 ms · 连奏关闭": "Release grace 20 ms · legato off",
    "固定力度 100": "Fixed velocity 100",
    "方案 · 裸铜 · 未校准（校准页制作中）":
        "Profile · bare copper · uncalibrated (calibration is being built)",
    "会话日志：后续版本接入": "Session log: coming in a later version",
    "工具": "Tools",
    "键位设置": "Key bindings",
    "音色页": "Sounds",
    "怎么用（F1）": "How to use (F1)",
    "键位可在“键位设置”里全部改绑；字母默认留给音符。":
        "Every key can be rebound in Key bindings; letters are reserved for notes.",
    "只缩放界面文字；光条与谱面几何不变":
        "Scales UI text only; the light bar and staff geometry do not change.",
    "中文/英文切换在下次启动生效。":
        "Language changes take effect on the next start.",
    # Library
    "曲谱库": "Library",
    "导入曲谱": "Import score",
    "查看制作中 →": "View planned →",
    "筛选": "Filter",
    "搜索标题 / 作曲家 / 阶段": "Search title / composer / stage",
    "刷新": "Refresh",
    "关闭": "Close",
    "可跟谱": "Followable",
    "收藏": "Favorites",
    "我的导入": "Imported",
    "全部": "All",
    "制作中": "Planned",
    "只把能解析的 MusicXML / MIDI 标为可跟随。导入只保存在本机，不上传。":
        "Only MusicXML / MIDI files that parse are marked followable. "
        "Imports stay on this machine.",
    # Learning chrome
    "9 个阶段：基础 → 演奏 → 创作。先看全貌，再选一课。":
        "9 stages: basics → playing → creating. See the path, then pick a lesson.",
    "不学也可以直接演奏 / 创作":
        "You can also skip learning and play or create directly.",
    "继续上次": "Continue last",
    "从这里开始": "Start here",
    "← 学习路线": "← Learning path",
    "指导书 · 点开看整页": "Guides · open a full lesson",
    "训练": "Training",
    "曲目": "Pieces",
    "考核 · 可选，不影响普通练习": "Exam · optional, does not block practice",
    "通关标准": "Pass criteria",
    "内容制作中": "Content in progress",
    "目标": "Goals",
    "先修": "Prerequisite",
    "知识": "Knowledge",
    "示范": "Demonstration",
    "练习": "Practice",
    "常见错误": "Common mistakes",
    "检查": "Check",
    "下一步": "Next",
    "这一课要做什么": "What this lesson covers",
    "要点": "Key points",
}


def normalize_language(value) -> str:
    return value if value in LANGUAGE_CODES else LANGUAGE_ZH


def set_language(code: str) -> None:
    global _current
    _current = normalize_language(code)


def language() -> str:
    return _current


def tr(text: str) -> str:
    if _current == LANGUAGE_EN:
        return EN.get(text, text)
    return text


def apply_language(root: QWidget) -> None:
    """Translate the current widget tree in place.

    Called after construction and when a page is shown, so lazily built
    headings are covered without threading a translator through every widget.
    """
    if _current != LANGUAGE_EN:
        return
    for widget in [root, *root.findChildren(QWidget)]:
        if isinstance(widget, (QLabel, QAbstractButton, QGroupBox)):
            text = widget.text()
            translated = EN.get(text)
            if translated is not None:
                widget.setText(translated)
        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            translated = EN.get(placeholder)
            if translated is not None:
                widget.setPlaceholderText(translated)
        if isinstance(widget, QComboBox):
            for index in range(widget.count()):
                translated = EN.get(widget.itemText(index))
                if translated is not None:
                    widget.setItemText(index, translated)
        tooltip = widget.toolTip()
        translated = EN.get(tooltip)
        if translated is not None:
            widget.setToolTip(translated)


__all__ = [
    "LANGUAGE_CODES",
    "LANGUAGE_EN",
    "LANGUAGE_NAMES",
    "LANGUAGE_ZH",
    "apply_language",
    "language",
    "normalize_language",
    "set_language",
    "tr",
]
