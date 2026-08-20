from __future__ import annotations

import ctypes
import base64
import binascii
import calendar
import hashlib
import fnmatch
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from dataclasses import dataclass
import codecs
import math
import os
import time
import struct
from pathlib import Path
import threading
import zlib
from typing import Any
from ctypes import wintypes

from core.playback.playback_events import (
    PlaybackEvent,
    normalize_shaped_action_to_playback_events,
)
from core.runtime.builtins.builtin_registry import BUILTIN_FUNCTION_NAMES
from core.runtime.execution_context import ExecutionContext
from core.runtime.external_values import ExternalFunctionBinding
from core.runtime.external_values import ExternalParameterInfo
from core.runtime.external_values import ExternalTypeInfo
from core.runtime.external_values import StructLayoutSummary
from core.runtime.runtime_errors import RuntimeErrorMessages
from core.scripting import CANONICAL_TYPE_NAMES
from core.runtime.struct_values import StructDefinition
from core.runtime.struct_values import StructFieldDefinition
from core.runtime.struct_values import StructInstance
from core.runtime.struct_values import RecordDefinition
from core.runtime.struct_values import RecordInstance
from core.runtime.struct_values import build_struct_instance
from core.runtime.struct_values import build_record_instance
from core.runtime.struct_values import clone_runtime_value
from core.scripting import normalize_type_name
from core.scripting import ast_nodes as ast
from core.scripting.diagnostics import DiagnosticBag, DiagnosticError
from core.scripting.lexer import lex
from core.scripting.parser import Parser
from infrastructure.debug_logger import DiagnosticDetail, get_diagnostic_logger


log = get_diagnostic_logger("script_runtime")
script_output_log = get_diagnostic_logger("script.output")


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]

_HOST_INTERACTION_BUILTIN_NAMES = frozenset(
    {
        "keytoggle",
        "getcursorpos",
        "getclientrect",
        "getwindowrect",
        "getwindowplacement",
        "getwindowtext",
        "getwindowlongptr",
        "getparent",
        "getclassname",
        "iszoomed",
        "isiconic",
        "iswindowvisible",
        "iswindowenabled",
        "msgbox",
        "getmonitorinfo",
        "getmonitorinfoex",
        "pixelgetcolor",
        "pixelsearch",
    }
)

_STRUCT_INTEGER_TYPE_BOUNDS: dict[str, tuple[int, int]] = {
    "Int8": (-(2**7), 2**7 - 1),
    "UInt8": (0, 2**8 - 1),
    "Int16": (-(2**15), 2**15 - 1),
    "UInt16": (0, 2**16 - 1),
    "Int32": (-(2**31), 2**31 - 1),
    "UInt32": (0, 2**32 - 1),
    "Int64": (-(2**63), 2**63 - 1),
    "UInt64": (0, 2**64 - 1),
}

_STRUCT_FLOAT_TYPE_NAMES = frozenset({"Float32", "Float64"})
_STRUCT_STRING_TYPE_NAMES = frozenset({"String"})
_STRUCT_BOOL_TYPE_NAMES = frozenset({"Bool"})
_STRUCT_CHAR_TYPE_NAMES = frozenset({"Char"})
_STRUCT_POINTER_TYPE_NAMES = frozenset({"Ptr", "IntPtr"})
_EXTERNAL_CALLING_CONVENTIONS = frozenset({"winapi", "stdcall", "cdecl"})
_EXTERNAL_STRING_BUFFER_CAPACITY = 4096

_DATE_TIME_UNIT_ALIASES: dict[str, str] = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "wk": "weeks",
    "wks": "weeks",
    "week": "weeks",
    "weeks": "weeks",
    "mo": "months",
    "mos": "months",
    "month": "months",
    "months": "months",
    "y": "years",
    "yr": "years",
    "yrs": "years",
    "year": "years",
    "years": "years",
}

_DATE_TIME_UNIT_TO_SECONDS: dict[str, int] = {
    "seconds": 1,
    "minutes": 60,
    "hours": 60 * 60,
    "days": 24 * 60 * 60,
    "weeks": 7 * 24 * 60 * 60,
}

# ParseDateTime tuning: these tables keep the strict-format fallback easy to
# tweak without digging through the parser body.
_NUMERIC_DATE_TIME_DATE_SEPARATORS = frozenset({"/", "-", "."})
_NUMERIC_DATE_TIME_TIME_SEPARATORS = frozenset({":", "-", "."})
_NUMERIC_DATE_TIME_BOUNDARY_SEPARATORS = frozenset({" ", "T", "_"})
_NUMERIC_DATE_TIME_SEPARATOR_GROUPS: dict[str, frozenset[str]] = {
    "date": _NUMERIC_DATE_TIME_DATE_SEPARATORS,
    "time": _NUMERIC_DATE_TIME_TIME_SEPARATORS,
    "datetime": _NUMERIC_DATE_TIME_BOUNDARY_SEPARATORS,
}
_NUMERIC_DATE_TIME_TOKEN_REGEX_PATTERNS: dict[str, str] = {
    "%": re.escape("%"),
    "Y": r"(?P<year>\d{4})",
    "y": r"(?P<year2>\d{2})",
    "m": r"(?P<month>\d{1,2})",
    "d": r"(?P<day>\d{1,2})",
    "H": r"(?P<hour24>\d{1,2})",
    "I": r"(?P<hour12>\d{1,2})",
    "M": r"(?P<minute>\d{1,2})",
    "S": r"(?P<second>\d{1,2})",
    "f": r"(?P<microsecond>\d{1,6})",
    "p": r"(?P<ampm>AM|PM|am|pm)",
}
_NUMERIC_DATE_TIME_TOKEN_GROUPS: dict[str, str] = {
    "Y": "date",
    "y": "date",
    "m": "date",
    "d": "date",
    "H": "time",
    "I": "time",
    "M": "time",
    "S": "time",
    "f": "time",
    "p": "time",
}

_ENGLISH_MONTH_NAME_TO_NUMBER: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_ENGLISH_WEEKDAY_NAME_TO_NUMBER: dict[str, int] = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "weds": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _build_external_builtin_layout_policy() -> dict[str, tuple[Any | None, int | None, int | None, bool, bool, bool, bool]]:
    pointer_size = max(1, struct.calcsize("P"))
    int_ptr_ctype = ctypes.c_int64 if pointer_size >= 8 else ctypes.c_int32
    return {
        "Int8": (ctypes.c_int8, 1, 1, True, True, True, True),
        "UInt8": (ctypes.c_uint8, 1, 1, True, True, True, True),
        "Int16": (ctypes.c_int16, 2, 2, True, True, True, True),
        "UInt16": (ctypes.c_uint16, 2, 2, True, True, True, True),
        "Int32": (ctypes.c_int32, 4, 4, True, True, True, True),
        "UInt32": (ctypes.c_uint32, 4, 4, True, True, True, True),
        "Int64": (ctypes.c_int64, 8, 8, True, True, True, True),
        "UInt64": (ctypes.c_uint64, 8, 8, True, True, True, True),
        "Float32": (ctypes.c_float, 4, 4, True, True, True, True),
        "Float64": (ctypes.c_double, 8, 8, True, True, True, True),
        "Bool": (ctypes.c_int32, 4, 4, True, True, True, True),
        "Char": (ctypes.c_uint16, 2, 2, True, True, True, True),
        "Ptr": (ctypes.c_void_p, pointer_size, pointer_size, True, True, True, True),
        "IntPtr": (int_ptr_ctype, pointer_size, pointer_size, True, True, True, True),
        "String": (ctypes.c_wchar_p, pointer_size, pointer_size, False, False, False, True),
    }


_EXTERNAL_BUILTIN_LAYOUT_POLICY = _build_external_builtin_layout_policy()


class _LoopExitSignal(Exception):
    def __init__(self, target: str | None = None) -> None:
        super().__init__(target)
        self.target = target


class _LoopContinueSignal(Exception):
    def __init__(self, target: str | None = None) -> None:
        super().__init__(target)
        self.target = target


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        super().__init__(value)
        self.value = value


class _ScriptQuitSignal(Exception):
    def __init__(self, exit_code: int) -> None:
        super().__init__(exit_code)
        self.exit_code = int(exit_code)


class _GotoSignal(Exception):
    def __init__(
        self,
        label: str,
        statement: ast.GotoStatement,
        source_ancestry: tuple[str, ...],
    ) -> None:
        super().__init__(label)
        self.label = str(label)
        self.statement = statement
        self.source_ancestry = tuple(source_ancestry)


class ScriptRuntimeCancelled(Exception):
    """Raised when execution is canceled externally."""


@dataclass(frozen=True, slots=True)
class _LabelInfo:
    name: str
    scope_id: str
    statement_index: int
    ancestry: tuple[str, ...]


class ScriptRuntime:
    DEFAULT_MAX_LOOP_ITERATIONS = 100_000
    DEFAULT_MAX_CALL_DEPTH = 250
    DEFAULT_MOUSE_MOVE_SPEED = 10

    def __init__(
        self,
        *,
        max_loop_iterations: int | None = None,
        max_call_depth: int = DEFAULT_MAX_CALL_DEPTH,
        debugger: Any | None = None,
        host_values: dict[str, Any] | None = None,
        special_values: dict[str, Any] | None = None,
        host_services: dict[str, Any] | None = None,
        default_mouse_move_speed: int = DEFAULT_MOUSE_MOVE_SPEED,
        default_current_event_delay_ms: int = 0,
        stop_event: threading.Event | None = None,
    ) -> None:
        self._max_loop_iterations = (
            self.DEFAULT_MAX_LOOP_ITERATIONS
            if max_loop_iterations is None
            else int(max_loop_iterations)
        )
        self._max_call_depth = int(max_call_depth)
        self._debugger = debugger
        self._host_values = dict(host_values or {})
        self._special_values = dict(special_values or {})
        self._host_services = dict(host_services or {})
        self._default_mouse_move_speed = self._clamp_mouse_move_speed(
            default_mouse_move_speed
        )
        self._default_current_event_delay_ms = max(0, int(default_current_event_delay_ms))
        self._stop_event = stop_event
        self._source_text = ""
        self._last_script_exit_code = 0
        self._active_loop_depth = 0
        self._loop_stack: list[str] = []
        self._dll_library_cache: dict[tuple[str, str], Any] = {}
        self._external_struct_layout_cache: dict[str, StructLayoutSummary] = {}
        self._external_struct_layout_in_progress: set[str] = set()
        self._external_struct_layout_stack: list[str] = []

    def _clamp_mouse_move_speed(self, speed: int) -> int:
        return max(0, min(100, int(speed)))

    def set_debugger(self, debugger: Any | None) -> None:
        self._debugger = debugger

    def _check_stop_requested(self) -> None:
        if isinstance(self._stop_event, threading.Event) and self._stop_event.is_set():
            raise ScriptRuntimeCancelled("Script execution was canceled.")

    def get_last_script_exit_code(self) -> int:
        return int(self._last_script_exit_code)

    def compile(self, source: str, *, source_path: str | Path | None = None) -> ExecutionContext:
        self._check_stop_requested()
        source_text = source or ""
        self._source_text = source_text
        self._last_script_exit_code = 0
        self._external_struct_layout_cache.clear()
        self._external_struct_layout_in_progress.clear()
        self._external_struct_layout_stack.clear()
        log.info(
            "Runtime execution started",
            event_id="runtime.execute.started",
            source_length=len(source_text),
            debugger_attached=self._debugger is not None,
        )

        diagnostics = DiagnosticBag()
        source_name = self._source_name_from_source_path(source_path)
        tokens = lex(source_text, diagnostics=diagnostics, source_name=source_name)
        parser = Parser(tokens, diagnostics=diagnostics, source_name=source_name)
        program = parser.parse()

        if diagnostics.has_errors:
            log.error(
                "Runtime execution failed due to diagnostics",
                event_id="runtime.execute.diagnostics_failed",
                diagnostic_count=len(diagnostics.items),
            )
            raise DiagnosticError(diagnostics.items, source_text)

        context = ExecutionContext(
            default_mouse_move_speed=self._default_mouse_move_speed,
            default_current_event_delay_ms=self._default_current_event_delay_ms,
        )
        context.max_call_depth = self._max_call_depth
        context.set_debugger(self._debugger)
        self._register_builtin_structs(context)
        self._register_enum_declarations(program.statements, context)

        for name, value in self._host_values.items():
            context.set_host_value(name, value)
        for name, value in self._special_values.items():
            context.set_special_value(name, value)
        self._apply_script_location_special_values(context, source_path)
        context.set_special_value("WorkingDir", os.getcwd())
        for name, service in self._host_services.items():
            context.set_host_service(name, service)

        try:
            self._execute_program(program, context)
        except ScriptRuntimeCancelled as exc:
            log.exception(
                "Runtime execution cancelled",
                exc,
                event_id="runtime.execute.cancelled",
            )
            raise
        except Exception as exc:
            log.exception(
                "Runtime execution failed",
                exc,
                event_id="runtime.execute.failed",
            )
            raise
        self._last_script_exit_code = int(context.script_exit_code)
        log.info(
            "Runtime execution completed",
            event_id="runtime.execute.completed",
            script_exit_code=self._last_script_exit_code,
            emitted_event_count=len(context.playback_events),
            diagnostic_count=len(context.diagnostics),
        )
        return context

    def evaluate_debug_expression(self, expression_text: str, context: ExecutionContext) -> Any:
        source_text = str(expression_text or "").strip()
        if not source_text:
            raise RuntimeError("Watch expression cannot be empty.")

        diagnostics = DiagnosticBag()
        tokens = lex(source_text, diagnostics=diagnostics, source_name="<watch>")
        expression = Parser(tokens, diagnostics=diagnostics, source_name="<watch>").parse_expression_only()
        diagnostics.throw_if_errors(source_text=source_text)

        if any(isinstance(node, ast.CallExpr) for node in ast.walk(expression)):
            raise RuntimeError("Watch expressions cannot call functions.")

        return self._evaluate_expression(expression, context)

    def execute_to_playback_events(
        self,
        source: str,
        *,
        source_path: str | Path | None = None,
    ) -> list[PlaybackEvent]:
        self._check_stop_requested()
        original_debugger = self._debugger
        self._debugger = None
        try:
            context = self.compile(source, source_path=source_path)
        finally:
            self._debugger = original_debugger
        playback_events = self._runtime_playback_events_from_context(context.playback_events)
        log.info(
            "Converted runtime execution context to playback events",
            event_id="runtime.playback_events.completed",
            raw_event_count=len(context.playback_events),
            playback_event_count=len(playback_events),
        )
        return playback_events

    def _runtime_playback_events_from_context(
        self,
        events: list[dict[str, Any]],
    ) -> list[PlaybackEvent]:
        playback_events: list[PlaybackEvent] = []
        for event in events:
            normalized_events = normalize_shaped_action_to_playback_events(event)
            if normalized_events is None:
                continue
            playback_events.extend(normalized_events)
        return playback_events

    def _source_name_from_source_path(self, source_path: str | Path | None) -> str:
        if source_path is None:
            return "<script>"
        path = Path(source_path)
        return str(path)

    def _apply_script_location_special_values(
        self,
        context: ExecutionContext,
        source_path: str | Path | None,
    ) -> None:
        if source_path is None:
            return

        path = Path(source_path)
        context.set_special_value("ScriptName", path.name or str(path))
        context.set_special_value("ScriptDirectory", str(path.parent))

    def _expect_arg_count(self, name: str, args: list[Any], count: int) -> None:
        if len(args) != count:
            raise RuntimeError(RuntimeErrorMessages.expects_argument_count(name, count))

    def _expect_arg_counts(self, name: str, args: list[Any], *counts: int) -> None:
        if len(args) not in counts:
            raise RuntimeError(RuntimeErrorMessages.expects_argument_counts(name, *counts))

    def _expect_at_least_arg_count(self, name: str, args: list[Any], minimum: int) -> None:
        if len(args) < minimum:
            raise RuntimeError(
                RuntimeErrorMessages.expects_at_least_arguments(name, minimum)
            )

    def _emit_script_output_diagnostic(
        self,
        message: str,
        context: ExecutionContext,
        *,
        event_id: str,
    ) -> None:
        fields: dict[str, object] = {}
        if context.current_source_line is not None:
            fields["source_line"] = context.current_source_line

        script_output_log.info(
            message,
            detail=DiagnosticDetail.ESSENTIAL,
            event_id=event_id,
            **fields,
        )

    def _execute_program(self, program: ast.Program, context: ExecutionContext) -> None:
        scope_id = "global"
        ancestry: tuple[str, ...] = ()
        scope_labels = self._collect_scope_labels(program.statements, scope_id, ancestry)

        for statement in program.statements:
            if isinstance(statement, ast.FunctionDecl):
                self._register_function_declaration(statement, context)
        self._register_struct_declarations(program.statements, context)
        self._register_record_declarations(program.statements, context)
        self._validate_registered_struct_definitions(context)
        self._validate_registered_record_definitions(context)
        self._register_external_function_declarations(program.statements, context)
        self._validate_registered_record_name_collisions(context)
        self._validate_registered_external_function_definitions(context)

        try:
            self._execute_statement_sequence(
                program.statements,
                context,
                scope_id=scope_id,
                scope_labels=scope_labels,
                ancestry=ancestry,
            )
        except _LoopContinueSignal as signal:
            exc = RuntimeError(self._outside_loop_error_message("Continue", signal.target))
            context.record_exception(exc, None)
            raise exc
        except _LoopExitSignal as signal:
            exc = RuntimeError(self._outside_loop_error_message("Exit", signal.target))
            context.record_exception(exc, None)
            raise exc
        except _GotoSignal as signal:
            exc = RuntimeError(self._goto_label_not_defined_message(signal.label))
            context.record_exception(exc, signal.statement)
            raise exc
        except _ScriptQuitSignal as signal:
            context.script_exit_code = self._coerce_script_exit_code(signal.exit_code)

    def _execute_block(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        self._execute_statement_sequence(
            statements,
            context,
            scope_id=scope_id,
            scope_labels=scope_labels,
            ancestry=ancestry,
        )

    def _execute_statement_sequence(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        index = 0
        while index < len(statements):
            statement = statements[index]
            self._check_stop_requested()
            try:
                self._execute_statement(
                    statement,
                    context,
                    scope_id=scope_id,
                    scope_labels=scope_labels,
                    ancestry=ancestry,
                )
            except _GotoSignal as signal:
                label_key = signal.label.strip().lower()
                target = scope_labels.get(label_key)
                if target is None:
                    raise
                if not self._goto_target_is_legal(
                    source_ancestry=signal.source_ancestry,
                    target_ancestry=target.ancestry,
                ):
                    exc = RuntimeError(self._goto_enters_structured_block_message(target.name))
                    context.record_exception(exc, signal.statement)
                    raise exc
                index = target.statement_index
                continue
            index += 1

    def _collect_scope_labels(
        self,
        statements: list[ast.Statement],
        scope_id: str,
        ancestry: tuple[str, ...],
    ) -> dict[str, _LabelInfo]:
        label_map: dict[str, _LabelInfo] = {}
        self._collect_scope_labels_into(
            statements,
            label_map,
            scope_id=scope_id,
            ancestry=ancestry,
        )
        return label_map

    def _execute_statement(
        self,
        statement: ast.Statement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        statement_line = self._get_node_line(statement)
        context.push_source_line(statement_line)
        debugger = self._get_debugger(context)
        try:
            if debugger is not None:
                before_statement = getattr(debugger, "before_statement", None)
                if callable(before_statement):
                    paused = bool(before_statement(statement, context))
                    if paused:
                        wait_for_resume = getattr(debugger, "wait_for_resume", None)
                        if callable(wait_for_resume):
                            wait_for_resume(context)

            try:
                if isinstance(statement, ast.Block):
                    self._execute_block(
                        statement.statements,
                        context,
                        scope_id=scope_id,
                        scope_labels=self._collect_scope_labels(statement.statements, scope_id, ancestry),
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.FunctionDecl):
                    self._register_function_declaration(statement, context)
                elif isinstance(statement, ast.StructDecl):
                    pass
                elif isinstance(statement, ast.EnumDecl):
                    self._execute_enum_decl(statement, context)
                elif isinstance(statement, ast.RecordDecl):
                    pass
                elif isinstance(statement, ast.ExternalFunctionDecl):
                    pass
                elif isinstance(statement, ast.VarDecl):
                    self._execute_var_decl(statement, context)
                elif isinstance(statement, ast.ConstDecl):
                    self._execute_const_decl(statement, context)
                elif isinstance(statement, ast.Assignment):
                    self._execute_assignment(statement, context)
                elif isinstance(statement, ast.ExpressionStatement):
                    self._execute_expression_statement(statement, context)
                elif isinstance(statement, ast.IfStatement):
                    self._execute_if_statement(
                        statement,
                        context,
                        scope_id=scope_id,
                        scope_labels=scope_labels,
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.SelectStatement):
                    self._execute_select_statement(
                        statement,
                        context,
                        scope_id=scope_id,
                        scope_labels=scope_labels,
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.ForStatement):
                    self._execute_for_statement(
                        statement,
                        context,
                        scope_id=scope_id,
                        scope_labels=scope_labels,
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.WhileStatement):
                    self._execute_while_statement(
                        statement,
                        context,
                        scope_id=scope_id,
                        scope_labels=scope_labels,
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.LoopStatement):
                    self._execute_loop_statement(
                        statement,
                        context,
                        scope_id=scope_id,
                        scope_labels=scope_labels,
                        ancestry=ancestry,
                    )
                elif isinstance(statement, ast.ReturnStatement):
                    self._execute_return_statement(statement, context)
                elif isinstance(statement, ast.ScriptQuitStatement):
                    self._execute_script_quit_statement(statement, context)
                elif isinstance(statement, ast.ExitStatement):
                    self._execute_exit_statement(statement, context)
                elif isinstance(statement, ast.ContinueStatement):
                    self._execute_continue_statement(statement, context)
                elif isinstance(statement, ast.GotoStatement):
                    self._execute_goto_statement(statement, context, ancestry=ancestry)
                elif isinstance(statement, ast.LabelStatement):
                    self._execute_label_statement(statement, context)
                else:
                    raise RuntimeError(
                        RuntimeErrorMessages.unsupported_statement(
                            "runtime execution",
                            statement.kind,
                        )
                    )
            except (_ReturnSignal, _LoopExitSignal, _LoopContinueSignal, _GotoSignal, _ScriptQuitSignal):
                raise
            except BaseException as exc:
                context.record_exception(exc, statement)
                raise
        finally:
            context.pop_source_line()

    def _register_function_declaration(
        self,
        statement: ast.FunctionDecl,
        context: ExecutionContext,
    ) -> None:
        context.register_function(statement.name, statement)

    def _register_builtin_structs(self, context: ExecutionContext) -> None:
        context.register_struct("tm", self._build_tm_struct_definition())

    def _register_struct_declarations(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.StructDecl):
                struct_name = normalize_type_name(statement.name)
                normalized_struct_name = struct_name.lower() if struct_name else ""
                if (
                    not normalized_struct_name
                    or normalized_struct_name in BUILTIN_FUNCTION_NAMES
                    or context.has_function(statement.name)
                    or context.has_record(statement.name)
                    or context.has_external_function(statement.name)
                    or context.has_enum(statement.name)
                    or context.has_struct(statement.name)
                ):
                    raise RuntimeError(RuntimeErrorMessages.struct_name_collision(statement.name))
                context.register_struct(
                    statement.name,
                    self._build_struct_definition(statement),
                )
                continue

            if isinstance(statement, ast.Block):
                self._register_struct_declarations(statement.statements, context)
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._register_struct_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.IfStatement):
                self._register_struct_declarations(statement.then_branch.statements, context)
                if statement.else_branch is not None:
                    self._register_struct_declarations(statement.else_branch.statements, context)
                continue

            if isinstance(statement, ast.ForStatement):
                self._register_struct_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.WhileStatement):
                self._register_struct_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.LoopStatement):
                self._register_struct_declarations(statement.body.statements, context)

    def _register_enum_declarations(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.EnumDecl):
                enum_name = normalize_type_name(statement.name)
                normalized_enum_name = enum_name.lower() if enum_name else ""
                existing_function_names = {name.lower() for name in context.functions}
                existing_struct_names = {name.lower() for name in context.structs}
                existing_record_names = {name.lower() for name in context.records}
                existing_external_names = {name.lower() for name in context.external_functions}
                existing_enum_names = {name.lower() for name in context.enums}
                if (
                    not normalized_enum_name
                    or normalized_enum_name in BUILTIN_FUNCTION_NAMES
                    or normalized_enum_name in existing_function_names
                    or normalized_enum_name in existing_struct_names
                    or normalized_enum_name in existing_record_names
                    or normalized_enum_name in existing_external_names
                    or normalized_enum_name in existing_enum_names
                ):
                    raise RuntimeError(RuntimeErrorMessages.enum_name_collision(statement.name))
                context.register_enum(statement.name, statement)
                continue

            if isinstance(statement, ast.Block):
                self._register_enum_declarations(statement.statements, context)
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._register_enum_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.IfStatement):
                self._register_enum_declarations(statement.then_branch.statements, context)
                if statement.else_branch is not None:
                    self._register_enum_declarations(statement.else_branch.statements, context)
                continue

            if isinstance(statement, ast.ForStatement):
                self._register_enum_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.WhileStatement):
                self._register_enum_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.LoopStatement):
                self._register_enum_declarations(statement.body.statements, context)

    def _execute_enum_decl(self, statement: ast.EnumDecl, context: ExecutionContext) -> None:
        enum_name = normalize_type_name(statement.name)
        if not enum_name:
            raise RuntimeError(RuntimeErrorMessages.enum_name_collision(statement.name))

        if (
            context.has_variable(enum_name)
            or context.has_function(enum_name)
            or context.has_struct(enum_name)
            or context.has_record(enum_name)
            or context.has_external_function(enum_name)
        ):
            raise RuntimeError(RuntimeErrorMessages.enum_name_collision(statement.name))

        enum_values: dict[str, int] = {}
        seen_member_names: set[str] = set()
        next_value = 0
        context.set_constant(statement.name, enum_values)

        for member in statement.members:
            member_name = str(member.name).strip()
            normalized_member_name = member_name.lower()
            if (
                not member_name
                or normalized_member_name in seen_member_names
                or context.has_variable(member_name)
                or context.has_function(member_name)
                or context.has_struct(member_name)
                or context.has_record(member_name)
                or context.has_external_function(member_name)
                or context.has_enum(member_name)
            ):
                raise RuntimeError(
                    RuntimeErrorMessages.enum_member_name_collision(enum_name, member_name)
                )

            if member.initializer is None:
                member_value = next_value
            else:
                evaluated_value = self._evaluate_expression(member.initializer, context)
                if isinstance(evaluated_value, bool) or not isinstance(evaluated_value, (int, float)):
                    raise RuntimeError(
                        RuntimeErrorMessages.enum_member_value_must_be_integer(
                            enum_name,
                            member_name,
                        )
                    )
                member_value = int(evaluated_value)

            enum_values[member_name] = member_value
            seen_member_names.add(normalized_member_name)
            context.set_constant(statement.name, dict(enum_values))
            context.set_constant(member_name, member_value)
            next_value = member_value + 1

        context.register_enum(statement.name, statement)

    def _register_record_declarations(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
        *,
        seen_record_names: set[str] | None = None,
    ) -> None:
        if seen_record_names is None:
            seen_record_names = set()
        for statement in statements:
            if isinstance(statement, ast.RecordDecl):
                record_name = normalize_type_name(statement.name)
                normalized_record_name = record_name.lower() if record_name else ""
                existing_function_names = {name.lower() for name in context.functions}
                existing_struct_names = {name.lower() for name in context.structs}
                existing_enum_names = {name.lower() for name in context.enums}
                if (
                    not normalized_record_name
                    or normalized_record_name in seen_record_names
                    or normalized_record_name in BUILTIN_FUNCTION_NAMES
                    or normalized_record_name in existing_function_names
                    or normalized_record_name in existing_struct_names
                    or normalized_record_name in existing_enum_names
                    or context.has_external_function(statement.name)
                ):
                    raise RuntimeError(
                        RuntimeErrorMessages.record_name_collision(statement.name)
                    )
                seen_record_names.add(normalized_record_name)
                context.register_record(
                    statement.name,
                    self._build_record_definition(statement),
                )
                continue

            if isinstance(statement, ast.Block):
                self._register_record_declarations(
                    statement.statements,
                    context,
                    seen_record_names=seen_record_names,
                )
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._register_record_declarations(
                    statement.body.statements,
                    context,
                    seen_record_names=seen_record_names,
                )
                continue

            if isinstance(statement, ast.IfStatement):
                self._register_record_declarations(
                    statement.then_branch.statements,
                    context,
                    seen_record_names=seen_record_names,
                )
                if statement.else_branch is not None:
                    self._register_record_declarations(
                        statement.else_branch.statements,
                        context,
                        seen_record_names=seen_record_names,
                    )
                continue

            if isinstance(statement, ast.ForStatement):
                self._register_record_declarations(
                    statement.body.statements,
                    context,
                    seen_record_names=seen_record_names,
                )
                continue

            if isinstance(statement, ast.WhileStatement):
                self._register_record_declarations(
                    statement.body.statements,
                    context,
                    seen_record_names=seen_record_names,
                )
                continue

            if isinstance(statement, ast.LoopStatement):
                self._register_record_declarations(
                    statement.body.statements,
                    context,
                    seen_record_names=seen_record_names,
                )

    def _register_external_function_declarations(
        self,
        statements: list[ast.Statement],
        context: ExecutionContext,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.ExternalFunctionDecl):
                binding = self._build_external_function_binding(statement, context)
                context.register_external_function(statement.name, binding)
                continue

            if isinstance(statement, ast.Block):
                self._register_external_function_declarations(statement.statements, context)
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._register_external_function_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.IfStatement):
                self._register_external_function_declarations(statement.then_branch.statements, context)
                if statement.else_branch is not None:
                    self._register_external_function_declarations(statement.else_branch.statements, context)
                continue

            if isinstance(statement, ast.ForStatement):
                self._register_external_function_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.WhileStatement):
                self._register_external_function_declarations(statement.body.statements, context)
                continue

            if isinstance(statement, ast.LoopStatement):
                self._register_external_function_declarations(statement.body.statements, context)

    def _validate_registered_struct_definitions(self, context: ExecutionContext) -> None:
        for struct_definition in context.structs.values():
            self._validate_struct_definition(struct_definition, context)
        self._validate_struct_layout_cycles(context)

    def _validate_registered_record_definitions(self, context: ExecutionContext) -> None:
        for record_definition in context.records.values():
            self._validate_record_definition(record_definition, context)
        self._validate_record_layout_cycles(context)

    def _validate_registered_record_name_collisions(self, context: ExecutionContext) -> None:
        existing_external_names = {name.lower() for name in context.external_functions}
        for record_name in context.records:
            if record_name.lower() in existing_external_names:
                raise RuntimeError(RuntimeErrorMessages.record_name_collision(record_name))

    def _validate_struct_definition(
        self,
        definition: StructDefinition,
        context: ExecutionContext,
    ) -> None:
        for field in definition.fields:
            expected_type_name = normalize_type_name(field.type_name)
            if not expected_type_name:
                raise RuntimeError(
                    RuntimeErrorMessages.struct_field_type_not_defined(
                        definition.name,
                        field.name,
                        field.type_name,
                    )
                )

            if expected_type_name in CANONICAL_TYPE_NAMES or context.has_enum(expected_type_name):
                continue

            if not context.has_struct(expected_type_name):
                raise RuntimeError(
                    RuntimeErrorMessages.struct_field_type_not_defined(
                        definition.name,
                        field.name,
                        expected_type_name,
                    )
                )

    def _validate_record_definition(
        self,
        definition: RecordDefinition,
        context: ExecutionContext,
    ) -> None:
        for field in definition.fields:
            expected_type_name = normalize_type_name(field.type_name)
            if not expected_type_name:
                raise RuntimeError(
                    RuntimeErrorMessages.record_field_type_not_defined(
                        definition.name,
                        field.name,
                        field.type_name,
                    )
                )

            if expected_type_name in CANONICAL_TYPE_NAMES or context.has_enum(expected_type_name):
                continue

            if not context.has_struct(expected_type_name) and not context.has_record(expected_type_name):
                raise RuntimeError(
                    RuntimeErrorMessages.record_field_type_not_defined(
                        definition.name,
                        field.name,
                        expected_type_name,
                    )
                )

    def _validate_struct_layout_cycles(self, context: ExecutionContext) -> None:
        adjacency: dict[str, tuple[str, ...]] = {}
        for struct_name, definition in context.structs.items():
            referenced_structs: list[str] = []
            for field in definition.fields:
                expected_type_name = normalize_type_name(field.type_name)
                if expected_type_name in CANONICAL_TYPE_NAMES or context.has_enum(expected_type_name):
                    continue
                if context.has_struct(expected_type_name):
                    referenced_structs.append(expected_type_name)
            adjacency[struct_name] = tuple(dict.fromkeys(referenced_structs))

        visited: set[str] = set()
        active: set[str] = set()
        path: list[str] = []

        def visit(struct_name: str) -> None:
            if struct_name in active:
                cycle_start = path.index(struct_name)
                cycle = path[cycle_start:] + [struct_name]
                raise RuntimeError(
                    RuntimeErrorMessages.recursive_struct_layout_detected(cycle)
                )
            if struct_name in visited:
                return

            visited.add(struct_name)
            active.add(struct_name)
            path.append(struct_name)
            try:
                for referenced_name in adjacency.get(struct_name, ()):
                    visit(referenced_name)
            finally:
                path.pop()
                active.remove(struct_name)

        for struct_name in adjacency:
            if struct_name not in visited:
                visit(struct_name)

    def _validate_record_layout_cycles(self, context: ExecutionContext) -> None:
        adjacency: dict[str, tuple[str, ...]] = {}
        for record_name, definition in context.records.items():
            referenced_records: list[str] = []
            for field in definition.fields:
                expected_type_name = normalize_type_name(field.type_name)
                if expected_type_name in CANONICAL_TYPE_NAMES or context.has_enum(expected_type_name):
                    continue
                if context.has_record(expected_type_name):
                    referenced_records.append(expected_type_name)
            adjacency[record_name] = tuple(dict.fromkeys(referenced_records))

        visited: set[str] = set()
        active: set[str] = set()
        path: list[str] = []

        def visit(record_name: str) -> None:
            if record_name in active:
                cycle_start = path.index(record_name)
                cycle = path[cycle_start:] + [record_name]
                raise RuntimeError(
                    RuntimeErrorMessages.recursive_record_layout_detected(cycle)
                )
            if record_name in visited:
                return

            visited.add(record_name)
            active.add(record_name)
            path.append(record_name)
            try:
                for referenced_name in adjacency.get(record_name, ()):
                    visit(referenced_name)
            finally:
                path.pop()
                active.remove(record_name)

        for record_name in adjacency:
            if record_name not in visited:
                visit(record_name)

    def _build_external_function_binding(
        self,
        declaration: ast.ExternalFunctionDecl,
        context: ExecutionContext,
    ) -> ExternalFunctionBinding:
        binding = ExternalFunctionBinding(
            declaration=declaration,
            library_name="",
            export_name="",
            calling_convention="winapi",
            params=(),
            return_type=None,
            is_void=bool(getattr(declaration, "is_sub", False)),
        )
        return self._ensure_external_function_binding(binding, context)

    def _ensure_external_function_binding(
        self,
        binding: ExternalFunctionBinding,
        context: ExecutionContext,
    ) -> ExternalFunctionBinding:
        if binding.resolved:
            return binding

        declaration = binding.declaration
        name = str(declaration.name).strip()
        if not name:
            raise RuntimeError(RuntimeErrorMessages.external_function_name_collision(name))

        library_name = str(declaration.library_name).strip()
        if not library_name:
            raise RuntimeError(RuntimeErrorMessages.external_function_library_name_empty())

        export_name = str(declaration.export_name).strip() if declaration.export_name is not None else name
        if not export_name:
            raise RuntimeError(RuntimeErrorMessages.external_function_alias_empty())

        calling_convention = self._normalize_external_calling_convention(
            getattr(declaration, "calling_convention", "winapi")
        )

        normalized_name = name.lower()
        existing_function_names = {existing.lower() for existing in context.functions}
        existing_struct_names = {existing.lower() for existing in context.structs}
        existing_record_names = {existing.lower() for existing in context.records}
        existing_enum_names = {existing.lower() for existing in context.enums}
        if (
            normalized_name in existing_function_names
            or normalized_name in existing_struct_names
            or normalized_name in existing_record_names
            or normalized_name in existing_enum_names
        ):
            raise RuntimeError(RuntimeErrorMessages.external_function_name_collision(name))
        existing_external_names = {existing.lower() for existing in context.external_functions}
        if normalized_name in existing_external_names:
            try:
                existing_binding = context.get_external_function(name)
            except RuntimeError:
                existing_binding = None
            if existing_binding is not binding:
                raise RuntimeError(RuntimeErrorMessages.external_function_name_collision(name))
        if calling_convention not in _EXTERNAL_CALLING_CONVENTIONS:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_unsupported_calling_convention(
                    calling_convention
                )
            )

        params: list[ExternalParameterInfo] = []
        seen_param_names: set[str] = set()
        for param in declaration.params:
            param_name = str(param.name).strip()
            if not param_name:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_duplicate_parameter(param_name)
                )
            normalized_param_name = param_name.lower()
            if normalized_param_name in seen_param_names:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_duplicate_parameter(param_name)
                )
            seen_param_names.add(normalized_param_name)

            if param.default is not None:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_parameter_default_disallowed(
                        param_name
                    )
                )

            type_info = self._resolve_external_type_info(param.type_name, context)
            params.append(
                ExternalParameterInfo(
                    name=param_name,
                    type_info=type_info,
                    is_byref=bool(param.is_byref),
                    is_byval=not bool(param.is_byref),
                    string_buffer_size=getattr(param, "string_buffer_size", None),
                )
            )

        return_type: ExternalTypeInfo | None = None
        if not binding.is_void:
            return_type = self._resolve_external_type_info(
                declaration.return_type_name,
                context,
                is_return_type=True,
            )

            if not return_type.is_return_eligible:
                if return_type.kind == "struct":
                    raise RuntimeError(
                        RuntimeErrorMessages.external_function_struct_return_not_supported(
                            return_type.name
                        )
                    )
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_type_not_allowed(
                        return_type.name
                    )
                )

        library_handle = self._load_external_library(library_name, calling_convention)
        function_handle = self._resolve_external_export(
            library_handle,
            export_name,
            library_name=library_name,
        )

        binding.library_name = library_name
        binding.export_name = export_name
        binding.calling_convention = calling_convention
        binding.params = tuple(params)
        binding.return_type = return_type
        binding.library_handle = library_handle
        binding.function_handle = function_handle
        self._configure_external_function_handle(binding)
        binding.resolved = True
        return binding

    def _validate_registered_external_function_definitions(self, context: ExecutionContext) -> None:
        for name, binding in list(context.external_functions.items()):
            resolved = self._ensure_external_function_binding(binding, context)
            context.external_functions[name] = resolved

    def _normalize_external_calling_convention(self, calling_convention: str | None) -> str:
        normalized = str(calling_convention or "winapi").strip().lower()
        if normalized == "default":
            return "winapi"
        return normalized or "winapi"

    @staticmethod
    def _align_up(value: int, alignment: int) -> int:
        if alignment <= 1:
            return value
        return ((value + alignment - 1) // alignment) * alignment

    def _resolve_external_type_info(
        self,
        type_name: str | None,
        context: ExecutionContext,
        *,
        is_return_type: bool = False,
    ) -> ExternalTypeInfo:
        normalized_name = normalize_type_name(type_name or "")
        if not normalized_name:
            raise RuntimeError(RuntimeErrorMessages.external_function_unknown_type(str(type_name or "")))

        if normalized_name == "String":
            pointer_size = max(1, struct.calcsize("P"))
            return ExternalTypeInfo(
                name="String",
                kind="builtin",
                native_type=ctypes.c_wchar_p,
                is_layout_safe=False,
                is_blittable=False,
                is_byref_eligible=True,
                is_return_eligible=True,
                size=pointer_size,
                alignment=pointer_size,
            )

        if context.has_enum(normalized_name):
            int32_policy = _EXTERNAL_BUILTIN_LAYOUT_POLICY["Int32"]
            native_type, size, alignment, is_layout_safe, is_blittable, is_byref_eligible, is_return_eligible = int32_policy
            return ExternalTypeInfo(
                name=normalized_name,
                kind="builtin",
                native_type=native_type,
                is_layout_safe=is_layout_safe,
                is_blittable=is_blittable,
                is_byref_eligible=is_byref_eligible,
                is_return_eligible=is_return_eligible,
                size=size,
                alignment=alignment,
            )

        builtin_policy = _EXTERNAL_BUILTIN_LAYOUT_POLICY.get(normalized_name)
        if builtin_policy is not None:
            native_type, size, alignment, is_layout_safe, is_blittable, is_byref_eligible, is_return_eligible = builtin_policy
            if not is_layout_safe or native_type is None or size is None or alignment is None:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_type_not_allowed(normalized_name)
                )
            return ExternalTypeInfo(
                name=normalized_name,
                kind="builtin",
                native_type=native_type,
                is_layout_safe=is_layout_safe,
                is_blittable=is_blittable,
                is_byref_eligible=is_byref_eligible,
                is_return_eligible=is_return_eligible,
                size=size,
                alignment=alignment,
            )

        if context.has_struct(normalized_name):
            summary = self._build_struct_layout_summary(normalized_name, context)
            if summary.cycle_path is not None:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_recursive_layout(summary.cycle_path)
                )
            if not summary.is_layout_safe or summary.ctypes_type is None:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_struct_not_layout_safe(normalized_name)
                )
            return ExternalTypeInfo(
                name=normalized_name,
                kind="struct",
                native_type=summary.ctypes_type,
                is_layout_safe=summary.is_layout_safe,
                is_blittable=summary.is_blittable,
                is_byref_eligible=True,
                is_return_eligible=(
                    summary.is_layout_safe
                    and summary.is_blittable
                    and summary.size is not None
                    and summary.size <= max(1, struct.calcsize("P"))
                ),
                size=summary.size,
                alignment=summary.alignment,
                struct_summary=summary,
            )

        raise RuntimeError(RuntimeErrorMessages.external_function_unknown_type(normalized_name))

    def _build_struct_layout_summary(
        self,
        struct_name: str,
        context: ExecutionContext,
    ) -> StructLayoutSummary:
        normalized_name = normalize_type_name(struct_name)
        if normalized_name in self._external_struct_layout_cache:
            return self._external_struct_layout_cache[normalized_name]

        if normalized_name in self._external_struct_layout_in_progress:
            cycle_start = self._external_struct_layout_stack.index(normalized_name)
            cycle_path = tuple(self._external_struct_layout_stack[cycle_start:] + [normalized_name])
            definition = context.get_struct(normalized_name)
            summary = StructLayoutSummary(
                name=normalized_name,
                is_layout_safe=False,
                is_blittable=False,
                size=None,
                alignment=None,
                packing=definition.packing,
                alignment_override=definition.alignment,
                cycle_path=cycle_path,
                rejection_reason="Recursive struct layout detected",
            )
            self._external_struct_layout_cache[normalized_name] = summary
            return summary

        self._external_struct_layout_in_progress.add(normalized_name)
        self._external_struct_layout_stack.append(normalized_name)
        try:
            definition = context.get_struct(normalized_name)
            field_layouts: list[tuple[str, Any]] = []
            field_names: list[str] = []
            field_offsets: list[int] = []
            field_sizes: list[int] = []
            field_alignments: list[int] = []
            field_blittable: list[bool] = []
            field_type_names: list[str] = []

            packing = definition.packing
            alignment_override = definition.alignment
            struct_alignment = 1
            offset = 0
            for field in definition.fields:
                field_type_name = normalize_type_name(field.type_name)
                field_type_names.append(field_type_name)
                type_info = self._resolve_external_type_info(field_type_name, context)
                if not type_info.is_layout_safe or type_info.native_type is None:
                    summary = StructLayoutSummary(
                        name=normalized_name,
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        rejection_reason=f"Field '{field.name}' uses non-layout-safe type '{field_type_name}'",
                    )
                    self._external_struct_layout_cache[normalized_name] = summary
                    return summary

                field_names.append(field.name)
                field_alignment = type_info.alignment or 1
                if packing is not None:
                    field_alignment = min(field_alignment, int(packing))
                field_layouts.append((field.name, type_info.native_type))
                offset = self._align_up(offset, field_alignment)
                field_offsets.append(offset)
                field_sizes.append(type_info.size or 0)
                field_alignments.append(field_alignment)
                field_blittable.append(type_info.is_blittable)
                struct_alignment = max(struct_alignment, field_alignment)
                offset += type_info.size or 0

            final_alignment = struct_alignment
            if packing is not None:
                final_alignment = min(final_alignment, int(packing))
            if alignment_override is not None and int(alignment_override) > struct_alignment:
                summary = StructLayoutSummary(
                    name=normalized_name,
                    is_layout_safe=False,
                    is_blittable=False,
                    size=None,
                    alignment=None,
                    packing=packing,
                    alignment_override=alignment_override,
                    field_offsets=tuple(field_offsets),
                    field_sizes=tuple(field_sizes),
                    field_alignments=tuple(field_alignments),
                    field_blittable=tuple(field_blittable),
                    field_type_names=tuple(field_type_names),
                    rejection_reason=(
                        "Struct alignment cannot be honored by the current runtime: "
                        f"Align({alignment_override})"
                    ),
                )
                self._external_struct_layout_cache[normalized_name] = summary
                return summary

            final_size = self._align_up(offset, final_alignment)

            struct_fields = tuple(field_layouts)
            struct_namespace = {
                "_fields_": struct_fields,
                "__module__": __name__,
            }
            if packing is not None:
                struct_namespace["_pack_"] = int(packing)
            struct_type = type(
                f"{normalized_name}Layout",
                (ctypes.Structure,),
                struct_namespace,
            )

            actual_alignment = ctypes.alignment(struct_type)
            actual_size = ctypes.sizeof(struct_type)
            if actual_alignment != final_alignment:
                summary = StructLayoutSummary(
                    name=normalized_name,
                    is_layout_safe=False,
                    is_blittable=False,
                    size=None,
                    alignment=None,
                    packing=packing,
                    alignment_override=alignment_override,
                    field_offsets=tuple(field_offsets),
                    field_sizes=tuple(field_sizes),
                    field_alignments=tuple(field_alignments),
                    field_blittable=tuple(field_blittable),
                    field_type_names=tuple(field_type_names),
                    rejection_reason=(
                        "Struct alignment cannot be honored by the current runtime: "
                        f"Align({alignment_override})"
                        if alignment_override is not None
                        else "Struct layout cannot be honored by the current runtime"
                    ),
                )
                self._external_struct_layout_cache[normalized_name] = summary
                return summary

            if actual_size > final_size:
                summary = StructLayoutSummary(
                    name=normalized_name,
                    is_layout_safe=False,
                    is_blittable=False,
                    size=None,
                    alignment=None,
                    packing=packing,
                    alignment_override=alignment_override,
                    field_offsets=tuple(field_offsets),
                    field_sizes=tuple(field_sizes),
                    field_alignments=tuple(field_alignments),
                    field_blittable=tuple(field_blittable),
                    field_type_names=tuple(field_type_names),
                    rejection_reason="Struct layout cannot be honored by the current runtime",
                )
                self._external_struct_layout_cache[normalized_name] = summary
                return summary

            if actual_size < final_size:
                padding_name = "_abi_tail_padding"
                while padding_name in field_names:
                    padding_name = f"{padding_name}_"
                struct_namespace["_fields_"] = struct_fields + (
                    (padding_name, ctypes.c_ubyte * (final_size - actual_size)),
                )
                struct_type = type(
                    f"{normalized_name}Layout",
                    (ctypes.Structure,),
                    struct_namespace,
                )
                actual_alignment = ctypes.alignment(struct_type)
                actual_size = ctypes.sizeof(struct_type)
                if actual_alignment != final_alignment or actual_size != final_size:
                    summary = StructLayoutSummary(
                        name=normalized_name,
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        rejection_reason=(
                            "Struct alignment cannot be honored by the current runtime: "
                            f"Align({alignment_override})"
                            if alignment_override is not None
                            else "Struct layout cannot be honored by the current runtime"
                        ),
                    )
                    self._external_struct_layout_cache[normalized_name] = summary
                    return summary

            summary = StructLayoutSummary(
                name=normalized_name,
                is_layout_safe=True,
                is_blittable=all(field_blittable),
                size=max(ctypes.sizeof(struct_type), final_size),
                alignment=final_alignment,
                packing=packing,
                alignment_override=alignment_override,
                field_offsets=tuple(getattr(struct_type, field.name).offset for field in definition.fields),
                field_sizes=tuple(field_sizes),
                field_alignments=tuple(field_alignments),
                field_blittable=tuple(field_blittable),
                field_type_names=tuple(field_type_names),
                ctypes_type=struct_type,
            )
            self._external_struct_layout_cache[normalized_name] = summary
            return summary
        finally:
            self._external_struct_layout_stack.pop()
            self._external_struct_layout_in_progress.remove(normalized_name)

    def _load_external_library(self, library_name: str, calling_convention: str) -> Any:
        cache_key = (calling_convention, library_name.lower().strip())
        if cache_key in self._dll_library_cache:
            return self._dll_library_cache[cache_key]

        loader: Any
        if calling_convention == "cdecl":
            loader = ctypes.CDLL
        else:
            loader = getattr(ctypes, "WinDLL", None) or ctypes.CDLL

        try:
            library_handle = loader(library_name)
        except OSError as exc:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_library_load_failed(library_name)
            ) from exc

        self._dll_library_cache[cache_key] = library_handle
        return library_handle

    def _resolve_external_export(
        self,
        library_handle: Any,
        export_name: str,
        *,
        library_name: str,
    ) -> Any:
        try:
            return getattr(library_handle, export_name)
        except AttributeError as exc:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_export_not_found(
                    export_name,
                    library_name,
                )
            ) from exc

    def _configure_external_function_handle(self, binding: ExternalFunctionBinding) -> None:
        if binding.function_handle is None:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_export_not_found(
                    binding.export_name,
                    binding.library_name,
                )
            )

        argtypes: list[Any] = []
        for param in binding.params:
            native_type = param.type_info.native_type
            if native_type is None:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_type_not_allowed(
                        param.type_info.name
                    )
                )
            if param.is_byref:
                if param.type_info.name == "String":
                    if param.string_buffer_size is None:
                        raise RuntimeError(
                            RuntimeErrorMessages.external_function_type_not_allowed(
                                param.type_info.name
                            )
                        )
                    argtypes.append(ctypes.POINTER(ctypes.c_wchar))
                else:
                    argtypes.append(ctypes.POINTER(native_type))
            else:
                argtypes.append(native_type)

        binding.function_handle.argtypes = argtypes
        binding.function_handle.restype = None if binding.is_void or binding.return_type is None else binding.return_type.native_type

    def _coerce_external_input_value(
        self,
        type_info: ExternalTypeInfo,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        if type_info.kind == "struct":
            return self._coerce_external_struct_value(type_info, value, context)
        if type_info.name == "String":
            return self._coerce_external_string_value(value)
        return self._coerce_external_scalar_value(type_info, value)

    def _coerce_external_string_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return str(value)
        raise RuntimeError(
            RuntimeErrorMessages.external_function_argument_type_mismatch(
                "String",
                "value",
                "String",
                self._describe_runtime_value_type(value),
            )
        )

    def _coerce_external_string_buffer(self, value: Any, capacity: int) -> Any:
        initial_text = ""
        if value is None:
            initial_text = ""
        elif isinstance(value, str):
            initial_text = value
        else:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    "String",
                    "value",
                    "String",
                    self._describe_runtime_value_type(value),
                )
            )

        requested_capacity = max(1, int(capacity))
        return ctypes.create_unicode_buffer(initial_text, max(requested_capacity, len(initial_text) + 1))

    def _coerce_external_scalar_value(self, type_info: ExternalTypeInfo, value: Any) -> Any:
        name = type_info.name
        if name in _STRUCT_BOOL_TYPE_NAMES:
            if isinstance(value, bool):
                return type_info.native_type(int(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name in _STRUCT_CHAR_TYPE_NAMES:
            if isinstance(value, str) and len(value) == 1:
                return type_info.native_type(ord(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name in _STRUCT_STRING_TYPE_NAMES:
            if value is None:
                return None
            if isinstance(value, str):
                return str(value)
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name in _STRUCT_FLOAT_TYPE_NAMES:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return type_info.native_type(float(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name in _STRUCT_INTEGER_TYPE_BOUNDS:
            if isinstance(value, int) and not isinstance(value, bool):
                minimum, maximum = _STRUCT_INTEGER_TYPE_BOUNDS[name]
                if minimum <= value <= maximum:
                    return type_info.native_type(int(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name == "Ptr":
            if value is None:
                return type_info.native_type(None)
            if isinstance(value, int) and not isinstance(value, bool):
                bits = self._pointer_bit_width()
                if 0 <= value <= (2**bits - 1):
                    return type_info.native_type(int(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )
        if name == "IntPtr":
            if value is None:
                return type_info.native_type(0)
            if isinstance(value, int) and not isinstance(value, bool):
                bits = self._pointer_bit_width()
                minimum = -(2 ** (bits - 1))
                maximum = 2 ** (bits - 1) - 1
                if minimum <= value <= maximum:
                    return type_info.native_type(int(value))
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    name,
                    "value",
                    name,
                    self._describe_runtime_value_type(value),
                )
            )

        raise RuntimeError(RuntimeErrorMessages.external_function_type_not_allowed(name))

    def _coerce_external_struct_value(
        self,
        type_info: ExternalTypeInfo,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        if not isinstance(value, StructInstance):
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_type_mismatch(
                    type_info.name,
                    "value",
                    type_info.name,
                    self._describe_runtime_value_type(value),
                )
            )

        summary = type_info.struct_summary
        if summary is None or summary.ctypes_type is None:
            summary = self._build_struct_layout_summary(type_info.name, context)

        field_values: list[Any] = []
        definition = context.get_struct(type_info.name)
        for field in definition.fields:
            field_value = value.get_field(field.name)
            field_type_info = self._resolve_external_type_info(field.type_name, context)
            field_values.append(self._coerce_external_input_value(field_type_info, field_value, context))

        return summary.ctypes_type(*field_values)

    def _convert_external_return_value(
        self,
        type_info: ExternalTypeInfo | None,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        if type_info is None:
            return None
        if type_info.kind == "struct":
            return self._convert_external_struct_return_value(type_info, value, context)
        return self._convert_external_scalar_return_value(type_info, value)

    def _convert_external_scalar_return_value(self, type_info: ExternalTypeInfo, value: Any) -> Any:
        if hasattr(value, "value"):
            value = value.value
        name = type_info.name
        if name in _STRUCT_STRING_TYPE_NAMES:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            return str(value)
        if name in _STRUCT_BOOL_TYPE_NAMES:
            return bool(value)
        if name in _STRUCT_CHAR_TYPE_NAMES:
            return chr(int(value) & 0xFFFF)
        if name == "Ptr":
            if value is None:
                return 0
            return int(value)
        if name == "IntPtr":
            if value is None:
                return 0
            return int(value)
        if name in _STRUCT_FLOAT_TYPE_NAMES:
            return float(value)
        if name in _STRUCT_INTEGER_TYPE_BOUNDS:
            return int(value)
        raise RuntimeError(RuntimeErrorMessages.external_function_type_not_allowed(name))

    def _convert_external_struct_return_value(
        self,
        type_info: ExternalTypeInfo,
        value: Any,
        context: ExecutionContext,
    ) -> StructInstance:
        if not isinstance(value, type_info.native_type):
            # ctypes may return a compatible instance or a plain object depending on ABI.
            if hasattr(value, "_fields_"):
                native_value = value
            else:
                raise RuntimeError(
                    RuntimeErrorMessages.external_function_struct_not_layout_safe(type_info.name)
                )
        else:
            native_value = value

        definition = context.get_struct(type_info.name)
        resolved_values: list[Any] = []
        for field in definition.fields:
            field_type_info = self._resolve_external_type_info(field.type_name, context)
            field_native_value = getattr(native_value, field.name)
            resolved_values.append(
                self._convert_external_native_field_value(field_type_info, field_native_value, context)
            )
        return build_struct_instance(definition, resolved_values)

    def _convert_external_native_field_value(
        self,
        type_info: ExternalTypeInfo,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        if type_info.kind == "struct":
            return self._convert_external_struct_return_value(type_info, value, context)
        return self._convert_external_scalar_return_value(type_info, value)

    def _execute_external_function_call(
        self,
        function_name: str,
        call_expr: ast.CallExpr,
        context: ExecutionContext,
    ) -> Any:
        binding = context.get_external_function(function_name)
        self._ensure_external_function_binding(binding, context)
        expected_argument_count = len(binding.params)
        actual_argument_count = len(call_expr.args)
        if actual_argument_count != expected_argument_count:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_argument_count_mismatch(
                    function_name,
                    expected_argument_count,
                    actual_argument_count,
                )
            )

        debugger = self._get_debugger(context)
        if debugger is not None:
            on_function_call = getattr(debugger, "on_function_call", None)
            if callable(on_function_call):
                on_function_call(function_name, context)

        prepared_arguments: list[Any] = []
        writeback_targets: list[tuple[Any, ExternalParameterInfo, Any]] = []
        try:
            for param, arg_expr in zip(binding.params, call_expr.args):
                if param.is_byref:
                    reference = self._resolve_byref_reference(arg_expr, context, param.name)
                    current_value = reference.get()
                    if param.type_info.name == "String":
                        buffer_capacity = int(param.string_buffer_size or _EXTERNAL_STRING_BUFFER_CAPACITY)
                        native_value = self._coerce_external_string_buffer(
                            current_value,
                            buffer_capacity,
                        )
                        prepared_arguments.append(
                            ctypes.cast(native_value, ctypes.POINTER(ctypes.c_wchar))
                        )
                    else:
                        native_value = self._coerce_external_input_value(
                            param.type_info,
                            current_value,
                            context,
                        )
                        prepared_arguments.append(ctypes.byref(native_value))
                    writeback_targets.append((reference, param, native_value))
                else:
                    evaluated_value = self._evaluate_expression(arg_expr, context)
                    prepared_arguments.append(
                        self._coerce_external_input_value(param.type_info, evaluated_value, context)
                    )

            result = binding.function_handle(*prepared_arguments)
            for reference, param, native_value in writeback_targets:
                reference.set(
                    self._convert_external_native_field_value(
                        param.type_info,
                        native_value,
                        context,
                    )
                )
            converted_result = self._convert_external_return_value(
                binding.return_type,
                result,
                context,
            )
        except BaseException as exc:
            if debugger is not None:
                on_exception = getattr(debugger, "on_exception", None)
                if callable(on_exception):
                    on_exception(exc, call_expr, context)
            raise

        if debugger is not None:
            on_function_return = getattr(debugger, "on_function_return", None)
            if callable(on_function_return):
                on_function_return(function_name, converted_result, context)
        return converted_result

    def _validate_struct_field_value(
        self,
        struct_name: str,
        field: StructFieldDefinition,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        expected_type_name = normalize_type_name(field.type_name)
        if not expected_type_name:
            raise RuntimeError(
                RuntimeErrorMessages.struct_field_type_not_defined(
                    struct_name,
                    field.name,
                    field.type_name,
                )
            )

        actual_type_name = self._describe_runtime_value_type(value)
        if expected_type_name in _STRUCT_BOOL_TYPE_NAMES:
            if isinstance(value, bool):
                return value
        elif expected_type_name in _STRUCT_CHAR_TYPE_NAMES:
            if isinstance(value, str) and len(value) == 1:
                return value
        elif expected_type_name in _STRUCT_STRING_TYPE_NAMES:
            if isinstance(value, str):
                return value
        elif expected_type_name in _STRUCT_FLOAT_TYPE_NAMES:
            if isinstance(value, float):
                return value
        elif expected_type_name in _STRUCT_INTEGER_TYPE_BOUNDS or context.has_enum(expected_type_name):
            if isinstance(value, int) and not isinstance(value, bool):
                minimum, maximum = _STRUCT_INTEGER_TYPE_BOUNDS.get(
                    expected_type_name,
                    _STRUCT_INTEGER_TYPE_BOUNDS["Int32"],
                )
                if minimum <= value <= maximum:
                    return value
        elif expected_type_name in _STRUCT_POINTER_TYPE_NAMES:
            if isinstance(value, int) and not isinstance(value, bool):
                bits = self._pointer_bit_width()
                if expected_type_name == "Ptr":
                    if 0 <= value <= (2**bits - 1):
                        return value
                else:
                    minimum = -(2 ** (bits - 1))
                    maximum = 2 ** (bits - 1) - 1
                    if minimum <= value <= maximum:
                        return value
        elif context.has_struct(expected_type_name):
            if isinstance(value, StructInstance) and value.struct_name == expected_type_name:
                return value
        else:
            raise RuntimeError(
                RuntimeErrorMessages.struct_field_type_not_defined(
                    struct_name,
                    field.name,
                    expected_type_name,
                )
            )

        raise RuntimeError(
            RuntimeErrorMessages.struct_field_type_mismatch(
                struct_name,
                field.name,
                expected_type_name,
                actual_type_name,
            )
        )

    def _validate_record_field_value(
        self,
        record_name: str,
        field: StructFieldDefinition,
        value: Any,
        context: ExecutionContext,
    ) -> Any:
        expected_type_name = normalize_type_name(field.type_name)
        if not expected_type_name:
            raise RuntimeError(
                RuntimeErrorMessages.record_field_type_not_defined(
                    record_name,
                    field.name,
                    field.type_name,
                )
            )

        actual_type_name = self._describe_runtime_value_type(value)
        if expected_type_name in _STRUCT_BOOL_TYPE_NAMES:
            if isinstance(value, bool):
                return value
        elif expected_type_name in _STRUCT_CHAR_TYPE_NAMES:
            if isinstance(value, str) and len(value) == 1:
                return value
        elif expected_type_name in _STRUCT_STRING_TYPE_NAMES:
            if isinstance(value, str):
                return value
        elif expected_type_name in _STRUCT_FLOAT_TYPE_NAMES:
            if isinstance(value, float):
                return value
        elif expected_type_name in _STRUCT_INTEGER_TYPE_BOUNDS or context.has_enum(expected_type_name):
            if isinstance(value, int) and not isinstance(value, bool):
                minimum, maximum = _STRUCT_INTEGER_TYPE_BOUNDS.get(
                    expected_type_name,
                    _STRUCT_INTEGER_TYPE_BOUNDS["Int32"],
                )
                if minimum <= value <= maximum:
                    return value
        elif expected_type_name in _STRUCT_POINTER_TYPE_NAMES:
            if isinstance(value, int) and not isinstance(value, bool):
                bits = self._pointer_bit_width()
                if expected_type_name == "Ptr":
                    if 0 <= value <= (2**bits - 1):
                        return value
                else:
                    minimum = -(2 ** (bits - 1))
                    maximum = 2 ** (bits - 1) - 1
                    if minimum <= value <= maximum:
                        return value
        elif context.has_record(expected_type_name):
            if isinstance(value, RecordInstance) and value.record_name == expected_type_name:
                return value
        elif context.has_struct(expected_type_name):
            if isinstance(value, StructInstance) and value.struct_name == expected_type_name:
                return value
        else:
            raise RuntimeError(
                RuntimeErrorMessages.record_field_type_not_defined(
                    record_name,
                    field.name,
                    expected_type_name,
                )
            )

        raise RuntimeError(
            RuntimeErrorMessages.record_field_type_mismatch(
                record_name,
                field.name,
                expected_type_name,
                actual_type_name,
            )
        )

    def _pointer_bit_width(self) -> int:
        return max(1, 8 * struct.calcsize("P"))

    def _describe_runtime_value_type(self, value: Any) -> str:
        if value is None:
            return "Null"
        if isinstance(value, StructInstance):
            return f"Struct<{value.struct_name}>"
        if isinstance(value, RecordInstance):
            return f"Record<{value.record_name}>"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, int):
            return "Int"
        if isinstance(value, float):
            return "Float"
        if isinstance(value, str):
            return "String"
        if isinstance(value, list):
            return "Array"
        if isinstance(value, tuple):
            return "Tuple"
        if isinstance(value, dict):
            return "Dictionary"
        return type(value).__name__


    def _build_struct_definition(self, statement: ast.StructDecl) -> StructDefinition:
        return StructDefinition(
            name=statement.name,
            fields=tuple(
                StructFieldDefinition(
                    name=field.name,
                    type_name=field.type_name,
                    initializer=field.initializer,
                )
                for field in statement.fields
            ),
            packing=statement.packing,
            alignment=statement.alignment,
        )

    def _build_tm_struct_definition(self) -> StructDefinition:
        return StructDefinition(
            name="tm",
            fields=(
                StructFieldDefinition(name="tm_sec", type_name="Int32"),
                StructFieldDefinition(name="tm_min", type_name="Int32"),
                StructFieldDefinition(name="tm_hour", type_name="Int32"),
                StructFieldDefinition(name="tm_mday", type_name="Int32"),
                StructFieldDefinition(name="tm_mon", type_name="Int32"),
                StructFieldDefinition(name="tm_year", type_name="Int32"),
                StructFieldDefinition(name="tm_wday", type_name="Int32"),
                StructFieldDefinition(name="tm_yday", type_name="Int32"),
                StructFieldDefinition(name="tm_isdst", type_name="Bool"),
            ),
        )

    def _build_record_definition(self, statement: ast.RecordDecl) -> RecordDefinition:
        return RecordDefinition(
            name=statement.name,
            fields=tuple(
                StructFieldDefinition(
                    name=field.name,
                    type_name=field.type_name,
                    initializer=field.initializer,
                )
                for field in statement.fields
            ),
        )

    def _execute_var_decl(self, statement: ast.VarDecl, context: ExecutionContext) -> None:
        for declarator in statement.declarators:
            value = self._evaluate_expression(declarator.initializer, context)
            context.set_variable(declarator.name, value)

    def _execute_redim_decl(self, statement: ast.Statement, context: ExecutionContext) -> None:
        raise RuntimeError(
            RuntimeErrorMessages.unsupported_statement(
                "runtime execution",
                statement.kind,
            )
        )

    def _execute_const_decl(self, statement: ast.ConstDecl, context: ExecutionContext) -> None:
        for declarator in statement.declarators:
            value = self._evaluate_expression(declarator.initializer, context)
            context.set_constant(declarator.name, value)

    def _execute_return_statement(
        self,
        statement: ast.ReturnStatement,
        context: ExecutionContext,
    ) -> None:
        if not context.in_function_scope():
            raise RuntimeError(RuntimeErrorMessages.return_outside_function())
        value = self._evaluate_expression(statement.value, context)
        raise _ReturnSignal(value)

    def _execute_exit_statement(self, statement: ast.ExitStatement, context: ExecutionContext) -> None:
        target = self._normalize_loop_target(statement.target)
        if target is None and not context.call_stack:
            raise RuntimeError(self._outside_loop_error_message("Exit", statement.target))
        raise _LoopExitSignal(target)

    def _execute_script_quit_statement(
        self,
        statement: ast.ScriptQuitStatement,
        context: ExecutionContext,
    ) -> None:
        value = self._evaluate_expression(statement.value, context)
        raise _ScriptQuitSignal(self._coerce_script_exit_code(value))

    def _execute_continue_statement(
        self,
        statement: ast.ContinueStatement,
        context: ExecutionContext,
    ) -> None:
        target = self._normalize_loop_target(statement.target)
        if target is None:
            if not self._loop_stack:
                raise RuntimeError(self._outside_loop_error_message("Continue", statement.target))
            raise _LoopContinueSignal(target)
        if target == "loop":
            if not self._loop_stack:
                raise RuntimeError(self._outside_loop_error_message("Continue", statement.target))
            raise _LoopContinueSignal(target)
        if target not in self._loop_stack:
            raise RuntimeError(self._outside_loop_error_message("Continue", statement.target))
        raise _LoopContinueSignal(target)

    def _execute_assignment(self, statement: ast.Assignment, context: ExecutionContext) -> None:
        reference = self._resolve_writable_reference(statement.target, context)
        value = clone_runtime_value(self._evaluate_expression(statement.value, context))
        if hasattr(reference, "set") and callable(reference.set):
            reference.set(value)
            return
        raise RuntimeError(
            RuntimeErrorMessages.assignment_target_not_writable(
                self._describe_assignment_target(statement.target)
            )
        )

    def _execute_expression_statement(
        self,
        statement: ast.ExpressionStatement,
        context: ExecutionContext,
    ) -> None:
        self._evaluate_expression(statement.expression, context)

    def _execute_if_statement(
        self,
        statement: ast.IfStatement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        if self._evaluate_expression(statement.condition, context):
            then_ancestry = ancestry + (self._structured_block_segment("then", statement),)
            self._execute_block(
                statement.then_branch.statements,
                context,
                scope_id="if",
                scope_labels=self._collect_scope_labels(
                    statement.then_branch.statements,
                    "if",
                    then_ancestry,
                ),
                ancestry=then_ancestry,
            )
            return

        if statement.else_branch is None:
            return

        nested = self._extract_nested_elseif_statement(statement.else_branch)
        if nested is not None:
            else_ancestry = ancestry + (self._structured_block_segment("else", statement),)
            self._execute_if_statement(
                nested,
                context,
                scope_id="else",
                scope_labels=self._collect_scope_labels(
                    statement.else_branch.statements,
                    "else",
                    else_ancestry,
                ),
                ancestry=else_ancestry,
            )
            return

        else_ancestry = ancestry + (self._structured_block_segment("else", statement),)
        self._execute_block(
            statement.else_branch.statements,
            context,
            scope_id="else",
            scope_labels=self._collect_scope_labels(
                statement.else_branch.statements,
                "else",
                else_ancestry,
            ),
            ancestry=else_ancestry,
        )

    def _execute_select_statement(
        self,
        statement: ast.SelectStatement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        select_value = self._evaluate_expression(statement.expression, context)
        select_ancestry = ancestry + (self._structured_block_segment("select", statement),)

        for case_index, case_arm in enumerate(statement.cases):
            case_ancestry = select_ancestry + (self._structured_case_segment(case_index, case_arm),)
            if case_arm.is_else or self._select_case_matches(select_value, case_arm, context):
                self._execute_block(
                    case_arm.body.statements,
                    context,
                    scope_id="select",
                    scope_labels=self._collect_scope_labels(
                        case_arm.body.statements,
                        "select",
                        case_ancestry,
                    ),
                    ancestry=case_ancestry,
                )
                return

    def _execute_for_statement(
        self,
        statement: ast.ForStatement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        if not isinstance(statement.variable, ast.Identifier):
            raise RuntimeError(RuntimeErrorMessages.FOR_LOOP_VARIABLE_MUST_BE_IDENTIFIER)

        start = self._evaluate_expression(statement.start, context)
        stop = self._evaluate_expression(statement.stop, context)
        step = self._evaluate_expression(statement.step, context) if statement.step is not None else 1

        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.FOR_LOOP_START_MUST_BE_INTEGER)
        if isinstance(stop, bool) or not isinstance(stop, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.FOR_LOOP_STOP_MUST_BE_INTEGER)
        if isinstance(step, bool) or not isinstance(step, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.FOR_LOOP_STEP_MUST_BE_INTEGER)

        start_i = int(start)
        stop_i = int(stop)
        step_i = int(step)
        if step_i == 0:
            raise RuntimeError(RuntimeErrorMessages.FOR_LOOP_STEP_MUST_NOT_BE_ZERO)

        loop_name = statement.variable.name
        current = start_i
        iteration = 0
        body_ancestry = ancestry + (self._structured_block_segment("for", statement),)
        self._loop_stack.append("for")
        self._active_loop_depth += 1
        try:
            while (current <= stop_i) if step_i > 0 else (current >= stop_i):
                self._guard_loop_iteration("For", iteration)
                context.set_variable(loop_name, current)
                try:
                    self._execute_block(
                        statement.body.statements,
                        context,
                        scope_id="for",
                        scope_labels=self._collect_scope_labels(
                            statement.body.statements,
                            "for",
                            body_ancestry,
                        ),
                        ancestry=body_ancestry,
                    )
                except _LoopContinueSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "for"):
                        iteration += 1
                        current += step_i
                        continue
                    raise
                except _LoopExitSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "for"):
                        break
                    raise
                iteration += 1
                current += step_i
        finally:
            self._active_loop_depth -= 1
            self._loop_stack.pop()

    def _execute_while_statement(
        self,
        statement: ast.WhileStatement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        iteration = 0
        body_ancestry = ancestry + (self._structured_block_segment("while", statement),)
        self._loop_stack.append("while")
        self._active_loop_depth += 1
        try:
            while self._evaluate_expression(statement.condition, context):
                self._guard_loop_iteration("While", iteration)
                try:
                    self._execute_block(
                        statement.body.statements,
                        context,
                        scope_id="while",
                        scope_labels=self._collect_scope_labels(
                            statement.body.statements,
                            "while",
                            body_ancestry,
                        ),
                        ancestry=body_ancestry,
                    )
                except _LoopContinueSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "while"):
                        iteration += 1
                        continue
                    raise
                except _LoopExitSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "while"):
                        break
                    raise
                iteration += 1
        finally:
            self._active_loop_depth -= 1
            self._loop_stack.pop()

    def _execute_loop_statement(
        self,
        statement: ast.LoopStatement,
        context: ExecutionContext,
        *,
        scope_id: str,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
    ) -> None:
        iteration = 0
        body_ancestry = ancestry + (self._structured_block_segment("loop", statement),)
        self._loop_stack.append("loop")
        self._active_loop_depth += 1
        try:
            if statement.is_until:
                while True:
                    self._guard_loop_iteration("Do", iteration)
                    try:
                        self._execute_block(
                            statement.body.statements,
                            context,
                            scope_id="loop",
                            scope_labels=self._collect_scope_labels(
                                statement.body.statements,
                                "loop",
                                body_ancestry,
                            ),
                            ancestry=body_ancestry,
                        )
                    except _LoopContinueSignal as signal:
                        if not self._signal_applies_to_loop(signal.target, "loop"):
                            raise
                    except _LoopExitSignal as signal:
                        if self._signal_applies_to_loop(signal.target, "loop"):
                            break
                        raise
                    iteration += 1
                    if self._evaluate_expression(statement.condition, context):
                        break
                return

            while self._evaluate_expression(statement.condition, context):
                self._guard_loop_iteration("Do", iteration)
                try:
                    self._execute_block(
                        statement.body.statements,
                        context,
                        scope_id="loop",
                        scope_labels=self._collect_scope_labels(
                            statement.body.statements,
                            "loop",
                            body_ancestry,
                        ),
                        ancestry=body_ancestry,
                    )
                except _LoopContinueSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "loop"):
                        iteration += 1
                        continue
                    raise
                except _LoopExitSignal as signal:
                    if self._signal_applies_to_loop(signal.target, "loop"):
                        break
                    raise
                iteration += 1
        finally:
            self._active_loop_depth -= 1
            self._loop_stack.pop()

    def _execute_goto_statement(
        self,
        statement: ast.GotoStatement,
        context: ExecutionContext,
        *,
        ancestry: tuple[str, ...],
    ) -> None:
        _ = context
        raise _GotoSignal(statement.label, statement, ancestry)

    def _execute_label_statement(self, statement: ast.LabelStatement, context: ExecutionContext) -> None:
        _ = statement
        _ = context

    def _evaluate_expression(
        self,
        expression: ast.Expression | None,
        context: ExecutionContext,
    ) -> Any:
        if expression is None:
            return None

        expression = self._unwrap_parens(expression)

        if isinstance(expression, ast.IntegerLiteral):
            return int(expression.value)
        if isinstance(expression, ast.FloatLiteral):
            return float(expression.value)
        if isinstance(expression, ast.StringLiteral):
            return str(expression.value)
        if isinstance(expression, ast.BooleanLiteral):
            return bool(expression.value)
        if isinstance(expression, ast.NullLiteral):
            return None
        if isinstance(expression, ast.Identifier):
            try:
                return context.get_variable(expression.name)
            except RuntimeError:
                if context.has_function(expression.name):
                    return context.get_function(expression.name)
                try:
                    return context.resolve_host_identifier(expression.name)
                except RuntimeError:
                    pass
                raise
        if isinstance(expression, ast.HostIdentifier):
            return context.resolve_host_identifier(expression.name)
        if isinstance(expression, ast.ArrayLiteral):
            return [self._evaluate_expression(item, context) for item in expression.items]
        if isinstance(expression, ast.InterpolatedStringLiteral):
            return self._evaluate_interpolated_string(expression, context)
        if isinstance(expression, ast.UnaryExpr):
            return self._evaluate_unary_expression(expression, context)
        if isinstance(expression, ast.BinaryExpr):
            return self._evaluate_binary_expression(expression, context)
        if isinstance(expression, ast.TernaryExpr):
            return self._evaluate_ternary_expression(expression, context)
        if isinstance(expression, ast.CallExpr):
            return self._evaluate_call_expression(expression, context)
        if isinstance(expression, ast.IndexExpr):
            reference = self._resolve_index_reference(
                expression,
                context,
                require_writable_base=False,
            )
            if hasattr(reference, "get") and callable(reference.get):
                return reference.get()
            return reference
        raise RuntimeError(
            RuntimeErrorMessages.unsupported_expression_type(
                "runtime execution",
                expression.kind,
            )
        )

    def _evaluate_interpolated_string(
        self,
        expression: ast.InterpolatedStringLiteral,
        context: ExecutionContext,
    ) -> str:
        parts: list[str] = []
        for part in expression.parts:
            if isinstance(part, ast.InterpolatedTextPart):
                parts.append(part.value)
            elif isinstance(part, ast.InterpolationPart):
                value = self._evaluate_expression(part.expression, context)
                parts.append(self._format_interpolated_value(value, part.format_spec))
        return "".join(parts)

    def _format_interpolated_value(self, value: Any, format_spec: str | None) -> str:
        if format_spec is None or not str(format_spec).strip():
            return self._stringify_interpolated_value(value)

        spec = str(format_spec).strip().lower()
        if spec in {"d", "i"}:
            return str(self._coerce_interpolation_integer(value, spec))
        if spec in {"f", "n"}:
            return str(self._coerce_interpolation_numeric(value, spec))
        raise RuntimeError(RuntimeErrorMessages.unknown_format_specifier(spec))

    def _stringify_interpolated_value(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _coerce_interpolation_integer(self, value: Any, format_spec: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(
                RuntimeErrorMessages.format_specifier_requires_integer(
                    format_spec,
                    type(value).__name__,
                )
            )
        return int(value)

    def _coerce_script_exit_code(self, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.script_quit_exit_code_must_be_integer())
        exit_code = int(value)
        if exit_code < -2_147_483_648 or exit_code > 2_147_483_647:
            raise RuntimeError(RuntimeErrorMessages.script_quit_exit_code_out_of_range())
        return exit_code

    def _coerce_interpolation_numeric(self, value: Any, format_spec: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(
                RuntimeErrorMessages.format_specifier_requires_numeric(
                    format_spec,
                    type(value).__name__,
                )
            )
        return float(value)

    def _evaluate_call_expression(self, expression: ast.CallExpr, context: ExecutionContext) -> Any:
        callee = self._unwrap_parens(expression.callee)
        if not isinstance(callee, ast.Identifier):
            raise RuntimeError(
                RuntimeErrorMessages.unsupported_expression_type(
                    "runtime execution",
                    callee.kind if callee is not None else "<missing>",
                )
            )

        function_name = str(callee.name).strip()
        normalized_name = function_name.lower()
        debugger = self._get_debugger(context)

        if context.has_function(function_name):
            function_decl = context.get_function(function_name)
            return self._execute_user_function_call(function_decl, expression, context)

        if context.has_external_function(function_name):
            return self._execute_external_function_call(function_name, expression, context)

        arguments = [self._evaluate_expression(arg, context) for arg in expression.args]

        if normalized_name in _HOST_INTERACTION_BUILTIN_NAMES:
            if debugger is not None:
                on_function_call = getattr(debugger, "on_function_call", None)
                if callable(on_function_call):
                    on_function_call(function_name, context)

            try:
                result = self._execute_builtin_call(normalized_name, arguments, context)
            except BaseException as exc:
                if debugger is not None:
                    on_exception = getattr(debugger, "on_exception", None)
                    if callable(on_exception):
                        on_exception(exc, expression, context)
                raise

            if debugger is not None:
                on_function_return = getattr(debugger, "on_function_return", None)
                if callable(on_function_return):
                    on_function_return(function_name, result, context)
            return result

        if normalized_name in BUILTIN_FUNCTION_NAMES or context.has_host_service(function_name):
            if debugger is not None:
                on_function_call = getattr(debugger, "on_function_call", None)
                if callable(on_function_call):
                    on_function_call(function_name, context)

            try:
                if context.has_host_service(function_name):
                    result = context.call_host_service(function_name, *arguments)
                else:
                    result = self._execute_builtin_call(normalized_name, arguments, context)
            except BaseException as exc:
                if debugger is not None:
                    on_exception = getattr(debugger, "on_exception", None)
                    if callable(on_exception):
                        on_exception(exc, expression, context)
                raise

            if debugger is not None:
                on_function_return = getattr(debugger, "on_function_return", None)
                if callable(on_function_return):
                    on_function_return(function_name, result, context)
            return result

        if context.has_struct(function_name):
            return self._execute_struct_constructor(function_name, arguments, context)

        if context.has_record(function_name):
            return self._execute_record_constructor(function_name, arguments, context)

        raise RuntimeError(RuntimeErrorMessages.unsupported_function(function_name))

    def _execute_struct_constructor(
        self,
        struct_name: str,
        arguments: list[Any],
        context: ExecutionContext,
    ) -> StructInstance:
        definition = context.get_struct(struct_name)
        field_count = len(definition.fields)
        if len(arguments) > field_count:
            raise RuntimeError(
                RuntimeErrorMessages.struct_constructor_argument_count_mismatch(
                    struct_name,
                    field_count,
                    len(arguments),
                )
            )

        resolved_values: list[Any] = []
        for index, field in enumerate(definition.fields):
            if index < len(arguments):
                resolved_value = self._validate_struct_field_value(
                    struct_name,
                    field,
                    arguments[index],
                    context,
                )
                resolved_values.append(clone_runtime_value(resolved_value))
                continue

            if field.initializer is not None:
                initializer_value = self._evaluate_expression(field.initializer, context)
                resolved_value = self._validate_struct_field_value(
                    struct_name,
                    field,
                    initializer_value,
                    context,
                )
                resolved_values.append(clone_runtime_value(resolved_value))
                continue

            raise RuntimeError(
                RuntimeErrorMessages.struct_constructor_missing_required_field(
                    struct_name,
                    field.name,
                )
            )

        return build_struct_instance(definition, resolved_values)

    def _execute_record_constructor(
        self,
        record_name: str,
        arguments: list[Any],
        context: ExecutionContext,
    ) -> RecordInstance:
        definition = context.get_record(record_name)
        field_count = len(definition.fields)
        if len(arguments) > field_count:
            raise RuntimeError(
                RuntimeErrorMessages.record_constructor_argument_count_mismatch(
                    record_name,
                    field_count,
                    len(arguments),
                )
            )

        resolved_values: list[Any] = []
        for index, field in enumerate(definition.fields):
            if index < len(arguments):
                resolved_value = self._validate_record_field_value(
                    record_name,
                    field,
                    arguments[index],
                    context,
                )
                resolved_values.append(clone_runtime_value(resolved_value))
                continue

            if field.initializer is not None:
                initializer_value = self._evaluate_expression(field.initializer, context)
                resolved_value = self._validate_record_field_value(
                    record_name,
                    field,
                    initializer_value,
                    context,
                )
                resolved_values.append(clone_runtime_value(resolved_value))
                continue

            raise RuntimeError(
                RuntimeErrorMessages.record_constructor_missing_required_field(
                    record_name,
                    field.name,
                )
            )

        return build_record_instance(definition, resolved_values)

    def _execute_user_function_call(
        self,
        function_decl: ast.FunctionDecl,
        call_expr: ast.CallExpr,
        context: ExecutionContext,
    ) -> Any:
        context.enforce_call_depth_limit()

        locals_dict: dict[str, Any] = {}
        byref_bindings: dict[str, Any] = {}
        arguments: dict[str, Any] = {}

        for index, param in enumerate(function_decl.params):
            arg_expr = call_expr.args[index] if index < len(call_expr.args) else None
            if arg_expr is None and param.default is None:
                raise RuntimeError(
                    self._function_missing_required_argument_message(
                        function_decl.name,
                        param.name,
                    )
                )

            if param.is_byref:
                reference = self._resolve_byref_reference(arg_expr, context, param.name)
                byref_bindings[param.name] = reference
                try:
                    locals_dict[param.name] = reference.get()
                except Exception:
                    locals_dict[param.name] = None
                arguments[param.name] = locals_dict[param.name]
                continue

            value = (
                self._evaluate_expression(arg_expr, context)
                if arg_expr is not None
                else self._evaluate_expression(param.default, context)
            )
            locals_dict[param.name] = clone_runtime_value(value)
            arguments[param.name] = clone_runtime_value(value)

        context.push_call_frame(
            function_decl.name,
            locals_dict,
            byref_bindings=byref_bindings,
            node=function_decl,
            arguments=arguments,
            line=self._get_node_line(function_decl),
        )

        try:
            self._execute_block(
                function_decl.body.statements,
                context,
                scope_id=function_decl.name,
                scope_labels=self._collect_scope_labels(
                    function_decl.body.statements,
                    function_decl.name,
                    (function_decl.name.lower(),),
                ),
                ancestry=(function_decl.name.lower(),),
            )
        except _ReturnSignal as signal:
            value = clone_runtime_value(signal.value)
            context.pop_call_frame(value)
            return value
        except BaseException:
            context.call_stack.pop()
            raise

        frame = context.current_frame()
        implicit_return = None
        if frame is not None and function_decl.name in frame.locals:
            implicit_return = frame.locals[function_decl.name]
        implicit_return = clone_runtime_value(implicit_return)
        context.pop_call_frame(implicit_return)
        return implicit_return

    def _evaluate_unary_expression(self, expression: ast.UnaryExpr, context: ExecutionContext) -> Any:
        operator = expression.operator.upper()
        if operator in {"++", "--"}:
            return self._evaluate_increment_decrement_expression(expression, context)

        operand = self._evaluate_expression(expression.operand, context)
        if operator == "+":
            return +operand
        if operator == "-":
            return -operand
        if operator == "NOT":
            return not bool(operand)
        raise RuntimeError(RuntimeErrorMessages.unsupported_unary_operator("runtime execution", operator))

    def _evaluate_increment_decrement_expression(
        self,
        expression: ast.UnaryExpr,
        context: ExecutionContext,
    ) -> Any:
        reference = self._resolve_writable_reference(expression.operand, context)
        current = reference.get() if hasattr(reference, "get") and callable(reference.get) else None
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.UNARY_OPERATOR_REQUIRES_NUMERIC_OPERAND)

        updated = current + 1 if expression.operator == "++" else current - 1
        if hasattr(reference, "set") and callable(reference.set):
            reference.set(updated)
        else:
            raise RuntimeError(
                RuntimeErrorMessages.assignment_target_not_writable(
                    self._describe_assignment_target(expression.operand)
                )
            )
        return updated if not expression.is_postfix else current

    def _evaluate_binary_expression(self, expression: ast.BinaryExpr, context: ExecutionContext) -> Any:
        left = self._evaluate_expression(expression.left, context)
        operator = expression.operator.upper()

        if operator == "AND":
            return bool(left) and bool(self._evaluate_expression(expression.right, context))
        if operator == "OR":
            return bool(left) or bool(self._evaluate_expression(expression.right, context))
        if operator == ".":
            attribute = expression.right.name if isinstance(expression.right, ast.Identifier) else str(expression.right)
            if isinstance(left, StructInstance):
                return left.get_field(attribute)
            if isinstance(left, RecordInstance):
                return left.get_field(attribute)
            if isinstance(left, dict) and attribute in left:
                return left[attribute]
            if isinstance(left, dict):
                normalized_attribute = attribute.lower()
                for key, value in left.items():
                    if isinstance(key, str) and key.lower() == normalized_attribute:
                        return value
            return getattr(left, attribute)

        right = self._evaluate_expression(expression.right, context)

        if operator == "+":
            if isinstance(left, str) or isinstance(right, str):
                return f"{self._stringify_interpolated_value(left)}{self._stringify_interpolated_value(right)}"
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            return left / right
        if operator == "%":
            return left % right
        if operator == "==":
            return left == right
        if operator == "<>":
            return left != right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        if operator == "&":
            return f"{self._stringify_interpolated_value(left)}{self._stringify_interpolated_value(right)}"

        raise RuntimeError(RuntimeErrorMessages.unsupported_binary_operator("runtime execution", operator))

    def _evaluate_ternary_expression(self, expression: ast.TernaryExpr, context: ExecutionContext) -> Any:
        condition = self._evaluate_expression(expression.condition, context)
        branch = expression.true_expression if bool(condition) else expression.false_expression
        return self._evaluate_expression(branch, context)

    def _guard_loop_iteration(self, loop_kind: str, iteration_count: int) -> None:
        if iteration_count > self._max_loop_iterations:
            raise RuntimeError(
                RuntimeErrorMessages.loop_iteration_limit_exceeded(
                    loop_kind,
                    self._max_loop_iterations,
                )
            )

    def _get_debugger(self, context: ExecutionContext) -> Any | None:
        debugger = getattr(context, "debugger", None)
        if debugger is not None:
            return debugger
        return self._debugger

    def _extract_nested_elseif_statement(
        self,
        else_branch: ast.Block | None,
    ) -> ast.IfStatement | None:
        if else_branch is None or len(else_branch.statements) != 1:
            return None
        nested = else_branch.statements[0]
        if isinstance(nested, ast.IfStatement):
            return nested
        return None

    def _normalize_loop_target(self, target: str | None) -> str | None:
        if target is None:
            return None
        normalized = str(target).strip().lower()
        return normalized or None

    def _signal_applies_to_loop(self, target: str | None, loop_kind: str) -> bool:
        if target is None or target == "loop":
            return True
        return target == loop_kind

    def _outside_loop_error_message(self, keyword: str, target: str | None) -> str:
        if target is None:
            return f"{keyword} statement used outside of loop"
        return f"{keyword} statement for target '{target}' used outside of matching loop"

    def _function_missing_required_argument_message(
        self,
        function_name: str,
        parameter_name: str,
    ) -> str:
        return RuntimeErrorMessages.function_missing_required_argument(
            function_name,
            parameter_name,
        )

    def _maximum_call_depth_exceeded_message(self, max_call_depth: int) -> str:
        return RuntimeErrorMessages.maximum_call_depth_exceeded(str(max_call_depth))

    def _with_call_stack_message(self, message: str, stack_text: str) -> str:
        return RuntimeErrorMessages.with_call_stack(message, stack_text)

    def _unwrap_parens(self, expression: ast.Expression | None) -> ast.Expression | None:
        while isinstance(expression, ast.ParenExpr):
            expression = expression.expression
        return expression

    def _get_node_line(self, node: Any | None) -> int | None:
        if node is None:
            return None
        line = getattr(node, "line", None)
        if isinstance(line, int) and line > 0:
            return line
        span = getattr(node, "span", None)
        if span is not None:
            start = getattr(span, "start", None)
            if isinstance(start, int) and start >= 0:
                source_text = self._source_text
                if not source_text:
                    return 1
                if start > len(source_text):
                    start = len(source_text)
                return source_text.count("\n", 0, start) + 1
        return None

    def _resolve_byref_reference(
        self,
        expression: ast.Expression | None,
        context: ExecutionContext,
        parameter_name: str,
    ) -> Any:
        reference = self._resolve_writable_reference(expression, context)
        if hasattr(reference, "get") and hasattr(reference, "set"):
            return reference
        raise RuntimeError(RuntimeErrorMessages.byref_argument_must_be_variable(parameter_name))

    def _resolve_writable_reference(
        self,
        expression: ast.Expression | None,
        context: ExecutionContext,
    ) -> Any:
        expression = self._unwrap_parens(expression)
        if isinstance(expression, ast.Identifier):
            return context.resolve_assignment_reference(expression.name)
        if isinstance(expression, ast.HostIdentifier):
            raise RuntimeError(
                RuntimeErrorMessages.runtime_value_is_read_only(expression.name)
            )
        if isinstance(expression, ast.IndexExpr):
            return self._resolve_index_reference(
                expression,
                context,
                require_writable_base=True,
            )
        if isinstance(expression, ast.BinaryExpr) and expression.operator == ".":
            base = self._evaluate_expression(expression.left, context)
            attribute = expression.right.name if isinstance(expression.right, ast.Identifier) else str(expression.right)
            if isinstance(base, StructInstance):
                raise RuntimeError(
                    RuntimeErrorMessages.struct_fields_are_immutable(
                        base.struct_name,
                        attribute,
                    )
                )
            if isinstance(base, RecordInstance):
                raise RuntimeError(
                    RuntimeErrorMessages.record_fields_are_immutable(
                        base.record_name,
                        attribute,
                    )
                )
        raise RuntimeError(
            RuntimeErrorMessages.assignment_target_not_writable(
                self._describe_assignment_target(expression)
            )
        )

    def _resolve_index_reference(
        self,
        expression: ast.IndexExpr,
        context: ExecutionContext,
        *,
        require_writable_base: bool,
    ) -> Any:
        base = self._evaluate_expression(expression.base, context)
        index_value = self._evaluate_expression(expression.index, context)

        if isinstance(base, list):
            if isinstance(index_value, bool) or not isinstance(index_value, (int, float)):
                raise RuntimeError(RuntimeErrorMessages.index_target_must_be_integer())
            index = int(index_value)
            if index < 0 or index >= len(base):
                raise RuntimeError(RuntimeErrorMessages.index_out_of_range(index))
            return self._list_item_reference(base, index)

        if isinstance(base, dict):
            if require_writable_base:
                return self._dict_item_reference(base, index_value)
            return base[index_value]

        raise RuntimeError(RuntimeErrorMessages.value_not_indexable(type(base).__name__))

    def _list_item_reference(self, container: list[Any], index: int) -> Any:
        from core.runtime.execution_context import VariableReference

        return VariableReference(
            getter=lambda container=container, index=index: container[index],
            setter=lambda value, container=container, index=index: container.__setitem__(index, value),
        )

    def _describe_assignment_target(self, expression: ast.Expression | None) -> str:
        expression = self._unwrap_parens(expression)
        if expression is None:
            return "<missing>"
        if isinstance(expression, ast.Identifier):
            return expression.name
        if isinstance(expression, ast.IndexExpr):
            return f"{self._describe_assignment_target(expression.base)}[...]"
        if isinstance(expression, ast.BinaryExpr) and expression.operator == ".":
            return f"{self._describe_assignment_target(expression.left)}.{self._describe_assignment_target(expression.right)}"
        return expression.kind

    def _goto_label_not_defined_message(self, label: str) -> str:
        return f"Goto target label not defined: {label}"

    def _goto_enters_structured_block_message(self, label: str) -> str:
        return f"Goto target enters a structured block: {label}"

    def _duplicate_label_message(self, label: str) -> str:
        return f"Duplicate label in block: {label}"

    def _structured_block_segment(self, kind: str, statement: ast.Statement) -> str:
        return f"{kind}:{statement.kind}"

    def _structured_case_segment(self, index: int, statement: ast.SelectCaseArm) -> str:
        arm_kind = "else" if statement.is_else else "case"
        return f"{arm_kind}:{index}:{statement.kind}"

    def _select_case_matches(
        self,
        select_value: Any,
        case_arm: ast.SelectCaseArm,
        context: ExecutionContext,
    ) -> bool:
        for condition in case_arm.conditions:
            if self._select_case_condition_matches(select_value, condition, context):
                return True
        return False

    def _select_case_condition_matches(
        self,
        select_value: Any,
        condition: ast.SelectCaseCondition,
        context: ExecutionContext,
    ) -> bool:
        _ = context
        if isinstance(condition, ast.SelectCaseValue):
            return self._safe_case_compare(select_value, self._evaluate_expression(condition.expression, context))
        if isinstance(condition, ast.SelectCaseRange):
            start = self._evaluate_expression(condition.start, context)
            end = self._evaluate_expression(condition.end, context)
            try:
                return start <= select_value <= end
            except TypeError:
                return False
        if isinstance(condition, ast.SelectCaseComparison):
            right = self._evaluate_expression(condition.expression, context)
            matched = self._compare_select_case_values(select_value, condition.operator, right)
            return (not matched) if condition.is_negated else matched
        if isinstance(condition, ast.SelectCaseLike):
            pattern_value = self._evaluate_expression(condition.pattern, context)
            matched = self._select_case_like_matches(select_value, pattern_value)
            return (not matched) if condition.is_negated else matched
        return False

    @staticmethod
    def _safe_case_compare(left: Any, right: Any) -> bool:
        try:
            return left == right
        except Exception:
            return False

    def _compare_select_case_values(self, left: Any, operator_text: str, right: Any) -> bool:
        op = operator_text.strip()
        if op in {"=", "=="}:
            return self._safe_case_compare(left, right)
        if op in {"<>", "!="}:
            return not self._safe_case_compare(left, right)

        try:
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
        except TypeError:
            return False

        return False

    def _select_case_like_matches(self, value: Any, pattern: Any) -> bool:
        candidate = "" if value is None else str(value)
        pattern_text = "" if pattern is None else str(pattern)
        regex = self._vb_like_pattern_to_regex(pattern_text)
        return re.fullmatch(regex, candidate) is not None

    def _vb_like_pattern_to_regex(self, pattern: str) -> str:
        pieces: list[str] = ["^"]
        index = 0
        length = len(pattern)

        while index < length:
            ch = pattern[index]
            if ch == "*":
                pieces.append(".*")
                index += 1
                continue
            if ch == "?":
                pieces.append(".")
                index += 1
                continue
            if ch == "#":
                pieces.append(r"\d")
                index += 1
                continue
            if ch == "[":
                close_index = pattern.find("]", index + 1)
                if close_index == -1:
                    pieces.append(re.escape(ch))
                    index += 1
                    continue

                char_class = pattern[index + 1 : close_index]
                if not char_class:
                    pieces.append(r"\[\]")
                    index = close_index + 1
                    continue

                negate = char_class.startswith("!")
                if negate:
                    char_class = char_class[1:]
                class_body = re.escape(char_class)
                class_body = class_body.replace(r"\-", "-")
                class_body = class_body.replace(r"\^", r"\^")
                class_body = class_body.replace(r"\]", r"\]")
                pieces.append("[" + ("^" if negate else "") + class_body + "]")
                index = close_index + 1
                continue

            pieces.append(re.escape(ch))
            index += 1

        pieces.append("$")
        return "".join(pieces)

    def _goto_target_is_legal(
        self,
        *,
        source_ancestry: tuple[str, ...],
        target_ancestry: tuple[str, ...],
    ) -> bool:
        if source_ancestry == target_ancestry:
            return True
        if len(target_ancestry) > len(source_ancestry):
            return False
        return source_ancestry[: len(target_ancestry)] == target_ancestry

    def _collect_labels_from_statement(
        self,
        statement: ast.Statement,
        label_map: dict[str, _LabelInfo],
        *,
        scope_id: str,
        ancestry: tuple[str, ...],
        statement_index: int,
    ) -> None:
        if isinstance(statement, ast.LabelStatement):
            label_key = statement.name.strip().lower()
            if label_key in label_map:
                raise RuntimeError(self._duplicate_label_message(statement.name))
            label_map[label_key] = _LabelInfo(
                name=statement.name,
                scope_id=scope_id,
                statement_index=statement_index,
                ancestry=ancestry,
            )

    def _collect_scope_labels_into(
        self,
        statements: list[ast.Statement],
        label_map: dict[str, _LabelInfo],
        *,
        scope_id: str,
        ancestry: tuple[str, ...],
    ) -> None:
        for index, statement in enumerate(statements):
            self._collect_labels_from_statement(
                statement,
                label_map,
                scope_id=scope_id,
                ancestry=ancestry,
                statement_index=index,
            )
            if isinstance(statement, ast.Block):
                self._collect_scope_labels_into(
                    statement.statements,
                    label_map,
                    scope_id=scope_id,
                    ancestry=ancestry,
                )
            elif isinstance(statement, ast.IfStatement):
                then_ancestry = ancestry + (self._structured_block_segment("then", statement),)
                self._collect_scope_labels_into(
                    statement.then_branch.statements,
                    label_map,
                    scope_id="if",
                    ancestry=then_ancestry,
                )
                if statement.else_branch is not None:
                    else_ancestry = ancestry + (self._structured_block_segment("else", statement),)
                    self._collect_scope_labels_into(
                        statement.else_branch.statements,
                        label_map,
                        scope_id="else",
                        ancestry=else_ancestry,
                    )
            elif isinstance(statement, ast.SelectStatement):
                select_ancestry = ancestry + (self._structured_block_segment("select", statement),)
                for case_index, case_arm in enumerate(statement.cases):
                    case_ancestry = select_ancestry + (self._structured_case_segment(case_index, case_arm),)
                    self._collect_scope_labels_into(
                        case_arm.body.statements,
                        label_map,
                        scope_id="select",
                        ancestry=case_ancestry,
                    )
            elif isinstance(statement, ast.ForStatement):
                body_ancestry = ancestry + (self._structured_block_segment("for", statement),)
                self._collect_scope_labels_into(
                    statement.body.statements,
                    label_map,
                    scope_id="for",
                    ancestry=body_ancestry,
                )
            elif isinstance(statement, ast.WhileStatement):
                body_ancestry = ancestry + (self._structured_block_segment("while", statement),)
                self._collect_scope_labels_into(
                    statement.body.statements,
                    label_map,
                    scope_id="while",
                    ancestry=body_ancestry,
                )
            elif isinstance(statement, ast.LoopStatement):
                body_ancestry = ancestry + (self._structured_block_segment("loop", statement),)
                self._collect_scope_labels_into(
                    statement.body.statements,
                    label_map,
                    scope_id="loop",
                    ancestry=body_ancestry,
                )

    def _execute_builtin_call(
        self,
        normalized_name: str,
        arguments: list[Any],
        context: ExecutionContext,
    ) -> Any:
        if normalized_name == "sleep":
            self._expect_arg_count(normalized_name, arguments, 1)
            duration_ms = self._require_int_value(normalized_name, arguments, 0)
            if duration_ms < 0:
                raise RuntimeError(RuntimeErrorMessages.SLEEP_DELAY_MUST_BE_NON_NEGATIVE)
            context.emit_event({"type": "delay", "duration_ms": duration_ms})
            return None
        if normalized_name == "time":
            self._expect_arg_count(normalized_name, arguments, 0)
            return int(time.time())
        if normalized_name == "utctime":
            self._expect_arg_count(normalized_name, arguments, 0)
            return self._build_tm_struct_instance(time.gmtime())
        if normalized_name == "localtime":
            return self._local_time(arguments, context)
        if normalized_name == "dayofweek":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._day_of_week(arguments, context)
        if normalized_name == "dayofyear":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._day_of_year(arguments, context)
        if normalized_name == "datepart":
            self._expect_arg_count(normalized_name, arguments, 2)
            return self._date_part(arguments, context)
        if normalized_name == "dateserial":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._date_serial(arguments, context)
        if normalized_name == "timeserial":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._time_serial(arguments, context)
        if normalized_name == "daysinmonth":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._days_in_month(arguments, context)
        if normalized_name == "isleapyear":
            self._expect_arg_count(normalized_name, arguments, 1)
            year = self._require_int_value("IsLeapYear", arguments, 0)
            return self._is_leap_year(year)
        if normalized_name == "isdate":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._is_date(arguments, context)
        if normalized_name == "istime":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._is_time(arguments, context)
        if normalized_name == "startofday":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._start_of_day(arguments, context)
        if normalized_name == "endofday":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._end_of_day(arguments, context)
        if normalized_name == "startofmonth":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._start_of_month(arguments, context)
        if normalized_name == "endofmonth":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._end_of_month(arguments, context)
        if normalized_name == "startofweek":
            self._expect_arg_counts(normalized_name, arguments, 1, 2)
            return self._start_of_week(arguments, context)
        if normalized_name == "nowdate":
            self._expect_arg_count(normalized_name, arguments, 0)
            return self._now_date()
        if normalized_name == "nowtime":
            self._expect_arg_count(normalized_name, arguments, 0)
            return self._now_time()
        if normalized_name == "nowdatetime":
            self._expect_arg_count(normalized_name, arguments, 0)
            return self._now_date_time()
        if normalized_name == "datetostring":
            self._expect_arg_counts(normalized_name, arguments, 0, 1)
            return self._date_to_string(arguments, context)
        if normalized_name == "datetolocalstring":
            self._expect_arg_counts(normalized_name, arguments, 0, 1)
            return self._date_to_local_string(arguments, context)
        if normalized_name == "datetoutcstring":
            self._expect_arg_counts(normalized_name, arguments, 0, 1)
            return self._date_to_utc_string(arguments, context)
        if normalized_name == "utcdatetime":
            self._expect_arg_count(normalized_name, arguments, 0)
            return self._utc_date_time()
        if normalized_name == "parsedatetime":
            self._expect_arg_counts(normalized_name, arguments, 1, 2)
            return self._parse_date_time(arguments, context)
        if normalized_name == "parsedatetimeinoffset":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._parse_date_time_in_offset(arguments, context)
        if normalized_name == "formatdatetime":
            self._expect_arg_count(normalized_name, arguments, 2)
            return self._format_date_time(arguments, context)
        if normalized_name == "formatdatetimeinoffset":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._format_date_time_in_offset(arguments, context)
        if normalized_name == "dateadd":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._date_add(arguments, context)
        if normalized_name == "datediff":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._date_diff(arguments, context)
        if normalized_name == "converttimezone":
            self._expect_arg_count(normalized_name, arguments, 3)
            return self._convert_time_zone(arguments, context)
        if normalized_name == "utcoffset":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._utc_offset(arguments, context)
        if normalized_name == "timezoneoffset":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._utc_offset(arguments, context)
        if normalized_name == "getcursorpos":
            return self._get_cursor_pos(arguments, context)
        if normalized_name == "getclientrect":
            return self._get_client_rect(arguments, context)
        if normalized_name == "getwindowrect":
            return self._get_window_rect(arguments, context)
        if normalized_name == "getwindowplacement":
            return self._get_window_placement(arguments, context)
        if normalized_name == "getwindowtext":
            return self._get_window_text(arguments, context)
        if normalized_name == "getwindowlongptr":
            return self._get_window_long_ptr(arguments, context)
        if normalized_name == "getparent":
            return self._get_parent(arguments, context)
        if normalized_name == "getclassname":
            return self._get_class_name(arguments, context)
        if normalized_name == "iszoomed":
            return self._get_is_zoomed(arguments, context)
        if normalized_name == "isiconic":
            return self._get_is_iconic(arguments, context)
        if normalized_name == "iswindowvisible":
            return self._get_is_window_visible(arguments, context)
        if normalized_name == "iswindowenabled":
            return self._get_is_window_enabled(arguments, context)
        if normalized_name == "getmonitorinfo":
            return self._get_monitor_info(arguments, context)
        if normalized_name == "getmonitorinfoex":
            return self._get_monitor_info_ex(arguments, context)
        if normalized_name == "getcurrenteventdelay":
            self._expect_arg_count(normalized_name, arguments, 0)
            return context.get_current_event_delay()
        if normalized_name == "setcurrenteventdelay":
            self._expect_arg_count(normalized_name, arguments, 1)
            delay_ms = self._require_int_value(normalized_name, arguments, 0)
            if delay_ms < 0:
                raise RuntimeError(
                    RuntimeErrorMessages.CURRENT_EVENT_DELAY_MUST_BE_NON_NEGATIVE
                )
            context.set_current_event_delay(delay_ms)
            return context.get_current_event_delay()

        if normalized_name == "keypress":
            return self._key_press(arguments, context)

        if normalized_name == "sendkeys":
            return self._send_keys(arguments, context)

        if normalized_name == "mousemove":
            self._expect_arg_counts(normalized_name, arguments, 2, 3)
            x = self._require_int_value(normalized_name, arguments, 0)
            y = self._require_int_value(normalized_name, arguments, 1)
            event = {"type": "mouse_move", "x": x, "y": y}
            if len(arguments) == 3:
                event["speed"] = self._coerce_mouse_speed(arguments[2], "MouseMove", 3)
            context.emit_event(self._apply_mouse_speed_override(event, context))
            return None

        if normalized_name == "mousedown":
            self._expect_arg_count(normalized_name, arguments, 3)
            button = self._require_string_value(normalized_name, arguments, 0).lower()
            x = self._require_int_value(normalized_name, arguments, 1)
            y = self._require_int_value(normalized_name, arguments, 2)
            context.emit_event({"type": "mouse_down", "button": button, "x": x, "y": y})
            return None

        if normalized_name == "mouseup":
            self._expect_arg_count(normalized_name, arguments, 3)
            button = self._require_string_value(normalized_name, arguments, 0).lower()
            x = self._require_int_value(normalized_name, arguments, 1)
            y = self._require_int_value(normalized_name, arguments, 2)
            context.emit_event({"type": "mouse_up", "button": button, "x": x, "y": y})
            return None

        if normalized_name == "mouseclick":
            self._expect_arg_counts(normalized_name, arguments, 4, 5)
            button = self._require_string_value(normalized_name, arguments, 0).lower()
            x = self._require_int_value(normalized_name, arguments, 1)
            y = self._require_int_value(normalized_name, arguments, 2)
            clicks = self._require_int_value(normalized_name, arguments, 3)
            event: dict[str, Any] = {
                "type": "mouse_click",
                "button": button,
                "x": x,
                "y": y,
                "clicks": clicks,
            }
            if len(arguments) == 5:
                event["speed"] = self._coerce_mouse_speed(arguments[4], "MouseClick", 5)
            context.emit_event(self._apply_mouse_speed_override(event, context))
            return None

        if normalized_name == "mouseclickdrag":
            return self._mouse_click_drag(arguments, context)

        if normalized_name == "mousedrag":
            return self._mouse_drag(arguments, context)

        if normalized_name == "mousewheel":
            self._expect_arg_counts(normalized_name, arguments, 1, 3)
            delta = self._require_int_value(normalized_name, arguments, 0)
            context.emit_event({"type": "mouse_wheel", "delta": delta})
            return None

        if normalized_name == "keydown":
            self._expect_arg_count(normalized_name, arguments, 1)
            key = self._require_string_value(normalized_name, arguments, 0).lower()
            context.emit_event({"type": "key_down", "key": key})
            return None

        if normalized_name == "keyup":
            self._expect_arg_count(normalized_name, arguments, 1)
            key = self._require_string_value(normalized_name, arguments, 0).lower()
            context.emit_event({"type": "key_up", "key": key})
            return None

        if normalized_name == "hotkey":
            self._expect_at_least_arg_count(normalized_name, arguments, 1)
            keys = [
                self._require_string_value(normalized_name, arguments, index).lower()
                for index in range(len(arguments))
            ]
            context.emit_event({"type": "hotkey", "keys": keys})
            return None

        if normalized_name == "sendtext":
            self._expect_arg_count(normalized_name, arguments, 1)
            text = self._require_string_value(normalized_name, arguments, 0)
            context.emit_event({"type": "text", "text": text})
            return None

        if normalized_name == "readfile":
            return self._read_file(arguments, context)
        if normalized_name == "writefile":
            return self._write_file(arguments, context)
        if normalized_name == "appendfile":
            return self._append_file(arguments, context)
        if normalized_name == "directorylist":
            return self._directory_list(arguments, context, "DirectoryList", want_directories=True)
        if normalized_name == "filelist":
            return self._directory_list(arguments, context, "FileList", want_directories=False)
        if normalized_name == "walkdir":
            return self._traverse_directory(arguments, context, "WalkDir", want_directories=True)
        if normalized_name == "enumeratefiles":
            return self._traverse_directory(arguments, context, "EnumerateFiles", want_directories=False)
        if normalized_name == "fileexists":
            return self._file_exists(arguments, context)
        if normalized_name == "deletefile":
            return self._delete_file(arguments, context)
        if normalized_name == "createdir":
            return self._create_dir(arguments, context)
        if normalized_name == "filesize":
            return self._file_size(arguments, context)
        if normalized_name == "filetime":
            return self._file_time(arguments, context)
        if normalized_name == "fileinfo":
            return self._file_info(arguments, context)
        if normalized_name == "filehash":
            return self._file_hash(arguments, context)
        if normalized_name == "filechecksum":
            return self._file_checksum(arguments, context)
        if normalized_name == "filecompare":
            return self._file_compare(arguments, context)
        if normalized_name == "copyfile":
            return self._copy_file(arguments, context)
        if normalized_name == "copydir":
            return self._copy_dir(arguments, context)
        if normalized_name == "movefile":
            return self._move_file(arguments, context)
        if normalized_name == "movedir":
            return self._move_dir(arguments, context)
        if normalized_name == "removedir":
            return self._remove_dir(arguments, context, "RemoveDir")
        if normalized_name == "directorydelete":
            return self._remove_dir(arguments, context, "DirectoryDelete")
        if normalized_name == "direxists":
            return self._dir_exists(arguments, context)
        if normalized_name == "pathexists":
            return self._path_exists(arguments, context)
        if normalized_name == "pathcombine":
            return self._path_combine(arguments, context)
        if normalized_name == "pathnormalize":
            return self._path_normalize(arguments, context)
        if normalized_name == "ispathvalid":
            return self._is_path_valid(arguments, context)
        if normalized_name == "filename":
            return self._file_name(arguments, context)
        if normalized_name == "directoryname":
            return self._directory_name(arguments, context)
        if normalized_name == "extensionname":
            return self._extension_name(arguments, context)
        if normalized_name == "readbytes":
            return self._read_bytes(arguments, context)
        if normalized_name == "writebytes":
            return self._write_bytes(arguments, context)
        if normalized_name == "appendbytes":
            return self._append_bytes(arguments, context)
        if normalized_name == "binarylength":
            return self._binary_length(arguments, context)
        if normalized_name == "hex":
            return self._hex(arguments, context)
        if normalized_name == "fromhex":
            return self._from_hex(arguments, context)
        if normalized_name == "base64":
            return self._base64(arguments, context)
        if normalized_name == "frombase64":
            return self._from_base64(arguments, context)
        if normalized_name == "binary":
            return self._binary(arguments, context)
        if normalized_name == "binarymid":
            return self._binary_mid(arguments, context)
        if normalized_name == "binarytostring":
            return self._binary_to_string(arguments, context)
        if normalized_name == "arraylength":
            return self._array_length(arguments, context)
        if normalized_name == "arrayinsert":
            return self._array_insert(arguments, context)
        if normalized_name == "arraypush":
            return self._array_push(arguments, context)
        if normalized_name == "arraypop":
            return self._array_pop(arguments, context)
        if normalized_name == "arrayremove":
            return self._array_remove(arguments, context)
        if normalized_name == "arrayremoveall":
            return self._array_remove_all(arguments, context)
        if normalized_name == "arraycontains":
            return self._array_contains(arguments, context)
        if normalized_name == "arraycontainsall":
            return self._array_contains_all(arguments, context)
        if normalized_name == "arraycount":
            return self._array_count(arguments, context)
        if normalized_name == "arrayinitialize":
            return self._array_initialize(arguments, context)
        if normalized_name == "arrayclear":
            return self._array_clear(arguments, context)
        if normalized_name == "arrayclone":
            return self._array_clone(arguments, context)
        if normalized_name == "arrayindexof":
            return self._array_index_of(arguments, context)
        if normalized_name == "arraylastindexof":
            return self._array_last_index_of(arguments, context)
        if normalized_name == "arrayjoin":
            return self._array_to_string(arguments, context, "ArrayJoin")
        if normalized_name == "arrayreverse":
            return self._array_reverse(arguments, context)
        if normalized_name == "arraysort":
            return self._array_sort(arguments, context)
        if normalized_name == "arrayunique":
            return self._array_unique(arguments, context)
        if normalized_name == "arraytostring":
            return self._array_to_string(arguments, context)
        if normalized_name == "arrayslice":
            return self._array_slice(arguments, context)

        if normalized_name == "write":
            text = "".join(self._stringify_interpolated_value(arg) for arg in arguments)
            context.add_output(text)
            return len(text)
        if normalized_name == "writeln":
            text = "".join(self._stringify_interpolated_value(arg) for arg in arguments) + "\n"
            context.add_output(text)
            return len(text)
        if normalized_name == "diagwrite":
            text = "".join(self._stringify_interpolated_value(arg) for arg in arguments)
            self._emit_script_output_diagnostic(
                text,
                context,
                event_id="runtime.script_output.write",
            )
            return len(text)
        if normalized_name == "diagwriteln":
            text = "".join(self._stringify_interpolated_value(arg) for arg in arguments)
            self._emit_script_output_diagnostic(
                text,
                context,
                event_id="runtime.script_output.writeln",
            )
            return len(text) + 1
        if normalized_name == "string":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._stringify_interpolated_value(arguments[0])
        if normalized_name == "stringlength":
            return self._string_length(arguments, context)
        if normalized_name == "stringleft":
            return self._string_left(arguments, context)
        if normalized_name == "stringstartswith":
            return self._string_starts_with(arguments, context)
        if normalized_name == "stringendswith":
            return self._string_ends_with(arguments, context)
        if normalized_name == "stringcontains":
            return self._string_contains(arguments, context)
        if normalized_name == "stringreplace":
            return self._string_replace(arguments, context)
        if normalized_name == "stringsplit":
            return self._string_split(arguments, context)
        if normalized_name == "stringjoin":
            return self._string_join(arguments, context)
        if normalized_name == "regexescape":
            return self._regex_escape(arguments, context)
        if normalized_name == "regexismatch":
            return self._regex_is_match(arguments, context)
        if normalized_name == "regexinstr":
            return self._regex_in_str(arguments, context)
        if normalized_name == "regexmatch":
            return self._regex_match(arguments, context)
        if normalized_name == "regexreplace":
            return self._regex_replace(arguments, context)
        if normalized_name == "stringreverse":
            return self._string_reverse(arguments, context)
        if normalized_name == "stringright":
            return self._string_right(arguments, context)
        if normalized_name == "stringmid":
            return self._string_mid(arguments, context)
        if normalized_name == "stringtrimleft":
            return self._string_trim_left(arguments, context)
        if normalized_name == "stringtrimright":
            return self._string_trim_right(arguments, context)
        if normalized_name == "stringtolower":
            return self._string_to_lower(arguments, context)
        if normalized_name == "stringtoupper":
            return self._string_to_upper(arguments, context)
        if normalized_name == "asc":
            return self._asc(arguments, context, "Asc")
        if normalized_name == "ascw":
            return self._asc(arguments, context, "AscW")
        if normalized_name == "chr":
            return self._chr(arguments, context, "Chr")
        if normalized_name == "chrw":
            return self._chr(arguments, context, "ChrW")
        if normalized_name == "stringcompare":
            self._expect_arg_counts(normalized_name, arguments, 2, 3)
            left = self._coerce_strict_string(arguments[0], "StringCompare", 1)
            right = self._coerce_strict_string(arguments[1], "StringCompare", 2)
            compare_type = 0 if len(arguments) == 2 else self._require_int_value("StringCompare", arguments, 2)
            if compare_type not in (0, 1):
                raise RuntimeError(
                    RuntimeErrorMessages.argument_must_be_one_of(
                        "StringCompare",
                        3,
                        [0, 1],
                    )
                )
            if compare_type == 0:
                left = left.casefold()
                right = right.casefold()
            return (left > right) - (left < right)
        if normalized_name == "stringisalpha":
            return self._string_is_alpha(arguments, context)
        if normalized_name == "stringisalphanumeric":
            return self._string_is_alphanumeric(arguments, context)
        if normalized_name == "stringisascii":
            return self._string_is_ascii(arguments, context)
        if normalized_name == "stringisdigit":
            return self._string_is_digit(arguments, context)
        if normalized_name == "stringisfloat":
            return self._string_is_float(arguments, context)
        if normalized_name == "stringisint":
            return self._string_is_int(arguments, context)
        if normalized_name == "stringislower":
            return self._string_is_lower(arguments, context)
        if normalized_name == "stringisspace":
            return self._string_is_space(arguments, context)
        if normalized_name == "stringisupper":
            return self._string_is_upper(arguments, context)
        if normalized_name == "stringinstr":
            return self._string_in_str(arguments, context)
        if normalized_name == "abs":
            self._expect_arg_count(normalized_name, arguments, 1)
            return abs(arguments[0])
        if normalized_name == "ceiling":
            self._expect_arg_count(normalized_name, arguments, 1)
            value = self._require_numeric_value("Ceiling", arguments, 0)
            return math.ceil(value)
        if normalized_name == "exp":
            self._expect_arg_count(normalized_name, arguments, 1)
            value = self._require_numeric_value("Exp", arguments, 0)
            return math.exp(value)
        if normalized_name == "floor":
            self._expect_arg_count(normalized_name, arguments, 1)
            value = self._require_numeric_value("Floor", arguments, 0)
            return math.floor(value)
        if normalized_name == "int":
            self._expect_arg_count(normalized_name, arguments, 1)
            value = self._require_numeric_value("Int", arguments, 0)
            return int(value)
        if normalized_name == "round":
            self._expect_arg_counts(normalized_name, arguments, 1, 2)
            value = self._require_numeric_value("Round", arguments, 0)
            decimal_places = 0
            if len(arguments) == 2:
                decimal_places = self._require_int_value("Round", arguments, 1)
            return self._round_numeric_value(value, decimal_places)
        if normalized_name in {"chr", "chrw"}:
            self._expect_arg_count(normalized_name, arguments, 1)
            return chr(self._require_int_value(normalized_name, arguments, 0))
        if normalized_name in {"asc", "ascw"}:
            self._expect_arg_count(normalized_name, arguments, 1)
            text = self._require_string_value(normalized_name, arguments, 0)
            return ord(text[0]) if text else 0
        if normalized_name == "mod":
            self._expect_arg_count(normalized_name, arguments, 2)
            left = self._require_numeric_value("Mod", arguments, 0)
            right = self._require_numeric_value("Mod", arguments, 1)
            return left % right
        if normalized_name == "bitand":
            self._expect_at_least_arg_count(normalized_name, arguments, 2)
            return int(arguments[0]) & int(arguments[1])
        if normalized_name == "bitor":
            self._expect_at_least_arg_count(normalized_name, arguments, 2)
            return int(arguments[0]) | int(arguments[1])
        if normalized_name == "bitxor":
            self._expect_at_least_arg_count(normalized_name, arguments, 2)
            return int(arguments[0]) ^ int(arguments[1])
        if normalized_name == "bitnot":
            self._expect_arg_count(normalized_name, arguments, 1)
            return ~int(arguments[0])
        if normalized_name == "bitnotunsigned":
            self._expect_arg_count(normalized_name, arguments, 1)
            return self._bit_not_unsigned(arguments, context)
        if normalized_name == "bitrotate":
            self._expect_arg_counts(normalized_name, arguments, 1, 2, 3)
            return self._bit_rotate(arguments, context)
        if normalized_name == "bitshift":
            self._expect_at_least_arg_count(normalized_name, arguments, 2)
            value = int(arguments[0])
            shift = int(arguments[1])
            return value << shift if shift >= 0 else value >> abs(shift)
        if normalized_name == "getmousemovespeed":
            return context.get_effective_mouse_move_speed()
        if normalized_name == "setmousemovespeed":
            self._expect_arg_count(normalized_name, arguments, 1)
            context.set_mouse_move_speed_override(
                self._coerce_mouse_speed(arguments[0], "SetMouseMoveSpeed", 1)
            )
            return context.get_effective_mouse_move_speed()

        if normalized_name == "keytoggle":
            return self._key_toggle(arguments, context)
        if normalized_name == "msgbox":
            return self._msgbox(arguments, context)
        if normalized_name == "pixelgetcolor":
            return self._pixel_get_color(arguments, context)
        if normalized_name == "pixelsearch":
            return self._pixel_search(arguments, context)

        raise RuntimeError(RuntimeErrorMessages.unsupported_function(normalized_name))

    def _require_int_value(self, name: str, args: list[Any], index: int) -> int:
        value = args[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_integer(name, index + 1))
        return int(value)

    def _require_numeric_value(self, name: str, args: list[Any], index: int) -> Any:
        value = args[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_number(name, index + 1))
        return value

    def _round_numeric_value(self, value: Any, decimal_places: int) -> int | float:
        decimal_value = Decimal(str(value))
        quantizer = Decimal("1").scaleb(-int(decimal_places))
        rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
        if rounded == rounded.to_integral_value(rounding=ROUND_HALF_UP):
            return int(rounded)
        return float(rounded)

    def _local_time(self, args: list[Any], _context: ExecutionContext) -> StructInstance:
        self._expect_arg_counts("LocalTime", args, 0, 1)
        epoch_seconds = time.time() if len(args) == 0 else self._require_numeric_value("LocalTime", args, 0)
        return self._build_tm_struct_instance(time.localtime(epoch_seconds))

    def _is_leap_year(self, year: int) -> bool:
        if year % 4 != 0:
            return False
        if year % 100 != 0:
            return True
        return year % 400 == 0

    def _is_date(self, args: list[Any], _context: ExecutionContext) -> bool:
        text = self._require_string_value("IsDate", args, 0).strip()
        if not text:
            return False
        if self._try_parse_date_time(text) is not None:
            return True
        return self._try_parse_time_text(text) is not None

    def _is_time(self, args: list[Any], _context: ExecutionContext) -> bool:
        text = self._require_string_value("IsTime", args, 0).strip()
        if not text:
            return False
        return self._try_parse_time_text(text) is not None

    def _day_of_week(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("DayOfWeek", args, 0)
        return self._build_tm_struct_instance(time.localtime(epoch_seconds)).tm_wday

    def _day_of_year(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("DayOfYear", args, 0)
        return self._build_tm_struct_instance(time.localtime(epoch_seconds)).tm_yday

    def _date_part(self, args: list[Any], _context: ExecutionContext) -> int:
        local_datetime = self._coerce_date_time_value("DatePart", args[0], 1)
        part = self._require_string_value("DatePart", args, 1).strip().lower()
        if part == "year":
            return int(local_datetime.year)
        if part == "month":
            return int(local_datetime.month)
        if part == "day":
            return int(local_datetime.day)
        if part == "hour":
            return int(local_datetime.hour)
        if part == "minute":
            return int(local_datetime.minute)
        if part == "second":
            return int(local_datetime.second)
        if part in {"weekday", "dayofweek"}:
            return (int(local_datetime.weekday()) + 1) % 7
        if part in {"yearday", "dayofyear"}:
            return int(local_datetime.timetuple().tm_yday) - 1
        raise RuntimeError(
            RuntimeErrorMessages.argument_must_be_one_of_strings(
                "DatePart",
                2,
                ["year", "month", "day", "hour", "minute", "second", "weekday", "yearday"],
            )
        )

    def _date_serial(self, args: list[Any], _context: ExecutionContext) -> int:
        year = self._require_int_value("DateSerial", args, 0)
        month = self._require_int_value("DateSerial", args, 1)
        day = self._require_int_value("DateSerial", args, 2)
        try:
            local_datetime = datetime(year, month, day)
        except ValueError:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("DateSerial", f"{year}-{month}-{day}")) from None
        return self._local_epoch_from_datetime(local_datetime)

    def _time_serial(self, args: list[Any], _context: ExecutionContext) -> int:
        hour = self._require_int_value("TimeSerial", args, 0)
        minute = self._require_int_value("TimeSerial", args, 1)
        second = self._require_int_value("TimeSerial", args, 2)
        if hour < 0 or hour > 23:
            raise RuntimeError("TimeSerial argument 1 must be between 0 and 23")
        if minute < 0 or minute > 59:
            raise RuntimeError("TimeSerial argument 2 must be between 0 and 59")
        if second < 0 or second > 59:
            raise RuntimeError("TimeSerial argument 3 must be between 0 and 59")
        return hour * 3600 + minute * 60 + second

    def _days_in_month(self, args: list[Any], _context: ExecutionContext) -> int:
        local_datetime = self._coerce_date_time_value("DaysInMonth", args[0], 1)
        return calendar.monthrange(local_datetime.year, local_datetime.month)[1]

    def _start_of_day(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("StartOfDay", args, 0)
        local_time = time.localtime(epoch_seconds)
        return self._local_epoch_from_components(local_time.tm_year, local_time.tm_mon, local_time.tm_mday)

    def _end_of_day(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("EndOfDay", args, 0)
        local_time = time.localtime(epoch_seconds)
        year, month, day = self._next_local_date(local_time.tm_year, local_time.tm_mon, local_time.tm_mday)
        return self._local_epoch_from_components(year, month, day) - 1

    def _start_of_month(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("StartOfMonth", args, 0)
        local_time = time.localtime(epoch_seconds)
        return self._local_epoch_from_components(local_time.tm_year, local_time.tm_mon, 1)

    def _end_of_month(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("EndOfMonth", args, 0)
        local_time = time.localtime(epoch_seconds)
        year, month = self._next_local_month(local_time.tm_year, local_time.tm_mon)
        return self._local_epoch_from_components(year, month, 1) - 1

    def _start_of_week(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("StartOfWeek", args, 0)
        local_time = time.localtime(epoch_seconds)
        current_weekday = (int(local_time.tm_wday) + 1) % 7
        week_starts_on = 0 if len(args) == 1 else self._require_int_value("StartOfWeek", args, 1)
        if week_starts_on < 0 or week_starts_on > 6:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StartOfWeek",
                    2,
                    [0, 1, 2, 3, 4, 5, 6],
                )
            )
        days_to_subtract = (current_weekday - week_starts_on) % 7
        start_date = datetime(
            int(local_time.tm_year),
            int(local_time.tm_mon),
            int(local_time.tm_mday),
        ) - timedelta(days=days_to_subtract)
        return self._local_epoch_from_datetime(start_date)

    def _local_epoch_from_components(self, year: int, month: int, day: int) -> int:
        return int(time.mktime((int(year), int(month), int(day), 0, 0, 0, 0, 0, -1)))

    def _next_local_date(self, year: int, month: int, day: int) -> tuple[int, int, int]:
        days_in_month = calendar.monthrange(int(year), int(month))[1]
        if int(day) < days_in_month:
            return int(year), int(month), int(day) + 1
        if int(month) < 12:
            return int(year), int(month) + 1, 1
        return int(year) + 1, 1, 1

    def _next_local_month(self, year: int, month: int) -> tuple[int, int]:
        if int(month) < 12:
            return int(year), int(month) + 1
        return int(year) + 1, 1

    def _build_tm_struct_instance(self, local_time: time.struct_time) -> StructInstance:
        return StructInstance(
            struct_name="tm",
            _field_names=(
                "tm_sec",
                "tm_min",
                "tm_hour",
                "tm_mday",
                "tm_mon",
                "tm_year",
                "tm_wday",
                "tm_yday",
                "tm_isdst",
            ),
            _values=(
                int(local_time.tm_sec),
                int(local_time.tm_min),
                int(local_time.tm_hour),
                int(local_time.tm_mday),
                int(local_time.tm_mon) - 1,
                int(local_time.tm_year) - 1900,
                (int(local_time.tm_wday) + 1) % 7,
                int(local_time.tm_yday) - 1,
                local_time.tm_isdst > 0,
            ),
        )

    def _now_date(self) -> str:
        current = datetime.now()
        if os.name == "nt":
            localized = self._format_windows_localized_date(current)
            if localized:
                return localized
        return current.strftime("%x")

    def _now_time(self) -> str:
        current = datetime.now()
        if os.name == "nt":
            localized = self._format_windows_localized_time(current)
            if localized:
                return localized
        return current.strftime("%X")

    def _now_date_time(self) -> str:
        return self._format_local_date_time_string(datetime.now())

    def _utc_date_time(self) -> str:
        return self._format_utc_date_time_string(datetime.utcnow())

    def _date_to_string(self, args: list[Any], _context: ExecutionContext) -> str:
        return self._date_to_local_string_with_name("DateToString", args)

    def _date_to_local_string(self, args: list[Any], _context: ExecutionContext) -> str:
        return self._date_to_local_string_with_name("DateToLocalString", args)

    def _date_to_local_string_with_name(self, name: str, args: list[Any]) -> str:
        current = datetime.now() if len(args) == 0 else self._coerce_local_datetime_value(name, args[0], 1)
        return self._format_local_date_time_string(current)

    def _date_to_utc_string(self, args: list[Any], _context: ExecutionContext) -> str:
        current = datetime.utcnow() if len(args) == 0 else self._coerce_utc_datetime_value("DateToUTCString", args[0], 1)
        return self._format_utc_date_time_string(current)

    def _parse_date_time(self, args: list[Any], _context: ExecutionContext) -> int:
        text = self._require_string_value("ParseDateTime", args, 0).strip()
        if not text:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTime", text))

        if len(args) == 2:
            format_text = self._require_string_value("ParseDateTime", args, 1).strip()
            if not format_text:
                raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTime", text))
            return self._parse_date_time_with_format("ParseDateTime", text, format_text)

        is_utc = False
        candidate_text = text
        if candidate_text.upper().endswith(" UTC"):
            is_utc = True
            candidate_text = candidate_text[:-4].rstrip()
        elif candidate_text.endswith("Z") and len(candidate_text) > 1:
            is_utc = True
            candidate_text = candidate_text[:-1].rstrip()

        parsed = self._try_parse_date_time(candidate_text)
        if parsed is None:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTime", text))

        if parsed.tzinfo is not None:
            return int(parsed.timestamp())
        if is_utc:
            return int(calendar.timegm(parsed.timetuple()))
        try:
            return int(time.mktime(parsed.timetuple()))
        except (OverflowError, OSError, ValueError):
            return int(calendar.timegm(parsed.timetuple()))

    def _parse_date_time_in_offset(self, args: list[Any], _context: ExecutionContext) -> int:
        text = self._require_string_value("ParseDateTimeInOffset", args, 0).strip()
        if not text:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTimeInOffset", text))
        format_text = self._require_string_value("ParseDateTimeInOffset", args, 1).strip()
        if not format_text:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTimeInOffset", text))
        offset_minutes = self._coerce_timezone_offset_minutes("ParseDateTimeInOffset", args[2], 2)
        default_timezone = timezone(timedelta(minutes=offset_minutes))
        return self._parse_date_time_with_format(
            "ParseDateTimeInOffset",
            text,
            format_text,
            default_timezone=default_timezone,
        )

    def _parse_date_time_with_format(
        self,
        name: str,
        text: str,
        format_text: str,
        *,
        default_timezone: timezone | None = None,
    ) -> int:
        if ("%I" in format_text) != ("%p" in format_text):
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text(name, text))
        try:
            parsed = datetime.strptime(text, format_text)
        except ValueError:
            parsed = None
            parsed = self._parse_date_time_with_numeric_separator_fallback(text, format_text)
            if parsed is None:
                parsed = self._parse_date_time_with_locale_name_fallback(text, format_text)
            if parsed is None:
                parsed = self._parse_date_time_with_timezone_fallback(text, format_text)
            if parsed is None:
                raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text(name, text)) from None

        if parsed.tzinfo is not None:
            return int(parsed.timestamp())
        if default_timezone is not None:
            return int(parsed.replace(tzinfo=default_timezone).timestamp())

        normalized_text = text.upper()
        normalized_format = format_text.upper()
        if "%Z" in normalized_format and normalized_text.endswith("UTC"):
            return int(calendar.timegm(parsed.timetuple()))
        if "%Z" in normalized_format and normalized_text.endswith("GMT"):
            return int(calendar.timegm(parsed.timetuple()))
        if "%z" in normalized_format and normalized_text.endswith("Z"):
            return int(calendar.timegm(parsed.timetuple()))

        try:
            return int(time.mktime(parsed.timetuple()))
        except (OverflowError, OSError, ValueError):
            return int(calendar.timegm(parsed.timetuple()))

    # The strict ParseDateTime(format) path tries a few targeted fallbacks when
    # the host strptime rules are too locale-specific. The numeric fallback only
    # relaxes separators within related token groups:
    # - date tokens can swap among slash, dash, and dot separators
    # - time tokens can swap among colon, dash, and dot separators
    # - the date/time boundary can swap among space, T, and underscore
    def _parse_date_time_with_numeric_separator_fallback(self, text: str, format_text: str) -> datetime | None:
        if not any(token in format_text for token in ("%Y", "%y", "%m", "%d", "%H", "%I", "%M", "%S", "%f")):
            return None

        parts = self._tokenize_date_time_format_for_numeric_fallback(format_text)
        if parts is None:
            return None

        regex_parts: list[str] = []
        token_groups = [
            self._numeric_date_time_format_token_group(part[1])
            for part in parts
            if part[0] == "token"
        ]
        token_index = 0
        for part_index, (part_kind, part_value) in enumerate(parts):
            if part_kind == "token":
                regex_parts.append(self._numeric_date_time_format_token_regex(part_value))
                token_index += 1
                continue

            if not part_value:
                continue
            if self._is_numeric_separator_chunk(part_value):
                left_group = token_groups[token_index - 1] if token_index > 0 else None
                right_group = token_groups[token_index] if token_index < len(token_groups) else None
                separator_pattern = self._numeric_separator_pattern_for_groups(left_group, right_group)
                if separator_pattern is None:
                    regex_parts.append(re.escape(part_value))
                else:
                    regex_parts.append(separator_pattern)
                continue

            regex_parts.append(re.escape(part_value))

        match = re.fullmatch("".join(regex_parts), text.strip(), flags=re.IGNORECASE)
        if match is None:
            return None

        groups = match.groupdict()
        year = 1900
        month = 1
        day = 1
        hour: int | None = None
        minute: int | None = None
        second: int | None = None
        microsecond: int | None = None
        ampm: str | None = None

        if groups.get("year"):
            year = int(groups["year"])
        elif groups.get("year2"):
            year2 = int(groups["year2"])
            year = 2000 + year2 if year2 <= 69 else 1900 + year2
        if groups.get("month"):
            month = int(groups["month"])
        if groups.get("day"):
            day = int(groups["day"])
        if groups.get("hour24"):
            hour = int(groups["hour24"])
        elif groups.get("hour12"):
            hour = int(groups["hour12"])
        if groups.get("minute"):
            minute = int(groups["minute"])
        if groups.get("second"):
            second = int(groups["second"])
        if groups.get("microsecond"):
            microsecond = int(groups["microsecond"].ljust(6, "0"))
        if groups.get("ampm"):
            ampm = groups["ampm"].casefold()

        if month > 12:
            return None
        if day > calendar.monthrange(year, month)[1]:
            return None
        if minute is not None and (minute < 0 or minute > 59):
            return None
        if second is not None and (second < 0 or second > 59):
            return None
        if microsecond is not None and (microsecond < 0 or microsecond > 999999):
            return None

        if groups.get("hour12") is not None:
            if ampm is None:
                return None
            if hour is None or hour < 1 or hour > 12:
                return None
            if ampm not in {"am", "pm"}:
                return None
            hour = 0 if hour == 12 else hour
            if ampm == "pm":
                hour += 12
        elif ampm is not None:
            return None

        try:
            return datetime(
                year,
                month,
                day,
                hour if hour is not None else 0,
                minute if minute is not None else 0,
                second if second is not None else 0,
                microsecond if microsecond is not None else 0,
            )
        except ValueError:
            return None

    def _tokenize_date_time_format_for_numeric_fallback(self, format_text: str) -> list[tuple[str, str]] | None:
        parts: list[tuple[str, str]] = []
        literal_buffer: list[str] = []
        index = 0

        def flush_literal_buffer() -> None:
            if literal_buffer:
                parts.append(("literal", "".join(literal_buffer)))
                literal_buffer.clear()

        while index < len(format_text):
            char = format_text[index]
            if char == "%" and index + 1 < len(format_text):
                token = format_text[index + 1]
                flush_literal_buffer()
                if token not in {"%", "Y", "y", "m", "d", "H", "I", "M", "S", "f", "p"}:
                    return None
                parts.append(("token", token))
                index += 2
                continue
            literal_buffer.append(char)
            index += 1

        flush_literal_buffer()
        return parts

    def _numeric_date_time_format_token_regex(self, token: str) -> str:
        pattern = _NUMERIC_DATE_TIME_TOKEN_REGEX_PATTERNS.get(token)
        if pattern is None:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("ParseDateTime", token))
        return pattern

    def _numeric_date_time_format_token_group(self, token: str) -> str | None:
        return _NUMERIC_DATE_TIME_TOKEN_GROUPS.get(token)

    def _is_numeric_separator_chunk(self, value: str) -> bool:
        return all((char.isspace() or char in {"/", "-", ".", ",", ":", "_", "T"}) for char in value)

    def _numeric_separator_pattern_for_groups(self, left_group: str | None, right_group: str | None) -> str | None:
        if left_group is None or right_group is None:
            return None
        if left_group == right_group and left_group in _NUMERIC_DATE_TIME_SEPARATOR_GROUPS:
            allowed = _NUMERIC_DATE_TIME_SEPARATOR_GROUPS[left_group]
        elif {left_group, right_group} == {"date", "time"}:
            allowed = _NUMERIC_DATE_TIME_SEPARATOR_GROUPS["datetime"]
        else:
            return None

        escaped_allowed = "".join(sorted(re.escape(char) for char in allowed))
        return rf"[{escaped_allowed}]+"

    def _parse_date_time_with_locale_name_fallback(self, text: str, format_text: str) -> datetime | None:
        if not any(token in format_text for token in ("%a", "%A", "%b", "%B")):
            return None

        regex_parts: list[str] = []
        year = month = day = hour = minute = second = microsecond = None
        hour_is_12_clock = False
        ampm: str | None = None
        tz_offset_minutes: int | None = None
        tz_name: str | None = None
        weekday_name: str | None = None

        index = 0
        while index < len(format_text):
            char = format_text[index]
            if char == "%" and index + 1 < len(format_text):
                token = format_text[index + 1]
                if token == "%":
                    regex_parts.append(re.escape("%"))
                elif token == "Y":
                    regex_parts.append(r"(?P<year>\d{4})")
                elif token == "y":
                    regex_parts.append(r"(?P<year2>\d{2})")
                elif token == "m":
                    regex_parts.append(r"(?P<month>\d{1,2})")
                elif token == "d":
                    regex_parts.append(r"(?P<day>\d{1,2})")
                elif token == "H":
                    regex_parts.append(r"(?P<hour24>\d{1,2})")
                elif token == "I":
                    regex_parts.append(r"(?P<hour12>\d{1,2})")
                    hour_is_12_clock = True
                elif token == "M":
                    regex_parts.append(r"(?P<minute>\d{1,2})")
                elif token == "S":
                    regex_parts.append(r"(?P<second>\d{1,2})")
                elif token == "f":
                    regex_parts.append(r"(?P<microsecond>\d{1,6})")
                elif token == "p":
                    regex_parts.append(r"(?P<ampm>AM|PM|am|pm)")
                elif token == "a":
                    regex_parts.append(r"(?P<weekday_name>[A-Za-z]+)")
                elif token == "A":
                    regex_parts.append(r"(?P<weekday_name>[A-Za-z]+)")
                elif token == "b":
                    regex_parts.append(r"(?P<month_name>[A-Za-z]+)")
                elif token == "B":
                    regex_parts.append(r"(?P<month_name>[A-Za-z]+)")
                elif token == "z":
                    regex_parts.append(r"(?P<tz_offset>Z|[+-]\d{2}:?\d{2})")
                elif token == "Z":
                    regex_parts.append(r"(?P<tz_name>[A-Za-z]+)")
                else:
                    return None
                index += 2
                continue

            if char.isspace():
                regex_parts.append(r"\s+")
            else:
                regex_parts.append(re.escape(char))
            index += 1

        match = re.fullmatch("".join(regex_parts), text.strip(), flags=re.IGNORECASE)
        if match is None:
            return None

        groups = match.groupdict()
        if groups.get("year"):
            year = int(groups["year"])
        elif groups.get("year2"):
            year2 = int(groups["year2"])
            year = 2000 + year2 if year2 <= 69 else 1900 + year2
        if groups.get("month"):
            month = int(groups["month"])
        elif groups.get("month_name"):
            month = _ENGLISH_MONTH_NAME_TO_NUMBER.get(groups["month_name"].casefold(), 0)
        if groups.get("day"):
            day = int(groups["day"])
        if groups.get("hour24"):
            hour = int(groups["hour24"])
        elif groups.get("hour12"):
            hour = int(groups["hour12"])
        if groups.get("minute"):
            minute = int(groups["minute"])
        if groups.get("second"):
            second = int(groups["second"])
        if groups.get("microsecond"):
            microsecond = int(groups["microsecond"].ljust(6, "0"))
        if groups.get("ampm"):
            ampm = groups["ampm"].casefold()
        if groups.get("weekday_name"):
            weekday_name = groups["weekday_name"].casefold()
        if groups.get("tz_name"):
            tz_name = groups["tz_name"].casefold()
        if groups.get("tz_offset"):
            tz_offset_minutes = self._parse_timezone_offset_minutes(groups["tz_offset"])

        if hour_is_12_clock:
            if ampm is None:
                return None
            if hour is None:
                hour = 0
            if hour < 1 or hour > 12:
                return None
            if ampm not in {"am", "pm"}:
                return None
            hour = 0 if hour == 12 else hour
            if ampm == "pm":
                hour += 12
        elif ampm is not None:
            return None

        if month < 1 or month > 12:
            return None
        if day < 1 or day > calendar.monthrange(year, month)[1]:
            return None
        if minute is not None and (minute < 0 or minute > 59):
            return None
        if second is not None and (second < 0 or second > 59):
            return None
        if microsecond is not None and (microsecond < 0 or microsecond > 999999):
            return None

        try:
            parsed = datetime(
                year,
                month,
                day,
                hour if hour is not None else 0,
                minute if minute is not None else 0,
                second if second is not None else 0,
                microsecond if microsecond is not None else 0,
            )
        except ValueError:
            return None

        if weekday_name is not None:
            expected_weekday = _ENGLISH_WEEKDAY_NAME_TO_NUMBER.get(weekday_name, None)
            if expected_weekday is None:
                return None
            if parsed.weekday() != expected_weekday:
                return None

        if tz_offset_minutes is not None:
            return parsed.replace(tzinfo=timezone(timedelta(minutes=tz_offset_minutes)))
        if tz_name is not None:
            if tz_name in {"utc", "gmt"}:
                return parsed.replace(tzinfo=timezone.utc)
            return None
        return parsed

    def _parse_timezone_offset_minutes(self, offset_text: str) -> int | None:
        normalized = offset_text.strip().upper()
        if normalized in {"Z", "UTC", "GMT"}:
            return 0
        match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", normalized)
        if match is None:
            return None
        sign = -1 if match.group(1) == "-" else 1
        hours = int(match.group(2))
        minutes = int(match.group(3))
        if hours > 23 or minutes > 59:
            return None
        return sign * (hours * 60 + minutes)

    def _coerce_timezone_offset_minutes(self, name: str, value: Any, index: int) -> int:
        allowed = ["-2359..+2359", "UTC", "GMT", "Z", "+HHMM", "+HH:MM"]
        if isinstance(value, bool):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_one_of_strings(name, index + 1, allowed))
        if isinstance(value, (int, float)):
            offset_minutes = int(value)
        elif isinstance(value, str):
            offset_minutes = self._parse_timezone_offset_minutes(value)
            if offset_minutes is None:
                raise RuntimeError(RuntimeErrorMessages.argument_must_be_one_of_strings(name, index + 1, allowed))
        else:
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_one_of_strings(name, index + 1, allowed))

        if offset_minutes < -(23 * 60 + 59) or offset_minutes > (23 * 60 + 59):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of_strings(
                    name,
                    index + 1,
                    allowed,
                )
            )
        return offset_minutes

    def _parse_date_time_with_timezone_fallback(self, text: str, format_text: str) -> datetime | None:
        normalized_format = format_text.upper()
        normalized_text = text.strip()
        if not normalized_text:
            return None

        fallback_pairs: list[tuple[str, str]] = []
        if "%Z" in normalized_format:
            fallback_pairs.extend(
                [
                    (normalized_text.removesuffix(" UTC").rstrip(), format_text.replace("%Z", "").rstrip()),
                    (normalized_text.removesuffix(" GMT").rstrip(), format_text.replace("%Z", "").rstrip()),
                    (normalized_text.removesuffix(" Z").rstrip(), format_text.replace("%Z", "").rstrip()),
                ]
            )
        if "%z" in normalized_format:
            fallback_pairs.extend(
                [
                    (normalized_text.removesuffix(" UTC").rstrip() + " +0000", format_text.replace("%z", "%z")),
                    (normalized_text.removesuffix(" GMT").rstrip() + " +0000", format_text.replace("%z", "%z")),
                    (normalized_text.removesuffix("Z").rstrip() + "+0000", format_text.replace("%z", "%z")),
                ]
            )

        for candidate_text, candidate_format in fallback_pairs:
            if not candidate_text or not candidate_format:
                continue
            try:
                return datetime.strptime(candidate_text, candidate_format)
            except ValueError:
                continue
        return None

    def _format_date_time(self, args: list[Any], _context: ExecutionContext) -> str:
        format_text = self._require_string_value("FormatDateTime", args, 1)
        local_datetime = self._coerce_date_time_value("FormatDateTime", args[0], 1)
        try:
            return local_datetime.strftime(format_text)
        except ValueError:
            raise RuntimeError(RuntimeErrorMessages.invalid_date_time_text("FormatDateTime", format_text)) from None

    def _format_date_time_in_offset(self, args: list[Any], _context: ExecutionContext) -> str:
        format_text = self._require_string_value("FormatDateTimeInOffset", args, 1)
        offset_minutes = self._coerce_timezone_offset_minutes("FormatDateTimeInOffset", args[2], 2)
        offset_timezone = timezone(timedelta(minutes=offset_minutes))
        offset_datetime = self._coerce_date_time_value_in_offset(
            "FormatDateTimeInOffset",
            args[0],
            1,
            offset_timezone,
        )
        try:
            return offset_datetime.strftime(format_text)
        except ValueError:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_date_time_text("FormatDateTimeInOffset", format_text)
            ) from None

    def _coerce_date_time_value(self, name: str, value: Any, index: int) -> datetime:
        if isinstance(value, StructInstance):
            if value.struct_name != "tm":
                raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
            return self._datetime_from_tm_struct(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
        return self._local_datetime_from_epoch(value)

    def _coerce_date_time_value_in_offset(self, name: str, value: Any, index: int, offset_timezone: timezone) -> datetime:
        if isinstance(value, StructInstance):
            if value.struct_name != "tm":
                raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
            return self._datetime_from_tm_struct(value).replace(tzinfo=offset_timezone)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
        return datetime.fromtimestamp(value, tz=timezone.utc).astimezone(offset_timezone)

    def _date_add(self, args: list[Any], _context: ExecutionContext) -> int:
        start_epoch = self._require_numeric_value("DateAdd", args, 0)
        amount = self._require_numeric_value("DateAdd", args, 1)
        unit = self._normalize_date_time_unit("DateAdd", self._require_string_value("DateAdd", args, 2), 2)

        if unit in _DATE_TIME_UNIT_TO_SECONDS:
            adjusted = self._local_datetime_from_epoch(start_epoch) + timedelta(seconds=float(amount) * _DATE_TIME_UNIT_TO_SECONDS[unit])
            return self._local_epoch_from_datetime(adjusted)

        local_datetime = self._local_datetime_from_epoch(start_epoch)
        months_delta = int(amount) * 12 if unit == "years" else int(amount)
        adjusted = self._shift_local_datetime_by_months(local_datetime, months_delta)
        return self._local_epoch_from_datetime(adjusted)

    def _date_diff(self, args: list[Any], _context: ExecutionContext) -> int:
        start_epoch = self._require_numeric_value("DateDiff", args, 0)
        end_epoch = self._require_numeric_value("DateDiff", args, 1)
        unit = self._normalize_date_time_unit("DateDiff", self._require_string_value("DateDiff", args, 2), 2)

        start_datetime = self._local_datetime_from_epoch(start_epoch)
        end_datetime = self._local_datetime_from_epoch(end_epoch)

        if unit in _DATE_TIME_UNIT_TO_SECONDS:
            delta_seconds = (end_datetime - start_datetime).total_seconds()
            return int(delta_seconds / _DATE_TIME_UNIT_TO_SECONDS[unit])

        start_months = start_datetime.year * 12 + start_datetime.month - 1
        end_months = end_datetime.year * 12 + end_datetime.month - 1
        month_delta = end_months - start_months
        if unit == "years":
            month_delta = int(month_delta / 12)
            candidate = self._shift_local_datetime_by_months(start_datetime, month_delta * 12)
            if end_datetime >= start_datetime and candidate > end_datetime:
                month_delta -= 1
            elif end_datetime < start_datetime and candidate < end_datetime:
                month_delta += 1
            return month_delta

        candidate = self._shift_local_datetime_by_months(start_datetime, month_delta)
        if end_datetime >= start_datetime and candidate > end_datetime:
            month_delta -= 1
        elif end_datetime < start_datetime and candidate < end_datetime:
            month_delta += 1
        return month_delta

    def _convert_time_zone(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("ConvertTimeZone", args, 0)
        from_offset_minutes = self._coerce_timezone_offset_minutes("ConvertTimeZone", args[1], 1)
        to_offset_minutes = self._coerce_timezone_offset_minutes("ConvertTimeZone", args[2], 2)
        return int(epoch_seconds) + ((from_offset_minutes - to_offset_minutes) * 60)

    def _utc_offset(self, args: list[Any], _context: ExecutionContext) -> int:
        epoch_seconds = self._require_numeric_value("UTCOffset", args, 0)
        local_datetime = datetime.fromtimestamp(epoch_seconds)
        utc_datetime = datetime.utcfromtimestamp(epoch_seconds)
        return int((local_datetime - utc_datetime).total_seconds() / 60)

    def _normalize_date_time_unit(self, name: str, unit_text: str, index: int) -> str:
        normalized = unit_text.strip().lower()
        if normalized in _DATE_TIME_UNIT_ALIASES:
            return _DATE_TIME_UNIT_ALIASES[normalized]
        raise RuntimeError(
            RuntimeErrorMessages.argument_must_be_one_of_strings(
                name,
                index + 1,
                ["seconds", "minutes", "hours", "days", "weeks", "months", "years"],
            )
        )

    def _local_datetime_from_epoch(self, epoch_seconds: Any) -> datetime:
        local_time = time.localtime(epoch_seconds)
        return datetime(
            int(local_time.tm_year),
            int(local_time.tm_mon),
            int(local_time.tm_mday),
            int(local_time.tm_hour),
            int(local_time.tm_min),
            int(local_time.tm_sec),
        )

    def _datetime_from_tm_struct(self, tm_value: StructInstance) -> datetime:
        return datetime(
            int(tm_value.tm_year) + 1900,
            int(tm_value.tm_mon) + 1,
            int(tm_value.tm_mday),
            int(tm_value.tm_hour),
            int(tm_value.tm_min),
            int(tm_value.tm_sec),
        )

    def _local_epoch_from_datetime(self, local_datetime: datetime) -> int:
        return int(
            time.mktime(
                (
                    local_datetime.year,
                    local_datetime.month,
                    local_datetime.day,
                    local_datetime.hour,
                    local_datetime.minute,
                    local_datetime.second,
                    0,
                    0,
                    -1,
                )
            )
        )

    def _shift_local_datetime_by_months(self, local_datetime: datetime, months_delta: int) -> datetime:
        total_months = local_datetime.year * 12 + (local_datetime.month - 1) + int(months_delta)
        year = total_months // 12
        month = total_months % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(local_datetime.day, last_day)
        return local_datetime.replace(year=year, month=month, day=day)

    def _try_parse_date_time(self, text: str) -> datetime | None:
        candidate_text = text.strip()
        if not candidate_text:
            return None

        try:
            return datetime.fromisoformat(candidate_text)
        except ValueError:
            pass

        candidate_formats = (
            "%x %X",
            "%x %I:%M:%S %p",
            "%x %H:%M:%S",
            "%x",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
        )
        for candidate_format in candidate_formats:
            try:
                return datetime.strptime(candidate_text, candidate_format)
            except ValueError:
                continue
        return None

    def _try_parse_time_text(self, text: str) -> datetime | None:
        candidate_text = text.strip()
        if not candidate_text:
            return None

        candidate_formats = (
            "%X",
            "%I:%M:%S %p",
            "%H:%M:%S",
            "%I:%M %p",
            "%H:%M",
            "%I %p",
            "%H",
        )
        for candidate_format in candidate_formats:
            try:
                parsed = datetime.strptime(candidate_text, candidate_format)
            except ValueError:
                continue
            return parsed
        return None

    def _format_windows_localized_date(self, current: datetime) -> str:
        if not hasattr(ctypes, "windll"):
            return ""

        system_time = self._to_system_time(current)
        buffer_length = ctypes.windll.kernel32.GetDateFormatW(
            0x0400,
            0,
            ctypes.byref(system_time),
            None,
            None,
            0,
        )
        if buffer_length <= 0:
            return ""

        buffer = ctypes.create_unicode_buffer(buffer_length)
        written = ctypes.windll.kernel32.GetDateFormatW(
            0x0400,
            0,
            ctypes.byref(system_time),
            None,
            buffer,
            buffer_length,
        )
        if written <= 0:
            return ""
        return buffer.value

    def _format_windows_localized_time(self, current: datetime) -> str:
        if not hasattr(ctypes, "windll"):
            return ""

        system_time = self._to_system_time(current)
        buffer_length = ctypes.windll.kernel32.GetTimeFormatW(
            0x0400,
            0,
            ctypes.byref(system_time),
            None,
            None,
            0,
        )
        if buffer_length <= 0:
            return ""

        buffer = ctypes.create_unicode_buffer(buffer_length)
        written = ctypes.windll.kernel32.GetTimeFormatW(
            0x0400,
            0,
            ctypes.byref(system_time),
            None,
            buffer,
            buffer_length,
        )
        if written <= 0:
            return ""
        return buffer.value

    def _format_local_date_time_string(self, current: datetime) -> str:
        if os.name == "nt":
            localized_date = self._format_windows_localized_date(current)
            localized_time = self._format_windows_localized_time(current)
            if localized_date and localized_time:
                return f"{localized_date} {localized_time}"
        return current.strftime("%x %X")

    def _format_utc_date_time_string(self, current: datetime) -> str:
        return current.strftime("%Y-%m-%d %H:%M:%S UTC")

    def _coerce_local_datetime_value(self, name: str, value: Any, index: int) -> datetime:
        if isinstance(value, StructInstance):
            if value.struct_name != "tm":
                raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
            return self._datetime_from_tm_struct(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
        return self._local_datetime_from_epoch(value)

    def _coerce_utc_datetime_value(self, name: str, value: Any, index: int) -> datetime:
        if isinstance(value, StructInstance):
            if value.struct_name != "tm":
                raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
            local_datetime = self._datetime_from_tm_struct(value)
            return datetime.utcfromtimestamp(self._local_epoch_from_datetime(local_datetime))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_datetime_value(name, index))
        return datetime.utcfromtimestamp(float(value))

    def _to_system_time(self, current: datetime) -> "SYSTEMTIME":
        return SYSTEMTIME(
            current.year,
            current.month,
            (current.weekday() + 1) % 7,
            current.day,
            current.hour,
            current.minute,
            current.second,
            current.microsecond // 1000,
        )

    def _require_string_value(self, name: str, args: list[Any], index: int) -> str:
        value = args[index]
        if not isinstance(value, str):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_string(name, index + 1))
        return value

    def _coerce_int(self, value: Any, name: str, index: int) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_integer(name, index))
        return int(value)

    def _coerce_uint32(self, value: Any, name: str, index: int) -> int:
        return self._coerce_int(value, name, index) & 0xFFFFFFFF

    def _to_signed_int32(self, value: int) -> int:
        masked = int(value) & 0xFFFFFFFF
        if masked >= 0x80000000:
            return masked - 0x100000000
        return masked

    def _key_press(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("KeyPress", args, 1, 2)

        key = self._coerce_non_empty_string(args[0], "KeyPress", 1)
        repeat_count = 1
        if len(args) == 2:
            repeat_count = self._require_int_value("KeyPress", args, 1)
            if repeat_count < 0:
                raise RuntimeError(
                    RuntimeErrorMessages.argument_must_be_at_least("KeyPress", 2, 0)
                )
            if repeat_count == 0:
                return None

        self._emit_key_taps(context, key, repeat_count)
        return None

    def _send_keys(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("SendKeys", args, 1, 2)
        sequence = self._coerce_strict_string(args[0], "SendKeys", 1)
        delay_ms = 0
        if len(args) == 2:
            delay_ms = self._require_int_value("SendKeys", args, 1)
            if delay_ms < 0:
                raise RuntimeError(
                    RuntimeErrorMessages.argument_must_be_at_least("SendKeys", 2, 0)
                )

        self._emit_sendkeys_sequence(sequence, context, delay_ms=delay_ms)
        return None

    def _key_toggle(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_count("KeyToggle", args, 2)

        lock_key = self._coerce_non_empty_string(args[0], "KeyToggle", 1).lower()
        state = self._coerce_non_empty_string(args[1], "KeyToggle", 2).lower()

        allowed_keys = ("capslock", "numlock", "scrolllock")
        if lock_key not in allowed_keys:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of_strings(
                    "KeyToggle",
                    1,
                    allowed_keys,
                )
            )

        allowed_states = ("on", "off", "toggle")
        if state not in allowed_states:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of_strings(
                    "KeyToggle",
                    2,
                    allowed_states,
                )
            )

        context.call_host_service("keytoggle", key=lock_key, state=state)
        return None

    def _msgbox(self, args: list[Any], context: ExecutionContext) -> int:
        if len(args) < 3 or len(args) > 5:
            raise RuntimeError(
                RuntimeErrorMessages.expects_argument_range("MsgBox", 3, 5)
            )

        flag = self._require_int_value("MsgBox", args, 0)
        title = self._coerce_display_string(args[1], "MsgBox", 2)
        text = self._coerce_display_string(args[2], "MsgBox", 3)

        timeout = 0
        if len(args) >= 4:
            timeout = self._require_int_value("MsgBox", args, 3)
            if timeout < 0:
                raise RuntimeError(RuntimeErrorMessages.MSGBOX_TIMEOUT_MUST_BE_NON_NEGATIVE)

        hwnd: int | None = None
        if len(args) >= 5 and args[4] is not None:
            hwnd = self._require_int_value("MsgBox", args, 4)

        result = context.call_host_service(
            "msgbox",
            flag=flag,
            title=title,
            text=text,
            timeout=timeout,
            hwnd=hwnd,
        )
        return self._coerce_host_service_integer("msgbox", result)

    def _pixel_get_color(self, args: list[Any], context: ExecutionContext) -> int:
        if len(args) not in (2, 3):
            raise RuntimeError(
                RuntimeErrorMessages.expects_argument_counts("PixelGetColor", 2, 3)
            )

        x = self._require_int_value("PixelGetColor", args, 0)
        y = self._require_int_value("PixelGetColor", args, 1)

        hwnd: int | None = None
        if len(args) == 3 and args[2] is not None:
            hwnd = self._require_int_value("PixelGetColor", args, 2)

        result = context.call_host_service(
            "pixelgetcolor",
            x=x,
            y=y,
            hwnd=hwnd,
        )
        return self._coerce_host_service_integer("pixelgetcolor", result)

    def _pixel_search(self, args: list[Any], context: ExecutionContext) -> list[int] | None:
        if len(args) < 5 or len(args) > 8:
            raise RuntimeError(
                RuntimeErrorMessages.expects_argument_range("PixelSearch", 5, 8)
            )

        left = self._require_int_value("PixelSearch", args, 0)
        top = self._require_int_value("PixelSearch", args, 1)
        right = self._require_int_value("PixelSearch", args, 2)
        bottom = self._require_int_value("PixelSearch", args, 3)
        color = self._require_int_value("PixelSearch", args, 4)

        shade_variation = 0
        if len(args) >= 6:
            shade_variation = self._require_int_value("PixelSearch", args, 5)
            if shade_variation < 0 or shade_variation > 255:
                raise RuntimeError(
                    RuntimeErrorMessages.PIXEL_SEARCH_SHADE_VARIATION_RANGE
                )

        step = 1
        if len(args) >= 7:
            step = self._require_int_value("PixelSearch", args, 6)
            if step < 1:
                raise RuntimeError(
                    RuntimeErrorMessages.PIXEL_SEARCH_STEP_MUST_BE_AT_LEAST_1
                )

        hwnd: int | None = None
        if len(args) >= 8 and args[7] is not None:
            hwnd = self._require_int_value("PixelSearch", args, 7)

        result = context.call_host_service(
            "pixelsearch",
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            color=color,
            shade_variation=shade_variation,
            step=step,
            hwnd=hwnd,
        )

        if result is None:
            self._set_runtime_error(context, 1)
            return None

        if isinstance(result, (list, tuple)) and len(result) == 2:
            try:
                return [
                    self._coerce_host_service_integer("pixelsearch", result[0]),
                    self._coerce_host_service_integer("pixelsearch", result[1]),
                ]
            except RuntimeError as exc:
                if "must return an integer" in str(exc):
                    raise RuntimeError(
                        RuntimeErrorMessages.host_service_must_return_point_pair("pixelsearch")
                    ) from None
                raise

        raise RuntimeError(
            RuntimeErrorMessages.host_service_must_return_point_pair("pixelsearch")
        )

    def _get_monitor_info(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        return self._get_monitor_info_struct(
            builtin_name="GetMonitorInfo",
            host_service_name="getmonitorinfo",
            struct_name="MonitorInfo",
            args=args,
            context=context,
        )

    def _get_monitor_info_ex(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        return self._get_monitor_info_struct(
            builtin_name="GetMonitorInfoEx",
            host_service_name="getmonitorinfoex",
            struct_name="MonitorInfoEx",
            args=args,
            context=context,
        )

    def _get_cursor_pos(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        self._expect_arg_count("GetCursorPos", args, 0)

        payload = context.call_host_service("getcursorpos")
        if not isinstance(payload, dict):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_point("getcursorpos")
            )

        if not context.has_struct("Point"):
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined("Point"))

        return self._build_struct_instance_from_payload("Point", payload, context)

    def _get_window_rect(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        self._expect_arg_count("GetWindowRect", args, 1)
        hwnd = self._require_int_value("GetWindowRect", args, 0)

        payload = context.call_host_service("getwindowrect", hwnd=hwnd)
        if not isinstance(payload, dict):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_rect("getwindowrect")
            )

        if not context.has_struct("Rect"):
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined("Rect"))

        return self._build_struct_instance_from_payload("Rect", payload, context)

    def _get_client_rect(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        self._expect_arg_count("GetClientRect", args, 1)
        hwnd = self._require_int_value("GetClientRect", args, 0)

        payload = context.call_host_service("getclientrect", hwnd=hwnd)
        if not isinstance(payload, dict):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_client_rect("getclientrect")
            )

        if not context.has_struct("Rect"):
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined("Rect"))

        return self._build_struct_instance_from_payload("Rect", payload, context)

    def _get_window_text(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("GetWindowText", args, 1)
        hwnd = self._require_int_value("GetWindowText", args, 0)

        payload = context.call_host_service("getwindowtext", hwnd=hwnd)
        if not isinstance(payload, str):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_string("getwindowtext")
            )

        return payload

    def _get_window_long_ptr(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("GetWindowLongPtr", args, 2)
        hwnd = self._require_int_value("GetWindowLongPtr", args, 0)
        index = self._require_int_value("GetWindowLongPtr", args, 1)

        payload = context.call_host_service("getwindowlongptr", hwnd=hwnd, index=index)
        if not isinstance(payload, int) or isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_integer("getwindowlongptr")
            )

        return int(payload)

    def _get_parent(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("GetParent", args, 1)
        hwnd = self._require_int_value("GetParent", args, 0)

        payload = context.call_host_service("getparent", hwnd=hwnd)
        if not isinstance(payload, int) or isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_integer("getparent")
            )

        return int(payload)

    def _get_class_name(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("GetClassName", args, 1)
        hwnd = self._require_int_value("GetClassName", args, 0)

        payload = context.call_host_service("getclassname", hwnd=hwnd)
        if not isinstance(payload, str):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_class_name("getclassname")
            )

        return payload

    def _get_is_zoomed(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("IsZoomed", args, 1)
        hwnd = self._require_int_value("IsZoomed", args, 0)

        payload = context.call_host_service("iszoomed", hwnd=hwnd)
        if not isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_bool("iszoomed")
            )

        return payload

    def _get_is_iconic(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("IsIconic", args, 1)
        hwnd = self._require_int_value("IsIconic", args, 0)

        payload = context.call_host_service("isiconic", hwnd=hwnd)
        if not isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_bool("isiconic")
            )

        return payload

    def _get_is_window_visible(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("IsWindowVisible", args, 1)
        hwnd = self._require_int_value("IsWindowVisible", args, 0)

        payload = context.call_host_service("iswindowvisible", hwnd=hwnd)
        if not isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_bool("iswindowvisible")
            )

        return payload

    def _get_is_window_enabled(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("IsWindowEnabled", args, 1)
        hwnd = self._require_int_value("IsWindowEnabled", args, 0)

        payload = context.call_host_service("iswindowenabled", hwnd=hwnd)
        if not isinstance(payload, bool):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_bool("iswindowenabled")
            )

        return payload

    def _get_window_placement(self, args: list[Any], context: ExecutionContext) -> StructInstance:
        self._expect_arg_count("GetWindowPlacement", args, 1)
        hwnd = self._require_int_value("GetWindowPlacement", args, 0)

        payload = context.call_host_service("getwindowplacement", hwnd=hwnd)
        if not isinstance(payload, dict):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_window_placement(
                    "getwindowplacement"
                )
            )

        if not context.has_struct("WindowPlacement"):
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined("WindowPlacement"))

        return self._build_struct_instance_from_payload("WindowPlacement", payload, context)

    def _get_monitor_info_struct(
        self,
        *,
        builtin_name: str,
        host_service_name: str,
        struct_name: str,
        args: list[Any],
        context: ExecutionContext,
    ) -> StructInstance:
        self._expect_arg_count(builtin_name, args, 1)
        hmonitor = self._require_int_value(builtin_name, args, 0)

        payload = context.call_host_service(host_service_name, hmonitor=hmonitor)
        if not isinstance(payload, dict):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_must_return_monitor_info(
                    host_service_name
                )
            )

        if not context.has_struct(struct_name):
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined(struct_name))

        return self._build_struct_instance_from_payload(struct_name, payload, context)

    def _build_struct_instance_from_payload(
        self,
        struct_name: str,
        payload: dict[str, object],
        context: ExecutionContext,
    ) -> StructInstance:
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Host service payload for {struct_name} must be a mapping"
            )

        definition = context.get_struct(struct_name)
        resolved_values: list[Any] = []
        for field in definition.fields:
            if field.name not in payload:
                raise RuntimeError(
                    f"Host service payload for {struct_name} is missing field '{field.name}'"
                )

            field_value = payload[field.name]
            field_type_name = normalize_type_name(field.type_name)
            if context.has_struct(field_type_name):
                if not isinstance(field_value, dict):
                    raise RuntimeError(
                        f"Host service payload for {struct_name}.{field.name} must be a mapping"
                    )
                resolved_values.append(
                    self._build_struct_instance_from_payload(
                        field_type_name,
                        field_value,
                        context,
                    )
                )
                continue

            resolved_values.append(
                self._validate_struct_field_value(
                    struct_name,
                    field,
                    field_value,
                    context,
                )
            )

        return build_struct_instance(definition, resolved_values)

    def _mouse_click_drag(self, args: list[Any], context: ExecutionContext) -> None:
        if len(args) not in (5, 6):
            raise RuntimeError(
                RuntimeErrorMessages.MOUSE_CLICK_DRAG_EXPECTS_5_OR_6_ARGUMENTS
            )

        button = self._coerce_button(args[0], "MouseClickDrag", 1)
        start_x = self._require_int_value("MouseClickDrag", args, 1)
        start_y = self._require_int_value("MouseClickDrag", args, 2)
        end_x = self._require_int_value("MouseClickDrag", args, 3)
        end_y = self._require_int_value("MouseClickDrag", args, 4)

        move_event: dict[str, Any] = {"type": "mouse_move", "x": end_x, "y": end_y}
        if len(args) == 6:
            move_event["speed"] = self._coerce_mouse_speed(args[5], "MouseClickDrag", 6)

        context.emit_event(
            {"type": "mouse_down", "button": button, "x": start_x, "y": start_y}
        )
        context.emit_event(self._apply_mouse_speed_override(move_event, context))
        context.emit_event({"type": "mouse_up", "button": button, "x": end_x, "y": end_y})

    def _mouse_drag(self, args: list[Any], context: ExecutionContext) -> None:
        if len(args) not in (6, 7):
            raise RuntimeError(RuntimeErrorMessages.MOUSE_DRAG_EXPECTS_6_OR_7_ARGUMENTS)

        button = self._coerce_button(args[0], "MouseDrag", 1)
        start_x = self._require_int_value("MouseDrag", args, 1)
        start_y = self._require_int_value("MouseDrag", args, 2)
        end_x = self._require_int_value("MouseDrag", args, 3)
        end_y = self._require_int_value("MouseDrag", args, 4)
        duration_ms = self._require_int_value("MouseDrag", args, 5)

        if duration_ms < 0:
            raise RuntimeError(RuntimeErrorMessages.MOUSE_DRAG_DURATION_MUST_BE_NON_NEGATIVE)

        path_points = self._coerce_drag_path_points(
            args[6] if len(args) == 7 else None,
            "MouseDrag",
            7,
            start=(start_x, start_y),
            end=(end_x, end_y),
        )

        context.emit_event(
            {"type": "mouse_down", "button": button, "x": start_x, "y": start_y}
        )

        drag_steps = self._build_drag_steps(path_points, duration_ms)
        for step_duration_ms, point_x, point_y in drag_steps:
            if step_duration_ms > 0.0:
                delay_ms = int(round(step_duration_ms))
                if delay_ms <= 0:
                    delay_ms = 1
                context.emit_event({"type": "delay", "duration_ms": delay_ms})
            context.emit_event({"type": "mouse_move", "x": point_x, "y": point_y})

        if not drag_steps and duration_ms > 0:
            context.emit_event({"type": "delay", "duration_ms": duration_ms})

        context.emit_event({"type": "mouse_up", "button": button, "x": end_x, "y": end_y})

    def _emit_key_taps(
        self,
        context: ExecutionContext,
        key: str,
        repeat_count: int = 1,
        *,
        delay_ms: int = 0,
    ) -> None:
        repeat_count = max(0, int(repeat_count))
        delay_ms = max(0, int(delay_ms))
        for index in range(repeat_count):
            context.emit_event({"type": "key", "key": key})
            if delay_ms > 0 and index + 1 < repeat_count:
                self._emit_sendkeys_delay(context, delay_ms)

    def _sendkeys_use_key_taps(self, context: ExecutionContext) -> bool:
        return bool(
            context.has_special_value("PlaybackSendKeyTapsInsteadOfText")
            and context.get_special_value("PlaybackSendKeyTapsInsteadOfText")
        )

    def _emit_hotkey_events(
        self,
        context: ExecutionContext,
        modifiers: list[str],
        final_key: str,
        repeat_count: int = 1,
        *,
        delay_ms: int = 0,
    ) -> None:
        repeat_count = max(0, int(repeat_count))
        delay_ms = max(0, int(delay_ms))
        for index in range(repeat_count):
            for key in modifiers:
                context.emit_event({"type": "key_down", "key": key})
            context.emit_event({"type": "key", "key": final_key})
            for key in reversed(modifiers):
                context.emit_event({"type": "key_up", "key": key})
            if delay_ms > 0 and index + 1 < repeat_count:
                self._emit_sendkeys_delay(context, delay_ms)

    def _emit_sendkeys_sequence(
        self,
        sequence: str,
        context: ExecutionContext,
        *,
        delay_ms: int = 0,
    ) -> None:
        delay_ms = max(0, int(delay_ms))
        use_key_taps = self._sendkeys_use_key_taps(context)
        if delay_ms <= 0:
            self._emit_sendkeys_sequence_without_delay(
                sequence,
                context,
                use_key_taps=use_key_taps,
            )
            return

        index = 0
        pending_modifiers: list[str] = []

        while index < len(sequence):
            char = sequence[index]

            if char == "{" and index + 1 < len(sequence) and sequence[index + 1] == "{":
                if pending_modifiers:
                    self._emit_hotkey_events(context, pending_modifiers, "{", 1)
                    pending_modifiers.clear()
                else:
                    self._emit_sendkeys_literal_character(
                        context,
                        "{",
                        use_key_taps=use_key_taps,
                    )
                index += 2
                if index < len(sequence):
                    self._emit_sendkeys_delay(context, delay_ms)
                continue

            if char == "}" and index + 1 < len(sequence) and sequence[index + 1] == "}":
                if pending_modifiers:
                    self._emit_hotkey_events(context, pending_modifiers, "}", 1)
                    pending_modifiers.clear()
                else:
                    self._emit_sendkeys_literal_character(
                        context,
                        "}",
                        use_key_taps=use_key_taps,
                    )
                index += 2
                if index < len(sequence):
                    self._emit_sendkeys_delay(context, delay_ms)
                continue

            if char in "^!+":
                pending_modifiers.append(
                    {
                        "^": "ctrl",
                        "!": "alt",
                        "+": "shift",
                    }[char]
                )
                index += 1
                if index >= len(sequence):
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence(
                            "modifier prefix must be followed by a key"
                        )
                    )
                continue

            if char == "{":
                closing_index = sequence.find("}", index + 1)
                if closing_index == -1:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence(
                            "missing closing '}'"
                        )
                    )

                token_body = sequence[index + 1 : closing_index].strip()
                if not token_body:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence("empty brace token")
                    )

                self._emit_sendkeys_token(
                    context,
                    token_body,
                    pending_modifiers,
                    delay_ms=delay_ms,
                )
                pending_modifiers.clear()
                index = closing_index + 1
                if index < len(sequence):
                    self._emit_sendkeys_delay(context, delay_ms)
                continue

            if pending_modifiers:
                self._emit_hotkey_events(context, pending_modifiers, char, 1)
                pending_modifiers.clear()
            else:
                self._emit_sendkeys_literal_character(
                    context,
                    char,
                    use_key_taps=use_key_taps,
                )
            index += 1
            if index < len(sequence):
                self._emit_sendkeys_delay(context, delay_ms)

        if pending_modifiers:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    "modifier prefix must be followed by a key"
                )
            )

    def _emit_sendkeys_sequence_without_delay(
        self,
        sequence: str,
        context: ExecutionContext,
        *,
        use_key_taps: bool = False,
    ) -> None:
        text_buffer: list[str] = []
        pending_modifiers: list[str] = []
        index = 0

        def flush_text() -> None:
            if not text_buffer:
                return
            if use_key_taps:
                for char in text_buffer:
                    self._emit_sendkeys_literal_character(
                        context,
                        char,
                        use_key_taps=True,
                    )
            else:
                context.emit_event({"type": "text", "text": "".join(text_buffer)})
            text_buffer.clear()

        while index < len(sequence):
            char = sequence[index]

            if char == "{" and index + 1 < len(sequence) and sequence[index + 1] == "{":
                if pending_modifiers:
                    flush_text()
                    self._emit_hotkey_events(context, pending_modifiers, "{", 1)
                    pending_modifiers.clear()
                else:
                    text_buffer.append("{")
                index += 2
                continue

            if char == "}" and index + 1 < len(sequence) and sequence[index + 1] == "}":
                if pending_modifiers:
                    flush_text()
                    self._emit_hotkey_events(context, pending_modifiers, "}", 1)
                    pending_modifiers.clear()
                else:
                    text_buffer.append("}")
                index += 2
                continue

            if char in "^!+":
                flush_text()
                pending_modifiers.append(
                    {
                        "^": "ctrl",
                        "!": "alt",
                        "+": "shift",
                    }[char]
                )
                index += 1
                if index >= len(sequence):
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence(
                            "modifier prefix must be followed by a key"
                        )
                    )
                continue

            if char == "{":
                flush_text()
                closing_index = sequence.find("}", index + 1)
                if closing_index == -1:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence(
                            "missing closing '}'"
                        )
                    )

                token_body = sequence[index + 1 : closing_index].strip()
                if not token_body:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence("empty brace token")
                    )

                self._emit_sendkeys_token(context, token_body, pending_modifiers)
                pending_modifiers.clear()
                index = closing_index + 1
                continue

            if char == "}":
                raise RuntimeError(
                    RuntimeErrorMessages.invalid_sendkeys_sequence("unmatched '}'")
                )

            if pending_modifiers:
                flush_text()
                self._emit_hotkey_events(context, pending_modifiers, char, 1)
                pending_modifiers.clear()
            else:
                text_buffer.append(char)
            index += 1

        if pending_modifiers:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    "modifier prefix must be followed by a key"
                )
            )

        flush_text()

    def _emit_sendkeys_token(
        self,
        context: ExecutionContext,
        token_body: str,
        pending_modifiers: list[str],
        *,
        delay_ms: int = 0,
    ) -> None:
        upper_body = token_body.upper()
        if upper_body == "ASC":
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence("ASC requires a code")
            )
        if upper_body.startswith("ASC "):
            self._emit_sendkeys_asc_token(context, token_body[4:].strip())
            return

        parts = token_body.split()
        if not parts:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence("empty brace token")
            )

        key_name = self._normalize_sendkeys_key(parts[0])
        if len(parts) == 1:
            if pending_modifiers:
                self._emit_hotkey_events(
                    context,
                    pending_modifiers,
                    key_name,
                    1,
                    delay_ms=delay_ms,
                )
                return
            self._emit_key_taps(context, key_name, 1)
            return

        if len(parts) == 2:
            command = parts[1].lower()
            if command in {"down", "up"}:
                if pending_modifiers:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_sendkeys_sequence(
                            "modifiers cannot be combined with down/up tokens"
                        )
                    )
                event_type = "key_down" if command == "down" else "key_up"
                context.emit_event({"type": event_type, "key": key_name})
                return

            repeat_count = self._parse_sendkeys_non_negative_int(parts[1], token_body)
            if pending_modifiers:
                self._emit_hotkey_events(
                    context,
                    pending_modifiers,
                    key_name,
                    repeat_count,
                    delay_ms=delay_ms,
                )
                return
            self._emit_key_taps(context, key_name, repeat_count, delay_ms=delay_ms)
            return

        raise RuntimeError(
            RuntimeErrorMessages.invalid_sendkeys_sequence(
                f"unsupported token '{token_body}'"
            )
        )

    def _emit_sendkeys_asc_token(self, context: ExecutionContext, value_text: str) -> None:
        if not value_text:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence("ASC requires a code")
            )
        try:
            code_point = int(value_text, 16 if value_text.lower().startswith("0x") else 10)
        except ValueError:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    f"invalid ASC code '{value_text}'"
                )
            ) from None

        if code_point < 0 or code_point > 0x10FFFF:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    "ASC code must be between 0 and 1114111"
                )
            )
        use_key_taps = self._sendkeys_use_key_taps(context)
        self._emit_sendkeys_literal_character(
            context,
            chr(code_point),
            use_key_taps=use_key_taps,
        )

    def _emit_sendkeys_delay(self, context: ExecutionContext, delay_ms: int) -> None:
        delay_ms = max(0, int(delay_ms))
        if delay_ms <= 0:
            return
        context.emit_event({"type": "delay", "duration_ms": delay_ms})

    def _emit_sendkeys_literal_character(
        self,
        context: ExecutionContext,
        char: str,
        *,
        use_key_taps: bool = False,
    ) -> None:
        if use_key_taps:
            mapped = self._map_sendkeys_printable_character_to_key_events(char)
            if mapped is not None:
                modifiers, key_name = mapped
                if modifiers:
                    self._emit_hotkey_events(context, modifiers, key_name, 1)
                else:
                    self._emit_key_taps(context, key_name, 1)
                return
            context.emit_event({"type": "key", "key": char})
            return
        context.emit_event({"type": "text", "text": char})

    def _map_sendkeys_printable_character_to_key_events(
        self,
        char: str,
    ) -> tuple[list[str], str] | None:
        if len(char) != 1:
            return None

        if char == " ":
            return [], "space"
        if char.isalpha():
            if char.isupper():
                return ["shift"], char.lower()
            return [], char

        mapping: dict[str, tuple[list[str], str]] = {
            "!": (["shift"], "1"),
            '"': (["shift"], "'"),
            "#": (["shift"], "3"),
            "$": (["shift"], "4"),
            "%": (["shift"], "5"),
            "&": (["shift"], "7"),
            "'": ([], "'"),
            "(": (["shift"], "9"),
            ")": (["shift"], "0"),
            "*": (["shift"], "8"),
            "+": (["shift"], "="),
            ",": ([], ","),
            "-": ([], "-"),
            ".": ([], "."),
            "/": ([], "/"),
            ":": (["shift"], ";"),
            ";": ([], ";"),
            "<": (["shift"], ","),
            "=": ([], "="),
            ">": (["shift"], "."),
            "?": (["shift"], "/"),
            "@": (["shift"], "2"),
            "[": ([], "["),
            "\\": ([], "\\"),
            "]": ([], "]"),
            "^": (["shift"], "6"),
            "_": (["shift"], "-"),
            "`": ([], "`"),
            "{": (["shift"], "["),
            "|": (["shift"], "\\"),
            "}": (["shift"], "]"),
            "~": (["shift"], "`"),
        }
        return mapping.get(char)

    def _parse_sendkeys_non_negative_int(self, value_text: str, token_body: str) -> int:
        try:
            value = int(value_text, 10)
        except ValueError:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    f"unsupported token '{token_body}'"
                )
            ) from None
        if value < 0:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_sendkeys_sequence(
                    f"repeat count must be >= 0 in '{token_body}'"
                )
            )
        return value

    def _normalize_sendkeys_key(self, token_key: str) -> str:
        normalized = str(token_key).strip().lower()
        aliases = {
            "del": "delete",
            "delete": "delete",
            "enter": "enter",
            "tab": "tab",
            "esc": "esc",
            "escape": "esc",
            "space": "space",
            "bs": "backspace",
            "backspace": "backspace",
            "pgup": "page_up",
            "pgdn": "page_down",
        }
        if normalized in aliases:
            return aliases[normalized]
        if len(token_key) == 1:
            return token_key
        return normalized

    def _coerce_non_empty_string(self, value: Any, name: str, index: int) -> str:
        if value is None:
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_string(name, index))

        text = str(value).strip()
        if not text:
            raise RuntimeError(RuntimeErrorMessages.argument_must_not_be_empty(name, index))

        return text

    def _coerce_strict_string(self, value: Any, name: str, index: int) -> str:
        if not isinstance(value, str):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_string(name, index))
        return value

    def _coerce_host_service_integer(self, service_name: str, value: Any) -> int:
        try:
            return self._require_int_value(service_name, [value], 0)
        except RuntimeError as exc:
            if "argument 1 must be an integer" in str(exc):
                raise RuntimeError(
                    RuntimeErrorMessages.host_service_must_return_integer(service_name)
                ) from None
            raise

    def _coerce_console_text(self, value: Any) -> str:
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("cp1252", errors="replace")
        if value is None:
            return ""
        return str(value)

    def _coerce_display_text(self, value: Any) -> str:
        if isinstance(value, (bytes, bytearray)):
            return f"<binary:{len(bytes(value))} bytes>"
        if value is None:
            return ""
        return str(value)

    def _coerce_display_string(self, value: Any, name: str, index: int) -> str:
        if value is None:
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_string(name, index))
        return self._coerce_display_text(value)

    def _coerce_binary(self, value: Any, name: str, index: int) -> bytes:
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        raise RuntimeError(RuntimeErrorMessages.argument_must_be_binary(name, index))

    def _coerce_binary_convertible(self, value: Any, name: str, index: int) -> bytes:
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if value is None:
            return b""
        return str(value).encode("cp1252", errors="replace")

    def _coerce_path_arg(self, value: Any, name: str, index: int) -> str:
        return self._coerce_non_empty_string(value, name, index)

    def _coerce_encoding_arg(self, value: Any, name: str, index: int) -> str:
        encoding = self._coerce_non_empty_string(value, name, index)
        try:
            return codecs.lookup(encoding).name
        except LookupError:
            raise RuntimeError(RuntimeErrorMessages.unsupported_encoding(name, encoding)) from None

    def _coerce_mouse_speed(self, value: Any, name: str, index: int) -> int:
        speed = self._require_int_value(name, [value], 0)
        if speed < 0 or speed > 100:
            raise RuntimeError(RuntimeErrorMessages.MOUSE_MOVE_SPEED_RANGE)
        return speed

    def _apply_mouse_speed_override(
        self,
        event: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        if "speed" not in event and context.has_mouse_move_speed_override():
            event["speed"] = context.get_effective_mouse_move_speed()
        return event

    def _coerce_button(self, value: Any, name: str, index: int) -> str:
        button = self._coerce_non_empty_string(value, name, index).lower()
        allowed = {"left", "right", "middle", "x1", "x2"}
        if button not in allowed:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_allowed_button(
                    name,
                    index,
                    allowed,
                )
            )
        return button

    def _coerce_drag_path_points(
        self,
        value: Any,
        name: str,
        index: int,
        *,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> list[tuple[int, int]]:
        if value is None:
            return [start, end]

        if not isinstance(value, list):
            raise RuntimeError(f"{name} argument {index} must be an array of [x, y] points")

        points: list[tuple[int, int]] = []
        for point_index, point in enumerate(value, start=1):
            if not isinstance(point, list) or len(point) != 2:
                raise RuntimeError(f"{name} argument {index} point {point_index} must be [x, y]")

            point_x = self._require_int_value(name, point, 0)
            point_y = self._require_int_value(name, point, 1)
            points.append((point_x, point_y))

        if not points:
            return [start, end]

        if points[0] != start:
            points.insert(0, start)
        if points[-1] != end:
            points.append(end)

        return points

    def _build_drag_steps(
        self,
        points: list[tuple[int, int]],
        duration_ms: int,
    ) -> list[tuple[float, int, int]]:
        if len(points) < 2:
            return []

        segment_lengths: list[float] = []
        total_distance = 0.0
        for index in range(len(points) - 1):
            start_x, start_y = points[index]
            end_x, end_y = points[index + 1]
            distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
            segment_lengths.append(distance)
            total_distance += distance

        if total_distance <= 0.0:
            return []

        steps: list[tuple[float, int, int]] = []
        previous_point = points[0]

        for index, segment_length in enumerate(segment_lengths):
            start_x, start_y = points[index]
            end_x, end_y = points[index + 1]

            segment_duration_ms = (
                (duration_ms * segment_length) / total_distance
                if duration_ms > 0
                else 0.0
            )
            segment_step_count = max(
                1,
                int(round(segment_duration_ms / 15.0)) if segment_duration_ms > 0 else 1,
            )
            step_duration_ms = (
                segment_duration_ms / segment_step_count
                if segment_step_count > 0
                else 0.0
            )

            for step_index in range(1, segment_step_count + 1):
                fraction = step_index / segment_step_count
                point_x = int(round(start_x + ((end_x - start_x) * fraction)))
                point_y = int(round(start_y + ((end_y - start_y) * fraction)))
                current_point = (point_x, point_y)
                if current_point == previous_point:
                    continue
                steps.append((step_duration_ms, point_x, point_y))
                previous_point = current_point

        if steps:
            last_duration_ms, _, _ = steps[-1]
            end_x, end_y = points[-1]
            if (steps[-1][1], steps[-1][2]) != (end_x, end_y):
                steps.append((last_duration_ms, end_x, end_y))

        return steps

    def _ensure_parent_directory_exists(self, path: Path, path_text: str, name: str) -> None:
        parent = path.parent
        if str(parent) in {"", "."}:
            return
        if not parent.exists():
            raise RuntimeError(RuntimeErrorMessages.parent_directory_not_found(name, path_text))
        if not parent.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory(name, str(parent)))

    def _is_valid_host_path(self, path_text: str) -> bool:
        if "\0" in path_text:
            return False

        invalid_chars = '<>"|?*'
        drive, tail = os.path.splitdrive(path_text)
        tail = tail.replace("/", os.sep).replace("\\", os.sep)

        for part in tail.split(os.sep):
            if not part or part == "." or part == "..":
                continue
            if any(ch in invalid_chars for ch in part):
                return False
            if ":" in part:
                return False

        if drive and len(drive) == 2 and drive[1] == ":" and not drive[0].isalpha():
            return False

        try:
            os.path.normpath(path_text)
        except Exception:
            return False
        return True

    def _read_file(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("ReadFile", args, 1, 2)
        path_text = self._coerce_path_arg(args[0], "ReadFile", 1)
        encoding = self._coerce_encoding_arg(args[1], "ReadFile", 2) if len(args) == 2 else "utf-8"
        path = Path(path_text)

        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found("ReadFile", path_text))
        if path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("ReadFile", path_text))

        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            raise RuntimeError(RuntimeErrorMessages.decode_failed("ReadFile", path_text, encoding)) from None
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("ReadFile", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("ReadFile", path_text)) from None

    def _write_file(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("WriteFile", args, 2, 3)
        path_text = self._coerce_path_arg(args[0], "WriteFile", 1)
        text = self._coerce_console_text(args[1])
        encoding = self._coerce_encoding_arg(args[2], "WriteFile", 3) if len(args) == 3 else "utf-8"
        path = Path(path_text)

        self._ensure_parent_directory_exists(path, path_text, "WriteFile")
        if path.exists() and path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("WriteFile", path_text))

        try:
            path.write_text(text, encoding=encoding)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("WriteFile", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("WriteFile", path_text)) from None
        return None

    def _append_file(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("AppendFile", args, 2, 3)
        path_text = self._coerce_path_arg(args[0], "AppendFile", 1)
        text = self._coerce_console_text(args[1])
        encoding = self._coerce_encoding_arg(args[2], "AppendFile", 3) if len(args) == 3 else "utf-8"
        path = Path(path_text)

        self._ensure_parent_directory_exists(path, path_text, "AppendFile")
        if path.exists() and path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("AppendFile", path_text))

        try:
            with path.open("a", encoding=encoding) as handle:
                handle.write(text)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("AppendFile", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("AppendFile", path_text)) from None
        return None

    def _file_exists(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("FileExists", args, 1)
        path_text = self._coerce_path_arg(args[0], "FileExists", 1)
        try:
            return Path(path_text).is_file()
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("FileExists", path_text)) from None

    def _file_size(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("FileSize", args, 1)
        path_text = self._coerce_path_arg(args[0], "FileSize", 1)
        path = Path(path_text)
        stat_result = self._path_stat(path, path_text, "FileSize")
        if path.is_dir():
            total = 0
            try:
                for entry in path.rglob("*"):
                    if entry.is_file():
                        total += entry.stat().st_size
            except PermissionError:
                raise RuntimeError(RuntimeErrorMessages.access_denied("FileSize", path_text)) from None
            except OSError:
                raise RuntimeError(RuntimeErrorMessages.operation_failed("FileSize", path_text)) from None
            return total
        return int(stat_result.st_size)

    def _file_time(self, args: list[Any], context: ExecutionContext) -> float:
        self._expect_arg_counts("FileTime", args, 1, 2)
        path_text = self._coerce_path_arg(args[0], "FileTime", 1)
        kind = "modified" if len(args) == 1 else self._coerce_strict_string(args[1], "FileTime", 2).strip().lower()
        if kind not in {"created", "modified", "accessed"}:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of_strings(
                    "FileTime",
                    2,
                    ("created", "modified", "accessed"),
                )
            )

        path = Path(path_text)
        stat_result = self._path_stat(path, path_text, "FileTime")
        return self._select_path_time(stat_result, kind)

    def _file_info(self, args: list[Any], context: ExecutionContext) -> RecordInstance:
        self._expect_arg_count("FileInfo", args, 1)
        path_text = self._coerce_path_arg(args[0], "FileInfo", 1)
        path = Path(path_text)
        stat_result = self._path_stat(path, path_text, "FileInfo")

        parent = path.parent
        parent_text = "" if str(parent) == "." else str(parent)
        size = self._file_size([path_text], context)
        field_names = (
            "Path",
            "Name",
            "ParentPath",
            "Extension",
            "IsDirectory",
            "Size",
            "CreatedTime",
            "ModifiedTime",
            "AccessedTime",
        )
        values = (
            path_text,
            path.name,
            parent_text,
            path.suffix,
            path.is_dir(),
            size,
            self._select_path_time(stat_result, "created"),
            self._select_path_time(stat_result, "modified"),
            self._select_path_time(stat_result, "accessed"),
        )
        return RecordInstance(record_name="FileInfo", _field_names=field_names, _values=values)

    def _file_hash(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("FileHash", args, 1, 2)
        path_text = self._coerce_path_arg(args[0], "FileHash", 1)
        algorithm = "sha256" if len(args) == 1 else self._coerce_strict_string(args[1], "FileHash", 2).strip().lower()
        allowed_algorithms = ("md5", "sha1", "sha256", "sha512")
        if algorithm not in allowed_algorithms:
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_one_of_strings("FileHash", 2, allowed_algorithms))
        return self._digest_file_contents(path_text, "FileHash", algorithm)

    def _file_checksum(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("FileChecksum", args, 1, 2)
        path_text = self._coerce_path_arg(args[0], "FileChecksum", 1)
        algorithm = "crc32" if len(args) == 1 else self._coerce_strict_string(args[1], "FileChecksum", 2).strip().lower()
        allowed_algorithms = ("crc32", "adler32")
        if algorithm not in allowed_algorithms:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of_strings("FileChecksum", 2, allowed_algorithms)
            )
        return self._digest_file_contents(path_text, "FileChecksum", algorithm)

    def _file_compare(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("FileCompare", args, 2)
        left_text = self._coerce_path_arg(args[0], "FileCompare", 1)
        right_text = self._coerce_path_arg(args[1], "FileCompare", 2)
        left_path = Path(left_text)
        right_path = Path(right_text)

        self._path_compare_validation(left_path, left_text, "FileCompare")
        self._path_compare_validation(right_path, right_text, "FileCompare")

        try:
            with left_path.open("rb") as left_handle, right_path.open("rb") as right_handle:
                while True:
                    left_chunk = left_handle.read(1024 * 1024)
                    right_chunk = right_handle.read(1024 * 1024)
                    if not left_chunk and not right_chunk:
                        return 0
                    if not left_chunk:
                        return -1
                    if not right_chunk:
                        return 1
                    if left_chunk != right_chunk:
                        return -1 if left_chunk < right_chunk else 1
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("FileCompare", left_text if not left_path.exists() else right_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("FileCompare", left_text if not left_path.exists() else right_text)) from None

    def _delete_file(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_count("DeleteFile", args, 1)
        path_text = self._coerce_path_arg(args[0], "DeleteFile", 1)
        path = Path(path_text)

        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found("DeleteFile", path_text))
        if path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("DeleteFile", path_text))

        try:
            path.unlink()
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("DeleteFile", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("DeleteFile", path_text)) from None
        return None

    def _create_dir(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_count("CreateDir", args, 1)
        path_text = self._coerce_path_arg(args[0], "CreateDir", 1)
        path = Path(path_text)

        if path.exists() and not path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory("CreateDir", path_text))

        try:
            path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("CreateDir", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("CreateDir", path_text)) from None
        return None

    def _copy_file(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("CopyFile", args, 2, 3)
        source_text = self._coerce_path_arg(args[0], "CopyFile", 1)
        destination_text = self._coerce_path_arg(args[1], "CopyFile", 2)
        overwrite = bool(self._require_int_value("CopyFile", args, 2)) if len(args) == 3 else False

        source = Path(source_text)
        destination = Path(destination_text)

        if not source.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found("CopyFile", source_text))
        if source.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("CopyFile", source_text))
        if self._paths_refer_to_same_location(source, destination):
            raise RuntimeError(RuntimeErrorMessages.path_already_exists("CopyFile", destination_text))
        if destination.exists():
            if destination.is_dir():
                raise RuntimeError(RuntimeErrorMessages.path_is_directory("CopyFile", destination_text))
            if not overwrite:
                raise RuntimeError(RuntimeErrorMessages.path_already_exists("CopyFile", destination_text))
        else:
            self._ensure_parent_directory_exists(destination, destination_text, "CopyFile")

        try:
            shutil.copy2(source, destination)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("CopyFile", destination_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("CopyFile", destination_text)) from None
        return None

    def _copy_dir(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("CopyDir", args, 2, 3)
        source_text = self._coerce_path_arg(args[0], "CopyDir", 1)
        destination_text = self._coerce_path_arg(args[1], "CopyDir", 2)
        overwrite = bool(self._require_int_value("CopyDir", args, 2)) if len(args) == 3 else False

        source = Path(source_text)
        destination = Path(destination_text)

        if not source.exists():
            raise RuntimeError(RuntimeErrorMessages.directory_not_found("CopyDir", source_text))
        if not source.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory("CopyDir", source_text))
        if self._paths_refer_to_same_location(source, destination):
            raise RuntimeError(RuntimeErrorMessages.path_already_exists("CopyDir", destination_text))
        if destination.exists():
            if not destination.is_dir():
                raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory("CopyDir", destination_text))
            if not overwrite:
                raise RuntimeError(RuntimeErrorMessages.path_already_exists("CopyDir", destination_text))
            try:
                shutil.rmtree(destination)
            except PermissionError:
                raise RuntimeError(RuntimeErrorMessages.access_denied("CopyDir", destination_text)) from None
            except OSError:
                raise RuntimeError(RuntimeErrorMessages.operation_failed("CopyDir", destination_text)) from None
        else:
            self._ensure_parent_directory_exists(destination, destination_text, "CopyDir")

        try:
            shutil.copytree(source, destination)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("CopyDir", destination_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("CopyDir", destination_text)) from None
        return None

    def _move_file(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("MoveFile", args, 2, 3)
        source_text = self._coerce_path_arg(args[0], "MoveFile", 1)
        destination_text = self._coerce_path_arg(args[1], "MoveFile", 2)
        overwrite = bool(self._require_int_value("MoveFile", args, 2)) if len(args) == 3 else False

        source = Path(source_text)
        destination = Path(destination_text)

        if not source.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found("MoveFile", source_text))
        if source.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("MoveFile", source_text))
        if self._paths_refer_to_same_location(source, destination):
            raise RuntimeError(RuntimeErrorMessages.path_already_exists("MoveFile", destination_text))
        if destination.exists():
            if destination.is_dir():
                raise RuntimeError(RuntimeErrorMessages.path_is_directory("MoveFile", destination_text))
            if not overwrite:
                raise RuntimeError(RuntimeErrorMessages.path_already_exists("MoveFile", destination_text))
        else:
            self._ensure_parent_directory_exists(destination, destination_text, "MoveFile")

        try:
            shutil.move(str(source), str(destination))
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("MoveFile", destination_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("MoveFile", destination_text)) from None
        return None

    def _move_dir(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_counts("MoveDir", args, 2, 3)
        source_text = self._coerce_path_arg(args[0], "MoveDir", 1)
        destination_text = self._coerce_path_arg(args[1], "MoveDir", 2)
        overwrite = bool(self._require_int_value("MoveDir", args, 2)) if len(args) == 3 else False

        source = Path(source_text)
        destination = Path(destination_text)

        if not source.exists():
            raise RuntimeError(RuntimeErrorMessages.directory_not_found("MoveDir", source_text))
        if not source.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory("MoveDir", source_text))
        if self._paths_refer_to_same_location(source, destination):
            raise RuntimeError(RuntimeErrorMessages.path_already_exists("MoveDir", destination_text))
        if destination.exists():
            if not destination.is_dir():
                raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory("MoveDir", destination_text))
            if not overwrite:
                raise RuntimeError(RuntimeErrorMessages.path_already_exists("MoveDir", destination_text))
            try:
                shutil.rmtree(destination)
            except PermissionError:
                raise RuntimeError(RuntimeErrorMessages.access_denied("MoveDir", destination_text)) from None
            except OSError:
                raise RuntimeError(RuntimeErrorMessages.operation_failed("MoveDir", destination_text)) from None
        else:
            self._ensure_parent_directory_exists(destination, destination_text, "MoveDir")

        try:
            shutil.move(str(source), str(destination))
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("MoveDir", destination_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("MoveDir", destination_text)) from None
        return None

    def _remove_dir(self, args: list[Any], context: ExecutionContext, name: str) -> None:
        self._expect_arg_counts(name, args, 1, 2)
        path_text = self._coerce_path_arg(args[0], name, 1)
        recursive = False
        if len(args) > 1:
            recursive = bool(self._require_int_value(name, args, 1))

        path = Path(path_text)

        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.directory_not_found(name, path_text))
        if not path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory(name, path_text))

        try:
            if recursive:
                shutil.rmtree(path)
            else:
                path.rmdir()
        except FileNotFoundError:
            raise RuntimeError(RuntimeErrorMessages.directory_not_found(name, path_text)) from None
        except OSError as exc:
            if not recursive and path.exists():
                raise RuntimeError(RuntimeErrorMessages.directory_not_empty(name, path_text)) from None
            raise RuntimeError(RuntimeErrorMessages.operation_failed(name, path_text)) from None
        return None

    def _path_stat(self, path: Path, path_text: str, name: str):
        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.path_not_found(name, path_text))
        try:
            return path.stat()
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied(name, path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed(name, path_text)) from None

    def _path_compare_validation(self, path: Path, path_text: str, name: str) -> None:
        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found(name, path_text))
        if path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory(name, path_text))

    def _digest_file_contents(self, path_text: str, name: str, algorithm: str) -> str:
        path = Path(path_text)
        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found(name, path_text))
        if path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory(name, path_text))

        try:
            with path.open("rb") as handle:
                if algorithm in {"md5", "sha1", "sha256", "sha512"}:
                    hasher = hashlib.new(algorithm)
                    while True:
                        chunk = handle.read(1024 * 1024)
                        if not chunk:
                            break
                        hasher.update(chunk)
                    return hasher.hexdigest().lower()

                checksum = 0 if algorithm == "crc32" else 1
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    if algorithm == "crc32":
                        checksum = zlib.crc32(chunk, checksum)
                    else:
                        checksum = zlib.adler32(chunk, checksum)
                return f"{checksum & 0xFFFFFFFF:08x}"
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied(name, path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed(name, path_text)) from None

    def _select_path_time(self, stat_result, kind: str) -> float:
        if kind == "created":
            return float(stat_result.st_ctime)
        if kind == "accessed":
            return float(stat_result.st_atime)
        return float(stat_result.st_mtime)

    def _dir_exists(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("DirExists", args, 1)
        path_text = self._coerce_path_arg(args[0], "DirExists", 1)
        try:
            return Path(path_text).is_dir()
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("DirExists", path_text)) from None

    def _path_exists(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("PathExists", args, 1)
        path_text = self._coerce_path_arg(args[0], "PathExists", 1)
        try:
            return Path(path_text).exists()
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("PathExists", path_text)) from None

    def _paths_refer_to_same_location(self, left: Path, right: Path) -> bool:
        left_key = os.path.normcase(str(left.resolve(strict=False)))
        right_key = os.path.normcase(str(right.resolve(strict=False)))
        return left_key == right_key

    def _path_combine(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_at_least_arg_count("PathCombine", args, 2)
        parts = [
            self._coerce_path_arg(value, "PathCombine", index)
            for index, value in enumerate(args, start=1)
        ]
        return os.path.join(*parts)

    def _path_normalize(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("PathNormalize", args, 1)
        path_text = self._coerce_path_arg(args[0], "PathNormalize", 1)
        return os.path.normpath(path_text)

    def _is_path_valid(self, args: list[Any], context: ExecutionContext) -> bool:
        self._expect_arg_count("IsPathValid", args, 1)
        path_text = self._coerce_path_arg(args[0], "IsPathValid", 1)
        return self._is_valid_host_path(path_text)

    def _file_name(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("FileName", args, 1)
        path_text = self._coerce_path_arg(args[0], "FileName", 1)
        return Path(path_text).name

    def _directory_name(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("DirectoryName", args, 1)
        path_text = self._coerce_path_arg(args[0], "DirectoryName", 1)
        parent = Path(path_text).parent
        if str(parent) == ".":
            return ""
        return str(parent)

    def _directory_list(
        self,
        args: list[Any],
        context: ExecutionContext,
        name: str,
        *,
        want_directories: bool,
    ) -> list[str]:
        self._expect_arg_counts(name, args, 1, 2)
        path_text = self._coerce_path_arg(args[0], name, 1)
        pattern = "*" if len(args) == 1 else self._coerce_strict_string(args[1], name, 2)
        root = Path(path_text)

        if not root.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found(name, path_text))
        if not root.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory(name, path_text))

        try:
            entries = list(root.iterdir())
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied(name, path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed(name, path_text)) from None

        matched_paths: list[str] = []
        for entry in entries:
            is_match_target = entry.is_dir() if want_directories else entry.is_file()
            if not is_match_target:
                continue
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                continue
            matched_paths.append(str(entry))

        matched_paths.sort(key=lambda item: Path(item).name.casefold())
        return matched_paths

    def _traverse_directory(
        self,
        args: list[Any],
        context: ExecutionContext,
        name: str,
        *,
        want_directories: bool,
    ) -> list[str]:
        self._expect_arg_counts(name, args, 1, 2)
        path_text = self._coerce_path_arg(args[0], name, 1)
        pattern = "*" if len(args) == 1 else self._coerce_strict_string(args[1], name, 2)
        root = Path(path_text)

        if not root.exists():
            raise RuntimeError(RuntimeErrorMessages.directory_not_found(name, path_text))
        if not root.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_exists_and_is_not_directory(name, path_text))

        try:
            entries = list(root.rglob("*"))
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied(name, path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed(name, path_text)) from None

        matched_paths: list[str] = []
        for entry in entries:
            is_match_target = entry.is_dir() if want_directories else entry.is_file()
            if not is_match_target:
                continue
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                continue
            matched_paths.append(str(entry))

        matched_paths.sort(key=lambda item: Path(item).relative_to(root).as_posix().casefold())
        return matched_paths

    def _extension_name(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("ExtensionName", args, 1)
        path_text = self._coerce_path_arg(args[0], "ExtensionName", 1)
        return Path(path_text).suffix

    def _read_bytes(self, args: list[Any], context: ExecutionContext) -> bytes:
        self._expect_arg_count("ReadBytes", args, 1)
        path_text = self._coerce_path_arg(args[0], "ReadBytes", 1)
        path = Path(path_text)

        if not path.exists():
            raise RuntimeError(RuntimeErrorMessages.file_not_found("ReadBytes", path_text))
        if path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("ReadBytes", path_text))

        try:
            return path.read_bytes()
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("ReadBytes", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("ReadBytes", path_text)) from None

    def _write_bytes(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_count("WriteBytes", args, 2)
        path_text = self._coerce_path_arg(args[0], "WriteBytes", 1)
        data = self._coerce_binary(args[1], "WriteBytes", 2)
        path = Path(path_text)

        self._ensure_parent_directory_exists(path, path_text, "WriteBytes")
        if path.exists() and path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("WriteBytes", path_text))

        try:
            path.write_bytes(data)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("WriteBytes", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("WriteBytes", path_text)) from None
        return None

    def _append_bytes(self, args: list[Any], context: ExecutionContext) -> None:
        self._expect_arg_count("AppendBytes", args, 2)
        path_text = self._coerce_path_arg(args[0], "AppendBytes", 1)
        data = self._coerce_binary(args[1], "AppendBytes", 2)
        path = Path(path_text)

        self._ensure_parent_directory_exists(path, path_text, "AppendBytes")
        if path.exists() and path.is_dir():
            raise RuntimeError(RuntimeErrorMessages.path_is_directory("AppendBytes", path_text))

        try:
            with path.open("ab") as handle:
                handle.write(data)
        except PermissionError:
            raise RuntimeError(RuntimeErrorMessages.access_denied("AppendBytes", path_text)) from None
        except OSError:
            raise RuntimeError(RuntimeErrorMessages.operation_failed("AppendBytes", path_text)) from None
        return None

    def _binary_length(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("BinaryLength", args, 1)
        return len(self._coerce_binary(args[0], "BinaryLength", 1))

    def _hex(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("Hex", args, 1)
        return self._coerce_binary(args[0], "Hex", 1).hex()

    def _from_hex(self, args: list[Any], context: ExecutionContext) -> bytes:
        self._expect_arg_count("FromHex", args, 1)
        text = self._coerce_strict_string(args[0], "FromHex", 1).strip()
        try:
            return bytes.fromhex(text)
        except ValueError:
            raise RuntimeError(RuntimeErrorMessages.invalid_hex_text("FromHex")) from None

    def _base64(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("Base64", args, 1)
        data = self._coerce_binary(args[0], "Base64", 1)
        return base64.b64encode(data).decode("ascii")

    def _from_base64(self, args: list[Any], context: ExecutionContext) -> bytes:
        self._expect_arg_count("FromBase64", args, 1)
        text = self._coerce_strict_string(args[0], "FromBase64", 1).strip()
        try:
            return base64.b64decode(text.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError, binascii.Error):
            raise RuntimeError(RuntimeErrorMessages.invalid_base64_text("FromBase64")) from None

    def _binary(self, args: list[Any], context: ExecutionContext) -> bytes:
        self._expect_arg_count("Binary", args, 1)
        return self._coerce_binary_convertible(args[0], "Binary", 1)

    def _binary_mid(self, args: list[Any], context: ExecutionContext) -> bytes:
        self._expect_arg_counts("BinaryMid", args, 2, 3)
        data = self._coerce_binary(args[0], "BinaryMid", 1)
        start = self._coerce_int(args[1], "BinaryMid", 2)
        if start < 1:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_at_least("BinaryMid", 2, 1)
            )

        start_index = start - 1
        if len(args) == 2:
            return data[start_index:]

        count = self._coerce_int(args[2], "BinaryMid", 3)
        if count < 0:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_at_least("BinaryMid", 3, 0)
            )
        return data[start_index : start_index + count]

    def _binary_to_string(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("BinaryToString", args, 1, 2)
        data = self._coerce_binary_convertible(args[0], "BinaryToString", 1)
        flag = 1 if len(args) == 1 else self._coerce_int(args[1], "BinaryToString", 2)

        encoding_map = {
            1: ("cp1252", "ANSI"),
            2: ("utf-16-le", "UTF16 Little Endian"),
            3: ("utf-16-be", "UTF16 Big Endian"),
            4: ("utf-8", "UTF8"),
        }
        if flag not in encoding_map:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "BinaryToString",
                    2,
                    [1, 2, 3, 4],
                )
            )

        encoding, label = encoding_map[flag]
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            raise RuntimeError(
                RuntimeErrorMessages.binary_decode_failed("BinaryToString", label)
            ) from None

    def _asc(self, args: list[Any], context: ExecutionContext, name: str) -> int:
        self._expect_arg_count(name, args, 1)
        text = self._coerce_non_empty_string(args[0], name, 1)
        return ord(text[0])

    def _chr(self, args: list[Any], context: ExecutionContext, name: str) -> str:
        self._expect_arg_count(name, args, 1)
        code_point = self._require_int_value(name, args, 0)
        if code_point < 0 or code_point > 0x10FFFF:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_unicode_code_point(name, 1)
            )
        return chr(code_point)

    def _string_in_str(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("StringInStr", args, 2, 3, 4, 5, 6)
        context.set_error(0)

        haystack = self._coerce_strict_string(args[0], "StringInStr", 1)
        needle = self._coerce_strict_string(args[1], "StringInStr", 2)

        case_sensitive = 0 if len(args) < 3 else self._coerce_int(args[2], "StringInStr", 3)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringInStr",
                    3,
                    [0, 1],
                )
            )

        occurrence = 1 if len(args) < 4 else self._coerce_int(args[3], "StringInStr", 4)
        if occurrence == 0:
            context.set_error(1)
            return 0

        start = 1 if len(args) < 5 else self._coerce_int(args[4], "StringInStr", 5)
        if start < 1 or start > len(haystack):
            context.set_error(1)
            return 0

        count = None if len(args) < 6 else self._coerce_int(args[5], "StringInStr", 6)
        if count is not None:
            if count < 0 or count < len(needle):
                context.set_error(1)
                return 0

        search_haystack = haystack if case_sensitive == 1 else haystack.casefold()
        search_needle = needle if case_sensitive == 1 else needle.casefold()

        start_index = start - 1
        segment_end = len(search_haystack) if count is None else min(
            len(search_haystack),
            start_index + count,
        )
        segment = search_haystack[start_index:segment_end]

        if occurrence > 0:
            position = 0
            found = -1
            for _ in range(occurrence):
                found = segment.find(search_needle, position)
                if found < 0:
                    return 0
                position = found + 1
            return start_index + found + 1

        remaining = abs(occurrence)
        found = -1
        for _ in range(remaining):
            found = segment.rfind(search_needle, 0, len(segment) if found < 0 else found)
            if found < 0:
                return 0
        return start_index + found + 1

    def _string_length(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringLength", args, 1)
        return len(self._coerce_strict_string(args[0], "StringLength", 1))

    def _string_is_alpha(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsAlpha", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsAlpha", 1)
        return 1 if text.isalpha() else 0

    def _string_is_alphanumeric(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsAlphaNumeric", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsAlphaNumeric", 1)
        return 1 if text.isalnum() else 0

    def _string_is_ascii(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsASCII", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsASCII", 1)
        return 1 if text.isascii() else 0

    def _string_is_digit(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsDigit", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsDigit", 1)
        return 1 if text.isdigit() else 0

    def _string_is_float(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsFloat", args, 1)
        text = str(args[0])
        if not text:
            return 0

        if text[0] in "+-":
            text = text[1:]

        if text.count(".") != 1:
            return 0

        left, right = text.split(".", 1)
        digits = left + right
        return 1 if digits and all(ch in "0123456789" for ch in digits) else 0

    def _string_is_int(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsInt", args, 1)
        value = args[0]

        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return 1

        text = str(value)
        if not text:
            return 0

        if text[0] in "+-":
            text = text[1:]

        return 1 if text and all(ch in "0123456789" for ch in text) else 0

    def _string_is_lower(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsLower", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsLower", 1)
        return 1 if text and all(ch.isalpha() and ch.islower() for ch in text) else 0

    def _string_is_space(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsSpace", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsSpace", 1)
        return 1 if all(ch.isspace() or ch == "\x00" for ch in text) else 0

    def _string_is_upper(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("StringIsUpper", args, 1)
        text = self._coerce_strict_string(args[0], "StringIsUpper", 1)
        return 1 if text and all(ch.isalpha() and ch.isupper() for ch in text) else 0

    def _string_left(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringLeft", args, 2)
        text = self._coerce_strict_string(args[0], "StringLeft", 1)
        count = self._require_int_value("StringLeft", args, 1)
        if count < 0:
            return ""
        return text[:count]

    def _string_replace(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("StringReplace", args, 3, 4, 5)
        text = self._coerce_strict_string(args[0], "StringReplace", 1)
        search_or_start = args[1]
        replacement = self._coerce_strict_string(args[2], "StringReplace", 3)

        context.set_error(0)
        context.set_special_value("Extended", 0)

        if isinstance(search_or_start, int) and not isinstance(search_or_start, bool):
            start = self._coerce_int(search_or_start, "StringReplace", 2)
            if start < 1 or start > len(text):
                context.set_error(1)
                return ""

            start_index = start - 1
            end_index = start_index + len(replacement)
            if end_index > len(text):
                context.set_error(1)
                return ""

            context.set_special_value("Extended", 1)
            return text[:start_index] + replacement + text[end_index:]

        search_string = self._coerce_strict_string(search_or_start, "StringReplace", 2)
        if not search_string:
            context.set_error(1)
            return text

        occurrence = 0 if len(args) < 4 else self._coerce_int(args[3], "StringReplace", 4)
        case_sensitive = 0 if len(args) < 5 else self._coerce_int(args[4], "StringReplace", 5)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringReplace",
                    5,
                    [0, 1],
                )
            )

        if occurrence == 0:
            selected_match_indexes: set[int] | None = None
        else:
            selected_match_indexes = set()

        pattern = re.escape(search_string)
        flags = 0 if case_sensitive == 1 else re.IGNORECASE
        matches = list(re.finditer(pattern, text, flags))
        if not matches:
            return text

        if occurrence > 0:
            for match_index in range(min(occurrence, len(matches))):
                selected_match_indexes.add(match_index)
        elif occurrence < 0:
            count = min(abs(occurrence), len(matches))
            for match_index in range(len(matches) - count, len(matches)):
                selected_match_indexes.add(match_index)
        else:
            selected_match_indexes = None

        pieces: list[str] = []
        cursor = 0
        replacements = 0
        for match_index, match in enumerate(matches):
            if selected_match_indexes is not None and match_index not in selected_match_indexes:
                continue
            pieces.append(text[cursor:match.start()])
            pieces.append(replacement)
            cursor = match.end()
            replacements += 1
        pieces.append(text[cursor:])

        context.set_special_value("Extended", replacements)
        return "".join(pieces)

    def _string_starts_with(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("StringStartsWith", args, 2, 3)
        text = self._coerce_strict_string(args[0], "StringStartsWith", 1)
        prefix = self._coerce_strict_string(args[1], "StringStartsWith", 2)
        case_sensitive = 0 if len(args) == 2 else self._coerce_int(args[2], "StringStartsWith", 3)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringStartsWith",
                    3,
                    [0, 1],
                )
            )

        if case_sensitive == 0:
            return 1 if text.casefold().startswith(prefix.casefold()) else 0
        return 1 if text.startswith(prefix) else 0

    def _string_ends_with(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("StringEndsWith", args, 2, 3)
        text = self._coerce_strict_string(args[0], "StringEndsWith", 1)
        suffix = self._coerce_strict_string(args[1], "StringEndsWith", 2)
        case_sensitive = 0 if len(args) == 2 else self._coerce_int(args[2], "StringEndsWith", 3)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringEndsWith",
                    3,
                    [0, 1],
                )
            )

        if case_sensitive == 0:
            return 1 if text.casefold().endswith(suffix.casefold()) else 0
        return 1 if text.endswith(suffix) else 0

    def _string_contains(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("StringContains", args, 2, 3)
        text = self._coerce_strict_string(args[0], "StringContains", 1)
        needle = self._coerce_strict_string(args[1], "StringContains", 2)
        case_sensitive = 0 if len(args) == 2 else self._coerce_int(args[2], "StringContains", 3)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringContains",
                    3,
                    [0, 1],
                )
            )

        if case_sensitive == 0:
            return 1 if needle.casefold() in text.casefold() else 0
        return 1 if needle in text else 0

    def _string_split(self, args: list[Any], context: ExecutionContext) -> list[str]:
        self._expect_arg_counts("StringSplit", args, 2, 3, 4)
        text = self._coerce_strict_string(args[0], "StringSplit", 1)
        delimiter = self._coerce_strict_string(args[1], "StringSplit", 2)
        if delimiter == "":
            return [text]

        if len(args) == 2:
            limit = 0
            case_sensitive = 0
        elif len(args) == 3:
            limit = self._require_int_value("StringSplit", args, 2)
            case_sensitive = 0
        else:
            limit = self._require_int_value("StringSplit", args, 2)
            case_sensitive = self._require_int_value("StringSplit", args, 3)

        if limit < 0:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_at_least("StringSplit", 3, 0)
            )
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of(
                    "StringSplit",
                    4,
                    [0, 1],
                )
            )

        if case_sensitive == 1:
            maxsplit = -1 if limit == 0 else limit
            return text.split(delimiter, maxsplit=maxsplit)

        pattern = re.compile(re.escape(delimiter), flags=re.IGNORECASE)
        return pattern.split(text, maxsplit=limit)

    def _string_join(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("StringJoin", args, 1, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("StringJoin", 1))

        delimiter = "" if len(args) == 1 else self._coerce_strict_string(args[1], "StringJoin", 2)
        return delimiter.join(self._stringify_interpolated_value(value) for value in values)

    def _array_length(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayLength", args, 1)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayLength", 1))
        return len(values)

    def _array_insert(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_at_least_arg_count("ArrayInsert", args, 3)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayInsert", 1))

        index = self._require_int_value("ArrayInsert", args, 1)
        if index < 0 or index > len(values):
            raise RuntimeError(RuntimeErrorMessages.index_out_of_range(index))

        insert_values = [clone_runtime_value(value) for value in args[2:]]
        values[index:index] = insert_values
        context.set_error(0)
        return len(values)

    def _array_push(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_at_least_arg_count("ArrayPush", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayPush", 1))

        for value in args[1:]:
            values.append(clone_runtime_value(value))

        context.set_error(0)
        return len(values)

    def _array_pop(self, args: list[Any], context: ExecutionContext) -> Any:
        self._expect_arg_count("ArrayPop", args, 1)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayPop", 1))

        if not values:
            context.set_error(1)
            return None

        context.set_error(0)
        return clone_runtime_value(values.pop())

    def _array_remove(self, args: list[Any], context: ExecutionContext) -> Any:
        self._expect_arg_counts("ArrayRemove", args, 2, 3)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayRemove", 1))

        index = self._require_int_value("ArrayRemove", args, 1)
        if index < 0 or index >= len(values):
            raise RuntimeError(RuntimeErrorMessages.index_out_of_range(index))

        count = 1 if len(args) == 2 else self._require_int_value("ArrayRemove", args, 2)
        if count < 0:
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_at_least("ArrayRemove", 3, 0))
        if count == 0:
            context.set_error(0)
            return []

        end = min(index + count, len(values))
        removed = [clone_runtime_value(value) for value in values[index:end]]
        del values[index:end]
        context.set_error(0)
        if count == 1:
            return removed[0]
        return removed

    def _array_contains(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayContains", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayContains", 1))

        needle = args[1]
        return 1 if any(item == needle for item in values) else 0

    def _array_contains_all(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_at_least_arg_count("ArrayContainsAll", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayContainsAll", 1))

        needles = args[1:]
        return 1 if all(any(item == needle for item in values) for needle in needles) else 0

    def _array_count(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayCount", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayCount", 1))

        needle = args[1]
        return sum(1 for item in values if item == needle)

    def _array_initialize(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayInitialize", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayInitialize", 1))

        value = args[1]
        if not isinstance(value, (int, float, str)) or isinstance(value, bool):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_string_or_number("ArrayInitialize", 2))

        for index in range(len(values)):
            values[index] = value

        context.set_error(0)
        return len(values)

    def _array_clear(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayClear", args, 1)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayClear", 1))

        for index in range(len(values)):
            values[index] = ""

        context.set_error(0)
        return len(values)

    def _array_clone(self, args: list[Any], context: ExecutionContext) -> list[Any]:
        self._expect_arg_count("ArrayClone", args, 1)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayClone", 1))

        return [clone_runtime_value(value) for value in values]

    def _array_remove_all(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayRemoveAll", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayRemoveAll", 1))

        needle = args[1]
        original_length = len(values)
        values[:] = [item for item in values if item != needle]
        context.set_error(0)
        return original_length - len(values)

    def _array_index_of(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayIndexOf", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayIndexOf", 1))

        needle = args[1]
        for index, item in enumerate(values):
            if item == needle:
                return index
        return -1

    def _array_last_index_of(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_count("ArrayLastIndexOf", args, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayLastIndexOf", 1))

        needle = args[1]
        for index in range(len(values) - 1, -1, -1):
            if values[index] == needle:
                return index
        return -1

    def _array_to_string(self, args: list[Any], context: ExecutionContext, name: str = "ArrayToString") -> str:
        self._expect_arg_counts(name, args, 1, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array(name, 1))

        separator = "," if len(args) == 1 else self._coerce_strict_string(args[1], name, 2)
        return separator.join(self._stringify_interpolated_value(value) for value in values)

    def _array_reverse(self, args: list[Any], context: ExecutionContext) -> list[Any]:
        self._expect_arg_count("ArrayReverse", args, 1)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayReverse", 1))

        return [clone_runtime_value(value) for value in reversed(values)]

    def _array_sort(self, args: list[Any], context: ExecutionContext) -> list[Any]:
        self._expect_arg_counts("ArraySort", args, 1, 2, 3)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArraySort", 1))

        descending = 0 if len(args) < 2 else self._require_int_value("ArraySort", args, 1)
        casesense = 0 if len(args) < 3 else self._require_int_value("ArraySort", args, 2)

        if descending not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of("ArraySort", 2, [0, 1])
            )
        if casesense not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of("ArraySort", 3, [0, 1])
            )

        sorted_values = [clone_runtime_value(value) for value in values]
        sorted_values.sort(key=lambda value: self._array_sort_key(value, casesense == 1), reverse=bool(descending))
        return sorted_values

    def _array_sort_key(self, value: Any, case_sensitive: bool) -> tuple[int, Any]:
        if isinstance(value, bool):
            return (4, int(value))
        if isinstance(value, (int, float)):
            return (0, float(value))
        if isinstance(value, str):
            return (1, value if case_sensitive else value.casefold())
        if value is None:
            return (3, "")
        return (2, repr(value) if case_sensitive else repr(value).casefold())

    def _array_unique(self, args: list[Any], context: ExecutionContext) -> list[Any]:
        self._expect_arg_counts("ArrayUnique", args, 1, 2)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArrayUnique", 1))

        case_sensitive = 0 if len(args) == 1 else self._require_int_value("ArrayUnique", args, 1)
        if case_sensitive not in (0, 1):
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_one_of("ArrayUnique", 2, [0, 1])
            )

        seen: list[Any] = []
        unique_values: list[Any] = []
        for value in values:
            comparison_value = value
            if isinstance(value, str) and case_sensitive == 0:
                comparison_value = value.casefold()
            if any(self._array_unique_equal(existing, comparison_value) for existing in seen):
                continue
            seen.append(comparison_value)
            unique_values.append(clone_runtime_value(value))
        return unique_values

    def _array_unique_equal(self, left: Any, right: Any) -> bool:
        return left == right

    def _array_slice(self, args: list[Any], context: ExecutionContext) -> list[Any]:
        self._expect_arg_counts("ArraySlice", args, 2, 3)
        values = args[0]
        if not isinstance(values, list):
            raise RuntimeError(RuntimeErrorMessages.argument_must_be_array("ArraySlice", 1))

        start = self._require_int_value("ArraySlice", args, 1)
        if start < 0 or start > len(values):
            return []

        if len(args) == 2:
            return [clone_runtime_value(value) for value in values[start:]]

        count = self._require_int_value("ArraySlice", args, 2)
        if count < 0:
            return []
        return [clone_runtime_value(value) for value in values[start : start + count]]

    def _regex_flags(self, options: Any, name: str, index: int) -> int:
        option_text = self._coerce_strict_string(options, name, index)
        flags = 0
        allowed_options = {"i", "m", "s", "x"}

        for option in option_text:
            normalized_option = option.lower()
            if normalized_option not in allowed_options:
                raise RuntimeError(
                    RuntimeErrorMessages.invalid_regex_option(name, option)
                )
            if normalized_option == "i":
                flags |= re.IGNORECASE
            elif normalized_option == "m":
                flags |= re.MULTILINE
            elif normalized_option == "s":
                flags |= re.DOTALL
            elif normalized_option == "x":
                flags |= re.VERBOSE

        return flags

    def _compile_regex(self, pattern: str, options: Any, name: str, index: int) -> re.Pattern[str]:
        try:
            flags = self._regex_flags(options, name, index)
            return re.compile(pattern, flags)
        except re.error as exc:
            raise RuntimeError(
                RuntimeErrorMessages.invalid_regular_expression(name, str(exc))
            ) from None

    def _regex_escape(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("RegexEscape", args, 1)
        text = self._coerce_strict_string(args[0], "RegexEscape", 1)
        return re.escape(text)

    def _regex_is_match(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("RegexIsMatch", args, 2, 3)
        text = self._coerce_strict_string(args[0], "RegexIsMatch", 1)
        pattern = self._coerce_strict_string(args[1], "RegexIsMatch", 2)
        options = "" if len(args) == 2 else args[2]
        compiled = self._compile_regex(pattern, options, "RegexIsMatch", 3)
        return 1 if compiled.search(text) is not None else 0

    def _regex_in_str(self, args: list[Any], context: ExecutionContext) -> int:
        self._expect_arg_counts("RegexInStr", args, 2, 3, 4)
        text = self._coerce_strict_string(args[0], "RegexInStr", 1)
        pattern = self._coerce_strict_string(args[1], "RegexInStr", 2)

        start = 1
        if len(args) >= 3 and len(args) != 4:
            start = self._require_int_value("RegexInStr", args, 2)
            options = ""
        elif len(args) == 4:
            start = self._require_int_value("RegexInStr", args, 2)
            options = args[3]
        else:
            options = ""

        if start < 1 or start > len(text):
            context.set_error(1)
            return 0

        compiled = self._compile_regex(pattern, options, "RegexInStr", 4)
        match = compiled.search(text, pos=start - 1)
        if match is None:
            context.set_error(1)
            return 0

        context.set_error(0)
        return match.start() + 1

    def _regex_match(self, args: list[Any], context: ExecutionContext) -> list[Any] | None:
        self._expect_arg_counts("RegexMatch", args, 2, 3)
        text = self._coerce_strict_string(args[0], "RegexMatch", 1)
        pattern = self._coerce_strict_string(args[1], "RegexMatch", 2)
        options = "" if len(args) == 2 else args[2]
        compiled = self._compile_regex(pattern, options, "RegexMatch", 3)
        match = compiled.search(text)
        if match is None:
            context.set_error(1)
            return None

        context.set_error(0)
        return [match.group(0), *match.groups()]

    def _regex_expand_replacement(self, replacement: str, match: re.Match[str], name: str) -> str:
        pieces: list[str] = []
        index = 0
        group_count = match.re.groups

        while index < len(replacement):
            char = replacement[index]
            if char != "$":
                pieces.append(char)
                index += 1
                continue

            if index + 1 >= len(replacement):
                pieces.append("$")
                index += 1
                continue

            next_char = replacement[index + 1]
            if next_char == "$":
                pieces.append("$")
                index += 2
                continue

            if next_char.isdigit():
                group_end = index + 2
                while group_end < len(replacement) and replacement[group_end].isdigit():
                    group_end += 1
                group_number = int(replacement[index + 1:group_end])
                if group_number > group_count:
                    raise RuntimeError(
                        RuntimeErrorMessages.invalid_regular_expression(
                            name,
                            f"replacement references capture group {group_number} but only {group_count} group(s) exist",
                        )
                    )
                group_value = match.group(group_number)
                pieces.append("" if group_value is None else group_value)
                index = group_end
                continue

            pieces.append("$")
            index += 1

        return "".join(pieces)

    def _regex_replace(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("RegexReplace", args, 3, 4, 5)
        text = self._coerce_strict_string(args[0], "RegexReplace", 1)
        pattern = self._coerce_strict_string(args[1], "RegexReplace", 2)
        replacement = self._coerce_strict_string(args[2], "RegexReplace", 3)

        count = 0
        options = ""
        if len(args) >= 4:
            count = self._require_int_value("RegexReplace", args, 3)
            if len(args) == 5:
                options = args[4]

        if count < 0:
            raise RuntimeError(
                RuntimeErrorMessages.argument_must_be_at_least("RegexReplace", 4, 0)
            )

        compiled = self._compile_regex(pattern, options, "RegexReplace", 5)
        replacements = 0

        def _replacement(match: re.Match[str]) -> str:
            nonlocal replacements
            replacements += 1
            return self._regex_expand_replacement(replacement, match, "RegexReplace")

        result, _ = compiled.subn(_replacement, text, count=count)
        context.set_error(0)
        context.set_special_value("Extended", replacements)
        return result

    def _string_reverse(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringReverse", args, 1)
        text = self._coerce_strict_string(args[0], "StringReverse", 1)
        return text[::-1]

    def _string_right(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringRight", args, 2)
        text = self._coerce_strict_string(args[0], "StringRight", 1)
        count = self._require_int_value("StringRight", args, 1)
        if count <= 0:
            return ""
        if count >= len(text):
            return text
        return text[-count:]

    def _string_trim_left(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringTrimLeft", args, 2)
        text = self._coerce_strict_string(args[0], "StringTrimLeft", 1)
        count = self._require_int_value("StringTrimLeft", args, 1)
        if count < 0 or count > len(text):
            return ""
        return text[count:]

    def _string_trim_right(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringTrimRight", args, 2)
        text = self._coerce_strict_string(args[0], "StringTrimRight", 1)
        count = self._require_int_value("StringTrimRight", args, 1)
        if count < 0 or count > len(text):
            return ""
        if count == 0:
            return text
        return text[:-count]

    def _string_mid(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_counts("StringMid", args, 2, 3)
        text = self._coerce_strict_string(args[0], "StringMid", 1)
        start = self._require_int_value("StringMid", args, 1)
        if start < 1 or start > len(text):
            return ""

        if len(args) == 2:
            return text[start - 1:]

        count = self._require_int_value("StringMid", args, 2)
        if count <= 0:
            if count < 0:
                return text[start - 1:]
            return ""
        end_index = start - 1 + count
        if end_index >= len(text):
            return text[start - 1:]
        return text[start - 1:end_index]

    def _string_to_lower(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringToLower", args, 1)
        return self._coerce_strict_string(args[0], "StringToLower", 1).lower()

    def _string_to_upper(self, args: list[Any], context: ExecutionContext) -> str:
        self._expect_arg_count("StringToUpper", args, 1)
        return self._coerce_strict_string(args[0], "StringToUpper", 1).upper()

    def _bit_not_unsigned(self, args: list[Any], context: ExecutionContext) -> int:
        value = self._coerce_uint32(args[0], "BitNOTUnsigned", 1)
        return (~value) & 0xFFFFFFFF

    def _bit_rotate(self, args: list[Any], context: ExecutionContext) -> int:
        value = self._coerce_uint32(args[0], "BitRotate", 1)
        shift = 1 if len(args) == 1 else self._coerce_int(args[1], "BitRotate", 2)
        size = "W" if len(args) < 3 else self._coerce_strict_string(args[2], "BitRotate", 3).strip().upper()

        size_map = {
            "B": 8,
            "W": 16,
            "D": 32,
        }
        width = size_map.get(size)
        if width is None:
            context.set_error(1)
            return 0

        context.set_error(0)

        mask = (1 << width) - 1
        rotate_by = shift % width
        low_bits = value & mask
        upper_bits = value & (~mask & 0xFFFFFFFF)
        rotated = ((low_bits << rotate_by) | (low_bits >> (width - rotate_by))) & mask
        combined = (upper_bits | rotated) & 0xFFFFFFFF
        return self._to_signed_int32(combined)

    def _dict_item_reference(self, container: dict[Any, Any], key: Any) -> Any:
        from core.runtime.execution_context import VariableReference

        return VariableReference(
            getter=lambda container=container, key=key: container[key],
            setter=lambda value, container=container, key=key: container.__setitem__(key, value),
        )
