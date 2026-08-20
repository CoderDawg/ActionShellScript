from __future__ import annotations

import builtins
from pathlib import Path

from apps.cli.debug_command import _load_script_document, build_parser, run


def test_debug_command_loader_preserves_source_path(tmp_path: Path) -> None:
    script_path = tmp_path / "debug.ass"
    script_path.write_text("Dim x = 1\n", encoding="utf-8")

    document = _load_script_document(str(script_path))

    assert document.document_id == str(script_path.resolve())
    assert document.text == "Dim x = 1\n"
    assert document.source_path == str(script_path.resolve())


def test_debug_command_parser_accepts_sendkeys_key_tap_flag(tmp_path: Path) -> None:
    script_path = tmp_path / "debug.ass"
    script_path.write_text("Dim x = 1\n", encoding="utf-8")

    args = build_parser().parse_args(
        [
            "script",
            str(script_path),
            "--ass-play",
        ]
    )

    assert args.source_kind == "script"
    assert args.source_path == str(script_path)
    assert args.ass_play is True


def test_debug_command_step_mode_prints_events_and_summary(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "debug.ass"
    script_path.write_text(
        "Dim x = 1\nx = x + 2\n",
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--step",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[session_started]" in captured.out
    assert "[stopped] line=1 reason=step" in captured.out
    assert "[stopped] line=2 reason=step" in captured.out
    assert "State        : completed" in captured.out
    assert "Call stack   :" in captured.out
    assert "Variables    :" in captured.out
    assert "- x: 3 (int)" in captured.out


def test_debug_command_breakpoint_mode_stops_on_line(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "breakpoint.ass"
    script_path.write_text(
        "Dim x = 1\nx = x + 2\n",
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=2 reason=breakpoint" in captured.out
    assert "State        : completed" in captured.out
    assert "Call stack   :" in captured.out
    assert "- x: 3 (int)" in captured.out


def test_debug_command_rejects_non_debuggable_breakpoint_line(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "non_debuggable.ass"
    script_path.write_text(
        "Func AddOne(value)\n"
        "    Return value + 1\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Invalid breakpoint request: Breakpoint line 1 is not debuggable." in captured.err
    assert captured.out == ""


def test_debug_command_rejects_duplicate_breakpoint_line(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "duplicate.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 2\n",
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
            "--breakpoint",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Invalid breakpoint request: Breakpoint line 1 is duplicated." in captured.err
    assert captured.out == ""


def test_debug_command_rejects_out_of_range_breakpoint_line(
    tmp_path,
    capsys,
) -> None:
    script_path = tmp_path / "out_of_range.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 2\n",
        encoding="utf-8",
    )

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "3",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Invalid breakpoint request: Breakpoint line 3 is out of range for this script (1-2)." in captured.err
    assert captured.out == ""


def test_debug_command_pause_prompt_shows_current_frame_and_line(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "prompt.ass"
    script_path.write_text(
        "Func AddOne(value)\n"
        "    Return value + 1\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n",
        encoding="utf-8",
    )

    prompts: list[str] = []

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "c"

    monkeypatch.setattr(builtins, "input", fake_input)

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert any("o=step over" in prompt for prompt in prompts)
    assert any("u=step out" in prompt for prompt in prompts)
    assert any("c=continue" in prompt for prompt in prompts)
    assert any("g=go" in prompt for prompt in prompts)
    assert any("q=quit" in prompt for prompt in prompts)
    assert any("h=help" in prompt for prompt in prompts)
    assert not any("r=restart" in prompt for prompt in prompts)
    assert not any("stack, vars, locals, frame N" in prompt for prompt in prompts)
    assert "Paused at line 2" in captured.out
    assert "Current frame: AddOne @ line 1" in captured.out
    assert "Top frame locals:" not in captured.out


def test_debug_command_stack_and_vars_commands_print_details(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "details.ass"
    script_path.write_text(
        "Func AddOne(value)\n"
        "    Return value + 1\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n",
        encoding="utf-8",
    )

    commands = iter(["stack", "vars", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Call stack:" in captured.out
    assert "-> 1. AddOne @ line 1" in captured.out
    assert "value: 1 (int)" in captured.out
    assert "Variables:" in captured.out
    assert "  - x: 1 (int)" in captured.out


def test_debug_command_locals_command_prints_top_frame_locals(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "locals.ass"
    script_path.write_text(
        "Func AddOne(value)\n"
        "    Dim inner = value + 1\n"
        "    Return inner\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n",
        encoding="utf-8",
    )

    commands = iter(["locals", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "3",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Locals:" in captured.out
    assert "  - value: 1 (int)" in captured.out
    assert "  - inner: 2 (int)" in captured.out


def test_debug_command_locals_command_renders_nested_struct_values(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "nested_struct_locals.ass"
    script_path.write_text(
        "Struct Point\n"
        "X As Int32\n"
        "Y As Int32\n"
        "End Struct\n"
        "Struct Pair\n"
        "First As Point\n"
        "Second As Point\n"
        "End Struct\n"
        "Func BuildPair()\n"
        "    Dim first = Point(1, 2)\n"
        "    Dim second = Point(3, 4)\n"
        "    Dim pair = Pair(first, second)\n"
        "    Return pair\n"
        "EndFunc\n"
        "Dim result = BuildPair()\n",
        encoding="utf-8",
    )

    commands = iter(["locals", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "13",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Locals:" in captured.out
    assert "  - first: Point(X=1, Y=2) (Point)" in captured.out
    assert "  - second: Point(X=3, Y=4) (Point)" in captured.out
    assert "  - pair: Pair(First=Point(X=1, Y=2), Second=Point(X=3, Y=4)) (Pair)" in captured.out


def test_debug_command_frame_command_prints_specific_stack_frame_locals(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "frame.ass"
    script_path.write_text(
        "Func Inner(innerValue)\n"
        "    Return innerValue + 1\n"
        "EndFunc\n"
        "\n"
        "Func AddOne(outerValue)\n"
        "    Dim innerResult = Inner(outerValue)\n"
        "    Return innerResult\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n",
        encoding="utf-8",
    )

    commands = iter(["frame 2", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Frame 2:" in captured.out
    assert "Inner @ line 1" in captured.out
    assert "  - innerValue: 1 (int)" in captured.out
    assert "outerValue" not in captured.out


def test_debug_command_frame_top_command_prints_current_frame_locals(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "frame_top.ass"
    script_path.write_text(
        "Func Inner(innerValue)\n"
        "    Return innerValue + 1\n"
        "EndFunc\n"
        "\n"
        "Func AddOne(outerValue)\n"
        "    Dim innerResult = Inner(outerValue)\n"
        "    Return innerResult\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n",
        encoding="utf-8",
    )

    commands = iter(["frame top", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Locals:" in captured.out
    assert "  - innerValue: 1 (int)" in captured.out
    assert "outerValue" not in captured.out


def test_debug_command_print_command_renders_current_marker_and_breakpoints(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "print.ass"
    script_path.write_text(
        "Dim a = 1\n"
        "Dim b = 2\n"
        "Dim c = 3\n"
        "Dim d = 4\n"
        "d = d + 1\n"
        "Dim e = 5\n"
        "Dim f = 6\n",
        encoding="utf-8",
    )

    commands = iter(["p", "p *", "p 5", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "5",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Script lines 3-7:" in captured.out
    assert "Script lines 1-7:" in captured.out
    assert "->* 5 | d = d + 1" in captured.out
    assert "  1 | Dim a = 1" in captured.out
    assert "  7 | Dim f = 6" in captured.out


def test_debug_command_step_over_pauses_after_function_body(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "step_over.ass"
    script_path.write_text(
        "Func AddOne(value)\n"
        "    Dim inner = value + 1\n"
        "    Return inner\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = AddOne(x)\n"
        "Dim y = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["o", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "7",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=7 reason=breakpoint" in captured.out
    assert "[stopped] line=8 reason=step_over" in captured.out
    assert "[stopped] line=2 reason=step_over" not in captured.out


def test_debug_command_step_over_still_hits_breakpoint_inside_callee(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "nested_breakpoint.ass"
    script_path.write_text(
        "Func Inner(value)\n"
        "    Dim inner = value + 1\n"
        "    Return inner\n"
        "EndFunc\n"
        "Dim x = 1\n"
        "x = Inner(x)\n"
        "Dim y = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["o", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "6",
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=6 reason=breakpoint" in captured.out
    assert "[stopped] line=2 reason=breakpoint" in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_step_over_still_hits_breakpoint_inside_loop_body(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "loop_breakpoint.ass"
    script_path.write_text(
        "Func LoopOnce()\n"
        "    For i = 1 To 1\n"
        "        Dim loopValue = i\n"
        "    Next\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "LoopOnce()\n"
        "Dim y = 2\n",
        encoding="utf-8",
    )

    commands = iter(["o", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "8",
            "--breakpoint",
            "3",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=8 reason=breakpoint" in captured.out
    assert "[stopped] line=3 reason=breakpoint" in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_step_over_still_hits_return_inside_branch(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "branch_return.ass"
    script_path.write_text(
        "Func Pick(flag)\n"
        "    If flag Then\n"
        "        Return 1\n"
        "    EndIf\n"
        "    Return 0\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = Pick(x)\n"
        "Dim y = 2\n",
        encoding="utf-8",
    )

    commands = iter(["o", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "9",
            "--breakpoint",
            "3",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=9 reason=breakpoint" in captured.out
    assert "[stopped] line=3 reason=breakpoint" in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_step_over_still_hits_exit_inside_while_branch(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "while_exit.ass"
    script_path.write_text(
        "Func Spin(flag)\n"
        "    While flag\n"
        "        If flag Then\n"
        "            Exit While\n"
        "        EndIf\n"
        "        flag = 0\n"
        "    WEnd\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "Spin(x)\n"
        "Dim y = 2\n",
        encoding="utf-8",
    )

    commands = iter(["o", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "11",
            "--breakpoint",
            "4",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=11 reason=breakpoint" in captured.out
    assert "[stopped] line=4 reason=breakpoint" in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_restart_relaunches_script(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "restart.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["r", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Restarting debugger..." in captured.out
    assert captured.out.count("[session_started]") == 2
    assert "State        : completed" in captured.out


def test_debug_command_quit_cancels_without_restart(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "quit.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["Q"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.count("[session_started]") == 1
    assert "Restarting script execution..." not in captured.out
    assert "State        : completed" not in captured.out


def test_debug_command_help_prints_pause_commands(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "help.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["h", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Debugger commands:" in captured.out
    assert "Navigation: Enter/i=step into, o=step over, u=step out, c=continue, g=go, r=restart, q=quit" in captured.out
    assert "g=go to completion, ignore breakpoints" in captured.out
    assert "Inspect   : stack, vars, locals, frame N, frame top" in captured.out
    assert "Source    : p, p *, p all, p N" in captured.out
    assert "Help      : h" in captured.out


def test_debug_command_go_command_continues_to_next_breakpoint(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "go.ass"
    script_path.write_text(
        "Dim x = 1\n"
        "x = x + 1\n"
        "x = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["g", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "1",
            "--breakpoint",
            "3",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=1 reason=breakpoint" in captured.out
    assert "[stopped] line=3 reason=breakpoint" not in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_step_out_returns_to_caller(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "step_out.ass"
    script_path.write_text(
        "Func Inner(value)\n"
        "    Return value + 1\n"
        "EndFunc\n"
        "\n"
        "Func Outer(value)\n"
        "    Dim innerValue = Inner(value)\n"
        "    Return innerValue\n"
        "EndFunc\n"
        "\n"
        "Dim x = 1\n"
        "x = Outer(x)\n"
        "Dim y = 2\n",
        encoding="utf-8",
    )

    commands = iter(["u", "c"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[stopped] line=2 reason=breakpoint" in captured.out
    assert "[stopped] line=7 reason=step_out" in captured.out
    assert "State        : completed" in captured.out


def test_debug_command_transcript_covers_help_print_step_over_restart_and_quit(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    script_path = tmp_path / "transcript.ass"
    script_path.write_text(
        "Func Inner(value)\n"
        "    Dim inner = value + 1\n"
        "    Return inner\n"
        "EndFunc\n"
        "Dim x = 1\n"
        "x = Inner(x)\n"
        "Dim y = x + 1\n",
        encoding="utf-8",
    )

    commands = iter(["h", "p", "o", "u", "r", "q"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    exit_code = run(
        [
            "script",
            str(script_path),
            "--breakpoint",
            "6",
            "--breakpoint",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.count("[session_started]") == 2
    assert "[stopped] line=6 reason=breakpoint" in captured.out
    assert "[stopped] line=2 reason=breakpoint" in captured.out
    assert "[stopped] line=7 reason=step_out" in captured.out
    assert "Debugger commands:" in captured.out
    assert "Script lines" in captured.out
    assert "Restarting debugger..." in captured.out
    assert "Debugger terminated by user." in captured.out
