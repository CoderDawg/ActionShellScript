from __future__ import annotations

from core.shaping.keyboard_shaper import shape_keyboard_actions
from core.shaping.shaping_config import ShapingConfig


def test_keyboard_shaper_collapses_printable_key_holds_into_text() -> None:
    actions = [
        {
            "type": "key_hold",
            "key": "h",
            "timestamp_ms": 100,
            "end_timestamp_ms": 120,
            "duration_ms": 20,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        },
        {
            "type": "key_hold",
            "key": "i",
            "timestamp_ms": 130,
            "end_timestamp_ms": 150,
            "duration_ms": 20,
            "source_start_index": 2,
            "source_end_index": 3,
            "source_event_count": 2,
        },
    ]

    shaped = shape_keyboard_actions(
        actions,
        config=ShapingConfig(keyboard_output_style="text"),
    )

    assert shaped == [
        {
            "type": "text",
            "text": "hi",
            "timestamp_ms": 100,
            "end_timestamp_ms": 150,
            "duration_ms": 50,
            "source_start_index": 0,
            "source_end_index": 3,
            "source_event_count": 4,
        }
    ]


def test_keyboard_shaper_keeps_structured_output_when_requested() -> None:
    actions = [
        {
            "type": "key_hold",
            "key": "A",
            "timestamp_ms": 100,
            "end_timestamp_ms": 120,
            "duration_ms": 20,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        },
        {
            "type": "hotkey",
            "modifiers": ["CTRL"],
            "trigger_key": "C",
            "keys": ["CTRL", "C"],
            "timestamp_ms": 130,
            "end_timestamp_ms": 160,
            "duration_ms": 30,
            "source_start_index": 2,
            "source_end_index": 5,
            "source_event_count": 4,
        },
    ]

    shaped = shape_keyboard_actions(
        actions,
        config=ShapingConfig(keyboard_output_style="structured"),
    )

    assert shaped == [
        {
            "type": "key_hold",
            "key": "a",
            "timestamp_ms": 100,
            "end_timestamp_ms": 120,
            "duration_ms": 20,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        },
        {
            "type": "hotkey",
            "modifiers": ["ctrl"],
            "trigger_key": "c",
            "keys": ["ctrl", "c"],
            "timestamp_ms": 130,
            "end_timestamp_ms": 160,
            "duration_ms": 30,
            "source_start_index": 2,
            "source_end_index": 5,
            "source_event_count": 4,
        },
    ]


def test_keyboard_shaper_can_disable_text_collapse_without_changing_style() -> None:
    actions = [
        {
            "type": "key_hold",
            "key": "x",
            "timestamp_ms": 100,
            "end_timestamp_ms": 110,
            "duration_ms": 10,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        }
    ]

    shaped = shape_keyboard_actions(
        actions,
        config=ShapingConfig(
            collapse_text_input=False,
            keyboard_output_style="text",
        ),
    )

    assert shaped == [
        {
            "type": "key_hold",
            "key": "x",
            "timestamp_ms": 100,
            "end_timestamp_ms": 110,
            "duration_ms": 10,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        }
    ]


def test_keyboard_shaper_collapses_shift_printable_hotkeys_into_text() -> None:
    actions = [
        {
            "type": "hotkey",
            "modifiers": ["SHIFT"],
            "trigger_key": "T",
            "keys": ["SHIFT", "T"],
            "timestamp_ms": 100,
            "end_timestamp_ms": 130,
            "duration_ms": 30,
            "source_start_index": 0,
            "source_end_index": 3,
            "source_event_count": 4,
        },
        {
            "type": "key_hold",
            "key": "h",
            "timestamp_ms": 140,
            "end_timestamp_ms": 150,
            "duration_ms": 10,
            "source_start_index": 4,
            "source_end_index": 5,
            "source_event_count": 2,
        },
    ]

    shaped = shape_keyboard_actions(
        actions,
        config=ShapingConfig(keyboard_output_style="text"),
    )

    assert shaped == [
        {
            "type": "text",
            "text": "Th",
            "timestamp_ms": 100,
            "end_timestamp_ms": 150,
            "duration_ms": 50,
            "source_start_index": 0,
            "source_end_index": 5,
            "source_event_count": 6,
        }
    ]
