from __future__ import annotations

import time
from dataclasses import dataclass, field

from momentshow.ocr import recognize_lines
from momentshow.parse import parse_lines
from momentshow.store import connect, insert_moment
from momentshow.wechat import ensure_moments_open, launch_wechat, scroll_window, wechat_pids
from momentshow.windows import (
    looks_black,
    pick_wechat_window,
    screenshot_window,
    window_bounds,
)


@dataclass
class CaptureResult:
    message: str
    screens: int = 0
    parsed: int = 0
    inserted: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "message": self.message,
            "screens": self.screens,
            "parsed": self.parsed,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "warnings": self.warnings,
        }


def capture_moments(*, scrolls: int = 8, manual: bool = False) -> CaptureResult:
    warnings: list[str] = []
    app = launch_wechat()
    if manual:
        opened = "已跳过自动点击，采集当前已打开的朋友圈/微信窗口。"
    else:
        opened = ensure_moments_open(app.pid)
        if "权限" in opened or "没有在界面上找到" in opened:
            warnings.append(opened)

    time.sleep(0.8)
    pids = wechat_pids() | {app.pid}
    bounds = _moments_window_bounds(pids)
    if bounds is None:
        return CaptureResult(
            message="没有找到可用的微信窗口。请先登录微信并打开朋友圈。",
            warnings=warnings,
        )

    conn = connect()
    parsed_total = 0
    inserted = 0
    skipped = 0
    screens = 0
    seen_hashes: set[str] = set()

    for index in range(max(1, scrolls)):
        window = _moments_window(pids)
        if window is None:
            warnings.append("采集中途找不到微信窗口了。")
            break
        image = _screenshot_window(int(window["kCGWindowNumber"]))
        if image is None:
            warnings.append("截不到朋友圈窗口。请给终端/Python 打开「屏幕录制」权限。")
            break
        if _looks_black(image):
            warnings.append(
                "截到的窗口是黑屏，通常是没有「屏幕录制」权限。请在系统设置里授权后重试。"
            )
            break

        screens += 1
        try:
            lines = recognize_lines(image)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"OCR 失败：{exc}")
            break

        moments = parse_lines(lines)
        parsed_total += len(moments)
        for moment in moments:
            if moment.content_hash in seen_hashes:
                skipped += 1
                continue
            seen_hashes.add(moment.content_hash)
            if insert_moment(
                conn,
                author=moment.author,
                time_text=moment.time_text,
                body=moment.body,
                raw_text=moment.raw_text,
                content_hash=moment.content_hash,
            ):
                inserted += 1
            else:
                skipped += 1

        if index < scrolls - 1:
            scroll_window(_bounds_dict(window), lines=10)
            time.sleep(0.9)

    conn.close()
    message = (
        f"{opened} 采集 {screens} 屏，识别 {parsed_total} 条，新增 {inserted} 条，"
        f"重复/已存在 {skipped} 条。"
    )
    return CaptureResult(
        message=message,
        screens=screens,
        parsed=parsed_total,
        inserted=inserted,
        skipped=skipped,
        warnings=warnings,
    )


def _moments_window(pids: set[int]) -> dict | None:
    return pick_wechat_window(pids, prefer_moments=True)


def _moments_window_bounds(pids: set[int]) -> dict[str, float] | None:
    window = _moments_window(pids)
    if window is None:
        return None
    return window_bounds(window)


def _bounds_dict(item: dict) -> dict[str, float]:
    return window_bounds(item)


def _screenshot_window(window_id: int):
    return screenshot_window(window_id)


def _looks_black(cg_image) -> bool:
    return looks_black(cg_image)
