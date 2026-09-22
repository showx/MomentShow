from __future__ import annotations

import re
from dataclasses import dataclass

from momentshow.ocr import OcrLine
from momentshow.parse import _is_time

CHAT_CHROME = {
    "发送",
    "表情",
    "语音",
    "搜索",
    "微信",
    "wechat",
    "消息",
    "通讯录",
    "发现",
    "我",
    "按住说话",
    "聊天文件",
    "截图",
    "相册",
    "拍摄",
    "文件",
    "视频通话",
    "语音通话",
    "更多",
    "静音",
    "置顶",
    "朋友圈",
    "moments",
    "发送给朋友",
    "收藏",
    "翻译",
    "多选",
    "引用",
    "撤回",
    "删除",
    "取消",
    "确定",
    "复制",
}

CLOCK_RE = re.compile(r"^\d{1,2}:\d{2}$")
DATE_CLOCK_RE = re.compile(
    r"^(昨天|前天|今天|星期[一二三四五六日天])\s*\d{1,2}:\d{2}$"
)


@dataclass(frozen=True)
class ChatMessage:
    speaker: str
    text: str
    x: float
    y: float

    def as_dict(self) -> dict:
        return {"speaker": self.speaker, "text": self.text}


@dataclass(frozen=True)
class ChatThread:
    contact: str
    messages: list[ChatMessage]

    def as_dicts(self) -> list[dict]:
        return [item.as_dict() for item in self.messages]


def parse_chat_lines(
    lines: list[OcrLine],
    *,
    contact: str = "当前聊天",
    limit: int = 20,
) -> ChatThread:
    useful = [line for line in lines if _keep_line(line)]
    inferred = _contact_from_lines(lines) or contact
    if not useful:
        return ChatThread(contact=inferred, messages=[])

    messages: list[ChatMessage] = []
    for block in _cluster(useful):
        parsed = _parse_block(block)
        if parsed is None:
            continue
        messages.append(parsed)
    return ChatThread(contact=inferred, messages=messages[-limit:])


def messages_from_dicts(items: list[dict]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for item in items:
        speaker = str(item.get("speaker") or "")
        text = str(item.get("text") or "").strip()
        if speaker not in {"me", "them"} or not text:
            continue
        messages.append(ChatMessage(speaker=speaker, text=text, x=0.0, y=0.0))
    return messages


def _keep_line(line: OcrLine) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if _is_chat_chrome(text):
        return False
    if _is_chat_time(text):
        return False
    if _is_centered_system(line):
        return False
    if _is_session_list(line):
        return False
    if line.y < 0.10:
        return False
    return True


def _is_session_list(line: OcrLine) -> bool:
    return line.x < 0.22 and (line.x + line.w) < 0.32


def _is_chat_chrome(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    return compact in CHAT_CHROME


def _is_chat_time(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if _is_time(text) or _is_time(compact):
        return True
    return bool(CLOCK_RE.match(compact) or DATE_CLOCK_RE.match(text.strip()))


SYSTEM_RE = re.compile(
    r"(你已添加|以上是打招呼|撤回了一条|拍了拍|消息已发出|邀请你加入|开启了朋友验证)"
)


def _is_centered_system(line: OcrLine) -> bool:
    compact = re.sub(r"\s+", "", line.text)
    if SYSTEM_RE.search(compact):
        return True
    center = line.x + line.w / 2
    return 0.42 <= center <= 0.58 and line.w <= 0.28 and len(compact) <= 10 and _is_chat_time(compact)


def _contact_from_lines(lines: list[OcrLine]) -> str | None:
    candidates = [
        line
        for line in lines
        if line.y < 0.10
        and 2 <= len(line.text.strip()) <= 20
        and not _is_chat_chrome(line.text)
        and not _is_chat_time(line.text)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (abs((item.x + item.w / 2) - 0.55), item.y))
    name = candidates[0].text.strip()
    if name.lower() in CHAT_CHROME:
        return None
    return name


def _cluster(lines: list[OcrLine]) -> list[list[OcrLine]]:
    heights = [line.h for line in lines if line.h > 0]
    gap = (sorted(heights)[len(heights) // 2] * 1.8) if heights else 0.03
    gap = max(gap, 0.022)
    blocks: list[list[OcrLine]] = []
    current: list[OcrLine] = []
    last_bottom = None
    last_side = None
    for line in lines:
        side = _side_of(line)
        if current and last_bottom is not None:
            if (line.y - last_bottom) > gap or side != last_side:
                blocks.append(current)
                current = []
        current.append(line)
        last_bottom = line.y + line.h
        last_side = side
    if current:
        blocks.append(current)
    return blocks


def _parse_block(block: list[OcrLine]) -> ChatMessage | None:
    texts = [line.text.strip() for line in block if line.text.strip()]
    if not texts:
        return None
    if len(texts) >= 2 and _looks_like_name(texts[0]) and _side_of(block[0]) == "them":
        texts = texts[1:]
        block = block[1:]
        if not texts:
            return None
    speaker = _side_of(block[0])
    text = "\n".join(texts).strip()
    if not text:
        return None
    return ChatMessage(speaker=speaker, text=text, x=block[0].x, y=block[0].y)


def _side_of(line: OcrLine) -> str:
    center = line.x + line.w / 2
    right_edge = line.x + line.w
    if right_edge >= 0.78 or center >= 0.54:
        return "me"
    return "them"


def _looks_like_name(text: str) -> bool:
    if _is_chat_time(text) or _is_chat_chrome(text):
        return False
    if len(text) > 16:
        return False
    if re.search(r"[。！？，、：:？?]", text):
        return False
    return True
