"""Catch whatever the board prints on its USB CDC port.

Usage: python serial_catch.py <PORT> [timeout_seconds]

Opens the port with DTR/RTS de-asserted so we neither reset the chip nor
disturb its boot mode, then reads until it sees data or the timeout expires.
Exits 0 if data arrived, 1 on timeout.
"""

import sys
import time

import serial


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0

    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.3
    s.dtr = False
    s.rts = False
    s.open()

    deadline = time.time() + timeout
    got = b""
    while time.time() < deadline:
        chunk = s.read(8192)
        if chunk:
            got += chunk
            # Give the burst a moment to finish, then report.
            time.sleep(0.4)
            got += s.read(8192)
            break
    s.close()

    if got:
        print(f"GOT {len(got)} bytes from {port}:")
        print("======================")
        print(got.decode("utf-8", "replace"))
        return 0
    print(f"TIMEOUT: {port} stayed silent", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
