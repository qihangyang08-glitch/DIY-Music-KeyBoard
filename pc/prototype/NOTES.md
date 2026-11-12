# PC-side core — prototype notes

**Question this prototype answers:** can the firmware's 20 ms `keys:` channel
mask drive a PC-side note/MIDI engine — press/release edges, chords,
glissando, repeats, octave/transpose, note-on/off timing — through an
open-source synth, and does the instrument behave correctly under real
fingers?

**Status:** one complete hardware session run on 2026-10-24
(`logs/session_20261024_203605`). The as-run checker reported 8 PASS / 5 WARN
/ 1 INFO, but replaying the same session through the tightened checker gives
**14/14 PASS**: the WARNs were short sensor blips on non-target pads and
operator retries, not functional failures. A focused rerun of S2/S3/S8
(`logs/session_20261024_204525`) produced clean S2 (3/3 taps) and S3 (875 ms
press); S8 recorded 3 slow taps (5 requested) plus one 32 ms ch 24 blip; the
other steps were skipped in that run. The ch 24/25 blips are intermittent.

Velocity was dropped by decision after the force probe: the pads are far more
sensitive to finger distance than to pressure, so a continuous velocity curve
would fight the physics. MIDI velocity is fixed at 100. The next phase is the
companion UI and threshold calibration (noise/hover/touch), not velocity.

## What runs

```
python pc/prototype/keyboard_proto.py sim                 # scripted session, no hardware
python pc/prototype/keyboard_proto.py sim --audio         # hear the scripted session
python pc/prototype/keyboard_proto.py live --port COM5    # free play
python pc/prototype/keyboard_proto.py test --port COM5    # guided one-shot test
python pc/prototype/keyboard_proto.py ports               # list serial ports
```

`live` hotkeys: `[` `]` octave, `-` `+` transpose, `p` program, `l` legato,
`k` panic, `q` quit.

The guided test has **no time limit per step**. It prints the requirement and
starts recording; you read, find the keys, do the action at your own pace,
then release everything and press Enter. The test then analyses what was
captured and moves on. Run it from an interactive terminal (it needs Enter);
`--no-audio` logs without sound.

It writes `logs/session_<timestamp>.jsonl` (frames, events, step results) and
a matching `.txt` transcript. Delete `logs/` freely.

## Input protocol

One line per change, plus a 2 s heartbeat:

```
[  10972 ms]  0x5A OK  0x5C OK  0x5D OK   keys: 12
```

Channels are 1-based, 1..36. `mapping/keymap.json` maps channel -> layout key
-> MIDI note (key 1 = F4 = MIDI 65); channels 33..36 are unused. The first
module's wiring is reversed (keys 1..12 -> channels 12..1), as recorded.

## Note-engine semantics (the part to validate)

- Rising edge = note-on, falling edge = note-off.
- Note-off is delayed by `--grace` (default 20 ms, one poll) so a gap in the
  middle of a slide does not chop the note. Re-pressing the same key inside
  that window still produces off -> on.
- `--legato` decides articulation when a new key lands while an old note is
  still in its grace window: off-first (piano) by default, on-first (overlap)
  with `--legato`.
- Simultaneous keys are independent voices (chords); nothing is stolen.
- Octave/transpose is applied at press time. Held notes keep their pitch.
- Velocity is fixed at 100: firmware v1 sends binary touch bits (see
  findings). `midi` is the note number actually sent to FluidSynth.

## Synth stack

- FluidSynth 2.6.1 (LGPL-2.1+), Windows x64 build, unpacked under
  `vendor/fluidsynth-v2.6.1-win10-x64-cpp11/`.
- TimGM6mb SoundFont (GPL-2.0, `vendor/soundfont/COPYING.txt`), loaded via
  `pyfluidsynth` (user-site install) through ctypes.
- The audio driver is created directly (`new_fluid_audio_driver`) instead of
  `Synth.start()`: this build has no valid MIDI input driver, and the serial
  port is the MIDI source anyway.
- If the DLL/SF2 is missing or audio cannot open, the program falls back to
  logging MIDI events, so the logic stays testable.

## Proposed guided test plan

One session, no fixed duration: each step ends when you press Enter. Steps
are in `make_plan()` in `keyboard_proto.py`; keys/actions are meant to be
negotiated and edited.

| step | action | keys | expected |
|---|---|---|---|
| S1 | hands off | - | no notes |
| S2 | 3 light taps | 8 (C5) | 3 on / 3 off, one note at a time |
| S3 | firm press ~1 s | 8 | at least 1 on/off (no velocity data) |
| S4 | long hold ~3 s | 1 (F4) | 1 on/off, held >= 2 s |
| S5 | chord ~1 s | 1, 16, 28 | 3 simultaneous notes, one per module |
| S6 | slow slide left->right | 1..12 | >= 8 ascending notes, no stuck note |
| S7 | slow slide right->left | 12..1 | >= 8 descending notes |
| S8 | 5 quick taps | 28 (G#6, module 3) | about 5 separate notes |
| S9 | tap neighbours one at a time | 7, 8, 9 | never more than 1 note at once |
| S10 | tool sets octave +1, tap twice | 8 | all notes MIDI 84 (C6) |
| S11 | tool sets octave -1, tap twice | 8 | all notes MIDI 60 (C4) |
| S12 | tool sets transpose +2, tap twice | 8 | all notes MIDI 74 (D5) |
| S13 | optional: unplug module 3 3V3 ~2 s | - | 0x5D goes `--`, comes back OK |
| S14 | hands off | - | nothing stuck |

Checks are intentionally forgiving about operator timing: a WARN means
"inspect this line", not necessarily a defect.

## Findings so far

1. **Device responds.** COM5 (VID 303A:1001), uptime read, modules 0x5A/0x5C/
   0x5D all `OK`; the parser and watchdog work against the real stream.
2. **No velocity.** The firmware reports touch bits only, so light vs hard
   press can only test detection reliability, not loudness. To add velocity
   the firmware must stream each active electrode's filtered-minus-baseline
   magnitude (e.g. extend the status line), and the PC maps magnitude to
   1..127. This is the single biggest missing feature.
3. **Latency floor.** Edge detection is quantised to the firmware's 20 ms
   poll, plus USB-CDC (~1-3 ms) and <1 ms in Python. A 20-40 ms worst case is
   fine for a keyboard but is audible on fast passages; the note-off grace
   trades a little more for fewer chopped notes. FluidSynth's audio buffer
   (dsound) adds its own output latency on top; that was not measured here.
   Chord onset is not quantised: simultaneous-ish presses arrive as separate
   note-ons, which is what a human chord looks like.
4. **Sub-poll taps are invisible.** A press and release entirely inside one
   20 ms window never reaches the PC. The MPR121 debounce register is 0, so
   quick bounces are only filtered by the polling window and the grace.
5. **MIDI path is direct.** Events go straight to FluidSynth; routing to a
   DAW/hardware port via `mido` is a small addition, not done here.
6. **Stale backlog playback (fixed after the first run).** The firmware keeps
   emitting status lines while a step prompt is waiting. The first version
   fed that backlog through the normal note path, so a touch made before the
   window (or an accidental brush) sounded as a fresh note during the
   "hands off" baseline. The serial buffer is now flushed on open,
   `settle_source()` only reads the backlog for the latest key state, and
   `NoteEngine.sync()` adopts that state without emitting note-ons. A key
   already held at step start is ignored until released and pressed again.
   Evidence: `logs/session_20261024_201522.txt`, which stops right after a
   backlog `ON 25 F6` during S1.
7. **Event log name collision (fixed after the second run).** The first real
   note crashed the guided test with `TypeError: Jsonl.add() got multiple
   values for argument 'kind'`: the method's first parameter and the event
   record's own `kind` field shared a name. The parameter is now
   `record_type`, so a record is `{"type": "event", "kind": "on", ...}`.
   Regression-checked by writing a synthetic NoteEvent through Jsonl.
8. **Operator-paced steps (design change after the timed runs).** The first
   plan used fixed 4-10 s windows. Logs `session_20261024_202655` and
   `session_20261024_202750` show S2/S3 collecting zero events because the
   operator was still reading the step and locating the keys. Each step now
   records until Enter; there is no timer. The settle/sync keeps the serial
   backlog from replaying during this open-ended wait.
9. **Licences.** FluidSynth is dynamically linked (LGPL); TimGM6mb is GPL.
   Both are fine for personal use; check before distributing an app with the
   SF2 vendored.

## Verdict (session 2026-10-24 20:36, replayed through the tightened checker)

**14/14 PASS.** The operator reported that it sounded correct; the event log
agrees. What the session actually proved:

- S2: three clean taps on key 8 (62-93 ms each). An extra 31 ms blip appeared
  on key 25.
- S3: key 8 held 953 ms. One 31 ms blip on key 24.
- S4: key 1 held 3188 ms; release was clean. One 31 ms blip on key 25.
- S5: chord keys 1 + 16 + 28 (one per module) sounded together both times the
  operator tried; max polyphony 4. An unintended long press on key 3 (656 and
  1344 ms) came from reaching across the instrument, not crosstalk.
- S6: slide 1 -> 12 produced all 12 notes ascending, with one duplicate
  key 2 and a pause; the user heard the glide. One 46 ms blip on key 25.
- S7: slide 12 -> 1 produced all 12 notes descending; one duplicate key 12
  at the start (hand positioning). Smooth, max poly 1.
- S8: seven repeats on key 28 (five requested), including a re-press inside
  the 20 ms grace: off -> on articulation worked. One 31 ms blip on key 25.
- S9: keys 7/8/9 never overlapped (max poly 1).
- S10-S12: octave +/-1 and transpose +2 produced exactly MIDI 84 / 60 / 74.
- S13: module 3 unplug/replug produced an I2C error, a reappearance and two
  "lost its config, re-initialised" events; the firmware recovered each time.
  The PC only saw this after notices were parsed (fixed).
- S14: no stuck notes.

Hardware caveat found by the run:

- **Channels 24 and 25 blip.** Channel 25 (key 25, F6, module 3 E0) produced
  31-46 ms false touches in S2, S4, S6 and S8; channel 24 (key 24, E6, module
  2 E11) did once in S3. They are short enough to ignore in the note engine
  and did not disturb any intended note, but they are real false triggers.
  Check the foil/wire on those two pads. Disabling module 3's unused
  electrodes E8-E11 (channels 33-36) is also worth trying; they are enabled
  but unconnected, and the two noisy keys sit at the module boundary.
- **Velocity was dropped.** The firmware reports binary touch bits; the force
  probe showed the pads respond much more to finger distance than to pressure.
  Keep MIDI velocity fixed at 100 and put expression into duration, release,
  glissando and sound choice. Do not promise a velocity curve in the UI.

Carry-forward decisions:

- Operator-paced steps (Enter to finish) are the right UX; the timed version
  cut off the operator while they were still locating keys.
- Keep the 20 ms release grace: it bridged the slide gaps and let fast
  repeats articulate cleanly.
- The checker now judges target keys only, ignores short blips on other keys,
  reports long unintended touches, and parses firmware health notices.
- Consider `setElectrodeCount(8)` for module 3 and hover-aware thresholds for
  the ch 24/25 blips.

## Force/velocity decision (2026-10-24)

A probe (REST/LIGHT/FIRM, later HOVER) was run; the result was mediocre and the
operator reports that the pads are very sensitive to finger distance. This is
expected for capacitive sensing (capacitance/proximity, not pressure). The
probe tool has been removed. Conclusion: fixed velocity; if thresholds need
help later, measure noise/hover/touch during calibration, not light/hard
force.

## Next phase (agreed direction)

1. Companion UI: top 32-key guide strip, centre score (image or parseable
   data), bottom 32-key performance keyboard with upward waves, mapping
   presets + auto-follow, and four extra pads.
2. Parseable score follow: MIDI/MusicXML, playhead, next-note highlight,
   auto-scroll, auto-mapping; image scores are display-only.
3. Threshold-only calibration: bare copper vs overlay, per-key noise/hover/
   touch thresholds (no velocity curve), profiles, device diagnostics.
4. Optional firmware work: per-key thresholds and active-key magnitude for
   calibration; disable unused module 3 electrodes; no velocity mapping.
