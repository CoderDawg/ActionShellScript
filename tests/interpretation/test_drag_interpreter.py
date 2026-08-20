from __future__ import annotations

from core.interpretation.click_interpreter import collapse_mouse_button_sequences_to_clicks
from core.interpretation.drag_interpreter import annotate_drag_sequences
from core.interpretation.interpretation_config import InterpretationConfig


def test_drag_is_recognized_above_threshold() -> None:
    raw_events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 25, "y": 20, "timestamp_ms": 130},
        {"type": "mouse_up", "button": "left", "x": 25, "y": 20, "timestamp_ms": 170},
    ]

    click_pass = collapse_mouse_button_sequences_to_clicks(
        raw_events,
        config=InterpretationConfig(click_max_move_distance_px=4),
    )
    interpreted = annotate_drag_sequences(
        click_pass,
        config=InterpretationConfig(drag_min_distance_px=8, drag_min_duration_ms=20),
    )

    assert interpreted == [
        {
            "type": "mouse_drag",
            "button": "left",
            "x": 25,
            "y": 20,
            "start_x": 10,
            "start_y": 20,
            "end_x": 25,
            "end_y": 20,
            "distance_px": 15,
            "timestamp_ms": 100,
            "end_timestamp_ms": 170,
            "duration_ms": 70,
            "source_start_index": 0,
            "source_end_index": 2,
            "source_event_count": 3,
        }
    ]


def test_small_mouse_motion_stays_non_drag() -> None:
    raw_events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 14, "y": 20, "timestamp_ms": 120},
        {"type": "mouse_up", "button": "left", "x": 14, "y": 20, "timestamp_ms": 140},
    ]

    click_pass = collapse_mouse_button_sequences_to_clicks(
        raw_events,
        config=InterpretationConfig(click_max_move_distance_px=2),
    )
    interpreted = annotate_drag_sequences(
        click_pass,
        config=InterpretationConfig(drag_min_distance_px=8),
    )

    assert [event["type"] for event in interpreted] == [
        "mouse_down",
        "mouse_move",
        "mouse_up",
    ]


def test_interleaved_non_mouse_event_rejects_drag_candidate() -> None:
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 25, "y": 20, "timestamp_ms": 120},
        {"type": "key_down", "key": "a", "timestamp_ms": 130},
        {"type": "mouse_up", "button": "left", "x": 25, "y": 20, "timestamp_ms": 150},
    ]

    interpreted = annotate_drag_sequences(events, config=InterpretationConfig())

    assert [event["type"] for event in interpreted] == [
        "mouse_down",
        "mouse_move",
        "key_down",
        "mouse_up",
    ]


def test_unmatched_mouse_up_remains_raw() -> None:
    events = [
        {"type": "mouse_up", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
    ]

    interpreted = annotate_drag_sequences(events, config=InterpretationConfig())

    assert [event["type"] for event in interpreted] == ["mouse_up"]


def test_drag_exact_distance_and_duration_thresholds_are_allowed() -> None:
    config = InterpretationConfig(drag_min_distance_px=8, drag_min_duration_ms=30)
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 18, "y": 20, "timestamp_ms": 115},
        {"type": "mouse_up", "button": "left", "x": 18, "y": 20, "timestamp_ms": 130},
    ]

    interpreted = annotate_drag_sequences(events, config=config)

    assert [event["type"] for event in interpreted] == ["mouse_drag"]


def test_drag_below_distance_or_duration_threshold_is_rejected() -> None:
    config = InterpretationConfig(drag_min_distance_px=8, drag_min_duration_ms=30)
    events = [
        {"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 100},
        {"type": "mouse_move", "x": 17, "y": 20, "timestamp_ms": 115},
        {"type": "mouse_up", "button": "left", "x": 17, "y": 20, "timestamp_ms": 129},
    ]

    interpreted = annotate_drag_sequences(events, config=config)

    assert [event["type"] for event in interpreted] == [
        "mouse_down",
        "mouse_move",
        "mouse_up",
    ]
