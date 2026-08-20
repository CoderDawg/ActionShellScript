from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class FilterResult(Generic[T]):
    value: T
    applied_filters: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
