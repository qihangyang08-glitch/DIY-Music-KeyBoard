"""Data plan for the Windows bundle (A4).

The build ships two trees: public content (``resources/``) and the audio
runtime (``prototype/vendor/``: FluidSynth DLLs and the TimGM6mb SoundFont).
Everything else — user data, logs, the source prototypes, build output — stays
out. The plan is a plain list of ``(source, destination)`` pairs so it can be
tested without PyInstaller installed; the spec file feeds it to ``Analysis``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Trees copied into the one-folder build, relative to the PC root.
BUNDLE_TREES = ("resources", "prototype/vendor")

# Host-only or build-only files: the executable is replaced by the bundle's own,
# import libraries and headers are only needed to compile FluidSynth, and debug
# symbols only bloat the installer.
SKIP_SUFFIXES = frozenset({".exe", ".lib", ".h", ".pdb", ".exp"})


def _skip(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return any(part in {"__pycache__", ".git"} for part in path.parts)


def collect_data_files(
    root: str | Path, repo_root: str | Path | None = None
) -> list[tuple[Path, str]]:
    """Every file to bundle, as ``(absolute source, POSIX destination dir)``.

    ``repo_root`` supplies the shared ``mapping/`` table, which lives one
    level above ``pc/`` in the source tree and is copied to ``mapping/`` in
    the bundle.
    """
    base = Path(root)
    plan: list[tuple[Path, str]] = []
    # The installer is a public distribution: reuse the release whitelist so
    # private scores/lesson files can never ride along just because they sit
    # in a local resources/ folder.
    from .release import plan_public_build

    allowed = set(plan_public_build(project_root=base).included_files)
    for tree in BUNDLE_TREES:
        directory = base / tree
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or _skip(path):
                continue
            relative = path.relative_to(base).as_posix()
            if tree == "resources" and relative not in allowed:
                continue
            destination = path.parent.relative_to(base).as_posix()
            plan.append((path, destination))
    if repo_root is not None:
        mapping = Path(repo_root) / "mapping"
        if mapping.is_dir():
            for path in sorted(mapping.rglob("*")):
                if not path.is_file() or _skip(path):
                    continue
                destination = path.parent.relative_to(repo_root).as_posix()
                plan.append((path, destination))
    return plan


def pyinstaller_datas(
    root: str | Path, repo_root: str | Path | None = None
) -> list[tuple[str, str]]:
    """The same plan in the ``datas=[(src, dest)]`` form PyInstaller expects."""
    return [
        (str(source), destination)
        for source, destination in collect_data_files(root, repo_root)
    ]


def pyinstaller_problem() -> str | None:
    """Return a user-facing reason when PyInstaller is unavailable, else None."""
    if importlib.util.find_spec("PyInstaller") is not None:
        return None
    return (
        "未安装 PyInstaller；请先运行 "
        "python -m pip install -r pc/requirements-dev.txt"
    )


__all__ = [
    "BUNDLE_TREES",
    "collect_data_files",
    "pyinstaller_datas",
    "pyinstaller_problem",
]
