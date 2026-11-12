"""Build the public content archive (H9a guardrail).

Usage (from ``pc/``):

    python tools/build_public.py [output.zip]

The archive contains only files that passed ``app.core.release``'s whitelist:
public curriculum assets and project templates, plus ``PUBLIC_CONTENT.md`` and
``public_exclusions.json``. Private content (currently ``mariage_fragment``)
and user data (``learning.json``, ``score_prefs.json``, logs, caches, mockups)
never enter it. Any validation problem exits non-zero and writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.release import PublicBuildError, build_public_archive  # noqa: E402

DEFAULT_OUTPUT = ROOT / "dist" / "public_content.zip"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = list(sys.argv[1:] if argv is None else argv)
    output = Path(args[0]) if args else DEFAULT_OUTPUT
    try:
        plan = build_public_archive(output)
    except PublicBuildError as error:
        print("公开包构建失败，未写入任何文件：", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"公开包：{output}")
    print(f"包含 {len(plan.included_files)} 个文件",
          f"；移除 {len(plan.removed_entries)} 条内容。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
