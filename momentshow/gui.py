from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request

from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSImage,
    NSMakeRect,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject, NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration

from momentshow.app import create_server
from momentshow.env import load_dotenv
from momentshow.paths import app_icon_path

DEFAULT_PORT = 8765


class AppDelegate(NSObject):
    def applicationShouldTerminateAfterLastWindowClosed_(self, _app) -> bool:
        return True


def run_gui(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> int:
    load_dotenv()
    httpd = _bind_server(host, port)
    bound_host, bound_port = httpd.server_address[:2]
    url = f"http://{bound_host}:{bound_port}/"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    _wait_ready(url)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(0)
    _apply_app_icon(app)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    style = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskMiniaturizable
        | NSWindowStyleMaskResizable
    )
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 1000, 740),
        style,
        NSBackingStoreBuffered,
        False,
    )
    window.setTitle_("MomentShow")
    window.center()
    window.setMinSize_((760, 560))

    config = WKWebViewConfiguration.alloc().init()
    view = WKWebView.alloc().initWithFrame_configuration_(window.contentView().bounds(), config)
    view.setAutoresizingMask_(18)
    view.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url)))
    window.setContentView_(view)
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    app.run()
    httpd.shutdown()
    return 0


def _apply_app_icon(app) -> None:
    path = app_icon_path()
    if not path.is_file():
        return
    image = NSImage.alloc().initWithContentsOfFile_(str(path))
    if image is not None:
        app.setApplicationIconImage_(image)


def _bind_server(host: str, port: int):
    try:
        return create_server(host, port)
    except OSError:
        return create_server(host, 0)


def _wait_ready(url: str, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.3)
            return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.05)
