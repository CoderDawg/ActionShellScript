from __future__ import annotations

from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument

from ..filter_profile import FilterProfile


class PreserveDocumentFilter:
    filter_id = "preserve_document"

    def apply(
        self,
        source: ScriptDocument,
        profile: FilterProfile,
    ) -> ScriptDocument:
        del profile
        return ScriptDocument(
            document_id=source.document_id,
            text=source.text,
            version=DocumentVersion(source.version.value),
            is_dirty=source.is_dirty,
            source_session_id=source.source_session_id,
            source_action_count=source.source_action_count,
            generated_from_recording=source.generated_from_recording,
            recording_conversion_route=source.recording_conversion_route,
            source_capture_excluded_main_window=source.source_capture_excluded_main_window,
        )
