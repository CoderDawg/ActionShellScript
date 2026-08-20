from __future__ import annotations

from core.shaping.mouse_shaper import shape_mouse_actions
from core.shaping.shaping_config import ShapingConfig


def test_mouse_shaper_can_drop_mouse_moves() -> None:
    actions = [
        {"type": "mouse_move", "x": 10, "y": 10},
        {"type": "mouse_click", "button": "left", "x": 10, "y": 10},
    ]

    shaped = shape_mouse_actions(
        actions,
        config=ShapingConfig(emit_mouse_moves=False),
    )

    assert shaped == [{"type": "mouse_click", "button": "left", "x": 10, "y": 10}]


def test_mouse_shaper_only_click_positions_keeps_click_and_drag_actions() -> None:
    actions = [
        {"type": "mouse_move", "x": 10, "y": 10},
        {"type": "mouse_click", "button": "left", "x": 10, "y": 10},
        {
            "type": "mouse_drag",
            "button": "left",
            "start_x": 10,
            "start_y": 10,
            "end_x": 20,
            "end_y": 20,
        },
    ]

    shaped = shape_mouse_actions(
        actions,
        config=ShapingConfig(emit_only_click_positions=True),
    )

    assert [action["type"] for action in shaped] == ["mouse_click", "mouse_drag"]


def test_mouse_shaper_collapses_consecutive_moves_and_preserves_span_metadata() -> None:
    actions = [
        {
            "type": "mouse_move",
            "x": 10,
            "y": 10,
            "timestamp_ms": 100,
            "end_timestamp_ms": 100,
            "duration_ms": 0,
            "source_start_index": 0,
            "source_end_index": 0,
            "source_event_count": 1,
        },
        {
            "type": "mouse_move",
            "x": 20,
            "y": 20,
            "timestamp_ms": 110,
            "end_timestamp_ms": 110,
            "duration_ms": 0,
            "source_start_index": 1,
            "source_end_index": 1,
            "source_event_count": 1,
        },
        {
            "type": "mouse_click",
            "button": "left",
            "x": 20,
            "y": 20,
            "timestamp_ms": 120,
            "end_timestamp_ms": 130,
            "duration_ms": 10,
            "source_start_index": 2,
            "source_end_index": 3,
            "source_event_count": 2,
        },
    ]

    shaped = shape_mouse_actions(actions, config=ShapingConfig())

    assert shaped == [
        {
            "type": "mouse_move",
            "x": 20,
            "y": 20,
            "timestamp_ms": 100,
            "end_timestamp_ms": 110,
            "duration_ms": 10,
            "source_start_index": 0,
            "source_end_index": 1,
            "source_event_count": 2,
        },
        {
            "type": "mouse_click",
            "button": "left",
            "x": 20,
            "y": 20,
            "timestamp_ms": 120,
            "end_timestamp_ms": 130,
            "duration_ms": 10,
            "source_start_index": 2,
            "source_end_index": 3,
            "source_event_count": 2,
        },
    ]


def test_mouse_shaper_can_keep_all_moves_when_collapse_is_disabled() -> None:
    actions = [
        {"type": "mouse_move", "x": 10, "y": 10},
        {"type": "mouse_move", "x": 20, "y": 20},
    ]

    shaped = shape_mouse_actions(
        actions,
        config=ShapingConfig(collapse_consecutive_mouse_moves=False),
    )

    assert shaped == actions
