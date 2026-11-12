"""Disk-derived score library: real files, real readiness, no manifest.

The library is rebuilt from two folders plus `curriculum.STAGES` whenever the
page is shown:

- built-in scores under `pc/resources/scores`;
- user imports under the app-config `scores` folder.

A piece is 可跟随 only when `parse_score` succeeds during the build. A valid
extension is never enough. Planned cards come only from Stage.pieces and are
never playable. There is no persisted index. The only cache is in-memory and
keyed by (resolved path, mtime_ns, size), so adding, deleting or rewriting a
file changes the next build; a restart starts cold. Failed parses are never
cached, so repairing a corrupt file is picked up immediately.

Imports are local-only. They are content-addressed for dedupe, copied
atomically with sanitized original names, and removed only from inside the
import folder. User files never get a license claim.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePath
from typing import Iterable

from .curriculum import SCORE_DIR, STAGES
from .note_engine import midi_name
from .score import Score, ScoreError, parse_score

SUPPORTED_SUFFIXES = (".musicxml", ".mxl", ".xml", ".mid", ".midi")
XML_SUFFIXES = (".musicxml", ".mxl", ".xml")
MIDI_SUFFIXES = (".mid", ".midi")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
PDF_SUFFIXES = (".pdf",)
DISPLAY_SUFFIXES = IMAGE_SUFFIXES + PDF_SUFFIXES
IMPORT_SUFFIXES = SUPPORTED_SUFFIXES + DISPLAY_SUFFIXES
EXT_RANK = {".musicxml": 0, ".mxl": 1, ".xml": 2, ".mid": 3, ".midi": 4}
MAX_IMPORT_BYTES = 12 * 1024 * 1024
META_FILE = "library_meta.json"
META_VERSION = 1
RECENT_LIMIT = 12
MAX_SCAN_FILES = 5000
MAX_SCAN_DIRS = 1000
MAX_SCAN_DEPTH = 8

VIEW_READY = "ready"
VIEW_IMPORTED = "imported"
VIEW_FAVORITES = "favorites"
VIEW_RECENT = "recent"
VIEW_ALL = "all"
VIEW_PLANNED = "planned"
DEFAULT_VIEW = VIEW_READY
VIEW_ORDER = (
    (VIEW_READY, "可跟谱"),
    (VIEW_FAVORITES, "收藏"),
    (VIEW_RECENT, "最近"),
    (VIEW_IMPORTED, "我的导入"),
    (VIEW_ALL, "全部"),
    (VIEW_PLANNED, "制作中"),
)

BADGE_MUSICXML = "MusicXML · 可跟随"
BADGE_MIDI = "MIDI · 可跟随"
BADGE_PLANNED = "制作中"
BADGE_FAILED = "解析失败"
BADGE_IMAGE = "图片 · 仅显示"
BADGE_PDF = "PDF · 仅显示"

_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class StageRef:
    stage_index: int
    stage_name: str
    item_name: str
    item_kind: str  # "training" | "piece"


@dataclass(frozen=True)
class ScoreFacts:
    title: str
    composer: str
    rights: str
    tempo: float
    time_signature: tuple[int, int]
    note_count: int
    measures: int
    duration: float
    min_midi: int
    max_midi: int
    format: str

    @property
    def range_label(self) -> str:
        return f"{midi_name(self.min_midi)}–{midi_name(self.max_midi)}"


@dataclass(frozen=True)
class LibraryFile:
    path: Path
    origin: str              # "builtin" | "imported"
    family: str              # "xml" | "midi"
    declared_format: str     # "MusicXML" | "MIDI"
    sha256: str              # imports only; "" for built-ins
    facts: ScoreFacts | None
    error: str | None
    duplicate_paths: tuple[Path, ...] = ()
    rel_dir: str = ""

    @property
    def parsed(self) -> bool:
        return self.facts is not None

    @property
    def display_format(self) -> str:
        return self.facts.format if self.facts is not None else self.declared_format

    @property
    def all_paths(self) -> tuple[Path, ...]:
        return (self.path, *self.duplicate_paths)


@dataclass(frozen=True)
class LibraryPiece:
    key: str
    title: str
    origin: str              # "builtin" | "imported" | "planned"
    status: str              # "ready" | "failed" | "planned"
    badge: str
    primary: LibraryFile | None
    files: tuple[LibraryFile, ...]
    facts: ScoreFacts | None
    stage_refs: tuple[StageRef, ...] = ()
    item_meta: str = ""
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def playable(self) -> bool:
        return (
            self.status == "ready"
            and self.primary is not None
            and self.primary.parsed
        )

    @property
    def paths(self) -> tuple[Path, ...]:
        seen: set[Path] = set()
        ordered: list[Path] = []
        for file in self.files:
            for path in file.all_paths:
                key = _norm_path(path)
                if key not in seen:
                    seen.add(key)
                    ordered.append(path)
        return tuple(ordered)

    @property
    def import_paths(self) -> tuple[Path, ...]:
        return self.paths if self.origin == "imported" else ()

    @property
    def stage_indexes(self) -> tuple[int, ...]:
        return tuple(sorted({ref.stage_index for ref in self.stage_refs}))


@dataclass(frozen=True)
class LibraryRegistry:
    pieces: tuple[LibraryPiece, ...]
    builtin_dir: Path
    import_dir: Path
    warnings: tuple[str, ...] = ()

    def select(
        self,
        view: str = DEFAULT_VIEW,
        query: str = "",
        meta: LibraryMeta | None = None,
    ) -> tuple[LibraryPiece, ...]:
        if view not in {key for key, _label in VIEW_ORDER}:
            raise ValueError(f"unknown library view: {view}")
        if view == VIEW_READY:
            selected = [p for p in self.pieces if p.status == "ready"]
        elif view == VIEW_IMPORTED:
            selected = [p for p in self.pieces if p.origin == "imported"]
        elif view == VIEW_PLANNED:
            selected = [p for p in self.pieces if p.status == "planned"]
        elif view == VIEW_FAVORITES:
            keys = meta.favorites if meta is not None else set()
            selected = [p for p in self.pieces if p.key in keys]
        elif view == VIEW_RECENT:
            order = meta.recent if meta is not None else []
            by_key = {p.key: p for p in self.pieces}
            selected = [by_key[key] for key in order if key in by_key]
        else:
            selected = list(self.pieces)
        needle = _search_key(query)
        if needle:
            tag_key = lambda piece: " ".join(
                meta.tags_for(piece.key) if meta is not None else ()
            )
            selected = [
                p
                for p in selected
                if needle in _piece_search_key(p)
                or needle in _search_key(tag_key(p))
            ]
        return tuple(selected)

    def counts(self) -> dict[str, int]:
        return {
            "ready": sum(1 for p in self.pieces if p.status == "ready"),
            "imported": sum(1 for p in self.pieces if p.origin == "imported"),
            "planned": sum(1 for p in self.pieces if p.status == "planned"),
            "failed": sum(1 for p in self.pieces if p.status == "failed"),
            "all": len(self.pieces),
        }

    def piece(self, key: str) -> LibraryPiece | None:
        for piece in self.pieces:
            if piece.key == key:
                return piece
        return None


@dataclass(frozen=True)
class ImportResult:
    kind: str                # "imported" | "duplicate" | "rejected"
    path: Path | None
    title: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.kind in ("imported", "duplicate")


@dataclass(frozen=True)
class RemoveResult:
    removed: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class LibraryMeta:
    """User-side library metadata; never affects whether a score parses."""

    favorites: set[str] = field(default_factory=set)
    tags: dict[str, list[str]] = field(default_factory=dict)
    recent: list[str] = field(default_factory=list)

    def is_favorite(self, key: str) -> bool:
        return key in self.favorites

    def toggle_favorite(self, key: str) -> bool:
        if key in self.favorites:
            self.favorites.discard(key)
            return False
        self.favorites.add(key)
        return True

    def tags_for(self, key: str) -> tuple[str, ...]:
        return tuple(self.tags.get(key, ()))

    def set_tags(self, key: str, tags: Iterable[str]) -> tuple[str, ...]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            tag = _WHITESPACE.sub(" ", str(raw)).strip()
            folded = tag.casefold()
            if not tag or folded in seen:
                continue
            seen.add(folded)
            cleaned.append(tag)
            if len(cleaned) >= 8:
                break
        if cleaned:
            self.tags[key] = cleaned
        else:
            self.tags.pop(key, None)
        return tuple(cleaned)

    def touch_recent(self, key: str) -> None:
        self.recent = [item for item in self.recent if item != key]
        self.recent.insert(0, key)
        del self.recent[RECENT_LIMIT:]

    def to_dict(self) -> dict:
        return {
            "version": META_VERSION,
            "favorites": sorted(self.favorites),
            "tags": {key: list(value) for key, value in sorted(self.tags.items())},
            "recent": list(self.recent),
        }

    @classmethod
    def from_dict(cls, raw) -> "LibraryMeta":
        meta = cls()
        if not isinstance(raw, dict):
            return meta
        favorites = raw.get("favorites")
        if isinstance(favorites, list):
            meta.favorites = {
                str(key) for key in favorites if isinstance(key, str) and key
            }
        tags = raw.get("tags")
        if isinstance(tags, dict):
            for key, values in tags.items():
                if not isinstance(key, str) or not isinstance(values, list):
                    continue
                meta.set_tags(key, [str(value) for value in values])
        recent = raw.get("recent")
        if isinstance(recent, list):
            cleaned: list[str] = []
            for key in recent:
                if isinstance(key, str) and key and key not in cleaned:
                    cleaned.append(key)
            meta.recent = cleaned[:RECENT_LIMIT]
        return meta

    @classmethod
    def load(cls, path: Path | str) -> "LibraryMeta":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(raw)

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".tmp-{uuid.uuid4().hex}-{path.name}")
        try:
            temp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp, path)
        finally:
            _unlink_quietly(temp)


# -- public entry points ---------------------------------------------------


def default_import_dir() -> Path:
    """The app-config `scores` folder, next to learning.json.

    QStandardPaths is imported lazily so the pure registry tests never need a
    QApplication.
    """
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    root = Path(base) if base else Path.home() / ".config" / "KeyBorad"
    return root / "scores"


def default_meta_path(import_dir: str | Path | None = None) -> Path:
    """Metadata lives next to the import folder, not inside the scan root."""
    root = Path(import_dir) if import_dir is not None else default_import_dir()
    return root.parent / META_FILE


class ScoreParseCache:
    """Bounded LRU of parsed score facts, invalidated by stat changes.

    Only successful parses are stored: a corrupt file is re-read on every
    build, so fixing it is seen immediately. The key includes the resolved
    path, so same-stem files in different folders never collide.
    """

    def __init__(self, max_entries: int = MAX_SCAN_FILES * 2):
        # Both scans can each yield MAX_SCAN_FILES. A smaller bound would
        # evict the oldest entries before a full sequential rescan reaches
        # them, turning every refresh into a full re-parse (LRU thrash).
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _key(path: Path | str, stat_key: tuple) -> tuple:
        normalized = os.path.normcase(os.path.abspath(str(path)))
        return (normalized, *stat_key)

    def get(self, path: Path | str, stat_key: tuple):
        key = self._key(path, stat_key)
        try:
            value = self._entries.pop(key)
        except KeyError:
            self.misses += 1
            return None
        self._entries[key] = value
        self.hits += 1
        return value

    def put(
        self,
        path: Path | str,
        stat_key: tuple,
        facts: ScoreFacts,
        error: str | None,
    ) -> None:
        key = self._key(path, stat_key)
        self._entries[key] = (facts, error)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0


DEFAULT_PARSE_CACHE = ScoreParseCache()


def build_registry(
    builtin_dir: str | Path | None = None,
    import_dir: str | Path | None = None,
    parse_cache: ScoreParseCache | None = None,
) -> LibraryRegistry:
    builtin = Path(builtin_dir) if builtin_dir is not None else SCORE_DIR
    imports = Path(import_dir) if import_dir is not None else default_import_dir()
    return _RegistryBuilder(builtin, imports, parse_cache).build()


def import_score(
    source: str | Path,
    import_dir: str | Path | None = None,
    max_bytes: int = MAX_IMPORT_BYTES,
) -> ImportResult:
    src = Path(source)
    name = src.name or str(src)
    if not src.exists():
        return ImportResult("rejected", None, src.stem, f"文件不存在：{name}")
    if not src.is_file():
        return ImportResult("rejected", None, src.stem, f"不能导入文件夹：{name}")
    if src.is_symlink():
        return ImportResult("rejected", None, src.stem, f"不能导入符号链接：{name}")
    suffix = src.suffix.lower()
    if suffix not in IMPORT_SUFFIXES:
        return ImportResult(
            "rejected",
            None,
            src.stem,
            f"不支持 {suffix or '该文件'}；请使用 MusicXML、MIDI，"
            "或图片/PDF（仅显示）。",
        )
    try:
        size = src.stat().st_size
    except OSError as exc:
        return ImportResult("rejected", None, src.stem, f"无法读取文件：{exc}")
    if size <= 0:
        return ImportResult("rejected", None, src.stem, f"文件为空：{name}")
    if size > max_bytes:
        limit = max_bytes / (1024 * 1024)
        return ImportResult(
            "rejected", None, src.stem, f"文件超过 {limit:g} MB 上限：{name}"
        )

    target_dir = Path(import_dir) if import_dir is not None else default_import_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ImportResult("rejected", None, src.stem, f"无法写入曲库目录：{exc}")
    if not target_dir.is_dir():
        return ImportResult("rejected", None, src.stem, "无法写入曲库目录：路径不是文件夹")

    try:
        data = src.read_bytes()
    except OSError as exc:
        return ImportResult("rejected", None, src.stem, f"无法读取文件：{exc}")

    digest = hashlib.sha256(data).hexdigest()
    duplicate = _existing_import(digest, target_dir)
    if duplicate is not None:
        return ImportResult("duplicate", duplicate, duplicate.stem, None)

    safe_name = sanitize_import_name(src.name)
    if PurePath(safe_name).suffix.lower() not in IMPORT_SUFFIXES:
        # Defensive: never store an extensionless file that the scanner and
        # remover would both ignore.
        safe_name = f"score{suffix}"
    stored_name = _free_import_name(target_dir, safe_name)
    destination = target_dir / stored_name
    temp = target_dir / f".tmp-{uuid.uuid4().hex}{suffix}"
    try:
        temp.write_bytes(data)
    except OSError as exc:
        _unlink_quietly(temp)
        return ImportResult("rejected", None, src.stem, f"无法写入曲库目录：{exc}")
    try:
        os.replace(temp, destination)
    except OSError as exc:
        _unlink_quietly(temp)
        return ImportResult("rejected", None, src.stem, f"无法写入曲库目录：{exc}")

    if suffix in DISPLAY_SUFFIXES:
        return ImportResult("imported", destination, src.stem, None)
    facts, error = _parse_facts(destination)
    title = facts.title if facts is not None else src.stem
    return ImportResult("imported", destination, title, error)


def remove_imports(
    paths: Iterable[str | Path], import_dir: str | Path
) -> RemoveResult:
    root = Path(import_dir).resolve()
    removed: list[Path] = []
    errors: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw)
        # Dedupe lexically: resolving first would collapse a symlink onto its
        # target and hide the symlink-specific rejection.
        key = _lexical_path(path)
        if key in seen:
            continue
        seen.add(key)
        name = path.name
        if path.is_symlink():
            errors.append(f"拒绝删除符号链接：{name}")
            continue
        lexical = path.absolute()
        ancestor = lexical.parent
        escaped = False
        while ancestor != root and ancestor != ancestor.parent:
            if ancestor.is_symlink():
                escaped = True
                break
            ancestor = ancestor.parent
        if escaped:
            errors.append(f"拒绝删除符号链接目录中的文件：{name}")
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"拒绝删除曲库外的文件：{name}")
            continue
        if resolved.suffix.lower() not in IMPORT_SUFFIXES:
            errors.append(f"拒绝删除非曲谱文件：{name}")
            continue
        if not resolved.exists():
            removed.append(resolved)
            continue
        if not resolved.is_file():
            errors.append(f"不是文件：{name}")
            continue
        try:
            resolved.unlink()
        except OSError as exc:
            errors.append(f"无法删除 {name}：{exc}")
            continue
        removed.append(resolved)
    return RemoveResult(tuple(removed), tuple(errors))


def sanitize_import_name(filename: str) -> str:
    # Take the suffix from the original name BEFORE stripping leading dots or
    # spaces, otherwise " .musicxml" becomes an extensionless "musicxml".
    name = PurePath(filename).name
    path = PurePath(name)
    suffix = path.suffix.lower()
    if suffix not in IMPORT_SUFFIXES:
        suffix = ""
    stem = path.stem if path.suffix else name
    stem = _INVALID_NAME_CHARS.sub("_", stem)
    stem = _WHITESPACE.sub(" ", stem).strip(" .")
    if stem.upper() in _RESERVED_WINDOWS_NAMES:
        stem = f"_{stem}"
    if not stem:
        stem = "score"
    if len(stem) > 80:
        stem = stem[:80].rstrip(" .")
    return f"{stem}{suffix}" if suffix else stem


def score_facts(score: Score) -> ScoreFacts:
    return ScoreFacts(
        title=_clean(score.title) or "未命名曲目",
        composer=_clean(score.composer) or "未标注作曲",
        rights=_clean(score.rights) or "未标注",
        tempo=float(score.tempo),
        time_signature=tuple(score.time_signature),
        note_count=len(score.notes),
        measures=score.measure_count or len({note.measure for note in score.notes}),
        duration=float(score.duration),
        min_midi=score.min_midi,
        max_midi=score.max_midi,
        format=_clean(score.format) or "MusicXML",
    )


# -- registry build --------------------------------------------------------


class _RegistryBuilder:
    def __init__(
        self,
        builtin_dir: Path,
        import_dir: Path,
        parse_cache: ScoreParseCache | None = None,
    ):
        self.builtin_dir = builtin_dir
        self.import_dir = import_dir
        self._parse_cache = (
            parse_cache if parse_cache is not None else DEFAULT_PARSE_CACHE
        )
        self.warnings: list[str] = []

    def _facts(self, path: Path) -> tuple[ScoreFacts | None, str | None]:
        try:
            stat = path.stat()
            stat_key = (
                stat.st_mtime_ns,
                stat.st_size,
                getattr(stat, "st_ino", 0),
            )
        except OSError:
            return _parse_facts(path)
        cached = self._parse_cache.get(path, stat_key)
        if cached is not None:
            return cached
        facts, error = _parse_facts(path)
        if facts is not None:
            self._parse_cache.put(path, stat_key, facts, None)
        return facts, error

    def build(self) -> LibraryRegistry:
        builtin_files = self._scan(self.builtin_dir, "builtin", warn_missing=True)
        imported_files = _dedupe_imports(
            self._scan(
                self.import_dir,
                "imported",
                warn_missing=False,
                recursive=True,
            )
        )
        score_builtin = [
            file
            for file in builtin_files
            if file.family in ("xml", "midi")
        ]
        scanned_paths = {_norm_path(file.path) for file in score_builtin}
        scanned_stems = {file.path.stem.casefold() for file in score_builtin}
        exact_refs, stem_refs = self._stage_index(scanned_paths, scanned_stems)

        pieces: list[LibraryPiece] = []
        seen: set[str] = set()
        self._add_file_cards(builtin_files, "builtin", pieces, seen)
        self._add_file_cards(imported_files, "imported", pieces, seen)
        self._add_planned(pieces, seen, scanned_paths, scanned_stems)

        # The first built-in card for a stem owns that stem's fallback stage
        # refs (used when the declared MusicXML is gone but its MIDI remains).
        first_by_stem: dict[str, str] = {}
        for piece in pieces:
            if (
                piece.origin != "builtin"
                or not piece.files
                or piece.status == "display"
            ):
                continue
            primary = piece.primary
            if primary is None or primary.family not in ("xml", "midi"):
                continue
            stem = primary.path.stem.casefold()
            first_by_stem.setdefault(stem, piece.key)

        # Planned cards already carry their stage ref; file cards get refs by
        # exact path, or by stem for the primary card when the declared file
        # itself was not scanned.
        pieces = [
            piece
            if piece.origin == "planned"
            else replace(
                piece,
                stage_refs=_refs_for(piece, exact_refs, stem_refs, first_by_stem),
            )
            for piece in pieces
        ]
        return LibraryRegistry(
            pieces=tuple(pieces),
            builtin_dir=self.builtin_dir,
            import_dir=self.import_dir,
            warnings=tuple(self.warnings),
        )

    def _scan(
        self,
        root: Path,
        origin: str,
        warn_missing: bool,
        recursive: bool = False,
    ) -> list[LibraryFile]:
        if not root.exists():
            if warn_missing:
                self.warnings.append(f"内置曲谱目录不存在：{root}")
            return []
        if not root.is_dir():
            self.warnings.append(f"曲谱路径不是文件夹：{root}")
            return []
        try:
            if recursive:
                entries: list[Path] = []
                dir_count = 0
                truncated = False
                root_resolved = root.resolve()
                for directory, dirnames, filenames in os.walk(root):
                    depth = len(
                        Path(directory).relative_to(root).parts
                    )
                    if depth > MAX_SCAN_DEPTH:
                        dirnames[:] = []
                        continue
                    dir_count += 1
                    if dir_count > MAX_SCAN_DIRS:
                        truncated = True
                        break
                    kept: list[str] = []
                    for name in sorted(dirnames):
                        if name.startswith("."):
                            continue
                        candidate = Path(directory) / name
                        try:
                            if candidate.is_symlink():
                                continue
                            candidate.resolve().relative_to(root_resolved)
                        except (OSError, ValueError):
                            continue
                        kept.append(name)
                    dirnames[:] = kept
                    for name in sorted(filenames):
                        if len(entries) >= MAX_SCAN_FILES:
                            truncated = True
                            break
                        candidate = Path(directory) / name
                        try:
                            if candidate.is_symlink():
                                continue
                            candidate.resolve().relative_to(root_resolved)
                        except (OSError, ValueError):
                            continue
                        entries.append(candidate)
                    if truncated:
                        break
                if truncated:
                    self.warnings.append(
                        f"曲库文件过多，只扫描了前 {MAX_SCAN_FILES} 个文件"
                    )
            else:
                entries = sorted(
                    root.iterdir(), key=lambda path: path.name.casefold()
                )
        except OSError as exc:
            self.warnings.append(f"无法读取曲谱目录 {root.name}：{exc}")
            return []
        files: list[LibraryFile] = []
        for path in entries:
            name = path.name
            if name.startswith(".") or name.startswith(".tmp-"):
                continue
            if path.is_symlink():
                self.warnings.append(f"跳过符号链接：{name}")
                continue
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            suffix = path.suffix.lower()
            if suffix not in IMPORT_SUFFIXES:
                continue
            try:
                rel_dir = path.parent.relative_to(root).as_posix()
            except ValueError:
                rel_dir = ""
            files.append(self._file(path, origin, suffix, rel_dir))
        return files

    def _file(
        self, path: Path, origin: str, suffix: str, rel_dir: str = ""
    ) -> LibraryFile:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if suffix in XML_SUFFIXES:
            family = "xml"
            declared = "MusicXML"
        elif suffix in MIDI_SUFFIXES:
            family = "midi"
            declared = "MIDI"
        elif suffix in IMAGE_SUFFIXES:
            family = "image"
            declared = "图片"
        else:
            family = "pdf"
            declared = "PDF"
        sha = ""
        if origin == "imported":
            try:
                sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except OSError as exc:
                return LibraryFile(
                    resolved,
                    origin,
                    family,
                    declared,
                    "",
                    None,
                    f"无法读取文件：{exc}",
                    rel_dir=rel_dir,
                )
        if family in ("image", "pdf"):
            return LibraryFile(
                resolved,
                origin,
                family,
                declared,
                sha,
                None,
                None,
                rel_dir=rel_dir,
            )
        facts, error = self._facts(resolved)
        return LibraryFile(
            resolved,
            origin,
            family,
            declared,
            sha,
            facts,
            error,
            rel_dir=rel_dir,
        )

    def _stage_index(
        self, scanned_paths: set[str], scanned_stems: set[str]
    ) -> tuple[dict[str, list[StageRef]], dict[str, list[StageRef]]]:
        """Exact-path refs plus same-stem fallback refs.

        The fallback keeps a curriculum item attached when its declared
        MusicXML is gone but a same-stem MIDI was scanned. A declared file
        that exists but was not scanned (subfolder, dotfile, symlink) is not
        a representation and is reported by `_add_planned` instead.
        """
        exact: dict[str, list[StageRef]] = {}
        by_stem: dict[str, list[StageRef]] = {}
        for stage in STAGES:
            for kind, items in (("training", stage.trainings), ("piece", stage.pieces)):
                for item in items:
                    if not item.score:
                        continue
                    candidate = self.builtin_dir / item.score
                    key = _norm_path(candidate)
                    ref = StageRef(stage.index, stage.name, item.name, kind)
                    if key in scanned_paths:
                        exact.setdefault(key, []).append(ref)
                        continue
                    stem = PurePath(item.score).stem.casefold()
                    if stem in scanned_stems:
                        by_stem.setdefault(stem, []).append(ref)
                        continue
                    if kind == "training":
                        self.warnings.append(
                            f"课程训练谱面缺失：{stage.name} · {item.name}（{item.score}）"
                        )
        return exact, by_stem

    def _add_file_cards(
        self,
        files: list[LibraryFile],
        origin: str,
        pieces: list[LibraryPiece],
        seen: set[str],
    ) -> None:
        display = [
            file for file in files if file.family in ("image", "pdf")
        ]
        score_files = [
            file for file in files if file.family in ("xml", "midi")
        ]
        for file in display:
            self._add_display_card(origin, file, pieces, seen)
        groups: dict[tuple[str, str], list[LibraryFile]] = {}
        for file in score_files:
            group_key = (file.rel_dir, file.path.stem.casefold())
            groups.setdefault(group_key, []).append(file)
        for rel_dir, stem in sorted(groups):
            group = groups[(rel_dir, stem)]
            xml = sorted(
                (f for f in group if f.family == "xml"),
                key=_file_rank,
            )
            midi = sorted(
                (f for f in group if f.family == "midi"),
                key=_file_rank,
            )
            selected = [f for f in (xml[0] if xml else None, midi[0] if midi else None) if f]
            extras = xml[1:] + midi[1:]
            self._add_pair_card(origin, stem, selected, pieces, seen, rel_dir)
            for extra in extras:
                self._add_pair_card(origin, stem, [extra], pieces, seen, rel_dir)

    def _add_display_card(
        self,
        origin: str,
        file: LibraryFile,
        pieces: list[LibraryPiece],
        seen: set[str],
    ) -> None:
        badge = BADGE_IMAGE if file.family == "image" else BADGE_PDF
        relative = (
            f"{file.rel_dir}/{file.path.name}"
            if file.rel_dir
            else file.path.name
        )
        base = f"display:{origin}:{relative.casefold()}"
        pieces.append(
            LibraryPiece(
                key=_unique_key(base, seen),
                title=file.path.stem or "未命名",
                origin=origin,
                status="display",
                badge=badge,
                primary=file,
                files=(file,),
                facts=None,
            )
        )

    def _add_pair_card(
        self,
        origin: str,
        stem: str,
        files: list[LibraryFile],
        pieces: list[LibraryPiece],
        seen: set[str],
        rel_dir: str = "",
    ) -> None:
        if not files:
            return
        xml = next((f for f in files if f.family == "xml"), None)
        midi = next((f for f in files if f.family == "midi"), None)
        canonical = None
        for candidate in (xml, midi):
            if candidate is not None and candidate.parsed:
                canonical = candidate
                break
        if canonical is None:
            canonical = xml or midi

        warnings: list[str] = []
        if canonical is midi and xml is not None and not xml.parsed:
            warnings.append("MusicXML 解析失败 · 已改用 MIDI")
        if canonical is xml and midi is not None and not midi.parsed:
            warnings.append("MIDI 示例解析失败 · 已忽略")

        if canonical is not None and canonical.parsed:
            status = "ready"
            facts = canonical.facts
            badge = BADGE_MIDI if canonical.display_format == "MIDI" else BADGE_MUSICXML
            title = facts.title if facts is not None else stem
            error = None
        else:
            status = "failed"
            facts = None
            badge = BADGE_FAILED
            title = stem or "未命名曲谱"
            error = (canonical.error if canonical is not None else None) or "无法解析曲谱"

        base = f"{origin}:{rel_dir}:{stem}" if rel_dir else f"{origin}:{stem}"
        key = _unique_key(base, seen)
        pieces.append(
            LibraryPiece(
                key=key,
                title=title,
                origin=origin,
                status=status,
                badge=badge,
                primary=canonical,
                files=tuple(files),
                facts=facts,
                warnings=tuple(warnings),
                error=error,
            )
        )

    def _add_planned(
        self,
        pieces: list[LibraryPiece],
        seen: set[str],
        scanned_paths: set[str],
        scanned_stems: set[str],
    ) -> None:
        for stage in STAGES:
            for item in stage.pieces:
                path = self.builtin_dir / item.score if item.score else None
                represented = False
                if item.score and path is not None:
                    represented = (
                        _norm_path(path) in scanned_paths
                        or PurePath(item.score).stem.casefold() in scanned_stems
                    )
                if represented:
                    continue
                warning = ""
                if item.score and path is not None:
                    try:
                        on_disk = path.exists()
                    except OSError:
                        on_disk = False
                    if on_disk:
                        warning = f"谱面无法扫描 · {item.score}"
                        self.warnings.append(
                            f"课程曲目谱面无法扫描：{stage.name} · {item.name}（{item.score}）"
                        )
                    else:
                        warning = f"谱面资源缺失 · {item.score}"
                        self.warnings.append(
                            f"课程曲目谱面缺失：{stage.name} · {item.name}（{item.score}）"
                        )
                base = f"planned:{stage.index}:{item.name.casefold()}"
                pieces.append(
                    LibraryPiece(
                        key=_unique_key(base, seen),
                        title=item.name,
                        origin="planned",
                        status="planned",
                        badge=BADGE_PLANNED,
                        primary=None,
                        files=(),
                        facts=None,
                        stage_refs=(
                            StageRef(stage.index, stage.name, item.name, "piece"),
                        ),
                        item_meta=item.meta,
                        warnings=(warning,) if warning else (),
                    )
                )


def _dedupe_imports(files: list[LibraryFile]) -> list[LibraryFile]:
    # Scope identical-content folding to the same stem. Folding globally can
    # make an unrelated same-bytes file (e.g. aaa.mid) the canonical and steal
    # song.mid out of its own MusicXML+MIDI pair.
    by_key: dict[tuple[str, str], list[LibraryFile]] = {}
    loose: list[LibraryFile] = []
    for file in files:
        if file.sha256:
            key = (file.path.stem.casefold(), file.sha256)
            by_key.setdefault(key, []).append(file)
        else:
            loose.append(file)
    result: list[LibraryFile] = []
    for group in by_key.values():
        group.sort(key=_file_rank)
        canonical = group[0]
        duplicates = tuple(f.path for f in group[1:])
        result.append(replace(canonical, duplicate_paths=duplicates))
    result.extend(loose)
    return result


def _file_rank(file: LibraryFile) -> tuple:
    return (
        not file.parsed,
        EXT_RANK.get(file.path.suffix.lower(), 99),
        file.path.name.casefold(),
    )


def _existing_import(digest: str, import_dir: Path) -> Path | None:
    if not import_dir.is_dir():
        return None
    paths: list[Path] = []
    root_resolved = import_dir.resolve()
    try:
        for directory, dirnames, filenames in os.walk(import_dir):
            kept = []
            for name in sorted(dirnames):
                if name.startswith("."):
                    continue
                candidate = Path(directory) / name
                try:
                    if candidate.is_symlink():
                        continue
                    candidate.resolve().relative_to(root_resolved)
                except (OSError, ValueError):
                    continue
                kept.append(name)
            dirnames[:] = kept
            for name in sorted(filenames):
                candidate = Path(directory) / name
                try:
                    if candidate.is_symlink():
                        continue
                    candidate.resolve().relative_to(root_resolved)
                except (OSError, ValueError):
                    continue
                paths.append(candidate)
    except OSError:
        return None
    for path in paths:
        name = path.name
        if name.startswith(".") or name.startswith(".tmp-"):
            continue
        if path.is_symlink():
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        if path.suffix.lower() not in IMPORT_SUFFIXES:
            continue
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                return path
        except OSError:
            continue
    return None


def _free_import_name(import_dir: Path, name: str) -> str:
    path = PurePath(name)
    suffix = path.suffix
    stem = path.stem
    candidate = name
    index = 2
    while (import_dir / candidate).exists():
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    return candidate


def _parse_facts(path: Path) -> tuple[ScoreFacts | None, str | None]:
    try:
        score = parse_score(path)
    except ScoreError as exc:
        return None, str(exc)
    except OSError as exc:
        return None, f"无法读取文件：{exc}"
    except Exception as exc:  # one bad user file must never take the page down
        return None, f"解析异常（{type(exc).__name__}）：{path.name}"
    try:
        return score_facts(score), None
    except Exception as exc:
        return None, f"解析异常（{type(exc).__name__}）：{path.name}"


def _refs_for(
    piece: LibraryPiece,
    exact_refs: dict[str, list[StageRef]],
    stem_refs: dict[str, list[StageRef]],
    first_by_stem: dict[str, str],
) -> tuple[StageRef, ...]:
    found: list[StageRef] = []
    seen: set[tuple[int, str, str]] = set()

    def add(ref: StageRef) -> None:
        marker = (ref.stage_index, ref.item_name, ref.item_kind)
        if marker in seen:
            return
        seen.add(marker)
        found.append(ref)

    for path in piece.paths:
        for ref in exact_refs.get(_norm_path(path), ()):
            add(ref)

    if not found and piece.origin == "builtin" and piece.files:
        stem = piece.files[0].path.stem.casefold()
        if first_by_stem.get(stem) == piece.key:
            for ref in stem_refs.get(stem, ()):
                add(ref)

    found.sort(
        key=lambda r: (r.stage_index, 0 if r.item_kind == "training" else 1, r.item_name)
    )
    return tuple(found)


def _piece_search_key(piece: LibraryPiece) -> str:
    parts = [
        piece.title,
        piece.badge,
        piece.item_meta,
        piece.error or "",
        *piece.warnings,
    ]
    if piece.facts is not None:
        parts.extend(
            [
                piece.facts.composer,
                piece.facts.rights,
                piece.facts.format,
                piece.facts.range_label,
            ]
        )
    for ref in piece.stage_refs:
        parts.extend([ref.stage_name, ref.item_name, f"阶段{ref.stage_index}"])
    return _search_key(" ".join(parts))


def _search_key(text: str) -> str:
    return "".join(text.split()).casefold()


def _unique_key(base: str, seen: set[str]) -> str:
    key = base
    index = 2
    while key in seen:
        key = f"{base}#{index}"
        index += 1
    seen.add(key)
    return key


def _norm_path(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve()))
    except OSError:
        return os.path.normcase(str(path))


def _lexical_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
