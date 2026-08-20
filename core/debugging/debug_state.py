from __future__ import annotations

from dataclasses import dataclass, field

from .call_stack_snapshot import DebugFrameSnapshot
from .debug_event import PauseReason
from .variable_snapshot import DebugVariable


@dataclass(frozen=True, slots=True)
class DebugState:
    session_id: str
    document_id: str
    state: str
    is_running: bool
    is_paused: bool
    pause_reason: PauseReason | None
    current_line: int | None
    breakpoints: list[int] = field(default_factory=list)
    call_stack: list[DebugFrameSnapshot] = field(default_factory=list)
    variables: list[DebugVariable] = field(default_factory=list)
    special_values: dict[str, object] = field(default_factory=dict)
    last_exception: str | None = None
