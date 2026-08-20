from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DebugRequest:
    document_id: str
    stop_mode: Literal["step", "continue"] = "continue"
    breakpoints: tuple[int, ...] = ()
