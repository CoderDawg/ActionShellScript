from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QPoint


@dataclass(frozen=True, slots=True)
class WindowExclusionSpec:
    hwnd: int


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


_GA_ROOT = 2


def normalize_window_handles(handles: Iterable[int]) -> tuple[int, ...]:
    normalized: list[int] = []
    for handle in handles:
        try:
            value = int(handle)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _resolve_root_window_handle(hwnd: int) -> int | None:
    if sys.platform != "win32":
        return None

    windll = getattr(ctypes, "windll", None)
    if windll is None or not hasattr(windll, "user32"):
        return None

    try:
        value = int(hwnd)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None

    root_hwnd = windll.user32.GetAncestor(wintypes.HWND(value), _GA_ROOT)
    if root_hwnd:
        return int(root_hwnd)
    return value


def _window_rect_from_hwnd(hwnd: int) -> tuple[int, int, int, int] | None:
    if sys.platform != "win32":
        return None

    windll = getattr(ctypes, "windll", None)
    if windll is None or not hasattr(windll, "user32"):
        return None

    try:
        value = int(hwnd)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None

    rect = _RECT()
    ok = windll.user32.GetWindowRect(ctypes.c_void_p(value), ctypes.byref(rect))
    if not ok:
        return None
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def _point_in_rect(point: QPoint, rect: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = rect
    return left <= point.x() <= right and top <= point.y() <= bottom


def point_hits_excluded_window(point: QPoint, excluded_window_hwnds: Iterable[int]) -> bool:
    handles = normalize_window_handles(excluded_window_hwnds)
    if not handles:
        return False

    if sys.platform != "win32":
        return False

    for hwnd in handles:
        rect = _window_rect_from_hwnd(hwnd)
        if rect is None:
            continue
        if _point_in_rect(point, rect):
            return True
    return False


def active_window_is_excluded(excluded_window_hwnds: Iterable[int]) -> bool:
    handles = normalize_window_handles(excluded_window_hwnds)
    if not handles or sys.platform != "win32":
        return False

    windll = getattr(ctypes, "windll", None)
    if windll is None or not hasattr(windll, "user32"):
        return False

    hwnd = windll.user32.GetForegroundWindow()
    root_hwnd = _resolve_root_window_handle(hwnd)
    if root_hwnd is None:
        return False
    return root_hwnd in handles


def window_info_from_point(
    point: QPoint,
    *,
    excluded_window_hwnds: Iterable[int] = (),
) -> tuple[int | None, str | None]:
    if sys.platform != "win32":
        return None, None

    windll = getattr(ctypes, "windll", None)
    if windll is None or not hasattr(windll, "user32"):
        return None, None

    hwnd = windll.user32.WindowFromPoint(_POINT(point.x(), point.y()))
    if not hwnd:
        return None, None

    root_hwnd = _resolve_root_window_handle(hwnd)
    if root_hwnd is not None:
        hwnd = root_hwnd

    if int(hwnd) in normalize_window_handles(excluded_window_hwnds):
        return None, None

    title_buffer = ctypes.create_unicode_buffer(512)
    windll.user32.GetWindowTextW(wintypes.HWND(hwnd), title_buffer, len(title_buffer))
    title = title_buffer.value.strip() or None
    return int(hwnd), title
