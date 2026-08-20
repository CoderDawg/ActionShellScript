from __future__ import annotations

from pathlib import Path

from application.persistence.dirty_state_service import DirtyStateService
from core.persistence.persistence_models import PendingAction, SaveRequirement
from editor.document.script_document import ScriptDocument


class UnsavedChangesService:
    def __init__(
        self,
        dirty_state_service: DirtyStateService | None = None,
    ) -> None:
        self._dirty_state_service = dirty_state_service or DirtyStateService()

    def requires_resolution(
        self,
        document: ScriptDocument,
        *,
        action: PendingAction,
    ) -> SaveRequirement:
        if action is PendingAction.CLOSE_DOCUMENT:
            return self._dirty_state_service.requires_save_before_close(document)
        if action is PendingAction.OPEN_OTHER_DOCUMENT:
            return self._dirty_state_service.requires_save_before_replace(document)
        if action is PendingAction.EXIT_APPLICATION:
            if not document.is_dirty:
                return SaveRequirement(requires_save=False)
            return SaveRequirement(
                requires_save=True,
                reason="Document has unsaved changes before application exit.",
            )
        raise ValueError(f"Unsupported pending action: {action!r}.")

    def requires_resolution_for_existing_target(
        self,
        *,
        target: Path,
        action: PendingAction,
        target_description: str = "Output file",
    ) -> SaveRequirement:
        if not target.exists():
            return SaveRequirement(requires_save=False)
        if action is PendingAction.REPLACE_EXISTING_OUTPUT:
            return SaveRequirement(
                requires_save=True,
                reason=f"{target_description} already exists.",
            )
        return SaveRequirement(
            requires_save=True,
            reason=f"{target_description} already exists and needs resolution.",
        )
