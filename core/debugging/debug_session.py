from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .breakpoints import BreakpointSet
from .call_stack_snapshot import DebugFrameSnapshot
from .debug_event import DebugEvent, PauseReason
from .variable_snapshot import DebugVariable


@dataclass(slots=True)
class DebugSession:
    session_id: str
    document_id: str
    breakpoints: BreakpointSet
    emit_event: Callable[[DebugEvent], None] | None = None

    state: str = "idle"
    is_running: bool = False
    is_paused: bool = False
    current_line: int | None = None
    pause_reason: PauseReason | None = None
    call_stack: list[DebugFrameSnapshot] = field(default_factory=list)
    variables: list[DebugVariable] = field(default_factory=list)
    last_exception: str | None = None

    def emit(self, event: DebugEvent) -> None:
        if self.emit_event is not None:
            self.emit_event(event)

    def start(self) -> None:
        self.state = "running"
        self.is_running = True
        self.is_paused = False
        self.pause_reason = None

    def pause(self, reason: PauseReason | None = None) -> None:
        self.state = "paused"
        self.is_running = True
        self.is_paused = True
        self.pause_reason = reason

    def resume(self) -> None:
        self.state = "running"
        self.is_running = True
        self.is_paused = False
        self.pause_reason = None

    def complete(self) -> None:
        self.state = "completed"
        self.is_running = False
        self.is_paused = False
        self.pause_reason = None

    def fail(self, message: str | None = None) -> None:
        self.state = "failed"
        self.is_running = False
        self.is_paused = False
        self.pause_reason = "exception"
        if message is not None:
            self.last_exception = str(message)

    def snapshot(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "document_id": self.document_id,
            "state": self.state,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "current_line": self.current_line,
            "breakpoints": self.breakpoints.lines(),
            "call_stack": list(self.call_stack),
            "variables": list(self.variables),
            "last_exception": self.last_exception,
        }
