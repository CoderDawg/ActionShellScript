from __future__ import annotations

import hashlib
import calendar
import os
import time
from pathlib import Path
from datetime import datetime
from datetime import timezone
import zlib

import pytest

import infrastructure.debug_logger as debug_logger
from infrastructure.debug_logger import DiagnosticConfig

from core.playback.playback_events import (
    DelayPlaybackEvent,
    MouseMovePlaybackEvent,
    TextPlaybackEvent,
)
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from core.runtime.execution_context import ExecutionContext
from core.runtime.script_runtime import ScriptRuntime
from core.runtime.struct_values import StructInstance
from editor.document.script_document import ScriptDocument


def test_execute_to_playback_events_uses_runtime_execution_semantics() -> None:
    runtime = ScriptRuntime()

    playback_events = runtime.execute_to_playback_events(
        (
            "Func EmitMove(x, y)\n"
            "    MouseMove(x + 1, y)\n"
            "EndFunc\n"
            "Dim should_emit = True\n"
            "If should_emit Then\n"
            "    EmitMove(9, 20)\n"
            "EndIf\n"
            "Sleep(25)\n"
            'SendText("done")\n'
        )
    )

    assert playback_events == [
        MouseMovePlaybackEvent(x=10, y=20),
        DelayPlaybackEvent(duration_ms=25),
        TextPlaybackEvent(text="done"),
    ]


def test_execute_to_playback_events_supports_function_name_return_assignment() -> None:
    runtime = ScriptRuntime()

    playback_events = runtime.execute_to_playback_events(
        (
            "Func Factorial(n)\n"
            "    If n <= 1 Then\n"
            "        Factorial = 1\n"
            "    Else\n"
            "        Factorial = n * Factorial(n - 1)\n"
            "    EndIf\n"
            "EndFunc\n"
            'WriteLn(Factorial(5))\n'
        )
    )

    assert playback_events == []
    assert runtime.get_last_script_exit_code() == 0


@pytest.mark.parametrize(
    ("script", "expected_output"),
    [
        (
            (
                "For i = 1 To 3\n"
                "    If i == 2 Then\n"
                "        Continue\n"
                "    EndIf\n"
                "    WriteLn(i)\n"
                "Next\n"
            ),
            ["1\n", "3\n"],
        ),
        (
            (
                "Dim x = 0\n"
                "While x < 3\n"
                "    x = x + 1\n"
                "    If x == 2 Then\n"
                "        Continue\n"
                "    EndIf\n"
                "    WriteLn(x)\n"
                "WEnd\n"
            ),
            ["1\n", "3\n"],
        ),
        (
            (
                "Dim x = 0\n"
                "Do\n"
                "    x = x + 1\n"
                "    If x == 2 Then\n"
                "        Continue\n"
                "    EndIf\n"
                "    WriteLn(x)\n"
                "Until x >= 3\n"
            ),
            ["1\n", "3\n"],
        ),
    ],
)
def test_continue_works_in_top_level_loops(script: str, expected_output: list[str]) -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(script)

    assert context.console_output == expected_output


def test_runtime_respects_custom_max_loop_iterations() -> None:
    runtime = ScriptRuntime(max_loop_iterations=1)

    with pytest.raises(RuntimeError, match="maximum iteration limit of 1"):
        runtime.compile(
            (
                "Dim i = 0\n"
                "While True\n"
                "    i = i + 1\n"
                "WEnd\n"
            )
        )


def test_runtime_commit_one_builtins_emit_expected_playback_events() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("keypress", ["A", 2], context)
    runtime._execute_builtin_call("sendkeys", ["^a{enter 2}"], context)
    runtime._execute_builtin_call("mouseclickdrag", ["left", 1, 2, 3, 4], context)
    runtime._execute_builtin_call("mousedrag", ["left", 1, 2, 5, 6, 30], context)

    assert [
        (event["type"], event.get("key"), event.get("button"), event.get("x"), event.get("y"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key", "A", None, None, None, None),
        ("key", "A", None, None, None, None),
        ("key_down", "ctrl", None, None, None, None),
        ("key", "a", None, None, None, None),
        ("key_up", "ctrl", None, None, None, None),
        ("key", "enter", None, None, None, None),
        ("key", "enter", None, None, None, None),
        ("mouse_down", None, "left", 1, 2, None),
        ("mouse_move", None, None, 3, 4, None),
        ("mouse_up", None, "left", 3, 4, None),
        ("mouse_down", None, "left", 1, 2, None),
        ("delay", None, None, None, None, 15),
        ("mouse_move", None, None, 3, 4, None),
        ("delay", None, None, None, None, 15),
        ("mouse_move", None, None, 5, 6, None),
        ("mouse_up", None, "left", 5, 6, None),
        ]


def test_sendkeys_supports_optional_delay_between_keypresses() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("sendkeys", ["Test", 250], context)

    assert [
        (event["type"], event.get("text"), event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("text", "T", None, None),
        ("delay", None, None, 250),
        ("text", "e", None, None),
        ("delay", None, None, 250),
        ("text", "s", None, None),
        ("delay", None, None, 250),
        ("text", "t", None, None),
    ]


def test_execute_to_playback_events_keeps_sendkeys_delay_as_text_events() -> None:
    runtime = ScriptRuntime()

    playback_events = runtime.execute_to_playback_events('SendKeys("Test", 250)\n')

    assert [event.type for event in playback_events] == [
        "text",
        "delay",
        "text",
        "delay",
        "text",
        "delay",
        "text",
    ]
    assert [getattr(event, "text", None) for event in playback_events] == [
        "T",
        None,
        "e",
        None,
        "s",
        None,
        "t",
    ]


def test_sendkeys_can_use_key_taps_instead_of_text_when_preference_is_enabled() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_special_value("PlaybackSendKeyTapsInsteadOfText", True)

    runtime._execute_builtin_call("sendkeys", ["Test", 250], context)

    assert [
        (event["type"], event.get("text"), event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key_down", None, "shift", None),
        ("key", None, "t", None),
        ("key_up", None, "shift", None),
        ("delay", None, None, 250),
        ("key", None, "e", None),
        ("delay", None, None, 250),
        ("key", None, "s", None),
        ("delay", None, None, 250),
        ("key", None, "t", None),
    ]


def test_execute_to_playback_events_can_use_key_taps_instead_of_text_when_preference_is_enabled() -> None:
    runtime = ScriptRuntime(
        special_values={"PlaybackSendKeyTapsInsteadOfText": True}
    )

    playback_events = runtime.execute_to_playback_events('SendKeys("Test", 250)\n')

    assert [event.type for event in playback_events] == [
        "key_down",
        "key_down",
        "key_up",
        "key_up",
        "delay",
        "key_down",
        "key_up",
        "delay",
        "key_down",
        "key_up",
        "delay",
        "key_down",
        "key_up",
    ]
    assert [getattr(event, "key", None) for event in playback_events] == [
        "shift",
        "t",
        "t",
        "shift",
        None,
        "e",
        "e",
        None,
        "s",
        "s",
        None,
        "t",
        "t",
    ]


def test_sendkeys_can_use_key_taps_for_double_quotes_when_preference_is_enabled() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_special_value("PlaybackSendKeyTapsInsteadOfText", True)

    runtime._execute_builtin_call("sendkeys", ['a"b', 100], context)

    assert [
        (event["type"], event.get("text"), event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key", None, "a", None),
        ("delay", None, None, 100),
        ("key_down", None, "shift", None),
        ("key", None, "'", None),
        ("key_up", None, "shift", None),
        ("delay", None, None, 100),
        ("key", None, "b", None),
    ]


def test_sendkeys_can_use_key_taps_for_spaces_when_preference_is_enabled() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_special_value("PlaybackSendKeyTapsInsteadOfText", True)

    runtime._execute_builtin_call("sendkeys", ["a b", 100], context)

    assert [
        (event["type"], event.get("text"), event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key", None, "a", None),
        ("delay", None, None, 100),
        ("key", None, "space", None),
        ("delay", None, None, 100),
        ("key", None, "b", None),
    ]


def test_sendkeys_delay_handles_punctuation_and_brace_tokens_explicitly() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("sendkeys", ["A,{enter}B", 100], context)

    assert [
        (event["type"], event.get("text"), event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("text", "A", None, None),
        ("delay", None, None, 100),
        ("text", ",", None, None),
        ("delay", None, None, 100),
        ("key", None, "enter", None),
        ("delay", None, None, 100),
        ("text", "B", None, None),
    ]


def test_execute_to_playback_events_handles_punctuation_and_brace_tokens_explicitly() -> None:
    runtime = ScriptRuntime()

    playback_events = runtime.execute_to_playback_events('SendKeys("A,{enter}B", 100)\n')

    assert [event.type for event in playback_events] == [
        "text",
        "delay",
        "text",
        "delay",
        "key_down",
        "key_up",
        "delay",
        "text",
    ]
    assert [getattr(event, "text", None) for event in playback_events] == [
        "A",
        None,
        ",",
        None,
        None,
        None,
        None,
        "B",
    ]
    assert [getattr(event, "key", None) for event in playback_events] == [
        None,
        None,
        None,
        None,
        "enter",
        "enter",
        None,
        None,
    ]


def test_sendkeys_supports_optional_delay_with_modifier_chords() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("sendkeys", ["^a", 100], context)

    assert [
        (event["type"], event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key_down", "ctrl", None),
        ("key", "a", None),
        ("key_up", "ctrl", None),
    ]


def test_sendkeys_supports_optional_delay_with_brace_repeat_tokens() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("sendkeys", ["{enter 2}", 100], context)

    assert [
        (event["type"], event.get("key"), event.get("duration_ms"))
        for event in context.playback_events
    ] == [
        ("key", "enter", None),
        ("delay", None, 100),
        ("key", "enter", None),
    ]


def test_execute_to_playback_events_supports_escaped_braces_with_delay() -> None:
    runtime = ScriptRuntime()

    playback_events = runtime.execute_to_playback_events('SendKeys("{{}}", 100)\n')

    assert [event.type for event in playback_events] == [
        "text",
        "delay",
        "text",
    ]
    assert [getattr(event, "text", None) for event in playback_events] == [
        "{",
        None,
        "}",
    ]


def test_sendkeys_rejects_negative_optional_delay() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="SendKeys argument 2 must be >= 0"):
        runtime._execute_builtin_call("sendkeys", ["abc", -1], ExecutionContext())


def test_mouse_speed_override_is_attached_to_mouse_events() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    runtime._execute_builtin_call("setmousemovespeed", [12], context)
    runtime._execute_builtin_call("mousemove", [100, 200], context)
    runtime._execute_builtin_call("mouseclick", ["left", 10, 20, 1], context)
    runtime._execute_builtin_call("mouseclickdrag", ["left", 1, 2, 3, 4], context)

    assert context.get_effective_mouse_move_speed() == 12
    assert context.playback_events == [
        {"type": "mouse_move", "x": 100, "y": 200, "speed": 12, "_debug_context": {"call_stack": [], "variables": {}, "special_values": {"Error": 0, "Extended": 0, "CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "ScriptName": "<script>", "ScriptDirectory": "", "WorkingDir": str(Path.cwd())}}},
        {"type": "mouse_click", "button": "left", "x": 10, "y": 20, "clicks": 1, "speed": 12, "_debug_context": {"call_stack": [], "variables": {}, "special_values": {"Error": 0, "Extended": 0, "CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "ScriptName": "<script>", "ScriptDirectory": "", "WorkingDir": str(Path.cwd())}}},
        {"type": "mouse_down", "button": "left", "x": 1, "y": 2, "_debug_context": {"call_stack": [], "variables": {}, "special_values": {"Error": 0, "Extended": 0, "CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "ScriptName": "<script>", "ScriptDirectory": "", "WorkingDir": str(Path.cwd())}}},
        {"type": "mouse_move", "x": 3, "y": 4, "speed": 12, "_debug_context": {"call_stack": [], "variables": {}, "special_values": {"Error": 0, "Extended": 0, "CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "ScriptName": "<script>", "ScriptDirectory": "", "WorkingDir": str(Path.cwd())}}},
        {"type": "mouse_up", "button": "left", "x": 3, "y": 4, "_debug_context": {"call_stack": [], "variables": {}, "special_values": {"Error": 0, "Extended": 0, "CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "ScriptName": "<script>", "ScriptDirectory": "", "WorkingDir": str(Path.cwd())}}},
    ]


def test_current_event_delay_override_is_script_local() -> None:
    runtime = ScriptRuntime(default_current_event_delay_ms=75)
    context = ExecutionContext(default_current_event_delay_ms=75)

    assert runtime._execute_builtin_call("getcurrenteventdelay", [], context) == 75
    assert runtime._execute_builtin_call("setcurrenteventdelay", [125], context) == 125
    assert runtime._execute_builtin_call("getcurrenteventdelay", [], context) == 125

    with pytest.raises(RuntimeError, match="Current event delay must be >= 0"):
        runtime._execute_builtin_call("setcurrenteventdelay", [-1], context)


def test_time_builtin_returns_current_unix_epoch_seconds() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.time", lambda: 1234567890.987)
        assert runtime._execute_builtin_call("time", [], context) == 1234567890


def test_utctime_builtin_returns_current_utc_calendar_time() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_struct_time = time.struct_time((2026, 5, 26, 3, 4, 5, 2, 147, 1))

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.gmtime", lambda: expected_struct_time)
        result = runtime._execute_builtin_call("utctime", [], context)

    assert isinstance(result, StructInstance)
    assert result.struct_name == "tm"
    assert result.as_dict() == {
        "tm_sec": 5,
        "tm_min": 4,
        "tm_hour": 3,
        "tm_mday": 26,
        "tm_mon": 4,
        "tm_year": 126,
        "tm_wday": 3,
        "tm_yday": 146,
        "tm_isdst": True,
    }


def test_localtime_builtin_returns_tm_struct_from_epoch_seconds() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_struct_time = time.struct_time((2026, 5, 26, 3, 4, 5, 2, 147, 1))
    seen_epoch_seconds: list[float] = []

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_epoch_seconds.append(epoch_seconds)
        return expected_struct_time

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.time", lambda: 1779848005.25)
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)

        result = runtime._execute_builtin_call("localtime", [], context)
        result_with_argument = runtime._execute_builtin_call("localtime", [42.5], context)

    assert isinstance(result, StructInstance)
    assert result.struct_name == "tm"
    assert isinstance(result_with_argument, StructInstance)
    assert result_with_argument.struct_name == "tm"
    assert seen_epoch_seconds == [1779848005.25, 42.5]
    assert result.as_dict() == {
        "tm_sec": 5,
        "tm_min": 4,
        "tm_hour": 3,
        "tm_mday": 26,
        "tm_mon": 4,
        "tm_year": 126,
        "tm_wday": 3,
        "tm_yday": 146,
        "tm_isdst": True,
    }
    assert result_with_argument.as_dict() == result.as_dict()


def test_day_of_week_builtin_returns_expected_weekday_from_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_struct_time = time.struct_time((2026, 5, 26, 3, 4, 5, 2, 147, 1))
    seen_epoch_seconds: list[float] = []

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_epoch_seconds.append(epoch_seconds)
        return expected_struct_time

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        assert runtime._execute_builtin_call("dayofweek", [1779848005.25], context) == 3

    assert seen_epoch_seconds == [1779848005.25]


def test_day_of_year_builtin_returns_expected_ordinal_day_from_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_struct_time = time.struct_time((2026, 5, 26, 3, 4, 5, 2, 147, 1))
    seen_epoch_seconds: list[float] = []

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_epoch_seconds.append(epoch_seconds)
        return expected_struct_time

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        assert runtime._execute_builtin_call("dayofyear", [1779848005.25], context) == 146

    assert seen_epoch_seconds == [1779848005.25]


def test_date_part_builtin_returns_expected_fields_from_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    base_datetime = datetime(2026, 5, 26, 15, 4, 5)

    def fake_local_datetime_from_epoch(epoch_seconds) -> datetime:
        assert epoch_seconds == 1779848005.25
        return base_datetime

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "year"], context) == 2026
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "month"], context) == 5
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "day"], context) == 26
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "hour"], context) == 15
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "minute"], context) == 4
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "second"], context) == 5
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "weekday"], context) == 2
        assert runtime._execute_builtin_call("datepart", [1779848005.25, "yearday"], context) == 145


def test_date_part_builtin_returns_expected_fields_from_tm_struct() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    tm_value = runtime._build_tm_struct_instance(time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 1)))

    assert runtime._execute_builtin_call("datepart", [tm_value, "year"], context) == 2026
    assert runtime._execute_builtin_call("datepart", [tm_value, "weekday"], context) == 2
    assert runtime._execute_builtin_call("datepart", [tm_value, "yearday"], context) == 145


def test_date_part_builtin_rejects_invalid_part() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="DatePart argument 2 must be one of"):
        runtime._execute_builtin_call("datepart", [1779848005.25, "bad"], context)


def test_date_serial_builtin_builds_local_midnight_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    seen_datetimes: list[datetime] = []

    def fake_local_epoch_from_datetime(local_datetime: datetime) -> int:
        seen_datetimes.append(local_datetime)
        return 12345

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_epoch_from_datetime", fake_local_epoch_from_datetime)
        assert runtime._execute_builtin_call("dateserial", [2026, 5, 26], context) == 12345

    assert seen_datetimes == [datetime(2026, 5, 26)]


def test_date_serial_builtin_rejects_invalid_date() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="DateSerial text is not a valid date/time: 2026-2-30"):
        runtime._execute_builtin_call("dateserial", [2026, 2, 30], context)


def test_time_serial_builtin_returns_seconds_since_midnight() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("timeserial", [15, 4, 5], context) == 15 * 3600 + 4 * 60 + 5
    assert runtime._execute_builtin_call("timeserial", [0, 0, 0], context) == 0


def test_time_serial_builtin_rejects_invalid_clock_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="TimeSerial argument 1 must be between 0 and 23"):
        runtime._execute_builtin_call("timeserial", [24, 0, 0], context)


def test_days_in_month_builtin_returns_correct_values_for_all_month_lengths() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    assert runtime._execute_builtin_call("daysinmonth", [runtime._build_tm_struct_instance(time.struct_time((2026, 1, 15, 0, 0, 0, 0, 15, 0)))], context) == 31
    assert runtime._execute_builtin_call("daysinmonth", [runtime._build_tm_struct_instance(time.struct_time((2026, 2, 15, 0, 0, 0, 0, 45, 0)))], context) == 28
    assert runtime._execute_builtin_call("daysinmonth", [runtime._build_tm_struct_instance(time.struct_time((2024, 2, 15, 0, 0, 0, 0, 45, 0)))], context) == 29
    assert runtime._execute_builtin_call("daysinmonth", [runtime._build_tm_struct_instance(time.struct_time((2026, 4, 15, 0, 0, 0, 0, 105, 0)))], context) == 30


def test_days_in_month_builtin_rejects_invalid_input() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="DaysInMonth argument 1 must be a number or tm struct"):
        runtime._execute_builtin_call("daysinmonth", ["bad"], context)


def test_is_leap_year_builtin_reports_expected_results() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("isleapyear", [2000], context) is True
    assert runtime._execute_builtin_call("isleapyear", [1900], context) is False
    assert runtime._execute_builtin_call("isleapyear", [2024], context) is True
    assert runtime._execute_builtin_call("isleapyear", [2026], context) is False

    with pytest.raises(RuntimeError, match="IsLeapYear argument 1 must be an integer"):
        runtime._execute_builtin_call("isleapyear", [True], context)


def test_is_date_builtin_accepts_locale_formatted_date_and_time_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    locale_date_text = datetime(2026, 5, 26).strftime("%x")
    locale_time_text = datetime(2026, 5, 26, 15, 4, 5).strftime("%X")

    assert runtime._execute_builtin_call("isdate", [locale_date_text], context) is True
    assert runtime._execute_builtin_call("isdate", [locale_time_text], context) is True


def test_is_date_builtin_rejects_invalid_text() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("isdate", ["not-a-date"], context) is False
    assert runtime._execute_builtin_call("isdate", [""], context) is False


def test_is_time_builtin_accepts_time_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    locale_time_text = datetime(2026, 5, 26, 15, 4, 5).strftime("%X")

    assert runtime._execute_builtin_call("istime", [locale_time_text], context) is True
    assert runtime._execute_builtin_call("istime", ["15:04:05"], context) is True
    assert runtime._execute_builtin_call("istime", ["3:04:05 PM"], context) is True


def test_is_time_builtin_rejects_dates_and_invalid_text() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("istime", ["05/26/2026"], context) is False
    assert runtime._execute_builtin_call("istime", ["05/26/2026 3:04 PM"], context) is False
    assert runtime._execute_builtin_call("istime", ["not-a-time"], context) is False
    assert runtime._execute_builtin_call("istime", [""], context) is False


def test_convert_time_zone_builtin_shifts_between_fixed_offsets() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("converttimezone", [0, "+0000", "+0200"], context) == -7200
    assert runtime._execute_builtin_call("converttimezone", [0, "-0700", "UTC"], context) == -25200
    assert runtime._execute_builtin_call("converttimezone", [0, -420, 0], context) == -25200


def test_convert_time_zone_builtin_rejects_invalid_offsets() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ConvertTimeZone argument 2 must be one of"):
        runtime._execute_builtin_call("converttimezone", [0, "bad", "+0200"], context)


def test_utc_offset_builtin_returns_local_offset_in_minutes() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    class FakeDateTime:
        @staticmethod
        def fromtimestamp(epoch_seconds: float) -> datetime:
            return datetime(2026, 5, 26, 5, 13, 25)

        @staticmethod
        def utcfromtimestamp(epoch_seconds: float) -> datetime:
            return datetime(2026, 5, 26, 12, 13, 25)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.datetime", FakeDateTime)
        assert runtime._execute_builtin_call("utcoffset", [1779797605], context) == -420


def test_utc_offset_builtin_rejects_non_numeric_input() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="UTCOffset argument 1 must be a number"):
        runtime._execute_builtin_call("utcoffset", ["bad"], context)


def test_time_zone_offset_builtin_aliases_utc_offset() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "core.runtime.script_runtime.datetime",
            type(
                "FakeDateTime",
                (),
                {
                    "fromtimestamp": staticmethod(lambda epoch_seconds: datetime(2026, 5, 26, 5, 13, 25)),
                    "utcfromtimestamp": staticmethod(lambda epoch_seconds: datetime(2026, 5, 26, 12, 13, 25)),
                },
            ),
        )
        assert runtime._execute_builtin_call("timezoneoffset", [1779797605], context) == -420


def test_start_of_day_builtin_returns_local_midnight_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_mktime_tuples: list[tuple[int, ...]] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        mapping = {
            (2026, 5, 26, 0, 0, 0): 1000.0,
        }
        return mapping[tuple(time_tuple[:6])]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert runtime._execute_builtin_call("startofday", [1779848005.25], context) == 1000

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_mktime_tuples == [(2026, 5, 26, 0, 0, 0, 0, 0, -1)]


def test_end_of_day_builtin_returns_local_last_second_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_mktime_tuples: list[tuple[int, ...]] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        mapping = {
            (2026, 5, 27, 0, 0, 0): 2000.0,
        }
        return mapping[tuple(time_tuple[:6])]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert runtime._execute_builtin_call("endofday", [1779848005.25], context) == 1999

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_mktime_tuples == [(2026, 5, 27, 0, 0, 0, 0, 0, -1)]


def test_start_of_month_builtin_returns_first_day_midnight_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_mktime_tuples: list[tuple[int, ...]] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        mapping = {
            (2026, 5, 1, 0, 0, 0): 3000.0,
        }
        return mapping[tuple(time_tuple[:6])]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert runtime._execute_builtin_call("startofmonth", [1779848005.25], context) == 3000

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_mktime_tuples == [(2026, 5, 1, 0, 0, 0, 0, 0, -1)]


def test_end_of_month_builtin_returns_last_day_last_second_epoch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_mktime_tuples: list[tuple[int, ...]] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        mapping = {
            (2026, 6, 1, 0, 0, 0): 4000.0,
        }
        return mapping[tuple(time_tuple[:6])]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert runtime._execute_builtin_call("endofmonth", [1779848005.25], context) == 3999

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_mktime_tuples == [(2026, 6, 1, 0, 0, 0, 0, 0, -1)]


def test_start_of_week_builtin_returns_expected_week_start() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_dates: list[datetime] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_local_epoch_from_datetime(self: ScriptRuntime, local_datetime: datetime) -> int:
        seen_dates.append(local_datetime)
        mapping = {
            datetime(2026, 5, 23, 0, 0, 0): 1000,
        }
        return mapping[local_datetime]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr(ScriptRuntime, "_local_epoch_from_datetime", fake_local_epoch_from_datetime)
        assert runtime._execute_builtin_call("startofweek", [1779848005.25], context) == 1000

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_dates == [datetime(2026, 5, 23, 0, 0, 0)]


def test_start_of_week_builtin_respects_custom_week_start() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_localtime_epochs: list[float] = []
    seen_dates: list[datetime] = []
    base_local_time = time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))

    def fake_localtime(epoch_seconds: float) -> time.struct_time:
        seen_localtime_epochs.append(epoch_seconds)
        return base_local_time

    def fake_local_epoch_from_datetime(self: ScriptRuntime, local_datetime: datetime) -> int:
        seen_dates.append(local_datetime)
        mapping = {
            datetime(2026, 5, 24, 0, 0, 0): 2000,
        }
        return mapping[local_datetime]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
        monkeypatch.setattr(ScriptRuntime, "_local_epoch_from_datetime", fake_local_epoch_from_datetime)
        assert runtime._execute_builtin_call("startofweek", [1779848005.25, 1], context) == 2000

    assert seen_localtime_epochs == [1779848005.25]
    assert seen_dates == [datetime(2026, 5, 24, 0, 0, 0)]


def test_start_of_week_builtin_rejects_invalid_week_start() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(
        RuntimeError,
        match="StartOfWeek argument 2 must be one of: 0, 1, 2, 3, 4, 5, 6",
    ):
        runtime._execute_builtin_call("startofweek", [1779848005.25, 7], context)


def test_nowdate_and_nowtime_builtin_return_localized_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ScriptRuntime, "_now_date", lambda self: "05/26/2026")
        monkeypatch.setattr(ScriptRuntime, "_now_time", lambda self: "3:04:05 PM")

        assert runtime._execute_builtin_call("nowdate", [], context) == "05/26/2026"
        assert runtime._execute_builtin_call("nowtime", [], context) == "3:04:05 PM"


def test_now_date_time_builtin_returns_localized_datetime_string() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ScriptRuntime, "_now_date_time", lambda self: "05/26/2026 3:04:05 PM")
        assert runtime._execute_builtin_call("nowdatetime", [], context) == "05/26/2026 3:04:05 PM"


def test_utc_date_time_builtin_returns_utc_datetime_string() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ScriptRuntime, "_utc_date_time", lambda self: "2026-05-26 22:13:25 UTC")
        assert runtime._execute_builtin_call("utcdatetime", [], context) == "2026-05-26 22:13:25 UTC"


def test_runtime_compile_uses_time_helpers_through_normal_script_execution() -> None:
    runtime = ScriptRuntime()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.time", lambda: 1779848005.25)
        monkeypatch.setattr(
            "core.runtime.script_runtime.time.localtime",
            lambda epoch_seconds=None: time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0)),
        )
        monkeypatch.setattr(
            "core.runtime.script_runtime.time.gmtime",
            lambda epoch_seconds=None: time.struct_time((2026, 5, 26, 22, 13, 25, 2, 146, 0)),
        )

        context = runtime.compile(
            (
                "Dim current_epoch = Time()\n"
                "WriteLn(current_epoch)\n"
                'WriteLn(FormatDateTime(LocalTime(current_epoch), "%Y-%m-%d %H:%M:%S"))\n'
                'WriteLn(FormatDateTime(UTCTime(), "%Y-%m-%d %H:%M:%S"))\n'
            )
        )

    assert context.console_output == [
        "1779848005\n",
        "2026-05-26 15:04:05\n",
        "2026-05-26 22:13:25\n",
    ]


def test_date_to_string_and_date_to_local_string_builtin_return_local_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    seen_local_datetimes: list[datetime] = []

    def fake_format_local_date_time_string(self, current: datetime) -> str:
        seen_local_datetimes.append(current)
        return "local-string"

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ScriptRuntime, "_format_local_date_time_string", fake_format_local_date_time_string)
        monkeypatch.setattr(
            ScriptRuntime,
            "_coerce_local_datetime_value",
            lambda self, name, value, index: datetime(2026, 5, 26, 15, 4, 5),
        )

        assert runtime._execute_builtin_call("datetostring", [], context) == "local-string"
        assert runtime._execute_builtin_call("datetolocalstring", [1779848005.25], context) == "local-string"
        assert runtime._execute_builtin_call(
            "datetostring",
            [runtime._build_tm_struct_instance(time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0)))],
            context,
        ) == "local-string"

    assert len(seen_local_datetimes) == 3


def test_date_to_utc_string_builtin_returns_utc_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    seen_utc_datetimes: list[datetime] = []

    def fake_format_utc_date_time_string(self, current: datetime) -> str:
        seen_utc_datetimes.append(current)
        return "utc-string"

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ScriptRuntime, "_format_utc_date_time_string", fake_format_utc_date_time_string)
        monkeypatch.setattr(
            ScriptRuntime,
            "_coerce_utc_datetime_value",
            lambda self, name, value, index: datetime(2026, 5, 26, 22, 13, 25),
        )

        assert runtime._execute_builtin_call("datetoutcstring", [], context) == "utc-string"
        assert runtime._execute_builtin_call("datetoutcstring", [1779848005.25], context) == "utc-string"
        assert runtime._execute_builtin_call(
            "datetoutcstring",
            [runtime._build_tm_struct_instance(time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0)))],
            context,
        ) == "utc-string"

    assert len(seen_utc_datetimes) == 3


def test_parse_date_time_builtin_parses_iso_local_datetime_text() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_mktime_tuples: list[tuple[int, ...]] = []

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        return 1234567890.75

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert runtime._execute_builtin_call("parsedatetime", ["2026-05-26 15:04:05"], context) == 1234567890

    assert seen_mktime_tuples == [(2026, 5, 26, 15, 4, 5, 1, 146, -1)]


def test_parse_date_time_builtin_parses_utc_datetime_text() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_timegm_tuples: list[tuple[int, ...]] = []

    def fake_timegm(time_tuple) -> float:
        seen_timegm_tuples.append(tuple(time_tuple))
        return 2233445566.75

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.calendar.timegm", fake_timegm)
        assert runtime._execute_builtin_call("parsedatetime", ["2026-05-26 22:13:25 UTC"], context) == 2233445566

    assert seen_timegm_tuples == [(2026, 5, 26, 22, 13, 25, 1, 146, -1)]


def test_parse_date_time_builtin_parses_text_with_explicit_local_format() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_mktime_tuples: list[tuple[int, ...]] = []

    def fake_mktime(time_tuple) -> float:
        seen_mktime_tuples.append(tuple(time_tuple))
        return 2233445566.75

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)
        assert (
            runtime._execute_builtin_call(
                "parsedatetime",
                ["05/26/2026 3:04:05 PM", "%m/%d/%Y %I:%M:%S %p"],
                context,
            )
            == 2233445566
        )

    assert seen_mktime_tuples == [(2026, 5, 26, 15, 4, 5, 1, 146, -1)]


def test_parse_date_time_builtin_parses_text_with_explicit_utc_format() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    seen_timegm_tuples: list[tuple[int, ...]] = []

    def fake_timegm(time_tuple) -> float:
        seen_timegm_tuples.append(tuple(time_tuple))
        return 3344556677.75

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("core.runtime.script_runtime.calendar.timegm", fake_timegm)
        assert (
            runtime._execute_builtin_call(
                "parsedatetime",
                ["2026-05-26 22:13:25 UTC", "%Y-%m-%d %H:%M:%S %Z"],
                context,
            )
            == 3344556677
        )

    assert seen_timegm_tuples == [(2026, 5, 26, 22, 13, 25, 1, 146, -1)]


def test_parse_date_time_in_offset_builtin_parses_text_using_supplied_offset() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call(
        "parsedatetimeinoffset",
        ["1970-01-01 02:00:00", "%Y-%m-%d %H:%M:%S", "+0200"],
        context,
    ) == 0


def test_parse_date_time_in_offset_builtin_rejects_invalid_offsets() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTimeInOffset argument 3 must be one of"):
        runtime._execute_builtin_call("parsedatetimeinoffset", ["1970-01-01 02:00:00", "%Y-%m-%d %H:%M:%S", "bad"], context)


def test_parse_date_time_builtin_parses_text_with_numeric_utc_offset() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_epoch = int(datetime(2026, 5, 26, 22, 13, 25, tzinfo=timezone.utc).timestamp())

    assert (
        runtime._execute_builtin_call(
            "parsedatetime",
            ["2026-05-26 22:13:25 +0000", "%Y-%m-%d %H:%M:%S %z"],
            context,
        )
        == expected_epoch
    )


def test_parse_date_time_builtin_parses_text_with_zulu_offset_marker() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    expected_epoch = calendar.timegm((2026, 5, 26, 22, 13, 25, 0, 0, 0))

    assert (
        runtime._execute_builtin_call(
            "parsedatetime",
            ["2026-05-26T22:13:25Z", "%Y-%m-%dT%H:%M:%S%z"],
            context,
        )
        == expected_epoch
    )


def test_parse_date_time_builtin_parses_zero_padded_numeric_day_and_month_tokens() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    source = datetime(2026, 5, 6, 7, 8, 9)

    assert (
        runtime._execute_builtin_call(
            "parsedatetime",
            ["2026-05-06 07:08:09", "%Y-%m-%d %H:%M:%S"],
            context,
        )
        == int(time.mktime(source.timetuple()))
    )


def test_parse_date_time_builtin_accepts_alternate_numeric_separators() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    source = datetime(2026, 5, 6, 7, 8, 9)

    assert runtime._execute_builtin_call(
        "parsedatetime",
        ["2026/05/06 07:08:09", "%Y-%m-%d %H:%M:%S"],
        context,
    ) == int(time.mktime(source.timetuple()))

    assert runtime._execute_builtin_call(
        "parsedatetime",
        ["05.06.2026 07:08:09", "%m/%d/%Y %H:%M:%S"],
        context,
    ) == int(time.mktime(source.timetuple()))

    assert runtime._execute_builtin_call(
        "parsedatetime",
        ["2026-05-06T07:08:09", "%Y-%m-%d %H:%M:%S"],
        context,
    ) == int(time.mktime(source.timetuple()))

    assert runtime._execute_builtin_call(
        "parsedatetime",
        ["07.08.09", "%H:%M:%S"],
        context,
    ) == calendar.timegm(datetime(1900, 1, 1, 7, 8, 9).timetuple())


def test_parse_date_time_builtin_rejects_unsupported_numeric_separator_group() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTime text is not a valid date/time: 2026_05_06"):
        runtime._execute_builtin_call("parsedatetime", ["2026_05_06", "%Y-%m-%d"], context)


def test_parse_date_time_builtin_rejects_invalid_12_hour_clock_without_meridiem() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTime text is not a valid date/time: 2026-05-26 03:04:05"):
        runtime._execute_builtin_call("parsedatetime", ["2026-05-26 03:04:05", "%Y-%m-%d %I:%M:%S"], context)


def test_parse_date_time_builtin_rejects_invalid_12_hour_clock_meridiem_mismatch() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTime text is not a valid date/time: 2026-05-26 13:04:05 PM"):
        runtime._execute_builtin_call("parsedatetime", ["2026-05-26 13:04:05 PM", "%Y-%m-%d %I:%M:%S %p"], context)


def test_parse_date_time_builtin_parses_english_abbreviated_weekday_and_month_names() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    english_weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    english_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    source = datetime(2026, 5, 26, 15, 4, 5)

    expected_text = f"{english_weekdays[source.weekday()]}, {english_months[source.month - 1]} {source.day:02d}, {source.year} {source:%I:%M:%S %p}"

    assert runtime._execute_builtin_call(
        "parsedatetime",
        [expected_text, "%a, %b %d, %Y %I:%M:%S %p"],
        context,
    ) == int(time.mktime(source.timetuple()))


def test_parse_date_time_builtin_parses_english_full_weekday_and_month_names_with_timezone() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    english_weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    english_months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    source = datetime(2026, 5, 26, 22, 13, 25)
    expected_text = f"{english_weekdays[source.weekday()]}, {english_months[source.month - 1]} {source.day:02d}, {source.year} {source:%H:%M:%S} +0000"

    assert (
        runtime._execute_builtin_call(
            "parsedatetime",
            [expected_text, "%A, %B %d, %Y %H:%M:%S %z"],
            context,
        )
        == calendar.timegm(source.timetuple())
    )


def test_parse_date_time_builtin_rejects_invalid_text() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTime text is not a valid date/time: not-a-date"):
        runtime._execute_builtin_call("parsedatetime", ["not-a-date"], context)


def test_parse_date_time_builtin_rejects_text_that_does_not_match_explicit_format() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="ParseDateTime text is not a valid date/time: 2026-05-26"):
        runtime._execute_builtin_call("parsedatetime", ["2026-05-26", "%Y-%m-%d %H:%M:%S"], context)


def test_format_date_time_builtin_formats_epoch_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    seen_epoch_seconds: list[float] = []

    def fake_local_datetime_from_epoch(epoch_seconds: float) -> datetime:
        seen_epoch_seconds.append(epoch_seconds)
        return datetime(2026, 5, 26, 15, 4, 5)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)
        assert runtime._execute_builtin_call(
            "formatdatetime",
            [1779848005.25, "%Y-%m-%d %H:%M:%S"],
            context,
        ) == "2026-05-26 15:04:05"

    assert seen_epoch_seconds == [1779848005.25]


def test_format_date_time_builtin_formats_tm_struct_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    tm_value = runtime._build_tm_struct_instance(time.struct_time((2026, 5, 26, 22, 13, 25, 2, 146, 1)))

    assert runtime._execute_builtin_call("formatdatetime", [tm_value, "%m/%d/%Y %I:%M:%S %p"], context) == "05/26/2026 10:13:25 PM"


def test_format_date_time_builtin_rejects_non_datetime_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="FormatDateTime argument 1 must be a number or tm struct"):
        runtime._execute_builtin_call("formatdatetime", ["not-a-date", "%Y-%m-%d"], context)


def test_format_date_time_in_offset_builtin_formats_epoch_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call(
        "formatdatetimeinoffset",
        [0, "%Y-%m-%d %H:%M:%S %z", "+0200"],
        context,
    ) == "1970-01-01 02:00:00 +0200"


def test_format_date_time_in_offset_builtin_formats_tm_struct_values() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    tm_value = runtime._build_tm_struct_instance(time.struct_time((2026, 5, 26, 22, 13, 25, 2, 146, 1)))

    assert runtime._execute_builtin_call(
        "formatdatetimeinoffset",
        [tm_value, "%m/%d/%Y %I:%M:%S %p %z", "-0700"],
        context,
    ) == "05/26/2026 10:13:25 PM -0700"


def test_format_date_time_in_offset_builtin_rejects_invalid_offsets() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="FormatDateTimeInOffset argument 3 must be one of"):
        runtime._execute_builtin_call("formatdatetimeinoffset", [0, "%Y-%m-%d", "bad"], context)


def test_date_add_builtin_adds_supported_time_units() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    base_datetime = datetime(2026, 5, 26, 15, 4, 5)
    seen_datetimes: list[datetime] = []

    def fake_local_datetime_from_epoch(_epoch_seconds) -> datetime:
        return base_datetime

    def fake_local_epoch_from_datetime(local_datetime: datetime) -> int:
        seen_datetimes.append(local_datetime)
        return 1000 + len(seen_datetimes)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)
        monkeypatch.setattr(runtime, "_local_epoch_from_datetime", fake_local_epoch_from_datetime)

        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 30, "seconds"], context) == 1001
        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 2, "minutes"], context) == 1002
        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 3, "hours"], context) == 1003
        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 1, "days"], context) == 1004
        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 1, "weeks"], context) == 1005

    assert seen_datetimes == [
        datetime(2026, 5, 26, 15, 4, 35),
        datetime(2026, 5, 26, 15, 6, 5),
        datetime(2026, 5, 26, 18, 4, 5),
        datetime(2026, 5, 27, 15, 4, 5),
        datetime(2026, 6, 2, 15, 4, 5),
    ]


def test_date_add_builtin_adds_months_and_years_with_month_end_clamping() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    base_datetime = datetime(2026, 1, 31, 15, 4, 5)
    seen_datetimes: list[datetime] = []

    def fake_local_datetime_from_epoch(_epoch_seconds) -> datetime:
        return base_datetime

    def fake_local_epoch_from_datetime(local_datetime: datetime) -> int:
        seen_datetimes.append(local_datetime)
        return 2000 + len(seen_datetimes)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)
        monkeypatch.setattr(runtime, "_local_epoch_from_datetime", fake_local_epoch_from_datetime)

        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 1, "months"], context) == 2001
        assert runtime._execute_builtin_call("dateadd", [1779848005.25, 1, "years"], context) == 2002

    assert seen_datetimes == [
        datetime(2026, 2, 28, 15, 4, 5),
        datetime(2027, 1, 31, 15, 4, 5),
    ]


def test_date_diff_builtin_returns_elapsed_values_for_time_units() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    start_datetime = datetime(2026, 5, 26, 15, 4, 5)
    end_datetime = datetime(2026, 5, 27, 15, 5, 35)

    def fake_local_datetime_from_epoch(epoch_seconds) -> datetime:
        return start_datetime if epoch_seconds == 1 else end_datetime

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)

        assert runtime._execute_builtin_call("datediff", [1, 2, "seconds"], context) == 86490
        assert runtime._execute_builtin_call("datediff", [1, 2, "minutes"], context) == 1441
        assert runtime._execute_builtin_call("datediff", [1, 2, "hours"], context) == 24
        assert runtime._execute_builtin_call("datediff", [1, 2, "days"], context) == 1
        assert runtime._execute_builtin_call("datediff", [1, 2, "weeks"], context) == 0


def test_date_diff_builtin_returns_elapsed_months_and_years() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    start_datetime = datetime(2024, 1, 15, 12, 0, 0)
    end_datetime = datetime(2026, 3, 15, 12, 0, 0)

    def fake_local_datetime_from_epoch(epoch_seconds) -> datetime:
        return start_datetime if epoch_seconds == 1 else end_datetime

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(runtime, "_local_datetime_from_epoch", fake_local_datetime_from_epoch)

        assert runtime._execute_builtin_call("datediff", [1, 2, "months"], context) == 26
        assert runtime._execute_builtin_call("datediff", [1, 2, "years"], context) == 2


def test_date_add_and_date_diff_builtin_reject_invalid_units() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="DateAdd argument 3 must be one of: seconds, minutes, hours, days, weeks, months, years"):
        runtime._execute_builtin_call("dateadd", [1, 1, "centuries"], context)

    with pytest.raises(RuntimeError, match="DateDiff argument 3 must be one of: seconds, minutes, hours, days, weeks, months, years"):
        runtime._execute_builtin_call("datediff", [1, 2, "centuries"], context)


def test_runtime_special_values_expose_playback_preferences_and_are_read_only() -> None:
    runtime = ScriptRuntime(
        special_values={
            "PlaybackRepeatCount": 4,
            "PlaybackEventPause": True,
            "PlaybackEventDelay": 125,
            "PlaybackMouseSettle": 17,
            "PlaybackSendKeyTapsInsteadOfText": True,
        }
    )

    context = runtime.compile(
        (
            "WriteLn(@PlaybackRepeatCount)\n"
            "WriteLn(@PlaybackEventPause)\n"
            "WriteLn(@PlaybackEventDelay)\n"
            "WriteLn(@PlaybackMouseSettle)\n"
            "WriteLn(@PlaybackSendKeyTapsInsteadOfText)\n"
        )
    )

    assert context.console_output == ["4\n", "True\n", "125\n", "17\n", "True\n"]
    assert runtime.evaluate_debug_expression("@PlaybackRepeatCount", context) == 4
    assert runtime.evaluate_debug_expression("@PlaybackEventPause", context) is True
    assert runtime.evaluate_debug_expression("@PlaybackEventDelay", context) == 125
    assert runtime.evaluate_debug_expression("@PlaybackMouseSettle", context) == 17
    assert runtime.evaluate_debug_expression("@PlaybackSendKeyTapsInsteadOfText", context) is True

    with pytest.raises(RuntimeError, match="Runtime value is read-only: @PlaybackRepeatCount"):
        runtime.compile("@PlaybackRepeatCount = 9\n")


def test_runtime_names_are_case_insensitive_for_variables_and_special_values() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Dim Foo = 1\n"
            "foo = foo + 1\n"
            "WriteLn(FOO)\n"
            "WriteLn(@crlf == @CRLF)\n"
        )
    )

    assert context.console_output == ["2\n", "True\n"]


def test_runtime_special_values_work_in_string_concatenation() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            'Dim message = "A" & @TAB & "B" & @CR & "C" & @LF & "D" & @CRLF & "E"\n'
            "WriteLn(message)\n"
        )
    )

    assert context.console_output == ["A\tB\rC\nD\r\nE\n"]


def test_runtime_special_values_can_shape_multi_line_output() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            'Write("row1" & @CRLF & "row2")\n'
            'WriteLn(@TAB & "row3")\n'
        )
    )

    assert context.console_output == ["row1\r\nrow2", "\trow3\n"]


def test_runtime_working_dir_value_uses_current_cwd(tmp_path: Path, monkeypatch) -> None:
    runtime = ScriptRuntime()
    monkeypatch.chdir(tmp_path)

    context = runtime.compile("WriteLn(@WorkingDir)\n")

    assert runtime.evaluate_debug_expression("@WorkingDir", context) == str(tmp_path)
    assert context.console_output == [f"{str(tmp_path)}\n"]


def test_runtime_working_dir_value_keeps_drive_root_trailing_separator(monkeypatch) -> None:
    runtime = ScriptRuntime()
    monkeypatch.setattr("core.runtime.execution_context.os.getcwd", lambda: "C:\\")
    monkeypatch.setattr("core.runtime.script_runtime.os.getcwd", lambda: "C:\\")

    context = runtime.compile("WriteLn(@WorkingDir)\n")

    assert runtime.evaluate_debug_expression("@WorkingDir", context) == "C:\\"
    assert context.console_output == ["C:\\\n"]


def test_runtime_script_location_values_use_source_path() -> None:
    runtime = ScriptRuntime()
    script_path = Path("C:/demo/scripts/sample.ass")

    context = runtime.compile(
        'WriteLn(@ScriptName & "|" & @ScriptDirectory & "|" & @CRLF)\n',
        source_path=script_path,
    )

    assert runtime.evaluate_debug_expression("@ScriptName", context) == "sample.ass"
    assert runtime.evaluate_debug_expression("@ScriptDirectory", context) == "C:\\demo\\scripts"
    assert context.console_output == ["sample.ass|C:\\demo\\scripts|\r\n\n"]


def test_runtime_script_directory_keeps_drive_root_trailing_separator() -> None:
    runtime = ScriptRuntime()
    root_script_path = Path("C:/sample.ass")

    context = runtime.compile(
        'WriteLn(@ScriptDirectory)\n',
        source_path=root_script_path,
    )

    assert runtime.evaluate_debug_expression("@ScriptName", context) == "sample.ass"
    assert runtime.evaluate_debug_expression("@ScriptDirectory", context) == "C:\\"
    assert context.console_output == ["C:\\\n"]


def test_runtime_local_output_builtins_write_to_runtime_collections() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("write", ["alpha"], context) == 5
    assert runtime._execute_builtin_call("writeln", ["beta"], context) == 5
    assert runtime._execute_builtin_call("diagwrite", ["gamma"], context) == 5
    assert runtime._execute_builtin_call("diagwriteln", ["delta"], context) == 6

    assert context.console_output == ["alpha", "beta\n"]
    assert context.diagnostics == []


def test_runtime_diagwrite_emits_structured_diagnostic_events() -> None:
    debug_logger.reset_diagnostic_config()
    debug_logger.set_diagnostic_config(
        DiagnosticConfig(
            enabled=True,
            log_to_file=False,
            log_to_stdout=False,
        )
    )

    runtime = ScriptRuntime()
    received: list[object] = []
    unsubscribe = debug_logger.subscribe_diagnostic_events(received.append)
    try:
        runtime.compile(
            (
                'DiagWrite("gamma")\n'
                'DiagWriteLn("delta")\n'
            )
        )
    finally:
        unsubscribe()
        debug_logger.reset_diagnostic_config()

    script_events = [
        event
        for event in received
        if getattr(event, "event_id", None) in {
            "runtime.script_output.write",
            "runtime.script_output.writeln",
        }
    ]

    assert [event.message for event in script_events] == ["gamma", "delta"]
    assert [event.fields.get("source_line") for event in script_events] == [1, 2]


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("ceiling", [1.2], 2),
        ("ceiling", [-1.2], -1),
        ("exp", [1], 2.718281828459045),
        ("floor", [1.8], 1),
        ("floor", [-1.2], -2),
        ("int", [3.9], 3),
        ("int", [-3.9], -3),
        ("round", [3.9], 4),
        ("round", [-3.9], -4),
        ("round", [1.25, 1], 1.3),
        ("round", [-1.25, 1], -1.3),
        ("round", [123.5, -1], 120),
        ("mod", [10, 3], 1),
        ("mod", [10.5, 3], 1.5),
    ],
)
def test_math_builtins_return_expected_results(name: str, args: list[object], expected: object) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    result = runtime._execute_builtin_call(name, args, context)

    assert result == expected


def test_math_builtins_reject_non_numeric_arguments() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="Ceiling argument 1 must be a number"):
        runtime._execute_builtin_call("ceiling", ["x"], context)

    with pytest.raises(RuntimeError, match="Int argument 1 must be a number"):
        runtime._execute_builtin_call("int", [True], context)

    with pytest.raises(RuntimeError, match="Round argument 2 must be an integer"):
        runtime._execute_builtin_call("round", [3.25, True], context)

    with pytest.raises(RuntimeError, match="Mod argument 2 must be a number"):
        runtime._execute_builtin_call("mod", [10, False], context)


def test_script_playback_builder_derives_console_output_and_emits_diagnostics() -> None:
    debug_logger.reset_diagnostic_config()
    debug_logger.set_diagnostic_config(
        DiagnosticConfig(
            enabled=True,
            log_to_file=False,
            log_to_stdout=False,
        )
    )

    builder = PlaybackPlanFromScriptBuilder(runtime=ScriptRuntime())
    document = ScriptDocument(
        document_id="script-playback-output",
        text=(
            'Write("alpha")\n'
            'WriteLn("beta")\n'
            'DiagWrite("gamma")\n'
            'DiagWriteLn("delta")\n'
        ),
    )

    received: list[object] = []
    unsubscribe = debug_logger.subscribe_diagnostic_events(received.append)
    try:
        plan = builder.build(document)
    finally:
        unsubscribe()
        debug_logger.reset_diagnostic_config()

    script_events = [
        event
        for event in received
        if getattr(event, "event_id", None) in {
            "runtime.script_output.write",
            "runtime.script_output.writeln",
        }
    ]

    assert plan.console_output == ["alpha", "beta\n"]
    assert plan.diagnostics_output == []
    assert [event.message for event in script_events] == ["gamma", "delta"]


def test_script_playback_builder_captures_current_event_delay_override() -> None:
    builder = PlaybackPlanFromScriptBuilder(
        runtime=ScriptRuntime(default_current_event_delay_ms=75)
    )
    document = ScriptDocument(
        document_id="script-playback-delay",
        text=(
            'WriteLn(GetCurrentEventDelay())\n'
            'SetCurrentEventDelay(125)\n'
            'WriteLn(GetCurrentEventDelay())\n'
        ),
    )

    plan = builder.build(document)

    assert plan.console_output == ["75\n", "125\n"]
    assert plan.delay_ms_override == 125


def test_host_interaction_builtins_use_host_service_seams() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def msgbox_service(**kwargs):
        calls.append(("msgbox", kwargs))
        return 42

    def pixelgetcolor_service(**kwargs):
        calls.append(("pixelgetcolor", kwargs))
        return 0x123456

    def pixelsearch_service(**kwargs):
        calls.append(("pixelsearch", kwargs))
        return [9, 10]

    def keytoggle_service(**kwargs):
        calls.append(("keytoggle", kwargs))
        return None

    runtime = ScriptRuntime(
        host_services={
            "msgbox": msgbox_service,
            "pixelgetcolor": pixelgetcolor_service,
            "pixelsearch": pixelsearch_service,
            "keytoggle": keytoggle_service,
        }
    )

    context = runtime.compile(
        (
            'MsgBox(1, "Title", "Body", 2)\n'
            "PixelGetColor(10, 20)\n"
            "PixelSearch(1, 2, 3, 4, 5, 6, 7, 8)\n"
            'KeyToggle("capslock", "toggle")\n'
        )
    )

    assert context.playback_events == []
    assert calls == [
        (
            "msgbox",
            {"flag": 1, "title": "Title", "text": "Body", "timeout": 2, "hwnd": None},
        ),
        ("pixelgetcolor", {"x": 10, "y": 20, "hwnd": None}),
        (
            "pixelsearch",
            {
                "left": 1,
                "top": 2,
                "right": 3,
                "bottom": 4,
                "color": 5,
                "shade_variation": 6,
                "step": 7,
                "hwnd": 8,
            },
        ),
        ("keytoggle", {"key": "capslock", "state": "toggle"}),
    ]


def test_get_monitor_info_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getmonitorinfo_service(**kwargs):
        calls.append(("getmonitorinfo", kwargs))
        return {
            "cbSize": 40,
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

    runtime = ScriptRuntime(host_services={"getmonitorinfo": getmonitorinfo_service})

    context = runtime.compile(
        (
            "Struct Rect\n"
            "    Left As Int32\n"
            "    Top As Int32\n"
            "    Right As Int32\n"
            "    Bottom As Int32\n"
            "End Struct\n"
            "Struct MonitorInfo\n"
            "    cbSize As UInt32\n"
            "    rcMonitor As Rect\n"
            "    rcWork As Rect\n"
            "    dwFlags As UInt32\n"
            "End Struct\n"
            "Dim info = GetMonitorInfo(123)\n"
        )
    )

    info = context.variables["info"]
    assert isinstance(info, StructInstance)
    assert info.struct_name == "MonitorInfo"
    assert info.cbSize == 40
    assert info.rcMonitor.Left == -10
    assert info.rcMonitor.Top == -20
    assert info.rcMonitor.Right == 100
    assert info.rcMonitor.Bottom == 200
    assert info.rcWork.Left == 0
    assert info.rcWork.Top == 0
    assert info.rcWork.Right == 90
    assert info.rcWork.Bottom == 180
    assert info.dwFlags == 1
    assert calls == [("getmonitorinfo", {"hmonitor": 123})]


def test_get_monitor_info_ex_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getmonitorinfoex_service(**kwargs):
        calls.append(("getmonitorinfoex", kwargs))
        return {
            "cbSize": 72,
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

    runtime = ScriptRuntime(host_services={"getmonitorinfoex": getmonitorinfoex_service})

    context = runtime.compile(
        (
            "Struct Rect\n"
            "    Left As Int32\n"
            "    Top As Int32\n"
            "    Right As Int32\n"
            "    Bottom As Int32\n"
            "End Struct\n"
            "Struct MonitorInfoEx\n"
            "    cbSize As UInt32\n"
            "    rcMonitor As Rect\n"
            "    rcWork As Rect\n"
            "    dwFlags As UInt32\n"
            "    szDevice As String\n"
            "End Struct\n"
            "Dim info = GetMonitorInfoEx(456)\n"
        )
    )

    info = context.variables["info"]
    assert isinstance(info, StructInstance)
    assert info.struct_name == "MonitorInfoEx"
    assert info.cbSize == 72
    assert info.rcMonitor.Left == 1
    assert info.rcMonitor.Top == 2
    assert info.rcMonitor.Right == 3
    assert info.rcMonitor.Bottom == 4
    assert info.rcWork.Left == 5
    assert info.rcWork.Top == 6
    assert info.rcWork.Right == 7
    assert info.rcWork.Bottom == 8
    assert info.dwFlags == 1
    assert info.szDevice == "DISPLAY-1"
    assert calls == [("getmonitorinfoex", {"hmonitor": 456})]


def test_get_cursor_pos_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getcursorpos_service(**kwargs):
        calls.append(("getcursorpos", kwargs))
        return {"X": 123, "Y": 456}

    runtime = ScriptRuntime(host_services={"getcursorpos": getcursorpos_service})

    context = runtime.compile(
        (
            "Struct Point\n"
            "    X As Int32\n"
            "    Y As Int32\n"
            "End Struct\n"
            "Dim cursor = GetCursorPos()\n"
        )
    )

    cursor = context.variables["cursor"]
    assert isinstance(cursor, StructInstance)
    assert cursor.struct_name == "Point"
    assert cursor.X == 123
    assert cursor.Y == 456
    assert calls == [("getcursorpos", {})]


def test_get_window_rect_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getwindowrect_service(**kwargs):
        calls.append(("getwindowrect", kwargs))
        return {"Left": -20, "Top": -10, "Right": 100, "Bottom": 200}

    runtime = ScriptRuntime(host_services={"getwindowrect": getwindowrect_service})

    context = runtime.compile(
        (
            "Struct Rect\n"
            "    Left As Int32\n"
            "    Top As Int32\n"
            "    Right As Int32\n"
            "    Bottom As Int32\n"
            "End Struct\n"
            "Dim rect = GetWindowRect(123)\n"
        )
    )

    rect = context.variables["rect"]
    assert isinstance(rect, StructInstance)
    assert rect.struct_name == "Rect"
    assert rect.Left == -20
    assert rect.Top == -10
    assert rect.Right == 100
    assert rect.Bottom == 200
    assert calls == [("getwindowrect", {"hwnd": 123})]


def test_get_client_rect_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getclientrect_service(**kwargs):
        calls.append(("getclientrect", kwargs))
        return {"Left": 0, "Top": 0, "Right": 640, "Bottom": 480}

    runtime = ScriptRuntime(host_services={"getclientrect": getclientrect_service})

    context = runtime.compile(
        (
            "Struct Rect\n"
            "    Left As Int32\n"
            "    Top As Int32\n"
            "    Right As Int32\n"
            "    Bottom As Int32\n"
            "End Struct\n"
            "Dim rect = GetClientRect(456)\n"
        )
    )

    rect = context.variables["rect"]
    assert isinstance(rect, StructInstance)
    assert rect.struct_name == "Rect"
    assert rect.Left == 0
    assert rect.Top == 0
    assert rect.Right == 640
    assert rect.Bottom == 480
    assert calls == [("getclientrect", {"hwnd": 456})]


def test_get_window_text_builtin_uses_host_service_and_returns_string() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getwindowtext_service(**kwargs):
        calls.append(("getwindowtext", kwargs))
        return "Hello World"

    runtime = ScriptRuntime(host_services={"getwindowtext": getwindowtext_service})

    context = runtime.compile(
        "Dim title = GetWindowText(789)\n"
    )

    assert context.variables["title"] == "Hello World"
    assert calls == [("getwindowtext", {"hwnd": 789})]


def test_get_window_placement_builtin_uses_host_service_and_returns_struct() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getwindowplacement_service(**kwargs):
        calls.append(("getwindowplacement", kwargs))
        return {
            "length": 60,
            "flags": 1,
            "showCmd": 3,
            "ptMinPosition": {"X": 10, "Y": 20},
            "ptMaxPosition": {"X": 30, "Y": 40},
            "rcNormalPosition": {"Left": 0, "Top": 0, "Right": 640, "Bottom": 480},
        }

    runtime = ScriptRuntime(host_services={"getwindowplacement": getwindowplacement_service})

    context = runtime.compile(
        (
            "Struct Point\n"
            "    X As Int32\n"
            "    Y As Int32\n"
            "End Struct\n"
            "Struct Rect\n"
            "    Left As Int32\n"
            "    Top As Int32\n"
            "    Right As Int32\n"
            "    Bottom As Int32\n"
            "End Struct\n"
            "Struct WindowPlacement\n"
            "    length As UInt32\n"
            "    flags As UInt32\n"
            "    showCmd As UInt32\n"
            "    ptMinPosition As Point\n"
            "    ptMaxPosition As Point\n"
            "    rcNormalPosition As Rect\n"
            "End Struct\n"
            "Dim placement = GetWindowPlacement(321)\n"
        )
    )

    placement = context.variables["placement"]
    assert isinstance(placement, StructInstance)
    assert placement.struct_name == "WindowPlacement"
    assert placement.length == 60
    assert placement.flags == 1
    assert placement.showCmd == 3
    assert placement.ptMinPosition.X == 10
    assert placement.ptMinPosition.Y == 20
    assert placement.ptMaxPosition.X == 30
    assert placement.ptMaxPosition.Y == 40
    assert placement.rcNormalPosition.Right == 640
    assert placement.rcNormalPosition.Bottom == 480
    assert calls == [("getwindowplacement", {"hwnd": 321})]


def test_get_class_name_builtin_uses_host_service_and_returns_string() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getclassname_service(**kwargs):
        calls.append(("getclassname", kwargs))
        return "MyWindowClass"

    runtime = ScriptRuntime(host_services={"getclassname": getclassname_service})

    context = runtime.compile(
        "Dim class_name = GetClassName(222)\n"
    )

    assert context.variables["class_name"] == "MyWindowClass"
    assert calls == [("getclassname", {"hwnd": 222})]


def test_get_window_state_builtins_use_host_service_and_return_bool() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def iszoomed_service(**kwargs):
        calls.append(("iszoomed", kwargs))
        return True

    def isiconic_service(**kwargs):
        calls.append(("isiconic", kwargs))
        return False

    runtime = ScriptRuntime(
        host_services={
            "iszoomed": iszoomed_service,
            "isiconic": isiconic_service,
        }
    )

    context = runtime.compile(
        (
            "Dim zoomed = IsZoomed(100)\n"
            "Dim iconic = IsIconic(101)\n"
        )
    )

    assert context.variables["zoomed"] is True
    assert context.variables["iconic"] is False
    assert calls == [("iszoomed", {"hwnd": 100}), ("isiconic", {"hwnd": 101})]


def test_get_window_visible_builtin_uses_host_service_and_returns_bool() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def iswindowvisible_service(**kwargs):
        calls.append(("iswindowvisible", kwargs))
        return True

    runtime = ScriptRuntime(host_services={"iswindowvisible": iswindowvisible_service})

    context = runtime.compile(
        "Dim visible = IsWindowVisible(222)\n"
    )

    assert context.variables["visible"] is True
    assert calls == [("iswindowvisible", {"hwnd": 222})]


def test_get_window_enabled_builtin_uses_host_service_and_returns_bool() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def iswindowenabled_service(**kwargs):
        calls.append(("iswindowenabled", kwargs))
        return False

    runtime = ScriptRuntime(host_services={"iswindowenabled": iswindowenabled_service})

    context = runtime.compile(
        "Dim enabled = IsWindowEnabled(333)\n"
    )

    assert context.variables["enabled"] is False
    assert calls == [("iswindowenabled", {"hwnd": 333})]


def test_get_window_long_ptr_builtin_uses_host_service_and_returns_integer() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getwindowlongptr_service(**kwargs):
        calls.append(("getwindowlongptr", kwargs))
        return 0x123456789ABCDEF

    runtime = ScriptRuntime(host_services={"getwindowlongptr": getwindowlongptr_service})

    context = runtime.compile(
        "Dim style = GetWindowLongPtr(333, -16)\n"
    )

    assert context.variables["style"] == 0x123456789ABCDEF
    assert calls == [("getwindowlongptr", {"hwnd": 333, "index": -16})]


def test_get_parent_builtin_uses_host_service_and_returns_integer() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def getparent_service(**kwargs):
        calls.append(("getparent", kwargs))
        return 1234

    runtime = ScriptRuntime(host_services={"getparent": getparent_service})

    context = runtime.compile(
        "Dim parent = GetParent(444)\n"
    )

    assert context.variables["parent"] == 1234
    assert calls == [("getparent", {"hwnd": 444})]


def test_commit_four_file_builtins_read_write_append_and_errors(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    file_path = tmp_path / "sample.txt"
    nested_path = tmp_path / "missing" / "child.txt"
    dir_path = tmp_path / "folder"
    dir_path.mkdir()

    assert runtime._execute_builtin_call("writefile", [str(file_path), "alpha"], context) is None
    assert runtime._execute_builtin_call("appendfile", [str(file_path), "beta"], context) is None
    assert runtime._execute_builtin_call("readfile", [str(file_path)], context) == "alphabeta"
    assert runtime._execute_builtin_call("fileexists", [str(file_path)], context) is True
    assert runtime._execute_builtin_call("pathexists", [str(file_path)], context) is True
    assert runtime._execute_builtin_call("direxists", [str(dir_path)], context) is True

    runtime._execute_builtin_call("createdir", [str(tmp_path / "newdir")], context)
    assert (tmp_path / "newdir").is_dir()

    with pytest.raises(RuntimeError, match="ReadFile file not found"):
        runtime._execute_builtin_call("readfile", [str(tmp_path / "missing.txt")], context)

    with pytest.raises(RuntimeError, match="ReadFile path is a directory"):
        runtime._execute_builtin_call("readfile", [str(dir_path)], context)

    with pytest.raises(RuntimeError, match="WriteFile parent directory not found"):
        runtime._execute_builtin_call("writefile", [str(nested_path), "text"], context)

    with pytest.raises(RuntimeError, match="DeleteFile path is a directory"):
        runtime._execute_builtin_call("deletefile", [str(dir_path)], context)


def test_commit_four_path_builtins_and_validation(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "report.txt"
    file_path.write_text("content", encoding="utf-8")

    combined = runtime._execute_builtin_call(
        "pathcombine",
        [str(base_dir), "sub", "report.txt"],
        context,
    )
    assert combined == os.path.join(str(base_dir), "sub", "report.txt")

    normalized = runtime._execute_builtin_call(
        "pathnormalize",
        [str(base_dir / ".." / "base" / "." / "report.txt")],
        context,
    )
    assert normalized == os.path.normpath(str(base_dir / ".." / "base" / "." / "report.txt"))

    assert runtime._execute_builtin_call("filename", [str(file_path)], context) == "report.txt"
    assert runtime._execute_builtin_call("directoryname", [str(file_path)], context) == str(base_dir)
    assert runtime._execute_builtin_call("extensionname", [str(file_path)], context) == ".txt"
    assert runtime._execute_builtin_call("ispathvalid", [str(file_path)], context) is True
    assert runtime._execute_builtin_call("ispathvalid", ["bad<path>"], context) is False


def test_commit_five_binary_builtins_round_trip_and_validation(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    file_path = tmp_path / "payload.bin"

    assert runtime._execute_builtin_call("writebytes", [str(file_path), b"abc"], context) is None
    assert runtime._execute_builtin_call("appendbytes", [str(file_path), bytearray(b"def")], context) is None
    assert runtime._execute_builtin_call("readbytes", [str(file_path)], context) == b"abcdef"
    assert runtime._execute_builtin_call("binarylength", [b"abcdef"], context) == 6
    assert runtime._execute_builtin_call("hex", [b"\x00\xff"], context) == "00ff"
    assert runtime._execute_builtin_call("fromhex", ["00ff"], context) == b"\x00\xff"
    assert runtime._execute_builtin_call("base64", [b"hello"], context) == "aGVsbG8="
    assert runtime._execute_builtin_call("frombase64", ["aGVsbG8="], context) == b"hello"
    assert runtime._execute_builtin_call("binary", ["text"], context) == b"text"
    assert runtime._execute_builtin_call("binarymid", [b"abcdef", 2, 3], context) == b"bcd"
    assert runtime._execute_builtin_call("binarymid", [b"abcdef", 4], context) == b"def"
    assert runtime._execute_builtin_call("binarytostring", [b"hello"], context) == "hello"
    assert runtime._execute_builtin_call("binarytostring", [b"\xff"], context) == "ÿ"

    with pytest.raises(RuntimeError, match="ReadBytes file not found"):
        runtime._execute_builtin_call("readbytes", [str(tmp_path / "missing.bin")], context)

    with pytest.raises(RuntimeError, match="FromHex text is not valid hexadecimal"):
        runtime._execute_builtin_call("fromhex", ["not-hex"], context)

    with pytest.raises(RuntimeError, match="FromBase64 text is not valid base64"):
        runtime._execute_builtin_call("frombase64", ["not-base64"], context)

    with pytest.raises(RuntimeError, match="BinaryMid argument 2 must be >= 1"):
        runtime._execute_builtin_call("binarymid", [b"abc", 0], context)

    with pytest.raises(RuntimeError, match="BinaryToString argument 2 must be one of"):
        runtime._execute_builtin_call("binarytostring", [b"abc", 9], context)


def test_commit_six_directory_and_file_enumeration_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    root = tmp_path / "inventory"
    root.mkdir()
    alpha_dir = root / "alpha"
    beta_dir = root / "beta"
    nested_dir = root / "nested"
    alpha_dir.mkdir()
    beta_dir.mkdir()
    nested_dir.mkdir()

    alpha_file = root / "alpha.txt"
    beta_file = root / "beta.csv"
    gamma_file = root / "gamma.log"
    alpha_file.write_text("alpha", encoding="utf-8")
    beta_file.write_text("beta", encoding="utf-8")
    gamma_file.write_text("gamma", encoding="utf-8")

    empty_dir = root / "empty"
    empty_dir.mkdir()

    assert runtime._execute_builtin_call("directorylist", [str(root)], context) == [
        str(alpha_dir),
        str(beta_dir),
        str(empty_dir),
        str(nested_dir),
    ]
    assert runtime._execute_builtin_call("directorylist", [str(root), "b*"], context) == [
        str(beta_dir),
    ]
    assert runtime._execute_builtin_call("directorylist", [str(empty_dir)], context) == []

    assert runtime._execute_builtin_call("filelist", [str(root)], context) == [
        str(alpha_file),
        str(beta_file),
        str(gamma_file),
    ]
    assert runtime._execute_builtin_call("filelist", [str(root), "*.txt"], context) == [
        str(alpha_file),
    ]
    assert runtime._execute_builtin_call("filelist", [str(empty_dir)], context) == []

    with pytest.raises(RuntimeError, match="DirectoryList file not found"):
        runtime._execute_builtin_call("directorylist", [str(tmp_path / "missing")], context)

    with pytest.raises(RuntimeError, match="FileList path exists and is not a directory"):
        runtime._execute_builtin_call("filelist", [str(alpha_file)], context)


def test_commit_six_directory_traversal_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    root = tmp_path / "tree"
    root.mkdir()
    alpha_dir = root / "alpha"
    beta_dir = root / "beta"
    nested_dir = root / "nested"
    nested_deep_dir = nested_dir / "deep"
    alpha_dir.mkdir()
    beta_dir.mkdir()
    nested_dir.mkdir()
    nested_deep_dir.mkdir()

    alpha_file = root / "alpha.txt"
    beta_file = root / "beta.csv"
    nested_file = nested_dir / "gamma.txt"
    nested_deep_file = nested_deep_dir / "omega.log"
    alpha_file.write_text("alpha", encoding="utf-8")
    beta_file.write_text("beta", encoding="utf-8")
    nested_file.write_text("gamma", encoding="utf-8")
    nested_deep_file.write_text("omega", encoding="utf-8")

    assert runtime._execute_builtin_call("walkdir", [str(root)], context) == [
        str(alpha_dir),
        str(beta_dir),
        str(nested_dir),
        str(nested_deep_dir),
    ]
    assert runtime._execute_builtin_call("walkdir", [str(root), "d*"], context) == [
        str(nested_deep_dir),
    ]
    assert runtime._execute_builtin_call("walkdir", [str(root), "z*"], context) == []

    assert runtime._execute_builtin_call("enumeratefiles", [str(root)], context) == [
        str(alpha_file),
        str(beta_file),
        str(nested_deep_file),
        str(nested_file),
    ]
    assert runtime._execute_builtin_call("enumeratefiles", [str(root), "*.txt"], context) == [
        str(alpha_file),
        str(nested_file),
    ]
    assert runtime._execute_builtin_call("enumeratefiles", [str(root), "*.md"], context) == []

    with pytest.raises(RuntimeError, match="WalkDir directory not found"):
        runtime._execute_builtin_call("walkdir", [str(tmp_path / "missing")], context)

    with pytest.raises(RuntimeError, match="EnumerateFiles path exists and is not a directory"):
        runtime._execute_builtin_call("enumeratefiles", [str(alpha_file)], context)


def test_commit_seven_directory_removal_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    child_dir = nested_dir / "child"
    child_dir.mkdir()
    payload_file = child_dir / "payload.txt"
    payload_file.write_text("payload", encoding="utf-8")

    file_target = tmp_path / "plain.txt"
    file_target.write_text("plain", encoding="utf-8")

    alias_dir = tmp_path / "alias"
    alias_dir.mkdir()

    assert runtime._execute_builtin_call("removedir", [str(empty_dir)], context) is None
    assert not empty_dir.exists()

    with pytest.raises(RuntimeError, match="RemoveDir directory is not empty"):
        runtime._execute_builtin_call("removedir", [str(nested_dir)], context)

    assert runtime._execute_builtin_call("directorydelete", [str(nested_dir), 1], context) is None
    assert not nested_dir.exists()

    assert runtime._execute_builtin_call("directorydelete", [str(alias_dir), 0], context) is None
    assert not alias_dir.exists()

    with pytest.raises(RuntimeError, match="RemoveDir directory not found"):
        runtime._execute_builtin_call("removedir", [str(tmp_path / "missing")], context)

    with pytest.raises(RuntimeError, match="RemoveDir path exists and is not a directory"):
        runtime._execute_builtin_call("removedir", [str(file_target)], context)


def test_commit_eight_copy_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    source_file = tmp_path / "source.txt"
    source_file.write_text("alpha", encoding="utf-8")

    file_copy = tmp_path / "copy.txt"
    overwrite_copy = tmp_path / "overwrite.txt"
    overwrite_copy.write_text("old", encoding="utf-8")

    assert runtime._execute_builtin_call("copyfile", [str(source_file), str(file_copy)], context) is None
    assert file_copy.read_text(encoding="utf-8") == "alpha"

    with pytest.raises(RuntimeError, match="CopyFile path already exists"):
        runtime._execute_builtin_call("copyfile", [str(source_file), str(file_copy)], context)

    assert runtime._execute_builtin_call("copyfile", [str(source_file), str(overwrite_copy), 1], context) is None
    assert overwrite_copy.read_text(encoding="utf-8") == "alpha"

    with pytest.raises(RuntimeError, match="CopyFile file not found"):
        runtime._execute_builtin_call("copyfile", [str(tmp_path / "missing.txt"), str(tmp_path / "missing_copy.txt")], context)

    with pytest.raises(RuntimeError, match="CopyFile path is a directory"):
        runtime._execute_builtin_call("copyfile", [str(tmp_path), str(tmp_path / "dir_copy.txt")], context)

    source_dir = tmp_path / "source_dir"
    source_dir.mkdir()
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "payload.txt").write_text("payload", encoding="utf-8")

    dir_copy = tmp_path / "copied_dir"
    existing_dir_copy = tmp_path / "existing_dir_copy"
    existing_dir_copy.mkdir()
    (existing_dir_copy / "old.txt").write_text("old", encoding="utf-8")

    assert runtime._execute_builtin_call("copydir", [str(source_dir), str(dir_copy)], context) is None
    assert (dir_copy / "nested" / "payload.txt").read_text(encoding="utf-8") == "payload"

    with pytest.raises(RuntimeError, match="CopyDir path already exists"):
        runtime._execute_builtin_call("copydir", [str(source_dir), str(dir_copy)], context)

    assert runtime._execute_builtin_call("copydir", [str(source_dir), str(existing_dir_copy), 1], context) is None
    assert not (existing_dir_copy / "old.txt").exists()
    assert (existing_dir_copy / "nested" / "payload.txt").read_text(encoding="utf-8") == "payload"

    with pytest.raises(RuntimeError, match="CopyDir directory not found"):
        runtime._execute_builtin_call("copydir", [str(tmp_path / "missing_dir"), str(tmp_path / "missing_dest")], context)

    with pytest.raises(RuntimeError, match="CopyDir path exists and is not a directory"):
        runtime._execute_builtin_call("copydir", [str(source_file), str(tmp_path / "bad_dir_copy")], context)


def test_commit_nine_move_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    source_file = tmp_path / "move_source.txt"
    source_file.write_text("alpha", encoding="utf-8")

    file_target = tmp_path / "moved.txt"
    file_target.write_text("old", encoding="utf-8")

    assert runtime._execute_builtin_call("movefile", [str(source_file), str(file_target), 1], context) is None
    assert not source_file.exists()
    assert file_target.read_text(encoding="utf-8") == "alpha"

    with pytest.raises(RuntimeError, match="MoveFile file not found"):
        runtime._execute_builtin_call("movefile", [str(source_file), str(tmp_path / "missing.txt")], context)

    source_dir = tmp_path / "move_source_dir"
    source_dir.mkdir()
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "payload.txt").write_text("payload", encoding="utf-8")

    dir_target = tmp_path / "moved_dir"
    dir_target.mkdir()
    (dir_target / "old.txt").write_text("old", encoding="utf-8")

    assert runtime._execute_builtin_call("movedir", [str(source_dir), str(dir_target), 1], context) is None
    assert not source_dir.exists()
    assert (dir_target / "nested" / "payload.txt").read_text(encoding="utf-8") == "payload"
    assert not (dir_target / "old.txt").exists()

    with pytest.raises(RuntimeError, match="MoveDir directory not found"):
        runtime._execute_builtin_call("movedir", [str(tmp_path / "missing_dir"), str(tmp_path / "missing_dest")], context)

    with pytest.raises(RuntimeError, match="MoveDir path exists and is not a directory"):
        runtime._execute_builtin_call("movedir", [str(file_target), str(tmp_path / "bad_dir_target")], context)


def test_commit_ten_metadata_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    root = tmp_path / "metadata"
    root.mkdir()
    nested_dir = root / "nested"
    nested_dir.mkdir()
    data_file = root / "payload.txt"
    data_file.write_text("hello world", encoding="utf-8")

    file_size = runtime._execute_builtin_call("filesize", [str(data_file)], context)
    dir_size = runtime._execute_builtin_call("filesize", [str(root)], context)
    file_time = runtime._execute_builtin_call("filetime", [str(data_file)], context)
    created_time = runtime._execute_builtin_call("filetime", [str(data_file), "created"], context)
    info = runtime._execute_builtin_call("fileinfo", [str(data_file)], context)
    dir_info = runtime._execute_builtin_call("fileinfo", [str(root)], context)

    assert file_size == 11
    assert dir_size == 11
    assert isinstance(file_time, float)
    assert isinstance(created_time, float)
    assert file_time == info.ModifiedTime
    assert info.Path == str(data_file)
    assert info.Name == "payload.txt"
    assert info.ParentPath == str(root)
    assert info.Extension == ".txt"
    assert info.IsDirectory is False
    assert info.Size == 11
    assert info.CreatedTime == created_time
    assert dir_info.IsDirectory is True
    assert dir_info.Size == 11

    with pytest.raises(RuntimeError, match="FileSize path not found"):
        runtime._execute_builtin_call("filesize", [str(tmp_path / "missing.txt")], context)

    with pytest.raises(RuntimeError, match="FileTime argument 2 must be one of"):
        runtime._execute_builtin_call("filetime", [str(data_file), "bad"], context)

    with pytest.raises(RuntimeError, match="FileInfo path not found"):
        runtime._execute_builtin_call("fileinfo", [str(tmp_path / "missing.txt")], context)


def test_commit_eleven_hash_and_checksum_builtins(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    data_file = tmp_path / "payload.txt"
    data_file.write_text("hello world", encoding="utf-8")

    expected_sha256 = hashlib.sha256(b"hello world").hexdigest()
    expected_md5 = hashlib.md5(b"hello world").hexdigest()
    expected_crc32 = f"{zlib.crc32(b'hello world') & 0xFFFFFFFF:08x}"
    expected_adler32 = f"{zlib.adler32(b'hello world') & 0xFFFFFFFF:08x}"

    assert runtime._execute_builtin_call("filehash", [str(data_file)], context) == expected_sha256
    assert runtime._execute_builtin_call("filehash", [str(data_file), "md5"], context) == expected_md5
    assert runtime._execute_builtin_call("filechecksum", [str(data_file)], context) == expected_crc32
    assert runtime._execute_builtin_call("filechecksum", [str(data_file), "adler32"], context) == expected_adler32

    with pytest.raises(RuntimeError, match="FileHash file not found"):
        runtime._execute_builtin_call("filehash", [str(tmp_path / "missing.txt")], context)

    with pytest.raises(RuntimeError, match="FileChecksum path is a directory"):
        runtime._execute_builtin_call("filechecksum", [str(tmp_path)], context)

    with pytest.raises(RuntimeError, match="FileHash argument 2 must be one of"):
        runtime._execute_builtin_call("filehash", [str(data_file), "sha3"], context)

    with pytest.raises(RuntimeError, match="FileChecksum argument 2 must be one of"):
        runtime._execute_builtin_call("filechecksum", [str(data_file), "sha1"], context)


def test_commit_twelve_file_compare_builtin(tmp_path) -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    alpha = tmp_path / "alpha.txt"
    beta = tmp_path / "beta.txt"
    gamma = tmp_path / "gamma.txt"
    prefix = tmp_path / "prefix.txt"
    longer = tmp_path / "longer.txt"

    alpha.write_text("same", encoding="utf-8")
    beta.write_text("same", encoding="utf-8")
    gamma.write_text("samf", encoding="utf-8")
    prefix.write_text("abc", encoding="utf-8")
    longer.write_text("abcd", encoding="utf-8")

    assert runtime._execute_builtin_call("filecompare", [str(alpha), str(beta)], context) == 0
    assert runtime._execute_builtin_call("filecompare", [str(alpha), str(gamma)], context) == -1
    assert runtime._execute_builtin_call("filecompare", [str(gamma), str(alpha)], context) == 1
    assert runtime._execute_builtin_call("filecompare", [str(prefix), str(longer)], context) == -1
    assert runtime._execute_builtin_call("filecompare", [str(longer), str(prefix)], context) == 1

    with pytest.raises(RuntimeError, match="FileCompare file not found"):
        runtime._execute_builtin_call("filecompare", [str(tmp_path / "missing.txt"), str(alpha)], context)

    with pytest.raises(RuntimeError, match="FileCompare path is a directory"):
        runtime._execute_builtin_call("filecompare", [str(tmp_path), str(alpha)], context)


def test_commit_thirteen_array_builtins_support_length_push_pop_and_slice() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    values = [1, 2, 3]
    nested_value = ["a"]

    assert runtime._execute_builtin_call("arraylength", [values], context) == 3

    assert runtime._execute_builtin_call("arraypush", [values, 4], context) == 4
    assert values == [1, 2, 3, 4]

    assert runtime._execute_builtin_call("arraypush", [values, nested_value], context) == 5
    assert values == [1, 2, 3, 4, ["a"]]
    nested_value.append("b")
    assert values[4] == ["a"]

    assert runtime._execute_builtin_call("arraypop", [values], context) == ["a"]
    assert context.get_error() == 0
    assert values == [1, 2, 3, 4]

    assert runtime._execute_builtin_call("arrayslice", [values, 1], context) == [2, 3, 4]
    assert runtime._execute_builtin_call("arrayslice", [values, 1, 2], context) == [2, 3]
    assert runtime._execute_builtin_call("arrayslice", [values, 10], context) == []
    assert runtime._execute_builtin_call("arrayslice", [values, -1], context) == []
    assert runtime._execute_builtin_call("arraytostring", [values], context) == "1,2,3,4"
    assert runtime._execute_builtin_call("arraytostring", [values, ";"], context) == "1;2;3;4"
    assert runtime._execute_builtin_call("arraytostring", [[1, None, "c"]], context) == "1,,c"
    assert runtime._execute_builtin_call("arrayjoin", [values], context) == "1,2,3,4"
    assert runtime._execute_builtin_call("arrayjoin", [values, ";"], context) == "1;2;3;4"
    assert runtime._execute_builtin_call("arrayreverse", [values], context) == [4, 3, 2, 1]
    assert values == [1, 2, 3, 4]

    sort_values = [3, 1, 2]
    assert runtime._execute_builtin_call("arraysort", [sort_values], context) == [1, 2, 3]
    assert sort_values == [3, 1, 2]
    assert runtime._execute_builtin_call("arraysort", [sort_values, 1], context) == [3, 2, 1]
    assert runtime._execute_builtin_call("arrayunique", [[1, 2, 1, 3, 2, 4]], context) == [1, 2, 3, 4]
    assert runtime._execute_builtin_call("arrayunique", [["Bravo", "alpha", "BRAVO"], 0], context) == ["Bravo", "alpha"]
    assert runtime._execute_builtin_call("arrayunique", [["Bravo", "alpha", "BRAVO"], 1], context) == ["Bravo", "alpha", "BRAVO"]

    string_sort_values = ["Bravo", "alpha", "charlie"]
    assert runtime._execute_builtin_call("arraysort", [string_sort_values], context) == ["alpha", "Bravo", "charlie"]
    assert runtime._execute_builtin_call("arraysort", [string_sort_values, 0, 1], context) == ["Bravo", "alpha", "charlie"]
    assert runtime._execute_builtin_call("arraysort", [string_sort_values, 1, 1], context) == ["charlie", "alpha", "Bravo"]

    mixed_sort_values = [3, "2", None, 1]
    assert runtime._execute_builtin_call("arraysort", [mixed_sort_values], context) == [1, 3, "2", None]

    slice_source = [1, ["x", "y"], 3]
    sliced = runtime._execute_builtin_call("arrayslice", [slice_source, 1, 1], context)
    assert sliced == [["x", "y"]]
    sliced[0].append("z")
    assert slice_source[1] == ["x", "y"]

    insert_values = [1, 2, 3]
    assert runtime._execute_builtin_call("arrayinsert", [insert_values, 1, 9], context) == 4
    assert insert_values == [1, 9, 2, 3]
    assert runtime._execute_builtin_call("arrayinsert", [insert_values, 4, 10, 11], context) == 6
    assert insert_values == [1, 9, 2, 3, 10, 11]

    assert runtime._execute_builtin_call("arrayremove", [insert_values, 1], context) == 9
    assert insert_values == [1, 2, 3, 10, 11]
    assert runtime._execute_builtin_call("arrayremove", [insert_values, 2, 2], context) == [3, 10]
    assert insert_values == [1, 2, 11]
    assert runtime._execute_builtin_call("arrayremove", [insert_values, 1, 0], context) == []
    assert insert_values == [1, 2, 11]

    search_values = [1, "two", 3, "two", 1]
    assert runtime._execute_builtin_call("arraycontains", [search_values, 3], context) == 1
    assert runtime._execute_builtin_call("arraycontains", [search_values, "missing"], context) == 0
    assert runtime._execute_builtin_call("arraycontainsall", [search_values, 1, "two"], context) == 1
    assert runtime._execute_builtin_call("arraycontainsall", [search_values, 1, "two", 3], context) == 1
    assert runtime._execute_builtin_call("arraycontainsall", [search_values, 1, "missing"], context) == 0
    assert runtime._execute_builtin_call("arraycontainsall", [search_values, 1, 1], context) == 1
    count_values = [1, 2, 3, 2, 1]
    assert runtime._execute_builtin_call("arraycount", [count_values, 1], context) == 2
    assert runtime._execute_builtin_call("arraycount", [count_values, 2], context) == 2
    assert runtime._execute_builtin_call("arraycount", [count_values, "missing"], context) == 0
    initialize_values = [1, 2, 3]
    assert runtime._execute_builtin_call("arrayinitialize", [initialize_values, 0], context) == 3
    assert initialize_values == [0, 0, 0]
    assert runtime._execute_builtin_call("arrayinitialize", [initialize_values, ""], context) == 3
    assert initialize_values == ["", "", ""]
    assert runtime._execute_builtin_call("arrayclear", [initialize_values], context) == 3
    assert initialize_values == ["", "", ""]
    clone_source = [1, ["nested"], 3]
    clone_values = runtime._execute_builtin_call("arrayclone", [clone_source], context)
    assert clone_values == [1, ["nested"], 3]
    clone_values[1].append("value")
    assert clone_source == [1, ["nested"], 3]
    empty_initialize_values: list[object] = []
    assert runtime._execute_builtin_call("arrayinitialize", [empty_initialize_values, "x"], context) == 0
    assert empty_initialize_values == []
    remove_all_values = [1, 2, 3, 2, 1]
    assert runtime._execute_builtin_call("arrayremoveall", [remove_all_values, 2], context) == 2
    assert remove_all_values == [1, 3, 1]
    assert runtime._execute_builtin_call("arrayremoveall", [remove_all_values, 1], context) == 2
    assert remove_all_values == [3]
    assert runtime._execute_builtin_call("arrayremoveall", [remove_all_values, "missing"], context) == 0
    assert remove_all_values == [3]
    assert runtime._execute_builtin_call("arrayindexof", [search_values, 1], context) == 0
    assert runtime._execute_builtin_call("arrayindexof", [search_values, "two"], context) == 1
    assert runtime._execute_builtin_call("arrayindexof", [search_values, "missing"], context) == -1
    assert runtime._execute_builtin_call("arraylastindexof", [search_values, 1], context) == 4
    assert runtime._execute_builtin_call("arraylastindexof", [search_values, "two"], context) == 3
    assert runtime._execute_builtin_call("arraylastindexof", [search_values, "missing"], context) == -1

    empty_values: list[object] = []
    assert runtime._execute_builtin_call("arraypop", [empty_values], context) is None
    assert context.get_error() == 1

    with pytest.raises(RuntimeError, match="ArrayLength argument 1 must be an array"):
        runtime._execute_builtin_call("arraylength", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayInsert argument 1 must be an array"):
        runtime._execute_builtin_call("arrayinsert", ["not-an-array", 0, 1], context)

    with pytest.raises(RuntimeError, match="ArrayPush expects at least 2 argument"):
        runtime._execute_builtin_call("arraypush", [values], context)

    with pytest.raises(RuntimeError, match="ArrayPop argument 1 must be an array"):
        runtime._execute_builtin_call("arraypop", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayRemove argument 3 must be >= 0"):
        runtime._execute_builtin_call("arrayremove", [values, 0, -1], context)

    with pytest.raises(RuntimeError, match="ArrayContains argument 1 must be an array"):
        runtime._execute_builtin_call("arraycontains", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayContainsAll argument 1 must be an array"):
        runtime._execute_builtin_call("arraycontainsall", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayContainsAll expects at least 2 argument"):
        runtime._execute_builtin_call("arraycontainsall", [search_values], context)

    with pytest.raises(RuntimeError, match="ArrayCount argument 1 must be an array"):
        runtime._execute_builtin_call("arraycount", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayInitialize argument 1 must be an array"):
        runtime._execute_builtin_call("arrayinitialize", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayInitialize argument 2 must be a string or number"):
        runtime._execute_builtin_call("arrayinitialize", [[1, 2], []], context)

    with pytest.raises(RuntimeError, match="ArrayClear argument 1 must be an array"):
        runtime._execute_builtin_call("arrayclear", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayClone argument 1 must be an array"):
        runtime._execute_builtin_call("arrayclone", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayRemoveAll argument 1 must be an array"):
        runtime._execute_builtin_call("arrayremoveall", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayRemoveAll expects 2 argument"):
        runtime._execute_builtin_call("arrayremoveall", [search_values], context)

    with pytest.raises(RuntimeError, match="ArrayIndexOf argument 1 must be an array"):
        runtime._execute_builtin_call("arrayindexof", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayLastIndexOf argument 1 must be an array"):
        runtime._execute_builtin_call("arraylastindexof", ["not-an-array", 1], context)

    with pytest.raises(RuntimeError, match="ArrayToString argument 1 must be an array"):
        runtime._execute_builtin_call("arraytostring", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayJoin argument 1 must be an array"):
        runtime._execute_builtin_call("arrayjoin", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArraySort argument 1 must be an array"):
        runtime._execute_builtin_call("arraysort", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArraySort argument 2 must be one of: 0, 1"):
        runtime._execute_builtin_call("arraysort", [[1, 2], 2], context)

    with pytest.raises(RuntimeError, match="ArraySort argument 3 must be one of: 0, 1"):
        runtime._execute_builtin_call("arraysort", [[1, 2], 0, 2], context)

    with pytest.raises(RuntimeError, match="ArrayReverse argument 1 must be an array"):
        runtime._execute_builtin_call("arrayreverse", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayUnique argument 1 must be an array"):
        runtime._execute_builtin_call("arrayunique", ["not-an-array"], context)

    with pytest.raises(RuntimeError, match="ArrayUnique argument 2 must be one of: 0, 1"):
        runtime._execute_builtin_call("arrayunique", [[1, 2], 2], context)


def test_string_compare_builtin_supports_case_sensitive_and_insensitive_modes() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringcompare", ["alpha", "alpha"], context) == 0
    assert runtime._execute_builtin_call("stringcompare", ["Alpha", "alpha"], context) == 0
    assert runtime._execute_builtin_call("stringcompare", ["bravo", "alpha"], context) > 0
    assert runtime._execute_builtin_call("stringcompare", ["alpha", "bravo"], context) < 0
    assert runtime._execute_builtin_call("stringcompare", ["Hello", "hello", 1], context) < 0
    assert runtime._execute_builtin_call("stringcompare", ["Hello", "world", 1], context) < 0

    with pytest.raises(RuntimeError, match="StringCompare argument 3 must be one of"):
        runtime._execute_builtin_call("stringcompare", ["alpha", "beta", 2], context)


def test_asc_and_chr_builtins_support_unicode_round_trip_and_validation() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("asc", ["A"], context) == ord("A")
    assert runtime._execute_builtin_call("ascw", ["🙂"], context) == ord("🙂")
    assert runtime._execute_builtin_call("chr", [ord("A")], context) == "A"
    assert runtime._execute_builtin_call("chrw", [ord("🙂")], context) == "🙂"

    with pytest.raises(RuntimeError, match="Asc argument 1 must not be empty"):
        runtime._execute_builtin_call("asc", [""], context)

    with pytest.raises(RuntimeError, match="ChrW argument 1 must be a Unicode code point between 0 and 1114111"):
        runtime._execute_builtin_call("chrw", [0x110000], context)


def test_string_case_conversion_builtins_lower_and_upper() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringtolower", ["MiXeD Case"], context) == "mixed case"
    assert runtime._execute_builtin_call("stringtoupper", ["MiXeD Case"], context) == "MIXED CASE"

    with pytest.raises(RuntimeError, match="StringToLower argument 1 must be a string"):
        runtime._execute_builtin_call("stringtolower", [123], context)

    with pytest.raises(RuntimeError, match="StringToUpper argument 1 must be a string"):
        runtime._execute_builtin_call("stringtoupper", [123], context)


def test_string_is_alpha_builtin_checks_for_letters_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisalpha", ["Alpha"], context) == 1
    assert runtime._execute_builtin_call("stringisalpha", ["Café"], context) == 1
    assert runtime._execute_builtin_call("stringisalpha", ["Alpha 1"], context) == 0
    assert runtime._execute_builtin_call("stringisalpha", ["Alpha\tBeta"], context) == 0
    assert runtime._execute_builtin_call("stringisalpha", [""], context) == 0

    with pytest.raises(RuntimeError, match="StringIsAlpha argument 1 must be a string"):
        runtime._execute_builtin_call("stringisalpha", [123], context)


def test_string_is_alphanumeric_builtin_checks_for_letters_and_digits_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisalphanumeric", ["Alpha123"], context) == 1
    assert runtime._execute_builtin_call("stringisalphanumeric", ["Café42"], context) == 1
    assert runtime._execute_builtin_call("stringisalphanumeric", ["Alpha 123"], context) == 0
    assert runtime._execute_builtin_call("stringisalphanumeric", ["Alpha-123"], context) == 0
    assert runtime._execute_builtin_call("stringisalphanumeric", [""], context) == 0

    with pytest.raises(RuntimeError, match="StringIsAlphaNumeric argument 1 must be a string"):
        runtime._execute_builtin_call("stringisalphanumeric", [123], context)


def test_string_is_ascii_builtin_checks_for_7_bit_ascii_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisascii", ["Alpha123"], context) == 1
    assert runtime._execute_builtin_call("stringisascii", ["!~\x00\x7f"], context) == 1
    assert runtime._execute_builtin_call("stringisascii", ["Alpha Café"], context) == 0
    assert runtime._execute_builtin_call("stringisascii", ["🙂"], context) == 0
    assert runtime._execute_builtin_call("stringisascii", [""], context) == 1

    with pytest.raises(RuntimeError, match="StringIsASCII argument 1 must be a string"):
        runtime._execute_builtin_call("stringisascii", [123], context)


def test_string_is_digit_builtin_checks_for_digits_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisdigit", ["123456"], context) == 1
    assert runtime._execute_builtin_call("stringisdigit", ["0123456789"], context) == 1
    assert runtime._execute_builtin_call("stringisdigit", ["12 34"], context) == 0
    assert runtime._execute_builtin_call("stringisdigit", ["12-34"], context) == 0
    assert runtime._execute_builtin_call("stringisdigit", [""], context) == 0

    with pytest.raises(RuntimeError, match="StringIsDigit argument 1 must be a string"):
        runtime._execute_builtin_call("stringisdigit", [123], context)


def test_string_is_float_builtin_checks_for_float_format_and_coerces_non_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisfloat", ["1.0"], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", ["+1.0"], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", ["-.5"], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", ["5."], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", [".5"], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", ["1"], context) == 0
    assert runtime._execute_builtin_call("stringisfloat", ["1.2.3"], context) == 0
    assert runtime._execute_builtin_call("stringisfloat", ["1,5"], context) == 0
    assert runtime._execute_builtin_call("stringisfloat", [1.25], context) == 1
    assert runtime._execute_builtin_call("stringisfloat", [1], context) == 0
    assert runtime._execute_builtin_call("stringisfloat", [True], context) == 0


def test_string_is_int_builtin_checks_for_integer_format_and_integer_expressions() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisint", ["0"], context) == 1
    assert runtime._execute_builtin_call("stringisint", ["+42"], context) == 1
    assert runtime._execute_builtin_call("stringisint", ["-42"], context) == 1
    assert runtime._execute_builtin_call("stringisint", ["42"], context) == 1
    assert runtime._execute_builtin_call("stringisint", ["42.0"], context) == 0
    assert runtime._execute_builtin_call("stringisint", ["42,0"], context) == 0
    assert runtime._execute_builtin_call("stringisint", [" 42"], context) == 0
    assert runtime._execute_builtin_call("stringisint", ["42 "], context) == 0
    assert runtime._execute_builtin_call("stringisint", ["+"], context) == 0
    assert runtime._execute_builtin_call("stringisint", [42], context) == 1
    assert runtime._execute_builtin_call("stringisint", [-42], context) == 1
    assert runtime._execute_builtin_call("stringisint", [42.0], context) == 0
    assert runtime._execute_builtin_call("stringisint", [True], context) == 0


def test_string_is_lower_builtin_checks_for_lowercase_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringislower", ["abc"], context) == 1
    assert runtime._execute_builtin_call("stringislower", ["abcé"], context) == 1
    assert runtime._execute_builtin_call("stringislower", ["abc123"], context) == 0
    assert runtime._execute_builtin_call("stringislower", ["abc!"], context) == 0
    assert runtime._execute_builtin_call("stringislower", ["abc def"], context) == 0
    assert runtime._execute_builtin_call("stringislower", [""], context) == 0

    with pytest.raises(RuntimeError, match="StringIsLower argument 1 must be a string"):
        runtime._execute_builtin_call("stringislower", [123], context)


def test_string_is_space_builtin_checks_for_whitespace_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisspace", [" "], context) == 1
    assert runtime._execute_builtin_call("stringisspace", ["\t"], context) == 1
    assert runtime._execute_builtin_call("stringisspace", ["\r\n"], context) == 1
    assert runtime._execute_builtin_call("stringisspace", ["\x00"], context) == 1
    assert runtime._execute_builtin_call("stringisspace", [" \t\r\n\x00"], context) == 1
    assert runtime._execute_builtin_call("stringisspace", [""], context) == 1
    assert runtime._execute_builtin_call("stringisspace", ["abc"], context) == 0
    assert runtime._execute_builtin_call("stringisspace", ["abc "], context) == 0
    assert runtime._execute_builtin_call("stringisspace", ["123"], context) == 0

    with pytest.raises(RuntimeError, match="StringIsSpace argument 1 must be a string"):
        runtime._execute_builtin_call("stringisspace", [123], context)


def test_string_is_upper_builtin_checks_for_uppercase_only_strings() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringisupper", ["ABC"], context) == 1
    assert runtime._execute_builtin_call("stringisupper", ["ABÉ"], context) == 1
    assert runtime._execute_builtin_call("stringisupper", ["ABC123"], context) == 0
    assert runtime._execute_builtin_call("stringisupper", ["ABC!"], context) == 0
    assert runtime._execute_builtin_call("stringisupper", ["ABC def"], context) == 0
    assert runtime._execute_builtin_call("stringisupper", [""], context) == 0

    with pytest.raises(RuntimeError, match="StringIsUpper argument 1 must be a string"):
        runtime._execute_builtin_call("stringisupper", [123], context)


def test_string_replace_builtin_supports_search_and_start_modes() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringreplace", ["aaa", "aa", "bb"], context) == "bba"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0

    assert runtime._execute_builtin_call("stringreplace", ["Hello World", "world", "there"], context) == "Hello there"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0

    assert runtime._execute_builtin_call("stringreplace", ["one two one two", "one", "1", 0, 0], context) == "1 two 1 two"
    assert context.get_special_value("Extended") == 2
    assert context.get_error() == 0

    assert runtime._execute_builtin_call("stringreplace", ["one two one two", "one", "1", -1], context) == "one two 1 two"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0

    assert runtime._execute_builtin_call("stringreplace", ["abcdef", 3, "XY"], context) == "abXYef"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0

    context.set_error(0)
    assert runtime._execute_builtin_call("stringreplace", ["abc", 3, "XYZ"], context) == ""
    assert context.get_error() == 1
    assert context.get_special_value("Extended") == 0

    with pytest.raises(RuntimeError, match="StringReplace argument 5 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringreplace", ["abc", "a", "b", 1, 2], context)


def test_string_slicing_builtins_length_left_right_mid() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringlength", ["Hello"], context) == 5
    assert runtime._execute_builtin_call("stringleft", ["Hello", 2], context) == "He"
    assert runtime._execute_builtin_call("stringleft", ["Hello", 99], context) == "Hello"
    assert runtime._execute_builtin_call("stringleft", ["Hello", -1], context) == ""

    assert runtime._execute_builtin_call("stringright", ["Hello", 2], context) == "lo"
    assert runtime._execute_builtin_call("stringright", ["Hello", 99], context) == "Hello"
    assert runtime._execute_builtin_call("stringright", ["Hello", 0], context) == ""
    assert runtime._execute_builtin_call("stringright", ["Hello", -1], context) == ""

    assert runtime._execute_builtin_call("stringmid", ["Hello", 2], context) == "ello"
    assert runtime._execute_builtin_call("stringmid", ["Hello", 2, 2], context) == "el"
    assert runtime._execute_builtin_call("stringmid", ["Hello", 2, 99], context) == "ello"
    assert runtime._execute_builtin_call("stringmid", ["Hello", 2, -1], context) == "ello"
    assert runtime._execute_builtin_call("stringmid", ["Hello", 0], context) == ""
    assert runtime._execute_builtin_call("stringmid", ["Hello", 10], context) == ""
    assert runtime._execute_builtin_call("stringmid", ["Hello", 2, 0], context) == ""

    assert runtime._execute_builtin_call("stringtrimleft", ["Hello", 2], context) == "llo"
    assert runtime._execute_builtin_call("stringtrimleft", ["Hello", 0], context) == "Hello"
    assert runtime._execute_builtin_call("stringtrimleft", ["Hello", 5], context) == ""
    assert runtime._execute_builtin_call("stringtrimleft", ["Hello", 99], context) == ""
    assert runtime._execute_builtin_call("stringtrimleft", ["Hello", -1], context) == ""

    assert runtime._execute_builtin_call("stringtrimright", ["Hello", 2], context) == "Hel"
    assert runtime._execute_builtin_call("stringtrimright", ["Hello", 0], context) == "Hello"
    assert runtime._execute_builtin_call("stringtrimright", ["Hello", 5], context) == ""
    assert runtime._execute_builtin_call("stringtrimright", ["Hello", 99], context) == ""
    assert runtime._execute_builtin_call("stringtrimright", ["Hello", -1], context) == ""

    with pytest.raises(RuntimeError, match="StringLength argument 1 must be a string"):
        runtime._execute_builtin_call("stringlength", [123], context)

    with pytest.raises(RuntimeError, match="StringLeft argument 2 must be an integer"):
        runtime._execute_builtin_call("stringleft", ["Hello", "2"], context)

    with pytest.raises(RuntimeError, match="StringMid argument 2 must be an integer"):
        runtime._execute_builtin_call("stringmid", ["Hello", "2"], context)

    with pytest.raises(RuntimeError, match="StringTrimLeft argument 2 must be an integer"):
        runtime._execute_builtin_call("stringtrimleft", ["Hello", "2"], context)

    with pytest.raises(RuntimeError, match="StringTrimRight argument 2 must be an integer"):
        runtime._execute_builtin_call("stringtrimright", ["Hello", "2"], context)


def test_string_reverse_builtin_reverses_text_and_validates_input() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringreverse", ["Hello"], context) == "olleH"
    assert runtime._execute_builtin_call("stringreverse", ["A🙂B"], context) == "B🙂A"

    with pytest.raises(RuntimeError, match="StringReverse argument 1 must be a string"):
        runtime._execute_builtin_call("stringreverse", [123], context)


def test_string_family_helpers_cover_prefix_suffix_contains_split_and_join() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("stringstartswith", ["ActionShellScript", "Action"], context) == 1
    assert runtime._execute_builtin_call("stringstartswith", ["ActionShellScript", "action"], context) == 1
    assert runtime._execute_builtin_call("stringstartswith", ["ActionShellScript", "action", 1], context) == 0
    assert runtime._execute_builtin_call("stringendswith", ["report.csv", ".csv"], context) == 1
    assert runtime._execute_builtin_call("stringendswith", ["report.csv", ".CSV", 1], context) == 0
    assert runtime._execute_builtin_call("stringcontains", ["Hello World", "world"], context) == 1
    assert runtime._execute_builtin_call("stringcontains", ["Hello World", "world", 1], context) == 0

    assert runtime._execute_builtin_call("stringsplit", ["a,b,c", ","], context) == ["a", "b", "c"]
    assert runtime._execute_builtin_call("stringsplit", ["a,b,c", ",", 1], context) == ["a", "b,c"]
    assert runtime._execute_builtin_call("stringsplit", ["a,b,c", ",", 0, 1], context) == ["a", "b", "c"]
    assert runtime._execute_builtin_call("stringsplit", ["aXaXb", "x", 0, 0], context) == ["a", "a", "b"]
    assert runtime._execute_builtin_call("stringsplit", ["abc", ","], context) == ["abc"]
    assert runtime._execute_builtin_call("stringsplit", ["abc", ""], context) == ["abc"]
    assert runtime._execute_builtin_call("stringsplit", ["", ","], context) == [""]

    assert runtime._execute_builtin_call("stringjoin", [["a", "b", "c"], ","], context) == "a,b,c"
    assert runtime._execute_builtin_call("stringjoin", [["a", "b", "c"]], context) == "abc"
    assert runtime._execute_builtin_call("stringjoin", [[], ","], context) == ""
    assert runtime._execute_builtin_call("stringjoin", [[1, None, "c"], "-"], context) == "1--c"

    with pytest.raises(RuntimeError, match="StringStartsWith argument 3 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringstartswith", ["ActionShellScript", "Action", 2], context)
    with pytest.raises(RuntimeError, match="StringEndsWith argument 3 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringendswith", ["report.csv", ".csv", 2], context)
    with pytest.raises(RuntimeError, match="StringContains argument 3 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringcontains", ["Hello", "he", 2], context)
    with pytest.raises(RuntimeError, match="StringSplit argument 3 must be >= 0"):
        runtime._execute_builtin_call("stringsplit", ["a,b,c", ",", -1], context)
    with pytest.raises(RuntimeError, match="StringSplit argument 4 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringsplit", ["a,b,c", ",", 0, 2], context)
    with pytest.raises(RuntimeError, match="StringJoin argument 1 must be an array"):
        runtime._execute_builtin_call("stringjoin", ["abc", ","], context)


def test_regex_builtins_support_matching_captures_and_backreferences() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("regexismatch", ["abc123", r"\d+"], context) == 1
    assert runtime._execute_builtin_call("regexismatch", ["abc", r"\d+"], context) == 0
    assert runtime._execute_builtin_call("regexismatch", ["ABC", "abc", "i"], context) == 1

    assert runtime._execute_builtin_call("regexinstr", ["abc123def", r"\d+"], context) == 4
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("regexinstr", ["abc123def", r"\d+", 5], context) == 5
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("regexinstr", ["abc", r"\d+"], context) == 0
    assert context.get_error() == 1

    assert runtime._execute_builtin_call(
        "regexmatch",
        ["abc123def", r"([a-z]+)(\d+)([a-z]+)"],
        context,
    ) == ["abc123def", "abc", "123", "def"]
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("regexmatch", ["ac", r"(a)(z)?(c)"], context) == [
        "ac",
        "a",
        None,
        "c",
    ]
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("regexmatch", ["abc", r"\d+"], context) is None
    assert context.get_error() == 1

    assert runtime._execute_builtin_call(
        "regexreplace",
        ["Ada Lovelace", r"(\w+)\s+(\w+)", "$2, $1"],
        context,
    ) == "Lovelace, Ada"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "regexreplace",
        ["a1b2c3", r"(\d)", "[$1]"],
        context,
    ) == "a[1]b[2]c[3]"
    assert context.get_special_value("Extended") == 3
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "regexreplace",
        ["a1b2c3", r"(\d)", "[$1]", 2],
        context,
    ) == "a[1]b[2]c3"
    assert context.get_special_value("Extended") == 2
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "regexreplace",
        ["abc", r"(a)(b)(c)", "$0-$3-$2-$1"],
        context,
    ) == "abc-c-b-a"
    assert context.get_special_value("Extended") == 1
    assert context.get_error() == 0

    assert runtime._execute_builtin_call("regexescape", ["a.b"], context) == r"a\.b"
    assert runtime._execute_builtin_call("regexescape", ["x+y*"], context) == r"x\+y\*"


def test_regex_builtins_reject_invalid_patterns_and_options() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    with pytest.raises(RuntimeError, match="RegexIsMatch invalid regular expression:"):
        runtime._execute_builtin_call("regexismatch", ["abc", "("], context)

    with pytest.raises(RuntimeError, match="RegexMatch invalid regex option: z"):
        runtime._execute_builtin_call("regexmatch", ["abc", "abc", "z"], context)

    with pytest.raises(RuntimeError, match="RegexReplace invalid regular expression:"):
        runtime._execute_builtin_call("regexreplace", ["abc", "(a)", "$2"], context)

    with pytest.raises(RuntimeError, match="RegexReplace invalid regex option: z"):
        runtime._execute_builtin_call("regexreplace", ["abc", "abc", "x", 0, "z"], context)


def test_string_in_str_builtin_supports_occurrence_start_and_count_limits() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime.evaluate_debug_expression("@CR", context) == "\r"
    assert runtime.evaluate_debug_expression("@LF", context) == "\n"
    assert runtime.evaluate_debug_expression("@CRLF", context) == "\r\n"
    assert runtime.evaluate_debug_expression("@TAB", context) == "\t"

    assert runtime._execute_builtin_call("stringinstr", ["Hello World", "world"], context) == 7
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("stringinstr", ["Hello World", "world", 1], context) == 0
    assert context.get_error() == 0
    with pytest.raises(RuntimeError, match="StringInStr argument 3 must be one of: 0, 1"):
        runtime._execute_builtin_call("stringinstr", ["Hello World", "world", 2], context)
    assert runtime._execute_builtin_call("stringinstr", ["Test with Ü", "Ü", 1], context) == 11
    assert context.get_error() == 0
    assert runtime._execute_builtin_call("stringinstr", ["Hello World", "world", 0, 0], context) == 0
    assert context.get_error() == 1
    assert runtime._execute_builtin_call("stringinstr", ["Hello World", "world", 0, 1, 99], context) == 0
    assert context.get_error() == 1
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["one two one two", "one", 0, 2],
        context,
    ) == 9
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["one two one two one", "one", 0, -1],
        context,
    ) == 17
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["the string to search", "string", 0, 1, 1, 11],
        context,
    ) == 5
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["the string to search", "string", 0, 1, 6],
        context,
    ) == 0
    assert context.get_error() == 0
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["the string to search", "string", 0, 1, 1, 5],
        context,
    ) == 0
    assert context.get_error() == 1
    assert runtime._execute_builtin_call(
        "stringinstr",
        ["the string to search", "string", 0, 1, 1, -1],
        context,
    ) == 0
    assert context.get_error() == 1


def test_remaining_bitwise_helpers_match_expected_old_runtime_behavior() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()

    assert runtime._execute_builtin_call("bitnotunsigned", [0], context) == 0xFFFFFFFF
    assert runtime._execute_builtin_call("bitnotunsigned", [0x12345678], context) == 0xEDCBA987

    assert runtime._execute_builtin_call("bitrotate", [0x0001], context) == 0x0002
    assert runtime._execute_builtin_call("bitrotate", [0x8000, 1, "W"], context) == 0x0001
    assert runtime._execute_builtin_call("bitrotate", [0x12, 4, "B"], context) == 0x21

    context.set_error(0)
    assert runtime._execute_builtin_call("bitrotate", [1, 1, "invalid"], context) == 0
    assert context.get_error() == 1
    assert runtime.evaluate_debug_expression("@Error", context) == 1
