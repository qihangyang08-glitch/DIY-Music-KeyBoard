#!/usr/bin/env python3
"""KeyBorad desktop instrument: perform, learn, library, creation.

Run from the repository root (or double-click pc/run.cmd):

    python pc/app/main.py                     # auto-detect device, audio on
    python pc/app/main.py --no-serial         # computer keyboard only
    python pc/app/main.py --port COM5         # force a serial port
    python pc/app/main.py --no-audio          # silent, for a quick look
    python pc/app/main.py --progress dev.json # dev learning-progress file
    python pc/app/main.py --library dev_scores # dev imported-score folder

Hardware: the ESP32-S3 USB-Serial/JTAG port is found automatically; close the
PlatformIO serial monitor first because one process owns the port. Audio:
FluidSynth + the vendored TimGM6mb SoundFont; the header reports 48 kHz when
ready and falls back to a silent backend otherwise.

The built-in public-domain sample score loads on startup; Space runs the
demo. 学习 opens on the 9-stage overview; score items hand the score to 演奏
and leave a "返回学习" chip, while generated drills open inside 学习.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # make "app" importable when run as a file

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402


def parse_size(text: str) -> tuple[int, int]:
    try:
        w, h = text.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("size must look like 1440x900")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KeyBorad desktop instrument",
        epilog=(
            "Examples: python pc/app/main.py --port COM5 ; "
            "python pc/app/main.py --no-serial --no-audio ; "
            "python pc/app/main.py --size 1280x800"
        ),
    )
    parser.add_argument("--port", help="force a serial port (e.g. COM5)")
    parser.add_argument("--no-serial", action="store_true", help="disable hardware auto-detect")
    parser.add_argument("--no-audio", action="store_true", help="run silently")
    parser.add_argument("--gain", type=float, default=0.6, help="FluidSynth gain (default 0.6)")
    parser.add_argument("--theme", choices=("studio", "stage"), default="studio")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--size", type=parse_size, help="window size, e.g. 1440x900")
    parser.add_argument("--screenshot", help="render one frame to this PNG and exit (dev)")
    parser.add_argument(
        "--progress",
        help="dev: use this learning-progress JSON instead of the user config",
    )
    parser.add_argument(
        "--library",
        help="dev: use this folder for imported scores instead of the user config",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("KeyBorad")
    app.setApplicationDisplayName("KeyBorad")
    app.setStyle("Fusion")

    window = MainWindow(
        port=args.port,
        serial_enabled=not args.no_serial,
        audio_enabled=not args.no_audio,
        gain=args.gain,
        theme_name=args.theme,
        fullscreen=args.fullscreen and not args.screenshot,
        progress_path=args.progress,
        library_root=args.library,
    )
    if args.size:
        window.resize(*args.size)
    if args.screenshot:
        # Render with the real platform's font database but never put a
        # window on screen. (QT_QPA_PLATFORM=offscreen has no fonts on
        # Windows, so a screenshot taken there is all tofu boxes.)
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        # The demo presses two keys; keep the shot silent but keep the real
        # 48 kHz audio status in the header.
        if getattr(window.synth, "available", False):
            window.synth.set_mute(True)
    window.show()

    if args.screenshot:
        out = Path(args.screenshot)

        def demo() -> None:
            # C5 + E5, the two bars the mockup shows pressed (computer keyboard).
            window.instrument.press_keyboard(8)
            window.instrument.press_keyboard(12)
            window.perform.add_wave(8)
            window.perform.add_wave(12)

        def grab() -> None:
            out.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(out))
            print(f"screenshot: {out}")
            window.close()
            app.quit()

        QTimer.singleShot(200, demo)
        QTimer.singleShot(520, grab)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
