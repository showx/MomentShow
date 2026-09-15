from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXDescriptionAttribute,
    kAXErrorSuccess,
    kAXPressAction,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXTrustedCheckOptionPrompt,
    kAXWindowsAttribute,
)
from Cocoa import NSDictionary
from Quartz import (
    CGEventCreateMouseEvent,
    CGEventPost,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
)


def accessibility_trusted(prompt: bool = True) -> bool:
    options = NSDictionary.dictionaryWithObject_forKey_(
        True if prompt else False,
        kAXTrustedCheckOptionPrompt,
    )
    return bool(AXIsProcessTrustedWithOptions(options))


def open_accessibility_settings() -> None:
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ],
        check=False,
    )


def open_screen_recording_settings() -> None:
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        ],
        check=False,
    )


def copy_attribute(element: Any, attribute: str) -> Any:
    try:
        result = AXUIElementCopyAttributeValue(element, attribute, None)
    except TypeError:
        result = AXUIElementCopyAttributeValue(element, attribute)
    if result is None:
        return None
    if isinstance(result, tuple):
        err, value = result[0], result[1] if len(result) > 1 else None
        if err not in (None, kAXErrorSuccess, 0):
            return None
        return value
    return result


def element_text(element: Any) -> str:
    parts: list[str] = []
    for attr in (kAXTitleAttribute, kAXDescriptionAttribute, "AXIdentifier"):
        value = copy_attribute(element, attr)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts)


def walk_ax(
    element: Any,
    visitor: Callable[[Any, str, str], bool | None],
    *,
    depth: int = 0,
    max_depth: int = 18,
) -> bool:
    if element is None or depth > max_depth:
        return False
    role = copy_attribute(element, kAXRoleAttribute) or ""
    text = element_text(element)
    if visitor(element, str(role), text):
        return True
    children = copy_attribute(element, kAXChildrenAttribute) or []
    try:
        iterable = list(children)
    except TypeError:
        return False
    for child in iterable:
        if walk_ax(child, visitor, depth=depth + 1, max_depth=max_depth):
            return True
    return False


def app_element_for_pid(pid: int) -> Any:
    return AXUIElementCreateApplication(pid)


def windows_for_app(app_element: Any) -> list[Any]:
    windows = copy_attribute(app_element, kAXWindowsAttribute) or []
    try:
        return list(windows)
    except TypeError:
        return []


def press(element: Any) -> bool:
    try:
        result = AXUIElementPerformAction(element, kAXPressAction)
    except TypeError:
        result = AXUIElementPerformAction(element, kAXPressAction, None)
    if isinstance(result, tuple):
        return result[0] in (None, kAXErrorSuccess, 0)
    return result in (None, kAXErrorSuccess, 0, True)


def click_screen(x: float, y: float) -> None:
    for event_type in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
        event = CGEventCreateMouseEvent(None, event_type, (x, y), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, event)
