#!/usr/bin/env python3
"""Build the Windows one-folder app with PyInstaller (A4).

Usage (from ``pc/``):

    python -m pip install -r requirements-dev.txt
    python tools/build_app.py [--clean] [--output DIR]

The output is ``dist/KeyBorad/KeyBorad.exe`` plus ``_internal/`` containing the
public content and the FluidSynth/SoundFont runtime. Missing PyInstaller is a
clear non-zero error rather than a traceback.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.packaging import pyinstaller_problem  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    args = list(sys.argv[1:] if argv is None else argv)
    output = ROOT / "dist"
    clean = False
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--clean":
            clean = True
            index += 1
        elif argument == "--output":
            if index + 1 >= len(args):
                print("--output 需要目录参数", file=sys.stderr)
                return 2
            output = Path(args[index + 1])
            index += 2
        else:
            print(f"未知参数：{argument}", file=sys.stderr)
            return 2

    problem = pyinstaller_problem()
    if problem is not None:
        print(problem, file=sys.stderr)
        return 2

    spec = ROOT / "packaging" / "keyborad.spec"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--noconfirm",
        "--distpath",
        str(output),
        "--workpath",
        str(ROOT / "build"),
    ]
    if clean:
        command.append("--clean")
    print("运行：", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe = output / "KeyBorad" / "KeyBorad.exe"
    if not exe.exists():
        print(f"构建结束但没有找到 {exe}", file=sys.stderr)
        return 1
    print(f"完成：{exe}")
    print("目标机器无需安装 Python；整个 KeyBorad 文件夹可复制运行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
