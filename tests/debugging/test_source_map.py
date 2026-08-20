from __future__ import annotations

from core.debugging.source_map import SourceMap
from core.scripting.diagnostics import DiagnosticBag
from core.scripting.lexer import lex
from core.scripting.parser import Parser


def test_source_map_collects_real_statement_lines() -> None:
    script = "Dim x = 1\nx = x + 2\nSendText(\"ok\")\n"

    assert SourceMap(script).collect_debuggable_source_lines() == [1, 2, 3]


def test_source_map_reports_real_line_for_statement_nodes() -> None:
    script = "Dim x = 1\nx = x + 2\n"
    diagnostics = DiagnosticBag()
    tokens = lex(script, diagnostics=diagnostics, source_name="<script>")
    program = Parser(tokens, diagnostics=diagnostics, source_name="<script>").parse()

    assert diagnostics.has_errors is False
    assert SourceMap(script).get_node_line(program.statements[0]) == 1
    assert SourceMap(script).get_node_line(program.statements[1]) == 2


def test_source_map_includes_select_case_body_statements() -> None:
    script = (
        "Select Case value\n"
        "Case 1\n"
        "    WriteLn(\"one\")\n"
        "Case Else\n"
        "    WriteLn(\"other\")\n"
        "End Select\n"
    )

    lines = SourceMap(script).collect_debuggable_source_lines()

    assert lines == [1, 3, 5]
