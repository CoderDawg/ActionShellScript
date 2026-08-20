from __future__ import annotations

from core.interpretation.click_interpreter import collapse_mouse_button_sequences_to_clicks
from core.interpretation.interpretation_config import InterpretationConfig


def test_simple_click_is_collapsed() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 140},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(),
    )

    assert interpreted == [
        {
            "type": "mouse_click",
            "button": "left",
            "clicks": 1,
            "x": 10,
            "y": 20,
            "press_x": 10,
            "press_y": 20,
            "release_x": 10,
            "release_y": 20,
            "max_move_distance_px": 0,
            "timestamp_ms": 100,
            "end_timestamp_ms": 140,
            "duration_ms": 40,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        }
    ]


def test_click_rejected_by_movement_threshold() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 20, "y": 20, "timestamp_ms": 120},
        {"type": "mouse_up", "button": "left", "x": 20, "y": 20, "timestamp_ms": 140},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(click_max_move_distance_px=4),
    )

    assert [event["type"] for event in interpreted] == [
        "mouse_down",
        "mouse_move",
        "mouse_up",
    ]


def test_double_click_is_collapsed_into_single_event() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 130},
        {"type": "mouse_move", "x": 11, "y": 20, "timestamp_ms": 150},
        {"type": "mouse_down", "button": "left", "x": 11, "y": 20, "timestamp_ms": 180},
        {"type": "mouse_up", "button": "left", "x": 11, "y": 20, "timestamp_ms": 210},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(),
    )

    assert len(interpreted) == 1
    assert interpreted[0]["type"] == "mouse_click"
    assert interpreted[0]["clicks"] == 2
    assert interpreted[0]["source_event_count"] == 5
    assert interpreted[0]["source_end_index"] == 4


def test_mismatched_button_does_not_collapse() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_up", "button": "right", "x": 10, "y": 20, "timestamp_ms": 120},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(),
    )

    assert [event["type"] for event in interpreted] == ["mouse_down", "mouse_up"]


def test_interleaved_non_mouse_event_rejects_click_candidate() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_wheel", "delta": 1, "timestamp_ms": 110},
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 120},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(),
    )

    assert [event["type"] for event in interpreted] == [
        "mouse_down",
        "mouse_wheel",
        "mouse_up",
    ]


def test_unmatched_mouse_down_remains_raw() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(
        events,
        config=InterpretationConfig(),
    )

    assert [event["type"] for event in interpreted] == ["mouse_down"]


def test_double_click_exact_thresholds_are_allowed() -> None:
    config = InterpretationConfig(
        double_click_max_interval_ms=120,
        double_click_max_distance_px=4,
        double_click_max_pause_ms=40,
        double_click_max_inter_click_move_distance_px=4,
    )
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 130},
        {"type": "mouse_move", "x": 14, "y": 20, "timestamp_ms": 150},
        {"type": "mouse_down", "button": "left", "x": 14, "y": 20, "timestamp_ms": 170},
        {"type": "mouse_up", "button": "left", "x": 14, "y": 20, "timestamp_ms": 220},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(events, config=config)

    assert [event["type"] for event in interpreted] == ["mouse_click"]
    assert interpreted[0]["clicks"] == 2


def test_double_click_just_over_threshold_is_rejected() -> None:
    config = InterpretationConfig(
        double_click_max_interval_ms=120,
        double_click_max_distance_px=4,
        double_click_max_pause_ms=40,
        double_click_max_inter_click_move_distance_px=4,
    )
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 130},
        {"type": "mouse_move", "x": 15, "y": 20, "timestamp_ms": 150},
        {"type": "mouse_down", "button": "left", "x": 15, "y": 20, "timestamp_ms": 171},
        {"type": "mouse_up", "button": "left", "x": 15, "y": 20, "timestamp_ms": 221},
    ]

    interpreted = collapse_mouse_button_sequences_to_clicks(events, config=config)

    assert [event["type"] for event in interpreted] == [
        "mouse_click",
        "mouse_move",
        "mouse_click",
    ]
    assert interpreted[0]["clicks"] == 1
    assert interpreted[2]["clicks"] == 1
