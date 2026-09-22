from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from momentshow.env import load_dotenv, parse_env


class EnvTests(unittest.TestCase):
    def test_parse_quotes_comments_and_export(self) -> None:
        values = parse_env(
            "\n".join(
                [
                    "# comment",
                    "MOMENTSHOW_LLM_API_KEY=sk-test",
                    'MOMENTSHOW_LLM_BASE_URL="https://example.com/v1"',
                    "export MOMENTSHOW_LLM_MODEL=gpt-test  # trailing",
                    "",
                    "not a line",
                ]
            )
        )
        self.assertEqual(values["MOMENTSHOW_LLM_API_KEY"], "sk-test")
        self.assertEqual(values["MOMENTSHOW_LLM_BASE_URL"], "https://example.com/v1")
        self.assertEqual(values["MOMENTSHOW_LLM_MODEL"], "gpt-test")

    def test_load_does_not_override_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("MOMENTSHOW_LLM_API_KEY=from-file\nALREADY_SET=from-file\n", encoding="utf-8")
            environ = {"ALREADY_SET": "from-shell"}
            loaded = load_dotenv(environ=environ, paths=[path])
        self.assertEqual(loaded, [path])
        self.assertEqual(environ["MOMENTSHOW_LLM_API_KEY"], "from-file")
        self.assertEqual(environ["ALREADY_SET"], "from-shell")


if __name__ == "__main__":
    unittest.main()
