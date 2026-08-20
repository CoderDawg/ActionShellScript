from __future__ import annotations

import pytest

from core.debugging.runtime_debug_hooks import RuntimeDebugHooks
from core.debugging.source_map import SourceMap
from core.runtime.script_runtime import ScriptRuntime


class _LineSink:
    def __init__(self) -> None:
        self.lines: list[int | None] = []

    def on_line(self, line, node, context) -> bool:
        _ = node
        _ = context
        self.lines.append(line)
        return True


def test_runtime_goto_jumps_to_label_and_preserves_source_line_stepping() -> None:
    script = (
        "Dim x = 0\n"
        "Start:\n"
        "x = x + 1\n"
        "Goto Finish\n"
        "x = 99\n"
        "Finish:\n"
        "x = x + 1\n"
    )

    sink = _LineSink()
    runtime = ScriptRuntime(
        debugger=RuntimeDebugHooks(source_map=SourceMap(script), sink=sink),
    )

    context = runtime.compile(script)

    assert context.variables["x"] == 2
    assert sink.lines == [1, 2, 3, 4, 6, 7]


def test_runtime_goto_rejects_missing_labels() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Goto target label not defined: Missing"):
        runtime.compile("Goto Missing\n")


def test_runtime_goto_rejects_duplicate_labels_in_a_block() -> None:
    runtime = ScriptRuntime()

    script = (
        "Start:\n"
        "Dim x = 1\n"
        "Start:\n"
        "Dim y = 2\n"
    )

    with pytest.raises(RuntimeError, match="Duplicate label in block: Start"):
        runtime.compile(script)


def test_runtime_goto_rejects_jumps_into_structured_blocks() -> None:
    runtime = ScriptRuntime()

    script = (
        "Goto Inner\n"
        "If True Then\n"
        "Inner:\n"
        "    Dim x = 1\n"
        "EndIf\n"
    )

    with pytest.raises(RuntimeError, match="Goto target enters a structured block: Inner"):
        runtime.compile(script)


def test_runtime_continue_for_honors_targeted_nested_loops() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim outer = 0\n"
        "For i = 1 To 2\n"
        "    While outer < 1\n"
        "        outer = outer + 1\n"
        "        Continue For\n"
        "    Wend\n"
        "    WriteLn(i)\n"
        "Next\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["2\n"]


def test_runtime_select_case_executes_the_first_matching_arm() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = 4\n"
        "Select Case value\n"
        "Case 1, 2\n"
        "    WriteLn(\"low\")\n"
        "Case 3 To 5\n"
        "    WriteLn(\"mid\")\n"
        "Case Else\n"
        "    WriteLn(\"other\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["mid\n"]


def test_runtime_select_case_supports_case_else_fallback() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = 9\n"
        "Select Case value\n"
        "Case 1 To 3\n"
        "    WriteLn(\"small\")\n"
        "Case Else\n"
        "    WriteLn(\"other\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["other\n"]


def test_runtime_select_case_supports_vb_style_comparisons_and_like_patterns() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = 7\n"
        "Select Case value\n"
        "Case Is < 5\n"
        "    WriteLn(\"small\")\n"
        "Case Is >= 5\n"
        "    WriteLn(\"big\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["big\n"]


def test_runtime_select_case_supports_is_not_comparisons() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = 7\n"
        "Select Case value\n"
        "Case Is Not < 5\n"
        "    WriteLn(\"not-small\")\n"
        "Case Is Not 7\n"
        "    WriteLn(\"not-seven\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["not-small\n"]


def test_runtime_select_case_supports_wildcard_like_patterns() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = \"Alpha\"\n"
        "Select Case value\n"
        "Case Like \"A*\"\n"
        "    WriteLn(\"match\")\n"
        "Case Else\n"
        "    WriteLn(\"miss\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["match\n"]


def test_runtime_select_case_supports_not_like_patterns() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = \"Beta\"\n"
        "Select Case value\n"
        "Case Not Like \"A*\"\n"
        "    WriteLn(\"not-a\")\n"
        "Case Else\n"
        "    WriteLn(\"a\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["not-a\n"]


def test_runtime_select_case_supports_is_not_like_patterns() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = \"Beta\"\n"
        "Select Case value\n"
        "Case Is Not Like \"A*\"\n"
        "    WriteLn(\"not-a\")\n"
        "Case Else\n"
        "    WriteLn(\"a\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["not-a\n"]


def test_runtime_select_case_supports_is_not_like_spelled_explicitly() -> None:
    runtime = ScriptRuntime()

    script = (
        "Dim value = \"Beta\"\n"
        "Select Case value\n"
        "Case Is Not Like \"A*\"\n"
        "    WriteLn(\"not-a\")\n"
        "Case Else\n"
        "    WriteLn(\"a\")\n"
        "End Select\n"
    )

    context = runtime.compile(script)

    assert context.console_output == ["not-a\n"]


@pytest.mark.parametrize(
    ("script", "message"),
    [
        ("Continue\n", "Continue statement used outside of loop"),
        ("Continue For\n", "Continue statement for target 'for' used outside of matching loop"),
        ("Continue While\n", "Continue statement for target 'while' used outside of matching loop"),
        ("Continue Loop\n", "Continue statement for target 'loop' used outside of matching loop"),
    ],
)
def test_runtime_continue_reports_a_clear_error_when_used_top_level(
    script: str,
    message: str,
) -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match=message):
        runtime.compile(script)
