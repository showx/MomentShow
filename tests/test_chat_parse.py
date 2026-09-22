from __future__ import annotations

import unittest

from momentshow.chat_parse import parse_chat_lines
from momentshow.ocr import OcrLine, remap_lines


def line(text: str, x: float, y: float, w: float = 0.3, h: float = 0.03) -> OcrLine:
    return OcrLine(text=text, x=x, y=y, w=w, h=h)


class ChatParseTests(unittest.TestCase):
    def test_splits_left_and_right_bubbles(self) -> None:
        thread = parse_chat_lines(
            [
                line("发送", 0.82, 0.92, w=0.08),
                line("12:30", 0.42, 0.18, w=0.12),
                line("今晚有空吗", 0.12, 0.30),
                line("还不确定", 0.58, 0.44),
                line("那你看一下", 0.12, 0.58),
            ],
            contact="当前聊天",
        )
        self.assertEqual([item.speaker for item in thread.messages], ["them", "me", "them"])
        self.assertEqual(thread.messages[0].text, "今晚有空吗")
        self.assertEqual(thread.messages[1].text, "还不确定")
        self.assertEqual(thread.messages[2].text, "那你看一下")

    def test_drops_chrome_and_name_prefix(self) -> None:
        thread = parse_chat_lines(
            [
                line("消息", 0.04, 0.04, w=0.08),
                line("Alice", 0.12, 0.28, w=0.16),
                line("周末去爬山", 0.12, 0.32),
            ]
        )
        self.assertEqual(len(thread.messages), 1)
        self.assertEqual(thread.messages[0].speaker, "them")
        self.assertEqual(thread.messages[0].text, "周末去爬山")

    def test_ignores_left_session_list(self) -> None:
        thread = parse_chat_lines(
            [
                line("张三", 0.04, 0.20, w=0.16),
                line("李四", 0.04, 0.28, w=0.16),
                line("今晚有空吗", 0.34, 0.40, w=0.28),
            ]
        )
        self.assertEqual([item.text for item in thread.messages], ["今晚有空吗"])
        self.assertEqual(thread.messages[0].speaker, "them")

    def test_remap_cropped_pane_back_to_window(self) -> None:
        cropped = [line("今晚有空吗", 0.10, 0.40, w=0.40)]
        mapped = remap_lines(cropped, 0.28, 0.08, 0.70, 0.78)
        self.assertAlmostEqual(mapped[0].x, 0.35)
        self.assertAlmostEqual(mapped[0].y, 0.392)
        self.assertAlmostEqual(mapped[0].w, 0.28)

    def test_reads_contact_from_top_title(self) -> None:
        thread = parse_chat_lines(
            [
                line("Bob", 0.42, 0.03, w=0.16),
                line("在吗", 0.14, 0.30),
            ]
        )
        self.assertEqual(thread.contact, "Bob")
        self.assertEqual(thread.messages[0].text, "在吗")


if __name__ == "__main__":
    unittest.main()
