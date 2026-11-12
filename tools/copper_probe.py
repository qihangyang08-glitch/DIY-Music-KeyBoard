"""Measure how much an MPR121 electrode reacts when you touch it.

Drives the firmware's live monitor over USB serial, parses the per-electrode
delta columns, then reports both a per-electrode swing table and a list of
individual touch events (depth + duration), so a direct touch can be compared
against a touch through an overlay.

Usage: python copper_probe.py <PORT> <seconds> [module 1|2|3]

Touch behaviour: adding capacitance makes the filtered reading *drop*, so a
touch shows up as a large NEGATIVE delta relative to baseline.
"""

import re
import sys
import time

import serial

LINE_RE = re.compile(r"\[[^\]]*\]\s*touch=0x([0-9A-Fa-f]+)\s*d=(.*)$")

# A run of samples whose delta goes at least this far negative counts as one
# touch event. Kept well below the firmware's touch threshold so we can still
# see events that never crossed the threshold.
EVENT_DEPTH = 8


def parse_line(line):
    m = LINE_RE.search(line)
    if not m:
        return None
    mask = int(m.group(1), 16)
    values = []
    for tok in m.group(2).split():
        try:
            values.append(int(tok))
        except ValueError:
            values.append(None)
    if len(values) != 12:
        return None
    return mask, values


def find_events(samples, electrode):
    """Contiguous runs where the electrode's delta dips to EVENT_DEPTH or below."""
    events = []
    current = None
    for i, row in enumerate(samples):
        v = row[electrode]
        if v is not None and v <= -EVENT_DEPTH:
            if current is None:
                current = {"start": i, "depth": v}
            current["depth"] = min(current["depth"], v)
            current["end"] = i
        elif current is not None:
            events.append(current)
            current = None
    if current is not None:
        events.append(current)
    return events


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    module = sys.argv[3] if len(sys.argv) > 3 else "1"

    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.2
    s.dtr = False
    s.rts = False
    s.open()
    time.sleep(0.3)
    s.reset_input_buffer()

    s.write(module.encode())          # select the module
    time.sleep(0.2)
    s.reset_input_buffer()
    s.write(b"c")                     # start the live monitor
    time.sleep(0.2)

    samples = []
    touch_masks = []
    deadline = time.time() + seconds
    buf = b""
    while time.time() < deadline:
        buf += s.read(4096)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            parsed = parse_line(line.decode("utf-8", "replace"))
            if not parsed:
                continue
            mask, values = parsed
            touch_masks.append(mask)
            samples.append(values)

    s.write(b"c")                     # stop the monitor
    time.sleep(0.4)
    tail = s.read(65536).decode("utf-8", "replace")
    s.close()

    print(f"captured {len(samples)} samples over {seconds:.0f}s"
          f" (~{len(samples) / seconds:.1f} Hz)")
    if not samples:
        print("NO SAMPLES — is the firmware running and the module initialised?")
        return 1

    odd = [t for t in touch_masks if t != 0]
    print(f"samples where the chip itself flagged a touch: {len(odd)}"
          f"   masks seen: {sorted(set(hex(t) for t in odd))}")
    print()

    print("ele    min delta    max delta    peak swing")
    interesting = []
    for e in range(12):
        col = [row[e] for row in samples if row[e] is not None]
        if not col:
            print(f" E{e:<2}      <no data>")
            continue
        lo, hi = min(col), max(col)
        print(f" E{e:<2} {lo:11d} {hi:12d} {hi - lo:13d}")
        if hi - lo >= EVENT_DEPTH:
            interesting.append(e)
    print()

    sample_period = seconds / len(samples)
    for e in interesting:
        events = find_events(samples, e)
        if not events:
            continue
        durations = [(ev["end"] - ev["start"] + 1) for ev in events]
        avg = sum(durations) / len(durations) * sample_period
        print(f"E{e}: {len(events)} touch event(s)"
              f"  (average duration {avg * 1000:.0f} ms)")
        print("      time(s) : depth")
        for ev in events:
            print(f"      {ev['start'] * sample_period:7.1f} : {-ev['depth']}")
        print()

    print("----- firmware's own peak table -----")
    print(tail.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
