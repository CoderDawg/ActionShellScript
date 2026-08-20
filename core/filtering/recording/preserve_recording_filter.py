from __future__ import annotations

from core.recording.recording_session import RecordingSession, RecordingState

from ..filter_profile import FilterProfile


class PreserveRecordingFilter:
    filter_id = "preserve_recording"

    def apply(
        self,
        source: RecordingSession,
        profile: FilterProfile,
    ) -> RecordingSession:
        del profile
        return RecordingSession(
            session_id=source.session_id,
            state=RecordingState(source.state.value),
            started_at_ms=source.started_at_ms,
            stopped_at_ms=source.stopped_at_ms,
            events=[dict(event) for event in source.events],
        )
