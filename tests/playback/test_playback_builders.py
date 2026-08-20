from __future__ import annotations

from core.playback.builders.from_recording_builder import PlaybackPlanFromRecordingBuilder
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from core.playback.playback_events import (
    HotkeyPlaybackEvent,
    DelayPlaybackEvent,
    MouseClickPlaybackEvent,
    MouseMovePlaybackEvent,
    TextPlaybackEvent,
)
from core.runtime.script_runtime import ScriptRuntime
from core.recording.recording_session import RecordingSession, RecordingState
from editor.document.script_document import ScriptDocument


def test_recording_builder_normalizes_shaped_actions_into_executable_events() -> None:
    session = RecordingSession(
        session_id="session-play-1",
        state=RecordingState.STOPPED,
        events=[
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
            {"type": "key_down", "key": "c", "timestamp_ms": 120},
            {"type": "key_up", "key": "c", "timestamp_ms": 140},
            {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
        ],
    )

    plan = PlaybackPlanFromRecordingBuilder().build(session)

    assert plan.source_kind == "recording_session"
    assert plan.source_id == "session-play-1"
    assert plan.event_count == 1
    assert plan.events == [HotkeyPlaybackEvent(keys=("ctrl", "c"))]


def test_script_builder_builds_playback_events_from_runtime_execution() -> None:
    document = ScriptDocument(
        document_id="doc-play-1",
        text=(
            'MouseMove(10, 20)\n'
            'Sleep(25)\n'
            'MouseClick("left", 10, 20, 2)\n'
            'Hotkey("ctrl", "shift", "x")\n'
            'SendText("hello")\n'
        ),
    )

    plan = PlaybackPlanFromScriptBuilder().build(document)

    assert plan.source_kind == "script_document"
    assert plan.source_id == "doc-play-1"
    assert plan.event_count == 5
    assert plan.events == [
        MouseMovePlaybackEvent(x=10, y=20),
        DelayPlaybackEvent(duration_ms=25),
        MouseClickPlaybackEvent(button="left", x=10, y=20, clicks=2),
        HotkeyPlaybackEvent(keys=("ctrl", "shift", "x")),
        TextPlaybackEvent(text="hello"),
    ]


def test_script_builder_preserves_executable_events_and_write_output() -> None:
    builder = PlaybackPlanFromScriptBuilder(runtime=ScriptRuntime())
    document = ScriptDocument(
        document_id="doc-play-3",
        text=(
            'Write("alpha")\n'
            'MouseMove(10, 20)\n'
            'WriteLn("beta")\n'
        ),
    )

    plan = builder.build(document)

    assert plan.source_kind == "script_document"
    assert plan.source_id == "doc-play-3"
    assert plan.event_count == 1
    assert plan.events == [MouseMovePlaybackEvent(x=10, y=20)]
    assert plan.console_output == ["alpha", "beta\n"]
    assert plan.diagnostics_output == []


def test_script_builder_uses_runtime_semantics_for_variables_control_flow_and_calls() -> None:
    document = ScriptDocument(
        document_id="doc-play-2",
        text=(
            "Func EmitMove(x, y)\n"
            "    Dim targetX = x + 1\n"
            "    If targetX <= y Then\n"
            "        MouseMove(targetX, y)\n"
            "    EndIf\n"
            '    SendText("inner")\n'
            "EndFunc\n"
            "Dim baseX = 9\n"
            "Dim baseY = baseX + 11\n"
            "Dim should_emit = baseX < baseY\n"
            "If should_emit Then\n"
            "    EmitMove(baseX, baseY)\n"
            "EndIf\n"
            'SendText("done")\n'
        ),
    )

    plan = PlaybackPlanFromScriptBuilder().build(document)

    assert plan.source_kind == "script_document"
    assert plan.source_id == "doc-play-2"
    assert plan.event_count == 3
    assert plan.events == [
        MouseMovePlaybackEvent(x=10, y=20),
        TextPlaybackEvent(text="inner"),
        TextPlaybackEvent(text="done"),
    ]


def test_script_builder_uses_runtime_default_mouse_move_speed() -> None:
    builder = PlaybackPlanFromScriptBuilder(runtime=ScriptRuntime(default_mouse_move_speed=42))
    document = ScriptDocument(
        document_id="doc-play-4",
        text="WriteLn(GetMouseMoveSpeed())\n",
    )

    plan = builder.build(document)

    assert plan.events == []
    assert plan.console_output == ["42\n"]
