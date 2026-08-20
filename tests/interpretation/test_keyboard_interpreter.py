from __future__ import annotations

from core.interpretation.event_vocabulary import ensure_common_fields
from core.interpretation.keyboard_interpreter import (
    annotate_hotkey_sequences,
    annotate_key_holds,
)


def _normalize(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        ensure_common_fields(dict(event), source_start_index=index)
        for index, event in enumerate(events)
    ]


def test_key_hold_is_collapsed() -> None:
    events = _normalize(
        [
            {"type": "key_down", "key": "a", "timestamp_ms": 100},
            {"type": "key_up", "key": "a", "timestamp_ms": 150},
        ]
    )

    interpreted = annotate_key_holds(events)

    assert interpreted == [
        {
            "type": "key_hold",
            "key": "a",
            "timestamp_ms": 100,
            "end_timestamp_ms": 150,
            "duration_ms": 50,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        }
    ]


def test_hotkey_is_collapsed_from_modifier_and_key_hold() -> None:
    events = annotate_key_holds(
        _normalize(
            [
                {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                {"type": "key_down", "key": "c", "timestamp_ms": 120},
                {"type": "key_up", "key": "c", "timestamp_ms": 150},
                {"type": "key_up", "key": "ctrl", "timestamp_ms": 180},
            ]
        )
    )

    interpreted = annotate_hotkey_sequences(events)

    assert interpreted == [
        {
            "type": "hotkey",
            "modifiers": ["ctrl"],
            "trigger_key": "c",
            "keys": ["ctrl", "c"],
            "timestamp_ms": 100,
            "end_timestamp_ms": 180,
            "duration_ms": 80,
            "source_start_index": 0,
            "source_end_index": 3,
            "source_event_count": 4,
        }
    ]


def test_ordinary_key_sequence_passes_through_as_key_holds() -> None:
    events = _normalize(
        [
            {"type": "key_down", "key": "a", "timestamp_ms": 100},
            {"type": "key_up", "key": "a", "timestamp_ms": 120},
            {"type": "key_down", "key": "b", "timestamp_ms": 140},
            {"type": "key_up", "key": "b", "timestamp_ms": 170},
        ]
    )

    interpreted = annotate_hotkey_sequences(annotate_key_holds(events))

    assert [event["type"] for event in interpreted] == ["key_hold", "key_hold"]
    assert [event["key"] for event in interpreted] == ["a", "b"]


def test_unmatched_key_down_remains_raw() -> None:
    events = _normalize(
        [
            {"type": "key_down", "key": "a", "timestamp_ms": 100},
        ]
    )

    interpreted = annotate_key_holds(events)

    assert [event["type"] for event in interpreted] == ["key_down"]


def test_unmatched_key_up_remains_raw() -> None:
    events = _normalize(
        [
            {"type": "key_up", "key": "a", "timestamp_ms": 100},
        ]
    )

    interpreted = annotate_hotkey_sequences(annotate_key_holds(events))

    assert [event["type"] for event in interpreted] == ["key_up"]


def test_extra_key_event_during_key_hold_keeps_sequence_raw() -> None:
    events = _normalize(
        [
            {"type": "key_down", "key": "a", "timestamp_ms": 100},
            {"type": "key_down", "key": "b", "timestamp_ms": 120},
            {"type": "key_up", "key": "a", "timestamp_ms": 150},
        ]
    )

    interpreted = annotate_key_holds(events)

    assert [event["type"] for event in interpreted] == [
        "key_down",
        "key_down",
        "key_up",
    ]


def test_hotkey_accepts_out_of_order_modifier_release() -> None:
    events = annotate_key_holds(
        _normalize(
            [
                {"type": "key_down", "key": "ctrl", "timestamp_ms": 100},
                {"type": "key_down", "key": "shift", "timestamp_ms": 110},
                {"type": "key_down", "key": "c", "timestamp_ms": 120},
                {"type": "key_up", "key": "c", "timestamp_ms": 150},
                {"type": "key_up", "key": "ctrl", "timestamp_ms": 170},
                {"type": "key_up", "key": "shift", "timestamp_ms": 190},
            ]
        )
    )

    interpreted = annotate_hotkey_sequences(events)

    assert [event["type"] for event in interpreted] == ["hotkey"]
    assert interpreted[0]["keys"] == ["ctrl", "shift", "c"]
