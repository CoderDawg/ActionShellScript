# core/recording/recording_session.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


RawEvent = dict[str, Any]


class RecordingState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPED = "stopped"


@dataclass(slots=True)
class RecordingSession:
    session_id: str
    state: RecordingState = RecordingState.IDLE
    started_at_ms: int | None = None
    stopped_at_ms: int | None = None
    events: list[RawEvent] = field(default_factory=list)

    def duration_ms(self) -> int:
        if self.started_at_ms is None or self.stopped_at_ms is None:
            return 0
        return max(0, self.stopped_at_ms - self.started_at_ms)

    def start(self, started_at_ms: int) -> None:
        if self.state == RecordingState.RECORDING:
            raise RuntimeError("Recording session is already active.")

        self.state = RecordingState.RECORDING
        self.started_at_ms = int(started_at_ms)
        self.stopped_at_ms = None
        self.events.clear()

    def stop(self, stopped_at_ms: int) -> None:
        if self.state != RecordingState.RECORDING:
            raise RuntimeError("Recording session is not active.")

        self.state = RecordingState.STOPPED
        self.stopped_at_ms = int(stopped_at_ms)

    def append_event(self, event: RawEvent) -> None:
        if self.state != RecordingState.RECORDING:
            raise RuntimeError("Cannot append event when recording is not active.")

        self.events.append(dict(event))
