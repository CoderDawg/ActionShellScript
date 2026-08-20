from __future__ import annotations

from copy import deepcopy

from core.interpretation.interpreted_recording import InterpretedRecording
from core.shaping.shaping_config import ShapingConfig
from core.shaping.shaping_pipeline import ShapingPipeline


def test_shaping_pipeline_does_not_mutate_interpreted_recording() -> None:
    interpreted = InterpretedRecording(
        source_session_id="session-1",
        source_event_count=9,
        events=[
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
                "type": "key_hold",
                "key": "h",
                "timestamp_ms": 120,
                "end_timestamp_ms": 130,
                "duration_ms": 10,
                "source_start_index": 2,
                "source_end_index": 3,
                "source_event_count": 2,
            },
            {
                "type": "key_hold",
                "key": "i",
                "timestamp_ms": 140,
                "end_timestamp_ms": 150,
                "duration_ms": 10,
                "source_start_index": 4,
                "source_end_index": 5,
                "source_event_count": 2,
            },
            {
                "type": "delay",
                "timestamp_ms": 160,
                "end_timestamp_ms": 165,
                "duration_ms": 5,
                "source_start_index": 6,
                "source_end_index": 6,
                "source_event_count": 1,
            },
            {
                "type": "delay",
                "timestamp_ms": 170,
                "end_timestamp_ms": 175,
                "duration_ms": 5,
                "source_start_index": 7,
                "source_end_index": 7,
                "source_event_count": 1,
            },
            {
                "type": "mouse_click",
                "button": "left",
                "clicks": 1,
                "x": 20,
                "y": 20,
                "press_x": 20,
                "press_y": 20,
                "release_x": 20,
                "release_y": 20,
                "max_move_distance_px": 0,
                "timestamp_ms": 180,
                "end_timestamp_ms": 200,
                "duration_ms": 20,
                "source_start_index": 8,
                "source_end_index": 9,
                "source_event_count": 2,
            },
        ],
    )
    original_events = deepcopy(interpreted.events)

    shaped = ShapingPipeline(
        config=ShapingConfig(keyboard_output_style="text"),
    ).shape(interpreted)

    assert interpreted.events == original_events
    assert shaped.source_session_id == "session-1"
    assert shaped.source_interpreted_event_count == 7
    assert [action["type"] for action in shaped.actions] == [
        "mouse_move",
        "text",
        "delay",
        "mouse_click",
    ]
    assert shaped.actions[0]["source_event_count"] == 2
    assert shaped.actions[1]["text"] == "hi"
    assert shaped.actions[1]["source_event_count"] == 4
    assert shaped.actions[2]["duration_ms"] == 10
    assert shaped.actions[2]["source_event_count"] == 2
    assert "press_x" not in shaped.actions[3]


def test_shaping_pipeline_flags_change_output_intentionally() -> None:
    interpreted = InterpretedRecording(
        source_session_id="session-2",
        source_event_count=4,
        events=[
            {
                "type": "key_hold",
                "key": "a",
                "timestamp_ms": 100,
                "end_timestamp_ms": 110,
                "duration_ms": 10,
                "source_start_index": 0,
                "source_end_index": 1,
                "source_event_count": 2,
            },
            {
                "type": "key_hold",
                "key": "b",
                "timestamp_ms": 120,
                "end_timestamp_ms": 130,
                "duration_ms": 10,
                "source_start_index": 2,
                "source_end_index": 3,
                "source_event_count": 2,
            },
        ],
    )

    structured = ShapingPipeline(
        config=ShapingConfig(keyboard_output_style="structured"),
    ).shape(interpreted)
    text = ShapingPipeline(
        config=ShapingConfig(keyboard_output_style="text"),
    ).shape(interpreted)

    assert [action["type"] for action in structured.actions] == ["key_hold", "key_hold"]
    assert text.actions == [
        {
            "type": "text",
            "text": "ab",
            "timestamp_ms": 100,
            "end_timestamp_ms": 130,
            "duration_ms": 30,
            "source_start_index": 0,
            "source_end_index": 3,
            "source_event_count": 4,
        }
    ]
