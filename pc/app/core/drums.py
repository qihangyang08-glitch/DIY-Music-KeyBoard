"""GM drum kits and the 32-key pad map (B9b).

GM drum kits live in SoundFont bank 128 and play on MIDI channel 10
(``DRUM_CHANNEL`` is the zero-based 9). TimGM6mb ships the eight kits listed
here, so B9b needs no new SoundFont either.

A drum pad is not a melody note: the 32 bars keep their physical order and
map straight onto GM percussion notes 35..66. The light bar and labels use
these names; learning/follow judgment is suppressed while drums are active.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# GM channel 10 in 1-based numbering.
DRUM_CHANNEL = 9


@dataclass(frozen=True)
class DrumKit:
    program: int  # bank 128 preset number
    name: str
    label: str


@dataclass(frozen=True)
class DrumPad:
    key: int  # physical bar 1..32
    midi: int  # GM percussion note
    name: str
    label: str


DRUM_KITS = (
    DrumKit(0, "Standard Kit", "标准鼓组"),
    DrumKit(8, "Room Kit", "房间鼓组"),
    DrumKit(16, "Power Kit", "强力鼓组"),
    DrumKit(24, "Electronic Kit", "电子鼓组"),
    DrumKit(25, "TR-808 Kit", "TR-808 鼓组"),
    DrumKit(32, "Jazz Kit", "爵士鼓组"),
    DrumKit(40, "Brush Kit", "刷鼓组"),
    DrumKit(48, "Orchestra Kit", "管弦鼓组"),
)

DRUM_PADS = (
    DrumPad(1, 35, "Acoustic Bass Drum", "低音鼓"),
    DrumPad(2, 36, "Bass Drum 1", "低音鼓 2"),
    DrumPad(3, 37, "Side Stick", "边击"),
    DrumPad(4, 38, "Acoustic Snare", "军鼓"),
    DrumPad(5, 39, "Hand Clap", "拍手"),
    DrumPad(6, 40, "Electric Snare", "电军鼓"),
    DrumPad(7, 41, "Low Floor Tom", "低落地嗵"),
    DrumPad(8, 42, "Closed Hi-Hat", "闭镲"),
    DrumPad(9, 43, "High Floor Tom", "高落地嗵"),
    DrumPad(10, 44, "Pedal Hi-Hat", "踩镲"),
    DrumPad(11, 45, "Low Tom", "低音嗵鼓"),
    DrumPad(12, 46, "Open Hi-Hat", "开镲"),
    DrumPad(13, 47, "Low-Mid Tom", "中低嗵鼓"),
    DrumPad(14, 48, "Hi-Mid Tom", "中高嗵鼓"),
    DrumPad(15, 49, "Crash Cymbal 1", "强音镲 1"),
    DrumPad(16, 50, "High Tom", "高音嗵鼓"),
    DrumPad(17, 51, "Ride Cymbal 1", "叮叮镲 1"),
    DrumPad(18, 52, "Chinese Cymbal", "中国镲"),
    DrumPad(19, 53, "Ride Bell", "叮叮镲帽"),
    DrumPad(20, 54, "Tambourine", "铃鼓"),
    DrumPad(21, 55, "Splash Cymbal", "水镲"),
    DrumPad(22, 56, "Cowbell", "牛铃"),
    DrumPad(23, 57, "Crash Cymbal 2", "强音镲 2"),
    DrumPad(24, 58, "Vibraslap", "颤音器"),
    DrumPad(25, 59, "Ride Cymbal 2", "叮叮镲 2"),
    DrumPad(26, 60, "Hi Bongo", "高音邦戈"),
    DrumPad(27, 61, "Low Bongo", "低音邦戈"),
    DrumPad(28, 62, "Mute Hi Conga", "闷音康加"),
    DrumPad(29, 63, "Open Hi Conga", "开放康加"),
    DrumPad(30, 64, "Low Conga", "低音康加"),
    DrumPad(31, 65, "High Timbale", "高音天巴"),
    DrumPad(32, 66, "Low Timbale", "低音天巴"),
)

_BY_KEY = {pad.key: pad for pad in DRUM_PADS}
_BY_MIDI = {pad.midi: pad for pad in DRUM_PADS}


def drum_for_key(key: int) -> Optional[DrumPad]:
    """The pad on one physical bar, or None outside 1..32."""
    return _BY_KEY.get(key)


def drum_label(midi: int) -> str:
    """Chinese drum name for a GM percussion note; safe for unknown notes."""
    pad = _BY_MIDI.get(midi)
    return pad.label if pad is not None else f"鼓 {midi}"
