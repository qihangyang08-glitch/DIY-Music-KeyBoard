"""Open the ESP32-S3 USB CDC port, read the boot banner, send a command,
and print everything that comes back.

Usage: python serial_cmd.py [port] [command ...]
Commands are sent one per line, each followed by a short settle delay.
"""
import sys
import time

import serial


def drain(ser, seconds):
    end = time.time() + seconds
    out = bytearray()
    while time.time() < end:
        chunk = ser.read(4096)
        if chunk:
            out += chunk
        else:
            time.sleep(0.02)
    return out.decode("utf-8", "replace")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    commands = sys.argv[2:]

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.1
    ser.dsrdtr = False
    ser.rtscts = False
    ser.open()
    # The S3 USB-Serial/JTAG does not wire DTR/RTS to EN/GPIO0, but drop them
    # anyway so the CDC endpoint never sees a spurious line change.
    ser.dtr = False
    ser.rts = False

    print("=== boot / streaming ===")
    print(drain(ser, 2.0).rstrip())

    for cmd in commands:
        ser.write(cmd.encode())
        ser.flush()
        print(f"\n=== sent {cmd!r} ===")
        print(drain(ser, 2.0).rstrip())

    ser.close()


if __name__ == "__main__":
    main()
