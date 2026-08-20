from __future__ import annotations

import threading

import pytest

from infrastructure.input import pynput_playback_adapter as adapter_module
from infrastructure.input.mouse_movement_profile import MouseMovementProfile
from infrastructure.input.pynput_playback_adapter import PynputPlaybackAdapter


def test_mouse_click_uses_press_and_release_pairs(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    traces: list[tuple[str, dict[str, object]]] = []

    class FakeMouseController:
        def __init__(self) -> None:
            self._position = (0, 0)

        @property
        def position(self) -> tuple[int, int]:
            return self._position

        @position.setter
        def position(self, value: tuple[int, int]) -> None:
            self._position = value
            calls.append(("position", value))

        def press(self, button) -> None:
            calls.append(("press", button))

        def release(self, button) -> None:
            calls.append(("release", button))

        def scroll(self, dx: int, dy: int) -> None:
            calls.append(("scroll", (dx, dy)))

    class FakeKeyboardController:
        def press(self, key) -> None:
            calls.append(("key_press", key))

        def release(self, key) -> None:
            calls.append(("key_release", key))

        def type(self, text: str) -> None:
            calls.append(("type", text))

    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.mouse.Controller",
        FakeMouseController,
    )
    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.keyboard.Controller",
        FakeKeyboardController,
    )
    monkeypatch.setattr(
        adapter_module.log,
        "trace",
        lambda message, **fields: traces.append((message, fields)),
    )

    adapter = PynputPlaybackAdapter()
    adapter.mouse_click("left", 2)

    assert [call[0] for call in calls] == [
        "press",
        "release",
        "press",
        "release",
    ]
    assert [trace[0] for trace in traces] == [
        "Applying mouse click via pynput",
        "Applying mouse click via pynput",
    ]
    assert [trace[1]["click_index"] for trace in traces] == [1, 2]


def test_mouse_move_uses_configurable_travel_profile_with_legacy_zero_boundary_curve(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    sleep_durations: list[float] = []

    class FakeMouseController:
        def __init__(self) -> None:
            self._position = (0, 0)

        @property
        def position(self) -> tuple[int, int]:
            return self._position

        @position.setter
        def position(self, value: tuple[int, int]) -> None:
            self._position = value
            calls.append(("position", value))

        def press(self, button) -> None:
            calls.append(("press", button))

        def release(self, button) -> None:
            calls.append(("release", button))

        def scroll(self, dx: int, dy: int) -> None:
            calls.append(("scroll", (dx, dy)))

    class FakeKeyboardController:
        def press(self, key) -> None:
            calls.append(("key_press", key))

        def release(self, key) -> None:
            calls.append(("key_release", key))

        def type(self, text: str) -> None:
            calls.append(("type", text))

    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.mouse.Controller",
        FakeMouseController,
    )
    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.keyboard.Controller",
        FakeKeyboardController,
    )
    monkeypatch.setattr(
        adapter_module,
        "sleep_seconds_interruptibly",
        lambda duration_seconds, **kwargs: sleep_durations.append(duration_seconds) or False,
    )
    monkeypatch.setattr(
        adapter_module.log,
        "trace",
        lambda message, **fields: None,
    )

    # Legacy compatibility coverage: the zero-speed point is intentionally
    # retained here to verify playback still handles older saved curves.
    # It is not the preferred/default curve shape.
    profile = MouseMovementProfile(
        duration_curve=((0, 0), (50, 240), (100, 60)),
        step_distance_px=10,
        max_steps=10,
    )
    adapter = PynputPlaybackAdapter(mouse_movement_profile=profile)
    adapter.move_mouse(30, 0, speed=50)

    assert calls[0] == ("position", (10, 0))
    assert calls[-1] == ("position", (30, 0))
    assert len(sleep_durations) == 2
    assert sleep_durations == [0.08, 0.08]


def test_mouse_move_can_be_interrupted_by_stop_request(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    stop_event = threading.Event()
    sleep_calls: list[float] = []
    sleep_kwargs: list[dict[str, object]] = []

    class FakeMouseController:
        def __init__(self) -> None:
            self._position = (0, 0)

        @property
        def position(self) -> tuple[int, int]:
            return self._position

        @position.setter
        def position(self, value: tuple[int, int]) -> None:
            self._position = value
            calls.append(("position", value))

        def press(self, button) -> None:
            calls.append(("press", button))

        def release(self, button) -> None:
            calls.append(("release", button))

        def scroll(self, dx: int, dy: int) -> None:
            calls.append(("scroll", (dx, dy)))

    class FakeKeyboardController:
        def press(self, key) -> None:
            calls.append(("key_press", key))

        def release(self, key) -> None:
            calls.append(("key_release", key))

        def type(self, text: str) -> None:
            calls.append(("type", text))

    def fake_interruptible_sleep(duration_seconds: float, *, stop_event=None, **kwargs) -> bool:
        sleep_calls.append(duration_seconds)
        sleep_kwargs.append(dict(kwargs))
        if len(sleep_calls) == 1 and stop_event is not None:
            stop_event.set()
        return bool(stop_event is not None and stop_event.is_set())

    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.mouse.Controller",
        FakeMouseController,
    )
    monkeypatch.setattr(
        "infrastructure.input.pynput_playback_adapter.keyboard.Controller",
        FakeKeyboardController,
    )
    monkeypatch.setattr(
        adapter_module,
        "sleep_seconds_interruptibly",
        fake_interruptible_sleep,
    )
    monkeypatch.setattr(
        adapter_module.log,
        "trace",
        lambda message, **fields: None,
    )

    profile = MouseMovementProfile(
        duration_curve=((0, 0), (50, 240), (100, 60)),
        step_distance_px=10,
        max_steps=10,
    )
    adapter = PynputPlaybackAdapter(
        mouse_movement_profile=profile,
        stop_event=stop_event,
        sleep_chunk_ms=20,
    )

    with pytest.raises(RuntimeError, match="Playback stopped."):
        adapter.move_mouse(30, 0, speed=50)

    assert calls[0] == ("position", (10, 0))
    assert sleep_calls == [0.08]
    assert sleep_kwargs == [{"chunk_seconds": 0.02}]
