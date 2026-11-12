"""Public-build guardrails (H9a).

The public build is a whitelist: only files explicitly selected for release
enter the archive. This module derives that whitelist from the curriculum and
the resource tree, records every exclusion, and audits package members so a
private asset or a user-data file can never slip into a public distribution.

Pure logic: no Qt, no network, no writes unless ``build_public_archive`` is
called with an explicit destination.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from .curriculum import STAGES, Stage
from .project import Project

SCORE_PREFIX = "resources/scores"
PROJECT_PREFIX = "resources/projects"

# Any same-stem variant of a private score must be excluded, not just the
# extension the curriculum happens to name.
SCORE_SUFFIXES = frozenset({".mxl", ".mid", ".midi", ".musicxml", ".xml"})

ROOT = Path(__file__).resolve().parents[2]  # pc/

# Directories that never belong in a distributable package. Compared against
# every path component case-insensitively.
FORBIDDEN_DIRS = frozenset(
    {
        ".git",
        ".pio",
        ".venv",
        ".cache",
        "__pycache__",
        "dist",
        "logs",
        "mockups",
        "user-data",
        "user_data",
        "venv",
    }
)

# User state written next to learning.json in the app-config directory.
FORBIDDEN_NAMES = frozenset(
    {
        "accessibility.json",
        "keybindings.json",
        "learning.json",
        "library_meta.json",
        "score_prefs.json",
    }
)

# Editor/OS debris and temporary files.
FORBIDDEN_SUFFIXES = frozenset(
    {".bak", ".log", ".pyc", ".pyo", ".tmp"}
)


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(str(path).replace("\\", "/")).parts


def forbidden_package_path(path: str) -> bool:
    """True when ``path`` may never appear inside a public package."""
    parts = _parts(path)
    if not parts:
        return False
    for part in parts[:-1]:
        if part.lower() in FORBIDDEN_DIRS:
            return True
    name = parts[-1]
    lowered = name.lower()
    if lowered in FORBIDDEN_DIRS or lowered in FORBIDDEN_NAMES:
        return True
    return PurePosixPath(lowered).suffix in FORBIDDEN_SUFFIXES


@dataclass(frozen=True)
class ContentEntry:
    """One curriculum item and the files that carry it."""

    content_id: str
    title: str
    stage: int
    visibility: str
    action: str  # include | remove
    files: tuple[str, ...]
    reason: str = ""


def _score_files(name: str) -> tuple[str, ...]:
    path = PurePosixPath(SCORE_PREFIX) / name
    files = [str(path)]
    if path.suffix.lower() in (".musicxml", ".mxl", ".xml"):
        files.append(str(path.with_suffix(".mid")))
    return tuple(files)


def content_manifest(stages: tuple[Stage, ...] = STAGES) -> tuple[ContentEntry, ...]:
    """Describe every curriculum item for a public build.

    Exclusion is derived from the same ``visibility`` field the UI already
    uses, so a private item cannot be forgotten in a hand-maintained list.
    """
    entries: list[ContentEntry] = []
    for stage in stages:
        for item in stage.items:
            files: list[str] = []
            if item.score:
                files.extend(_score_files(item.score))
            if item.project:
                files.append(str(PurePosixPath(PROJECT_PREFIX) / f"{item.project}.json"))
            if item.visibility == "private":
                action, reason = "remove", "visibility=private"
            elif item.visibility != "public":
                action, reason = "remove", f"invalid visibility={item.visibility}"
            else:
                action, reason = "include", ""
            entries.append(
                ContentEntry(
                    content_id=f"stage{stage.index}:{item.name}",
                    title=item.name,
                    stage=stage.index,
                    visibility=item.visibility,
                    action=action,
                    files=tuple(files),
                    reason=reason,
                )
            )
    return tuple(entries)


@dataclass(frozen=True)
class PublicBuildPlan:
    """Files a public build may ship, plus everything it must drop."""

    entries: tuple[ContentEntry, ...]
    included_files: tuple[str, ...]
    excluded_files: tuple[tuple[str, str], ...]  # (path, reason)
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def removed_entries(self) -> tuple[ContentEntry, ...]:
        return tuple(entry for entry in self.entries if entry.action == "remove")


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _project_exclusion(path: Path) -> str:
    """Why this project template may not ship publicly ('' = it may)."""
    project = Project.load(path)
    if project.visibility != "public":
        return f"project visibility={project.visibility}"
    if project.public_release != "yes":
        return f"project public_release={project.public_release}"
    return ""


def _lesson_exclusion(path: Path) -> str:
    """Why this Lesson JSON may not ship publicly ('' = it may)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unreadable lesson"
    if not isinstance(data, dict):
        return "invalid lesson"
    visibility = data.get("visibility")
    if visibility != "public":
        return f"lesson visibility={visibility}"
    if data.get("public_release") != "yes":
        return f"lesson public_release={data.get('public_release')}"
    return ""


def plan_public_build(
    stages: tuple[Stage, ...] = STAGES,
    project_root: Path | str = ROOT,
) -> PublicBuildPlan:
    """Whitelist every resource file, dropping private/unshippable content.

    The whole ``resources/`` tree is scanned rather than a hardcoded list, so
    newly added assets cannot be silently omitted from the public archive.
    Curriculum visibility and project metadata are the two exclusion sources;
    anything forbidden by path policy is excluded and reported as a problem.
    """
    root = Path(project_root)
    resources = root / "resources"
    entries = content_manifest(stages)
    problems: list[str] = []
    excluded: dict[str, str] = {}

    private_files: dict[str, str] = {}
    private_score_stems: set[str] = set()
    for entry in entries:
        if entry.action != "remove":
            continue
        for file in entry.files:
            private_files[file] = f"{entry.content_id}: {entry.reason}"
            path = PurePosixPath(file)
            if (
                path.parent == PurePosixPath(SCORE_PREFIX)
                and path.suffix.lower() in SCORE_SUFFIXES
            ):
                private_score_stems.add(str(path.with_suffix("")))

    scan = (
        sorted(path for path in resources.rglob("*") if path.is_file())
        if resources.is_dir()
        else []
    )
    included: list[str] = []
    for path in scan:
        relative = _relative(path, root)
        if forbidden_package_path(relative):
            excluded[relative] = "forbidden package path"
            problems.append(f"forbidden file inside resources/: {relative}")
            continue
        relative_path = PurePosixPath(relative)
        private_sibling = (
            relative_path.suffix.lower() in SCORE_SUFFIXES
            and str(relative_path.with_suffix("")) in private_score_stems
        )
        if relative in private_files or private_sibling:
            excluded[relative] = private_files.get(
                relative, "private score companion"
            )
            continue
        if path.suffix.lower() == ".json" and path.parent.name == "projects":
            reason = _project_exclusion(path)
            if reason:
                excluded[relative] = reason
                continue
        if path.suffix.lower() == ".json" and path.parent.name == "lessons":
            reason = _lesson_exclusion(path)
            if reason:
                excluded[relative] = reason
                continue
        included.append(relative)

    for entry in entries:
        if entry.action != "include":
            continue
        for file in entry.files:
            if not (root / file).is_file():
                problems.append(f"missing asset for {entry.content_id}: {file}")

    # Defense in depth: whatever the scan produced must survive the same audit
    # that a finished archive goes through.
    for file in included:
        if file in excluded or forbidden_package_path(file):
            problems.append(f"excluded file leaked into public build: {file}")

    return PublicBuildPlan(
        entries=entries,
        included_files=tuple(sorted(included)),
        excluded_files=tuple(sorted(excluded.items())),
        problems=tuple(problems),
    )


def audit_package(plan: PublicBuildPlan, members) -> tuple[str, ...]:
    """Return every reason ``members`` may not ship in a public package."""
    violations: list[str] = []
    excluded = {path for path, _reason in plan.excluded_files}
    for raw in members:
        member = str(raw).replace("\\", "/")
        parts = PurePosixPath(member).parts
        if member.startswith("/") or ".." in parts:
            violations.append(f"unsafe archive path: {member}")
        elif forbidden_package_path(member):
            violations.append(f"forbidden archive member: {member}")
        elif member in excluded:
            violations.append(f"private asset in package: {member}")
    return tuple(violations)


class PublicBuildError(RuntimeError):
    """The public build is not shippable; nothing was written."""

    def __init__(self, problems) -> None:
        self.problems = tuple(problems)
        super().__init__("public build failed:\n" + "\n".join(self.problems))


def _exclusions_payload(
    plan: PublicBuildPlan, generated_at: str
) -> dict:
    items = [
        {
            "content_id": entry.content_id,
            "action": entry.action,
            "reason": entry.reason,
            "files": list(entry.files),
        }
        for entry in plan.removed_entries
    ]
    covered = {file for entry in plan.removed_entries for file in entry.files}
    for path, reason in plan.excluded_files:
        if path in covered:
            continue
        items.append(
            {
                "content_id": f"file:{path}",
                "action": "remove",
                "reason": reason,
                "files": [path],
            }
        )
    return {"schema_version": 1, "generated_at": generated_at, "items": items}


def _content_markdown(
    plan: PublicBuildPlan, generated_at: str
) -> str:
    lines = [
        "# 公开版内容清单",
        "",
        f"- 生成日期：{generated_at}",
        f"- 包含文件：{len(plan.included_files)}",
        f"- 移除条目：{len(plan.removed_entries)}",
        "",
        "## 移除 / 替换",
        "",
    ]
    for entry in plan.removed_entries:
        lines.append(f"- {entry.content_id} — {entry.reason}")
        for file in entry.files:
            lines.append(f"  - {file}")
    project_exclusions = [
        (path, reason)
        for path, reason in plan.excluded_files
        if not any(path in entry.files for entry in plan.removed_entries)
    ]
    if project_exclusions:
        lines.extend(["", "## 移除的文件", ""])
        for path, reason in project_exclusions:
            lines.append(f"- {path} — {reason}")
    lines.extend(["", "## 包含", ""])
    for entry in plan.entries:
        if entry.action == "include":
            lines.append(f"- {entry.content_id}")
    lines.append("")
    return "\n".join(lines)


def build_public_archive(
    destination: Path | str,
    project_root: Path | str = ROOT,
    stages: tuple[Stage, ...] = STAGES,
    generated_at: str | None = None,
) -> PublicBuildPlan:
    """Write the public content archive and return the plan that produced it.

    Fails closed: any plan problem or any audit violation raises
    :class:`PublicBuildError` and leaves no partial archive behind.
    """
    plan = plan_public_build(stages, project_root)
    if not plan.ok:
        raise PublicBuildError(plan.problems)

    root = Path(project_root)
    destination = Path(destination)
    shipped_at = generated_at or date.today().isoformat()
    exclusions = json.dumps(
        _exclusions_payload(plan, shipped_at), ensure_ascii=False, indent=2
    )
    content = _content_markdown(plan, shipped_at)

    temporary = destination.with_name(destination.name + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in plan.included_files:
                archive.write(root / relative, arcname=relative)
            archive.writestr("public_exclusions.json", exclusions)
            archive.writestr("PUBLIC_CONTENT.md", content)
        with zipfile.ZipFile(temporary) as archive:
            violations = audit_package(plan, archive.namelist())
        if violations:
            raise PublicBuildError(violations)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return plan
