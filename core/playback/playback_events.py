from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol


class PlaybackEvent(Protocol):
    type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class DelayPlaybackEvent:
    duration_ms: int
    type: ClassVar[str] = "delay"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "duration_ms": self.duration_ms}


@dataclass(frozen=True, slots=True)
class HotkeyPlaybackEvent:
    keys: tuple[str, ...]
    type: ClassVar[str] = "hotkey"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "keys": list(self.keys)}


@dataclass(frozen=True, slots=True)
class KeyDownPlaybackEvent:
    key: str
    type: ClassVar[str] = "key_down"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "key": self.key}


@dataclass(frozen=True, slots=True)
class KeyUpPlaybackEvent:
    key: str
    type: ClassVar[str] = "key_up"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "key": self.key}


@dataclass(frozen=True, slots=True)
class MouseClickPlaybackEvent:
    button: str
    x: int
    y: int
    clicks: int = 1
    speed: int | None = None
    type: ClassVar[str] = "mouse_click"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "type": self.type,
            "button": self.button,
            "x": self.x,
            "y": self.y,
            "clicks": self.clicks,
        }
        if self.speed is not None:
            payload["speed"] = self.speed
        return payload


@dataclass(frozen=True, slots=True)
class MouseDownPlaybackEvent:
    button: str
    x: int
    y: int
    type: ClassVar[str] = "mouse_down"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "button": self.button,
            "x": self.x,
            "y": self.y,
        }


@dataclass(frozen=True, slots=True)
class MouseMovePlaybackEvent:
    x: int
    y: int
    speed: int | None = None
    type: ClassVar[str] = "mouse_move"

    def to_dict(self) -> dict[str, Any]:
        payload = {"type": self.type, "x": self.x, "y": self.y}
        if self.speed is not None:
            payload["speed"] = self.speed
        return payload


@dataclass(frozen=True, slots=True)
class MouseUpPlaybackEvent:
    button: str
    x: int
    y: int
    type: ClassVar[str] = "mouse_up"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "button": self.button,
            "x": self.x,
            "y": self.y,
        }


@dataclass(frozen=True, slots=True)
class MouseWheelPlaybackEvent:
    delta: int
    type: ClassVar[str] = "mouse_wheel"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "delta": self.delta}


@dataclass(frozen=True, slots=True)
class TextPlaybackEvent:
    text: str
    type: ClassVar[str] = "text"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


PlaybackEventType = (
    DelayPlaybackEvent
    | HotkeyPlaybackEvent
    | KeyDownPlaybackEvent
    | KeyUpPlaybackEvent
    | MouseClickPlaybackEvent
    | MouseDownPlaybackEvent
    | MouseMovePlaybackEvent
    | MouseUpPlaybackEvent
    | MouseWheelPlaybackEvent
    | TextPlaybackEvent
)

PLAYBACK_EVENT_TYPES = frozenset(
    {
        "delay",
        "hotkey",
        "key_down",
        "key_up",
        "mouse_click",
        "mouse_down",
        "mouse_move",
        "mouse_up",
        "mouse_wheel",
        "text",
    }
)


def playback_event_to_dict(event: PlaybackEvent) -> dict[str, Any]:
    return event.to_dict()


def playback_event_source_line(event: object) -> int | None:
    source_line = getattr(event, "source_line", None)
    if isinstance(source_line, int) and source_line > 0:
        return source_line
    if isinstance(event, dict):
        source_line = event.get("_source_line")
        if isinstance(source_line, int) and source_line > 0:
            return source_line
    return None


def normalize_shaped_action_to_playback_events(
    action: dict[str, Any],
) -> list[PlaybackEvent] | None:
    action_type = str(action.get("type", "")).strip().lower()

    if action_type == "delay":
        duration_ms = _int_field(action, "duration_ms", default=0)
        if duration_ms is None:
            return None
        return [DelayPlaybackEvent(duration_ms=max(0, duration_ms))]

    if action_type == "mouse_move":
        x = _int_field(action, "x")
        y = _int_field(action, "y")
        if x is None or y is None:
            return None
        speed = _int_field(action, "speed")
        return [MouseMovePlaybackEvent(x=x, y=y, speed=speed)]

    if action_type == "mouse_down":
        button = _normalized_string_field(action, "button") or "left"
        x = _int_field(action, "x")
        y = _int_field(action, "y")
        if x is None or y is None:
            return None
        return [MouseDownPlaybackEvent(button=button, x=x, y=y)]

    if action_type == "mouse_up":
        button = _normalized_string_field(action, "button") or "left"
        x = _int_field(action, "x")
        y = _int_field(action, "y")
        if x is None or y is None:
            return None
        return [MouseUpPlaybackEvent(button=button, x=x, y=y)]

    if action_type == "mouse_click":
        button = _normalized_string_field(action, "button") or "left"
        x = _int_field(action, "x")
        y = _int_field(action, "y")
        clicks = _int_field(action, "clicks", default=1)
        speed = _int_field(action, "speed")
        if x is None or y is None or clicks is None:
            return None
        return [
            MouseClickPlaybackEvent(
                button=button,
                x=x,
                y=y,
                clicks=max(1, clicks),
                speed=speed,
            )
        ]

    if action_type == "mouse_drag":
        button = _normalized_string_field(action, "button")
        start_x = _int_field(action, "start_x")
        start_y = _int_field(action, "start_y")
        end_x = _int_field(action, "end_x")
        end_y = _int_field(action, "end_y")
        duration_ms = _int_field(action, "duration_ms", default=0)
        if (
            not button
            or start_x is None
            or start_y is None
            or end_x is None
            or end_y is None
            or duration_ms is None
        ):
            return None

        events: list[PlaybackEvent] = [
            MouseMovePlaybackEvent(x=start_x, y=start_y),
            MouseDownPlaybackEvent(button=button, x=start_x, y=start_y),
        ]
        if duration_ms > 0:
            events.append(DelayPlaybackEvent(duration_ms=duration_ms))
        events.extend(
            [
                MouseMovePlaybackEvent(x=end_x, y=end_y),
                MouseUpPlaybackEvent(button=button, x=end_x, y=end_y),
            ]
        )
        return events

    if action_type == "mouse_wheel":
        delta = _int_field(action, "delta", default=0)
        if delta is None:
            return None
        return [MouseWheelPlaybackEvent(delta=delta)]

    if action_type == "key_down":
        key = _normalized_string_field(action, "key")
        if not key:
            return None
        return [KeyDownPlaybackEvent(key=key)]

    if action_type == "key_up":
        key = _normalized_string_field(action, "key")
        if not key:
            return None
        return [KeyUpPlaybackEvent(key=key)]

    if action_type == "key_hold":
        key = _normalized_string_field(action, "key")
        duration_ms = _int_field(action, "duration_ms", default=0)
        if not key or duration_ms is None:
            return None
        events: list[PlaybackEvent] = [KeyDownPlaybackEvent(key=key)]
        if duration_ms > 0:
            events.append(DelayPlaybackEvent(duration_ms=duration_ms))
        events.append(KeyUpPlaybackEvent(key=key))
        return events

    if action_type == "hotkey":
        keys = _normalized_string_list(action.get("keys"))
        if not keys:
            trigger_key = _normalized_string_field(action, "trigger_key")
            modifiers = _normalized_string_list(action.get("modifiers"))
            keys = [*modifiers, trigger_key] if trigger_key else modifiers
        if not keys:
            return None
        return [HotkeyPlaybackEvent(keys=tuple(keys))]

    if action_type == "key":
        key = _normalized_string_field(action, "key")
        if not key:
            return None
        return [
            KeyDownPlaybackEvent(key=key),
            KeyUpPlaybackEvent(key=key),
        ]

    if action_type == "text":
        return [TextPlaybackEvent(text=str(action.get("text", "")))]

    return None


def _normalized_string_field(action: dict[str, Any], name: str) -> str:
    value = action.get(name)
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalized for item in value if (normalized := str(item).strip().lower())]


def _int_field(
    action: dict[str, Any],
    name: str,
    *,
    default: int | None = None,
) -> int | None:
    value = action.get(name, default)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
