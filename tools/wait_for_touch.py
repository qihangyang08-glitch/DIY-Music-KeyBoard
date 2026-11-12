"""Sit and wait for any electrode to move, then record the whole event.

Timing-free alternative to copper_probe.py: no need to coordinate with the
person touching the pads. Keeps a rolling buffer of samples, and as soon as an
electrode deviates by TRIGGER counts it keeps recording for a few more seconds
and then dumps the window around the event.

Usage: python wait_for_touch.py <PORT> <timeout_seconds> [module 1|2|3]
"""

import collections
import re
import sys
import time

import serial

LINE_RE = re.compile(r"\[[^\]]*\]\s*touch=0x([0-9A-Fa-f]+)\s*d=(.*)$")

TRIGGER = 6          # counts of deviation that count as "something happened"
TAIL_SAMPLES = 40    # how many samples to keep recording after the trigger
PRE_SAMPLES = 25     # how many samples of history to show before the trigger


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
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
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
    s.write(module.encode())
    time.sleep(0.2)
    s.reset_input_buffer()
    s.write(b"c")
    time.sleep(0.2)

    history = collections.deque(maxlen=PRE_SAMPLES + TAIL_SAMPLES + 10)
    deadline = time.time() + timeout
    trigger_index = None
    tail_left = 0
    buf = b""
    started = time.time()

    print(f"listening on {port} (module {module}) for up to {timeout:.0f}s,"
          f" trigger = {TRIGGER} counts", flush=True)

    while time.time() < deadline:
        buf += s.read(4096)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            parsed = parse(line.decode("utf-8", "replace"))
            if not parsed:
                continue
            mask, values = parsed
            history.append((time.time() - started, mask, values))

            if trigger_index is None:
                moved = [abs(v) for v in values if v is not None and abs(v) >= TRIGGER]
                if moved:
                    trigger_index = len(history) - 1
                    tail_left = TAIL_SAMPLES
                    print(f"triggered at t={history[-1][0]:.1f}s"
                          f" (deviation {max(moved)} counts)", flush=True)
            elif tail_left > 0:
                tail_left -= 1
                if tail_left == 0:
                    break
        if trigger_index is not None and tail_left == 0:
            break

    s.write(b"c")   # stop the monitor
    time.sleep(0.3)
    s.close()

    if trigger_index is None:
        print(f"TIMEOUT: no electrode moved by {TRIGGER} counts in {timeout:.0f}s")
        return 1

    print()
    print("time(s)  mask   E0   E1   E2   E3   E4   E5   E6   E7   E8   E9  E10  E11")
    for t, mask, values in history:
        cells = "".join(f"{v:5d}" if v is not None else " <e>" for v in values)
        print(f"{t:7.1f}  0x{mask:02X} {cells}")

    print()
    print("----- peak deviation per electrode across this window -----")
    for e in range(12):
        col = [abs(v[e]) for _, _, v in history if v[e] is not None]
        if col and max(col) >= 2:
            print(f" E{e:<2} max |delta| = {max(col)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
