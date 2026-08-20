from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DebugEventKind = Literal[
    "session_started",
    "stopped",
    "continued",
    "function_call",
    "function_return",
    "exception",
    "session_completed",
    "session_failed",
]


PauseReason = Literal[
    "entry",
    "breakpoint",
    "step",
    "step_over",
    "step_out",
    "exception",
    "manual_pause",
]


@dataclass(frozen=True, slots=True)
class DebugEvent:
    kind: DebugEventKind
    session_id: str
    document_id: str
    line: int | None = None
    function_name: str | None = None
    pause_reason: PauseReason | None = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
