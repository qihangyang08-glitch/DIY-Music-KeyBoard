"""Continuously mirror the board's live monitor into a small status file.

Unlike the one-shot tools, this never exits. It keeps an accumulating log of
every "activity episode" since it started, plus the most recent samples, in
tools/live_status.txt. Because history accumulates, whoever reads the file can
see whether anything happened at any point since the tool started -- no need to
guess when to look.

Usage: python live_status.py <PORT> [module 1|2|3] [period_ms]
"""

import re
import sys
import time

import serial

LINE_RE = re.compile(r"\[[^\]]*\]\s*touch=0x([0-9A-Fa-f]+)\s*d=(.*)$")
OUT = "tools/live_status.txt"
ACTIVE = 3      # counts of deviation that start/continue an episode
IDLE_GAP = 0.6  # seconds of quiet that ends an episode


def set_period(s, desired, tries=8):
    for _ in range(tries):
        s.reset_input_buffer()
        s.write(b"f")
        time.sleep(0.15)
        m = re.search(r"sample period -> (\d+) ms",
                      s.read(4000).decode("utf-8", "replace"))
        if m and int(m.group(1)) == desired:
            return True
    return False


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    module = sys.argv[2] if len(sys.argv) > 2 else "1"
    period = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.2
    s.dtr = False
    s.rts = False
    s.open()
    time.sleep(0.3)
    s.reset_input_buffer()
    set_period(s, period)
    s.write(module.encode())
    time.sleep(0.2)
    s.reset_input_buffer()

    # 'c' toggles the monitor, so a previous tool that was killed mid-run can
    # leave it switched on. Verify data is actually flowing and toggle again if
    # it is not.
    flowing = False
    for _ in range(4):
        s.write(b"c")
        time.sleep(0.6)
        probe = s.read(16384).decode("utf-8", "replace")
        if LINE_RE.search(probe):
            flowing = True
            break
    if not flowing:
        print("ERROR: no monitor data from the board after toggling 'c'", flush=True)

    started = time.time()
    episodes = []          # each: {start, end, peak(E0..E11), driver}
    current = None
    recent = []
    peak_all = [0] * 12
    buf = b""

    while True:
        buf += s.read(4096)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            m = LINE_RE.search(line.decode("utf-8", "replace"))
            if not m:
                continue
            values = []
            for tok in m.group(2).split():
                try:
                    values.append(int(tok))
                except ValueError:
                    values.append(None)
            if len(values) != 12 or any(v is None for v in values):
                continue

            t = time.time() - started
            recent.append((t, int(m.group(1), 16), values))
            if len(recent) > 20:
                recent.pop(0)

            hot = any(abs(v) >= ACTIVE for v in values[:8])
            if hot:
                if current is None:
                    current = {"start": t, "end": t, "peaks": [0] * 12}
                current["end"] = t
                for e in range(12):
                    current["peaks"][e] = max(current["peaks"][e], abs(values[e]))
                    peak_all[e] = max(peak_all[e], abs(values[e]))
            elif current is not None and t - current["end"] > IDLE_GAP:
                episodes.append(current)
                current = None

            if len(recent) % 4:      # refresh the file ~5x/second
                continue

        all_eps = episodes + ([current] if current else [])
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(f"# live_status: module {module}, {period} ms, "
                     f"running for {time.time() - started:.0f}s\n")
            fh.write(f"# {len(all_eps)} activity episode(s) so far"
                     f" (threshold {ACTIVE} counts)\n")
            fh.write(f"# overall peak |delta| E0..E11: {peak_all[:8]}"
                     f"  E8..E11: {peak_all[8:]}\n\n")
            for i, ep in enumerate(all_eps[-40:], 1):
                driver = max(range(12), key=lambda e: ep["peaks"][e])
                others = {f"E{e}": ep["peaks"][e] for e in range(12)
                          if e != driver and ep["peaks"][e] >= 2}
                fh.write(f"EP{len(all_eps) - len(all_eps[-40:]) + i}: "
                         f"t={ep['start']:.1f}..{ep['end']:.1f}s "
                         f"({(ep['end'] - ep['start']) * 1000:.0f} ms) "
                         f"driver=E{driver} peak={ep['peaks'][driver]} "
                         f"others={others if others else 'NONE'}\n")
            fh.write("\n# most recent samples (time, mask, E0..E7)\n")
            for t, mask, v in recent[-8:]:
                fh.write(f"  {t:7.2f}  0x{mask:02X} " +
                         "".join(f"{x:5d}" for x in v[:8]) + "\n")


if __name__ == "__main__":
    main()
