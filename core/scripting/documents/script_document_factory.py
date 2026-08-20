from __future__ import annotations

import json
import uuid

from core.recording.recording_session import RecordingSession
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument


class ScriptDocumentFactory:
    def create_from_generated_script(
        self,
        generated: GeneratedScript,
        *,
        recording_conversion_route: str | None = None,
        source_capture_excluded_main_window: bool | None = None,
    ) -> ScriptDocument:
        return ScriptDocument(
            document_id=str(uuid.uuid4()),
            text=generated.text,
            version=DocumentVersion(),
            is_dirty=False,
            source_session_id=generated.source_session_id,
            source_action_count=generated.source_action_count,
            generated_from_recording=True,
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )

    def create_from_recording_session(
        self,
        session: RecordingSession,
        *,
        recording_conversion_route: str | None = None,
        source_capture_excluded_main_window: bool | None = None,
    ) -> ScriptDocument:
        lines = [
            "# Imported directly from RecordingSession",
            f"# Session ID: {session.session_id}",
            f"# State: {session.state.value}",
        ]
        if session.started_at_ms is not None:
            lines.append(f"# Started at: {session.started_at_ms}")
        if session.stopped_at_ms is not None:
            lines.append(f"# Stopped at: {session.stopped_at_ms}")
        lines.append(f"# Event count: {len(session.events)}")
        if session.events:
            lines.append("# Raw events:")
            for event in session.events:
                lines.append(f"# {json.dumps(event, sort_keys=True)}")
        else:
            lines.append("# Raw events: <none>")
        lines.append("")

        return ScriptDocument(
            document_id=str(uuid.uuid4()),
            text="\n".join(lines),
            version=DocumentVersion(),
            is_dirty=False,
            source_session_id=session.session_id,
            source_action_count=len(session.events),
            generated_from_recording=True,
            recording_conversion_route=recording_conversion_route,
            source_capture_excluded_main_window=source_capture_excluded_main_window,
        )
