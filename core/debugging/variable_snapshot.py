from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DebugVariable:
    name: str
    value: Any
    type_name: str
