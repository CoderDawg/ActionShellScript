from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.scripting import ast_nodes as ast
from core.scripting.diagnostics import DiagnosticBag, DiagnosticError, TextSpan
from core.scripting.lexer import lex
from core.scripting.parser import Parser


@dataclass(frozen=True, slots=True)
class SourceLocation:
    line: int
    span: TextSpan


class SourceMap:
    def __init__(self, source_text: str) -> None:
        self._source_text = source_text or ""

    def collect_debuggable_source_lines(self) -> list[int]:
        diagnostics = DiagnosticBag()
        tokens = lex(
            self._source_text,
            diagnostics=diagnostics,
            source_name="<script>",
        )
        parser = Parser(
            tokens,
            diagnostics=diagnostics,
            source_name="<script>",
        )
        program = parser.parse()

        if diagnostics.has_errors:
            raise DiagnosticError(diagnostics.items, self._source_text)

        debuggable_lines: set[int] = set()
        for statement in self._iter_statements_preorder(program.statements):
            if not self._statement_supports_debug_boundary(statement):
                continue
            line = self.get_node_line(statement)
            if isinstance(line, int) and line >= 1:
                debuggable_lines.add(line)

        return sorted(debuggable_lines)

    def is_debuggable_line(self, line: int) -> bool:
        return int(line) in set(self.collect_debuggable_source_lines())

    def location_for_node(self, node: ast.AstNode | None) -> SourceLocation | None:
        if node is None or node.span is None:
            return None
        line = self.line_for_span(node.span)
        if line is None:
            return None
        return SourceLocation(line=line, span=node.span)

    def line_for_span(self, span: TextSpan | None) -> int | None:
        if span is None:
            return None
        start = getattr(span, "start", None)
        if not isinstance(start, int) or start < 0:
            return None
        return self._line_from_source_index(self._source_text, start)

    def get_node_line(self, node: Any) -> int | None:
        if node is None:
            return None

        direct_line = self._safe_line_attr(node)
        if direct_line is not None:
            return direct_line

        span_start = self._safe_span_start(node)
        if span_start is not None:
            return self._line_from_source_index(self._source_text, span_start)

        return None

    def describe_line_origin(self, node: Any) -> str:
        if node is None:
            return "none"
        if self._safe_line_attr(node) is not None:
            return "direct"
        if self._safe_span_start(node) is not None:
            return "span"
        return "missing"

    def _collect_executable_source_lines(self, source_text: str) -> list[int]:
        executable_lines: list[int] = []
        for index, raw_line in enumerate(source_text.splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            executable_lines.append(index)
        return executable_lines

    def _iter_statements_preorder(
        self,
        statements: list[ast.Statement],
    ) -> Iterable[ast.Statement]:
        for statement in statements:
            yield statement

            if isinstance(statement, ast.Block):
                yield from self._iter_statements_preorder(statement.statements)
            elif isinstance(statement, ast.IfStatement):
                yield from self._iter_statements_preorder(statement.then_branch.statements)
                if statement.else_branch is not None:
                    yield from self._iter_statements_preorder(statement.else_branch.statements)
            elif isinstance(statement, ast.SelectStatement):
                for case_arm in statement.cases:
                    yield from self._iter_statements_preorder(case_arm.body.statements)
            elif isinstance(statement, ast.ForStatement):
                yield from self._iter_statements_preorder(statement.body.statements)
            elif isinstance(statement, ast.WhileStatement):
                yield from self._iter_statements_preorder(statement.body.statements)
            elif isinstance(statement, ast.LoopStatement):
                yield from self._iter_statements_preorder(statement.body.statements)
            elif isinstance(statement, ast.FunctionDecl):
                yield from self._iter_statements_preorder(statement.body.statements)

    def _statement_supports_debug_boundary(self, statement: ast.Statement) -> bool:
        return isinstance(
            statement,
            (
                ast.VarDecl,
                ast.ConstDecl,
                ast.Assignment,
                ast.ExpressionStatement,
                ast.IfStatement,
                ast.SelectStatement,
                ast.ForStatement,
                ast.WhileStatement,
                ast.LoopStatement,
                ast.ReturnStatement,
                ast.ScriptQuitStatement,
                ast.ExitStatement,
                ast.ContinueStatement,
                ast.GotoStatement,
            ),
        )

    def _line_from_source_index(self, source_text: str, index: int) -> int:
        if not source_text:
            return 1
        if index <= 0:
            return 1
        if index > len(source_text):
            index = len(source_text)
        return source_text.count("\n", 0, index) + 1

    def _safe_line_attr(self, node: Any) -> int | None:
        if node is None:
            return None
        for attr_name in ("line", "line_number", "lineno", "source_line", "_source_line"):
            value = getattr(node, attr_name, None)
            if isinstance(value, int) and value > 0:
                return value
        return None

    def _safe_span_start(self, node: Any) -> int | None:
        if node is None:
            return None
        span = getattr(node, "span", None)
        if span is None:
            return None
        start = getattr(span, "start", None)
        if isinstance(start, int) and start >= 0:
            return start
        return None
