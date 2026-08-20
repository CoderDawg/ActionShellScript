from __future__ import annotations

from core.scripting.generation.action_to_script_renderer import render_actions_to_lines
from core.scripting.generation.script_generation_config import ScriptGenerationConfig


def test_action_renderer_covers_phase_4_shaped_action_vocabulary() -> None:
    actions = [
        {"type": "delay", "duration_ms": 25},
        {"type": "hotkey", "keys": ["ctrl", "c"]},
        {"type": "key_down", "key": "shift"},
        {"type": "key_hold", "key": "a", "duration_ms": 80},
        {"type": "key_up", "key": "shift"},
        {"type": "mouse_click", "button": "left", "x": 10, "y": 20, "clicks": 2},
        {"type": "mouse_down", "button": "right", "x": 30, "y": 40},
        {
            "type": "mouse_drag",
            "button": "left",
            "start_x": 10,
            "start_y": 20,
            "end_x": 50,
            "end_y": 60,
            "duration_ms": 120,
        },
        {"type": "mouse_move", "x": 70, "y": 80},
        {"type": "mouse_up", "button": "right", "x": 30, "y": 40},
        {"type": "mouse_wheel", "delta": -1},
        {"type": "text", "text": 'say "hi" \\ there'},
    ]

    lines = render_actions_to_lines(actions, config=ScriptGenerationConfig())

    assert lines == [
        "Sleep(25)",
        'Hotkey("ctrl", "c")',
        'KeyDown("shift")',
        'KeyDown("a")',
        "Sleep(80)",
        'KeyUp("a")',
        'KeyUp("shift")',
        'MouseClick("left", 10, 20, 2)',
        'MouseDown("right", 30, 40)',
        "MouseMove(10, 20)",
        'MouseDown("left", 10, 20)',
        "Sleep(120)",
        "MouseMove(50, 60)",
        'MouseUp("left", 50, 60)',
        "MouseMove(70, 80)",
        'MouseUp("right", 30, 40)',
        "MouseWheel(-1)",
        'SendText("say ""hi"" \\\\ there")',
    ]


def test_action_renderer_can_drop_standalone_delay_actions() -> None:
    lines = render_actions_to_lines(
        [
            {"type": "delay", "duration_ms": 25},
            {"type": "mouse_move", "x": 1, "y": 2},
        ],
        config=ScriptGenerationConfig(emit_delays=False),
    )

    assert lines == ["MouseMove(1, 2)"]


def test_action_renderer_can_emit_intentional_unsupported_comments() -> None:
    lines = render_actions_to_lines(
        [
            {"type": "macro_loop"},
            {"type": "mouse_click", "button": "left", "x": 1, "y": 2},
        ],
        config=ScriptGenerationConfig(emit_metadata_comments=True),
    )

    assert lines == [
        "# Unknown action: macro_loop",
        'MouseClick("left", 1, 2, 1)',
    ]


def test_action_renderer_does_not_silently_drop_unsupported_shaped_actions() -> None:
    lines = render_actions_to_lines(
        [
            {"type": "key_hold"},
            {"type": "hotkey", "keys": []},
            {"type": "mouse_drag", "button": "left", "start_x": 10, "start_y": 20},
        ],
        config=ScriptGenerationConfig(),
    )

    assert lines == [
        "# Unsupported shaped action: key_hold",
        "# Unsupported shaped action: hotkey",
        "# Unsupported shaped action: mouse_drag",
    ]


def test_action_renderer_can_build_hotkey_from_trigger_and_modifiers() -> None:
    lines = render_actions_to_lines(
        [{"type": "hotkey", "modifiers": ["ctrl", "shift"], "trigger_key": "x"}],
        config=ScriptGenerationConfig(),
    )

    assert lines == ['Hotkey("ctrl", "shift", "x")']
