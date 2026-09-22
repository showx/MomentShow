from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from momentshow.chat_parse import ChatMessage, ChatThread, messages_from_dicts, parse_chat_lines
from momentshow.drafts import Draft, generate_drafts
from momentshow.ocr import OcrLine, recognize_lines, remap_lines
from momentshow.paths import chat_session_path
from momentshow.wechat import fill_compose_box, launch_wechat, wechat_pids
from momentshow.windows import (
    CHAT_PANE,
    contact_from_title,
    crop_normalized,
    is_moments_window,
    looks_black,
    pick_wechat_window,
    screenshot_window,
    window_bounds,
    window_title,
)


@dataclass
class ChatReadResult:
    message: str
    contact: str = "当前聊天"
    messages: list[ChatMessage] = field(default_factory=list)
    drafts: list[Draft] = field(default_factory=list)
    source: str = "rules"
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": True,
            "message": self.message,
            "contact": self.contact,
            "messages": [item.as_dict() for item in self.messages],
            "drafts": [item.as_dict() for item in self.drafts],
            "source": self.source,
            "warnings": self.warnings,
        }


@dataclass
class ChatFillResult:
    message: str
    sent: bool = False
    text: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": True,
            "message": self.message,
            "sent": self.sent,
            "text": self.text,
            "warnings": self.warnings,
        }


def read_chat(*, session_path: Path | None = None) -> ChatReadResult:
    warnings: list[str] = []
    app = launch_wechat()
    time.sleep(0.5)
    pids = wechat_pids() | {app.pid}
    window = pick_wechat_window(pids, prefer_moments=False)
    if window is None:
        return ChatReadResult(message="没有找到可用的微信窗口。请先登录微信并打开一个聊天。")
    if is_moments_window(window):
        warnings.append("当前像是朋友圈窗口，请先打开一个聊天再读一次。")

    image = screenshot_window(int(window["kCGWindowNumber"]))
    if image is None:
        return ChatReadResult(
            message="截不到微信窗口。请给终端/Python 打开「屏幕录制」权限。",
            warnings=warnings,
        )
    if looks_black(image):
        return ChatReadResult(
            message="截到的窗口是黑屏，通常是没有「屏幕录制」权限。请在系统设置里授权后重试。",
            warnings=warnings,
        )

    try:
        lines = _read_visible_lines(image)
    except Exception as exc:  # noqa: BLE001
        return ChatReadResult(message=f"OCR 失败：{exc}", warnings=warnings)

    contact = contact_from_title(window_title(window)) or "当前聊天"
    thread = parse_chat_lines(lines, contact=contact)
    drafts, source, draft_warnings = generate_drafts(thread.messages, contact=thread.contact)
    warnings.extend(draft_warnings)

    if thread.messages:
        message = (
            f"已读取「{thread.contact}」当前可见的 {len(thread.messages)} 条对话，"
            f"生成 {len(drafts)} 条{('模型' if source == 'model' else '规则')}草稿。"
        )
    else:
        message = "当前窗口几乎没有识别到对话，已给出通用草稿。请确认打开的是聊天窗口。"
        warnings.append("没有解析到气泡，可能是群公告、图片消息，或 OCR 没读到文字。")

    result = ChatReadResult(
        message=message,
        contact=thread.contact,
        messages=thread.messages,
        drafts=drafts,
        source=source,
        warnings=warnings,
    )
    save_session(result, session_path)
    return result


def _read_visible_lines(image) -> list[OcrLine]:
    pane = crop_normalized(image, *CHAT_PANE)
    if pane is None:
        return recognize_lines(image)
    return remap_lines(recognize_lines(pane), *CHAT_PANE)


def fill_chat(
    *,
    index: int | None = None,
    text: str | None = None,
    send: bool = False,
    session_path: Path | None = None,
) -> ChatFillResult:
    chosen = (text or "").strip()
    if not chosen:
        session = load_session(session_path)
        if session is None:
            raise ValueError("还没有读取过聊天。请先运行 momentshow chat，或在页面点「读取当前聊天」。")
        if index is None:
            raise ValueError("请指定草稿编号，或传入要填入的文字。")
        chosen = _draft_text(session, index)
    if not chosen:
        raise ValueError("没有可填入的文字。")

    app = launch_wechat()
    time.sleep(0.4)
    pids = wechat_pids() | {app.pid}
    window = pick_wechat_window(pids, prefer_moments=False)
    if window is None:
        raise RuntimeError("没有找到可用的微信窗口。请先打开要回复的聊天。")
    warnings: list[str] = []
    if is_moments_window(window):
        warnings.append("当前像是朋友圈窗口，填入可能进错地方。")

    filled = fill_compose_box(app.pid, window_bounds(window), chosen, send=send)
    return ChatFillResult(message=filled, sent=send, text=chosen, warnings=warnings)


def save_session(result: ChatReadResult, session_path: Path | None = None) -> None:
    path = session_path or chat_session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict()
    payload["read_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session(session_path: Path | None = None) -> dict | None:
    path = session_path or chat_session_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def session_thread(session: dict) -> ChatThread:
    contact = str(session.get("contact") or "当前聊天")
    messages = messages_from_dicts(list(session.get("messages") or []))
    return ChatThread(contact=contact, messages=messages)


def _draft_text(session: dict, index: int) -> str:
    drafts = session.get("drafts") or []
    for item in drafts:
        if int(item.get("index") or 0) == index:
            return str(item.get("text") or "").strip()
    if 1 <= index <= len(drafts):
        return str(drafts[index - 1].get("text") or "").strip()
    raise ValueError(f"没有第 {index} 条草稿。请先重新读取聊天。")
