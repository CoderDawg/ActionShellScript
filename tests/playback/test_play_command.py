from __future__ import annotations

import builtins
import ctypes
import json
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest

from apps.cli.play_command import _load_script_document, build_parser, run
from application.playback_service import PlaybackService
from core.playback.playback_builder import PlaybackBuilder
from core.playback.playback_result import PlaybackResult
from infrastructure.debug_logger import reset_diagnostic_config


@pytest.mark.parametrize(
    ("argv", "source_kind", "source_path"),
    [
        (["recording", "session.json", "--mode", "preview", "--repeat", "2", "--step", "--delay-ms", "75", "--show-events", "--recording-conversion-mode", "direct_import", "--ass-play"], "recording", "session.json"),
        (["script", "playback.ass", "--mode", "live", "--demo-live", "--show-events"], "script", "playback.ass"),
    ],
)
def test_play_command_parser_accepts_phase_6_flags_after_source_selection(
    argv: list[str],
    source_kind: str,
    source_path: str,
) -> None:
    args = build_parser().parse_args(
        argv
    )

    assert args.source_kind == source_kind
    assert args.source_path == source_path

    if source_kind == "recording":
        assert args.mode == "preview"
        assert args.repeat == 2
        assert args.step is True
        assert args.delay_ms == 75
        assert args.settle_ms == 0
        assert args.show_events is True
        assert args.demo_live is False
        assert args.ass_play is True
        assert args.recording_conversion_mode == "direct_import"
    else:
        assert args.mode == "live"
        assert args.repeat == 1
        assert args.step is False
        assert args.delay_ms == 0
        assert args.settle_ms == 0
        assert args.show_events is True
        assert args.demo_live is True


def test_play_command_recording_parser_defaults_to_session_json() -> None:
    args = build_parser().parse_args(["recording"])

    assert args.source_kind == "recording"
    assert args.source_path == r".\session.json"


def test_play_command_help_uses_ass_cli_play_prog(capsys) -> None:
    parser = build_parser()

    assert parser.prog == "ass-cli play"

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    captured = capsys.readouterr()

    assert "usage: ass-cli play" in captured.out
    assert "usage: ass-play" not in captured.out


def test_play_command_loader_preserves_source_path(tmp_path: Path) -> None:
    script_path = tmp_path / "playback.ass"
    script_path.write_text("WriteLn(\"hello\")\n", encoding="utf-8")

    document = _load_script_document(str(script_path))

    assert document.document_id == str(script_path.resolve())
    assert document.text == 'WriteLn("hello")\n'
    assert document.source_path == str(script_path.resolve())


def test_play_command_runs_recording_direct_import_conversion_flow_end_to_end(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-direct-import",
                "state": "stopped",
                "started_at_ms": 100,
                "stopped_at_ms": 180,
                "events": [
                    {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                    {"type": "key_down", "key": "c", "timestamp_ms": 120},
                    {"type": "key_up", "key": "c", "timestamp_ms": 150},
                    {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            "recording",
            str(session_path),
            "--mode",
            "preview",
            "--recording-conversion-mode",
            "direct_import",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recording route        : Converted document path (direct_import)" in captured.out
    assert "Source kind            : script_document" in captured.out
    assert "Playback success       : True" in captured.out


def test_play_command_runs_recording_promote_generated_conversion_flow_end_to_end(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-promote-generated",
                "state": "stopped",
                "events": [
                    {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                    {"type": "key_down", "key": "c", "timestamp_ms": 120},
                    {"type": "key_up", "key": "c", "timestamp_ms": 150},
                    {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            "recording",
            str(session_path),
            "--mode",
            "preview",
            "--recording-conversion-mode",
            "promote_generated",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recording route        : Converted document path (promote_generated)" in captured.out
    assert "Source kind            : script_document" in captured.out
    assert "Playback success       : True" in captured.out


def test_play_command_runs_recording_preview_flow_end_to_end(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-play-cli",
                "state": "stopped",
                "events": [
                    {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                    {"type": "key_down", "key": "c", "timestamp_ms": 120},
                    {"type": "key_up", "key": "c", "timestamp_ms": 150},
                    {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
                ],
            }
        ),
        encoding="utf-8",
    )

    build_calls = 0
    original_build_from_recording = PlaybackBuilder.build_from_recording

    def counting_build_from_recording(self, session):
        nonlocal build_calls
        build_calls += 1
        return original_build_from_recording(self, session)

    monkeypatch.setattr(
        PlaybackBuilder,
        "build_from_recording",
        counting_build_from_recording,
    )

    exit_code = run(
        [
            "recording",
            str(session_path),
            "--mode",
            "preview",
            "--repeat",
            "2",
            "--settle-ms",
            "250",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert build_calls == 1
    assert "Recording route        : Raw recording path" in captured.out
    assert "Source kind            : recording_session" in captured.out
    assert "Playback mode          : preview" in captured.out
    assert "Planned event count    : 1" in captured.out
    assert "Step mode              : False" in captured.out
    assert "Delay per event (ms)   : 0" in captured.out
    assert "Mouse settle (ms)      : 250" in captured.out
    assert "Executed event count   : 2" in captured.out
    assert '"keys": ["ctrl", "c"]' in captured.out


def test_play_command_runs_recording_preview_flow_with_default_session_json(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-play-default",
                "state": "stopped",
                "events": [
                    {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                    {"type": "key_down", "key": "c", "timestamp_ms": 120},
                    {"type": "key_up", "key": "c", "timestamp_ms": 150},
                    {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run(
        [
            "recording",
            "--mode",
            "preview",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recording route        : Raw recording path" in captured.out
    assert "Source kind            : recording_session" in captured.out
    assert "Playback success       : True" in captured.out


def test_play_command_runs_script_preview_flow_end_to_end(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "playback.ass"
    script_path.write_text(
        (
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
            'Write("alpha")\n'
            'WriteLn("beta")\n'
            'DiagWrite("gamma")\n'
            'DiagWriteLn("delta")\n'
        ),
        encoding="utf-8",
    )

    build_calls = 0
    original_build_from_script = PlaybackBuilder.build_from_script

    def counting_build_from_script(self, document):
        nonlocal build_calls
        build_calls += 1
        return original_build_from_script(self, document)

    monkeypatch.setattr(
        PlaybackBuilder,
        "build_from_script",
        counting_build_from_script,
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert build_calls == 1
    assert "Source kind            : script_document" in captured.out
    assert "Playback success       : True" in captured.out
    assert "Playback mode          : preview" in captured.out
    assert "SendKeys transport     : text events" in captured.out
    assert "Planned event count    : 3" in captured.out
    assert "Step mode              : False" in captured.out
    assert "Delay per event (ms)   : 0" in captured.out
    assert "Console output:" in captured.out
    assert "Console output:\nalpha\nbeta" in captured.out
    assert "Diagnostics output:" not in captured.out
    assert "gamma" not in captured.out
    assert "delta" not in captured.out
    assert '"type": "mouse_move"' in captured.out
    assert '"text": "inner"' in captured.out
    assert '"type": "text"' in captured.out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DLL interop only")
def test_play_command_runs_script_preview_flow_for_cursor_pos_struct_smoke(
    capsys,
    monkeypatch,
) -> None:
    script_path = Path("samples/struct_and_dll_cursor_pos_demo.ass")

    calls: list[str] = []

    def fake_get_cursor_pos(point_ptr):
        calls.append("GetCursorPos")
        point = ctypes.cast(point_ptr, ctypes.POINTER(ctypes.c_int32))
        point[0] = 321
        point[1] = 654
        return True

    fake_library = SimpleNamespace(GetCursorPos=fake_get_cursor_pos)
    monkeypatch.setattr(
        "core.runtime.script_runtime.ctypes.WinDLL",
        lambda library_name: fake_library,
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == ["GetCursorPos"]
    assert "Source kind            : script_document" in captured.out
    assert "Playback success       : True" in captured.out
    assert "Console output:" in captured.out
    assert "True" in captured.out
    assert "321" in captured.out
    assert "654" in captured.out


def test_play_command_uses_script_current_event_delay_override_for_scripts(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "delay-override.ass"
    script_path.write_text(
        (
            "SetCurrentEventDelay(125)\n"
            'SendText("done")\n'
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Delay per event (ms)   : 125" in captured.out


def test_play_command_runs_script_preview_flow_with_implicit_function_return(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "factorial.ass"
    script_path.write_text(
        (
            "Func Factorial(n)\n"
            "    If n <= 1 Then\n"
            "        Factorial = 1\n"
            "    Else\n"
            "        Factorial = n * Factorial(n - 1)\n"
            "    EndIf\n"
            "EndFunc\n"
            'WriteLn(Factorial(5))\n'
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback success       : True" in captured.out
    assert "120" in captured.out


def test_play_command_prints_error_line_when_playback_fails(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "failure.ass"
    script_path.write_text('SendText("boom")\n', encoding="utf-8")

    def fake_play_plan(self, plan, request):
        return PlaybackResult(
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            executed_event_count=0,
            success=False,
            error_line=4,
            error_message="boom",
        )

    monkeypatch.setattr(PlaybackService, "play_plan", fake_play_plan)

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Playback error line    : 4" in captured.out
    assert "Playback error         : boom" in captured.out


def test_play_command_runs_script_live_demo_flow_end_to_end(tmp_path, capsys) -> None:
    script_path = tmp_path / "live-demo.ass"
    script_path.write_text(
        'MouseMove(10, 20)\nHotkey("ctrl", "c")\nSendText("demo")\n',
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "live",
            "--demo-live",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback mode          : live" in captured.out
    assert "Playback success       : True" in captured.out
    assert "SendKeys transport     : text events" in captured.out
    assert "Live dispatch 01:" in captured.out
    assert "Dispatched host calls:" in captured.out
    assert '"action": "move_mouse"' in captured.out
    assert '"action": "key_down"' in captured.out
    assert '"action": "send_text"' in captured.out


def test_play_command_runs_script_live_demo_flow_with_sendkeys_key_taps_sample(
    capsys,
) -> None:
    script_path = Path("samples/sendkeys_key_taps_demo.ass")

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "live",
            "--demo-live",
            "--ass-play",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback mode          : live" in captured.out
    assert "Playback success       : True" in captured.out
    assert "SendKeys transport     : key taps" in captured.out
    assert "Dispatched host calls (SendKeys key taps mode):" in captured.out
    assert '"action": "key_down"' in captured.out
    assert '"action": "key_up"' in captured.out
    assert '"action": "send_text"' not in captured.out
    assert '"type": "text"' not in captured.out


def test_play_command_runs_script_preview_flow_with_sendkeys_key_taps_mode(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "sendkeys-taps.ass"
    script_path.write_text(
        'SendKeys("Ab")\n',
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--ass-play",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback events (SendKeys key taps mode):" in captured.out
    assert "Playback mode          : preview" in captured.out
    assert "SendKeys transport     : key taps" in captured.out
    assert '"type": "key_down"' in captured.out
    assert '"type": "key_up"' in captured.out
    assert '"type": "text"' not in captured.out


def test_play_command_runs_recording_live_demo_flow_end_to_end(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session-click.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-live-click",
                "state": "stopped",
                "events": [
                    {"type": "mouse_down", "button": "left", "x": 282, "y": 501, "timestamp_ms": 100},
                    {"type": "mouse_up", "button": "left", "x": 282, "y": 501, "timestamp_ms": 140},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            "recording",
            str(session_path),
            "--mode",
            "live",
            "--demo-live",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback mode          : live" in captured.out
    assert "Live dispatch 01:" in captured.out
    assert "Dispatched host calls:" in captured.out
    assert '"action": "move_mouse"' in captured.out
    assert '"action": "mouse_click"' in captured.out
    assert '"clicks": 1' in captured.out


def test_play_command_runs_script_step_mode_with_prompting(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "step-demo.ass"
    script_path.write_text(
        'MouseMove(10, 20)\nSendText("demo")\n',
        encoding="utf-8",
    )

    prompts: list[str] = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": prompts.append(prompt) or "",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--step",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Step mode              : True" in captured.out
    assert len(prompts) == 2
    assert "Step 1/2" in captured.out
    assert "Step 2/2" in captured.out


def test_play_command_preview_mode_does_not_import_live_adapter(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    script_path = tmp_path / "preview-only.ass"
    script_path.write_text('SendText("preview")\n', encoding="utf-8")

    sys.modules.pop("infrastructure.input.pynput_playback_adapter", None)

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "infrastructure.input.pynput_playback_adapter":
            raise AssertionError("live adapter should not be imported in preview mode")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    exit_code = run(
        [
            "script",
            str(script_path),
            "--mode",
            "preview",
            "--show-events",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Playback mode          : preview" in captured.out


@pytest.mark.parametrize(
    ("diagnostic_path", "expected_override"),
    [
        (None, None),
        ("custom-diagnostics.log", "custom-diagnostics.log"),
    ],
)
def test_play_command_announces_diagnostic_log_path_up_front(
    tmp_path,
    monkeypatch,
    capsys,
    diagnostic_path: str | None,
    expected_override: str | None,
) -> None:
    script_path = tmp_path / "diagnostics-preview.ass"
    script_path.write_text('SendText("preview")\n', encoding="utf-8")

    monkeypatch.setenv("ASS_DIAGNOSTICS", "1")
    monkeypatch.delenv("ASS_DIAGNOSTIC_FILE", raising=False)
    monkeypatch.setenv("ASS_DIAGNOSTIC_MIN_SEVERITY", "info")
    monkeypatch.setenv("ASS_DIAGNOSTIC_MAX_DETAIL", "1")
    monkeypatch.delenv("ASS_DIAGNOSTIC_PATH", raising=False)
    if diagnostic_path is not None:
        expected_path = (tmp_path / diagnostic_path).resolve()
        monkeypatch.setenv("ASS_DIAGNOSTIC_PATH", str(expected_path))

    reset_diagnostic_config()
    try:
        exit_code = run(
            [
                "script",
                str(script_path),
                "--mode",
                "preview",
            ]
        )
    finally:
        reset_diagnostic_config()

    captured = capsys.readouterr()

    assert exit_code == 0
    first_line = captured.out.splitlines()[0]
    assert first_line.startswith("Diagnostics log file   : ")

    printed_path = Path(first_line.removeprefix("Diagnostics log file   : ").strip())
    if expected_override is None:
        assert printed_path.parent == Path(tempfile.gettempdir())
        assert printed_path.name.startswith("actionshellscript_diagnostics_")
        assert printed_path.suffix == ".log"
    else:
        assert printed_path == (tmp_path / expected_override).resolve()
