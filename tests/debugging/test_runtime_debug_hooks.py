from __future__ import annotations

from core.debugging.runtime_debug_hooks import RuntimeDebugHooks
from core.debugging.source_map import SourceMap
from core.runtime.execution_context import ExecutionContext
from core.scripting.diagnostics import DiagnosticBag
from core.scripting.lexer import lex
from core.scripting.parser import Parser


class _Sink:
    def __init__(self) -> None:
        self.lines: list[int | None] = []
        self.calls: list[str] = []

    def on_line(self, line, node, context) -> bool:
        _ = node
        _ = context
        self.lines.append(line)
        return True

    def on_function_call(self, function_name, context) -> None:
        _ = context
        self.calls.append(f"call:{function_name}")

    def on_function_return(self, function_name, return_value, context) -> None:
        _ = return_value
        _ = context
        self.calls.append(f"return:{function_name}")

    def on_exception(self, exc, node, context) -> None:
        _ = exc
        _ = node
        _ = context


def test_runtime_debug_hooks_forward_real_line_numbers() -> None:
    script = "Dim x = 1\nx = x + 2\n"
    diagnostics = DiagnosticBag()
    tokens = lex(script, diagnostics=diagnostics, source_name="<script>")
    program = Parser(tokens, diagnostics=diagnostics, source_name="<script>").parse()
    statement = program.statements[0]

    sink = _Sink()
    hooks = RuntimeDebugHooks(source_map=SourceMap(script), sink=sink)
    context = ExecutionContext()

    paused = hooks.before_statement(statement, context)

    assert paused is True
    assert context.current_source_line == 1
    assert sink.lines == [1]
