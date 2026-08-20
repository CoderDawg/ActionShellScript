from __future__ import annotations

from core.shaping.click_shaper import shape_click_actions
from core.shaping.shaping_config import ShapingConfig


def test_click_shaper_collapses_simple_click_to_minimal_contract() -> None:
    actions = [
        {
            "type": "mouse_click",
            "button": "left",
            "clicks": 1,
            "x": 50,
            "y": 60,
            "press_x": 49,
            "press_y": 60,
            "release_x": 50,
            "release_y": 60,
            "max_move_distance_px": 1,
            "timestamp_ms": 100,
            "end_timestamp_ms": 130,
            "duration_ms": 30,
            "source_start_index": 2,
            "source_end_index": 3,
            "source_event_count": 2,
        }
    ]

    shaped = shape_click_actions(actions, config=ShapingConfig())

    assert shaped == [
        {
            "type": "mouse_click",
            "button": "left",
            "clicks": 1,
            "x": 50,
            "y": 60,
            "timestamp_ms": 100,
            "end_timestamp_ms": 130,
            "duration_ms": 30,
            "source_start_index": 2,
            "source_end_index": 3,
            "source_event_count": 2,
        }
    ]


def test_click_shaper_preserves_detailed_click_when_threshold_not_met() -> None:
    action = {
        "type": "mouse_click",
        "button": "left",
        "clicks": 1,
        "x": 50,
        "y": 60,
        "press_x": 45,
        "press_y": 60,
        "release_x": 50,
        "release_y": 60,
        "max_move_distance_px": 5,
        "timestamp_ms": 100,
        "end_timestamp_ms": 400,
        "duration_ms": 300,
        "source_start_index": 2,
        "source_end_index": 3,
        "source_event_count": 2,
    }

    shaped = shape_click_actions(
        [action],
        config=ShapingConfig(
            click_collapse_distance_px=3,
            click_collapse_max_duration_ms=250,
        ),
    )

    assert shaped == [action]


def test_click_shaper_can_be_disabled() -> None:
    action = {
        "type": "mouse_click",
        "button": "left",
        "clicks": 2,
        "x": 10,
        "y": 20,
        "press_x": 10,
        "press_y": 20,
        "release_x": 10,
        "release_y": 20,
        "max_move_distance_px": 0,
        "timestamp_ms": 100,
        "end_timestamp_ms": 120,
        "duration_ms": 20,
        "source_start_index": 0,
        "source_end_index": 3,
        "source_event_count": 4,
    }

    shaped = shape_click_actions(
        [action],
        config=ShapingConfig(collapse_simple_click_sequences=False),
    )

    assert shaped == [action]
