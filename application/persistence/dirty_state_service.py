from __future__ import annotations

from core.persistence.persistence_models import DirtyState, SaveRequirement
from editor.document.script_document import ScriptDocument


class DirtyStateService:
    def summarize(self, document: ScriptDocument) -> DirtyState:
        return DirtyState(
            is_dirty=document.is_dirty,
            version=document.version.value,
            last_saved_version=document.last_saved_version,
        )

    def requires_save_before_close(self, document: ScriptDocument) -> SaveRequirement:
        if not document.is_dirty:
            return SaveRequirement(requires_save=False)
        return SaveRequirement(
            requires_save=True,
            reason="Document has unsaved changes before close.",
        )

    def requires_save_before_replace(self, document: ScriptDocument) -> SaveRequirement:
        if not document.is_dirty:
            return SaveRequirement(requires_save=False)
        return SaveRequirement(
            requires_save=True,
            reason="Document has unsaved changes before replace.",
        )
