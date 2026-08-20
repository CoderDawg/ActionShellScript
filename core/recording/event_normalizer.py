"""
Event normalizer.
Purpose:
    reserved for later derived workflows
    not part of the authoritative phase-1 recording path
    must not replace raw-event storage in RecordingSession
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RecordedEvent:
    type: str
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class MouseMoveEvent(RecordedEvent):
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class MouseButtonEvent(RecordedEvent):
    button: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class MouseWheelEvent(RecordedEvent):
    delta: int
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True, slots=True)
class KeyEvent(RecordedEvent):
    key: str


class EventNormalizer:
    def normalize_event(self, raw_event: dict[str, Any]) -> RecordedEvent | None:
        event_type = str(raw_event.get("type", "")).strip().lower()

        if event_type == "mouse_move":
            return MouseMoveEvent(
                type="mouse_move",
                timestamp_ms=self._int(raw_event.get("timestamp_ms")),
                x=self._int(raw_event.get("x")),
                y=self._int(raw_event.get("y")),
            )

        if event_type in {"mouse_down", "mouse_up"}:
            return MouseButtonEvent(
                type=event_type,
                timestamp_ms=self._int(raw_event.get("timestamp_ms")),
                button=str(raw_event.get("button", "left")).lower(),
                x=self._int(raw_event.get("x")),
                y=self._int(raw_event.get("y")),
            )

        if event_type == "mouse_wheel":
            return MouseWheelEvent(
                type="mouse_wheel",
                timestamp_ms=self._int(raw_event.get("timestamp_ms")),
                delta=self._int(raw_event.get("delta")),
                x=self._optional_int(raw_event.get("x")),
                y=self._optional_int(raw_event.get("y")),
            )

        if event_type in {"key_down", "key_up"}:
            return KeyEvent(
                type=event_type,
                timestamp_ms=self._int(raw_event.get("timestamp_ms")),
                key=str(raw_event.get("key", "")).strip().lower(),
            )

        return None

    def _int(self, value: Any) -> int:
        return int(value)

    def _optional_int(self, value: Any) -> int | None:
        return None if value is None else int(value)
