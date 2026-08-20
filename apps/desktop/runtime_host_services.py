from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication
from pynput import keyboard


class _MonitorInfoRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int32),
        ("top", ctypes.c_int32),
        ("right", ctypes.c_int32),
        ("bottom", ctypes.c_int32),
    ]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("rcMonitor", _MonitorInfoRect),
        ("rcWork", _MonitorInfoRect),
        ("dwFlags", ctypes.c_uint32),
    ]


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("rcMonitor", _MonitorInfoRect),
        ("rcWork", _MonitorInfoRect),
        ("dwFlags", ctypes.c_uint32),
        ("szDevice", ctypes.c_wchar * 32),
    ]


class _CursorPosPoint(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32),
    ]


class _WindowRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int32),
        ("top", ctypes.c_int32),
        ("right", ctypes.c_int32),
        ("bottom", ctypes.c_int32),
    ]


class _WindowPlacement(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("showCmd", ctypes.c_uint32),
        ("ptMinPosition", _CursorPosPoint),
        ("ptMaxPosition", _CursorPosPoint),
        ("rcNormalPosition", _WindowRect),
    ]


class DesktopRuntimeMonitorInfoService:
    def get_monitor_info(self, *, hmonitor: int) -> dict[str, object]:
        return self._read_monitor_info_payload(
            hmonitor=hmonitor,
            struct_type=_MonitorInfo,
            monitor_name_field=None,
        )

    def get_monitor_info_ex(self, *, hmonitor: int) -> dict[str, object]:
        return self._read_monitor_info_payload(
            hmonitor=hmonitor,
            struct_type=_MonitorInfoEx,
            monitor_name_field="szDevice",
        )

    def _read_monitor_info_payload(
        self,
        *,
        hmonitor: int,
        struct_type: type[ctypes.Structure],
        monitor_name_field: str | None,
    ) -> dict[str, object]:
        if sys.platform != "win32":
            raise RuntimeError("GetMonitorInfo host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetMonitorInfo host service requires Win32 ctypes support")

        info = struct_type()
        info.cbSize = ctypes.sizeof(struct_type)

        ok = windll.user32.GetMonitorInfoW(
            ctypes.c_void_p(int(hmonitor)),
            ctypes.byref(info),
        )
        if not ok:
            raise RuntimeError("GetMonitorInfo host service could not sample the monitor")

        payload = {
            "cbSize": int(info.cbSize),
            "rcMonitor": self._rect_payload(info.rcMonitor),
            "rcWork": self._rect_payload(info.rcWork),
            "dwFlags": int(info.dwFlags),
        }
        if monitor_name_field is not None:
            payload[monitor_name_field] = str(getattr(info, monitor_name_field)).rstrip("\x00")
        return payload

    def _rect_payload(self, rect: _MonitorInfoRect) -> dict[str, int]:
        return {
            "Left": int(rect.left),
            "Top": int(rect.top),
            "Right": int(rect.right),
            "Bottom": int(rect.bottom),
        }


class DesktopRuntimeCursorPosService:
    def get_cursor_pos(self) -> dict[str, int]:
        if sys.platform != "win32":
            raise RuntimeError("GetCursorPos host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetCursorPos host service requires Win32 ctypes support")

        point = _CursorPosPoint()
        ok = windll.user32.GetCursorPos(ctypes.byref(point))
        if not ok:
            raise RuntimeError("GetCursorPos host service could not sample the cursor")

        return {"X": int(point.x), "Y": int(point.y)}


class DesktopRuntimeWindowRectService:
    def get_window_rect(self, *, hwnd: int) -> dict[str, int]:
        if sys.platform != "win32":
            raise RuntimeError("GetWindowRect host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetWindowRect host service requires Win32 ctypes support")

        rect = _WindowRect()
        ok = windll.user32.GetWindowRect(ctypes.c_void_p(int(hwnd)), ctypes.byref(rect))
        if not ok:
            raise RuntimeError("GetWindowRect host service could not sample the window")

        return {
            "Left": int(rect.left),
            "Top": int(rect.top),
            "Right": int(rect.right),
            "Bottom": int(rect.bottom),
        }

    def get_client_rect(self, *, hwnd: int) -> dict[str, int]:
        if sys.platform != "win32":
            raise RuntimeError("GetClientRect host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetClientRect host service requires Win32 ctypes support")

        rect = _WindowRect()
        ok = windll.user32.GetClientRect(ctypes.c_void_p(int(hwnd)), ctypes.byref(rect))
        if not ok:
            raise RuntimeError("GetClientRect host service could not sample the window")

        return {
            "Left": int(rect.left),
            "Top": int(rect.top),
            "Right": int(rect.right),
            "Bottom": int(rect.bottom),
        }

    def get_window_text(self, *, hwnd: int) -> str:
        if sys.platform != "win32":
            raise RuntimeError("GetWindowText host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetWindowText host service requires Win32 ctypes support")

        length = int(windll.user32.GetWindowTextLengthW(ctypes.c_void_p(int(hwnd))))
        buffer = ctypes.create_unicode_buffer(max(1, length + 1))
        copied = windll.user32.GetWindowTextW(
            ctypes.c_void_p(int(hwnd)),
            buffer,
            ctypes.c_int32(len(buffer)),
        )
        if copied < 0:
            raise RuntimeError("GetWindowText host service could not sample the window text")

        return str(buffer.value)


class DesktopRuntimeWindowPlacementService:
    def get_window_placement(self, *, hwnd: int) -> dict[str, object]:
        if sys.platform != "win32":
            raise RuntimeError("GetWindowPlacement host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetWindowPlacement host service requires Win32 ctypes support")

        placement = _WindowPlacement()
        placement.length = ctypes.sizeof(_WindowPlacement)

        ok = windll.user32.GetWindowPlacement(
            ctypes.c_void_p(int(hwnd)),
            ctypes.byref(placement),
        )
        if not ok:
            raise RuntimeError("GetWindowPlacement host service could not sample the window")

        return {
            "length": int(placement.length),
            "flags": int(placement.flags),
            "showCmd": int(placement.showCmd),
            "ptMinPosition": {
                "X": int(placement.ptMinPosition.x),
                "Y": int(placement.ptMinPosition.y),
            },
            "ptMaxPosition": {
                "X": int(placement.ptMaxPosition.x),
                "Y": int(placement.ptMaxPosition.y),
            },
            "rcNormalPosition": {
                "Left": int(placement.rcNormalPosition.left),
                "Top": int(placement.rcNormalPosition.top),
                "Right": int(placement.rcNormalPosition.right),
                "Bottom": int(placement.rcNormalPosition.bottom),
            },
        }

    def get_class_name(self, *, hwnd: int) -> str:
        if sys.platform != "win32":
            raise RuntimeError("GetClassName host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetClassName host service requires Win32 ctypes support")

        buffer = ctypes.create_unicode_buffer(256)
        copied = windll.user32.GetClassNameW(
            ctypes.c_void_p(int(hwnd)),
            buffer,
            ctypes.c_int32(len(buffer)),
        )
        if copied <= 0:
            raise RuntimeError("GetClassName host service could not sample the window class")

        return str(buffer.value)

    def is_zoomed(self, *, hwnd: int) -> bool:
        if sys.platform != "win32":
            raise RuntimeError("IsZoomed host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("IsZoomed host service requires Win32 ctypes support")

        return bool(windll.user32.IsZoomed(ctypes.c_void_p(int(hwnd))))

    def is_iconic(self, *, hwnd: int) -> bool:
        if sys.platform != "win32":
            raise RuntimeError("IsIconic host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("IsIconic host service requires Win32 ctypes support")

        return bool(windll.user32.IsIconic(ctypes.c_void_p(int(hwnd))))

    def is_window_visible(self, *, hwnd: int) -> bool:
        if sys.platform != "win32":
            raise RuntimeError("IsWindowVisible host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("IsWindowVisible host service requires Win32 ctypes support")

        return bool(windll.user32.IsWindowVisible(ctypes.c_void_p(int(hwnd))))

    def is_window_enabled(self, *, hwnd: int) -> bool:
        if sys.platform != "win32":
            raise RuntimeError("IsWindowEnabled host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("IsWindowEnabled host service requires Win32 ctypes support")

        return bool(windll.user32.IsWindowEnabled(ctypes.c_void_p(int(hwnd))))

    def get_window_long_ptr(self, *, hwnd: int, index: int) -> int:
        if sys.platform != "win32":
            raise RuntimeError("GetWindowLongPtr host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetWindowLongPtr host service requires Win32 ctypes support")

        user32 = windll.user32
        getter = getattr(user32, "GetWindowLongPtrW", None)
        if getter is None:
            getter = getattr(user32, "GetWindowLongW", None)
        if getter is None:
            raise RuntimeError("GetWindowLongPtr host service requires GetWindowLongPtrW or GetWindowLongW")

        value = getter(
            ctypes.c_void_p(int(hwnd)),
            ctypes.c_int32(int(index)),
        )
        return self._coerce_pointer_sized_int(value)

    def get_parent(self, *, hwnd: int) -> int:
        if sys.platform != "win32":
            raise RuntimeError("GetParent host service is available only on Windows")

        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "user32"):
            raise RuntimeError("GetParent host service requires Win32 ctypes support")

        value = windll.user32.GetParent(ctypes.c_void_p(int(hwnd)))
        if value is None:
            return 0
        return self._coerce_pointer_sized_int(value)

    @staticmethod
    def _coerce_pointer_sized_int(value: object) -> int:
        if hasattr(value, "value"):
            raw_value = getattr(value, "value")
            if raw_value is None:
                return 0
            return int(raw_value)
        return int(value)


class DesktopRuntimeScreenSamplingService:
    def get_pixel_color(self, *, x: int, y: int, hwnd: int | None) -> int:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("PixelGetColor host service is unavailable: no screen")

        window_id = 0 if hwnd is None else int(hwnd)
        local_x = int(x)
        local_y = int(y)
        if hwnd is None:
            point = QPoint(local_x, local_y)
            active_screen = QGuiApplication.screenAt(point) or screen
            origin = active_screen.geometry().topLeft()
            local_x -= origin.x()
            local_y -= origin.y()
            screen = active_screen

        pixmap = screen.grabWindow(window_id, local_x, local_y, 1, 1)
        if pixmap.isNull():
            raise RuntimeError("PixelGetColor host service could not sample the screen")

        image = pixmap.toImage()
        color = image.pixelColor(0, 0)
        return (color.red() << 16) | (color.green() << 8) | color.blue()

    def search_pixel(
        self,
        *,
        left: int,
        top: int,
        right: int,
        bottom: int,
        color: int,
        shade_variation: int,
        step: int,
        hwnd: int | None,
    ) -> list[int] | None:
        fallback_screen = QGuiApplication.primaryScreen()
        if fallback_screen is None:
            raise RuntimeError("PixelSearch host service is unavailable: no screen")

        window_id = 0 if hwnd is None else int(hwnd)
        global_search_left = min(left, right)
        global_search_right = max(left, right)
        global_search_top = min(top, bottom)
        global_search_bottom = max(top, bottom)
        width = max(1, global_search_right - global_search_left + 1)
        height = max(1, global_search_bottom - global_search_top + 1)

        screen = fallback_screen
        search_origin_x = 0
        search_origin_y = 0
        if hwnd is None:
            point = QPoint(global_search_left, global_search_top)
            screen = QGuiApplication.screenAt(point) or fallback_screen
            origin = screen.geometry().topLeft()
            search_origin_x = origin.x()
            search_origin_y = origin.y()
            search_left = global_search_left - origin.x()
            search_top = global_search_top - origin.y()
        else:
            search_left = global_search_left
            search_top = global_search_top

        pixmap = screen.grabWindow(
            window_id,
            search_left,
            search_top,
            width,
            height,
        )
        if pixmap.isNull():
            raise RuntimeError("PixelSearch host service could not sample the screen")

        image = pixmap.toImage()
        target_r = (int(color) >> 16) & 0xFF
        target_g = (int(color) >> 8) & 0xFF
        target_b = int(color) & 0xFF
        tolerance = max(0, int(shade_variation))
        stride = max(1, int(step))

        for y in range(0, image.height(), stride):
            for x in range(0, image.width(), stride):
                sample = image.pixelColor(x, y)
                if (
                    abs(sample.red() - target_r) <= tolerance
                    and abs(sample.green() - target_g) <= tolerance
                    and abs(sample.blue() - target_b) <= tolerance
                ):
                    return [search_left + x + search_origin_x, search_top + y + search_origin_y]

        return None


class DesktopRuntimeKeyboardToggleService:
    _LOCK_KEY_VK_CODES = {
        "capslock": 0x14,
        "numlock": 0x90,
        "scrolllock": 0x91,
    }

    _LOCK_KEY_PYNPUT_NAMES = {
        "capslock": "caps_lock",
        "numlock": "num_lock",
        "scrolllock": "scroll_lock",
    }

    def __init__(self) -> None:
        self._keyboard = keyboard.Controller()

    def toggle_lock_key(self, *, key: str, state: str) -> None:
        lock_key = str(key).strip().lower()
        lock_state = str(state).strip().lower()

        if lock_key not in self._LOCK_KEY_PYNPUT_NAMES:
            raise RuntimeError(f"Unsupported KeyToggle key: {key}")
        if lock_state not in {"on", "off", "toggle"}:
            raise RuntimeError(f"Unsupported KeyToggle state: {state}")

        if lock_state == "toggle":
            self._press_lock_key(lock_key)
            return

        desired_on = lock_state == "on"
        if self._is_lock_key_on(lock_key) != desired_on:
            self._press_lock_key(lock_key)

    def _press_lock_key(self, lock_key: str) -> None:
        resolved = self._resolve_lock_key(lock_key)
        self._keyboard.press(resolved)
        self._keyboard.release(resolved)

    def _resolve_lock_key(self, lock_key: str) -> keyboard.Key | keyboard.KeyCode:
        key_name = self._LOCK_KEY_PYNPUT_NAMES[lock_key]
        resolved = getattr(keyboard.Key, key_name, None)
        if resolved is not None:
            return resolved
        if sys.platform == "win32":
            return keyboard.KeyCode.from_vk(self._LOCK_KEY_VK_CODES[lock_key])
        raise RuntimeError(
            f"KeyToggle key is not supported by this pynput backend: {lock_key}"
        )

    def _is_lock_key_on(self, lock_key: str) -> bool:
        if sys.platform != "win32":
            raise RuntimeError(
                "KeyToggle host service requires Windows lock-state support"
            )

        vk_code = self._LOCK_KEY_VK_CODES[lock_key]
        state = ctypes.windll.user32.GetKeyState(vk_code)
        return bool(state & 0x0001)


@dataclass(slots=True)
class DesktopRuntimeHostServices:
    controller: object
    cursor_pos_service: DesktopRuntimeCursorPosService
    window_rect_service: DesktopRuntimeWindowRectService
    window_placement_service: DesktopRuntimeWindowPlacementService
    screen_sampling_service: DesktopRuntimeScreenSamplingService
    keyboard_toggle_service: DesktopRuntimeKeyboardToggleService
    monitor_info_service: DesktopRuntimeMonitorInfoService

    def as_mapping(self) -> dict[str, object]:
        return {
            "getcursorpos": self.get_cursor_pos,
            "getclientrect": self.get_client_rect,
            "getwindowrect": self.get_window_rect,
            "getwindowtext": self.get_window_text,
            "getwindowlongptr": self.get_window_long_ptr,
            "getparent": self.get_parent,
            "getwindowplacement": self.get_window_placement,
            "getclassname": self.get_class_name,
            "iszoomed": self.is_zoomed,
            "isiconic": self.is_iconic,
            "iswindowvisible": self.is_window_visible,
            "iswindowenabled": self.is_window_enabled,
            "getmonitorinfo": self.get_monitor_info,
            "getmonitorinfoex": self.get_monitor_info_ex,
            "msgbox": self.msgbox,
            "keytoggle": self.keytoggle,
            "pixelgetcolor": self.pixel_get_color,
            "pixelsearch": self.pixel_search,
        }

    def msgbox(
        self,
        *,
        flag: int,
        title: str,
        text: str,
        timeout: int,
        hwnd: int | None,
    ) -> int:
        _ = hwnd
        return self.controller._show_msgbox_dialog(
            flag=int(flag),
            title=str(title),
            text=str(text),
            timeout=max(0, int(timeout)),
        )

    def keytoggle(self, *, key: str, state: str) -> None:
        self.keyboard_toggle_service.toggle_lock_key(key=key, state=state)

    def get_cursor_pos(self) -> dict[str, int]:
        return self.cursor_pos_service.get_cursor_pos()

    def get_client_rect(self, *, hwnd: int) -> dict[str, int]:
        return self.window_rect_service.get_client_rect(hwnd=int(hwnd))

    def get_window_rect(self, *, hwnd: int) -> dict[str, int]:
        return self.window_rect_service.get_window_rect(hwnd=int(hwnd))

    def get_window_text(self, *, hwnd: int) -> str:
        return self.window_rect_service.get_window_text(hwnd=int(hwnd))

    def get_window_placement(self, *, hwnd: int) -> dict[str, object]:
        return self.window_placement_service.get_window_placement(hwnd=int(hwnd))

    def get_class_name(self, *, hwnd: int) -> str:
        return self.window_placement_service.get_class_name(hwnd=int(hwnd))

    def is_zoomed(self, *, hwnd: int) -> bool:
        return self.window_placement_service.is_zoomed(hwnd=int(hwnd))

    def is_iconic(self, *, hwnd: int) -> bool:
        return self.window_placement_service.is_iconic(hwnd=int(hwnd))

    def is_window_visible(self, *, hwnd: int) -> bool:
        return self.window_placement_service.is_window_visible(hwnd=int(hwnd))

    def is_window_enabled(self, *, hwnd: int) -> bool:
        return self.window_placement_service.is_window_enabled(hwnd=int(hwnd))

    def get_window_long_ptr(self, *, hwnd: int, index: int) -> int:
        return self.window_placement_service.get_window_long_ptr(
            hwnd=int(hwnd),
            index=int(index),
        )

    def get_parent(self, *, hwnd: int) -> int:
        return self.window_placement_service.get_parent(hwnd=int(hwnd))

    def get_monitor_info(self, *, hmonitor: int) -> dict[str, object]:
        return self.monitor_info_service.get_monitor_info(hmonitor=int(hmonitor))

    def get_monitor_info_ex(self, *, hmonitor: int) -> dict[str, object]:
        return self.monitor_info_service.get_monitor_info_ex(hmonitor=int(hmonitor))

    def pixel_get_color(self, *, x: int, y: int, hwnd: int | None) -> int:
        return self.screen_sampling_service.get_pixel_color(x=int(x), y=int(y), hwnd=hwnd)

    def pixel_search(
        self,
        *,
        left: int,
        top: int,
        right: int,
        bottom: int,
        color: int,
        shade_variation: int,
        step: int,
        hwnd: int | None,
    ) -> list[int] | None:
        return self.screen_sampling_service.search_pixel(
            left=int(left),
            top=int(top),
            right=int(right),
            bottom=int(bottom),
            color=int(color),
            shade_variation=int(shade_variation),
            step=int(step),
            hwnd=hwnd,
        )
