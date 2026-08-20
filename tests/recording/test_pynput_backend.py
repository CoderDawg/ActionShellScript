from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import threading
import time

from pynput import keyboard, mouse

from core.recording.recorder_config import RecorderConfig
import infrastructure.input.pynput_backend as pynput_backend
from infrastructure.input.pynput_backend import PynputCaptureBackend


class BlockingFakeListener:
    instances: list["BlockingFakeListener"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self._wait_event = threading.Event()
        self.wait_entered = threading.Event()
        type(self).instances.append(self)

    def start(self) -> None:
        self.started = True

    def wait(self) -> None:
        self.wait_entered.set()
        self._wait_event.wait(1)

    def stop(self) -> None:
        self.stopped = True
        self._wait_event.set()


def _wait_for(condition, *, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_macos_listener_context_workaround_avoids_darwin_layout_lookup(
    monkeypatch,
) -> None:
    class FakeDarwinListener:
        pass

    FakeDarwinListener.__module__ = "pynput.keyboard._darwin"

    @contextmanager
    def original_context():
        yield ("keyboard-type", "layout-data")

    fake_darwin_module = SimpleNamespace(keycode_context=original_context)
    monkeypatch.setattr(pynput_backend.sys, "platform", "darwin")
    monkeypatch.setattr(pynput_backend.keyboard, "Listener", FakeDarwinListener)
    monkeypatch.setitem(
        pynput_backend.sys.modules,
        "pynput.keyboard._darwin",
        fake_darwin_module,
    )

    installed = pynput_backend._install_macos_listener_keycode_context_workaround()

    assert installed is True
    assert fake_darwin_module._actionshellscript_original_keycode_context is original_context
    assert fake_darwin_module._actionshellscript_listener_keycode_context_workaround is True
    with fake_darwin_module.keycode_context() as context:
        assert context == (None, None)
    assert pynput_backend._install_macos_listener_keycode_context_workaround() is False


def test_backend_emits_phase1_event_vocabulary() -> None:
    observed: list[dict[str, object]] = []
    backend = PynputCaptureBackend(config=RecorderConfig())
    backend._on_event = observed.append
    backend._base_time_ns = 0

    backend._on_mouse_move(10, 20)
    backend._on_mouse_click(10, 20, mouse.Button.left, True)
    backend._on_mouse_click(10, 20, mouse.Button.left, False)
    backend._on_mouse_scroll(10, 20, 0, 1)
    backend._on_key_press(keyboard.Key.space)
    backend._on_key_release(keyboard.Key.space)

    assert [event["type"] for event in observed] == [
        "mouse_move",
        "mouse_down",
        "mouse_up",
        "mouse_wheel",
        "key_down",
        "key_up",
    ]


def test_backend_respects_capture_flags() -> None:
    observed: list[dict[str, object]] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(
            capture_mouse_moves=False,
            capture_mouse_buttons=True,
            capture_mouse_wheel=False,
            capture_keyboard=True,
        )
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0

    backend._on_mouse_move(10, 20)
    backend._on_mouse_click(10, 20, mouse.Button.left, True)
    backend._on_mouse_scroll(10, 20, 0, 1)
    backend._on_key_press(keyboard.Key.enter)

    assert [event["type"] for event in observed] == ["mouse_down", "key_down"]


def test_backend_skips_mouse_input_for_excluded_windows(monkeypatch) -> None:
    observed: list[dict[str, object]] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(
            excluded_window_hwnds=(123,),
        )
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0

    monkeypatch.setattr(
        pynput_backend,
        "point_hits_excluded_window",
        lambda point, excluded: True,
    )

    backend._on_mouse_move(10, 20)
    backend._on_mouse_click(10, 20, mouse.Button.left, True)
    backend._on_mouse_scroll(10, 20, 0, 1)

    assert observed == []


def test_backend_skips_keyboard_input_for_excluded_active_window(monkeypatch) -> None:
    observed: list[dict[str, object]] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(
            excluded_window_hwnds=(123,),
        )
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0

    monkeypatch.setattr(
        pynput_backend,
        "active_window_is_excluded",
        lambda excluded: True,
    )

    backend._on_key_press(keyboard.Key.enter)
    backend._on_key_release(keyboard.Key.enter)

    assert observed == []


def test_stop_hotkey_requests_stop_without_recording_chord() -> None:
    observed: list[dict[str, object]] = []
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0
    backend._hotkey_parts = backend._parse_hotkey("shift+esc")

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_press(keyboard.Key.esc)

    assert stop_requests == ["stop"]
    assert observed == []


def test_partial_stop_hotkey_is_still_recorded_as_keyboard_input() -> None:
    observed: list[dict[str, object]] = []
    backend = PynputCaptureBackend(config=RecorderConfig())
    backend._on_event = observed.append
    backend._base_time_ns = 0
    backend._hotkey_parts = backend._parse_hotkey("shift+esc")

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_release(keyboard.Key.shift)

    assert [event["type"] for event in observed] == ["key_down", "key_up"]
    assert [event["key"] for event in observed] == ["shift", "shift"]


def test_custom_stop_hotkey_is_respected() -> None:
    observed: list[dict[str, object]] = []
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        stop_hotkey="alt+x",
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0
    backend._hotkey_parts = backend._parse_hotkey("alt+x")
    backend._on_key_press(keyboard.Key.alt_l)
    backend._on_key_press(keyboard.KeyCode.from_char("x"))

    assert stop_requests == ["stop"]
    assert observed == []


def test_stop_hotkey_rearms_after_release() -> None:
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._hotkey_parts = backend._parse_hotkey("shift+esc")

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_press(keyboard.Key.esc)
    backend._on_key_release(keyboard.Key.esc)
    backend._on_key_release(keyboard.Key.shift)

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_press(keyboard.Key.esc)

    assert stop_requests == ["stop", "stop"]


def test_stop_hotkey_can_match_when_final_key_only_arrives_on_release() -> None:
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._hotkey_parts = backend._parse_hotkey("shift+esc")

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_release(keyboard.Key.esc)

    assert stop_requests == ["stop"]


def test_stop_hotkey_can_accept_multiple_alternatives() -> None:
    observed: list[dict[str, object]] = []
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0
    backend._hotkey_parts = backend._parse_hotkey("shift+esc|ctrl+c")

    backend._on_key_press(keyboard.Key.ctrl_l)
    backend._on_key_press(keyboard.KeyCode.from_char("c"))

    assert stop_requests == ["stop"]
    assert observed == []


def test_backend_reports_listener_readiness_then_shutdown(monkeypatch) -> None:
    BlockingFakeListener.instances = []
    monkeypatch.setattr(pynput_backend.mouse, "Listener", BlockingFakeListener)
    monkeypatch.setattr(pynput_backend.keyboard, "Listener", BlockingFakeListener)

    diagnostics: list[tuple[str, str, dict[str, object]]] = []
    monkeypatch.setattr(
        pynput_backend.log,
        "info",
        lambda message, **fields: diagnostics.append(("info", message, fields)),
    )
    monkeypatch.setattr(
        pynput_backend.log,
        "exception",
        lambda message, exc, **fields: diagnostics.append(
            ("exception", message, {"exc": exc, **fields})
        ),
    )

    backend = PynputCaptureBackend(config=RecorderConfig())
    backend._on_event = lambda event: None

    thread = threading.Thread(target=backend.start, args=(lambda event: None,))
    thread.start()

    assert _wait_for(lambda: len(BlockingFakeListener.instances) == 2)
    assert _wait_for(lambda: backend._started is True)
    assert BlockingFakeListener.instances[0].wait_entered.wait(1)

    assert any(fields.get("event_id") == "recording.pynput.listeners_ready" for _, _, fields in diagnostics)
    assert not any(fields.get("event_id") == "recording.pynput.listeners_stopped" for _, _, fields in diagnostics)

    backend.stop()
    thread.join(1)

    assert thread.is_alive() is False
    assert backend._started is False
    assert BlockingFakeListener.instances[0].stopped is True
    assert BlockingFakeListener.instances[1].stopped is True
    assert any(fields.get("event_id") == "recording.pynput.listeners_stopped" for _, _, fields in diagnostics)
    assert any(fields.get("event_id") == "recording.pynput.stop_completed" for _, _, fields in diagnostics)


def test_stop_hotkey_requests_stop_while_backend_is_live(monkeypatch) -> None:
    BlockingFakeListener.instances = []
    monkeypatch.setattr(pynput_backend.mouse, "Listener", BlockingFakeListener)
    monkeypatch.setattr(pynput_backend.keyboard, "Listener", BlockingFakeListener)

    diagnostics: list[tuple[str, str, dict[str, object]]] = []
    monkeypatch.setattr(
        pynput_backend.log,
        "info",
        lambda message, **fields: diagnostics.append(("info", message, fields)),
    )
    monkeypatch.setattr(
        pynput_backend.log,
        "exception",
        lambda message, exc, **fields: diagnostics.append(
            ("exception", message, {"exc": exc, **fields})
        ),
    )

    observed: list[dict[str, object]] = []
    stop_requests: list[str] = []
    backend = PynputCaptureBackend(
        config=RecorderConfig(),
        on_stop_requested=lambda: stop_requests.append("stop"),
    )
    backend._on_event = observed.append
    backend._base_time_ns = 0
    backend._hotkey_parts = backend._parse_hotkey("shift+esc")

    thread = threading.Thread(target=backend.start, args=(observed.append,))
    thread.start()

    assert _wait_for(lambda: len(BlockingFakeListener.instances) == 2)
    assert _wait_for(lambda: backend._started is True)
    assert BlockingFakeListener.instances[0].wait_entered.wait(1)

    backend._on_key_press(keyboard.Key.shift)
    backend._on_key_press(keyboard.Key.esc)

    assert stop_requests == ["stop"]
    assert observed == []
    assert thread.is_alive() is True
    assert not any(fields.get("event_id") == "recording.pynput.listeners_stopped" for _, _, fields in diagnostics)

    backend.stop()
    thread.join(1)

    assert thread.is_alive() is False
    assert backend._started is False
    assert any(fields.get("event_id") == "recording.pynput.listeners_ready" for _, _, fields in diagnostics)
    assert any(fields.get("event_id") == "recording.pynput.listeners_stopped" for _, _, fields in diagnostics)
