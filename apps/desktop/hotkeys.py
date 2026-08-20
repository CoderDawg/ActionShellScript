from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class HotkeyDefinition:
    action_id: str
    label: str
    default_shortcut: str = ""
    help_text: str = ""
    supports_alternates: bool = False


def split_hotkey_clauses(hotkey: str) -> tuple[str, ...]:
    return tuple(
        clause.strip()
        for clause in str(hotkey).split("|")
        if clause.strip()
    )


def primary_hotkey_clause(hotkey: str) -> str:
    clauses = split_hotkey_clauses(hotkey)
    if clauses:
        return clauses[0]
    return ""


def display_hotkey_clauses(hotkey: str) -> str:
    return " | ".join(split_hotkey_clauses(hotkey))


def normalized_hotkey_binding(hotkey: str) -> str:
    clauses = [clause.casefold() for clause in split_hotkey_clauses(hotkey)]
    return "|".join(sorted(clauses))


HOTKEY_DEFINITIONS: tuple[HotkeyDefinition, ...] = (
    HotkeyDefinition("new", "New", "Ctrl+N"),
    HotkeyDefinition("open", "Open...", "Ctrl+O"),
    HotkeyDefinition("save", "Save", "Ctrl+S"),
    HotkeyDefinition("save_as", "Save As...", "Ctrl+Shift+S"),
    HotkeyDefinition("undo", "Undo", "Ctrl+Z"),
    HotkeyDefinition("redo", "Redo", "Ctrl+Y"),
    HotkeyDefinition("cut", "Cut", "Ctrl+X"),
    HotkeyDefinition("copy", "Copy", "Ctrl+C"),
    HotkeyDefinition("paste", "Paste", "Ctrl+V"),
    HotkeyDefinition("delete", "Delete", "Delete"),
    HotkeyDefinition("select_all", "Select All", "Ctrl+A"),
    HotkeyDefinition("find", "Find...", "Ctrl+F", "Opens the find sidebar in the editor."),
    HotkeyDefinition("find_next", "Next", "F3", "Moves to the next search match."),
    HotkeyDefinition(
        "find_previous",
        "Previous",
        "Shift+F3",
        "Moves to the previous search match.",
    ),
    HotkeyDefinition(
        "replace",
        "Replace...",
        "Ctrl+H",
        "Opens the replace sidebar in the editor.",
    ),
    HotkeyDefinition("analyze", "Analyze", "F5", "Analyzes the current workspace."),
    HotkeyDefinition(
        "preview",
        "Refresh Preview",
        "F6",
        "Rebuilds the preview without starting playback.",
    ),
    HotkeyDefinition("debugger", "Run...", "", "Open Run"),
    HotkeyDefinition(
        "clear_breakpoints",
        "Clear Breakpoints",
        "Ctrl+Shift+F9",
        "Clears all breakpoints in the current editor.",
    ),
    HotkeyDefinition(
        "debug_step_into",
        "Step Into",
        "F11",
        "Steps into the next expression or function call.",
    ),
    HotkeyDefinition(
        "debug_step_over",
        "Step Over",
        "F10",
        "Steps over the next line or function call.",
    ),
    HotkeyDefinition(
        "debug_step_out",
        "Step Out",
        "Shift+F11",
        "Runs until the current function returns.",
    ),
    HotkeyDefinition(
        "debug_continue",
        "Continue",
        "Ctrl+F5",
        "Continues execution until the next breakpoint or pause.",
    ),
    HotkeyDefinition(
        "debug_pause",
        "Pause",
        "Ctrl+Alt+P",
        "Requests a pause at the next statement boundary.",
    ),
    HotkeyDefinition(
        "debug_restart",
        "Restart Debug",
        "Ctrl+Shift+F5",
        "Restarts the active debug session.",
    ),
    HotkeyDefinition(
        "debug_stop",
        "Stop",
        "Shift+F5",
        "Stops the active debug session.",
    ),
    HotkeyDefinition(
        "view_debugger_tab",
        "Run Sidebar",
        "",
        "Focuses the Run Sidebar.",
    ),
    HotkeyDefinition("play", "Play", "Ctrl+Enter", "Starts playback of the current script."),
    HotkeyDefinition("record", "Record", "Ctrl+Shift+R", "Starts recording new input."),
    HotkeyDefinition(
        "stop",
        "Stop",
        "Shift+Esc",
        "Stops recording or playback without sending Ctrl+C. Default shortcut: Shift+Esc. "
        "Use | to add alternate stop chords, such as Shift+Esc|Ctrl+C.",
        True,
    ),
    HotkeyDefinition(
        "toggle_breakpoint",
        "Toggle Breakpoint",
        "F9",
        "Toggles a breakpoint at the current position.",
    ),
    HotkeyDefinition("pixel_inspector", "Pixel Inspector...", "", "Opens the Pixel Inspector."),
    HotkeyDefinition("preferences", "Preferences...", "Ctrl+,", "Opens the preferences dialog."),
    HotkeyDefinition("documentation", "Documentation", "F1", "Opens the user guide."),
    HotkeyDefinition("about", "About", "", "Shows app version and build information."),
    HotkeyDefinition("exit", "Exit", "Ctrl+Q", "Closes the app."),
)


def default_hotkey_bindings() -> dict[str, str]:
    return {
        definition.action_id: definition.default_shortcut
        for definition in HOTKEY_DEFINITIONS
        if definition.default_shortcut
    }


def hotkey_conflict_groups(
    bindings: Mapping[str, str],
) -> list[tuple[str, list[HotkeyDefinition]]]:
    grouped: dict[str, tuple[str, list[HotkeyDefinition]]] = {}
    for definition in HOTKEY_DEFINITIONS:
        sequence_text = str(bindings.get(definition.action_id, "")).strip()
        if not sequence_text:
            continue
        normalized = normalized_hotkey_binding(sequence_text)
        if normalized not in grouped:
            grouped[normalized] = (sequence_text, [definition])
        else:
            grouped[normalized][1].append(definition)
    return [
        entry
        for entry in grouped.values()
        if len(entry[1]) > 1
    ]
