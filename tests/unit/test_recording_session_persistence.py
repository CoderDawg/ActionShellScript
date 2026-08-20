from __future__ import annotations

import pytest

from application.persistence.persistence_errors import PersistenceLoadError
from core.recording.recording_session import RecordingSession, RecordingState
from infrastructure.persistence.recording_session_file_store import (
    RecordingSessionFileStore,
)


def test_recording_session_file_store_round_trips_session(tmp_path) -> None:
    path = tmp_path / "session.json"
    store = RecordingSessionFileStore()
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        started_at_ms=10,
        stopped_at_ms=20,
        events=[{"type": "mouse_move", "x": 1, "y": 2}],
    )

    store.save(path, session)
    loaded = store.load(path)

    assert loaded == session


def test_recording_session_file_store_rejects_invalid_payload(tmp_path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"state": "stopped", "events": []}', encoding="utf-8")

    with pytest.raises(PersistenceLoadError):
        RecordingSessionFileStore().load(path)
