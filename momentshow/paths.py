from __future__ import annotations

from pathlib import Path


APP_DIR_NAME = "MomentShow"


def app_support_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return app_support_dir() / "moments.db"


def chat_session_path() -> Path:
    return app_support_dir() / "chat_session.json"


def app_icon_path() -> Path:
    icns = Path(__file__).resolve().parent / "assets" / "AppIcon.icns"
    if icns.is_file():
        return icns
    return Path(__file__).resolve().parent / "assets" / "AppIcon.png"
