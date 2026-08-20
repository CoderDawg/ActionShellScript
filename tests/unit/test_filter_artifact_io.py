from __future__ import annotations

from apps.cli.filter_artifact_io import (
    load_interpreted_recording,
    load_interpretation_source,
    load_recording_session,
    load_shaped_action_sequence,
    load_shaping_source,
    load_script_document,
    save_interpreted_recording,
    save_recording_session,
    save_shaped_action_sequence,
    save_script_document,
)
from core.interpretation.interpreted_recording import InterpretedRecording
from core.recording.recording_session import RecordingSession, RecordingState
from core.shaping.shaped_action_sequence import ShapedActionSequence
from editor.document.script_document import ScriptDocument


def test_recording_session_round_trips_through_json(tmp_path) -> None:
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        started_at_ms=10,
        stopped_at_ms=20,
        events=[{"type": "mouse_move", "x": 1, "y": 2}],
    )

    path = tmp_path / "session.json"
    save_recording_session(session, str(path))

    loaded = load_recording_session(str(path))

    assert loaded == session


def test_interpreted_recording_round_trips_through_json(tmp_path) -> None:
    interpreted = InterpretedRecording(
        source_session_id="session-2",
        source_event_count=4,
        events=[{"type": "text", "text": "hi"}],
    )

    path = tmp_path / "interpreted.json"
    save_interpreted_recording(interpreted, str(path))

    loaded = load_interpreted_recording(str(path))
    inferred = load_interpretation_source(str(path))

    assert loaded == interpreted
    assert inferred == interpreted


def test_shaped_action_sequence_round_trips_through_json(tmp_path) -> None:
    shaped = ShapedActionSequence(
        source_session_id="session-3",
        source_interpreted_event_count=2,
        actions=[{"type": "mouse_move", "x": 3, "y": 4}],
    )

    path = tmp_path / "shaped.json"
    save_shaped_action_sequence(shaped, str(path))

    loaded = load_shaped_action_sequence(str(path))
    inferred = load_shaping_source(str(path))

    assert loaded == shaped
    assert inferred == shaped


def test_script_document_round_trips_through_text(tmp_path) -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="Func Demo()\nEndFunc\n",
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=False,
    )

    path = tmp_path / "document.ass"
    save_script_document(document, str(path))

    loaded = load_script_document(str(path))

    assert loaded.text == document.text
    assert loaded.document_id == "document"
    assert loaded.source_path == str(path)
    assert (path.parent / f"{path.name}.meta.json").exists()
    assert loaded.source_session_id == "session-1"
    assert loaded.source_action_count == 2
    assert loaded.generated_from_recording is True
    assert loaded.recording_conversion_route == "promote_generated"
    assert loaded.source_capture_excluded_main_window is False
