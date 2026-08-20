from __future__ import annotations

from dataclasses import dataclass

from .event_vocabulary import (
    InterpretedEvent,
    RawEvent,
    build_derived_event,
    distance_squared,
    ensure_common_fields,
    event_type,
)
from .interpretation_config import InterpretationConfig


@dataclass(frozen=True, slots=True)
class _ClickCandidate:
    start_index: int
    end_exclusive: int
    button: str
    press_x: int
    press_y: int
    release_x: int
    release_y: int
    max_move_distance_sq: int
    source_events: list[RawEvent]


def collapse_mouse_button_sequences_to_clicks(
    events: list[RawEvent],
    *,
    config: InterpretationConfig,
) -> list[InterpretedEvent]:
    interpreted: list[InterpretedEvent] = []
    index = 0

    while index < len(events):
        current = dict(events[index])

        if event_type(current) != "mouse_down":
            interpreted.append(ensure_common_fields(current, source_start_index=index))
            index += 1
            continue

        first_click = _try_build_single_click(events, index=index, config=config)
        if first_click is None:
            interpreted.append(ensure_common_fields(current, source_start_index=index))
            index += 1
            continue

        second_click = _try_build_double_click(
            events,
            first_click=first_click,
            config=config,
        )
        if second_click is not None:
            interpreted.append(_build_click_event(first_click, second_click))
            index = second_click.end_exclusive
            continue

        interpreted.append(_build_click_event(first_click))
        index = first_click.end_exclusive

    return interpreted


def _try_build_single_click(
    events: list[RawEvent],
    *,
    index: int,
    config: InterpretationConfig,
) -> _ClickCandidate | None:
    down_event = dict(events[index])
    button = str(down_event.get("button", "")).strip().lower()
    press_x = int(down_event.get("x", 0))
    press_y = int(down_event.get("y", 0))
    max_move_distance_sq = 0

    for cursor in range(index + 1, len(events)):
        event = dict(events[cursor])
        current_type = event_type(event)

        if current_type == "mouse_move":
            move_distance_sq = distance_squared(
                press_x,
                press_y,
                int(event.get("x", press_x)),
                int(event.get("y", press_y)),
            )
            max_move_distance_sq = max(max_move_distance_sq, move_distance_sq)
            if move_distance_sq > config.click_max_move_distance_px**2:
                return None
            continue

        if current_type != "mouse_up":
            return None

        if str(event.get("button", "")).strip().lower() != button:
            return None

        release_x = int(event.get("x", press_x))
        release_y = int(event.get("y", press_y))
        release_distance_sq = distance_squared(press_x, press_y, release_x, release_y)
        max_move_distance_sq = max(max_move_distance_sq, release_distance_sq)
        if release_distance_sq > config.click_max_move_distance_px**2:
            return None

        return _ClickCandidate(
            start_index=index,
            end_exclusive=cursor + 1,
            button=button or "left",
            press_x=press_x,
            press_y=press_y,
            release_x=release_x,
            release_y=release_y,
            max_move_distance_sq=max_move_distance_sq,
            source_events=[dict(raw_event) for raw_event in events[index : cursor + 1]],
        )

    return None


def _try_build_double_click(
    events: list[RawEvent],
    *,
    first_click: _ClickCandidate,
    config: InterpretationConfig,
) -> _ClickCandidate | None:
    cursor = first_click.end_exclusive
    inter_click_events: list[RawEvent] = []

    while cursor < len(events) and event_type(events[cursor]) == "mouse_move":
        move_event = dict(events[cursor])
        inter_click_distance_sq = distance_squared(
            first_click.release_x,
            first_click.release_y,
            int(move_event.get("x", first_click.release_x)),
            int(move_event.get("y", first_click.release_y)),
        )
        if (
            inter_click_distance_sq
            > config.double_click_max_inter_click_move_distance_px**2
        ):
            return None
        inter_click_events.append(move_event)
        cursor += 1

    if cursor >= len(events) or event_type(events[cursor]) != "mouse_down":
        return None

    second_click = _try_build_single_click(events, index=cursor, config=config)
    if second_click is None:
        return None

    first_up = first_click.source_events[-1]
    second_down = second_click.source_events[0]
    second_up = second_click.source_events[-1]

    if second_click.button != first_click.button:
        return None

    pause_ms = int(second_down.get("timestamp_ms", 0)) - int(first_up.get("timestamp_ms", 0))
    if pause_ms > config.double_click_max_pause_ms:
        return None

    interval_ms = int(second_up.get("timestamp_ms", 0)) - int(
        first_click.source_events[0].get("timestamp_ms", 0)
    )
    if interval_ms > config.double_click_max_interval_ms:
        return None

    anchor_distance_sq = distance_squared(
        first_click.release_x,
        first_click.release_y,
        second_click.release_x,
        second_click.release_y,
    )
    if anchor_distance_sq > config.double_click_max_distance_px**2:
        return None

    return _ClickCandidate(
        start_index=first_click.start_index,
        end_exclusive=second_click.end_exclusive,
        button=first_click.button,
        press_x=first_click.press_x,
        press_y=first_click.press_y,
        release_x=second_click.release_x,
        release_y=second_click.release_y,
        max_move_distance_sq=max(
            first_click.max_move_distance_sq,
            second_click.max_move_distance_sq,
            *(distance_squared(
                first_click.release_x,
                first_click.release_y,
                int(move.get("x", first_click.release_x)),
                int(move.get("y", first_click.release_y)),
            ) for move in inter_click_events),
        ),
        source_events=(
            first_click.source_events
            + inter_click_events
            + second_click.source_events
        ),
    )


def _build_click_event(
    first_click: _ClickCandidate,
    second_click: _ClickCandidate | None = None,
) -> InterpretedEvent:
    click_count = 2 if second_click is not None else 1
    final_click = second_click or first_click
    return build_derived_event(
        "mouse_click",
        final_click.source_events,
        source_start_index=first_click.start_index,
        extra_fields={
            "button": final_click.button,
            "clicks": click_count,
            "x": final_click.release_x,
            "y": final_click.release_y,
            "press_x": first_click.press_x,
            "press_y": first_click.press_y,
            "release_x": final_click.release_x,
            "release_y": final_click.release_y,
            "max_move_distance_px": _sqrt_distance(final_click.max_move_distance_sq),
        },
    )


def _sqrt_distance(distance_sq: int) -> int:
    return int(distance_sq ** 0.5)
