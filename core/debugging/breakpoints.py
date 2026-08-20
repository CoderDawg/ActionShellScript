from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Breakpoint:
    line: int
    enabled: bool = True


@dataclass(slots=True)
class BreakpointSet:
    document_id: str
    breakpoints: dict[int, Breakpoint] = field(default_factory=dict)

    def set_breakpoint(self, line: int) -> None:
        self.breakpoints[int(line)] = Breakpoint(line=int(line))

    def remove_breakpoint(self, line: int) -> None:
        self.breakpoints.pop(int(line), None)

    def clear(self) -> None:
        self.breakpoints.clear()

    def is_enabled(self, line: int) -> bool:
        bp = self.breakpoints.get(int(line))
        return bp is not None and bp.enabled

    def add(self, line: int) -> None:
        self.set_breakpoint(line)

    def remove(self, line: int) -> None:
        self.remove_breakpoint(line)

    def has(self, line: int) -> bool:
        return self.is_enabled(line)

    def lines(self) -> list[int]:
        return list(self.breakpoints.keys())
