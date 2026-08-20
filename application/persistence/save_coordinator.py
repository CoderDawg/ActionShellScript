from __future__ import annotations

from pathlib import Path

from application.persistence.script_document_store import ScriptDocumentStore
from core.persistence.file_reference import FileReference
from core.persistence.save_result import SaveResult
from editor.document.script_document import ScriptDocument


class SaveCoordinator:
    def save_script_document(
        self,
        document: ScriptDocument,
        *,
        path: Path,
        store: ScriptDocumentStore,
    ) -> SaveResult:
        store.save(path, document)
        document.source_path = str(path)
        document.mark_saved()
        return SaveResult(
            target=FileReference(path=path),
            version=document.version.value,
        )
