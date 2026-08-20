from __future__ import annotations

from .event_vocabulary import (
    InterpretedEvent,
    build_derived_event,
    distance_squared,
    ensure_common_fields,
    event_type,
)
from .interpretation_config import InterpretationConfig


def annotate_drag_sequences(
    events: list[InterpretedEvent],
    *,
    config: InterpretationConfig,
) -> list[InterpretedEvent]:
    annotated: list[InterpretedEvent] = []
    index = 0

    while index < len(events):
        current = dict(events[index])
        if event_type(current) != "mouse_down":
            annotated.append(
                ensure_common_fields(
                    current,
                    source_start_index=int(current.get("source_start_index", index)),
                )
            )
            index += 1
            continue

        candidate = _try_build_drag(events, index=index, config=config)
        if candidate is None:
            annotated.append(
                ensure_common_fields(
                    current,
                    source_start_index=int(current.get("source_start_index", index)),
                )
            )
            index += 1
            continue

        drag_event, next_index = candidate
        annotated.append(drag_event)
        index = next_index

    return annotated


def _try_build_drag(
    events: list[InterpretedEvent],
    *,
    index: int,
    config: InterpretationConfig,
) -> tuple[InterpretedEvent, int] | None:
    down_event = ensure_common_fields(dict(events[index]), source_start_index=index)
    button = str(down_event.get("button", "")).strip().lower()
    start_x = int(down_event.get("x", 0))
    start_y = int(down_event.get("y", 0))
    max_distance_sq = 0
    saw_move = False

    for cursor in range(index + 1, len(events)):
        event = ensure_common_fields(
            dict(events[cursor]),
            source_start_index=int(events[cursor].get("source_start_index", cursor)),
        )
        current_type = event_type(event)

        if current_type == "mouse_move":
            saw_move = True
            move_distance_sq = distance_squared(
                start_x,
                start_y,
                int(event.get("x", start_x)),
                int(event.get("y", start_y)),
            )
            max_distance_sq = max(max_distance_sq, move_distance_sq)
            continue

        if current_type != "mouse_up":
            return None

        if str(event.get("button", "")).strip().lower() != button:
            return None

        end_x = int(event.get("x", start_x))
        end_y = int(event.get("y", start_y))
        max_distance_sq = max(
            max_distance_sq,
            distance_squared(start_x, start_y, end_x, end_y),
        )
        duration_ms = int(event.get("timestamp_ms", 0)) - int(
            down_event.get("timestamp_ms", 0)
        )
        if (
            not saw_move
            or max_distance_sq < config.drag_min_distance_px**2
            or duration_ms < config.drag_min_duration_ms
        ):
            return None

        source_events = [dict(raw_event) for raw_event in events[index : cursor + 1]]
        return (
            build_derived_event(
                "mouse_drag",
                source_events,
                source_start_index=int(down_event["source_start_index"]),
                extra_fields={
                    "button": button or "left",
                    "x": end_x,
                    "y": end_y,
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": end_x,
                    "end_y": end_y,
                    "distance_px": int(max_distance_sq ** 0.5),
                },
            ),
            cursor + 1,
        )

    return None
