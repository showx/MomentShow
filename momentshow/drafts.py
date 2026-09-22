from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from momentshow.chat_parse import ChatMessage
from momentshow.env import setting

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "qwen3.8:27b"
STYLES = ("顺着说", "简短收到", "晚点再回")
GREETING_RE = re.compile(r"^(在吗|在不在|你好|您好|哈喽|嗨|hi|hello|hey)[啊呀嘛吗！!？?\s]*$", re.I)


@dataclass(frozen=True)
class Draft:
    index: int
    style: str
    text: str
    source: str

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "style": self.style,
            "text": self.text,
            "source": self.source,
        }


def llm_provider() -> str:
    value = setting("MOMENTSHOW_LLM_PROVIDER", "openai").lower()
    return value if value in {"openai", "ollama"} else "openai"


def llm_configured(api_key: str | None = None) -> bool:
    if api_key is not None:
        return bool(str(api_key).strip())
    return llm_provider() == "ollama" or bool(setting("MOMENTSHOW_LLM_API_KEY"))


def resolve_llm(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, str | int]:
    chosen_provider = (provider or llm_provider()).lower()
    if chosen_provider not in {"openai", "ollama"}:
        chosen_provider = "openai"
    key = (setting("MOMENTSHOW_LLM_API_KEY") if api_key is None else api_key).strip()
    raw_base = (base_url or setting("MOMENTSHOW_LLM_BASE_URL")).rstrip("/")
    raw_model = model or setting("MOMENTSHOW_LLM_MODEL")
    if chosen_provider == "ollama":
        if not raw_base or "openai.com" in raw_base:
            raw_base = OLLAMA_BASE_URL
        if not raw_model or raw_model == DEFAULT_MODEL:
            raw_model = OLLAMA_MODEL
        key = key or "ollama"
        timeout = int(setting("MOMENTSHOW_LLM_TIMEOUT") or "180")
    else:
        raw_base = raw_base or DEFAULT_BASE_URL
        raw_model = raw_model or DEFAULT_MODEL
        timeout = int(setting("MOMENTSHOW_LLM_TIMEOUT") or "20")
    return {
        "provider": chosen_provider,
        "api_key": key,
        "base_url": _openai_root(raw_base),
        "model": raw_model,
        "timeout": timeout,
    }


def generate_drafts(
    messages: list[ChatMessage],
    *,
    contact: str = "当前聊天",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[list[Draft], str, list[str]]:
    warnings: list[str] = []
    options = resolve_llm(api_key=api_key, base_url=base_url, model=model, provider=provider)
    if api_key is not None:
        use_model = bool(str(api_key).strip())
    else:
        use_model = options["provider"] == "ollama" or bool(options["api_key"])
    if use_model:
        try:
            drafts = model_drafts(
                messages,
                contact=contact,
                api_key=str(options["api_key"] or "ollama"),
                base_url=str(options["base_url"]),
                model=str(options["model"]),
                provider=str(options["provider"]),
                timeout=int(options["timeout"]),
            )
            return drafts, "model", warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"模型草稿失败，已改用规则草稿：{exc}")
    return rule_drafts(messages), "rules", warnings


def rule_drafts(messages: list[ChatMessage]) -> list[Draft]:
    last = last_them_text(messages)
    compact = re.sub(r"\s+", " ", last).strip()
    snippet = compact[:16]
    if _is_greeting(compact):
        follow = "在的"
    elif _looks_question(compact):
        follow = "我看一下，待会回你"
    elif snippet and len(snippet) <= 12:
        follow = f"好的，{snippet}"
    elif snippet:
        follow = "好的，我知道了"
    else:
        follow = "好的"
    brief = "好的" if _looks_question(compact) else "收到"
    later = "现在不太方便，晚点回你"
    return [
        Draft(1, STYLES[0], follow, "rules"),
        Draft(2, STYLES[1], brief, "rules"),
        Draft(3, STYLES[2], later, "rules"),
    ]


def last_them_text(messages: list[ChatMessage]) -> str:
    for item in reversed(messages):
        if item.speaker == "them" and item.text.strip():
            return item.text.strip()
    return ""


def model_drafts(
    messages: list[ChatMessage],
    *,
    contact: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    timeout: int | None = None,
) -> list[Draft]:
    options = resolve_llm(api_key=api_key, base_url=base_url, model=model, provider=provider)
    root = str(options["base_url"])
    chosen = str(options["model"])
    wait = timeout if timeout is not None else int(options["timeout"])
    payload = {
        "model": chosen,
        "temperature": 0.6,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你在帮用户起草他自己的微信回复。只写用户本人要发出的话。"
                    "根据对话给出 3 条中文短回复。只输出 JSON 数组，每项含 style 和 text。"
                    f"style 必须依次是：{'、'.join(STYLES)}。不要扮演对方，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": _prompt_conversation(messages, contact),
            },
        ],
    }
    if options["provider"] == "ollama":
        payload["think"] = False
    request = urllib.request.Request(
        f"{root}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {options['api_key'] or 'ollama'}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=wait) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"HTTP {exc.code} {detail}".strip()) from exc
    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    return parse_model_output(str(content or ""))


def parse_model_output(text: str) -> list[Draft]:
    payload = _extract_json_array(_strip_think(text))
    drafts: list[Draft] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            style = str(item.get("style") or "").strip()
            body = str(item.get("text") or "").strip()
            if not body:
                continue
            drafts.append(Draft(len(drafts) + 1, style or STYLES[len(drafts) % 3], body, "model"))
            if len(drafts) == 3:
                break
    if len(drafts) < 3:
        for line in text.splitlines():
            cleaned = re.sub(r"^\s*(?:\d+[\.\)、]|\-\s*)", "", line).strip()
            cleaned = re.sub(r"^【?[^】]{2,8}】?[:：]\s*", "", cleaned).strip()
            if len(cleaned) < 2:
                continue
            if any(item.text == cleaned for item in drafts):
                continue
            style = STYLES[len(drafts)] if len(drafts) < 3 else "补充"
            drafts.append(Draft(len(drafts) + 1, style, cleaned, "model"))
            if len(drafts) == 3:
                break
    if len(drafts) < 3:
        raise ValueError("模型没有返回 3 条可用草稿")
    return drafts[:3]


def _prompt_conversation(messages: list[ChatMessage], contact: str) -> str:
    if not messages:
        return f"联系人：{contact}\n当前窗口几乎没有识别到对话。请给 3 条通用、简短、得体的回复。"
    lines = [f"联系人：{contact}", "对话："]
    for item in messages[-12:]:
        who = "我" if item.speaker == "me" else "对方"
        lines.append(f"{who}：{item.text}")
    lines.append("请按指定 JSON 输出 3 条回复草稿。")
    return "\n".join(lines)


def _openai_root(url: str) -> str:
    root = url.rstrip("/")
    if root.endswith("/v1"):
        return root
    if ":11434" in root:
        return f"{root}/v1"
    return root


def _strip_think(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def _extract_json_array(text: str):
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _is_greeting(text: str) -> bool:
    return bool(GREETING_RE.match(text.strip()))


def _looks_question(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return False
    if "?" in compact or "？" in compact:
        return True
    return bool(re.search(r"(吗|呢|嘛)\s*$", compact))
