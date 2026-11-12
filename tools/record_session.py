"""Record a whole touch session, then split it into individual events.

Lets the operator perform an entire experiment in one go (e.g. bare-pad taps,
then the same taps with the PVC overlay on) instead of trying to hit a narrow
window. Every event is reported with the peak deviation of *all twelve*
electrodes, so cross-talk and false-trigger questions can be answered from a
single recording.

Usage: python record_session.py <PORT> <seconds> [module 1|2|3] [period_ms 20|50|100|200]
"""

import re
import sys
import time

import serial

LINE_RE = re.compile(r"\[[^\]]*\]\s*touch=0x([0-9A-Fa-f]+)\s*d=(.*)$")

PERIODS = [200, 100, 50, 20]
ACTIVE = 4      # a frame counts as "something is happening" at this deviation


def set_period(s, desired, tries=8):
    """'f' cycles the firmware's sample period, so ask it what it settled on
    rather than assuming a starting index (which drifts between runs)."""
    for _ in range(tries):
        s.reset_input_buffer()
        s.write(b"f")
        time.sleep(0.15)
        resp = s.read(4000).decode("utf-8", "replace")
        m = re.search(r"sample period -> (\d+) ms", resp)
        if m:
            if int(m.group(1)) == desired:
                return desired
    return None


def parse(line):
    m = LINE_RE.search(line)
    if not m:
        return None
    values = []
    for tok in m.group(2).split():
        try:
            values.append(int(tok))
        except ValueError:
            values.append(None)
    return (int(m.group(1), 16), values) if len(values) == 12 else None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    module = sys.argv[3] if len(sys.argv) > 3 else "1"
    period = int(sys.argv[4]) if len(sys.argv) > 4 else 50

    if period not in PERIODS:
        print(f"period must be one of {PERIODS}")
        return 2

    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.2
    s.dtr = False
    s.rts = False
    s.open()
    time.sleep(0.3)
    s.reset_input_buffer()

    reached = set_period(s, period)
    if reached is None:
        print(f"WARNING: could not confirm a {period} ms sample period")
    s.write(module.encode())
    time.sleep(0.2)
    s.reset_input_buffer()
    s.write(b"c")
    time.sleep(0.2)

    started = time.time()
    frames = []
    buf = b""
    while time.time() - started < seconds:
        buf += s.read(8192)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            parsed = parse(line.decode("utf-8", "replace"))
            if parsed:
                frames.append((time.time() - started, parsed[0], parsed[1]))

    s.write(b"c")
    time.sleep(0.3)
    s.close()

    print(f"recorded {len(frames)} frames in {seconds:.0f}s at ~{period} ms")
    if not frames:
        print("NO FRAMES — is the firmware running?")
        return 1

    # Segment into events.
    events = []
    current = None
    for t, mask, values in frames:
        hot = any(v is not None and abs(v) >= ACTIVE for v in values)
        if hot:
            if current is None:
                current = {"start": t, "end": t, "frames": []}
            current["end"] = t
            current["frames"].append((t, mask, values))
        elif current is not None:
            events.append(current)
            current = None
    if current is not None:
        events.append(current)

    print(f"{len(events)} event(s) detected (activity >= {ACTIVE} counts)\n")
    for n, ev in enumerate(events, 1):
        peaks = []
        for e in range(12):
            col = [abs(v[e]) for _, _, v in ev["frames"] if v[e] is not None]
            peaks.append(max(col) if col else 0)
        driver = max(range(12), key=lambda e: peaks[e])
        print(f"--- event {n}: t={ev['start']:.1f}s..{ev['end']:.1f}s "
              f"({(ev['end'] - ev['start']) * 1000:.0f} ms), driven by E{driver} "
              f"(peak {peaks[driver]}) ---")
        row = "  ".join(f"E{e}:{peaks[e]}" for e in range(12) if peaks[e] >= 2)
        print(f"    peaks: {row}")
        neighbours = [f"E{e}:{peaks[e]}" for e in range(12)
                      if e != driver and peaks[e] >= 2]
        print(f"    other electrodes that moved: {neighbours if neighbours else 'NONE'}")
        print()

    # Full trace to a file, for closer inspection.
    path = "tools/session_trace.txt"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("time(s)  mask   E0   E1   E2   E3   E4   E5   E6   E7   E8   E9  E10  E11\n")
        for t, mask, values in frames:
            cells = "".join(f"{v:5d}" if v is not None else " <e>" for v in values)
            fh.write(f"{t:7.2f}  0x{mask:02X} {cells}\n")
    print(f"full trace written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
