from __future__ import annotations

import argparse
import json
import sys
import webbrowser

from momentshow.axutil import (
    accessibility_trusted,
    open_accessibility_settings,
    open_screen_recording_settings,
)
from momentshow.capture import capture_moments
from momentshow.drafts import llm_configured, llm_provider, resolve_llm
from momentshow.env import ensure_env_example, load_dotenv
from momentshow.paths import database_path
from momentshow.store import connect, count_moments, list_authors


def main(argv: list[str] | None = None) -> int:
    ensure_env_example()
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="momentshow",
        description="打开 MomentShow 窗口。不带子命令时直接进入界面。",
    )
    sub = parser.add_subparsers(dest="cmd", required=False)
    sub.add_parser("gui", help="打开桌面窗口（默认）")

    capture_cmd = sub.add_parser("capture", help="打开微信并采集当前可见朋友圈")
    capture_cmd.add_argument("--scrolls", type=int, default=8, help="滚动屏数，默认 8")
    capture_cmd.add_argument(
        "--manual",
        action="store_true",
        help="不自动点朋友圈，只采集当前已打开的窗口",
    )

    chat_cmd = sub.add_parser("chat", help="读取当前聊天并生成回复草稿")
    chat_cmd.add_argument("--fill", type=int, metavar="N", help="把第 N 条草稿填入输入框，不发送")
    chat_cmd.add_argument("--send", type=int, metavar="N", help="把第 N 条草稿填入并发送")
    chat_cmd.add_argument("--text", help="填入自定义文字，可与 --fill/--send 一起用")

    serve_cmd = sub.add_parser("serve", help="只开本地网页，不打开桌面窗口")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--no-open", action="store_true", help="不自动打开浏览器")

    sub.add_parser("status", help="查看权限、微信和本地库状态")

    args = parser.parse_args(argv)
    if args.cmd in (None, "gui"):
        return _cmd_gui()
    if args.cmd == "capture":
        return _cmd_capture(args.scrolls, args.manual)
    if args.cmd == "chat":
        return _cmd_chat(args.fill, args.send, args.text)
    if args.cmd == "serve":
        return _cmd_serve(args.host, args.port, not args.no_open)
    if args.cmd == "status":
        return _cmd_status()
    parser.print_help()
    return 2


def _cmd_gui() -> int:
    from momentshow.gui import run_gui

    return run_gui()


def _cmd_capture(scrolls: int, manual: bool) -> int:
    if not accessibility_trusted(prompt=True):
        print("需要辅助功能权限才能自动点击和滚动微信。正在打开系统设置。")
        open_accessibility_settings()
    result = capture_moments(scrolls=scrolls, manual=manual)
    print(result.message)
    for warning in result.warnings:
        print(f"注意：{warning}")
    if any("屏幕录制" in item for item in result.warnings):
        print(
            "当前是 Cursor 代为运行。请在「屏幕录制」里勾选 Cursor"
            "（如列表里还有 Python，也一并勾选），然后跟我说一声再采一次。"
        )
        open_screen_recording_settings()
    return 0 if result.screens else 1


def _cmd_chat(fill: int | None, send: int | None, text: str | None) -> int:
    if not accessibility_trusted(prompt=True):
        print("需要辅助功能权限才能读取窗口或填入草稿。正在打开系统设置。")
        open_accessibility_settings()
    if send is not None or fill is not None or (text or "").strip():
        return _cmd_chat_fill(fill=fill, send=send, text=text)
    return _cmd_chat_read()


def _cmd_chat_read() -> int:
    from momentshow.chat import read_chat

    result = read_chat()
    print(result.message)
    for warning in result.warnings:
        print(f"注意：{warning}")
    print()
    print(f"联系人：{result.contact}")
    print(f"来源：{'模型草稿' if result.source == 'model' else '规则草稿'}")
    print("对话：")
    if result.messages:
        for item in result.messages:
            who = "我" if item.speaker == "me" else "对方"
            print(f"  {who}：{item.text}")
    else:
        print("  （当前窗口没有识别到气泡）")
    print("草稿：")
    for draft in result.drafts:
        print(f"  {draft.index}. [{draft.style}] {draft.text}")
    print()
    print("确认后填入：momentshow chat --fill 1")
    print("填入并发送：momentshow chat --send 1")
    if any("屏幕录制" in item for item in result.warnings) or "屏幕录制" in result.message:
        print(
            "当前是 Cursor 代为运行。请在「屏幕录制」里勾选 Cursor"
            "（如列表里还有 Python，也一并勾选），然后跟我说一声再读一次。"
        )
        open_screen_recording_settings()
        return 1
    return 0 if result.drafts else 1


def _cmd_chat_fill(*, fill: int | None, send: int | None, text: str | None) -> int:
    from momentshow.chat import fill_chat

    try:
        result = fill_chat(index=send if send is not None else fill, text=text, send=send is not None)
    except Exception as exc:  # noqa: BLE001
        print(str(exc))
        return 1
    print(result.message)
    if result.text:
        print(f"内容：{result.text}")
    for warning in result.warnings:
        print(f"注意：{warning}")
    return 0


def _cmd_serve(host: str, port: int, open_browser: bool) -> int:
    from momentshow.app import serve

    url = f"http://{host}:{port}"
    if open_browser:
        webbrowser.open(url)
    serve(host=host, port=port)
    return 0


def _cmd_status() -> int:
    from momentshow.wechat import running_wechat

    conn = connect()
    payload = {
        "database": str(database_path()),
        "moments": count_moments(conn),
        "authors": list_authors(conn),
        "accessibility": accessibility_trusted(prompt=False),
        "wechat_running": running_wechat() is not None,
        "llm_configured": llm_configured(),
        "llm_provider": llm_provider(),
        "llm_model": resolve_llm()["model"],
        "env_files": [str(path) for path in load_dotenv()],
    }
    conn.close()
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
