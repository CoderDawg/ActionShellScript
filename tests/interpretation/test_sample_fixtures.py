from __future__ import annotations

from apps.cli.interpret_command import load_session
from core.interpretation.interpretation_config import InterpretationConfig
from core.interpretation.recording_interpreter import RecordingInterpreter


def test_sample_click_fixture_interprets_as_single_click() -> None:
    session = load_session("samples/click.json")

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == ["mouse_click"]
    assert interpreted.events[0]["clicks"] == 1


def test_sample_double_click_fixture_interprets_as_double_click() -> None:
    session = load_session("samples/double_click.json")

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == ["mouse_click"]
    assert interpreted.events[0]["clicks"] == 2


def test_sample_drag_fixture_interprets_as_drag() -> None:
    session = load_session("samples/drag.json")

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == ["mouse_drag"]


def test_sample_hotkey_fixture_interprets_as_hotkey() -> None:
    session = load_session("samples/hotkey_copy.json")

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == ["hotkey"]
    assert interpreted.events[0]["keys"] == ["ctrl", "c"]


def test_sample_borderline_fixture_stays_raw_by_default() -> None:
    session = load_session("samples/borderline_click_drag.json")

    interpreted = RecordingInterpreter().interpret(session)

    assert [event["type"] for event in interpreted.events] == [
        "mouse_down",
        "mouse_move",
        "mouse_up",
    ]


def test_sample_borderline_fixture_can_become_click_with_looser_click_threshold() -> None:
    session = load_session("samples/borderline_click_drag.json")

    interpreted = RecordingInterpreter(
        config=InterpretationConfig(click_max_move_distance_px=6)
    ).interpret(session)

    assert [event["type"] for event in interpreted.events] == ["mouse_click"]


def test_sample_borderline_fixture_can_become_drag_with_lower_drag_threshold() -> None:
    session = load_session("samples/borderline_click_drag.json")

    interpreted = RecordingInterpreter(
        config=InterpretationConfig(drag_min_distance_px=6)
    ).interpret(session)

    assert [event["type"] for event in interpreted.events] == ["mouse_drag"]
