from __future__ import annotations

from typing import Any


InterpretedEvent = dict[str, Any]
RawEvent = dict[str, Any]

MODIFIER_KEYS = frozenset(
    {
        "alt",
        "alt_gr",
        "alt_l",
        "alt_r",
        "cmd",
        "cmd_l",
        "cmd_r",
        "ctrl",
        "ctrl_l",
        "ctrl_r",
        "shift",
        "shift_l",
        "shift_r",
        "win",
        "win_l",
        "win_r",
    }
)


def event_type(event: RawEvent) -> str:
    return str(event.get("type", "")).strip().lower()


def event_key(event: RawEvent) -> str:
    return str(event.get("key", "")).strip().lower()


def ensure_common_fields(
    event: RawEvent,
    *,
    source_start_index: int,
) -> InterpretedEvent:
    interpreted = dict(event)
    timestamp_ms = int(interpreted.get("timestamp_ms", 0))
    end_timestamp_ms = int(interpreted.get("end_timestamp_ms", timestamp_ms))
    source_end_index = int(interpreted.get("source_end_index", source_start_index))

    interpreted["timestamp_ms"] = timestamp_ms
    interpreted["end_timestamp_ms"] = end_timestamp_ms
    interpreted["duration_ms"] = int(
        interpreted.get("duration_ms", max(0, end_timestamp_ms - timestamp_ms))
    )
    interpreted["source_start_index"] = int(
        interpreted.get("source_start_index", source_start_index)
    )
    interpreted["source_end_index"] = source_end_index
    interpreted["source_event_count"] = int(
        interpreted.get(
            "source_event_count",
            max(1, source_end_index - interpreted["source_start_index"] + 1),
        )
    )
    return interpreted


def build_derived_event(
    event_type_name: str,
    source_events: list[RawEvent],
    *,
    source_start_index: int,
    extra_fields: dict[str, Any] | None = None,
) -> InterpretedEvent:
    if not source_events:
        raise ValueError("Derived interpreted events require at least one source event.")

    normalized_source = [
        ensure_common_fields(event, source_start_index=source_start_index + offset)
        for offset, event in enumerate(source_events)
    ]
    first = normalized_source[0]
    last = normalized_source[-1]

    derived: InterpretedEvent = {
        "type": event_type_name,
        "timestamp_ms": first["timestamp_ms"],
        "end_timestamp_ms": last["end_timestamp_ms"],
        "duration_ms": max(0, last["end_timestamp_ms"] - first["timestamp_ms"]),
        "source_start_index": min(
            int(event["source_start_index"]) for event in normalized_source
        ),
        "source_end_index": max(int(event["source_end_index"]) for event in normalized_source),
        "source_event_count": sum(int(event["source_event_count"]) for event in normalized_source),
    }
    if extra_fields:
        derived.update(extra_fields)
    return derived


def distance_squared(x1: int, y1: int, x2: int, y2: int) -> int:
    dx = int(x2) - int(x1)
    dy = int(y2) - int(y1)
    return (dx * dx) + (dy * dy)
