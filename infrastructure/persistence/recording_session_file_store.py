from __future__ import annotations

from pathlib import Path

from application.persistence.persistence_errors import (
    PersistenceLoadError,
    PersistenceSaveError,
)
from application.persistence.recording_session_store import RecordingSessionStore
from core.recording.recording_session import RecordingSession, RecordingState
from infrastructure.persistence.json_file_store import JsonFileStore


class RecordingSessionFileStore(RecordingSessionStore):
    def __init__(
        self,
        json_store: JsonFileStore | None = None,
    ) -> None:
        self._json_store = json_store or JsonFileStore()

    def load(self, path: Path) -> RecordingSession:
        try:
            payload = self._json_store.load(path)
        except (OSError, ValueError, TypeError) as exc:
            raise PersistenceLoadError(
                f"Could not load recording session from {path}."
            ) from exc

        try:
            return RecordingSession(
                session_id=str(payload["session_id"]),
                state=RecordingState(str(payload.get("state", "stopped"))),
                started_at_ms=self._optional_int(payload.get("started_at_ms")),
                stopped_at_ms=self._optional_int(payload.get("stopped_at_ms")),
                events=[dict(event) for event in payload.get("events", [])],
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise PersistenceLoadError(
                f"Recording session payload is invalid in {path}."
            ) from exc

    def save(self, path: Path, session: RecordingSession) -> None:
        payload = {
            "session_id": session.session_id,
            "state": session.state.value,
            "started_at_ms": session.started_at_ms,
            "stopped_at_ms": session.stopped_at_ms,
            "events": [dict(event) for event in session.events],
        }
        try:
            self._json_store.save(path, payload)
        except (OSError, TypeError, ValueError) as exc:
            raise PersistenceSaveError(
                f"Could not save recording session to {path}."
            ) from exc

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        return int(value)
