from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint

from apps.desktop import runtime_host_services


def test_keyboard_toggle_service_defers_missing_lock_key_lookup(monkeypatch) -> None:
    caps_lock = object()
    pressed: list[object] = []
    released: list[object] = []

    class FakeController:
        def press(self, key: object) -> None:
            pressed.append(key)

        def release(self, key: object) -> None:
            released.append(key)

    fake_keyboard = SimpleNamespace(
        Key=SimpleNamespace(caps_lock=caps_lock),
        KeyCode=SimpleNamespace(from_vk=lambda vk_code: ("vk", vk_code)),
        Controller=FakeController,
    )

    monkeypatch.setattr(runtime_host_services, "keyboard", fake_keyboard)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "darwin")

    service = runtime_host_services.DesktopRuntimeKeyboardToggleService()
    service.toggle_lock_key(key="capslock", state="toggle")

    assert pressed == [caps_lock]
    assert released == [caps_lock]

    with pytest.raises(RuntimeError, match="numlock"):
        service.toggle_lock_key(key="numlock", state="toggle")


def test_keyboard_toggle_service_uses_virtual_key_fallback_on_windows(monkeypatch) -> None:
    pressed: list[object] = []
    released: list[object] = []

    class FakeController:
        def press(self, key: object) -> None:
            pressed.append(key)

        def release(self, key: object) -> None:
            released.append(key)

    fake_keyboard = SimpleNamespace(
        Key=SimpleNamespace(),
        KeyCode=SimpleNamespace(from_vk=lambda vk_code: ("vk", vk_code)),
        Controller=FakeController,
    )

    monkeypatch.setattr(runtime_host_services, "keyboard", fake_keyboard)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")

    service = runtime_host_services.DesktopRuntimeKeyboardToggleService()
    service.toggle_lock_key(key="numlock", state="toggle")

    expected_key = ("vk", 0x90)
    assert pressed == [expected_key]
    assert released == [expected_key]


def test_monitor_info_service_reads_monitor_info_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_monitor_info_w(hmonitor: object, lpmi: object) -> int:
        captured["hmonitor"] = hmonitor
        monitor_info_ptr = runtime_host_services.ctypes.cast(
            lpmi,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._MonitorInfo,
            ),
        )
        monitor_info = monitor_info_ptr.contents
        monitor_info.cbSize = runtime_host_services.ctypes.sizeof(
            runtime_host_services._MonitorInfo,
        )
        monitor_info.rcMonitor.left = -10
        monitor_info.rcMonitor.top = -20
        monitor_info.rcMonitor.right = 100
        monitor_info.rcMonitor.bottom = 200
        monitor_info.rcWork.left = 0
        monitor_info.rcWork.top = 0
        monitor_info.rcWork.right = 90
        monitor_info.rcWork.bottom = 180
        monitor_info.dwFlags = 1
        return 1

    fake_user32 = SimpleNamespace(GetMonitorInfoW=fake_get_monitor_info_w)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeMonitorInfoService()
    result = service.get_monitor_info(hmonitor=123)

    assert captured["hmonitor"].value == 123
    assert result == {
        "cbSize": runtime_host_services.ctypes.sizeof(
            runtime_host_services._MonitorInfo,
        ),
        "rcMonitor": {
            "Left": -10,
            "Top": -20,
            "Right": 100,
            "Bottom": 200,
        },
        "rcWork": {
            "Left": 0,
            "Top": 0,
            "Right": 90,
            "Bottom": 180,
        },
        "dwFlags": 1,
    }


def test_monitor_info_ex_service_reads_monitor_info_ex_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_monitor_info_w(hmonitor: object, lpmi: object) -> int:
        captured["hmonitor"] = hmonitor
        monitor_info_ptr = runtime_host_services.ctypes.cast(
            lpmi,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._MonitorInfoEx,
            ),
        )
        monitor_info = monitor_info_ptr.contents
        monitor_info.cbSize = runtime_host_services.ctypes.sizeof(
            runtime_host_services._MonitorInfoEx,
        )
        monitor_info.rcMonitor.left = 1
        monitor_info.rcMonitor.top = 2
        monitor_info.rcMonitor.right = 3
        monitor_info.rcMonitor.bottom = 4
        monitor_info.rcWork.left = 5
        monitor_info.rcWork.top = 6
        monitor_info.rcWork.right = 7
        monitor_info.rcWork.bottom = 8
        monitor_info.dwFlags = 1
        monitor_info.szDevice = "DISPLAY-1"
        return 1

    fake_user32 = SimpleNamespace(GetMonitorInfoW=fake_get_monitor_info_w)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeMonitorInfoService()
    result = service.get_monitor_info_ex(hmonitor=456)

    assert captured["hmonitor"].value == 456
    assert result == {
        "cbSize": runtime_host_services.ctypes.sizeof(
            runtime_host_services._MonitorInfoEx,
        ),
        "rcMonitor": {
            "Left": 1,
            "Top": 2,
            "Right": 3,
            "Bottom": 4,
        },
        "rcWork": {
            "Left": 5,
            "Top": 6,
            "Right": 7,
            "Bottom": 8,
        },
        "dwFlags": 1,
        "szDevice": "DISPLAY-1",
    }


def test_cursor_pos_service_reads_cursor_pos_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_cursor_pos(lp_point: object) -> int:
        captured["lp_point"] = lp_point
        point_ptr = runtime_host_services.ctypes.cast(
            lp_point,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._CursorPosPoint,
            ),
        )
        point = point_ptr.contents
        point.x = 123
        point.y = 456
        return 1

    fake_user32 = SimpleNamespace(GetCursorPos=fake_get_cursor_pos)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeCursorPosService()
    result = service.get_cursor_pos()

    assert captured["lp_point"] is not None
    assert result == {"X": 123, "Y": 456}


def test_window_rect_service_reads_window_rect_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_window_rect(hwnd: object, lp_rect: object) -> int:
        captured["hwnd"] = hwnd
        rect_ptr = runtime_host_services.ctypes.cast(
            lp_rect,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._WindowRect,
            ),
        )
        rect = rect_ptr.contents
        rect.left = -20
        rect.top = -10
        rect.right = 100
        rect.bottom = 200
        return 1

    fake_user32 = SimpleNamespace(GetWindowRect=fake_get_window_rect)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowRectService()
    result = service.get_window_rect(hwnd=987)

    assert captured["hwnd"].value == 987
    assert result == {
        "Left": -20,
        "Top": -10,
        "Right": 100,
        "Bottom": 200,
    }


def test_client_rect_service_reads_client_rect_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_client_rect(hwnd: object, lp_rect: object) -> int:
        captured["hwnd"] = hwnd
        rect_ptr = runtime_host_services.ctypes.cast(
            lp_rect,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._WindowRect,
            ),
        )
        rect = rect_ptr.contents
        rect.left = 0
        rect.top = 0
        rect.right = 640
        rect.bottom = 480
        return 1

    fake_user32 = SimpleNamespace(GetClientRect=fake_get_client_rect)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowRectService()
    result = service.get_client_rect(hwnd=222)

    assert captured["hwnd"].value == 222
    assert result == {
        "Left": 0,
        "Top": 0,
        "Right": 640,
        "Bottom": 480,
    }


def test_window_text_service_reads_window_text_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_window_text_length_w(hwnd: object) -> int:
        captured["hwnd_length"] = hwnd
        return 11

    def fake_get_window_text_w(hwnd: object, buffer: object, length: object) -> int:
        captured["hwnd_text"] = hwnd
        captured["length"] = length
        buffer.value = "Hello World"
        return 11

    fake_user32 = SimpleNamespace(
        GetWindowTextLengthW=fake_get_window_text_length_w,
        GetWindowTextW=fake_get_window_text_w,
    )
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowRectService()
    result = service.get_window_text(hwnd=333)

    assert captured["hwnd_length"].value == 333
    assert captured["hwnd_text"].value == 333
    assert int(captured["length"].value) >= 12
    assert result == "Hello World"


def test_window_placement_service_reads_window_placement_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_window_placement(hwnd: object, lp_placement: object) -> int:
        captured["hwnd"] = hwnd
        placement_ptr = runtime_host_services.ctypes.cast(
            lp_placement,
            runtime_host_services.ctypes.POINTER(
                runtime_host_services._WindowPlacement,
            ),
        )
        placement = placement_ptr.contents
        placement.length = runtime_host_services.ctypes.sizeof(
            runtime_host_services._WindowPlacement,
        )
        placement.flags = 1
        placement.showCmd = 3
        placement.ptMinPosition.x = 10
        placement.ptMinPosition.y = 20
        placement.ptMaxPosition.x = 30
        placement.ptMaxPosition.y = 40
        placement.rcNormalPosition.left = 0
        placement.rcNormalPosition.top = 0
        placement.rcNormalPosition.right = 640
        placement.rcNormalPosition.bottom = 480
        return 1

    fake_user32 = SimpleNamespace(GetWindowPlacement=fake_get_window_placement)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowPlacementService()
    result = service.get_window_placement(hwnd=444)

    assert captured["hwnd"].value == 444
    assert result == {
        "length": runtime_host_services.ctypes.sizeof(
            runtime_host_services._WindowPlacement,
        ),
        "flags": 1,
        "showCmd": 3,
        "ptMinPosition": {"X": 10, "Y": 20},
        "ptMaxPosition": {"X": 30, "Y": 40},
        "rcNormalPosition": {
            "Left": 0,
            "Top": 0,
            "Right": 640,
            "Bottom": 480,
        },
    }


def test_class_name_service_reads_class_name_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_class_name_w(hwnd: object, buffer: object, length: object) -> int:
        captured["hwnd"] = hwnd
        captured["length"] = length
        buffer.value = "MyWindowClass"
        return 13

    fake_user32 = SimpleNamespace(GetClassNameW=fake_get_class_name_w)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowPlacementService()
    result = service.get_class_name(hwnd=555)

    assert captured["hwnd"].value == 555
    assert int(captured["length"].value) == 256
    assert result == "MyWindowClass"


def test_window_state_services_read_state_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_is_zoomed(hwnd: object) -> int:
        captured["zoomed"] = hwnd
        return 1

    def fake_is_iconic(hwnd: object) -> int:
        captured["iconic"] = hwnd
        return 0

    def fake_is_window_visible(hwnd: object) -> int:
        captured["visible"] = hwnd
        return 1

    def fake_is_window_enabled(hwnd: object) -> int:
        captured["enabled"] = hwnd
        return 1

    fake_user32 = SimpleNamespace(
        IsZoomed=fake_is_zoomed,
        IsIconic=fake_is_iconic,
        IsWindowVisible=fake_is_window_visible,
        IsWindowEnabled=fake_is_window_enabled,
    )
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowPlacementService()
    assert service.is_zoomed(hwnd=600) is True
    assert service.is_iconic(hwnd=601) is False
    assert service.is_window_visible(hwnd=602) is True
    assert service.is_window_enabled(hwnd=603) is True
    assert captured["zoomed"].value == 600
    assert captured["iconic"].value == 601
    assert captured["visible"].value == 602
    assert captured["enabled"].value == 603


def test_window_host_service_reads_parent_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_parent(hwnd: object) -> object:
        captured["hwnd"] = hwnd
        return runtime_host_services.ctypes.c_void_p(1234)

    fake_user32 = SimpleNamespace(GetParent=fake_get_parent)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowPlacementService()
    result = service.get_parent(hwnd=701)

    assert captured["hwnd"].value == 701
    assert result == 1234


def test_window_long_ptr_service_reads_window_long_ptr_from_win32(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_window_long_ptr_w(hwnd: object, index: object) -> int:
        captured["hwnd"] = hwnd
        captured["index"] = index
        return 0x123456789ABCDEF

    fake_user32 = SimpleNamespace(GetWindowLongPtrW=fake_get_window_long_ptr_w)
    monkeypatch.setattr(runtime_host_services.sys, "platform", "win32")
    monkeypatch.setattr(
        runtime_host_services.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    service = runtime_host_services.DesktopRuntimeWindowPlacementService()
    result = service.get_window_long_ptr(hwnd=700, index=-16)

    assert captured["hwnd"].value == 700
    assert int(captured["index"].value) == -16
    assert result == 0x123456789ABCDEF


def test_pixel_search_uses_the_matching_non_primary_screen(monkeypatch) -> None:
    calls: list[tuple[str, tuple[int, ...]]] = []

    class FakeGeometry:
        def __init__(self, left: int, top: int) -> None:
            self._top_left = QPoint(left, top)

        def topLeft(self) -> QPoint:
            return self._top_left

    class FakeImage:
        def __init__(self, color: object) -> None:
            self._color = color

        def width(self) -> int:
            return 1

        def height(self) -> int:
            return 1

        def pixelColor(self, x: int, y: int) -> object:
            _ = (x, y)
            return self._color

    class FakePixmap:
        def __init__(self, color: object) -> None:
            self._color = color

        def isNull(self) -> bool:
            return False

        def toImage(self) -> FakeImage:
            return FakeImage(self._color)

    class FakeScreen:
        def __init__(self, name: str, left: int, top: int) -> None:
            self.name = name
            self._geometry = FakeGeometry(left, top)

        def geometry(self) -> FakeGeometry:
            return self._geometry

        def grabWindow(
            self,
            window_id: int,
            x: int,
            y: int,
            width: int,
            height: int,
        ) -> FakePixmap:
            calls.append((self.name, (window_id, x, y, width, height)))
            return FakePixmap(SimpleNamespace(red=lambda: 0x11, green=lambda: 0x22, blue=lambda: 0x33))

    primary_screen = FakeScreen("primary", 0, 0)
    secondary_screen = FakeScreen("secondary", 1920, 0)

    monkeypatch.setattr(
        runtime_host_services.QGuiApplication,
        "primaryScreen",
        lambda: primary_screen,
    )
    monkeypatch.setattr(
        runtime_host_services.QGuiApplication,
        "screenAt",
        lambda point: secondary_screen if point == QPoint(2000, 100) else None,
    )

    service = runtime_host_services.DesktopRuntimeScreenSamplingService()
    result = service.search_pixel(
        left=2000,
        top=100,
        right=2000,
        bottom=100,
        color=0x112233,
        shade_variation=0,
        step=1,
        hwnd=None,
    )

    assert result == [2000, 100]
    assert calls == [("secondary", (0, 80, 100, 1, 1))]


def test_pixel_search_keeps_hwnd_grab_path_intact(monkeypatch) -> None:
    calls: list[tuple[str, tuple[int, ...]]] = []

    class FakeGeometry:
        def __init__(self, left: int, top: int) -> None:
            self._top_left = QPoint(left, top)

        def topLeft(self) -> QPoint:
            return self._top_left

    class FakeImage:
        def width(self) -> int:
            return 1

        def height(self) -> int:
            return 1

        def pixelColor(self, x: int, y: int) -> object:
            _ = (x, y)
            return SimpleNamespace(red=lambda: 0xAA, green=lambda: 0xBB, blue=lambda: 0xCC)

    class FakePixmap:
        def isNull(self) -> bool:
            return False

        def toImage(self) -> FakeImage:
            return FakeImage()

    class FakeScreen:
        def __init__(self, name: str, left: int, top: int) -> None:
            self.name = name
            self._geometry = FakeGeometry(left, top)

        def geometry(self) -> FakeGeometry:
            return self._geometry

        def grabWindow(
            self,
            window_id: int,
            x: int,
            y: int,
            width: int,
            height: int,
        ) -> FakePixmap:
            calls.append((self.name, (window_id, x, y, width, height)))
            return FakePixmap()

    primary_screen = FakeScreen("primary", 0, 0)

    def fail_screen_at(point: QPoint) -> None:
        raise AssertionError(f"screenAt should not be used for hwnd searches: {point}")

    monkeypatch.setattr(
        runtime_host_services.QGuiApplication,
        "primaryScreen",
        lambda: primary_screen,
    )
    monkeypatch.setattr(
        runtime_host_services.QGuiApplication,
        "screenAt",
        fail_screen_at,
    )

    service = runtime_host_services.DesktopRuntimeScreenSamplingService()
    result = service.search_pixel(
        left=2000,
        top=100,
        right=2000,
        bottom=100,
        color=0xAABBCC,
        shade_variation=0,
        step=1,
        hwnd=42,
    )

    assert result == [2000, 100]
    assert calls == [("primary", (42, 2000, 100, 1, 1))]
