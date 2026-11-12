"""Serial reader for the firmware's status line.

The firmware streams one line per change plus a 2 s heartbeat:

    [  10972 ms]  0x5A OK  0x5C OK  0x5D OK   keys: 12

This thread owns the port, parses frames, and emits them to the UI. It also
auto-detects the ESP32-S3's native USB-Serial/JTAG port (VID 303A, PID 1001)
so plugging the instrument in needs no configuration. A port can be forced
with --port; --no-serial disables the thread entirely.

The parsing regexes are the ones validated in pc/prototype/keyboard_proto.py.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from .calibration import parse_calibration_line
from .note_engine import Frame

STATUS_RE = re.compile(r"^\[\s*(\d+)\s*ms\]\s*(.*)$")
MODULE_RE = re.compile(r"0x([0-9A-Fa-f]{2})\s+(OK|--)")
KEYS_RE = re.compile(r"keys:\s*(.*)$")

ESP32_VID = 0x303A
ESP32_PID = 0x1001


def parse_line(text: str) -> Optional[Frame]:
    """Status line -> Frame, or None for boot banners/notices."""
    match = STATUS_RE.match(text)
    if match is None:
        return None
    rest = match.group(2)
    keys_match = KEYS_RE.search(rest)
    if keys_match is None:
        return None
    modules = {int(addr, 16): (state == "OK") for addr, state in MODULE_RE.findall(rest)}
    active = {int(n) for n in re.findall(r"\d+", keys_match.group(1))}
    return Frame(
        t=time.monotonic(),
        active=active,
        dev_ms=int(match.group(1)),
        modules=modules,
        raw=text,
    )


def find_device_port() -> Optional[str]:
    """Return the ESP32-S3 USB-Serial/JTAG port, if one is plugged in."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    for info in list_ports.comports():
        if info.vid == ESP32_VID and info.pid == ESP32_PID:
            return info.device
    for info in list_ports.comports():
        text = f"{info.description or ''} {info.hwid or ''}".lower()
        if "usb jtag" in text or "usb serial/jtag" in text or "usb-serial/jtag" in text:
            return info.device
    return None


class SerialService(QThread):
    frameReady = Signal(object)          # Frame
    calibrationFrame = Signal(object)    # CalibrationFrame (CAL stream)
    connectionChanged = Signal(bool, str)  # connected, human-readable detail
    notice = Signal(str)                 # non-status firmware output

    def __init__(self, port: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.forced_port = port
        self._stop = False
        self._serial = None
        self._state: Optional[tuple[bool, str]] = None
        self._last_port: Optional[str] = None
        self._connected = False
        self._write_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    # -- thread -----------------------------------------------------------

    def run(self) -> None:
        try:
            import serial  # noqa: F401  (import check inside the thread)
        except ImportError:
            self._set_state(False, "pyserial 未安装")
            return

        while not self._stop:
            port = self.forced_port or find_device_port()
            if not port:
                self._set_state(False, "等待设备")
                self._sleep(1.2)
                continue

            import serial

            try:
                ser = serial.Serial(port, 115200, timeout=0.2)
                ser.reset_input_buffer()
                self._serial = ser
                self._last_port = port
                self._set_state(True, port)
                while not self._stop:
                    raw = ser.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", "replace").strip()
                    if not text:
                        continue
                    self.dispatch_line(text)
            except Exception as exc:
                if not self._stop:
                    self._set_state(False, f"{port} 断开（{type(exc).__name__}）")
            finally:
                try:
                    if self._serial is not None:
                        self._serial.close()
                except Exception:
                    pass
                self._serial = None

            if not self._stop:
                self._sleep(1.0)

    def dispatch_line(self, text: str) -> None:
        """Route one decoded line to the right signal.

        CAL is checked first so a calibration frame is never mistaken for a
        status line or a boot notice; malformed CAL lines fall through to
        ``notice`` rather than being silently dropped.
        """
        frame = parse_calibration_line(text)
        if frame is not None:
            self.calibrationFrame.emit(frame)
            return
        status = parse_line(text)
        if status is not None:
            self.frameReady.emit(status)
            return
        self.notice.emit(text)

    def send_line(self, text: str) -> bool:
        """Write one command line to the open port; False if unavailable.

        The reader thread only reads and this method only writes, so a single
        short write is safe without routing it through the thread. Callers
        treat False as "not connected" and show a message instead of piling
        commands up for a reconnect (a stale `c` or `T` would be worse).
        """
        with self._write_lock:
            ser = self._serial
            if ser is None or not self._connected:
                return False
            try:
                ser.write((text.rstrip("\r\n") + "\n").encode("utf-8"))
                ser.flush()
                return True
            except Exception:
                return False

    def stop(self) -> None:
        self._stop = True
        ser = self._serial
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        self.wait(1500)

    # -- helpers ----------------------------------------------------------

    def _set_state(self, connected: bool, detail: str) -> None:
        self._connected = connected
        state = (connected, detail)
        if state != self._state:
            self._state = state
            self.connectionChanged.emit(connected, detail)

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(0.05)
