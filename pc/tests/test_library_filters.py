"""Library difficulty/key/kind filters and user playlists (B4, no Qt)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.library import (
    LibraryFilters,
    LibraryMeta,
    LibraryPiece,
    LibraryRegistry,
    ScoreFacts,
    StageRef,
)


def facts(
    measures: int = 8,
    low: int = 60,
    high: int = 72,
    fifths: int = 0,
) -> ScoreFacts:
    return ScoreFacts(
        title="T",
        composer="",
        rights="",
        tempo=120.0,
        time_signature=(4, 4),
        note_count=10,
        measures=measures,
        duration=16.0,
        min_midi=low,
        max_midi=high,
        format="MusicXML",
        key_fifths=fifths,
    )


def piece(
    key: str,
    *,
    stage: int | None = None,
    kind: str = "piece",
    origin: str = "builtin",
    status: str = "ready",
    data: ScoreFacts | None = None,
    title: str = "曲目",
) -> LibraryPiece:
    refs = ()
    if stage is not None:
        refs = (StageRef(stage, f"阶段 {stage}", "练习", kind),)
    return LibraryPiece(
        key=key,
        title=title,
        origin=origin,
        status=status,
        badge="",
        primary=None,
        files=(),
        facts=data,
        stage_refs=refs,
    )


class PieceFilterFieldsTest(unittest.TestCase):
    def test_difficulty_uses_the_curriculum_stage_first(self) -> None:
        self.assertEqual(piece("a", stage=0, data=facts(40)).difficulty, "入门")
        self.assertEqual(piece("b", stage=4).difficulty, "初级")
        self.assertEqual(piece("c", stage=6).difficulty, "中级")
        self.assertEqual(piece("d", stage=8).difficulty, "高级")

    def test_imported_pieces_derive_difficulty_from_the_score(self) -> None:
        self.assertEqual(
            piece("a", origin="imported", data=facts(4, 60, 67)).difficulty,
            "入门",
        )
        self.assertEqual(
            piece("b", origin="imported", data=facts(12, 60, 76)).difficulty,
            "初级",
        )
        self.assertEqual(
            piece("c", origin="imported", data=facts(24, 55, 80)).difficulty,
            "中级",
        )
        self.assertEqual(
            piece("d", origin="imported", data=facts(40, 48, 84)).difficulty,
            "高级",
        )

    def test_key_and_kind_labels(self) -> None:
        self.assertEqual(piece("a", data=facts(fifths=0)).key_label, "C")
        self.assertEqual(piece("b", data=facts(fifths=-1)).key_label, "F")
        self.assertEqual(piece("c", data=facts(fifths=2)).key_label, "D")
        self.assertEqual(piece("d", data=facts(fifths=99)).key_label, "")

        self.assertEqual(piece("e", stage=1, kind="training").kind_label, "训练")
        self.assertEqual(piece("f", stage=3, kind="piece").kind_label, "曲目")
        self.assertEqual(
            piece("g", origin="imported", data=facts()).kind_label, "导入"
        )
        self.assertEqual(piece("h", status="planned").kind_label, "制作中")


class RegistryFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pieces = (
            piece("beginner", stage=0, kind="training", data=facts(4)),
            piece("early", stage=3, kind="piece", data=facts(8, fifths=2)),
            piece("middle", stage=5, kind="piece", data=facts(16, fifths=-1)),
            piece("advanced", stage=8, kind="piece", data=facts(32, fifths=0)),
            piece(
                "imported",
                origin="imported",
                data=facts(24, 55, 80, fifths=3),
            ),
        )
        self.registry = LibraryRegistry(
            pieces=self.pieces,
            builtin_dir=Path("/builtin"),
            import_dir=Path("/import"),
        )

    def keys(self, **kwargs) -> list[str]:
        return [item.key for item in self.registry.select(**kwargs)]

    def test_filters_compose_with_the_view_and_search(self) -> None:
        self.assertEqual(
            self.keys(filters=LibraryFilters(difficulty="入门")),
            ["beginner"],
        )
        self.assertEqual(
            self.keys(filters=LibraryFilters(kind="曲目")),
            ["early", "middle", "advanced"],
        )
        self.assertEqual(
            self.keys(filters=LibraryFilters(key_label="F")), ["middle"]
        )
        self.assertEqual(
            self.keys(
                filters=LibraryFilters(difficulty="中级", kind="导入"),
            ),
            ["imported"],
        )
        self.assertEqual(
            self.keys(filters=LibraryFilters(difficulty="入门"), query="no"),
            [],
        )

    def test_playlist_membership_limits_the_selection(self) -> None:
        keys = {"early", "advanced"}
        self.assertEqual(
            self.keys(playlist_keys=keys), ["early", "advanced"]
        )
        self.assertEqual(
            self.keys(
                playlist_keys=keys,
                filters=LibraryFilters(key_label="D"),
            ),
            ["early"],
        )


class PlaylistMetaTest(unittest.TestCase):
    def test_add_remove_and_persist(self) -> None:
        meta = LibraryMeta()
        self.assertTrue(meta.set_playlist_membership("练习", "a", True))
        self.assertTrue(meta.set_playlist_membership("练习", "b", True))
        self.assertEqual(meta.playlist_keys("练习"), {"a", "b"})
        self.assertEqual(meta.playlists_for("a"), ("练习",))

        self.assertFalse(meta.set_playlist_membership("练习", "a", False))
        self.assertEqual(meta.playlist_keys("练习"), {"b"})
        self.assertFalse(meta.set_playlist_membership("练习", "b", False))
        self.assertEqual(meta.playlist_names(), ())

        meta.set_playlist_membership("  我的   歌单 ", "a", True)
        self.assertEqual(meta.playlist_names(), ("我的 歌单",))

        raw = meta.to_dict()
        restored = LibraryMeta.from_dict(raw)
        self.assertEqual(restored.playlist_keys("我的 歌单"), {"a"})

    def test_prune_key_cleans_every_metadata_section(self) -> None:
        meta = LibraryMeta()
        meta.favorites.add("k")
        meta.set_tags("k", ["练习"])
        meta.touch_recent("k")
        meta.set_playlist_membership("歌单", "k", True)

        meta.prune_key("k")

        self.assertEqual(meta.favorites, set())
        self.assertEqual(meta.tags_for("k"), ())
        self.assertEqual(meta.recent, [])
        self.assertEqual(meta.playlist_names(), ())

    def test_playlist_limits(self) -> None:
        meta = LibraryMeta()
        for index in range(25):
            meta.set_playlist_membership(f"p{index}", "a", True)
        self.assertEqual(len(meta.playlist_names()), 20)

        big = LibraryMeta()
        for index in range(260):
            big.set_playlist_membership("big", f"k{index}", True)
        self.assertEqual(len(big.playlist_keys("big")), 200)


if __name__ == "__main__":
    unittest.main()
