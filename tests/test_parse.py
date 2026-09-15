from __future__ import annotations

import unittest

from momentshow.ocr import OcrLine
from momentshow.parse import parse_lines


def line(text: str, y: float, h: float = 0.03) -> OcrLine:
    return OcrLine(text=text, x=0.12, y=y, w=0.4, h=h)


class ParseTests(unittest.TestCase):
    def test_splits_two_posts_by_gap_and_time(self) -> None:
        lines = [
            line("朋友圈", 0.02),
            line("Alice", 0.10),
            line("今天天气很好", 0.14),
            line("3分钟前", 0.18),
            line("Bob", 0.36),
            line("周末去爬山", 0.40),
            line("昨天", 0.44),
        ]
        moments = parse_lines(lines)
        self.assertEqual(len(moments), 2)
        self.assertEqual(moments[0].author, "Alice")
        self.assertEqual(moments[0].time_text, "3分钟前")
        self.assertEqual(moments[0].body, "今天天气很好")
        self.assertEqual(moments[1].author, "Bob")
        self.assertEqual(moments[1].body, "周末去爬山")

    def test_skips_chrome_only_blocks(self) -> None:
        moments = parse_lines([line("评论", 0.1), line("赞", 0.14)])
        self.assertEqual(moments, [])

    def test_keeps_image_only_post(self) -> None:
        moments = parse_lines([line("Carol", 0.2), line("1小时前", 0.24)])
        self.assertEqual(len(moments), 1)
        self.assertEqual(moments[0].author, "Carol")
        self.assertEqual(moments[0].body, "")


if __name__ == "__main__":
    unittest.main()
