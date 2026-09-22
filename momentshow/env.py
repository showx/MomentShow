from __future__ import annotations

import os
import re
from pathlib import Path

from momentshow.paths import app_support_dir

_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_loaded = False


def env_paths() -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        app_support_dir() / ".env",
    ):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        else:
            value = re.sub(r"\s+#.*$", "", value).rstrip()
        values[key] = value
    return values


def load_dotenv(*, environ: dict[str, str] | None = None, paths: list[Path] | None = None) -> list[Path]:
    global _loaded
    target = os.environ if environ is None else environ
    loaded: list[Path] = []
    for path in paths or env_paths():
        if not path.is_file():
            continue
        try:
            values = parse_env(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        for key, value in values.items():
            if key not in target or target[key] == "":
                target[key] = value
        loaded.append(path)
    if environ is None:
        _loaded = True
    return loaded


def setting(name: str, default: str = "") -> str:
    if not _loaded:
        load_dotenv()
    return str(os.environ.get(name) or default).strip()


def ensure_env_example(path: Path | None = None) -> Path:
    target = path or (Path(__file__).resolve().parents[1] / ".env")
    if not target.exists():
        target.write_text(ENV_TEMPLATE, encoding="utf-8")
    return target


ENV_TEMPLATE = """# 二选一：openai（官方或兼容接口）或 ollama（本地）。
# 改 PROVIDER 后，用下面对应那一组，另一组保持注释即可。

# --- OpenAI / 兼容接口 ---
# MOMENTSHOW_LLM_PROVIDER=openai
# MOMENTSHOW_LLM_API_KEY=sk-...
# MOMENTSHOW_LLM_BASE_URL=https://api.openai.com/v1
# MOMENTSHOW_LLM_MODEL=gpt-4o-mini

# --- 本地 Ollama ---
MOMENTSHOW_LLM_PROVIDER=ollama
MOMENTSHOW_LLM_API_KEY=
MOMENTSHOW_LLM_BASE_URL=http://127.0.0.1:11434/v1
MOMENTSHOW_LLM_MODEL=qwen3.8:27b
"""
