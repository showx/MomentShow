from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from momentshow.ocr import OcrLine

CHROME = {
    "朋友圈",
    "发现",
    "微信",
    "wechat",
    "消息",
    "通讯录",
    "我",
    "评论",
    "赞",
    "相册",
    "详情",
    "搜索",
    "发表",
    "拍照",
    "长按",
    "分享",
    "删除",
    "取消",
    "确定",
    "转发",
    "点赞",
    "回复",
    "全文",
    "收起",
    "广告",
    "视频号",
    "直播",
    "服务",
    "看一看",
    "搜一搜",
    "附近",
    "小程序",
    "游戏",
}

TIME_RE = re.compile(
    r"^(刚刚|\d+\s*分钟前|\d+\s*小时前|\d+\s*天前|昨天|前天|"
    r"星期[一二三四五六日天]|"
    r"\d{1,2}月\d{1,2}日(?:\s*\d{1,2}:\d{2})?|"
    r"\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}:\d{2})?)$"
)


@dataclass(frozen=True)
class ParsedMoment:
    author: str
    time_text: str
    body: str
    raw_text: str
    content_hash: str


def parse_lines(lines: list[OcrLine]) -> list[ParsedMoment]:
    useful = [line for line in lines if not _is_chrome(line.text)]
    if not useful:
        return []
    blocks = _cluster(useful)
    moments: list[ParsedMoment] = []
    seen: set[str] = set()
    for block in blocks:
        parsed = _parse_block(block)
        if parsed is None or parsed.content_hash in seen:
            continue
        seen.add(parsed.content_hash)
        moments.append(parsed)
    return moments


def _cluster(lines: list[OcrLine]) -> list[list[OcrLine]]:
    heights = [line.h for line in lines if line.h > 0]
    gap = (sorted(heights)[len(heights) // 2] * 2.6) if heights else 0.04
    gap = max(gap, 0.028)
    blocks: list[list[OcrLine]] = []
    current: list[OcrLine] = []
    last_bottom = None
    for line in lines:
        if current and last_bottom is not None and (line.y - last_bottom) > gap:
            blocks.append(current)
            current = []
        current.append(line)
        last_bottom = line.y + line.h
    if current:
        blocks.append(current)
    return blocks


def _parse_block(block: list[OcrLine]) -> ParsedMoment | None:
    texts = [line.text.strip() for line in block if line.text.strip()]
    if not texts:
        return None

    time_text = ""
    time_index = -1
    for idx in range(len(texts) - 1, -1, -1):
        if _is_time(texts[idx]):
            time_text = texts[idx]
            time_index = idx
            break

    remaining = texts[:time_index] if time_index >= 0 else texts
    remaining = [item for item in remaining if not _is_time(item)]
    if not remaining and not time_text:
        return None

    author = "未知"
    body_parts = remaining
    if remaining and _looks_like_author(remaining[0]):
        author = remaining[0]
        body_parts = remaining[1:]

    body = "\n".join(body_parts).strip()
    if not body and not time_text:
        return None
    if not body and author == "未知":
        return None

    raw_text = "\n".join(texts)
    digest = hashlib.sha256(
        f"{author}|{time_text}|{body}".encode("utf-8")
    ).hexdigest()
    return ParsedMoment(
        author=author,
        time_text=time_text,
        body=body,
        raw_text=raw_text,
        content_hash=digest,
    )


def _is_chrome(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    if compact in CHROME:
        return True
    if len(compact) <= 6 and compact in {"评论", "点赞", "赞"}:
        return True
    return False


def _is_time(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(TIME_RE.match(compact))


def _looks_like_author(text: str) -> bool:
    if _is_time(text) or _is_chrome(text):
        return False
    if len(text) > 20:
        return False
    if re.search(r"[。！？，、：:]", text):
        return False
    return True
