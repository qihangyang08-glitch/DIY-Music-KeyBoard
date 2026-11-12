# 32-key note ↔ MPR121 channel map

`keymap.json` (machine-readable) and `keymap.csv` (spreadsheet) describe the
same table. `note_reference.md` / `note_reference.csv` add the note name in
scientific pitch notation, MIDI number, 简谱 (1=C and 1=F) and treble-staff
position for each of the 32 keys.

## Where the data comes from

Recorded on 2026-10-24 by pressing keys **1 → 32** in the order of
`32键电子琴分布.png` and reading the resulting channel numbers from the
firmware's serial output (`按键顺序`).

```
keys 1..12  -> channels 12,11,10,...,1     module 1 (0x5A), reversed
keys 13..24 -> channels 13,14,...,24       module 2 (0x5C), straight
keys 25..32 -> channels 25,26,...,32       module 3 (0x5D), straight
```

All 32 keys produced 32 distinct channels, so nothing was double-assigned.

One 20 ms blip on channel 25 appeared between key 16 and key 17 in the raw log.
It was ignored as noise; key 25's real press is the one at t=29092 ms.

## Assumptions to check

1. **Octave.** The drawing fixes the note names but not which octave. Key 1 is
   taken as **F4 (MIDI 65)**, so key 32 is C7 (MIDI 96). To transpose, add the
   same offset to every `midi` value; the note names then move with it.

2. **The first octave is wired in reverse.** Keys 1–12 map to channels
   12→1, not 1→12. Quick check: touch only the leftmost key; the firmware
   should report `keys: 12`. If it reports `keys: 1`, the recording was made in
   reverse and the first 12 rows should be flipped.

## Deriving module / electrode from a channel

```
channel is 1-based, 1..36
module    = (channel - 1) / 12 + 1      -> 1, 2, 3
electrode = (channel - 1) % 12          -> 0..11
address   = [0x5A, 0x5C, 0x5D][module-1]
```

The firmware already reports channels in this numbering, so PC-side code only
needs `channel -> midi`, e.g.:

```python
keymap = json.load(open("keymap.json"))
by_channel = {k["channel"]: k["midi"] for k in keymap["keys"]}
midi_note = by_channel[channel]          # ignore channels not in the map
```

## Modules

| module | address | strap | channels |
|---|---|---|---|
| 1 | 0x5A | ADD → GND | 1–12 |
| 2 | 0x5C | ADD → SDA | 13–24 |
| 3 | 0x5D | ADD → SCL | 25–32 used (25–36 available) |

The address is latched at power-on; changing an ADD strap requires a power
cycle.
