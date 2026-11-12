"""Validate the built-in beginner content batch and its wiring."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from score_writer import write_score  # noqa: E402

from app.core.accompaniment import split_accompaniment
from app.core.curriculum import (
    SCORE_DIR,
    STAGES,
    mapping_for_library_path,
    mapping_for_score,
)
from app.core.library import VIEW_PLANNED, build_registry
from app.core.mapping import MappingSpec, PRESET_BY_KEY
from app.core.score import parse_score
from app.core.window import plan_windows

# title -> (MusicXML file, stage index)
EXPECTED = {
    "C 大调音阶上下行": ("scale_c_major_updown.musicxml", 3),
    "二度与三度音程": ("intervals_seconds_thirds.musicxml", 3),
    "连奏与断奏对比": ("legato_staccato.musicxml", 3),
    "C–F–G 和弦": ("chords_cfg.musicxml", 4),
    "分解和弦 · 4/4": ("arpeggio_4_4.musicxml", 4),
    "左右分区 · 8 小节": ("split_hands_8bars.musicxml", 5),
    "慢速合手 · 50%": ("ode_to_joy_both_slow.musicxml", 5),
    "固定伴奏型": ("fixed_accompaniment.musicxml", 5),
    "小星星 · 自动左手": ("twinkle_auto_accompaniment.musicxml", 5),
    "欢乐颂 · 自动左手": ("ode_auto_accompaniment.musicxml", 5),
    "两只老虎 · 自动左手": ("two_tigers_auto_accompaniment.musicxml", 5),
    "小步舞曲": ("minuet_3_4.musicxml", 5),
    "乐句起落": ("phrasing_8bars.musicxml", 6),
    "速度阶梯 60→100%": ("tempo_ladder_60.musicxml", 6),
    "致爱丽丝 · 主题": ("fur_elise_theme.musicxml", 6),
    "梦中的婚礼 · 片段": ("mariage_fragment.musicxml", 6),
    "两只老虎": ("two_tigers.musicxml", 0),
    "伦敦桥": ("london_bridge.musicxml", 0),
    "小蜜蜂": ("lightly_row.musicxml", 0),
    "欢乐颂": ("ode_to_joy.musicxml", 3),
    "铃儿响叮当": ("jingle_bells.musicxml", 3),
    "卡农片段 · 简易版": ("canon_easy.musicxml", 4),
    "送别": ("farewell.musicxml", 4),
    "欢乐颂 · 双手版": ("ode_to_joy_both.musicxml", 5),
    "五指位置 · G/F": ("five_finger_gf_8bars.musicxml", 3),
    "3/4 华尔兹 · 左手": ("minuet_3_4.musicxml", 4),
    "反向与平行 · 8 小节": ("contrary_parallel_8bars.musicxml", 5),
    "连奏/断奏/重音": ("legato_staccato.musicxml", 6),
    "延音踏板 · 和弦转换": ("fixed_accompaniment.musicxml", 6),
    "弱起与反复 · 8 小节": ("pickup_repeat_8bars.musicxml", 6),
    "玛丽有只小羊羔": ("mary_had_a_little_lamb.musicxml", 0),
    "老麦克唐纳": ("old_macdonald.musicxml", 0),
    "友谊地久天长": ("auld_lang_syne.musicxml", 3),
    "勃拉姆斯摇篮曲": ("brahms_lullaby.musicxml", 3),
}


class ContentTest(unittest.TestCase):
    def test_every_musicxml_has_matching_midi_and_parses(self) -> None:
        xml_files = sorted(SCORE_DIR.glob("*.musicxml"))
        self.assertTrue(xml_files)
        for xml_path in xml_files:
            midi_path = xml_path.with_suffix(".mid")
            self.assertTrue(midi_path.is_file(), f"{xml_path.name} missing .mid")
            xml_score = parse_score(xml_path)
            midi_score = parse_score(midi_path)
            self.assertGreater(len(xml_score.notes), 0)
            self.assertEqual(len(xml_score.notes), len(midi_score.notes))
            xml_notes = [
                (note.midi, round(note.start, 2), round(note.duration, 2), note.measure)
                for note in xml_score.notes
            ]
            midi_notes = [
                (note.midi, round(note.start, 2), round(note.duration, 2), note.measure)
                for note in midi_score.notes
            ]
            self.assertEqual(xml_notes, midi_notes, xml_path.name)
            self.assertAlmostEqual(
                xml_score.duration, midi_score.duration, delta=0.1
            )

            # Wide two-hand content (the split exercise) is played with the
            # 左右分区 preset; everything else fits the default chromatic map.
            plan = plan_windows(xml_score, PRESET_BY_KEY["chromatic"])
            if any(segment.unplayable for segment in plan.segments):
                plan = plan_windows(xml_score, PRESET_BY_KEY["split"])
            for segment in plan.segments:
                self.assertEqual(
                    segment.unplayable,
                    0,
                    f"{xml_path.name} segment {segment.index} has unplayable notes",
                )

    def test_beginner_batch_is_wired_into_curriculum(self) -> None:
        found: dict[str, tuple[str | None, int, bool]] = {}
        for stage in STAGES:
            for item in stage.items:
                if item.name in EXPECTED:
                    found[item.name] = (item.score, stage.index, item.ready)
        for title, (filename, stage_index) in EXPECTED.items():
            self.assertIn(title, found)
            score, actual_stage, ready = found[title]
            self.assertEqual(score, filename)
            self.assertEqual(actual_stage, stage_index)
            # A public checkout omits the private score; the item then stays
            # planned instead of claiming readiness for a missing asset.
            self.assertEqual(
                ready, (SCORE_DIR / filename).is_file(), title
            )

    def test_scale_exercise_has_eight_bars_and_c5_c6_range(self) -> None:
        item = next(
            item
            for item in STAGES[3].trainings
            if item.name == "C 大调音阶上下行"
        )
        self.assertEqual(item.score, "scale_c_major_updown.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 24)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 84),
        )

    def test_interval_exercise_has_eight_bars_and_c5_c6_range(self) -> None:
        item = next(
            item
            for item in STAGES[3].trainings
            if item.name == "二度与三度音程"
        )
        self.assertEqual(item.score, "intervals_seconds_thirds.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 30)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 84),
        )

    def test_legato_staccato_exercise_has_gaps_and_eighths(self) -> None:
        item = next(
            item
            for item in STAGES[3].trainings
            if item.name == "连奏与断奏对比"
        )
        self.assertEqual(item.score, "legato_staccato.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 31)
        self.assertEqual(max(note.measure for note in score.notes), 8)

        # Bars 1–4 are contiguous quarter notes (legato); bars 5–8 contain
        # eighth notes separated by rests (staccato).
        legato = [note for note in score.notes if note.measure <= 4]
        staccato = [note for note in score.notes if note.measure >= 5]
        self.assertEqual(len(legato), 16)
        self.assertTrue(
            all(abs(note.duration - 0.75) < 0.01 for note in legato)
        )
        self.assertTrue(
            any(abs(note.duration - 0.375) < 0.01 for note in staccato)
        )

    def test_chord_exercise_has_eight_three_note_onsets(self) -> None:
        item = next(
            item
            for item in STAGES[4].trainings
            if item.name == "C–F–G 和弦"
        )
        self.assertEqual(item.score, "chords_cfg.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 24)
        self.assertEqual(max(note.measure for note in score.notes), 8)

        onsets: dict[float, list[int]] = {}
        for note in score.notes:
            onsets.setdefault(round(note.start, 2), []).append(note.midi)
        self.assertEqual(len(onsets), 8)
        self.assertTrue(all(len(midis) == 3 for midis in onsets.values()))
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 86),
        )

    def test_arpeggio_exercise_has_eight_bars_and_c5_g6_range(self) -> None:
        item = next(
            item
            for item in STAGES[4].trainings
            if item.name == "分解和弦 · 4/4"
        )
        self.assertEqual(item.score, "arpeggio_4_4.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 32)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 91),
        )

    def test_split_hands_exercise_needs_the_split_preset(self) -> None:
        item = next(
            item
            for item in STAGES[5].trainings
            if item.name == "左右分区 · 8 小节"
        )
        self.assertEqual(item.score, "split_hands_8bars.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(max(note.measure for note in score.notes), 8)

        split_plan = plan_windows(score, PRESET_BY_KEY["split"])
        self.assertEqual(
            sum(segment.unplayable for segment in split_plan.segments), 0
        )
        default_plan = plan_windows(score, PRESET_BY_KEY["chromatic"])
        self.assertGreater(
            sum(segment.unplayable for segment in default_plan.segments), 0
        )

    def test_slow_hands_together_is_half_tempo(self) -> None:
        item = next(
            item
            for item in STAGES[5].trainings
            if item.name == "慢速合手 · 50%"
        )
        self.assertEqual(item.score, "ode_to_joy_both_slow.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        fast = parse_score(SCORE_DIR / "ode_to_joy_both.musicxml")
        self.assertEqual(score.tempo, 40)
        self.assertEqual(len(score.notes), len(fast.notes))
        self.assertEqual(max(note.measure for note in score.notes), 8)

    def test_fixed_accompaniment_covers_eight_bars(self) -> None:
        item = next(
            item
            for item in STAGES[5].trainings
            if item.name == "固定伴奏型"
        )
        self.assertEqual(item.score, "fixed_accompaniment.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (67, 79),
        )

    def assert_auto_accompaniment_piece(
        self,
        item,
        filename: str,
        bars: int,
        accompaniment_count: int,
        practice_count: int,
        lo: int,
        hi: int,
    ) -> None:
        """Shared contract for H7e right-hand + auto-left content."""
        self.assertEqual(item.score, filename)
        self.assertEqual(item.accompaniment, "P2")
        self.assertTrue(item.ready)

        score = parse_score(SCORE_DIR / item.score)
        practice, accompaniment = split_accompaniment(score, item.accompaniment)
        self.assertEqual(len(accompaniment), accompaniment_count)
        self.assertEqual(len(practice.notes), practice_count)
        self.assertTrue(all(note.part == "P2" for note in accompaniment))
        self.assertTrue(all(note.midi < 65 for note in accompaniment))
        self.assertEqual(
            (
                min(note.midi for note in practice.notes),
                max(note.midi for note in practice.notes),
            ),
            (lo, hi),
        )
        self.assertEqual(max(note.measure for note in score.notes), bars)

        # The practiced right hand fits the default mapping; the left hand is
        # below it and therefore can never be judged by accident.
        plan = plan_windows(practice, PRESET_BY_KEY["chromatic"])
        self.assertEqual(
            sum(segment.unplayable for segment in plan.segments), 0
        )

    def test_auto_accompaniment_keeps_the_left_hand_out_of_practice(self) -> None:
        item = next(
            item
            for item in STAGES[5].trainings
            if item.name == "小星星 · 自动左手"
        )
        self.assert_auto_accompaniment_piece(
            item, "twinkle_auto_accompaniment.musicxml", 12, 24, 42, 72, 81
        )

    def test_ode_auto_accompaniment_is_right_hand_only_practice(self) -> None:
        item = next(
            item
            for item in STAGES[5].pieces
            if item.name == "欢乐颂 · 自动左手"
        )
        self.assert_auto_accompaniment_piece(
            item, "ode_auto_accompaniment.musicxml", 8, 16, 30, 72, 79
        )

    def test_two_tigers_auto_accompaniment_is_right_hand_only(self) -> None:
        item = next(
            item
            for item in STAGES[5].pieces
            if item.name == "两只老虎 · 自动左手"
        )
        self.assert_auto_accompaniment_piece(
            item, "two_tigers_auto_accompaniment.musicxml", 8, 16, 27, 72, 81
        )

    def test_declared_mappings_are_valid(self) -> None:
        for stage in STAGES:
            for item in stage.items:
                if not item.mapping:
                    continue
                if isinstance(item.mapping, str):
                    self.assertIn(item.mapping, PRESET_BY_KEY, item.name)
                else:
                    self.assertIsInstance(item.mapping, MappingSpec, item.name)
                    item.mapping.to_preset()

        split = next(
            item
            for item in STAGES[5].trainings
            if item.name == "左右分区 · 8 小节"
        )
        self.assertIsInstance(split.mapping, MappingSpec)
        self.assertEqual(split.mapping.split.bar, 16)
        self.assertEqual(split.mapping.split.left.base, 48)
        self.assertEqual(split.mapping.split.right.base, 72)

    def test_library_mapping_lookup_finds_the_declaration(self) -> None:
        direct = mapping_for_score("split_hands_8bars")
        self.assertIsInstance(direct, MappingSpec)
        self.assertEqual(direct.split.bar, 16)
        self.assertIsInstance(
            mapping_for_score("split_hands_8bars.musicxml"), MappingSpec
        )
        self.assertEqual(mapping_for_score("xiaoxingxing.musicxml"), "")
        self.assertEqual(mapping_for_score("not-a-piece.mid"), "")

        builtin = SCORE_DIR / "split_hands_8bars.musicxml"
        self.assertIsInstance(
            mapping_for_library_path(builtin), MappingSpec
        )

    def test_imported_file_does_not_inherit_a_builtin_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imported = Path(tmp) / "split_hands_8bars.musicxml"
            imported.write_text("<score/>", encoding="utf-8")
            self.assertEqual(mapping_for_library_path(imported), "")

    def test_minuet_is_three_four(self) -> None:
        item = next(
            item for item in STAGES[5].pieces if item.name == "小步舞曲"
        )
        self.assertEqual(item.score, "minuet_3_4.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(score.time_signature, (3, 4))
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(len(score.notes), 44)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (65, 79),
        )

    def test_phrasing_exercise_has_a_breath(self) -> None:
        item = next(
            item
            for item in STAGES[6].trainings
            if item.name == "乐句起落"
        )
        self.assertEqual(item.score, "phrasing_8bars.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(len(score.notes), 22)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 81),
        )

    def test_tempo_ladder_starts_at_60(self) -> None:
        item = next(
            item
            for item in STAGES[6].trainings
            if item.name == "速度阶梯 60→100%"
        )
        self.assertEqual(item.score, "tempo_ladder_60.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(score.tempo, 60)
        self.assertEqual(len(score.notes), 26)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 79),
        )

    def test_fur_elise_theme_is_three_four_with_accidentals(self) -> None:
        item = next(
            item
            for item in STAGES[6].pieces
            if item.name == "致爱丽丝 · 主题"
        )
        self.assertEqual(item.score, "fur_elise_theme.musicxml")
        self.assertTrue(item.ready)
        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(score.time_signature, (3, 4))
        self.assertEqual(len(score.notes), 24)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        midis = {note.midi for note in score.notes}
        self.assertIn(75, midis)  # D#5
        self.assertEqual((min(midis), max(midis)), (69, 84))

    def test_private_mariage_fragment_is_marked(self) -> None:
        item = next(
            item
            for item in STAGES[6].pieces
            if item.name == "梦中的婚礼 · 片段"
        )
        self.assertEqual(item.visibility, "private")
        self.assertEqual(item.score, "mariage_fragment.musicxml")
        path = SCORE_DIR / item.score
        if not path.is_file():
            # The public repository deliberately omits this private score.
            self.assertFalse(item.ready)
            return
        self.assertTrue(item.ready)
        score = parse_score(path)
        self.assertEqual(len(score.notes), 26)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (72, 85),
        )

    def test_ready_score_items_have_xml_and_midi(self) -> None:
        for stage in STAGES:
            for item in stage.items:
                if not item.ready or item.score is None:
                    continue
                path = SCORE_DIR / item.score
                self.assertTrue(path.is_file(), f"{stage.index}:{item.name}")
                self.assertTrue(
                    path.with_suffix(".mid").is_file(),
                    f"{stage.index}:{item.name} missing MIDI",
                )

    def test_new_pieces_are_not_planned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_registry(SCORE_DIR, Path(tmp) / "imports")
            planned = {piece.title for piece in registry.select(VIEW_PLANNED)}
            for title, (filename, _stage) in EXPECTED.items():
                if not (SCORE_DIR / filename).is_file():
                    continue  # private content is absent from public checkouts
                self.assertNotIn(title, planned)


class ScoreWriterTest(unittest.TestCase):
    def test_accidental_notes_round_trip(self) -> None:
        measures = (
            (("D#", 5, 1), ("D", 5, 1), ("Bb", 4, 1), ("B", 4, 1)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_score(Path(tmp), "acc", "t", "c", "r", 60, measures)
            score = parse_score(Path(tmp) / "acc.musicxml")
        self.assertEqual(
            [note.midi for note in score.notes], [75, 74, 70, 71]
        )

    def test_three_four_time_signature_round_trip(self) -> None:
        measures = (
            (("C", 5, 1), ("D", 5, 1), ("E", 5, 1)),
            (("C", 5, 2), ("E", 5, 1)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_score(
                Path(tmp),
                "waltz",
                "t",
                "c",
                "r",
                60,
                measures,
                beats_per_measure=3,
            )
            score = parse_score(Path(tmp) / "waltz.musicxml")
        self.assertEqual(score.time_signature, (3, 4))
        self.assertEqual(len(score.notes), 5)
        self.assertEqual(max(note.measure for note in score.notes), 2)

    def test_chord_cells_round_trip_as_same_onset(self) -> None:
        measures = ((
            ((("C", 5), ("E", 5), ("G", 5)), 4),
        ),)
        with tempfile.TemporaryDirectory() as tmp:
            write_score(Path(tmp), "chord", "t", "c", "r", 60, measures)
            score = parse_score(Path(tmp) / "chord.musicxml")
        self.assertEqual(len(score.notes), 3)
        self.assertEqual({note.midi for note in score.notes}, {72, 76, 79})
        self.assertEqual(
            {round(note.start, 2) for note in score.notes}, {0.0}
        )
        self.assertEqual(
            {round(note.duration, 2) for note in score.notes}, {4.0}
        )

    def test_eighth_notes_and_rests_round_trip(self) -> None:
        measures = (
            (
                ("C", 4, 0.5),
                (None, None, 0.5),
                ("D", 4, 1),
                (None, None, 1),
                ("E", 4, 1),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            # 60 BPM makes one beat one second, so the expected values are
            # directly the note's beat position/duration.
            write_score(Path(tmp), "rests", "t", "c", "r", 60, measures)
            score = parse_score(Path(tmp) / "rests.musicxml")
        self.assertEqual(
            [
                (note.midi, round(note.start, 2), round(note.duration, 2))
                for note in score.notes
            ],
            [(60, 0.0, 0.5), (62, 1.0, 1.0), (64, 3.0, 1.0)],
        )


class RemainingPracticeTest(unittest.TestCase):
    @staticmethod
    def _item(stage_index: int, name: str):
        return next(
            item for item in STAGES[stage_index].trainings if item.name == name
        )

    @staticmethod
    def _guide(stage_index: int, title: str):
        return next(
            guide for guide in STAGES[stage_index].guides
            if guide.title == title
        )

    def test_gf_position_exercise_moves_the_same_five_finger_shape(self) -> None:
        item = self._item(3, "五指位置 · G/F")
        self.assertEqual(item.score, "five_finger_gf_8bars.musicxml")
        self.assertTrue(item.ready)
        self.assertEqual(self._guide(3, "五指位置 G/F").practice, item.name)

        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual(max(note.measure for note in score.notes), 8)
        self.assertEqual(
            (min(note.midi for note in score.notes),
             max(note.midi for note in score.notes)),
            (65, 74),
        )
        # F position needs B♭4, written on the B line.
        flat = next(note for note in score.notes if note.midi == 70)
        self.assertEqual((flat.step, flat.alter), ("B", -1))

    def test_contrary_parallel_exercise_moves_in_both_directions(self) -> None:
        item = self._item(5, "反向与平行 · 8 小节")
        self.assertEqual(item.score, "contrary_parallel_8bars.musicxml")
        self.assertTrue(item.ready)
        self.assertEqual(self._guide(5, "反向/平行进行").practice, item.name)

        score = parse_score(SCORE_DIR / item.score)
        self.assertEqual({note.voice for note in score.notes}, {"1", "2"})
        self.assertEqual(max(note.measure for note in score.notes), 8)

        def direction(measure: int, voice: str) -> int:
            notes = sorted(
                (
                    note for note in score.notes
                    if note.measure == measure and note.voice == voice
                ),
                key=lambda note: note.start,
            )
            return (notes[-1].midi > notes[0].midi) - (
                notes[-1].midi < notes[0].midi
            )

        for measure in (1, 2, 3):
            self.assertEqual(
                direction(measure, "1"), direction(measure, "2")
            )
        for measure in (5, 6, 7):
            self.assertNotEqual(
                direction(measure, "1"), direction(measure, "2")
            )

    def test_stage4_and_6_missing_practices_are_wired(self) -> None:
        waltz = self._item(4, "3/4 华尔兹 · 左手")
        self.assertEqual(waltz.score, "minuet_3_4.musicxml")
        self.assertTrue(waltz.ready)
        self.assertEqual(self._guide(4, "3/4 华尔兹").practice, waltz.name)

        legato = self._item(6, "连奏/断奏/重音")
        self.assertEqual(legato.score, "legato_staccato.musicxml")
        self.assertTrue(legato.ready)
        self.assertEqual(
            self._guide(6, "连奏/断奏/重音").practice, legato.name
        )

        pedal = self._item(6, "延音踏板 · 和弦转换")
        self.assertEqual(pedal.score, "fixed_accompaniment.musicxml")
        self.assertTrue(pedal.ready)
        self.assertEqual(self._guide(6, "延音踏板").practice, pedal.name)

        pickup = self._item(6, "弱起与反复 · 8 小节")
        self.assertEqual(pickup.score, "pickup_repeat_8bars.musicxml")
        self.assertTrue(pickup.ready)
        self.assertEqual(
            self._guide(6, "弱起、收尾、反复").practice, pickup.name
        )
        score = parse_score(SCORE_DIR / pickup.score)
        self.assertEqual(score.measure_count, 13)
        self.assertGreater(score.notes[0].start, 0.0)  # enters on beat 4
        first_a = [n.midi for n in score.notes if 2 <= n.measure <= 5]
        repeat_a = [n.midi for n in score.notes if 6 <= n.measure <= 9]
        self.assertEqual(first_a, repeat_a)

    def test_recording_review_opens_a_project_task(self) -> None:
        item = self._item(6, "录音自评")
        self.assertEqual(item.project, "stage6_record_review")
        self.assertIsNotNone(item.task)
        self.assertTrue(item.ready)
        self.assertEqual(self._guide(6, "录音与自评").practice, item.name)

    def test_stage1_bass_clef_and_stage5_loop_are_wired(self) -> None:
        bass = self._item(1, "低音谱号 · C3–C4")
        self.assertEqual(bass.drill, "note_names_bass_c3_c4")
        self.assertTrue(bass.ready)
        self.assertEqual(self._guide(1, "低音谱号").practice, bass.name)

        loop = self._item(5, "困难小节循环 · 小步舞曲")
        self.assertEqual(loop.score, "minuet_3_4.musicxml")
        self.assertTrue(loop.ready)
        self.assertEqual(
            self._guide(5, "困难小节循环").practice, loop.name
        )


if __name__ == "__main__":
    unittest.main()
