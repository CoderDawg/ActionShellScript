from __future__ import annotations

from dataclasses import dataclass, field

from .variable_snapshot import DebugVariable


@dataclass(frozen=True, slots=True)
class DebugFrameSnapshot:
    function_name: str
    source_line: int | None
    locals: list[DebugVariable] = field(default_factory=list)
