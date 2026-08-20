from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    value: int = 1

    def next(self) -> "DocumentVersion":
        return DocumentVersion(self.value + 1)
