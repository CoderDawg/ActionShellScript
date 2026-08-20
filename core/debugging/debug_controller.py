from __future__ import annotations

import uuid
import threading
from typing import Any, Callable

from editor.document.script_document import ScriptDocument

from .breakpoints import BreakpointSet
from .call_stack_snapshot import DebugFrameSnapshot
from .debug_event import DebugEvent
from .debug_request import DebugRequest
from .debug_session import DebugSession
from .debug_state import DebugState
from .source_map import SourceMap
from .variable_snapshot import DebugVariable
from core.runtime.struct_values import describe_debugger_value_type
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("debug_controller")


class DebugController:
    def __init__(
        self,
        *,
        document: ScriptDocument,
        request: DebugRequest,
        emit_event: Callable[[DebugEvent], None] | None = None,
    ) -> None:
        self._document = document
        self._source_map = SourceMap(document.text)
        self._request = request
        self._emit_event = emit_event
        self._debuggable_lines = set(self._source_map.collect_debuggable_source_lines())
        self._session = DebugSession(
            session_id=str(uuid.uuid4()),
            document_id=document.document_id,
            breakpoints=BreakpointSet(document_id=document.document_id),
            emit_event=emit_event,
        )
        self._current_line: int | None = None
        self._call_stack: list[DebugFrameSnapshot] = []
        self._variables: list[DebugVariable] = []
        self._special_values: dict[str, object] = {}
        self._last_exception: str | None = None
        self._active_mode: str = request.stop_mode
        self._step_target_depth: int | None = None
        self._resume_condition = threading.Condition()
        self._resume_requested = False
        self._pause_requested = False

        self.set_breakpoints(list(request.breakpoints))
        log.info(
            "Debug controller initialized",
            event_id="debug.controller.initialized",
            document_id=document.document_id,
            stop_mode=request.stop_mode,
            breakpoint_count=len(request.breakpoints),
        )

    @property
    def session(self) -> DebugSession:
        return self._session

    @property
    def source_map(self) -> SourceMap:
        return self._source_map

    def set_breakpoints(self, lines: list[int]) -> None:
        self._session.breakpoints.clear()
        for line in lines:
            if not isinstance(line, int) or line <= 0:
                log.decision(
                    "Ignored invalid breakpoint line",
                    event_id="debug.breakpoints.invalid",
                    line=line,
                )
                continue
            if line not in self._debuggable_lines:
                log.error(
                    "Rejected non-debuggable breakpoint line",
                    event_id="debug.breakpoints.not_debuggable",
                    line=line,
                )
                raise ValueError(f"Line {line} is not a debuggable source line.")
            self._session.breakpoints.set_breakpoint(line)
        log.info(
            "Debugger breakpoints updated",
            event_id="debug.breakpoints.updated",
            document_id=self._session.document_id,
            breakpoints=self._session.breakpoints.lines(),
        )

    def start(self) -> None:
        self._session.start()
        log.info(
            "Debug session started",
            event_id="debug.session.started",
            session_id=self._session.session_id,
            document_id=self._session.document_id,
        )
        self.emit(
            DebugEvent(
                kind="session_started",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
            )
        )

    def complete(self) -> None:
        self._session.complete()
        with self._resume_condition:
            self._resume_requested = True
            self._resume_condition.notify_all()
        log.info(
            "Debug session completed",
            event_id="debug.session.completed",
            session_id=self._session.session_id,
            document_id=self._session.document_id,
            current_line=self._current_line,
        )
        self.emit(
            DebugEvent(
                kind="session_completed",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
            )
        )

    def fail(self, exc: BaseException) -> None:
        self._last_exception = str(exc)
        self._session.fail(self._last_exception)
        with self._resume_condition:
            self._resume_requested = True
            self._resume_condition.notify_all()
        log.exception(
            "Debug session failed",
            exc,
            event_id="debug.session.failed",
            session_id=self._session.session_id,
            document_id=self._session.document_id,
            current_line=self._current_line,
        )
        self.emit(
            DebugEvent(
                kind="session_failed",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
                message=self._last_exception,
            )
        )

    def snapshot(self) -> DebugState:
        return DebugState(
            session_id=self._session.session_id,
            document_id=self._session.document_id,
            state=self._session.state,
            is_running=self._session.is_running,
            is_paused=self._session.is_paused,
            pause_reason=self._session.pause_reason,
            current_line=self._current_line,
            breakpoints=self._session.breakpoints.lines(),
            call_stack=list(self._call_stack),
            variables=list(self._variables),
            special_values=dict(self._special_values),
            last_exception=self._last_exception,
        )

    def sync_from_context(self, context: Any) -> None:
        self._refresh_from_context(context)

    def resume_step(self) -> None:
        self._request_resume("step", target_depth=None)

    def resume_step_over(self) -> None:
        target_depth = len(self._call_stack)
        self._request_resume("step_over", target_depth=target_depth)

    def resume_step_out(self) -> None:
        target_depth = max(len(self._call_stack) - 1, 0)
        self._request_resume("step_out", target_depth=target_depth)

    def resume_continue(self) -> None:
        self._request_resume("continue", target_depth=None)

    def resume_go(self) -> None:
        self._request_resume("go", target_depth=None)

    def request_pause(self) -> None:
        with self._resume_condition:
            self._pause_requested = True
            self._resume_condition.notify_all()

    def wait_for_pause(self, timeout: float | None = None) -> bool:
        with self._resume_condition:
            if self._session.is_paused:
                return True
            if self._session.state in {"completed", "failed"}:
                return False
            self._resume_condition.wait_for(
                lambda: self._session.is_paused or self._session.state in {"completed", "failed"},
                timeout=timeout,
            )
            return self._session.is_paused

    def wait_for_resume(self, context: Any) -> None:
        _ = context
        with self._resume_condition:
            self._resume_condition.wait_for(
                lambda: self._resume_requested or self._session.state in {"completed", "failed"},
            )
            self._resume_requested = False

    def _request_resume(self, mode: str, *, target_depth: int | None) -> None:
        self._active_mode = mode
        self._step_target_depth = target_depth
        self._session.resume()
        log.decision(
            "Debugger resume requested",
            event_id="debug.resume.requested",
            session_id=self._session.session_id,
            document_id=self._session.document_id,
            mode=mode,
            current_line=self._current_line,
            target_depth=target_depth,
        )
        self.emit(
            DebugEvent(
                kind="continued",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
                pause_reason=self._session.pause_reason,
                payload={"mode": mode, "target_depth": target_depth},
            )
        )
        with self._resume_condition:
            self._resume_requested = True
            self._resume_condition.notify_all()

    def emit(self, event: DebugEvent) -> None:
        self._session.emit(event)

    def on_line(self, line: int | None, node: Any | None, context: Any) -> bool:
        _ = node
        self._current_line = line
        self._session.current_line = line
        self._refresh_from_context(context)
        current_depth = len(self._call_stack)

        should_stop = False
        pause_reason: str | None = None
        if self._pause_requested:
            should_stop = True
            pause_reason = "manual_pause"
        elif line is not None:
            if self._active_mode == "go":
                should_stop = False
            elif self._active_mode == "step":
                should_stop = True
                pause_reason = "step"
            elif self._active_mode == "step_over":
                target_depth = self._step_target_depth if self._step_target_depth is not None else 0
                if current_depth <= target_depth:
                    should_stop = True
                    pause_reason = "step_over"
            elif self._active_mode == "step_out":
                target_depth = self._step_target_depth if self._step_target_depth is not None else 0
                if current_depth <= target_depth:
                    should_stop = True
                    pause_reason = "step_out"
        breakpoint_enabled = (
            self._active_mode != "go"
            and line is not None
            and self._session.breakpoints.is_enabled(line)
        )
        if breakpoint_enabled and self._active_mode == "step_out":
            target_depth = self._step_target_depth if self._step_target_depth is not None else 0
            breakpoint_enabled = current_depth <= target_depth
        if breakpoint_enabled:
            should_stop = True
            pause_reason = "breakpoint"

        if should_stop:
            self._active_mode = "continue"
            self._step_target_depth = None
            self._pause_requested = False
            self._session.pause(pause_reason)
            with self._resume_condition:
                self._resume_requested = False
                self._resume_condition.notify_all()
            log.decision(
                "Debugger paused execution",
                event_id="debug.session.paused",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=line,
                pause_reason=pause_reason,
                call_stack_depth=current_depth,
            )
            self.emit(
                DebugEvent(
                    kind="stopped",
                    session_id=self._session.session_id,
                    document_id=self._session.document_id,
                    line=line,
                    pause_reason=pause_reason,
                    payload={"mode": pause_reason or "continue", "depth": current_depth},
                )
            )

        return should_stop

    def on_function_call(self, function_name: str, context: Any) -> None:
        self._refresh_from_context(context)
        log.trace(
            "Debugger observed function call",
            event_id="debug.function.called",
            session_id=self._session.session_id,
            function_name=function_name,
            line=self._current_line,
        )
        self.emit(
            DebugEvent(
                kind="function_call",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
                function_name=function_name,
            )
        )

    def on_function_return(
        self,
        function_name: str,
        return_value: Any,
        context: Any,
    ) -> None:
        self._refresh_from_context(context)
        log.trace(
            "Debugger observed function return",
            event_id="debug.function.returned",
            session_id=self._session.session_id,
            function_name=function_name,
            line=self._current_line,
        )
        self.emit(
            DebugEvent(
                kind="function_return",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
                function_name=function_name,
                payload={"return_value": return_value},
            )
        )

    def on_exception(
        self,
        exc: BaseException,
        node: Any | None,
        context: Any,
    ) -> None:
        location = self._source_map.location_for_node(node)
        self._current_line = location.line if location is not None else self._current_line
        self._refresh_from_context(context)
        self._session.current_line = self._current_line
        self._last_exception = str(exc)
        log.exception(
            "Debugger observed runtime exception",
            exc,
            event_id="debug.session.exception",
            session_id=self._session.session_id,
            document_id=self._session.document_id,
            line=self._current_line,
        )
        self.fail(exc)
        self.emit(
            DebugEvent(
                kind="exception",
                session_id=self._session.session_id,
                document_id=self._session.document_id,
                line=self._current_line,
                pause_reason="exception",
                message=str(exc),
            )
        )

    def _refresh_from_context(self, context: Any) -> None:
        if context is None:
            return

        current_line = getattr(context, "current_source_line", None)
        if isinstance(current_line, int) and current_line > 0:
            self._current_line = current_line
            self._session.current_line = current_line

        variables = getattr(context, "variables", None)
        if isinstance(variables, dict):
            self._variables = [
                DebugVariable(
                    name=str(name),
                    value=value,
                    type_name=describe_debugger_value_type(value),
                )
                for name, value in variables.items()
            ]
            self._session.variables = list(self._variables)

        special_values = getattr(context, "special_values", None)
        if isinstance(special_values, dict):
            self._special_values = {
                str(name): value
                for name, value in special_values.items()
            }

        call_stack = getattr(context, "call_stack", None)
        if call_stack is not None:
            frames: list[DebugFrameSnapshot] = []
            for frame in call_stack:
                snapshot = getattr(frame, "snapshot", None)
                if callable(snapshot):
                    frames.append(snapshot())
            self._call_stack = frames
            self._session.call_stack = list(frames)

