from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from core.persistence.file_reference import FileReference

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LoadResult(Generic[T]):
    target: FileReference
    value: T
