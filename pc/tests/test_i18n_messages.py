"""English coverage of toasts, status messages and dialogs (A5)."""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.ui.i18n_ui import EN, set_language, tr_message
from app.ui.widgets import Toast

HAN = re.compile(r"[一-鿿]")
UI_DIR = ROOT / "app" / "ui"
SKIP_FILES = {"i18n_ui.py", "i18n_messages.py", "i18n_labels.py"}


def template(node: ast.AST) -> str | None:
    """Reconstruct an f-string as ``…{…}…``; None when no Chinese is present."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if HAN.search(node.value) else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            else:
                parts.append("{…}")
        text = "".join(parts)
        return text if HAN.search(text) else None
    return None


def expressions(node: ast.AST):
    """Yield every message expression, following conditional branches."""
    yield node
    if isinstance(node, ast.IfExp):
        yield from expressions(node.body)
        yield from expressions(node.orelse)


def emitted_messages():
    for path in sorted(UI_DIR.glob("*.py")):
        if path.name in SKIP_FILES:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else function.id
                if isinstance(function, ast.Name)
                else ""
            )
            if name not in {"emit", "show_message"} or not node.args:
                continue
            for expression in expressions(node.args[0]):
                text = template(expression)
                if text is not None:
                    yield path.name, text


class MessageCatalogueTest(unittest.TestCase):
    def tearDown(self) -> None:
        set_language("zh-CN")

    def test_exact_and_template_messages_translate(self) -> None:
        set_language("en")
        self.assertEqual(
            tr_message("谱面已不在 · 已刷新曲库"),
            "The score is gone · the library was refreshed",
        )
        self.assertEqual(
            tr_message("设备已连接 · COM5"), "Device connected · COM5"
        )
        self.assertEqual(
            tr_message("音轨 2 · 静音关"), "Track 2 · mute off"
        )
        self.assertEqual(
            tr_message("循环 3–5 小节 · 已开启"), "Loop bars 3–5 · on"
        )
        # Values are data; an untranslated song title stays as written.
        self.assertEqual(
            tr_message("已载入 · 小星星"),
            "Loaded · 小星星",
        )
        set_language("zh-CN")
        self.assertEqual(tr_message("已载入 · 小星星"), "已载入 · 小星星")

    def test_every_emitted_message_has_a_catalogue_entry(self) -> None:
        missing = sorted(
            {
                text
                for _file, text in emitted_messages()
                if text not in EN
            }
        )
        self.assertEqual(missing, [], "\n".join(missing))


class ToastTranslationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        set_language("zh-CN")

    def test_toast_renders_english_and_data_values(self) -> None:
        set_language("en")
        toast = Toast(None)
        try:
            toast.show_message("设备已连接 · COM5")
            self.assertEqual(toast.text(), "Device connected · COM5")
            toast.show_message("谱面载入失败：无法解析文件（ScoreError）")
            self.assertNotIn("谱面", toast.text())
            self.assertIn("ScoreError", toast.text())
        finally:
            toast.deleteLater()

    def test_unknown_message_is_unchanged(self) -> None:
        set_language("en")
        toast = Toast(None)
        try:
            toast.show_message("完全新的消息")
            self.assertEqual(toast.text(), "完全新的消息")
        finally:
            toast.deleteLater()


if __name__ == "__main__":
    unittest.main()
