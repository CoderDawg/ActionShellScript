from __future__ import annotations

import threading

import pytest

from application.debugging_service import DebuggingService
from core.debugging.debug_request import DebugRequest
from apps.desktop.settings import DesktopPlaybackSettings
from apps.desktop.settings import DesktopRuntimeSettings
from editor.document.script_document import ScriptDocument
from core.runtime.struct_values import StructInstance


def test_debugging_service_emits_step_and_function_events() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text=(
            "Func AddOne(value)\n"
            "    Return value + 1\n"
            "EndFunc\n"
            "\n"
            "Dim x = 1\n"
            "x = AddOne(x)\n"
        ),
    )
    events = []

    service = DebuggingService()
    handle = service.run_debug_session(
        document,
        DebugRequest(
            document_id=document.document_id,
            stop_mode="step",
        ),
        emit_event=events.append,
    )

    kinds = [event.kind for event in events]

    assert kinds[0] == "session_started"
    assert "stopped" in kinds
    assert "function_call" in kinds
    assert "function_return" in kinds
    assert kinds[-1] == "session_completed"
    assert handle.session.state == "completed"
    assert handle.controller.snapshot().variables[-1].name == "x"
    assert handle.controller.snapshot().variables[-1].value == 2


def test_debugging_service_snapshot_preserves_nested_struct_names() -> None:
    document = ScriptDocument(
        document_id="doc-structs",
        text=(
            "Struct Point\n"
            "X As Int32\n"
            "Y As Int32\n"
            "End Struct\n"
            "Struct Pair\n"
            "First As Point\n"
            "Second As Point\n"
            "End Struct\n"
            "Dim pair = Pair(Point(1, 2), Point(3, 4))\n"
        ),
    )

    service = DebuggingService()
    handle = service.run_debug_session(
        document,
        DebugRequest(
            document_id=document.document_id,
            stop_mode="continue",
        ),
    )

    snapshot = handle.controller.snapshot()
    pair_variable = snapshot.variables[-1]

    assert pair_variable.name == "pair"
    assert pair_variable.type_name == "Pair"
    assert isinstance(pair_variable.value, StructInstance)
    assert pair_variable.value.struct_name == "Pair"
    assert repr(pair_variable.value) == "Pair(First=Point(X=1, Y=2), Second=Point(X=3, Y=4))"


def test_debugging_service_emits_exception_event_on_runtime_failure() -> None:
    document = ScriptDocument(
        document_id="doc-2",
        text="Dim x = 1\nx = 1 / 0\n",
    )
    events = []

    service = DebuggingService()

    with pytest.raises(ZeroDivisionError):
        service.run_debug_session(
            document,
            DebugRequest(
                document_id=document.document_id,
                stop_mode="continue",
            ),
            emit_event=events.append,
        )

    kinds = [event.kind for event in events]

    assert "session_started" in kinds
    assert "exception" in kinds
    assert "session_failed" in kinds


def test_debugging_service_pause_loop_waits_for_resume() -> None:
    document = ScriptDocument(
        document_id="doc-3",
        text="Dim x = 1\nx = x + 2\n",
    )
    events = []

    service = DebuggingService()
    handle = service.start_debug_session(
        document,
        DebugRequest(
            document_id=document.document_id,
            stop_mode="step",
        ),
        emit_event=events.append,
    )

    runtime_result: dict[str, object] = {}
    runtime_error: dict[str, BaseException] = {}

    def run_runtime() -> None:
        try:
            runtime_result["context"] = handle.runtime.compile(document.text)
        except Exception as exc:
            runtime_error["exc"] = exc

    worker = threading.Thread(target=run_runtime, daemon=True)
    worker.start()

    assert handle.controller.wait_for_pause(timeout=1.0) is True
    assert handle.session.is_paused is True
    assert worker.is_alive() is True

    handle.controller.resume_continue()
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert "exc" not in runtime_error
    assert "context" in runtime_result

    handle.controller.sync_from_context(runtime_result["context"])
    handle.controller.complete()

    kinds = [event.kind for event in events]

    assert "stopped" in kinds
    assert "continued" in kinds
    assert kinds[-1] == "session_completed"


def test_debugging_service_pause_request_stops_on_next_statement() -> None:
    document = ScriptDocument(
        document_id="doc-4",
        text="Dim x = 1\nx = x + 2\nx = x + 3\n",
    )
    events = []

    service = DebuggingService()
    handle = service.start_debug_session(
        document,
        DebugRequest(
            document_id=document.document_id,
            stop_mode="step",
        ),
        emit_event=events.append,
    )

    runtime_result: dict[str, object] = {}
    runtime_error: dict[str, BaseException] = {}

    def run_runtime() -> None:
        try:
            runtime_result["context"] = handle.runtime.compile(document.text)
        except Exception as exc:
            runtime_error["exc"] = exc

    worker = threading.Thread(target=run_runtime, daemon=True)
    worker.start()

    assert handle.controller.wait_for_pause(timeout=1.0) is True
    assert handle.session.is_paused is True

    handle.controller.request_pause()
    handle.controller.resume_continue()

    assert handle.controller.wait_for_pause(timeout=1.0) is True
    snapshot = handle.controller.snapshot()
    assert snapshot.is_paused is True
    assert snapshot.pause_reason == "manual_pause"

    handle.controller.resume_continue()
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert "exc" not in runtime_error
    assert "context" in runtime_result

    handle.controller.sync_from_context(runtime_result["context"])
    handle.controller.complete()

    kinds = [event.kind for event in events]

    assert kinds.count("stopped") >= 2
    assert kinds[-1] == "session_completed"


def test_debugging_service_uses_saved_runtime_settings_for_script_runtime(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeScriptRuntime:
        def __init__(self, **kwargs) -> None:
            captured["kwargs"] = kwargs

        def compile(self, source: str):
            _ = source
            return None

    monkeypatch.setattr("application.debugging_service.ScriptRuntime", FakeScriptRuntime)

    service = DebuggingService(
        runtime_settings=DesktopRuntimeSettings(
            max_loop_iterations=321,
            max_call_depth=45,
            default_mouse_move_speed=18,
        )
    )
    service.start_debug_session(
        ScriptDocument(document_id="doc-4", text="WriteLn(1)\n"),
        DebugRequest(document_id="doc-4"),
    )

    kwargs = captured["kwargs"]
    assert kwargs["stop_event"] is None
    assert kwargs["max_loop_iterations"] == 321
    assert kwargs["max_call_depth"] == 45
    assert kwargs["default_mouse_move_speed"] == 18
    assert type(kwargs["debugger"]).__name__ == "RuntimeDebugHooks"


def test_debugging_service_propagates_sendkeys_key_tap_preference() -> None:
    document = ScriptDocument(
        document_id="doc-sendkeys",
        text='SendKeys("Ab")\n',
    )

    service = DebuggingService(
        playback_settings=DesktopPlaybackSettings(
            send_key_taps_instead_of_text=True,
        )
    )
    handle = service.start_debug_session(
        document,
        DebugRequest(
            document_id=document.document_id,
            stop_mode="continue",
        ),
    )

    context = handle.runtime.compile(document.text)

    assert [
        event["type"]
        for event in context.playback_events
    ] == [
        "key_down",
        "key",
        "key_up",
        "key",
    ]
    assert [event.get("key") for event in context.playback_events] == [
        "shift",
        "a",
        "shift",
        "b",
    ]
