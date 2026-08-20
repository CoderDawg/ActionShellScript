from __future__ import annotations

from core.shaping.delay_shaper import shape_delays
from core.shaping.shaping_config import ShapingConfig


def test_delay_shaper_clamps_and_collapses_consecutive_delays() -> None:
    actions = [
        {
            "type": "delay",
            "timestamp_ms": 100,
            "end_timestamp_ms": 110,
            "duration_ms": 10,
            "source_start_index": 0,
            "source_end_index": 0,
            "source_event_count": 1,
        },
        {
            "type": "delay",
            "timestamp_ms": 120,
            "end_timestamp_ms": 150,
            "duration_ms": 30,
            "source_start_index": 1,
            "source_end_index": 1,
            "source_event_count": 1,
        },
        {"type": "mouse_click", "button": "left", "x": 5, "y": 5},
    ]

    shaped = shape_delays(
        actions,
        config=ShapingConfig(min_delay_ms=5, max_delay_ms=20),
    )

    assert shaped == [
        {
            "type": "delay",
            "timestamp_ms": 100,
            "end_timestamp_ms": 130,
            "duration_ms": 30,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        },
        {"type": "mouse_click", "button": "left", "x": 5, "y": 5},
    ]


def test_delay_shaper_can_drop_delays_entirely() -> None:
    actions = [
        {"type": "delay", "duration_ms": 50},
        {"type": "key_hold", "key": "a"},
    ]

    shaped = shape_delays(actions, config=ShapingConfig(emit_delays=False))

    assert shaped == [{"type": "key_hold", "key": "a"}]


def test_delay_shaper_can_keep_separate_delay_actions() -> None:
    actions = [
        {
            "type": "delay",
            "timestamp_ms": 100,
            "end_timestamp_ms": 110,
            "duration_ms": 10,
            "source_start_index": 0,
            "source_end_index": 0,
            "source_event_count": 1,
        },
        {
            "type": "delay",
            "timestamp_ms": 120,
            "end_timestamp_ms": 130,
            "duration_ms": 10,
            "source_start_index": 1,
            "source_end_index": 1,
            "source_event_count": 1,
        },
    ]

    shaped = shape_delays(
        actions,
        config=ShapingConfig(collapse_consecutive_delays=False),
    )

    assert shaped == actions
