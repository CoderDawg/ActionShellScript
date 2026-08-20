# core/recording/session_recorder.py
"""
Session recorder.
Purpose:
    primary recording component
    owns start/stop
    owns current session
    collects raw events from capture
    stores raw events only
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .input_capture import InputCapture
from .recorder_config import RecorderConfig
from .recording_session import RecordingSession, RecordingState
from infrastructure.debug_logger import get_diagnostic_logger

log = get_diagnostic_logger("session_recorder")

RawEvent = dict[str, Any]
Clock = Callable[[], int]


class SessionRecorder:
    def __init__(
        self,
        *,
        config: RecorderConfig,
        capture: InputCapture,
        clock: Clock | None = None,
    ) -> None:
        self._config = config
        self._capture = capture
        self._session: RecordingSession | None = None
        self._clock = clock or self._now_ms

    @property
    def is_recording(self) -> bool:
        return (
            self._session is not None
            and self._session.state == RecordingState.RECORDING
        )

    @property
    def session(self) -> RecordingSession | None:
        return self._session

    def start(self, *, session_id: str) -> RecordingSession:
        log.info(
            "Recording start requested",
            event_id="recording.start.started",
            session_id=session_id,
        )

        if self.is_recording:
            log.warning(
                "Recording start rejected because a session is already active",
                event_id="recording.start.already_active",
                session_id=self._session.session_id if self._session is not None else None,
            )
            raise RuntimeError("Recording is already active.")

        session = RecordingSession(session_id=session_id)
        session.start(started_at_ms=self._clock())
        self._session = session

        try:
            self._capture.start(self.handle_raw_event)
        except Exception as exc:
            self._session = None
            log.exception(
                "Recording capture backend failed to start",
                exc,
                event_id="recording.capture.start_failed",
                session_id=session_id,
            )
            raise

        log.info(
            "Recording session started",
            event_id="recording.start.completed",
            session_id=session_id,
        )

        return session

    def stop(self) -> RecordingSession:
        if not self.is_recording or self._session is None:
            log.warning(
                "Recording stop rejected because no session is active",
                event_id="recording.stop.not_active",
            )
            raise RuntimeError("Recording is not active.")

        try:
            self._capture.stop()
        finally:
            self._session.stop(stopped_at_ms=self._clock())

        log.info(
            "Recording session stopped",
            event_id="recording.stop.completed",
            session_id=self._session.session_id,
            event_count=len(self._session.events),
            duration_ms=self._session.duration_ms(),
        )

        return self._session

    def reset(self) -> None:
        if self.is_recording:
            try:
                self._capture.stop()
            finally:
                if self._session is not None:
                    self._session.stop(stopped_at_ms=self._clock())

        if self._session is not None:
            log.info(
                "Recording session reset",
                event_id="recording.service.reset",
                session_id=self._session.session_id,
                event_count=len(self._session.events),
            )

        self._session = None

    def handle_raw_event(self, raw_event: dict[str, object]) -> None:
        if not self.is_recording or self._session is None:
            return

        stored_event = self._prepare_raw_event(raw_event)
        if stored_event is None:
            log.decision(
                "Rejected raw event during normalization",
                event_id="recording.event.reject_invalid",
                raw_event=raw_event,
            )
            return

        if not self._should_store(stored_event["type"]):
            log.decision(
                "Suppressed raw event because capture config disables its type",
                event_id="recording.event.suppressed",
                event_type=stored_event["type"],
            )
            return

        self._session.append_event(stored_event)
        log.trace(
            "Stored raw event",
            event_id="recording.event.stored",
            event_type=stored_event["type"],
            timestamp_ms=stored_event.get("timestamp_ms"),
        )

    def _prepare_raw_event(self, raw_event: dict[str, object]) -> RawEvent | None:
        # Phase 1 keeps raw event authority here: validate the envelope, but do
        # not reinterpret the event into richer domain structures.
        if not isinstance(raw_event, dict):
            return None

        event = dict(raw_event)

        event_type = str(event.get("type", "")).strip().lower()
        if not event_type:
            return None
        event["type"] = event_type

        timestamp_value: Any = event.get("timestamp_ms")
        if timestamp_value is None:
            event["timestamp_ms"] = self._relative_now_ms()
        else:
            try:
                event["timestamp_ms"] = int(timestamp_value)
            except (TypeError, ValueError):
                return None

        return event

    def _should_store(self, event_type: str) -> bool:
        match event_type:
            case "mouse_move":
                return self._config.capture_mouse_moves
            case "mouse_down" | "mouse_up":
                return self._config.capture_mouse_buttons
            case "mouse_wheel":
                return self._config.capture_mouse_wheel
            case "key_down" | "key_up":
                return self._config.capture_keyboard
            case _:
                return False

    def _now_ms(self) -> int:
        return int(time.perf_counter() * 1000)

    def _relative_now_ms(self) -> int:
        if self._session is None or self._session.started_at_ms is None:
            return 0
        return max(0, self._clock() - self._session.started_at_ms)

