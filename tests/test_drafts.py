from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from momentshow.chat import ChatReadResult, load_session, save_session
from momentshow.chat_parse import ChatMessage
from momentshow.drafts import generate_drafts, parse_model_output, resolve_llm, rule_drafts


def them(text: str) -> ChatMessage:
    return ChatMessage(speaker="them", text=text, x=0.1, y=0.2)


class DraftTests(unittest.TestCase):
    def test_question_uses_three_rule_styles(self) -> None:
        drafts = rule_drafts([them("今晚吃饭吗")])
        self.assertEqual([item.style for item in drafts], ["顺着说", "简短收到", "晚点再回"])
        self.assertEqual(drafts[0].text, "我看一下，待会回你")
        self.assertEqual(drafts[1].text, "好的")
        self.assertEqual(drafts[2].text, "现在不太方便，晚点回你")
        self.assertTrue(all(item.source == "rules" for item in drafts))

    def test_greeting_and_plain_ack(self) -> None:
        greeting = rule_drafts([them("在吗")])
        plain = rule_drafts([them("到了")])
        self.assertEqual(greeting[0].text, "在的")
        self.assertEqual(plain[0].text, "好的，到了")
        self.assertEqual(plain[1].text, "收到")

    def test_generate_drafts_skips_model_without_key(self) -> None:
        drafts, source, warnings = generate_drafts([them("在吗")], api_key="")
        self.assertEqual(source, "rules")
        self.assertEqual(warnings, [])
        self.assertEqual(drafts[0].text, "在的")

    def test_ollama_defaults_to_local_qwen(self) -> None:
        options = resolve_llm(
            provider="ollama",
            api_key="",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )
        self.assertEqual(options["provider"], "ollama")
        self.assertEqual(options["base_url"], "http://127.0.0.1:11434/v1")
        self.assertEqual(options["model"], "qwen3.8:27b")

    def test_parse_model_strips_think_tags(self) -> None:
        drafts = parse_model_output(
            "<think>先分析语气</think>\n"
            + json.dumps(
                [
                    {"style": "顺着说", "text": "好啊"},
                    {"style": "简短收到", "text": "收到"},
                    {"style": "晚点再回", "text": "晚点说"},
                ],
                ensure_ascii=False,
            )
        )
        self.assertEqual([item.text for item in drafts], ["好啊", "收到", "晚点说"])

    def test_parse_model_json(self) -> None:
        drafts = parse_model_output(
            json.dumps(
                [
                    {"style": "顺着说", "text": "好啊"},
                    {"style": "简短收到", "text": "收到"},
                    {"style": "晚点再回", "text": "晚点说"},
                ],
                ensure_ascii=False,
            )
        )
        self.assertEqual([item.text for item in drafts], ["好啊", "收到", "晚点说"])
        self.assertTrue(all(item.source == "model" for item in drafts))

    def test_session_roundtrip(self) -> None:
        result = ChatReadResult(
            message="ok",
            contact="Alice",
            messages=[them("在吗")],
            drafts=rule_drafts([them("在吗")]),
            source="rules",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat_session.json"
            save_session(result, path)
            loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["contact"], "Alice")
        self.assertEqual(loaded["drafts"][0]["text"], "在的")


if __name__ == "__main__":
    unittest.main()
