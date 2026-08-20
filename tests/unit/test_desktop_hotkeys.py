from __future__ import annotations

from apps.desktop.hotkeys import (
    HOTKEY_DEFINITIONS,
    default_hotkey_bindings,
    hotkey_conflict_groups,
)
from apps.desktop.settings import DesktopHotkeySettings


def test_desktop_hotkeys_include_script_actions_with_expected_defaults() -> None:
    bindings = default_hotkey_bindings()

    assert "play" in bindings
    assert "record" in bindings
    assert "stop" in bindings
    assert "about" not in bindings
    assert bindings["play"] == "Ctrl+Enter"
    assert bindings["record"] == "Ctrl+Shift+R"
    assert bindings["stop"] == "Shift+Esc"
    assert bindings["clear_breakpoints"] == "Ctrl+Shift+F9"
    assert bindings["find"] == "Ctrl+F"
    assert bindings["find_next"] == "F3"
    assert bindings["find_previous"] == "Shift+F3"
    assert bindings["replace"] == "Ctrl+H"

    labels_by_id = {definition.action_id: definition.label for definition in HOTKEY_DEFINITIONS}
    assert labels_by_id["play"] == "Play"
    assert labels_by_id["record"] == "Record"
    assert labels_by_id["stop"] == "Stop"
    assert labels_by_id["clear_breakpoints"] == "Clear Breakpoints"
    assert labels_by_id["find"] == "Find..."
    assert labels_by_id["find_next"] == "Next"
    assert labels_by_id["find_previous"] == "Previous"
    assert labels_by_id["replace"] == "Replace..."
    assert labels_by_id["pixel_inspector"] == "Pixel Inspector..."
    assert labels_by_id["about"] == "About"
    assert "pixel_inspector" not in bindings


def test_desktop_hotkeys_include_run_action_definition() -> None:
    debug_definition = next(
        definition
        for definition in HOTKEY_DEFINITIONS
        if definition.action_id == "debugger"
    )

    assert debug_definition.label == "Run..."
    assert debug_definition.default_shortcut == ""
    assert debug_definition.help_text == "Open Run"
    assert "debugger" not in default_hotkey_bindings()


def test_desktop_hotkeys_include_debugger_step_control_definitions() -> None:
    bindings = default_hotkey_bindings()
    settings = DesktopHotkeySettings()
    definitions_by_id = {definition.action_id: definition for definition in HOTKEY_DEFINITIONS}

    assert bindings["debug_step_into"] == "F11"
    assert bindings["debug_step_over"] == "F10"
    assert bindings["debug_step_out"] == "Shift+F11"
    assert bindings["debug_continue"] == "Ctrl+F5"
    assert bindings["debug_pause"] == "Ctrl+Alt+P"
    assert bindings["debug_restart"] == "Ctrl+Shift+F5"
    assert bindings["debug_stop"] == "Shift+F5"
    assert settings.bindings["debug_step_into"] == "F11"
    assert settings.bindings["debug_step_over"] == "F10"
    assert settings.bindings["debug_step_out"] == "Shift+F11"
    assert settings.bindings["debug_continue"] == "Ctrl+F5"
    assert settings.bindings["debug_pause"] == "Ctrl+Alt+P"
    assert settings.bindings["debug_restart"] == "Ctrl+Shift+F5"
    assert settings.bindings["debug_stop"] == "Shift+F5"
    assert definitions_by_id["debug_step_into"].label == "Step Into"
    assert definitions_by_id["debug_step_over"].label == "Step Over"
    assert definitions_by_id["debug_step_out"].label == "Step Out"
    assert definitions_by_id["debug_continue"].label == "Continue"
    assert definitions_by_id["debug_pause"].label == "Pause"
    assert definitions_by_id["debug_restart"].label == "Restart Debug"
    assert definitions_by_id["debug_stop"].label == "Stop"
    assert definitions_by_id["debug_step_into"].help_text == (
        "Steps into the next expression or function call."
    )
    assert definitions_by_id["debug_step_over"].help_text == (
        "Steps over the next line or function call."
    )
    assert definitions_by_id["debug_step_out"].help_text == (
        "Runs until the current function returns."
    )
    assert definitions_by_id["debug_continue"].help_text == (
        "Continues execution until the next breakpoint or pause."
    )
    assert definitions_by_id["debug_pause"].help_text == (
        "Requests a pause at the next statement boundary."
    )
    assert definitions_by_id["debug_restart"].help_text == "Restarts the active debug session."
    assert definitions_by_id["debug_stop"].help_text == "Stops the active debug session."
    assert definitions_by_id["stop"].help_text == (
        "Stops recording or playback without sending Ctrl+C. Default shortcut: Shift+Esc. "
        "Use | to add alternate stop chords, such as Shift+Esc|Ctrl+C."
    )
    assert definitions_by_id["stop"].supports_alternates is True


def test_desktop_hotkeys_include_search_action_definitions() -> None:
    definitions_by_id = {definition.action_id: definition for definition in HOTKEY_DEFINITIONS}

    assert definitions_by_id["find"].default_shortcut == "Ctrl+F"
    assert definitions_by_id["find_next"].default_shortcut == "F3"
    assert definitions_by_id["find_previous"].default_shortcut == "Shift+F3"
    assert definitions_by_id["replace"].default_shortcut == "Ctrl+H"
    assert definitions_by_id["find"].help_text == "Opens the find sidebar in the editor."
    assert definitions_by_id["find_next"].help_text == "Moves to the next search match."
    assert definitions_by_id["find_previous"].help_text == "Moves to the previous search match."
    assert definitions_by_id["replace"].help_text == "Opens the replace sidebar in the editor."


def test_desktop_hotkeys_include_view_debugger_tab_definition() -> None:
    debug_tab_definition = next(
        definition
        for definition in HOTKEY_DEFINITIONS
        if definition.action_id == "view_debugger_tab"
    )

    assert debug_tab_definition.label == "Run Sidebar"
    assert debug_tab_definition.default_shortcut == ""
    assert debug_tab_definition.help_text == "Focuses the Run Sidebar."
    assert "view_debugger_tab" not in default_hotkey_bindings()


def test_desktop_hotkeys_include_clear_breakpoints_action_definition() -> None:
    clear_definition = next(
        definition
        for definition in HOTKEY_DEFINITIONS
        if definition.action_id == "clear_breakpoints"
    )

    assert clear_definition.label == "Clear Breakpoints"
    assert clear_definition.default_shortcut == "Ctrl+Shift+F9"
    assert clear_definition.help_text == "Clears all breakpoints in the current editor."


def test_desktop_hotkeys_detect_conflict_groups() -> None:
    conflict_groups = hotkey_conflict_groups(
        {
            "new": "Ctrl+N",
            "open": "Ctrl+N",
        }
    )

    assert len(conflict_groups) == 1
    sequence_text, definitions = conflict_groups[0]
    assert sequence_text == "Ctrl+N"
    assert [definition.action_id for definition in definitions] == ["new", "open"]


def test_desktop_hotkeys_detect_conflict_groups_for_alternate_shortcuts() -> None:
    conflict_groups = hotkey_conflict_groups(
        {
            "record": "Shift+Esc|Ctrl+C",
            "stop": "Ctrl+C | Shift+Esc",
        }
    )

    assert len(conflict_groups) == 1
    sequence_text, definitions = conflict_groups[0]
    assert sequence_text == "Shift+Esc|Ctrl+C"
    assert {definition.action_id for definition in definitions} == {"record", "stop"}
