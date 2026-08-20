from __future__ import annotations

from core.recording.recording_session import RecordingSession, RecordingState
from core.scripting.documents.script_document_factory import ScriptDocumentFactory
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.document_version import DocumentVersion


def test_factory_promotes_generated_script_with_provenance() -> None:
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-7",
        source_action_count=1,
    )

    document = ScriptDocumentFactory().create_from_generated_script(
        generated,
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=True,
    )

    assert document.text == generated.text
    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False
    assert document.source_session_id == "session-7"
    assert document.source_action_count == 1
    assert document.generated_from_recording is True
    assert document.recording_conversion_route == "promote_generated"
    assert document.source_capture_excluded_main_window is True


def test_factory_imports_recording_session_with_minimal_translation() -> None:
    session = RecordingSession(
        session_id="session-8",
        state=RecordingState.STOPPED,
        started_at_ms=100,
        stopped_at_ms=180,
        events=[
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
        ],
    )

    document = ScriptDocumentFactory().create_from_recording_session(
        session,
        recording_conversion_route="direct_import",
        source_capture_excluded_main_window=False,
    )

    assert document.text.startswith(
        "# Imported directly from RecordingSession\n"
        "# Session ID: session-8\n"
        "# State: stopped\n"
        "# Started at: 100\n"
        "# Stopped at: 180\n"
        "# Event count: 1\n"
    )
    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False
    assert document.source_session_id == "session-8"
    assert document.source_action_count == 1
    assert document.generated_from_recording is True
    assert document.recording_conversion_route == "direct_import"
    assert document.source_capture_excluded_main_window is False
