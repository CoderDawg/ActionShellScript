from __future__ import annotations

from application.interpretation_filter_service import InterpretationFilterService
from application.document_filter_service import DocumentFilterService
from application.recording_filter_service import RecordingFilterService
from application.shaping_filter_service import ShapingFilterService
from core.recording.recording_session import RecordingSession, RecordingState
from editor.document.script_document import ScriptDocument


def test_recording_filter_service_cleans_mouse_jitter() -> None:
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        started_at_ms=10,
        stopped_at_ms=20,
        events=[
            {"type": "mouse_move", "x": 10, "y": 10},
            {"type": "mouse_move", "x": 10, "y": 10},
            {"type": "mouse_move", "x": 12, "y": 10},
        ],
    )

    service = RecordingFilterService()
    result = service.apply_filter(session, "mouse_jitter_cleanup")
    summary = service.summarize(
        result,
        profile_id="mouse_jitter_cleanup",
        source_session_id=session.session_id,
        source_event_count=len(session.events),
    )

    assert result.value is not session
    assert result.value.events == [
        {"type": "mouse_move", "x": 10, "y": 10},
        {"type": "mouse_move", "x": 12, "y": 10},
    ]
    assert result.applied_filters == ["mouse_jitter_cleanup"]
    assert summary.filtered_event_count == 2


def test_interpretation_filter_service_refines_text_runs() -> None:
    session = RecordingSession(
        session_id="session-2",
        state=RecordingState.STOPPED,
        events=[
            {"type": "key_down", "key": "h", "timestamp_ms": 100},
            {"type": "key_up", "key": "h", "timestamp_ms": 120},
            {"type": "key_down", "key": "i", "timestamp_ms": 130},
            {"type": "key_up", "key": "i", "timestamp_ms": 150},
        ],
    )

    service = InterpretationFilterService()
    result = service.apply_filter(session, "text_run_refinement")

    assert [event["type"] for event in result.value.events] == ["text"]
    assert result.value.events[0]["text"] == "hi"
    assert result.applied_filters == ["text_run_refinement"]


def test_interpretation_filter_service_refines_shift_printable_hotkeys_into_text() -> None:
    session = RecordingSession(
        session_id="session-2b",
        state=RecordingState.STOPPED,
        events=[
            {"type": "key_down", "key": "shift", "timestamp_ms": 100},
            {"type": "key_down", "key": "t", "timestamp_ms": 110},
            {"type": "key_up", "key": "t", "timestamp_ms": 120},
            {"type": "key_up", "key": "shift", "timestamp_ms": 130},
            {"type": "key_down", "key": "h", "timestamp_ms": 140},
            {"type": "key_up", "key": "h", "timestamp_ms": 150},
        ],
    )

    service = InterpretationFilterService()
    result = service.apply_filter(session, "text_run_refinement")

    assert [event["type"] for event in result.value.events] == ["text"]
    assert result.value.events[0]["text"] == "Th"
    assert result.applied_filters == ["text_run_refinement"]


def test_shaping_filter_service_lists_default_profiles() -> None:
    service = ShapingFilterService()

    assert "smooth_mouse" in service.list_profile_ids()


def test_shaping_filter_service_smooths_small_mouse_jitter() -> None:
    session = RecordingSession(
        session_id="session-3",
        state=RecordingState.STOPPED,
        events=[
            {"type": "mouse_move", "x": 10, "y": 10, "timestamp_ms": 100},
            {"type": "key_down", "key": "a", "timestamp_ms": 110},
            {"type": "key_up", "key": "a", "timestamp_ms": 120},
            {"type": "mouse_move", "x": 11, "y": 10, "timestamp_ms": 130},
        ],
    )

    service = ShapingFilterService()
    result = service.apply_filter(session, "smooth_mouse")

    assert [action["type"] for action in result.value.actions] == [
        "mouse_move",
        "key_hold",
    ]
    assert result.value.actions[0]["x"] == 10
    assert result.value.actions[0]["y"] == 10


def test_document_filter_service_copies_document() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="Func Demo(a,b)\r\nCallThing(1,2)\r\nEndFunc\r\n\r\n\r\n",
    )

    service = DocumentFilterService()
    result = service.apply_filter(document, "normalize_document")

    assert result.value is not document
    assert result.value.text == (
        "Func Demo( a, b )\n"
        "    CallThing(1, 2)\n"
        "EndFunc\n"
    )
    assert result.applied_filters == ["normalize_document"]
