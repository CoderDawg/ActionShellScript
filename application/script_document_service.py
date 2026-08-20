from __future__ import annotations

from dataclasses import dataclass

from core.recording.recording_session import RecordingSession
from core.scripting.documents.script_document_factory import ScriptDocumentFactory
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.script_document import ScriptDocument
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("script_document_service")


@dataclass(frozen=True, slots=True)
class ScriptDocumentSummary:
    document_id: str
    version: int
    line_count: int
    is_dirty: bool
    last_saved_version: int | None
    source_session_id: str | None
    recording_conversion_route: str | None
    source_capture_excluded_main_window: bool | None


class ScriptDocumentService:
    def __init__(
        self,
        factory: ScriptDocumentFactory | None = None,
    ) -> None:
        self._factory = factory or ScriptDocumentFactory()

    def promote_generated_script(
        self,
        generated: GeneratedScript,
        *,
        recording_conversion_route: str | None = None,
        source_capture_excluded_main_window: bool | None = None,
    ) -> ScriptDocument:
        log.info(
            "Script document promotion started",
            event_id="document.promoted.started",
            source_session_id=generated.source_session_id,
            source_action_count=generated.source_action_count,
            line_count=generated.line_count(),
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )
        document = self._factory.create_from_generated_script(
            generated,
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )
        log.info(
            "Script document promotion completed",
            event_id="document.promoted.completed",
            document_id=document.document_id,
            version=document.version.value,
            line_count=document.line_count(),
            source_session_id=document.source_session_id,
            last_saved_version=document.last_saved_version,
            recording_conversion_route=document.recording_conversion_route,
            source_capture_excluded_main_window=document.source_capture_excluded_main_window,
        )
        return document

    def import_recording_session(
        self,
        session: RecordingSession,
        *,
        recording_conversion_route: str | None = None,
        source_capture_excluded_main_window: bool | None = None,
    ) -> ScriptDocument:
        log.info(
            "Script document import started",
            event_id="document.imported.started",
            session_id=session.session_id,
            event_count=len(session.events),
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )
        document = self._factory.create_from_recording_session(
            session,
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )
        log.info(
            "Script document import completed",
            event_id="document.imported.completed",
            document_id=document.document_id,
            version=document.version.value,
            line_count=document.line_count(),
            source_session_id=document.source_session_id,
            last_saved_version=document.last_saved_version,
            recording_conversion_route=document.recording_conversion_route,
            source_capture_excluded_main_window=document.source_capture_excluded_main_window,
        )
        return document

    def update_text(
        self,
        document: ScriptDocument,
        new_text: str,
    ) -> ScriptDocument:
        old_line_count = document.line_count()
        document.replace_text(new_text)
        log.info(
            "Script document text updated",
            event_id="document.service.updated",
            document_id=document.document_id,
            version=document.version.value,
            old_line_count=old_line_count,
            new_line_count=document.line_count(),
            is_dirty=document.is_dirty,
            last_saved_version=document.last_saved_version,
        )
        return document

    def mark_saved(
        self,
        document: ScriptDocument,
    ) -> ScriptDocument:
        document.mark_saved()
        log.info(
            "Script document marked saved",
            event_id="document.service.saved",
            document_id=document.document_id,
            version=document.version.value,
            is_dirty=document.is_dirty,
            last_saved_version=document.last_saved_version,
        )
        return document

    def summarize(
        self,
        document: ScriptDocument,
    ) -> ScriptDocumentSummary:
        summary = ScriptDocumentSummary(
            document_id=document.document_id,
            version=document.version.value,
            line_count=document.line_count(),
            is_dirty=document.is_dirty,
            last_saved_version=document.last_saved_version,
            source_session_id=document.source_session_id,
            recording_conversion_route=document.recording_conversion_route,
            source_capture_excluded_main_window=document.source_capture_excluded_main_window,
        )
        log.trace(
            "Script document summary created",
            event_id="document.service.summary",
            document_id=summary.document_id,
            version=summary.version,
            line_count=summary.line_count,
            is_dirty=summary.is_dirty,
            last_saved_version=summary.last_saved_version,
            source_session_id=summary.source_session_id,
            recording_conversion_route=summary.recording_conversion_route,
            source_capture_excluded_main_window=summary.source_capture_excluded_main_window,
        )
        return summary

