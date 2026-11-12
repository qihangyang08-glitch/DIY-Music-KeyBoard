"""Wait for the ESP32-S3 to (re)appear on USB.

Usage: python board_watch.py [timeout_seconds]

Exits 0 as soon as an Espressif (VID 0x303A) device shows up, 1 on timeout.
Polling both the serial-port list and the PnP tree covers the case where the
board enumerates but Windows hasn't attached a COM port to it yet.
"""

import subprocess
import sys
import time

import serial.tools.list_ports as lp


def esp_ports():
    return [p for p in lp.comports() if p.vid == 0x303A]


def esp_pnp_count():
    try:
        out = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_PnPEntity | "
                "Where-Object { $_.PNPDeviceID -like '*VID_303A*' } | "
                "Measure-Object).Count",
            ],
            capture_output=True, text=True, timeout=25,
        ).stdout.strip()
        return int(out or 0)
    except Exception:
        return 0


def main():
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    deadline = time.time() + timeout
    i = 0
    while time.time() < deadline:
        ports = esp_ports()
        if ports:
            for p in ports:
                print(f"FOUND {p.device} | {p.description} | {p.hwid}", flush=True)
            return 0
        if i % 5 == 0 and esp_pnp_count():
            print("FOUND via PnP tree (no COM port attached yet)", flush=True)
            return 0
        i += 1
        time.sleep(2)
    print("TIMEOUT: no Espressif device appeared", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
