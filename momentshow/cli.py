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
from momentshow.paths import database_path
from momentshow.store import connect, count_moments, list_authors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="momentshow",
        description="打开本机微信，读取当前可见的朋友圈，并存成本地时间线。",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    capture_cmd = sub.add_parser("capture", help="打开微信并采集当前可见朋友圈")
    capture_cmd.add_argument("--scrolls", type=int, default=8, help="滚动屏数，默认 8")
    capture_cmd.add_argument(
        "--manual",
        action="store_true",
        help="不自动点朋友圈，只采集当前已打开的窗口",
    )

    serve_cmd = sub.add_parser("serve", help="打开本地时间线页面")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--no-open", action="store_true", help="不自动打开浏览器")

    sub.add_parser("status", help="查看权限、微信和本地库状态")

    args = parser.parse_args(argv)
    if args.cmd == "capture":
        return _cmd_capture(args.scrolls, args.manual)
    if args.cmd == "serve":
        return _cmd_serve(args.host, args.port, not args.no_open)
    if args.cmd == "status":
        return _cmd_status()
    parser.print_help()
    return 2


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
    }
    conn.close()
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
