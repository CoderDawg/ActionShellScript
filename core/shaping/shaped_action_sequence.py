from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ShapedAction = dict[str, Any]
COMMON_SHAPED_ACTION_FIELDS = (
    "timestamp_ms",
    "end_timestamp_ms",
    "duration_ms",
    "source_start_index",
    "source_end_index",
    "source_event_count",
)
SHAPED_ACTION_TYPES = frozenset(
    {
        "delay",
        "hotkey",
        "key_down",
        "key_hold",
        "key_up",
        "mouse_click",
        "mouse_down",
        "mouse_drag",
        "mouse_move",
        "mouse_up",
        "mouse_wheel",
        "text",
    }
)


def common_fields_from_action(action: ShapedAction) -> ShapedAction:
    timestamp_ms = int(action.get("timestamp_ms", 0))
    end_timestamp_ms = int(action.get("end_timestamp_ms", timestamp_ms))
    source_start_index = int(action.get("source_start_index", 0))
    source_end_index = int(action.get("source_end_index", source_start_index))
    return {
        "timestamp_ms": timestamp_ms,
        "end_timestamp_ms": end_timestamp_ms,
        "duration_ms": int(
            action.get("duration_ms", max(0, end_timestamp_ms - timestamp_ms))
        ),
        "source_start_index": source_start_index,
        "source_end_index": source_end_index,
        "source_event_count": int(
            action.get(
                "source_event_count",
                max(1, source_end_index - source_start_index + 1),
            )
        ),
    }


def combined_common_fields(actions: list[ShapedAction]) -> ShapedAction:
    if not actions:
        raise ValueError("combined_common_fields requires at least one action.")

    normalized = [common_fields_from_action(action) for action in actions]
    timestamp_ms = min(int(action["timestamp_ms"]) for action in normalized)
    end_timestamp_ms = max(int(action["end_timestamp_ms"]) for action in normalized)
    source_start_index = min(int(action["source_start_index"]) for action in normalized)
    source_end_index = max(int(action["source_end_index"]) for action in normalized)
    return {
        "timestamp_ms": timestamp_ms,
        "end_timestamp_ms": end_timestamp_ms,
        "duration_ms": max(0, end_timestamp_ms - timestamp_ms),
        "source_start_index": source_start_index,
        "source_end_index": source_end_index,
        "source_event_count": sum(int(action["source_event_count"]) for action in normalized),
    }


@dataclass(slots=True)
class ShapedActionSequence:
    source_session_id: str
    source_interpreted_event_count: int
    actions: list[ShapedAction] = field(default_factory=list)

    def action_count(self) -> int:
        return len(self.actions)
