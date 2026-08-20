from __future__ import annotations

import builtins
import sys
import threading

import pytest

from application.playback_service import PlaybackService
from core.playback.playback_events import (
    DelayPlaybackEvent,
    HotkeyPlaybackEvent,
    MouseClickPlaybackEvent,
    MouseMovePlaybackEvent,
    MouseWheelPlaybackEvent,
    TextPlaybackEvent,
)
from core.playback.executors.live_input_executor import LiveInputExecutor
from core.playback.executors.preview_input_executor import PreviewInputExecutor
from core.playback.playback_builder import PlaybackBuilder
from core.playback.playback_engine import PlaybackEngine
from core.playback.playback_mode import PlaybackMode
from core.playback.playback_plan import PlaybackPlan
from core.playback.playback_request import PlaybackRequest
from core.playback.playback_result import PlaybackResult
from core.playback.playback_result_bus import reset_playback_result_bus, get_latest_playback_result
from core.recording.recording_session import RecordingSession, RecordingState
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from editor.document.script_document import ScriptDocument


def test_preview_executor_collects_event_snapshots() -> None:
    executor = PreviewInputExecutor()
    event = MouseMovePlaybackEvent(x=1, y=2)

    executor.execute(event)

    assert executor.executed_events == [event]


def test_live_input_executor_dispatches_supported_events_in_order() -> None:
    calls: list[tuple[str, object]] = []

    class FakeHost:
        def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
            calls.append(("move_mouse", (x, y, speed)))

        def mouse_down(self, button: str) -> None:
            calls.append(("mouse_down", button))

        def mouse_up(self, button: str) -> None:
            calls.append(("mouse_up", button))

        def mouse_click(self, button: str, clicks: int) -> None:
            calls.append(("mouse_click", (button, clicks)))

        def mouse_wheel(self, delta: int) -> None:
            calls.append(("mouse_wheel", delta))

        def key_down(self, key: str) -> None:
            calls.append(("key_down", key))

        def key_up(self, key: str) -> None:
            calls.append(("key_up", key))

        def send_text(self, text: str) -> None:
            calls.append(("send_text", text))

        def sleep_ms(self, duration_ms: int) -> None:
            calls.append(("sleep_ms", duration_ms))

    executor = LiveInputExecutor(FakeHost())
    for event in [
        MouseMovePlaybackEvent(x=5, y=6),
        MouseWheelPlaybackEvent(delta=-1),
        HotkeyPlaybackEvent(keys=("ctrl", "c")),
        TextPlaybackEvent(text="ok"),
        DelayPlaybackEvent(duration_ms=30),
    ]:
        executor.execute(event)

    assert calls == [
        ("move_mouse", (5, 6, None)),
        ("mouse_wheel", -1),
        ("key_down", "ctrl"),
        ("key_down", "c"),
        ("key_up", "c"),
        ("key_up", "ctrl"),
        ("send_text", "ok"),
        ("sleep_ms", 30),
    ]


def test_live_input_executor_applies_mouse_speed_before_mouse_actions() -> None:
    calls: list[tuple[str, object]] = []

    class FakeHost:
        def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
            calls.append(("move_mouse", (x, y, speed)))

        def mouse_down(self, button: str) -> None:
            calls.append(("mouse_down", button))

        def mouse_up(self, button: str) -> None:
            calls.append(("mouse_up", button))

        def mouse_click(self, button: str, clicks: int) -> None:
            calls.append(("mouse_click", (button, clicks)))

        def mouse_wheel(self, delta: int) -> None:
            calls.append(("mouse_wheel", delta))

        def key_down(self, key: str) -> None:
            calls.append(("key_down", key))

        def key_up(self, key: str) -> None:
            calls.append(("key_up", key))

        def send_text(self, text: str) -> None:
            calls.append(("send_text", text))

        def sleep_ms(self, duration_ms: int) -> None:
            calls.append(("sleep_ms", duration_ms))

    executor = LiveInputExecutor(FakeHost(), mouse_settle_ms=500)
    executor.execute(MouseMovePlaybackEvent(x=1, y=2, speed=9))
    executor.execute(MouseClickPlaybackEvent(button="left", x=3, y=4, clicks=2, speed=7))

    assert calls == [
        ("move_mouse", (1, 2, 9)),
        ("move_mouse", (3, 4, 7)),
        ("sleep_ms", 500),
        ("mouse_click", ("left", 2)),
    ]


def test_live_input_executor_does_not_apply_default_mouse_settle() -> None:
    calls: list[tuple[str, object]] = []

    class FakeHost:
        def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
            calls.append(("move_mouse", (x, y, speed)))

        def mouse_down(self, button: str) -> None:
            calls.append(("mouse_down", button))

        def mouse_up(self, button: str) -> None:
            calls.append(("mouse_up", button))

        def mouse_click(self, button: str, clicks: int) -> None:
            calls.append(("mouse_click", (button, clicks)))

        def mouse_wheel(self, delta: int) -> None:
            calls.append(("mouse_wheel", delta))

        def key_down(self, key: str) -> None:
            calls.append(("key_down", key))

        def key_up(self, key: str) -> None:
            calls.append(("key_up", key))

        def send_text(self, text: str) -> None:
            calls.append(("send_text", text))

        def sleep_ms(self, duration_ms: int) -> None:
            calls.append(("sleep_ms", duration_ms))

    executor = LiveInputExecutor(FakeHost())
    executor.execute(MouseClickPlaybackEvent(button="left", x=3, y=4, clicks=2))

    assert calls == [
        ("move_mouse", (3, 4, None)),
        ("mouse_click", ("left", 2)),
    ]


def test_live_input_executor_interrupts_long_delay_events_when_stop_is_requested() -> None:
    calls: list[int] = []
    stop_event = threading.Event()

    class InterruptingHost:
        def sleep_ms(self, duration_ms: int) -> None:
            calls.append(int(duration_ms))
            stop_event.set()

        def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
            raise AssertionError("move_mouse should not be called for a delay event")

        def mouse_down(self, button: str) -> None:
            raise AssertionError("mouse_down should not be called for a delay event")

        def mouse_up(self, button: str) -> None:
            raise AssertionError("mouse_up should not be called for a delay event")

        def mouse_click(self, button: str, clicks: int) -> None:
            raise AssertionError("mouse_click should not be called for a delay event")

        def mouse_wheel(self, delta: int) -> None:
            raise AssertionError("mouse_wheel should not be called for a delay event")

        def key_down(self, key: str) -> None:
            raise AssertionError("key_down should not be called for a delay event")

        def key_up(self, key: str) -> None:
            raise AssertionError("key_up should not be called for a delay event")

        def send_text(self, text: str) -> None:
            raise AssertionError("send_text should not be called for a delay event")

    executor = LiveInputExecutor(InterruptingHost(), stop_event=stop_event)

    with pytest.raises(RuntimeError, match="Playback stopped."):
        executor.execute(DelayPlaybackEvent(duration_ms=30000))

    assert calls == [50]


def test_live_input_executor_releases_pressed_hotkeys_when_pressing_fails() -> None:
    calls: list[tuple[str, str]] = []

    class FailingHotkeyHost:
        def key_down(self, key: str) -> None:
            calls.append(("key_down", key))
            if key == "c":
                raise RuntimeError("boom")

        def key_up(self, key: str) -> None:
            calls.append(("key_up", key))

    executor = LiveInputExecutor(FailingHotkeyHost())

    with pytest.raises(RuntimeError, match="boom"):
        executor.execute(HotkeyPlaybackEvent(keys=("ctrl", "c", "shift")))

    assert calls == [
        ("key_down", "ctrl"),
        ("key_down", "c"),
        ("key_up", "ctrl"),
    ]


def test_playback_engine_applies_repeat_count_and_returns_success() -> None:
    executor = PreviewInputExecutor()
    engine = PlaybackEngine(executor)
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-2",
        event_count=2,
        events=[
            MouseMovePlaybackEvent(x=1, y=2),
            DelayPlaybackEvent(duration_ms=10),
        ],
        console_output=["alpha", "beta\n"],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-2",
            repeat_count=3,
        ),
    )

    assert result == PlaybackResult(
        source_kind="recording_session",
        source_id="session-play-2",
        executed_event_count=6,
        success=True,
        playback_mode="live",
        sendkeys_transport="text events",
        console_output=["alpha", "beta\n"],
        error_message=None,
    )
    assert len(executor.executed_events) == 6
    assert result.console_output == ["alpha", "beta\n"]


def test_playback_engine_converts_executor_failures_into_failed_result() -> None:
    class FailingExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, event) -> None:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("boom")

    engine = PlaybackEngine(FailingExecutor())
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-3",
        event_count=3,
        events=[
            MouseMovePlaybackEvent(x=1, y=2),
            DelayPlaybackEvent(duration_ms=10),
            TextPlaybackEvent(text="never"),
        ],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-3",
        ),
    )

    assert result.executed_event_count == 1
    assert result.success is False
    assert result.error_line is None
    assert result.error_message == "boom"


def test_playback_engine_reports_script_source_line_on_failure() -> None:
    class FailingExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, event) -> None:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("boom")

    builder = PlaybackPlanFromScriptBuilder()
    plan = builder.build(
        ScriptDocument(
            document_id="script-play-3",
            text=(
                'SendText("first")\n'
                'SendText("second")\n'
            ),
        )
    )

    engine = PlaybackEngine(FailingExecutor())

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="script_document",
            source_id="script-play-3",
        ),
    )

    assert result.executed_event_count == 1
    assert result.success is False
    assert result.error_line == 2
    assert result.error_message == "boom"


def test_playback_service_uses_request_mode_and_repeat_count() -> None:
    preview_executor = PreviewInputExecutor()
    service = PlaybackService(
        builder=PlaybackBuilder(),
        live_engine=PlaybackEngine(PreviewInputExecutor()),
        preview_engine=PlaybackEngine(preview_executor),
    )
    session = RecordingSession(
        session_id="session-play-4",
        state=RecordingState.STOPPED,
        events=[
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
            {"type": "key_down", "key": "c", "timestamp_ms": 120},
            {"type": "key_up", "key": "c", "timestamp_ms": 140},
            {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
        ],
    )

    result = service.play_recording(
        session,
        PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-4",
            mode=PlaybackMode.PREVIEW,
            repeat_count=2,
        ),
    )

    assert result.success is True
    assert result.executed_event_count == 2
    assert preview_executor.executed_events == [
        HotkeyPlaybackEvent(keys=("ctrl", "c")),
        HotkeyPlaybackEvent(keys=("ctrl", "c")),
    ]


def test_playback_service_publishes_result_to_shared_bus() -> None:
    reset_playback_result_bus()
    try:
        service = PlaybackService(
            builder=PlaybackBuilder(),
            live_engine=PlaybackEngine(PreviewInputExecutor()),
            preview_engine=PlaybackEngine(PreviewInputExecutor()),
        )
        session = RecordingSession(
            session_id="session-play-bus",
            state=RecordingState.STOPPED,
            events=[
                {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                {"type": "key_down", "key": "c", "timestamp_ms": 120},
                {"type": "key_up", "key": "c", "timestamp_ms": 150},
                {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
            ],
        )

        result = service.play_recording(
            session,
            PlaybackRequest(
                source_kind="recording_session",
                source_id="session-play-bus",
                mode=PlaybackMode.PREVIEW,
            ),
        )

        assert get_latest_playback_result() == result
    finally:
        reset_playback_result_bus()


def test_playback_service_summary_exposes_console_output() -> None:
    service = PlaybackService(
        builder=PlaybackBuilder(),
        live_engine=PlaybackEngine(PreviewInputExecutor()),
        preview_engine=PlaybackEngine(PreviewInputExecutor()),
    )
    plan = PlaybackPlan(
        source_kind="script_document",
        source_id="script-play-1",
        event_count=1,
        console_output=["alpha", "beta\n"],
        diagnostics_output=["gamma", "delta\n"],
    )

    summary = service.summarize_plan(plan)

    assert summary.console_output == ["alpha", "beta\n"]
    assert summary.diagnostics_output == ["gamma", "delta\n"]
    assert summary.event_count == 1


def test_playback_engine_carries_diagnostics_output_into_result() -> None:
    executor = PreviewInputExecutor()
    engine = PlaybackEngine(executor)
    plan = PlaybackPlan(
        source_kind="script_document",
        source_id="script-play-2",
        event_count=1,
        events=[TextPlaybackEvent(text="done")],
        console_output=["alpha", "beta\n"],
        diagnostics_output=["gamma", "delta\n"],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="script_document",
            source_id="script-play-2",
        ),
    )

    assert result.success is True
    assert result.console_output == ["alpha", "beta\n"]
    assert result.diagnostics_output == ["gamma", "delta\n"]


def test_playback_engine_steps_through_events_when_requested(
    monkeypatch,
    capsys,
) -> None:
    executor = PreviewInputExecutor()
    engine = PlaybackEngine(executor)
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-step",
        event_count=2,
        events=[
            MouseMovePlaybackEvent(x=1, y=2),
            TextPlaybackEvent(text="done"),
        ],
    )

    prompts: list[str] = []
    monkeypatch.setattr(sys, "stdin", type("FakeStdin", (), {"isatty": lambda self: True})())
    monkeypatch.setattr(builtins, "input", lambda prompt="": prompts.append(prompt) or "")

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-step",
            step_mode=True,
        ),
    )
    captured = capsys.readouterr()

    assert result.success is True
    assert result.executed_event_count == 2
    assert len(prompts) == 2
    assert "Step 1/2" in captured.out
    assert "Step 2/2" in captured.out
    assert "Press Enter to continue, or Ctrl-C to quit." in captured.out


def test_playback_engine_step_mode_ctrl_c_stops_cleanly(monkeypatch) -> None:
    class FakeStdin:
        def isatty(self) -> bool:
            return True

    def raise_keyboard_interrupt(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    monkeypatch.setattr(builtins, "input", raise_keyboard_interrupt)

    engine = PlaybackEngine(PreviewInputExecutor())
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-step-interrupt",
        event_count=1,
        events=[TextPlaybackEvent(text="done")],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-step-interrupt",
            step_mode=True,
        ),
    )

    assert result.success is False
    assert result.executed_event_count == 0
    assert result.error_message == "Playback interrupted by user."


def test_playback_engine_applies_global_delay_before_each_event(
    monkeypatch,
) -> None:
    calls: list[float] = []

    def fake_sleep(duration: float) -> None:
        calls.append(duration)

    monkeypatch.setattr("core.playback.playback_engine.time.sleep", fake_sleep)

    executor = PreviewInputExecutor()
    engine = PlaybackEngine(executor)
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-delay",
        event_count=2,
        events=[
            MouseMovePlaybackEvent(x=1, y=2),
            TextPlaybackEvent(text="done"),
        ],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-delay",
            delay_ms=250,
        ),
    )

    assert result.success is True
    assert calls == [0.25, 0.25]


def test_playback_engine_interrupts_long_global_delay_when_stop_is_requested(
    monkeypatch,
) -> None:
    calls: list[float] = []
    stop_event = threading.Event()

    def fake_sleep(duration: float) -> None:
        calls.append(duration)
        stop_event.set()

    monkeypatch.setattr("core.playback.playback_engine.time.sleep", fake_sleep)

    executor = PreviewInputExecutor()
    engine = PlaybackEngine(executor, stop_event=stop_event)
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-delay-stop",
        event_count=1,
        events=[TextPlaybackEvent(text="done")],
    )

    result = engine.play(
        plan,
        request=PlaybackRequest(
            source_kind="recording_session",
            source_id="session-play-delay-stop",
            delay_ms=30000,
        ),
    )

    assert result.success is False
    assert result.executed_event_count == 0
    assert result.error_message == "Playback interrupted by user."
    assert calls == [0.05]


def test_playback_engine_rejects_step_mode_without_tty(monkeypatch) -> None:
    class FakeStdin:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", FakeStdin())

    engine = PlaybackEngine(PreviewInputExecutor())
    plan = PlaybackPlan(
        source_kind="recording_session",
        source_id="session-play-step-fail",
        event_count=1,
        events=[TextPlaybackEvent(text="done")],
    )

    with pytest.raises(RuntimeError, match="interactive terminal"):
        engine.play(
            plan,
            request=PlaybackRequest(
                source_kind="recording_session",
                source_id="session-play-step-fail",
                step_mode=True,
            ),
        )


def test_playback_service_rejects_mismatched_request_source() -> None:
    service = PlaybackService(
        builder=PlaybackBuilder(),
        live_engine=PlaybackEngine(PreviewInputExecutor()),
        preview_engine=PlaybackEngine(PreviewInputExecutor()),
    )
    session = RecordingSession(
        session_id="session-play-5",
        state=RecordingState.STOPPED,
        events=[],
    )

    try:
        service.play_recording(
            session,
            PlaybackRequest(
                source_kind="script_document",
                source_id="wrong",
                mode=PlaybackMode.PREVIEW,
            ),
        )
    except ValueError as exc:
        assert "source_kind mismatch" in str(exc)
    else:
        raise AssertionError("Expected mismatched playback request validation failure.")
