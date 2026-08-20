from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from .call_stack_snapshot import DebugFrameSnapshot
from .variable_snapshot import DebugVariable
from core.runtime.struct_values import describe_debugger_value_type


@dataclass(slots=True)
class CallFrame:
    function_name: str
    locals: dict[str, Any] = field(default_factory=dict)
    byref_bindings: dict[str, Any] = field(default_factory=dict)
    node: Any | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    line: int | None = None

    def snapshot(self) -> DebugFrameSnapshot:
        locals_snapshot: list[DebugVariable] = []
        for name, value in self.locals.items():
            locals_snapshot.append(
                DebugVariable(
                    name=str(name),
                    value=value,
                    type_name=describe_debugger_value_type(value),
                )
            )

        for name, reference in self.byref_bindings.items():
            try:
                value = reference.get()
            except Exception:
                value = "<unavailable>"
            locals_snapshot.append(
                DebugVariable(
                    name=str(name),
                    value=value,
                    type_name=describe_debugger_value_type(value),
                )
            )

        return DebugFrameSnapshot(
            function_name=self.function_name,
            source_line=self.line,
            locals=locals_snapshot,
        )


@dataclass(slots=True)
class CallStack:
    _frames: list[CallFrame] = field(default_factory=list)

    def push(self, frame: CallFrame) -> None:
        self._frames.append(frame)

    def pop(self) -> CallFrame:
        if not self._frames:
            raise IndexError("Call stack is empty.")
        return self._frames.pop()

    def current(self) -> CallFrame | None:
        if not self._frames:
            return None
        return self._frames[-1]

    def depth(self) -> int:
        return len(self._frames)

    def snapshot(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for frame in self._frames:
            frame_snapshot = frame.snapshot()
            snapshots.append(
                {
                    "function_name": frame_snapshot.function_name,
                    "source_line": frame_snapshot.source_line,
                    "locals": [
                        {
                            "name": variable.name,
                            "value": variable.value,
                            "type_name": variable.type_name,
                        }
                        for variable in frame_snapshot.locals
                    ],
                }
            )
        return snapshots

    def __iter__(self) -> Iterator[CallFrame]:
        return iter(self._frames)

    def __bool__(self) -> bool:
        return bool(self._frames)
