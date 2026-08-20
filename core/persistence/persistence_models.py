from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class DirtyState:
    is_dirty: bool
    version: int
    last_saved_version: int | None


@dataclass(frozen=True, slots=True)
class SaveRequirement:
    requires_save: bool
    reason: str | None = None


class PendingAction(StrEnum):
    CLOSE_DOCUMENT = "close_document"
    OPEN_OTHER_DOCUMENT = "open_other_document"
    EXIT_APPLICATION = "exit_application"
    REPLACE_EXISTING_OUTPUT = "replace_existing_output"
