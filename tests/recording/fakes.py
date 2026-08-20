from __future__ import annotations

from typing import Any

from core.recording.input_capture import RawEventHandler


class FakeInputCaptureBackend:
    def __init__(self, *, fail_on_start: Exception | None = None) -> None:
        self.fail_on_start = fail_on_start
        self.started = False
        self.stopped = False
        self.on_event: RawEventHandler | None = None

    def start(self, on_event: RawEventHandler) -> None:
        if self.fail_on_start is not None:
            raise self.fail_on_start

        self.started = True
        self.stopped = False
        self.on_event = on_event

    def stop(self) -> None:
        self.stopped = True
        self.started = False

    def emit(self, event: dict[str, Any]) -> None:
        if self.on_event is None:
            raise RuntimeError("Cannot emit without a registered event handler.")
        self.on_event(event)
