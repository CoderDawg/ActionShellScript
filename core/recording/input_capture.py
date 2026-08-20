# core/recording/input_capture.py
"""
Input capture adapter.
Purpose:
    adapter around whatever backend captures OS input
    emits low-level raw events
    knows nothing about sessions, playback, scripts, or UI
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


RawEvent = dict[str, Any]
RawEventHandler = Callable[[RawEvent], None]


class InputCaptureBackend(Protocol):
    def start(self, on_event: RawEventHandler) -> None: ...
    def stop(self) -> None: ...


@dataclass(slots=True)
class InputCapture:
    backend: InputCaptureBackend

    def start(self, on_event: RawEventHandler) -> None:
        self.backend.start(on_event)

    def stop(self) -> None:
        self.backend.stop()
