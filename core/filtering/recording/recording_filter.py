from __future__ import annotations

from typing import Protocol

from core.recording.recording_session import RecordingSession

from ..filter_profile import FilterProfile


class RecordingFilter(Protocol):
    filter_id: str

    def apply(
        self,
        source: RecordingSession,
        profile: FilterProfile,
    ) -> RecordingSession: ...
