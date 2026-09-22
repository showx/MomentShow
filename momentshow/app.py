from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from momentshow.axutil import accessibility_trusted
from momentshow.capture import capture_moments
from momentshow.drafts import llm_configured, llm_provider, resolve_llm
from momentshow.env import load_dotenv
from momentshow.paths import database_path
from momentshow.store import connect, count_moments, list_authors, list_moments
from momentshow.wechat import WECHAT_BUNDLE_ID, running_wechat

WEB_DIR = Path(__file__).resolve().parent / "web"
_CAPTURE_LOCK = threading.Lock()
_CHAT_LOCK = threading.Lock()


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    load_dotenv()
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = create_server(host, port)
    print(f"MomentShow：http://{host}:{port}", flush=True)
    print("按 Ctrl+C 停止。采集或填入时会把微信带到前台。", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/moments":
            query = parse_qs(parsed.query)
            author = (query.get("author") or [None])[0] or None
            conn = connect()
            items = list_moments(conn, author=author)
            conn.close()
            self._send_json([item.__dict__ for item in items])
            return
        if parsed.path == "/api/authors":
            conn = connect()
            authors = list_authors(conn)
            conn.close()
            self._send_json(authors)
            return
        if parsed.path == "/api/status":
            self._send_json(_status())
            return
        if parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            path = (WEB_DIR / name).resolve()
            if WEB_DIR.resolve() not in path.parents and path != WEB_DIR.resolve():
                self._send_status(404, "not found")
                return
            ctype = "text/css" if path.suffix == ".css" else "application/javascript"
            self._send_file(path, ctype)
            return
        self._send_status(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/capture":
            self._handle_capture()
            return
        if parsed.path == "/api/chat/read":
            self._handle_chat_read()
            return
        if parsed.path == "/api/chat/fill":
            self._handle_chat_fill()
            return
        self._send_status(404, "not found")

    def _handle_capture(self) -> None:
        body = self._read_json()
        scrolls = int(body.get("scrolls") or 8)
        manual = bool(body.get("manual") or False)
        if not _CAPTURE_LOCK.acquire(blocking=False):
            self._send_json({"ok": False, "message": "正在采集中，请稍候。"}, status=409)
            return
        try:
            result = capture_moments(scrolls=max(1, min(scrolls, 20)), manual=manual)
            payload = result.as_dict()
            payload["ok"] = True
            self._send_json(payload)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "message": str(exc)}, status=500)
        finally:
            _CAPTURE_LOCK.release()

    def _handle_chat_read(self) -> None:
        from momentshow.chat import read_chat

        if not _CHAT_LOCK.acquire(blocking=False):
            self._send_json({"ok": False, "message": "正在读取或填入聊天，请稍候。"}, status=409)
            return
        try:
            self._send_json(read_chat().as_dict())
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "message": str(exc)}, status=500)
        finally:
            _CHAT_LOCK.release()

    def _handle_chat_fill(self) -> None:
        from momentshow.chat import fill_chat

        body = self._read_json()
        index = body.get("index")
        text = body.get("text")
        send = bool(body.get("send") or False)
        try:
            chosen_index = int(index) if index not in (None, "") else None
        except (TypeError, ValueError):
            self._send_json({"ok": False, "message": "草稿编号无效。"}, status=400)
            return
        if not _CHAT_LOCK.acquire(blocking=False):
            self._send_json({"ok": False, "message": "正在读取或填入聊天，请稍候。"}, status=409)
            return
        try:
            result = fill_chat(
                index=chosen_index,
                text=str(text) if text else None,
                send=send,
            )
            self._send_json(result.as_dict())
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "message": str(exc)}, status=400)
        finally:
            _CHAT_LOCK.release()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _send_json(self, payload, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send_status(404, "not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_status(self, status: int, message: str) -> None:
        self._send_json({"ok": False, "message": message}, status=status)


def _status() -> dict:
    conn = connect()
    total = count_moments(conn)
    authors = list_authors(conn)
    conn.close()
    wechat = running_wechat()
    return {
        "database": str(database_path()),
        "total": total,
        "authors": len(authors),
        "accessibility": accessibility_trusted(prompt=False),
        "wechat_running": wechat is not None,
        "wechat_bundle": WECHAT_BUNDLE_ID,
        "llm_configured": llm_configured(),
        "llm_provider": llm_provider(),
        "llm_model": resolve_llm()["model"],
        "env_files": [str(path) for path in load_dotenv()],
    }
