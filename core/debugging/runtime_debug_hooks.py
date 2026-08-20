from __future__ import annotations

from typing import Any, Protocol

from core.debugging.source_map import SourceMap
from core.scripting import ast_nodes as ast


class DebugEventSink(Protocol):
    def on_line(self, line: int | None, node: ast.Statement | None, context: Any) -> bool: ...
    def on_function_call(self, function_name: str, context: Any) -> None: ...
    def on_function_return(self, function_name: str, return_value: Any, context: Any) -> None: ...
    def on_exception(self, exc: BaseException, node: Any | None, context: Any) -> None: ...
    def wait_for_resume(self, context: Any) -> None: ...


class RuntimeDebugHooks:
    def __init__(
        self,
        *,
        source_map: SourceMap,
        sink: DebugEventSink | None = None,
    ) -> None:
        self._source_map = source_map
        self._sink = sink

    def before_statement(
        self,
        statement: ast.Statement,
        context: Any,
    ) -> bool:
        line = self._source_map.get_node_line(statement)
        if hasattr(context, "set_current_source_line"):
            context.set_current_source_line(line)
        if self._sink is not None:
            return bool(self._sink.on_line(line, statement, context))
        return False

    def on_function_call(self, function_name: str, context: Any) -> None:
        if self._sink is not None:
            self._sink.on_function_call(function_name, context)

    def on_function_return(
        self,
        function_name: str,
        return_value: Any,
        context: Any,
    ) -> None:
        if self._sink is not None:
            self._sink.on_function_return(function_name, return_value, context)

    def on_exception(
        self,
        exc: BaseException,
        node: Any | None,
        context: Any,
    ) -> None:
        line = self._source_map.get_node_line(node)
        if hasattr(context, "set_current_source_line"):
            context.set_current_source_line(line)
        if self._sink is not None:
            self._sink.on_exception(exc, node, context)

    def wait_for_resume(self, context: Any) -> None:
        if self._sink is not None:
            wait_for_resume = getattr(self._sink, "wait_for_resume", None)
            if callable(wait_for_resume):
                wait_for_resume(context)


class RuntimeTraceHooks:
    def __init__(self, *, source_map: SourceMap) -> None:
        self._source_map = source_map

    def trace_statement(
        self,
        label: str,
        statement: ast.Statement | None,
        context: Any,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        _ = label
        _ = statement
        _ = context
        _ = extra

    def trace_function_enter(
        self,
        function_name: str,
        bound_args: dict[str, Any],
        context: Any,
    ) -> None:
        _ = function_name
        _ = bound_args
        _ = context

    def trace_function_return(
        self,
        function_name: str,
        value: Any,
        context: Any,
    ) -> None:
        _ = function_name
        _ = value
        _ = context

    def trace_function_exit(self, function_name: str, context: Any) -> None:
        _ = function_name
        _ = context

    def trace_function_error(
        self,
        function_name: str,
        message: str,
        context: Any,
    ) -> None:
        _ = function_name
        _ = message
        _ = context
