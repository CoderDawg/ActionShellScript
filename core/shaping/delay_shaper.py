from __future__ import annotations

from typing import Any

from .shaping_config import ShapingConfig
from .shaped_action_sequence import combined_common_fields, common_fields_from_action


ShapedAction = dict[str, Any]


def shape_delays(
    actions: list[ShapedAction],
    *,
    config: ShapingConfig,
) -> list[ShapedAction]:
    if not config.emit_delays:
        return [
            dict(action)
            for action in actions
            if str(action.get("type", "")).strip().lower() != "delay"
        ]

    shaped: list[ShapedAction] = []
    pending_delays: list[ShapedAction] = []

    for action in actions:
        current = dict(action)
        action_type = str(current.get("type", "")).strip().lower()

        if action_type != "delay":
            _flush_pending_delays(shaped, pending_delays)
            shaped.append(current)
            continue

        duration_ms = int(current.get("duration_ms", 0))
        if duration_ms < config.min_delay_ms:
            continue
        if config.max_delay_ms is not None:
            duration_ms = min(duration_ms, config.max_delay_ms)

        delay_action = {
            "type": "delay",
            "duration_ms": duration_ms,
            **common_fields_from_action(current),
        }
        delay_action["end_timestamp_ms"] = (
            int(delay_action["timestamp_ms"]) + duration_ms
        )
        delay_action["duration_ms"] = duration_ms

        if config.collapse_consecutive_delays:
            pending_delays.append(delay_action)
        else:
            shaped.append(delay_action)

    _flush_pending_delays(shaped, pending_delays)

    return shaped


def _flush_pending_delays(
    shaped: list[ShapedAction],
    pending_delays: list[ShapedAction],
) -> None:
    if not pending_delays:
        return

    if len(pending_delays) == 1:
        shaped.append(dict(pending_delays[0]))
        pending_delays.clear()
        return

    total_duration_ms = sum(int(action.get("duration_ms", 0)) for action in pending_delays)
    combined = combined_common_fields(pending_delays)
    combined["duration_ms"] = total_duration_ms
    combined["end_timestamp_ms"] = int(combined["timestamp_ms"]) + total_duration_ms
    shaped.append(
        {
            "type": "delay",
            **combined,
        }
    )
    pending_delays.clear()
