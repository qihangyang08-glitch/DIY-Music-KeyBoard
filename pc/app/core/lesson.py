"""Lesson/guide content model and Lesson JSON loading (P2-G).

A lesson follows CONTENT_SCHEMA §4 (a runtime subset): objectives, a few
knowledge blocks, steps, and a self-check. The stage page shows one card per
lesson; the course page renders the five sections from UI_DESIGN_V3 §9.3.

Loading is deliberately tolerant: a broken or incomplete JSON file never
crashes the app and never pretends to be finished. Anything missing a core
section stays ``planned`` and the UI keeps the "制作中" placeholder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

READINESS = ("planned", "drafting", "review", "ready", "deprecated")
READY = "ready"

# UI_DESIGN_V3 §9.2: one stage shows 3–8 lesson cards.
MAX_LESSONS_PER_STAGE = 8


@dataclass(frozen=True)
class KnowledgeCard:
    title: str
    body: str = ""
    asset: str = ""
    kind: str = "text"

    def has_content(self) -> bool:
        return bool(self.title.strip() and self.body.strip())


@dataclass(frozen=True)
class Guide:
    """One lesson. The first three fields keep the pre-P2-G constructor valid."""

    title: str
    minutes: int
    outline: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()
    prereq: str = ""
    cards: tuple[KnowledgeCard, ...] = ()
    demonstration: str = ""
    demo_asset: str = ""
    steps: tuple[str, ...] = ()
    mistakes: tuple[str, ...] = ()
    self_check: tuple[str, ...] = ()
    next_step: str = ""
    practice: str = ""
    readiness: str = "planned"
    visibility: str = "private"
    public_release: str = "no"
    lesson_id: str = ""
    source: str = ""

    def is_ready(self) -> bool:
        """True only when the five-section page has real content to show."""
        return (
            self.readiness == READY
            and bool(self.objectives)
            and any(card.has_content() for card in self.cards)
            and bool(self.steps)
            and bool(self.self_check)
        )


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, number)


def _strings(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            out.append(text)
    return tuple(out)


def _stage_number(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 8 else None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        for prefix in ("stage", "s"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        try:
            number = int(cleaned)
        except ValueError:
            return None
        return number if 0 <= number <= 8 else None
    return None


def _blocks(value) -> tuple[tuple[KnowledgeCard, ...], str, str, tuple[str, ...], tuple[str, ...]]:
    cards: list[KnowledgeCard] = []
    demonstration = ""
    demo_asset = ""
    steps: list[str] = []
    self_check: list[str] = []
    if not isinstance(value, (list, tuple)):
        return (), "", "", (), ()
    for block in value:
        if not isinstance(block, dict):
            continue
        kind = _text(block.get("type"))
        if kind == "text":
            title = _text(block.get("title")) or "知识卡"
            body = _text(block.get("body"))
            if body:
                cards.append(KnowledgeCard(title, body))
        elif kind == "image":
            title = _text(block.get("caption")) or "图示"
            alt = _text(block.get("alt"))
            asset = _text(block.get("src"))
            if alt or asset:
                cards.append(KnowledgeCard(title, alt, asset, kind="image"))
        elif kind in ("staff", "roll"):
            title = _text(block.get("caption")) or "谱例"
            alt = _text(block.get("alt"))
            asset = _text(block.get("score"))
            if alt or asset:
                cards.append(KnowledgeCard(title, alt, asset, kind=kind))
        elif kind == "demo":
            demonstration = _text(block.get("caption")) or "听示范"
            demo_asset = _text(block.get("score"))
        elif kind == "steps":
            steps.extend(_strings(block.get("items")))
        elif kind == "checklist":
            self_check.extend(_strings(block.get("items")))
        # compare / glossary / quiz stay design-only until a later batch.
    return tuple(cards), demonstration, demo_asset, tuple(steps), tuple(self_check)


def _checks(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = _text(item)
        elif isinstance(item, dict):
            text = _text(item.get("question"))
        else:
            text = ""
        if text:
            out.append(text)
    return tuple(out)


def guide_from_dict(data, *, source: str = "") -> Guide | None:
    """Build a Guide from one Lesson JSON object, tolerating bad fields."""
    if not isinstance(data, dict):
        return None
    title = _text(data.get("title"))
    if not title:
        return None
    cards, demonstration, demo_asset, steps, checklist = _blocks(data.get("blocks"))
    self_check = checklist + _checks(data.get("check"))
    status = _text(data.get("status"))
    readiness = status if status in READINESS else "planned"
    visibility = "public" if _text(data.get("visibility")) == "public" else "private"
    public_release = (
        "yes" if _text(data.get("public_release")) == "yes" else "no"
    )
    return Guide(
        title=title,
        minutes=_int(data.get("duration_min", data.get("minutes"))),
        outline=_strings(data.get("outline")),
        objectives=_strings(data.get("objectives")),
        prereq="、".join(_strings(data.get("prerequisites"))),
        cards=cards,
        demonstration=demonstration,
        demo_asset=demo_asset,
        steps=steps,
        mistakes=_strings(data.get("mistakes")),
        self_check=self_check,
        next_step=_text(data.get("next")),
        practice=_text(data.get("practice")),
        readiness=readiness,
        visibility=visibility,
        public_release=public_release,
        lesson_id=_text(data.get("id")),
        source=source,
    )


def load_lesson(path: Path | str, stage_index: int | None = None) -> Guide | None:
    """Load one lesson file; return None for unreadable or mismatched files."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if stage_index is not None:
        declared = _stage_number(data.get("stage")) if isinstance(data, dict) else None
        if declared is not None and declared != stage_index:
            return None
    return guide_from_dict(data, source=str(path))


def overlay_lessons(
    stage_index: int,
    guides: tuple[Guide, ...],
    directory: Path | str,
) -> tuple[Guide, ...]:
    """Replace same-title guides and append new lessons from ``stageN_*.json``.

    Files are read in name order. A malformed file is skipped. Duplicate new
    titles keep the first file; the visible card count is capped at eight.
    """
    directory = Path(directory)
    result = list(guides)
    if not directory.is_dir():
        return tuple(result[:MAX_LESSONS_PER_STAGE])
    seen = {guide.title for guide in result}
    for path in sorted(directory.glob(f"stage{stage_index}_*.json")):
        guide = load_lesson(path, stage_index)
        if guide is None:
            continue
        for index, existing in enumerate(result):
            if existing.title == guide.title:
                result[index] = guide
                break
        else:
            if guide.title in seen:
                continue
            seen.add(guide.title)
            result.append(guide)
    return tuple(result[:MAX_LESSONS_PER_STAGE])


__all__ = [
    "Guide",
    "KnowledgeCard",
    "MAX_LESSONS_PER_STAGE",
    "READINESS",
    "guide_from_dict",
    "load_lesson",
    "overlay_lessons",
]
