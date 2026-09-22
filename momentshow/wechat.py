from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

from AppKit import NSRunningApplication, NSWorkspace
from ApplicationServices import kAXPositionAttribute, kAXSizeAttribute, kAXTitleAttribute
from Quartz import (
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    kCGHIDEventTap,
    kCGScrollEventUnitLine,
)

from momentshow.axutil import (
    accessibility_trusted,
    app_element_for_pid,
    click_screen,
    copy_attribute,
    element_text,
    paste_clipboard,
    press,
    press_return,
    select_all,
    set_clipboard,
    walk_ax,
    windows_for_app,
)

WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"
WECHAT_APP_EX_BUNDLE_ID = "com.tencent.flue.WeChatAppEx"
WECHAT_APP_PATH = "/Applications/微信.app"
WECHAT_BUNDLES = {WECHAT_BUNDLE_ID, WECHAT_APP_EX_BUNDLE_ID}
MOMENT_KEYWORDS = ("朋友圈", "Moments")
DISCOVER_KEYWORDS = ("发现", "Discover")


@dataclass
class WeChatApp:
    pid: int
    name: str


def launch_wechat(timeout: float = 20.0) -> WeChatApp:
    app = _running_wechat()
    if app is None:
        subprocess.run(["open", "-a", WECHAT_APP_PATH], check=False)
        deadline = time.time() + timeout
        while time.time() < deadline:
            app = _running_wechat()
            if app is not None:
                break
            time.sleep(0.4)
    if app is None:
        raise RuntimeError("无法启动微信，请确认已安装 /Applications/微信.app")
    app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
    time.sleep(0.8)
    return WeChatApp(pid=int(app.processIdentifier()), name=str(app.localizedName() or "WeChat"))


def running_wechat() -> NSRunningApplication | None:
    matches: list[NSRunningApplication] = []
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        bundle = str(app.bundleIdentifier() or "")
        if bundle in WECHAT_BUNDLES:
            matches.append(app)
    if not matches:
        return None
    preferred = [app for app in matches if str(app.bundleIdentifier() or "") == WECHAT_BUNDLE_ID]
    return (preferred or matches)[0]


def wechat_pids() -> set[int]:
    pids: set[int] = set()
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        bundle = str(app.bundleIdentifier() or "")
        if bundle in WECHAT_BUNDLES:
            pids.add(int(app.processIdentifier()))
    return pids


def _running_wechat() -> NSRunningApplication | None:
    return running_wechat()


def ensure_moments_open(pid: int) -> str:
    if not accessibility_trusted(prompt=True):
        return "需要辅助功能权限才能自动点开朋友圈。已弹出系统设置，授权后请再运行一次。"

    pids = wechat_pids() | {pid}
    for current in pids:
        app_el = app_element_for_pid(current)
        if _moments_window_open(app_el):
            return "朋友圈窗口已打开。"

    for current in pids:
        app_el = app_element_for_pid(current)
        clicked = _click_labeled(app_el, MOMENT_KEYWORDS)
        time.sleep(1.0)
        if _moments_window_open(app_el) or clicked:
            if _moments_window_open(app_el):
                return "已打开朋友圈。"
            return "已点击朋友圈入口，将采集当前微信窗口。"

        if _click_labeled(app_el, DISCOVER_KEYWORDS):
            time.sleep(0.8)
            if _click_labeled(app_el, MOMENT_KEYWORDS):
                time.sleep(1.0)
                if _moments_window_open(app_el):
                    return "已从发现页打开朋友圈。"
                return "已点击发现/朋友圈，将采集当前微信窗口。"

    return "没有在界面上找到「朋友圈」按钮。请手动点开朋友圈，然后继续采集。"


def _moments_window_open(app_el) -> bool:
    for window in windows_for_app(app_el):
        title = copy_attribute(window, kAXTitleAttribute) or ""
        if any(key in str(title) for key in MOMENT_KEYWORDS):
            return True
    return False


def _click_labeled(app_el, keywords: tuple[str, ...]) -> bool:
    found = {"hit": False}

    def visitor(element, role: str, text: str):
        if not text:
            return False
        if not any(key in text for key in keywords):
            return False
        if press(element):
            found["hit"] = True
            return True
        pos = copy_attribute(element, kAXPositionAttribute)
        size = copy_attribute(element, kAXSizeAttribute)
        point = _unpack_point(pos)
        extent = _unpack_size(size)
        if point and extent:
            click_screen(point[0] + extent[0] / 2, point[1] + extent[1] / 2)
            found["hit"] = True
            return True
        return False

    walk_ax(app_el, visitor)
    return found["hit"]


def _unpack_point(value) -> tuple[float, float] | None:
    parsed = _unpack_xy(value, ("x", "X"), ("y", "Y"))
    if parsed:
        return parsed
    return _unpack_from_text(str(value), ("x", "y"))


def _unpack_size(value) -> tuple[float, float] | None:
    if value is None:
        return None
    if hasattr(value, "width") and hasattr(value, "height"):
        return float(value.width), float(value.height)
    if hasattr(value, "sizeValue"):
        size = value.sizeValue()
        return float(size.width), float(size.height)
    parsed = _unpack_xy(value, ("width", "Width", "w"), ("height", "Height", "h"))
    if parsed:
        return parsed
    return _unpack_from_text(str(value), ("w", "h", "width", "height"))


def _unpack_xy(value, x_keys: tuple[str, ...], y_keys: tuple[str, ...]) -> tuple[float, float] | None:
    if value is None:
        return None
    if hasattr(value, "pointValue"):
        point = value.pointValue()
        return float(point.x), float(point.y)
    if hasattr(value, "x") and hasattr(value, "y") and x_keys[0].lower() == "x":
        return float(value.x), float(value.y)
    if isinstance(value, dict):
        x_key = next((key for key in x_keys if key in value), None)
        y_key = next((key for key in y_keys if key in value), None)
        if x_key and y_key:
            return float(value[x_key]), float(value[y_key])
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return None


def _unpack_from_text(text: str, names: tuple[str, ...]) -> tuple[float, float] | None:
    import re

    found: list[float] = []
    for name in names:
        match = re.search(rf"{name}\s*[=:]\s*(-?\d+(?:\.\d+)?)", text, re.I)
        if match:
            found.append(float(match.group(1)))
        if len(found) >= 2:
            return found[0], found[1]
    return None


def scroll_window(bounds: dict[str, float], lines: int = 8) -> None:
    x = bounds["X"] + bounds["Width"] / 2
    y = bounds["Y"] + bounds["Height"] / 2
    click_screen(x, y)
    time.sleep(0.12)
    event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, -abs(lines))
    CGEventPost(kCGHIDEventTap, event)


def fill_compose_box(pid: int, bounds: dict[str, float], text: str, *, send: bool) -> str:
    if not text.strip():
        raise ValueError("没有可填入的文字。")
    set_clipboard(text)
    _focus_compose_box(pid, bounds)
    time.sleep(0.18)
    select_all()
    time.sleep(0.08)
    paste_clipboard()
    time.sleep(0.12)
    if send:
        press_return()
        return "已填入并发送。"
    return "已填入输入框，尚未发送。"


def _focus_compose_box(pid: int, bounds: dict[str, float]) -> None:
    pids = wechat_pids() | {pid}
    for current in pids:
        field = _last_text_field(app_element_for_pid(current))
        if field is None:
            continue
        if press(field):
            return
        pos = copy_attribute(field, kAXPositionAttribute)
        size = copy_attribute(field, kAXSizeAttribute)
        point = _unpack_point(pos)
        extent = _unpack_size(size)
        if point and extent:
            click_screen(point[0] + extent[0] / 2, point[1] + extent[1] / 2)
            return
    click_screen(
        bounds["X"] + bounds["Width"] * 0.62,
        bounds["Y"] + bounds["Height"] * 0.88,
    )


def _last_text_field(app_el):
    found = {"el": None}

    def visitor(element, role: str, text: str):
        if role not in {"AXTextArea", "AXTextField"}:
            return False
        label = f"{text} {element_text(element)}".lower()
        if any(key in label for key in ("搜索", "search")):
            return False
        found["el"] = element
        return False

    walk_ax(app_el, visitor)
    return found["el"]
