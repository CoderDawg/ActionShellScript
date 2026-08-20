from __future__ import annotations

from .event_vocabulary import (
    InterpretedEvent,
    MODIFIER_KEYS,
    build_derived_event,
    ensure_common_fields,
    event_key,
    event_type,
)


def annotate_key_holds(
    events: list[InterpretedEvent],
) -> list[InterpretedEvent]:
    interpreted: list[InterpretedEvent] = []
    index = 0

    while index < len(events):
        current = ensure_common_fields(
            dict(events[index]),
            source_start_index=int(events[index].get("source_start_index", index)),
        )
        key = event_key(current)

        if event_type(current) != "key_down" or key in MODIFIER_KEYS:
            interpreted.append(current)
            index += 1
            continue

        candidate = _try_build_key_hold(events, index=index)
        if candidate is None:
            interpreted.append(current)
            index += 1
            continue

        key_hold_event, next_index = candidate
        interpreted.append(key_hold_event)
        index = next_index

    return interpreted


def annotate_hotkey_sequences(
    events: list[InterpretedEvent],
) -> list[InterpretedEvent]:
    interpreted: list[InterpretedEvent] = []
    index = 0

    while index < len(events):
        current = ensure_common_fields(
            dict(events[index]),
            source_start_index=int(events[index].get("source_start_index", index)),
        )
        if event_type(current) != "key_down" or event_key(current) not in MODIFIER_KEYS:
            interpreted.append(current)
            index += 1
            continue

        candidate = _try_build_hotkey(events, index=index)
        if candidate is None:
            interpreted.append(current)
            index += 1
            continue

        hotkey_event, next_index = candidate
        interpreted.append(hotkey_event)
        index = next_index

    return interpreted


def _try_build_key_hold(
    events: list[InterpretedEvent],
    *,
    index: int,
) -> tuple[InterpretedEvent, int] | None:
    down_event = ensure_common_fields(
        dict(events[index]),
        source_start_index=int(events[index].get("source_start_index", index)),
    )
    key = event_key(down_event)

    for cursor in range(index + 1, len(events)):
        event = ensure_common_fields(
            dict(events[cursor]),
            source_start_index=int(events[cursor].get("source_start_index", cursor)),
        )
        current_type = event_type(event)
        current_key = event_key(event)

        if current_type == "key_down":
            if current_key in MODIFIER_KEYS:
                continue
            return None

        if current_type != "key_up":
            return None

        if current_key in MODIFIER_KEYS:
            continue

        if current_key != key:
            return None

        return (
            build_derived_event(
                "key_hold",
                [dict(raw_event) for raw_event in events[index : cursor + 1]],
                source_start_index=int(down_event["source_start_index"]),
                extra_fields={
                    "key": key,
                },
            ),
            cursor + 1,
        )

    return None


def _try_build_hotkey(
    events: list[InterpretedEvent],
    *,
    index: int,
) -> tuple[InterpretedEvent, int] | None:
    modifier_events: list[InterpretedEvent] = []
    active_modifiers: list[str] = []
    cursor = index

    while cursor < len(events):
        event = ensure_common_fields(
            dict(events[cursor]),
            source_start_index=int(events[cursor].get("source_start_index", cursor)),
        )
        if event_type(event) != "key_down" or event_key(event) not in MODIFIER_KEYS:
            break

        key = event_key(event)
        if key in active_modifiers:
            return None
        active_modifiers.append(key)
        modifier_events.append(event)
        cursor += 1

    if not active_modifiers or cursor >= len(events):
        return None

    trigger = ensure_common_fields(
        dict(events[cursor]),
        source_start_index=int(events[cursor].get("source_start_index", cursor)),
    )
    if event_type(trigger) != "key_hold" or event_key(trigger) in MODIFIER_KEYS:
        return None

    release_events: list[InterpretedEvent] = []
    remaining = set(active_modifiers)
    cursor += 1

    while cursor < len(events) and remaining:
        event = ensure_common_fields(
            dict(events[cursor]),
            source_start_index=int(events[cursor].get("source_start_index", cursor)),
        )
        if event_type(event) != "key_up":
            return None

        key = event_key(event)
        if key not in remaining:
            return None

        release_events.append(event)
        remaining.remove(key)
        cursor += 1

    if remaining:
        return None

    source_events = modifier_events + [trigger] + release_events
    return (
        build_derived_event(
            "hotkey",
            [dict(raw_event) for raw_event in source_events],
            source_start_index=int(modifier_events[0]["source_start_index"]),
            extra_fields={
                "modifiers": list(active_modifiers),
                "trigger_key": event_key(trigger),
                "keys": [*active_modifiers, event_key(trigger)],
            },
        ),
        cursor,
    )
