"""Pure tests for the disk-derived score library."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.curriculum import STAGES, PracticeItem, Stage
from app.core.library import (
    BADGE_FAILED,
    BADGE_IMAGE,
    BADGE_MIDI,
    BADGE_MUSICXML,
    BADGE_PDF,
    BADGE_PLANNED,
    SUPPORTED_SUFFIXES,
    VIEW_ALL,
    VIEW_FAVORITES,
    VIEW_IMPORTED,
    VIEW_PLANNED,
    VIEW_READY,
    VIEW_RECENT,
    LibraryMeta,
    build_registry,
    import_score,
    remove_imports,
    sanitize_import_name,
)

SAMPLE_XML = ROOT / "resources" / "scores" / "xiaoxingxing.musicxml"
SAMPLE_MID = ROOT / "resources" / "scores" / "xiaoxingxing.mid"

_STEPS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def copy_sample(dst: Path, stem: str = "xiaoxingxing", midi: bool = True) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SAMPLE_XML, dst / f"{stem}.musicxml")
    if midi:
        shutil.copyfile(SAMPLE_MID, dst / f"{stem}.mid")


def _pitch(midi: int) -> tuple[str, int, int]:
    name = _STEPS[midi % 12]
    alter = 1 if name.endswith("#") else 0
    return name[0], alter, midi // 12 - 1


def write_musicxml(
    path: Path,
    title: str = "Test",
    composer: str = "",
    rights: str = "",
    tempo: float = 100,
    measures: list[list[int]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    measures = measures or [[72]]
    parts = []
    for index, midis in enumerate(measures, start=1):
        attrs = ""
        if index == 1:
            attrs = (
                "<attributes><divisions>1</divisions><key><fifths>0</fifths></key>"
                "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            )
        sound = f'<sound tempo="{tempo}"/>' if index == 1 else ""
        notes = []
        for midi in midis:
            step, alter, octave = _pitch(midi)
            alter_xml = f"<alter>{alter}</alter>" if alter else ""
            notes.append(
                "<note><pitch>"
                f"<step>{step}</step>{alter_xml}<octave>{octave}</octave>"
                "</pitch><duration>1</duration><type>quarter</type></note>"
            )
        parts.append(
            f'<measure number="{index}">{attrs}{sound}{"".join(notes)}</measure>'
        )
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<score-partwise version=\"4.0\">"
        f"<work><work-title>{escape(title)}</work-title></work>"
        "<identification>"
        f"<creator type=\"composer\">{escape(composer)}</creator>"
        f"<rights>{escape(rights)}</rights>"
        "</identification>"
        "<part-list><score-part id=\"P1\"><part-name>Piano</part-name>"
        "</score-part></part-list>"
        f"<part id=\"P1\">{''.join(parts)}</part>"
        "</score-partwise>",
        encoding="utf-8",
    )


def write_broken_musicxml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<not-musicxml/>", encoding="utf-8")


def write_broken_midi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Header + a truncated track whose payload starts with a continuation byte.
    path.write_bytes(
        b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
        b"MTrk\x00\x00\x00\x02\x00\xff"
    )


class LibraryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.builtin = self.tmp / "builtin"
        self.imports = self.tmp / "imports"
        self.builtin.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def registry(self):
        return build_registry(self.builtin, self.imports)


class ReadyCardTest(LibraryTestCase):
    def test_sample_pair_groups_into_one_ready_card_and_facts(self) -> None:
        copy_sample(self.builtin)
        registry = self.registry()
        self.assertEqual(len(registry.select(VIEW_READY)), 1)
        self.assertEqual(
            registry.counts()["planned"],
            sum(len(stage.pieces) for stage in STAGES) - 1,
        )
        piece = registry.select(VIEW_READY)[0]
        self.assertEqual(piece.origin, "builtin")
        self.assertEqual(piece.status, "ready")
        self.assertEqual(piece.badge, BADGE_MUSICXML)
        self.assertEqual(piece.primary.path.name, "xiaoxingxing.musicxml")
        self.assertEqual(
            {p.name for p in piece.paths}, {"xiaoxingxing.musicxml", "xiaoxingxing.mid"}
        )
        facts = piece.facts
        self.assertEqual(facts.title, "小星星（片段）")
        self.assertEqual(facts.composer, "传统 / 公有领域")
        self.assertEqual(facts.rights, "Public Domain")
        self.assertEqual(facts.tempo, 100)
        self.assertEqual(facts.time_signature, (4, 4))
        self.assertEqual(facts.note_count, 42)
        self.assertEqual(facts.measures, 12)
        self.assertAlmostEqual(facts.duration, 28.8)
        self.assertEqual((facts.min_midi, facts.max_midi), (72, 81))
        self.assertEqual(facts.format, "MusicXML")
        self.assertEqual(facts.range_label, "C5–A5")

    def test_midi_only_builtin_is_ready_with_midi_badge(self) -> None:
        self.builtin.mkdir(exist_ok=True)
        shutil.copyfile(SAMPLE_MID, self.builtin / "xiaoxingxing.mid")
        piece = self.registry().select(VIEW_READY)[0]
        self.assertEqual(piece.badge, BADGE_MIDI)
        self.assertTrue(piece.primary.path.suffix == ".mid")
        self.assertTrue(piece.playable)
        self.assertEqual(piece.facts.title, "xiaoxingxing")
        self.assertEqual(piece.facts.composer, "—")
        self.assertAlmostEqual(piece.facts.duration, 28.8)

    def test_broken_musicxml_falls_back_to_midi_sibling(self) -> None:
        shutil.copyfile(SAMPLE_MID, self.builtin / "song.mid")
        write_broken_musicxml(self.builtin / "song.musicxml")
        piece = self.registry().select(VIEW_READY)[0]
        self.assertEqual(piece.badge, BADGE_MIDI)
        self.assertTrue(piece.primary.path.suffix == ".mid")
        self.assertEqual(len(piece.files), 2)
        self.assertTrue(any("MusicXML" in warning for warning in piece.warnings))

    def test_broken_pair_is_one_failed_card(self) -> None:
        write_broken_musicxml(self.builtin / "song.musicxml")
        write_broken_midi(self.builtin / "song.mid")
        registry = self.registry()
        self.assertEqual(len(registry.select(VIEW_READY)), 0)
        self.assertEqual(
            len(registry.select(VIEW_ALL)),
            sum(len(stage.pieces) for stage in STAGES) + 1,
        )
        piece = registry.select(VIEW_ALL)[0]
        self.assertEqual(piece.status, "failed")
        self.assertEqual(piece.badge, BADGE_FAILED)
        self.assertFalse(piece.playable)
        self.assertTrue(piece.error)
        self.assertEqual(len(piece.files), 2)

    def test_malformed_midi_never_crashes_registry(self) -> None:
        write_broken_midi(self.builtin / "bad.mid")
        registry = self.registry()
        failed = [p for p in registry.pieces if p.status == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0].error)

    def test_rest_only_measure_counts_toward_length(self) -> None:
        write_musicxml(
            self.builtin / "rests.musicxml",
            title="Rests",
            measures=[[], [72]],
        )
        piece = self.registry().select(VIEW_READY)[0]
        self.assertEqual(piece.title, "Rests")
        self.assertEqual(piece.facts.measures, 2)

    def test_extra_same_format_xml_files_are_separate_cards(self) -> None:
        write_musicxml(self.builtin / "song.musicxml", title="Song A")
        write_musicxml(self.builtin / "song.xml", title="Song B")
        ready = self.registry().select(VIEW_READY)
        self.assertEqual(len(ready), 2)
        self.assertEqual({p.title for p in ready}, {"Song A", "Song B"})
        self.assertEqual(len({p.key for p in ready}), 2)

    def test_extra_same_format_midi_files_are_separate_cards(self) -> None:
        shutil.copyfile(SAMPLE_MID, self.builtin / "song.mid")
        shutil.copyfile(SAMPLE_MID, self.builtin / "song.midi")
        ready = self.registry().select(VIEW_READY)
        self.assertEqual(len(ready), 2)
        self.assertEqual(len({p.key for p in ready}), 2)
        self.assertEqual(
            {p.paths[0].name for p in ready}, {"song.mid", "song.midi"}
        )


class ImportTest(LibraryTestCase):
    def test_mxl_import_parses_zip(self) -> None:
        source = self.tmp / "song.mxl"
        with zipfile.ZipFile(source, "w") as archive:
            archive.write(SAMPLE_XML, "score.xml")
        result = import_score(source, self.imports)
        self.assertEqual(result.kind, "imported")
        self.assertIsNone(result.error)
        self.assertTrue(result.path.is_file())
        piece = self.registry().select(VIEW_IMPORTED)[0]
        self.assertTrue(piece.playable)
        self.assertEqual(piece.badge, BADGE_MUSICXML)

    def test_import_copies_and_dedupes_identical_bytes(self) -> None:
        result = import_score(SAMPLE_XML, self.imports)
        self.assertEqual(result.kind, "imported")
        self.assertNotEqual(result.path.resolve(), SAMPLE_XML.resolve())
        self.assertTrue(result.path.is_file())
        self.assertTrue(SAMPLE_XML.is_file())
        self.assertEqual(len(list(self.imports.iterdir())), 1)
        self.assertEqual(len(self.registry().select(VIEW_IMPORTED)), 1)

        renamed = self.tmp / "renamed.musicxml"
        shutil.copyfile(SAMPLE_XML, renamed)
        duplicate = import_score(renamed, self.imports)
        self.assertEqual(duplicate.kind, "duplicate")
        self.assertEqual(duplicate.path.resolve(), result.path.resolve())
        self.assertEqual(len(list(self.imports.iterdir())), 1)

    def test_import_same_name_different_content_gets_suffix(self) -> None:
        first = self.tmp / "a" / "song.musicxml"
        second = self.tmp / "b" / "song.musicxml"
        write_musicxml(first, title="Song A")
        write_musicxml(second, title="Song B")
        one = import_score(first, self.imports)
        two = import_score(second, self.imports)
        self.assertEqual(one.path.name, "song.musicxml")
        self.assertEqual(two.path.name, "song-2.musicxml")
        self.assertEqual(len(self.registry().select(VIEW_IMPORTED)), 2)

    def test_import_xml_and_midi_same_stem_merge_one_card(self) -> None:
        xml_source = self.tmp / "song.musicxml"
        midi_source = self.tmp / "song.mid"
        write_musicxml(xml_source, title="Song")
        shutil.copyfile(SAMPLE_MID, midi_source)
        self.assertEqual(import_score(xml_source, self.imports).kind, "imported")
        self.assertEqual(import_score(midi_source, self.imports).kind, "imported")
        pieces = self.registry().select(VIEW_IMPORTED)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0].primary.path.suffix, ".musicxml")
        self.assertEqual(len(pieces[0].files), 2)
        self.assertTrue(pieces[0].playable)

    def test_import_parse_failure_is_kept_and_visible(self) -> None:
        source = self.tmp / "broken.musicxml"
        write_broken_musicxml(source)
        result = import_score(source, self.imports)
        self.assertEqual(result.kind, "imported")
        self.assertTrue(result.error)
        self.assertTrue(result.path.is_file())
        registry = self.registry()
        piece = registry.select(VIEW_IMPORTED)[0]
        self.assertEqual(piece.badge, BADGE_FAILED)
        self.assertFalse(piece.playable)
        self.assertEqual(len(registry.select(VIEW_READY)), 0)
        self.assertEqual(
            len(registry.select(VIEW_ALL)),
            sum(len(stage.pieces) for stage in STAGES) + 1,
        )

    def test_import_rejects_bad_sources(self) -> None:
        text = self.tmp / "note.txt"
        text.write_text("hello", encoding="utf-8")
        empty = self.tmp / "empty.musicxml"
        empty.write_bytes(b"")
        folder = self.tmp / "folder"
        folder.mkdir()
        cases = [
            import_score(text, self.imports),
            import_score(folder, self.imports),
            import_score(self.tmp / "missing.musicxml", self.imports),
            import_score(empty, self.imports),
            import_score(SAMPLE_XML, self.imports, max_bytes=1),
        ]
        for result in cases:
            self.assertEqual(result.kind, "rejected")
            self.assertTrue(result.error)
        self.assertFalse(self.imports.exists())

        blocker = self.tmp / "not_a_dir"
        blocker.write_text("x", encoding="utf-8")
        result = import_score(SAMPLE_XML, blocker)
        self.assertEqual(result.kind, "rejected")
        self.assertEqual(blocker.read_text(encoding="utf-8"), "x")


class RemoveTest(LibraryTestCase):
    def test_remove_import_deletes_all_card_files(self) -> None:
        xml_source = self.tmp / "song.musicxml"
        midi_source = self.tmp / "song.mid"
        write_musicxml(xml_source)
        shutil.copyfile(SAMPLE_MID, midi_source)
        import_score(xml_source, self.imports)
        import_score(midi_source, self.imports)
        piece = self.registry().select(VIEW_IMPORTED)[0]
        result = remove_imports(piece.import_paths, self.imports)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.removed), 2)
        for path in piece.import_paths:
            self.assertFalse(path.exists())
        self.assertEqual(len(self.registry().select(VIEW_IMPORTED)), 0)

        again = remove_imports(piece.import_paths, self.imports)
        self.assertTrue(again.ok)

    def test_remove_import_rejects_paths_outside_library(self) -> None:
        inside = import_score(SAMPLE_XML, self.imports).path
        outside = self.tmp / "outside.musicxml"
        shutil.copyfile(SAMPLE_XML, outside)
        traversal = self.imports / ".." / "outside.musicxml"
        builtin = self.builtin / "builtin.musicxml"
        shutil.copyfile(SAMPLE_XML, builtin)

        symlink = self.imports / "link.musicxml"
        try:
            os.symlink(outside, symlink)
            has_symlink = True
        except (OSError, NotImplementedError):
            has_symlink = False

        paths = [outside, traversal, builtin]
        if has_symlink:
            paths.append(symlink)
        paths.append(inside)
        result = remove_imports(paths, self.imports)
        self.assertTrue(outside.is_file())
        self.assertTrue(builtin.is_file())
        if has_symlink:
            self.assertTrue(symlink.is_symlink())
            self.assertTrue(any("符号链接" in error for error in result.errors))
        self.assertFalse(inside.exists())
        self.assertTrue(result.errors)

    def test_sanitize_import_name(self) -> None:
        unsafe = sanitize_import_name('..\\a/b<>:"|?*\x00c.musicxml')
        self.assertNotIn("/", unsafe)
        self.assertNotIn("\\", unsafe)
        for char in '<>:"|?*\x00':
            self.assertNotIn(char, unsafe)
        self.assertEqual(sanitize_import_name("CON.musicxml"), "_CON.musicxml")
        self.assertEqual(sanitize_import_name(""), "score")
        long_name = sanitize_import_name("a" * 200 + ".musicxml")
        self.assertLessEqual(len(Path(long_name).stem), 80)
        self.assertEqual(Path(long_name).suffix, ".musicxml")
        self.assertEqual(sanitize_import_name("小星星.musicxml"), "小星星.musicxml")
        self.assertEqual(sanitize_import_name(" .musicxml"), "score.musicxml")
        self.assertEqual(sanitize_import_name("..musicxml"), "score.musicxml")

    def test_dot_only_stem_import_stays_visible_and_removable(self) -> None:
        source = self.tmp / "..musicxml"
        shutil.copyfile(SAMPLE_XML, source)
        result = import_score(source, self.imports)
        self.assertEqual(result.kind, "imported")
        self.assertEqual(result.path.suffix.lower(), ".musicxml")
        piece = self.registry().select(VIEW_IMPORTED)[0]
        self.assertTrue(piece.playable)
        removed = remove_imports(piece.import_paths, self.imports)
        self.assertTrue(removed.ok)
        self.assertEqual(self.registry().select(VIEW_IMPORTED), ())


class RegistryTest(LibraryTestCase):
    def test_default_view_and_filters(self) -> None:
        copy_sample(self.builtin)
        registry = self.registry()
        self.assertEqual([p.title for p in registry.select()], ["小星星（片段）"])
        self.assertEqual(registry.select(VIEW_IMPORTED), ())
        expected_planned = sum(
            1
            for stage in STAGES
            for item in stage.pieces
            if not (item.score and (self.builtin / item.score).is_file())
        )
        self.assertEqual(len(registry.select(VIEW_PLANNED)), expected_planned)
        planned_titles = {p.title for p in registry.select(VIEW_PLANNED)}
        self.assertIn("欢乐颂", planned_titles)
        self.assertIn("铃儿响叮当", planned_titles)
        self.assertEqual(len(registry.select(VIEW_ALL)), expected_planned + 1)
        self.assertEqual(
            len({p.key for p in registry.select(VIEW_ALL)}),
            len(registry.select(VIEW_ALL)),
        )
        with self.assertRaises(ValueError):
            registry.select("nope")

    def test_planned_cards_are_stage_pieces_only(self) -> None:
        copy_sample(self.builtin)
        registry = self.registry()
        planned = registry.select(VIEW_PLANNED)
        for piece in planned:
            self.assertEqual(piece.status, "planned")
            self.assertEqual(piece.badge, BADGE_PLANNED)
            self.assertIsNone(piece.primary)
            self.assertEqual(piece.files, ())
            self.assertIsNone(piece.facts)
            self.assertFalse(piece.playable)
            self.assertTrue(piece.item_meta)
            self.assertTrue(piece.stage_refs)
        titles = {p.title for p in planned}
        self.assertNotIn("音名闪卡 · C4–C5", titles)
        self.assertNotIn("小星星（片段）", titles)
        joy = next(p for p in planned if p.title == "欢乐颂")
        self.assertEqual(joy.stage_refs[0].stage_name, "右手旋律")

    def test_stage_refs_are_unioned_and_deduplicated(self) -> None:
        copy_sample(self.builtin)
        piece = self.registry().select(VIEW_READY)[0]
        self.assertEqual(
            [(r.stage_index, r.stage_name, r.item_name, r.item_kind) for r in piece.stage_refs],
            [
                (0, "上手", "跟弹《小星星》第一句", "training"),
                (3, "右手旋律", "五指位置 · C–G", "training"),
                (3, "右手旋律", "小星星（片段）", "piece"),
            ],
        )
        self.assertEqual(piece.stage_indexes, (0, 3))

    def test_counts_are_derived(self) -> None:
        copy_sample(self.builtin)
        planned = sum(len(stage.pieces) for stage in STAGES) - 1
        self.assertEqual(
            self.registry().counts(),
            {"ready": 1, "imported": 0, "planned": planned, "failed": 0, "all": planned + 1},
        )
        write_broken_musicxml(self.imports / "bad.musicxml")
        self.assertEqual(
            self.registry().counts(),
            {
                "ready": 1,
                "imported": 1,
                "planned": planned,
                "failed": 1,
                "all": planned + 2,
            },
        )

    def test_search_combines_with_filters(self) -> None:
        copy_sample(self.builtin)
        registry = self.registry()
        self.assertEqual(len(registry.select(VIEW_READY, "小星星")), 1)
        self.assertEqual(len(registry.select(VIEW_PLANNED, "铃儿")), 1)
        self.assertGreaterEqual(len(registry.select(VIEW_PLANNED, "阶段3")), 2)
        self.assertEqual(registry.select(VIEW_READY, "欢乐颂"), ())
        self.assertEqual(len(registry.select(VIEW_ALL, "可跟随")), 1)
        self.assertEqual(registry.select(VIEW_ALL, "__none__"), ())

    def test_builtin_and_imported_copy_are_separate(self) -> None:
        copy_sample(self.builtin)
        import_score(SAMPLE_XML, self.imports)
        registry = self.registry()
        ready = registry.select(VIEW_READY)
        self.assertEqual(len(ready), 2)
        self.assertEqual(len(registry.select(VIEW_IMPORTED)), 1)
        builtin = next(p for p in ready if p.origin == "builtin")
        imported = next(p for p in ready if p.origin == "imported")
        self.assertNotEqual(builtin.primary.path, imported.primary.path)
        remove_imports(imported.import_paths, self.imports)
        self.assertEqual(len(self.registry().select(VIEW_IMPORTED)), 0)
        self.assertTrue(builtin.primary.path.is_file())

    def test_midi_only_fallback_keeps_stage_refs_and_no_duplicate_planned(self) -> None:
        shutil.copyfile(SAMPLE_MID, self.builtin / "xiaoxingxing.mid")
        registry = self.registry()
        self.assertEqual(registry.counts()["ready"], 1)
        self.assertEqual(
            registry.counts()["planned"],
            sum(len(stage.pieces) for stage in STAGES) - 1,
        )
        piece = registry.select(VIEW_READY)[0]
        self.assertEqual(piece.badge, BADGE_MIDI)
        self.assertEqual(piece.stage_indexes, (0, 3))
        self.assertEqual(len(piece.stage_refs), 3)

    def test_declared_but_unscanned_piece_becomes_planned_with_warning(self) -> None:
        stage = Stage(
            index=99,
            name="测试",
            band="基础",
            goal="",
            prereq="",
            guides=(),
            trainings=(),
            pieces=(PracticeItem("隐藏曲", "★ · 制作中", ".hidden.musicxml"),),
            pass_rule="",
            next_step="",
        )
        write_musicxml(self.builtin / ".hidden.musicxml", title="Hidden")
        with patch("app.core.library.STAGES", (stage,)):
            registry = self.registry()
        planned = registry.select(VIEW_PLANNED)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].title, "隐藏曲")
        self.assertTrue(any("无法扫描" in warning for warning in planned[0].warnings))
        self.assertTrue(any("无法扫描" in warning for warning in registry.warnings))

    def test_identical_imports_under_different_stems_do_not_steal_a_sibling(self) -> None:
        self.imports.mkdir()
        shutil.copyfile(SAMPLE_MID, self.imports / "song.mid")
        shutil.copyfile(SAMPLE_MID, self.imports / "aaa.mid")
        write_broken_musicxml(self.imports / "song.musicxml")
        registry = self.registry()
        imported = registry.select(VIEW_IMPORTED)
        self.assertEqual(len(imported), 2)
        song = next(
            p for p in imported if any(f.path.name == "song.mid" for f in p.files)
        )
        self.assertTrue(song.playable)
        self.assertEqual(song.badge, BADGE_MIDI)
        self.assertEqual(
            {f.path.name for f in song.files}, {"song.musicxml", "song.mid"}
        )
        aaa = next(
            p for p in imported if any(f.path.name == "aaa.mid" for f in p.files)
        )
        self.assertTrue(aaa.playable)
        self.assertNotEqual(aaa.key, song.key)

        result = remove_imports(aaa.import_paths, self.imports)
        self.assertTrue(result.ok)
        self.assertFalse((self.imports / "aaa.mid").exists())
        self.assertTrue((self.imports / "song.mid").is_file())

    def test_scan_does_not_create_import_dir(self) -> None:
        missing = self.tmp / "missing" / "scores"
        registry = build_registry(self.builtin, missing)
        self.assertEqual(registry.counts()["imported"], 0)
        self.assertFalse(missing.exists())
        self.assertFalse(missing.parent.exists())

    def test_missing_curriculum_score_warns_without_crashing(self) -> None:
        registry = self.registry()
        self.assertEqual(registry.counts()["ready"], 0)
        self.assertEqual(
            registry.counts()["planned"],
            sum(len(stage.pieces) for stage in STAGES),
        )
        joined = "\n".join(registry.warnings)
        self.assertIn("xiaoxingxing.musicxml", joined)
        self.assertIn("课程训练谱面缺失", joined)

        blocker = self.tmp / "imports_file"
        blocker.write_text("x", encoding="utf-8")
        registry = build_registry(self.builtin, blocker)
        self.assertTrue(any("不是文件夹" in w for w in registry.warnings))

        registry = build_registry(self.tmp / "no_such_builtin", self.imports)
        self.assertTrue(any("不存在" in w for w in registry.warnings))


class LibraryMetaTest(unittest.TestCase):
    def test_metadata_round_trips_and_is_tolerant(self) -> None:
        meta = LibraryMeta()
        self.assertTrue(meta.toggle_favorite("builtin:a"))
        meta.set_tags("builtin:a", [" 练习 ", "练习", "入门"])
        meta.touch_recent("builtin:a")
        meta.touch_recent("builtin:b")
        meta.touch_recent("builtin:a")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "library.json"
            meta.save(path)
            loaded = LibraryMeta.load(path)
            broken = Path(tmp) / "broken.json"
            broken.write_text("{oops", encoding="utf-8")
            tolerant = LibraryMeta.load(broken)

        self.assertEqual(loaded.favorites, {"builtin:a"})
        self.assertEqual(loaded.tags_for("builtin:a"), ("练习", "入门"))
        self.assertEqual(loaded.recent, ["builtin:a", "builtin:b"])
        self.assertEqual(tolerant.favorites, set())

    def test_metadata_rejects_wrong_types(self) -> None:
        meta = LibraryMeta.from_dict(
            {"favorites": "x", "tags": {"a": "b"}, "recent": [1, "a"]}
        )
        self.assertEqual(meta.favorites, set())
        self.assertEqual(meta.tags, {})
        self.assertEqual(meta.recent, ["a"])


class LibraryViewMetaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.builtin = self.root / "builtin"
        self.imports = self.root / "imports"
        self.builtin.mkdir()
        write_musicxml(self.imports / "one.musicxml", title="One")
        write_musicxml(self.imports / "two.musicxml", title="Two")
        self.registry = build_registry(self.builtin, self.imports)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_favorites_tags_and_recent_views(self) -> None:
        one, two = self.registry.select(VIEW_IMPORTED)
        meta = LibraryMeta()
        meta.toggle_favorite(two.key)
        meta.set_tags(two.key, ["演出"])
        meta.touch_recent(one.key)

        self.assertEqual(
            [p.key for p in self.registry.select(VIEW_FAVORITES, meta=meta)],
            [two.key],
        )
        self.assertEqual(
            [p.key for p in self.registry.select(VIEW_RECENT, meta=meta)],
            [one.key],
        )
        self.assertEqual(
            [p.key for p in self.registry.select(VIEW_FAVORITES, "演出", meta)],
            [two.key],
        )
        self.assertEqual(
            self.registry.select(VIEW_FAVORITES, "", meta=None), ()
        )


class RecursiveScanTest(unittest.TestCase):
    def test_same_stem_in_two_folders_stays_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            imports = root / "imports"
            builtin.mkdir()
            write_musicxml(imports / "a" / "song.musicxml", title="A")
            write_musicxml(imports / "b" / "song.musicxml", title="B")
            registry = build_registry(builtin, imports)

        imported = registry.select(VIEW_IMPORTED)
        self.assertEqual(len(imported), 2)
        self.assertEqual({piece.title for piece in imported}, {"A", "B"})
        self.assertNotEqual(imported[0].key, imported[1].key)

    def test_nested_import_folders_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            imports = root / "imports"
            builtin.mkdir()
            write_musicxml(imports / "nested" / "deep" / "song.musicxml")
            registry = build_registry(builtin, imports)

        imported = registry.select(VIEW_IMPORTED)
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].status, "ready")
        self.assertEqual(imported[0].title, "Test")


class DisplayOnlyTest(unittest.TestCase):
    def test_images_and_pdfs_are_display_only_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            imports = root / "imports"
            builtin.mkdir()
            imports.mkdir()
            (imports / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (imports / "notes.pdf").write_bytes(b"%PDF-1.4\n")
            registry = build_registry(builtin, imports)

        pieces = {piece.title: piece for piece in registry.pieces}
        self.assertEqual(pieces["cover"].status, "display")
        self.assertEqual(pieces["cover"].badge, BADGE_IMAGE)
        self.assertFalse(pieces["cover"].playable)
        self.assertEqual(pieces["notes"].badge, BADGE_PDF)
        self.assertEqual(
            [p.title for p in registry.select(VIEW_READY)], []
        )
        self.assertEqual(
            {p.title for p in registry.select(VIEW_IMPORTED)},
            {"cover", "notes"},
        )
        self.assertEqual(
            sum(1 for piece in registry.pieces if piece.status == "display"), 2
        )

    def test_nested_imports_and_display_assets_can_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            imports = root / "imports"
            nested = imports / "nested" / "song.musicxml"
            write_musicxml(nested)
            image = imports / "cover.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")

            result = remove_imports([nested, image], imports)

            self.assertTrue(result.ok)
            self.assertEqual(len(result.removed), 2)
            self.assertFalse(nested.exists())
            self.assertFalse(image.exists())

    def test_builtin_display_file_does_not_represent_a_course_piece(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            imports = Path(tmp) / "imports"
            builtin.mkdir()
            (builtin / "xiaoxingxing.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            registry = build_registry(builtin, imports)

        display = [
            piece for piece in registry.pieces if piece.status == "display"
        ][0]
        self.assertEqual(display.stage_refs, ())
        planned = [
            piece
            for piece in registry.select(VIEW_PLANNED)
            if piece.title == "小星星（片段）"
        ]
        self.assertTrue(planned)
        self.assertTrue(any("xiaoxingxing" in w for w in registry.warnings))

    def test_display_files_can_be_imported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cover.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n")
            imports = root / "imports"

            result = import_score(source, imports)

            self.assertEqual(result.kind, "imported")
            self.assertIsNone(result.error)
            self.assertTrue((imports / "cover.png").is_file())


if __name__ == "__main__":
    unittest.main()
