"""
Centralized diagnostic types and helpers for the scripting frontend.

This module is intentionally lightweight and shared by both lexer.py and parser.py.
It provides:
- diagnostic severity levels
- source positions and text spans
- a diagnostic container
- common lexer/parser factory helpers
- source excerpt rendering

Design notes
------------
- Spans are stored as half-open character offsets: [start, end).
- Tokens are expected to carry absolute source offsets via start_index/end_index.
- `span_from_legacy_token()` is kept only for explicit compatibility callers
  that still provide legacy line/column metadata instead of absolute offsets.
- No parser, AST, or semantic logic lives here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, List, Optional, Sequence


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SourcePosition:
    """A 0-based character index plus cached 1-based line/column for display."""

    index: int
    line: int
    column: int

    @staticmethod
    def from_index(text: str, index: int) -> "SourcePosition":
        if index < 0:
            index = 0
        if index > len(text):
            index = len(text)

        line = 1
        column = 1
        for ch in text[:index]:
            if ch == "\n":
                line += 1
                column = 1
            else:
                column += 1

        return SourcePosition(index=index, line=line, column=column)


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Half-open character span [start, end)."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("TextSpan.start cannot be negative")
        if self.end < self.start:
            raise ValueError("TextSpan.end cannot be less than TextSpan.start")

    @property
    def length(self) -> int:
        return self.end - self.start

    @staticmethod
    def from_bounds(start: int, end: int) -> "TextSpan":
        return TextSpan(start=start, end=end)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: DiagnosticSeverity
    code: str
    message: str
    span: Optional[TextSpan] = None
    source_name: Optional[str] = None
    notes: Sequence[str] = field(default_factory=tuple)

    def format_header(self, source_text: Optional[str] = None) -> str:
        location = ""
        if source_text is not None and self.span is not None:
            pos = SourcePosition.from_index(source_text, self.span.start)
            name = self.source_name or "<source>"
            location = f"{name}:{pos.line}:{pos.column}: "
        elif self.source_name:
            location = f"{self.source_name}: "

        return f"{location}{self.severity.value.upper()} {self.code}: {self.message}"

    def format(self, source_text: Optional[str] = None, context_lines: int = 1) -> str:
        parts: List[str] = [self.format_header(source_text)]

        if source_text is not None and self.span is not None:
            excerpt = render_span_excerpt(source_text, self.span, context_lines=context_lines)
            if excerpt:
                parts.append(excerpt)

        for note in self.notes:
            parts.append(f"note: {note}")

        return "\n".join(parts)


class DiagnosticError(Exception):
    """Raised when compilation should stop after one or more errors."""

    def __init__(self, diagnostics: Sequence[Diagnostic], source_text: Optional[str] = None) -> None:
        self.diagnostics = list(diagnostics)
        self.source_text = source_text
        message = self._build_message()
        super().__init__(message)

    def _build_message(self) -> str:
        if not self.diagnostics:
            return "Compilation failed with unknown diagnostics."
        return "\n\n".join(d.format(self.source_text) for d in self.diagnostics)


class DiagnosticBag:
    def __init__(self) -> None:
        self._items: List[Diagnostic] = []

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    @property
    def items(self) -> List[Diagnostic]:
        return list(self._items)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == DiagnosticSeverity.ERROR for d in self._items)

    @property
    def has_warnings(self) -> bool:
        return any(d.severity == DiagnosticSeverity.WARNING for d in self._items)

    def add(self, diagnostic: Diagnostic) -> Diagnostic:
        self._items.append(diagnostic)
        return diagnostic

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        self._items.extend(diagnostics)

    def clear(self) -> None:
        self._items.clear()

    def error(
        self,
        code: str,
        message: str,
        span: Optional[TextSpan] = None,
        *,
        source_name: Optional[str] = None,
        notes: Optional[Sequence[str]] = None,
    ) -> Diagnostic:
        return self.add(
            Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=code,
                message=message,
                span=span,
                source_name=source_name,
                notes=tuple(notes or ()),
            )
        )

    def warning(
        self,
        code: str,
        message: str,
        span: Optional[TextSpan] = None,
        *,
        source_name: Optional[str] = None,
        notes: Optional[Sequence[str]] = None,
    ) -> Diagnostic:
        return self.add(
            Diagnostic(
                severity=DiagnosticSeverity.WARNING,
                code=code,
                message=message,
                span=span,
                source_name=source_name,
                notes=tuple(notes or ()),
            )
        )

    def info(
        self,
        code: str,
        message: str,
        span: Optional[TextSpan] = None,
        *,
        source_name: Optional[str] = None,
        notes: Optional[Sequence[str]] = None,
    ) -> Diagnostic:
        return self.add(
            Diagnostic(
                severity=DiagnosticSeverity.INFO,
                code=code,
                message=message,
                span=span,
                source_name=source_name,
                notes=tuple(notes or ()),
            )
        )

    def throw_if_errors(self, source_text: Optional[str] = None) -> None:
        if self.has_errors:
            raise DiagnosticError(
                [d for d in self._items if d.severity == DiagnosticSeverity.ERROR],
                source_text,
            )

    def format_all(self, source_text: Optional[str] = None, context_lines: int = 1) -> str:
        return "\n\n".join(d.format(source_text, context_lines=context_lines) for d in self._items)


def span_from_bounds(start: int, end: int) -> TextSpan:
    return TextSpan(start, end)


def span_from_token(token: Any) -> TextSpan:
    """Build a span from token offsets."""
    start = getattr(token, "start_index", None)
    end = getattr(token, "end_index", None)
    if start is not None and end is not None:
        return TextSpan(int(start), int(end))

    raise ValueError("span_from_token requires token start_index/end_index offsets.")


def span_from_legacy_token(token: Any, *, line_width: int) -> TextSpan:
    """Build a span from legacy line/column metadata.

    This helper exists only for older token-shaped inputs that do not yet carry
    absolute source offsets.
    """
    line = int(getattr(token, "line", 1) or 1)
    column = int(getattr(token, "column", 1) or 1)
    value = str(getattr(token, "value", "") or "")
    start = max(0, (line - 1) * line_width + (column - 1))
    end = start + max(1, len(value))
    return TextSpan(start, end)


def make_unexpected_character(char: str, index: int, *, source_name: Optional[str] = None) -> Diagnostic:
    display = repr(char)
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="LEX001",
        message=f"Unexpected character {display}.",
        span=TextSpan(index, index + 1),
        source_name=source_name,
    )


def make_unterminated_string(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="LEX002",
        message="Unterminated string literal.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_invalid_number(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="LEX003",
        message="Invalid numeric literal.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_unexpected_token(
    expected: str,
    actual: str,
    start: int,
    end: int,
    *,
    source_name: Optional[str] = None,
) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="PAR001",
        message=f"Unexpected token '{actual}', expected {expected}.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_expected_expression(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="PAR002",
        message="Expected expression.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_expected_statement(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="PAR003",
        message="Expected statement.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_missing_token(expected: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="PAR004",
        message=f"Expected '{expected}'.",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_syntax_error(message: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="PAR999",
        message=message,
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_duplicate_label(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM001",
        message=f"Duplicate label in block: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_missing_goto_target(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM002",
        message=f"Goto target label not defined: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_illegal_goto_target(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM003",
        message=f"Goto target enters a structured block: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_return_outside_function(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM004",
        message="Return statement used outside of function",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_invalid_external_function_declaration(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM009",
        message="Invalid external function declaration",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_name_collision(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM010",
        message=f"External function already declared: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_library_name_empty(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM011",
        message="External function library name must not be empty",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_alias_empty(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM012",
        message="External function alias must not be empty",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_duplicate_parameter(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM013",
        message=f"External function parameter name is duplicated: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_parameter_default_disallowed(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM014",
        message=f"External function parameter default values are not allowed: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_unknown_type(type_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM015",
        message=f"External function type is unknown: {type_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_type_not_allowed(type_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM016",
        message=f"External function type is not allowed in DLL signatures: {type_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_struct_not_layout_safe(type_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM017",
        message=f"External function struct type is not layout-safe: {type_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_recursive_layout(cycle: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM018",
        message=f"External function signature contains a recursive struct layout: {cycle}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_calling_convention_unsupported(convention: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM019",
        message=f"External function calling convention is not supported: {convention}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_struct_return_not_supported(type_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM028",
        message=f"External function struct return is not supported by the current runtime: {type_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_struct_layout_clause_invalid(clause: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM022",
        message=f"Invalid struct layout clause: {clause}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_struct_layout_clause_duplicated(clause: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM023",
        message=f"External function struct layout clause is duplicated: {clause}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_struct_layout_value_must_be_positive(clause: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM024",
        message=f"External function struct layout value must be positive: {clause}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_struct_layout_value_must_be_power_of_two(clause: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM025",
        message=f"External function struct layout value must be a power of two: {clause}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_struct_layout_clauses_mutually_exclusive(start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM026",
        message="External function struct layout clauses are mutually exclusive: Packed and Align",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_record_name_collision(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM029",
        message=f"Record already declared: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_record_field_type_not_defined(record_name: str, field_name: str, type_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM030",
        message=f"Record '{record_name}' field '{field_name}' uses unknown type: {type_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_enum_name_collision(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM032",
        message=f"Enum already declared: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_enum_member_name_collision(enum_name: str, member_name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM033",
        message=f"Enum '{enum_name}' member already declared: {member_name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_record_recursive_layout(cycle: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM031",
        message=f"Recursive record layout detected: {cycle}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_string_buffer_size_missing(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM020",
        message=f"External function string buffer size must be specified for: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_external_function_string_buffer_size_invalid(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM021",
        message=f"External function string buffer size is invalid: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_unsupported_function(
    name: str,
    start: int,
    end: int,
    *,
    source_name: Optional[str] = None,
    suggested_replacement: Optional[str] = None,
) -> Diagnostic:
    message = f"Unsupported function: {name}"
    if suggested_replacement:
        message += f". Did you mean {suggested_replacement}?"
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM008",
        message=message,
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_undefined_variable(name: str, start: int, end: int, *, source_name: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="SEM007",
        message=f"Undefined variable: {name}",
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def make_loop_control_error(
    keyword: str,
    target: str | None,
    start: int,
    end: int,
    *,
    source_name: Optional[str] = None,
) -> Diagnostic:
    normalized_keyword = keyword.strip().capitalize()
    code = "SEM005" if normalized_keyword == "Continue" else "SEM006"
    if target is None:
        message = f"{normalized_keyword} statement used outside of loop"
    else:
        message = f"{normalized_keyword} statement for target '{target}' used outside of matching loop"
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        span=TextSpan(start, max(start + 1, end)),
        source_name=source_name,
    )


def render_span_excerpt(source_text: str, span: TextSpan, context_lines: int = 1) -> str:
    if not source_text:
        return ""

    start = max(0, min(span.start, len(source_text)))
    end = max(start, min(span.end, len(source_text)))

    line_starts = [0]
    for i, ch in enumerate(source_text):
        if ch == "\n":
            line_starts.append(i + 1)

    def line_index_for_offset(offset: int) -> int:
        lo = 0
        hi = len(line_starts) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if line_starts[mid] <= offset:
                lo = mid + 1
            else:
                hi = mid - 1
        return max(0, hi)

    start_line_idx = line_index_for_offset(start)
    end_line_idx = line_index_for_offset(end if end > start else start)

    first_line = max(0, start_line_idx - context_lines)
    last_line = min(len(line_starts) - 1, end_line_idx + context_lines)

    lines = source_text.splitlines()
    if source_text.endswith("\n"):
        lines.append("")

    width = len(str(last_line + 1))
    rendered: List[str] = []

    for line_idx in range(first_line, last_line + 1):
        line_no = line_idx + 1
        line_text = lines[line_idx] if line_idx < len(lines) else ""
        rendered.append(f"{line_no:>{width}} | {line_text}")

        line_start = line_starts[line_idx]
        line_end = line_starts[line_idx + 1] - 1 if line_idx + 1 < len(line_starts) else len(source_text)
        line_end = max(line_start, line_end)

        highlight_start = max(start, line_start)
        highlight_end = min(max(end, start + 1), line_end)

        if highlight_start < line_end or (span.length == 0 and line_start <= start <= line_end):
            caret_col = max(0, highlight_start - line_start)
            caret_len = max(1, highlight_end - highlight_start)
            rendered.append(f"{' ' * width} | {' ' * caret_col}{'^' * caret_len}")

    return "\n".join(rendered)


__all__ = [
    "Diagnostic",
    "DiagnosticBag",
    "DiagnosticError",
    "DiagnosticSeverity",
    "SourcePosition",
    "TextSpan",
    "make_expected_expression",
    "make_expected_statement",
    "make_duplicate_label",
    "make_illegal_goto_target",
    "make_loop_control_error",
    "make_invalid_number",
    "make_missing_goto_target",
    "make_missing_token",
    "make_invalid_external_function_declaration",
    "make_external_function_name_collision",
    "make_external_function_library_name_empty",
    "make_external_function_alias_empty",
    "make_external_function_duplicate_parameter",
    "make_external_function_parameter_default_disallowed",
    "make_external_function_unknown_type",
    "make_external_function_type_not_allowed",
    "make_external_function_struct_not_layout_safe",
    "make_external_function_recursive_layout",
    "make_external_function_calling_convention_unsupported",
    "make_external_function_struct_return_not_supported",
    "make_struct_layout_clause_invalid",
    "make_struct_layout_clause_duplicated",
    "make_struct_layout_value_must_be_positive",
    "make_struct_layout_value_must_be_power_of_two",
    "make_struct_layout_clauses_mutually_exclusive",
    "make_record_name_collision",
    "make_record_field_type_not_defined",
    "make_record_recursive_layout",
    "make_external_function_string_buffer_size_missing",
    "make_external_function_string_buffer_size_invalid",
    "make_return_outside_function",
    "make_syntax_error",
    "make_unsupported_function",
    "make_undefined_variable",
    "make_unexpected_character",
    "make_unexpected_token",
    "make_unterminated_string",
    "render_span_excerpt",
    "span_from_bounds",
    "span_from_legacy_token",
    "span_from_token",
]
