from __future__ import annotations

import pytest

from core.recording.recording_session import RecordingSession, RecordingState


def test_start_sets_recording_state_and_clears_events() -> None:
    session = RecordingSession(
        session_id="session-1",
        events=[{"type": "stale"}],
        stopped_at_ms=50,
    )

    session.start(started_at_ms=100)

    assert session.state is RecordingState.RECORDING
    assert session.started_at_ms == 100
    assert session.stopped_at_ms is None
    assert session.events == []


def test_stop_sets_stopped_state() -> None:
    session = RecordingSession(session_id="session-1")
    session.start(started_at_ms=100)

    session.stop(stopped_at_ms=160)

    assert session.state is RecordingState.STOPPED
    assert session.stopped_at_ms == 160


def test_append_event_only_while_recording() -> None:
    session = RecordingSession(session_id="session-1")

    with pytest.raises(RuntimeError):
        session.append_event({"type": "mouse_move"})

    session.start(started_at_ms=100)
    session.append_event({"type": "mouse_move", "timestamp_ms": 10})
    session.stop(stopped_at_ms=140)

    assert session.events == [{"type": "mouse_move", "timestamp_ms": 10}]

    with pytest.raises(RuntimeError):
        session.append_event({"type": "mouse_move"})


def test_duration_calculation_uses_start_and_stop() -> None:
    session = RecordingSession(session_id="session-1")

    assert session.duration_ms() == 0

    session.start(started_at_ms=100)
    assert session.duration_ms() == 0

    session.stop(stopped_at_ms=175)
    assert session.duration_ms() == 75
