from __future__ import annotations

from dataclasses import dataclass

from core.persistence.file_reference import FileReference


@dataclass(frozen=True, slots=True)
class SaveResult:
    target: FileReference
    version: int
