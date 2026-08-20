# application/recording_service.py
"""
Recording service.
Purpose:
    start/stop recording as an application use case
    expose a simple result for CLI or UI
    not own low-level capture logic
"""
from __future__ import annotations

from dataclasses import dataclass

from core.recording.recording_session import RecordingSession
from core.recording.session_recorder import SessionRecorder
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("recording_service")


@dataclass(frozen=True, slots=True)
class RecordingSummary:
    session_id: str
    state: str
    event_count: int
    started_at_ms: int | None
    stopped_at_ms: int | None
    duration_ms: int


class RecordingService:
    def __init__(self, recorder: SessionRecorder) -> None:
        self._recorder = recorder

    def start_recording(self, *, session_id: str) -> RecordingSession:
        session = self._recorder.start(session_id=session_id)
        log.info(
            "Recording service start completed",
            event_id="recording.service.started",
            session_id=session.session_id,
            state=session.state.value,
        )
        return session

    def stop_recording(self) -> RecordingSession:
        session = self._recorder.stop()
        log.info(
            "Recording service stop completed",
            event_id="recording.service.stopped",
            session_id=session.session_id,
            event_count=len(session.events),
            duration_ms=session.duration_ms(),
        )
        return session

    def reset_recording(self) -> None:
        current = self._recorder.session
        self._recorder.reset()
        log.info(
            "Recording service reset completed",
            event_id="recording.service.reset",
            session_id=current.session_id if current is not None else None,
        )

    def is_recording(self) -> bool:
        return self._recorder.is_recording

    def current_session(self) -> RecordingSession | None:
        return self._recorder.session

    def summarize(self, session: RecordingSession) -> RecordingSummary:
        summary = RecordingSummary(
            session_id=session.session_id,
            state=session.state.value,
            event_count=len(session.events),
            started_at_ms=session.started_at_ms,
            stopped_at_ms=session.stopped_at_ms,
            duration_ms=session.duration_ms(),
        )
        log.trace(
            "Recording summary created",
            event_id="recording.service.summary",
            session_id=summary.session_id,
            state=summary.state,
            event_count=summary.event_count,
            duration_ms=summary.duration_ms,
        )
        return summary
