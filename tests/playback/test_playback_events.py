from __future__ import annotations

from core.playback.playback_events import (
    HotkeyPlaybackEvent,
    MouseClickPlaybackEvent,
    MouseMovePlaybackEvent,
    playback_event_to_dict,
)


def test_playback_events_are_immutable_objects_with_plain_dict_serialization() -> None:
    event = MouseClickPlaybackEvent(button="left", x=10, y=20, clicks=2, speed=7)

    assert playback_event_to_dict(event) == {
        "type": "mouse_click",
        "button": "left",
        "x": 10,
        "y": 20,
        "clicks": 2,
        "speed": 7,
    }


def test_hotkey_event_keeps_its_keys_as_an_immutable_tuple() -> None:
    event = HotkeyPlaybackEvent(keys=("ctrl", "shift", "x"))

    assert event.keys == ("ctrl", "shift", "x")
    assert playback_event_to_dict(event)["keys"] == ["ctrl", "shift", "x"]


def test_preview_events_can_be_serialized_for_cli_output() -> None:
    event = MouseMovePlaybackEvent(x=4, y=8, speed=11)

    assert playback_event_to_dict(event) == {"type": "mouse_move", "x": 4, "y": 8, "speed": 11}
