from __future__ import annotations

from core.recording.recording_session import RecordingSession, RecordingState
from application.script_document_service import ScriptDocumentService
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.document_version import DocumentVersion


def test_service_promotes_generated_script_into_authoritative_document() -> None:
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-9",
        source_action_count=1,
    )

    document = ScriptDocumentService().promote_generated_script(
        generated,
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=True,
    )

    assert document.text == generated.text
    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False
    assert document.last_saved_version is None
    assert document.source_session_id == "session-9"
    assert document.recording_conversion_route == "promote_generated"
    assert document.source_capture_excluded_main_window is True


def test_service_summary_flattens_document_state() -> None:
    service = ScriptDocumentService()
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-10",
        source_action_count=1,
    )

    document = service.promote_generated_script(
        generated,
        recording_conversion_route="promote_generated",
    )
    service.update_text(document, 'Hotkey("ctrl", "v")\n')
    summary = service.summarize(document)

    assert summary.version == 2
    assert summary.line_count == 1
    assert summary.is_dirty is True
    assert summary.last_saved_version is None
    assert summary.source_session_id == "session-10"
    assert summary.recording_conversion_route == "promote_generated"
    assert summary.source_capture_excluded_main_window is None


def test_service_imports_recording_session_into_authoritative_document() -> None:
    session = RecordingSession(
        session_id="session-11",
        state=RecordingState.STOPPED,
        started_at_ms=100,
        stopped_at_ms=180,
        events=[
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
        ],
    )

    document = ScriptDocumentService().import_recording_session(
        session,
        recording_conversion_route="direct_import",
        source_capture_excluded_main_window=False,
    )

    assert document.text.startswith("# Imported directly from RecordingSession\n")
    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False
    assert document.last_saved_version is None
    assert document.source_session_id == "session-11"
    assert document.source_action_count == 1
    assert document.recording_conversion_route == "direct_import"
    assert document.source_capture_excluded_main_window is False
