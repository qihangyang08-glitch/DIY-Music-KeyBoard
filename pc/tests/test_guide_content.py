"""Guide/lesson content model, JSON loading, and the five-section course page."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from app.core.curriculum import STAGES, lesson_ref_label, stage_by_index
from app.core.lesson import (
    Guide,
    KnowledgeCard,
    guide_from_dict,
    overlay_lessons,
)
from app.ui.main_window import MainWindow


def sample_lesson(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "id": "s0-l1",
        "stage": "s0",
        "index": 1,
        "title": "测试课",
        "objectives": ["目标一", "目标二"],
        "prerequisites": ["s0-l0"],
        "duration_min": 4,
        "blocks": [
            {"type": "text", "title": "知识卡", "body": "正文" * 30},
            {"type": "image", "src": "images/x.png", "alt": "图示说明", "caption": "图"},
            {"type": "demo", "score": "xiaoxingxing", "caption": "听示范"},
            {"type": "steps", "items": ["步骤一", "步骤二"]},
            {"type": "checklist", "items": ["自检一"]},
        ],
        "check": [{"question": "检查一", "type": "self"}],
        "mistakes": ["错误一"],
        "practice": "找到中央 C",
        "next": "s0-l2",
        "tags": ["测试"],
        "status": "ready",
        "visibility": "public",
        "public_release": "yes",
    }
    data.update(overrides)
    return data


class LessonJsonTest(unittest.TestCase):
    def test_documented_blocks_map_to_guide_fields(self) -> None:
        guide = guide_from_dict(sample_lesson())
        self.assertIsNotNone(guide)
        assert guide is not None
        self.assertEqual(guide.title, "测试课")
        self.assertEqual(guide.minutes, 4)
        self.assertEqual(guide.objectives, ("目标一", "目标二"))
        self.assertEqual(guide.prereq, "s0-l0")
        self.assertEqual(len(guide.cards), 2)
        self.assertEqual(guide.cards[0].title, "知识卡")
        self.assertEqual(guide.cards[1].asset, "images/x.png")
        self.assertEqual(guide.demonstration, "听示范")
        self.assertEqual(guide.steps, ("步骤一", "步骤二"))
        self.assertEqual(guide.mistakes, ("错误一",))
        self.assertIn("自检一", guide.self_check)
        self.assertIn("检查一", guide.self_check)
        self.assertEqual(guide.next_step, "s0-l2")
        self.assertEqual(guide.practice, "找到中央 C")
        self.assertEqual(guide.readiness, "ready")
        self.assertEqual(guide.visibility, "public")
        self.assertEqual(guide.public_release, "yes")
        self.assertTrue(guide.is_ready())

    def test_ready_gate_requires_core_sections(self) -> None:
        self.assertFalse(
            guide_from_dict(sample_lesson(objectives=[])).is_ready()
        )
        self.assertFalse(
            guide_from_dict(
                sample_lesson(
                    blocks=[
                        {"type": "text", "title": "空卡", "body": ""},
                        {"type": "steps", "items": ["步骤一"]},
                    ],
                    check=[{"question": "检查一"}],
                )
            ).is_ready()
        )
        self.assertFalse(
            guide_from_dict(sample_lesson(status="planned")).is_ready()
        )
        self.assertFalse(
            guide_from_dict(
                sample_lesson(blocks=[{"type": "text", "title": "卡", "body": "正文"}])
            ).is_ready()
        )

    def test_invalid_json_types_fall_back_without_crashing(self) -> None:
        self.assertIsNone(guide_from_dict(None))
        self.assertIsNone(guide_from_dict({}))
        self.assertIsNone(guide_from_dict(sample_lesson(title="   ")))
        guide = guide_from_dict(
            sample_lesson(
                blocks="not a list",
                objectives=["目标"],
                status="bogus",
                visibility="friends",
                public_release="true",
                mistakes="not a list",
                duration_min="4",
            )
        )
        assert guide is not None
        self.assertEqual(guide.readiness, "planned")
        self.assertEqual(guide.visibility, "private")
        self.assertEqual(guide.public_release, "no")
        self.assertEqual(guide.minutes, 4)
        self.assertFalse(guide.is_ready())

    def test_overlay_replaces_by_title_and_appends_new_lessons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "stage0_01.json").write_text(
                json.dumps(sample_lesson(title="A")), encoding="utf-8"
            )
            (directory / "stage0_02.json").write_text(
                json.dumps(sample_lesson(title="C")), encoding="utf-8"
            )
            (directory / "stage0_03.json").write_text("{bad json", encoding="utf-8")
            guides = overlay_lessons(
                0,
                (Guide("A", 3, ("旧",)), Guide("B", 3, ("旧",))),
                directory,
            )
        self.assertEqual([guide.title for guide in guides], ["A", "B", "C"])
        self.assertTrue(guides[0].is_ready())
        self.assertEqual(guides[1].outline, ("旧",))

    def test_overlay_caps_stage_cards_at_eight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for index in range(10):
                (directory / f"stage0_{index:02d}.json").write_text(
                    json.dumps(sample_lesson(title=f"课{index}")),
                    encoding="utf-8",
                )
            guides = overlay_lessons(0, (), directory)
        self.assertEqual(len(guides), 8)

    def test_visual_blocks_keep_their_kind(self) -> None:
        guide = guide_from_dict(
            sample_lesson(
                blocks=[
                    {"type": "text", "title": "卡", "body": "正文"},
                    {"type": "image", "src": "images/x.png", "alt": "图示说明"},
                    {
                        "type": "staff",
                        "score": "xiaoxingxing",
                        "caption": "谱例",
                        "alt": "五线谱：C4 到 G4",
                    },
                    {"type": "roll", "score": "xiaoxingxing", "caption": "落键"},
                ]
            )
        )
        assert guide is not None
        self.assertEqual(
            [card.kind for card in guide.cards],
            ["text", "image", "staff", "roll"],
        )
        self.assertEqual(guide.cards[0].asset, "")
        self.assertEqual(guide.cards[1].asset, "images/x.png")
        self.assertEqual(guide.cards[2].asset, "xiaoxingxing")

    def test_legacy_three_argument_guide_still_works(self) -> None:
        guide = Guide("旧课", 3, ("要点一", "要点二"))
        self.assertEqual(guide.title, "旧课")
        self.assertEqual(guide.outline, ("要点一", "要点二"))
        self.assertFalse(guide.is_ready())
        self.assertEqual(KnowledgeCard("卡").body, "")


class PilotContentTest(unittest.TestCase):
    def test_stage0_pilot_lessons_are_ready_and_bound(self) -> None:
        stage = stage_by_index(0)
        self.assertEqual(len(stage.guides), 3)
        ready = [guide for guide in stage.guides if guide.is_ready()]
        self.assertEqual(len(ready), 3)
        item_names = {item.name for item in stage.items}
        for guide in ready:
            self.assertTrue(guide.objectives)
            self.assertTrue(guide.cards)
            self.assertTrue(guide.steps)
            self.assertTrue(guide.self_check)
            self.assertIn(guide.practice, item_names)
            self.assertEqual(guide.readiness, "ready")
            self.assertEqual(guide.visibility, "public")
            self.assertEqual(guide.public_release, "yes")

    def test_stage1_and_2_pilot_lessons_are_ready_and_bound(self) -> None:
        for index in (1, 2):
            stage = stage_by_index(index)
            self.assertEqual(len(stage.guides), 6)
            ready = [guide for guide in stage.guides if guide.is_ready()]
            self.assertEqual(len(ready), 6, stage.name)
            item_names = {item.name for item in stage.items}
            bound = 0
            for guide in ready:
                self.assertTrue(guide.objectives)
                self.assertTrue(guide.cards)
                self.assertTrue(guide.steps)
                self.assertTrue(guide.self_check)
                self.assertEqual(guide.readiness, "ready")
                self.assertEqual(guide.visibility, "public")
                self.assertEqual(guide.public_release, "yes")
                if guide.practice:
                    self.assertIn(guide.practice, item_names, guide.title)
                    bound += 1
            # Some lessons (low clef, 6/8, syncopation) have no matching drill
            # yet; they must say so instead of binding an unrelated practice.
            self.assertGreaterEqual(bound, 3, stage.name)

    def test_stage3_and_4_lessons_are_ready_and_bound(self) -> None:
        for index in (3, 4):
            stage = stage_by_index(index)
            self.assertEqual(len(stage.guides), 8)
            ready = [guide for guide in stage.guides if guide.is_ready()]
            self.assertEqual(len(ready), 8, stage.name)
            item_names = {item.name for item in stage.items}
            bound = 0
            for guide in ready:
                self.assertTrue(guide.objectives)
                self.assertTrue(guide.cards)
                self.assertTrue(guide.steps)
                self.assertTrue(guide.self_check)
                self.assertEqual(guide.readiness, "ready")
                if guide.practice:
                    self.assertIn(guide.practice, item_names, guide.title)
                    bound += 1
            self.assertGreaterEqual(bound, 4, stage.name)

    def test_stage5_and_6_lessons_are_ready_and_bound(self) -> None:
        expected_counts = {5: 8, 6: 7}
        minimum_bound = {5: 4, 6: 2}
        for index, expected in expected_counts.items():
            stage = stage_by_index(index)
            self.assertEqual(len(stage.guides), expected)
            ready = [guide for guide in stage.guides if guide.is_ready()]
            self.assertEqual(len(ready), expected, stage.name)
            item_names = {item.name for item in stage.items}
            bound = 0
            for guide in ready:
                self.assertTrue(guide.objectives)
                self.assertTrue(guide.cards)
                self.assertTrue(guide.steps)
                self.assertTrue(guide.self_check)
                self.assertEqual(guide.readiness, "ready")
                if guide.practice:
                    self.assertIn(guide.practice, item_names, guide.title)
                    bound += 1
            self.assertGreaterEqual(bound, minimum_bound[index], stage.name)

    def test_stage6_does_not_expose_private_piece(self) -> None:
        stage = stage_by_index(6)
        private_names = {
            item.name for item in stage.items if item.visibility == "private"
        }
        self.assertTrue(private_names)
        for guide in stage.guides:
            self.assertNotIn(guide.practice, private_names)

    def test_stage7_and_8_lessons_are_ready_and_bound(self) -> None:
        expected = {7: 6, 8: 5}
        for index, count in expected.items():
            stage = stage_by_index(index)
            self.assertEqual(len(stage.guides), count)
            ready = [guide for guide in stage.guides if guide.is_ready()]
            self.assertEqual(len(ready), count, stage.name)
            item_names = {item.name for item in stage.items}
            bound = 0
            for guide in ready:
                self.assertTrue(guide.objectives)
                self.assertTrue(guide.cards)
                self.assertTrue(guide.steps)
                self.assertTrue(guide.self_check)
                self.assertEqual(guide.readiness, "ready")
                if guide.practice:
                    self.assertIn(guide.practice, item_names, guide.title)
                    bound += 1
            self.assertEqual(bound, count, stage.name)

    def test_staff_snippets_point_at_packaged_scores(self) -> None:
        from app.core.curriculum import SCORE_DIR

        snippets = [
            (stage.index, guide, card)
            for stage in STAGES
            for guide in stage.guides
            for card in guide.cards
            if card.kind in ("staff", "roll")
        ]
        self.assertGreaterEqual(len(snippets), 5)
        for _, guide, card in snippets:
            stem = Path(card.asset).stem
            matches = [
                SCORE_DIR / f"{stem}.musicxml",
                SCORE_DIR / f"{stem}.mid",
            ]
            self.assertTrue(
                any(path.is_file() for path in matches),
                f"{guide.title}: {card.asset}",
            )
            # A visual card is useless to a screen reader without alt text.
            self.assertTrue(card.body.strip(), guide.title)

    def test_image_cards_point_at_packaged_figures(self) -> None:
        cards = [
            (guide, card)
            for stage in STAGES
            for guide in stage.guides
            for card in guide.cards
            if card.kind == "image"
        ]
        self.assertGreaterEqual(len(cards), 1)
        for guide, card in cards:
            self.assertTrue(card.body.strip(), guide.title)
            path = ROOT / "resources" / card.asset
            self.assertTrue(path.is_file(), f"{guide.title}: {card.asset}")

    def test_every_ready_lesson_has_a_practice_binding(self) -> None:
        for stage in STAGES:
            names = {item.name for item in stage.items}
            for guide in stage.guides:
                if not guide.is_ready():
                    continue
                self.assertTrue(guide.practice, f"{stage.index}:{guide.title}")
                self.assertIn(
                    guide.practice, names, f"{stage.index}:{guide.title}"
                )

    def test_all_57_lessons_are_ready(self) -> None:
        total = sum(len(stage.guides) for stage in STAGES)
        self.assertEqual(total, 57)
        for stage in STAGES:
            for guide in stage.guides:
                self.assertTrue(guide.is_ready(), f"{stage.index}:{guide.title}")

    def test_lesson_refs_resolve_to_titles(self) -> None:
        self.assertEqual(lesson_ref_label("s1-l2"), "高音谱号")
        self.assertEqual(lesson_ref_label("s0-l1"), "认识 32 条光条")
        self.assertEqual(lesson_ref_label("s2"), "节奏与拍号")
        self.assertEqual(lesson_ref_label("s9-l9"), "s9-l9")
        self.assertEqual(lesson_ref_label("自由练习"), "自由练习")

    def test_every_stage_keeps_three_to_eight_lesson_cards(self) -> None:
        for stage in STAGES:
            self.assertGreaterEqual(len(stage.guides), 3)
            self.assertLessEqual(len(stage.guides), 8)
            titles = [guide.title for guide in stage.guides]
            self.assertEqual(len(titles), len(set(titles)))


def wait(ms: int) -> None:
    QTest.qWait(ms)
    QApplication.processEvents()


class GuideContentUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.window = MainWindow(
            serial_enabled=False,
            audio_enabled=False,
            progress_path=root / "learning.json",
            bindings_path=root / "keybindings.json",
            prefs_path=root / "score_prefs.json",
            library_root=root / "scores",
            accessibility_path=root / "accessibility.json",
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.window.resize(1120, 760)
        self.window.show()
        wait(160)
        self.window._show_page(1)
        wait(80)

    def tearDown(self) -> None:
        self.window.close()
        wait(60)
        self.tmp.cleanup()

    def visible_texts(self) -> list[str]:
        texts = [
            label.text()
            for label in self.window.findChildren(QLabel)
            if label.isVisible()
        ]
        texts.extend(
            box.text()
            for box in self.window.findChildren(QCheckBox)
            if box.isVisible()
        )
        return texts

    def visible_buttons(self) -> list[QPushButton]:
        return [
            button
            for button in self.window.findChildren(QPushButton)
            if button.isVisible()
        ]

    def open_stage0_lesson(self, title: str):
        page = self.window.learning_page
        page.open_stage(0)
        wait(60)
        self.assertTrue(page.open_course(title))
        wait(60)
        return page

    def test_staff_card_renders_the_score_instead_of_an_asset_path(self) -> None:
        from app.ui.score_view import ScoreCanvas

        guide = Guide(
            "谱例课",
            3,
            objectives=("读一小段五线谱。",),
            cards=(
                KnowledgeCard("知识卡", "先看谱，再按键。"),
                KnowledgeCard(
                    "C 五指位置",
                    "五线谱：C4–G4",
                    "xiaoxingxing",
                    kind="staff",
                ),
            ),
            steps=("照着谱例弹一遍。",),
            self_check=("能认出 C4 吗？",),
            readiness="ready",
        )
        stage = replace(stage_by_index(0), guides=(guide,))
        page = self.window.learning_page
        page._course_view.set_course(stage, guide)
        wait(40)
        canvases = page._course_view.findChildren(ScoreCanvas)
        self.assertTrue(canvases)
        self.assertTrue(canvases[0].has_score)
        texts = [
            label.text()
            for label in page._course_view.findChildren(QLabel)
        ]
        self.assertIn("C 五指位置", texts)
        self.assertFalse(any("素材 ·" in text for text in texts))
        self.assertFalse(any("xiaoxingxing" in text for text in texts))

    def test_image_card_shows_the_figure_and_its_alt_text(self) -> None:
        from PySide6.QtGui import QColor, QPixmap

        image_path = Path(self.tmp.name) / "hand.png"
        pixmap = QPixmap(48, 32)
        pixmap.fill(QColor("#c89b6a"))
        self.assertTrue(pixmap.save(str(image_path), "PNG"))
        guide = Guide(
            "手型课",
            3,
            objectives=("看清手型。",),
            cards=(
                KnowledgeCard("知识卡", "手腕保持平稳。"),
                KnowledgeCard(
                    "手型示意",
                    "手背放平，手指自然弯曲。",
                    str(image_path),
                    kind="image",
                ),
            ),
            steps=("照着图示摆好手型。",),
            self_check=("手腕平了吗？",),
            readiness="ready",
        )
        stage = replace(stage_by_index(0), guides=(guide,))
        page = self.window.learning_page
        page._course_view.set_course(stage, guide)
        wait(40)
        figures = [
            label
            for label in page._course_view.findChildren(QLabel)
            if label.property("role") == "figure"
        ]
        self.assertEqual(len(figures), 1)
        self.assertFalse(figures[0].pixmap().isNull())
        texts = [
            label.text()
            for label in page._course_view.findChildren(QLabel)
        ]
        self.assertIn("手背放平，手指自然弯曲。", texts)
        self.assertFalse(any("素材 ·" in text for text in texts))

    def test_missing_visual_assets_say_so_without_a_raw_path(self) -> None:
        guide = Guide(
            "缺素材课",
            3,
            objectives=("先看示范。",),
            cards=(
                KnowledgeCard("知识卡", "正文。"),
                KnowledgeCard("谱例", "五线谱示意", "nope-score", kind="staff"),
                KnowledgeCard("图示", "手型示意", "nope-image.png", kind="image"),
            ),
            steps=("练习。",),
            self_check=("检查。",),
            readiness="ready",
        )
        stage = replace(stage_by_index(0), guides=(guide,))
        page = self.window.learning_page
        page._course_view.set_course(stage, guide)
        wait(30)
        texts = [
            label.text()
            for label in page._course_view.findChildren(QLabel)
        ]
        self.assertIn("谱例未找到 · 谱例", texts)
        self.assertIn("图示未找到 · 图示", texts)
        self.assertFalse(any("nope-score" in text for text in texts))
        self.assertFalse(any("nope-image" in text for text in texts))

    def test_ready_lesson_renders_five_sections(self) -> None:
        guide = stage_by_index(0).guides[0]
        self.open_stage0_lesson(guide.title)
        texts = self.visible_texts()
        for heading in ("目标", "知识", "示范", "练习", "检查", "下一步"):
            self.assertIn(heading, texts)
        self.assertIn(guide.objectives[0], texts)
        self.assertIn(guide.cards[0].title, texts)
        self.assertIn(guide.cards[0].body, texts)
        self.assertIn(guide.steps[0], texts)
        self.assertIn(guide.self_check[0], texts)
        self.assertFalse(
            any("正文、图示与可试听的谱例制作中" in text for text in texts)
        )

    def test_planned_lesson_keeps_the_placeholder(self) -> None:
        # All 57 shipped lessons are ready, but the placeholder branch must
        # still cover future/broken content. Drive it with a synthetic guide.
        stage = replace(
            stage_by_index(0),
            guides=(Guide("计划课", 3, ("要点一", "要点二")),),
        )
        page = self.window.learning_page
        page._course_view.set_course(stage, stage.guides[0])
        wait(30)
        texts = [
            label.text()
            for label in page._course_view.findChildren(QLabel)
        ]
        self.assertTrue(
            any("正文、图示与可试听的谱例制作中" in text for text in texts)
        )
        self.assertFalse(any(text == "检查" for text in texts))

    def test_ready_lesson_uses_its_own_practice_binding(self) -> None:
        guide = stage_by_index(0).guides[0]
        self.assertNotEqual(guide.practice, stage_by_index(0).first_practice().name)
        self.open_stage0_lesson(guide.title)
        buttons = [button.text() for button in self.visible_buttons()]
        self.assertTrue(any(guide.practice in text for text in buttons), buttons)

    def test_stage1_ready_lesson_renders_content(self) -> None:
        guide = stage_by_index(1).guides[1]
        page = self.window.learning_page
        page.open_stage(1)
        wait(60)
        self.assertTrue(page.open_course(guide.title))
        wait(60)
        texts = self.visible_texts()
        for heading in ("目标", "知识", "示范", "练习", "检查", "下一步"):
            self.assertIn(heading, texts)
        self.assertIn(guide.cards[0].body, texts)

    def test_guide_shows_prereq_and_next_as_titles(self) -> None:
        guide = stage_by_index(1).guides[1]
        page = self.window.learning_page
        page.open_stage(1)
        wait(60)
        self.assertTrue(page.open_course(guide.title))
        wait(60)
        texts = self.visible_texts()
        self.assertIn("五线谱是什么", texts)
        self.assertIn("下一课 · 音名与八度", texts)
        self.assertNotIn("s1-l1", texts)
        self.assertNotIn("s1-l3", texts)

    def test_ready_lesson_without_a_drill_says_so(self) -> None:
        # Every shipped lesson is bound now; keep the honesty branch covered
        # with a synthetic guide so future content can't silently borrow a
        # neighbouring practice.
        guide = Guide(
            "无训练课",
            3,
            objectives=("先看示范。",),
            cards=(KnowledgeCard("知识卡", "正文。"),),
            steps=("练习。",),
            self_check=("检查。",),
            readiness="ready",
        )
        stage = replace(stage_by_index(0), guides=(guide,))
        page = self.window.learning_page
        page._course_view.set_course(stage, guide)
        wait(40)
        texts = [
            label.text()
            for label in page._course_view.findChildren(QLabel)
        ]
        self.assertTrue(any("本课暂无对应训练" in text for text in texts))
        buttons = [
            button.text()
            for button in page._course_view.findChildren(QPushButton)
        ]
        self.assertFalse(any(" · " in text and "训练" in text for text in buttons))

    def test_lesson_cards_mark_ready_content(self) -> None:
        page = self.window.learning_page

        def card_texts() -> list[str]:
            return [
                label.text()
                for label in page._stage_view.findChildren(QLabel)
                if label.isVisible()
            ]

        page.open_stage(0)
        wait(60)
        self.assertTrue(any("打开" in text for text in card_texts()))
        self.assertFalse(any("制作中" in text for text in card_texts()))


if __name__ == "__main__":
    unittest.main()
