from __future__ import annotations

from AppKit import NSBitmapImageRep, NSColorSpace
from Quartz import (
    CGImageCreateWithImageInRect,
    CGImageGetHeight,
    CGImageGetWidth,
    CGRectMake,
    CGRectNull,
    CGWindowListCopyWindowInfo,
    CGWindowListCreateImage,
    kCGNullWindowID,
    kCGWindowImageBoundsIgnoreFraming,
    kCGWindowImageNominalResolution,
    kCGWindowListExcludeDesktopElements,
    kCGWindowListOptionAll,
    kCGWindowListOptionIncludingWindow,
    kCGWindowListOptionOnScreenOnly,
)

# 微信主窗口：左侧会话列表 + 右侧聊天区。只扫聊天区能少做很多 OCR。
CHAT_PANE = (0.28, 0.08, 0.70, 0.78)

MOMENT_WINDOW_KEYS = ("朋友圈", "Moments")
GENERIC_TITLES = {"微信", "WeChat", "朋友圈", "Moments", ""}


def list_wechat_windows(pids: set[int], *, on_screen_only: bool) -> list[dict]:
    options = kCGWindowListExcludeDesktopElements
    options |= kCGWindowListOptionOnScreenOnly if on_screen_only else kCGWindowListOptionAll
    raw = CGWindowListCopyWindowInfo(options, kCGNullWindowID) or []
    owned: list[dict] = []
    seen: set[int] = set()
    for raw_item in raw:
        item = dict(raw_item)
        owner_pid = int(item.get("kCGWindowOwnerPID") or 0)
        owner = str(item.get("kCGWindowOwnerName") or "")
        if owner_pid not in pids and owner not in {"WeChat", "微信"}:
            continue
        layer = int(item.get("kCGWindowLayer") or 0)
        if layer != 0:
            continue
        bounds = window_bounds(item)
        if bounds["Width"] < 300 or bounds["Height"] < 300:
            continue
        window_id = int(item.get("kCGWindowNumber") or 0)
        if window_id in seen:
            continue
        seen.add(window_id)
        owned.append(item)
    return owned


def pick_wechat_window(pids: set[int], *, prefer_moments: bool) -> dict | None:
    owned = list_wechat_windows(pids, on_screen_only=True)
    if not owned:
        owned = list_wechat_windows(pids, on_screen_only=False)
    if not owned:
        return None

    def score(item: dict) -> tuple:
        name = str(item.get("kCGWindowName") or "")
        is_moments = 1 if any(key in name for key in MOMENT_WINDOW_KEYS) else 0
        bounds = window_bounds(item)
        area = bounds["Width"] * bounds["Height"]
        if prefer_moments:
            return (is_moments, area)
        return (0 if is_moments else 1, area)

    return max(owned, key=score)


def window_bounds(item: dict) -> dict[str, float]:
    bounds = item.get("kCGWindowBounds") or {}
    return {
        "X": float(bounds.get("X", 0)),
        "Y": float(bounds.get("Y", 0)),
        "Width": float(bounds.get("Width", 0)),
        "Height": float(bounds.get("Height", 0)),
    }


def window_title(item: dict) -> str:
    return str(item.get("kCGWindowName") or "").strip()


def is_moments_window(item: dict) -> bool:
    name = window_title(item)
    return any(key in name for key in MOMENT_WINDOW_KEYS)


def contact_from_title(title: str) -> str | None:
    name = title.strip()
    if name in GENERIC_TITLES:
        return None
    if any(key in name for key in MOMENT_WINDOW_KEYS):
        return None
    return name or None


def screenshot_window(window_id: int):
    return CGWindowListCreateImage(
        CGRectNull,
        kCGWindowListOptionIncludingWindow,
        window_id,
        kCGWindowImageBoundsIgnoreFraming | kCGWindowImageNominalResolution,
    )


def crop_normalized(cg_image, nx: float, ny: float, nw: float, nh: float):
    if cg_image is None:
        return None
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    if not width or not height:
        return None
    return CGImageCreateWithImageInRect(
        cg_image,
        CGRectMake(width * nx, height * ny, width * nw, height * nh),
    )


def looks_black(cg_image) -> bool:
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    if not width or not height:
        return True
    rep = NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
    if rep is None:
        return False
    samples = []
    for fx, fy in ((0.2, 0.2), (0.5, 0.5), (0.8, 0.3), (0.4, 0.7)):
        x = min(max(int(width * fx), 0), int(width) - 1)
        y = min(max(int(height * fy), 0), int(height) - 1)
        color = rep.colorAtX_y_(x, y)
        if color is None:
            continue
        converted = color.colorUsingColorSpace_(NSColorSpace.genericRGBColorSpace())
        target = converted or color
        samples.append(
            float(target.redComponent())
            + float(target.greenComponent())
            + float(target.blueComponent())
        )
    if not samples:
        return False
    return sum(samples) / len(samples) < 0.12
