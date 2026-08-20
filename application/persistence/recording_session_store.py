from __future__ import annotations

from pathlib import Path
from typing import Protocol

from core.recording.recording_session import RecordingSession


class RecordingSessionStore(Protocol):
    def load(self, path: Path) -> RecordingSession: ...

    def save(self, path: Path, session: RecordingSession) -> None: ...
