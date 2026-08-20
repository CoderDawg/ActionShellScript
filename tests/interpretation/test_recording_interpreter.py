from __future__ import annotations

from copy import deepcopy

from core.interpretation.recording_interpreter import RecordingInterpreter
from core.recording.recording_session import RecordingSession, RecordingState


def test_full_pipeline_output_is_meaningful() -> None:
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        started_at_ms=100,
        stopped_at_ms=250,
        events=[
            {"type": "mouse_down", "button": "left", "x": 10, "y": 10, "timestamp_ms": 100},
            {"type": "mouse_up", "button": "left", "x": 10, "y": 10, "timestamp_ms": 130},
            {"type": "mouse_down", "button": "left", "x": 20, "y": 20, "timestamp_ms": 140},
            {"type": "mouse_move", "x": 40, "y": 20, "timestamp_ms": 165},
            {"type": "mouse_up", "button": "left", "x": 40, "y": 20, "timestamp_ms": 190},
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 200},
            {"type": "key_down", "key": "c", "timestamp_ms": 210},
            {"type": "key_up", "key": "c", "timestamp_ms": 220},
            {"type": "key_up", "key": "ctrl", "timestamp_ms": 230},
        ],
    )

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == [
        "mouse_click",
        "mouse_drag",
        "hotkey",
    ]
    assert interpreted.source_session_id == "session-1"
    assert interpreted.source_event_count == 9


def test_interpretation_does_not_mutate_input_session_events() -> None:
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        events=[
            {"type": "mouse_down", "button": "left", "x": 10, "y": 10, "timestamp_ms": 100},
            {"type": "mouse_up", "button": "left", "x": 10, "y": 10, "timestamp_ms": 130},
        ],
    )
    original_events = deepcopy(session.events)

    RecordingInterpreter().interpret(session)

    assert session.events == original_events
