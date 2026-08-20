from __future__ import annotations

from .script_generation_config import ScriptGenerationConfig
from core.shaping.shaped_action_sequence import SHAPED_ACTION_TYPES


ShapedAction = dict[str, object]


def render_actions_to_lines(
    actions: list[ShapedAction],
    *,
    config: ScriptGenerationConfig,
) -> list[str]:
    lines: list[str] = []

    for action in actions:
        action_type = str(action.get("type", "")).strip().lower()
        rendered = _render_action(action, action_type=action_type, config=config)
        if rendered is not None:
            lines.extend(rendered)
            continue

        rendered_type = action_type or "<missing>"
        if action_type in SHAPED_ACTION_TYPES:
            lines.append(f"# Unsupported shaped action: {rendered_type}")
            continue

        if config.emit_metadata_comments:
            lines.append(f"# Unknown action: {rendered_type}")

    return lines


def _render_action(
    action: ShapedAction,
    *,
    action_type: str,
    config: ScriptGenerationConfig,
) -> list[str] | None:
    if action_type == "mouse_move":
        x = action.get("x", 0)
        y = action.get("y", 0)
        return [f"MouseMove({x}, {y})"]

    if action_type == "mouse_down":
        button = _quote_string(str(action.get("button", "left")))
        x = action.get("x", 0)
        y = action.get("y", 0)
        return [f"MouseDown({button}, {x}, {y})"]

    if action_type == "mouse_up":
        button = _quote_string(str(action.get("button", "left")))
        x = action.get("x", 0)
        y = action.get("y", 0)
        return [f"MouseUp({button}, {x}, {y})"]

    if action_type == "mouse_click":
        button = _quote_string(str(action.get("button", "left")))
        x = action.get("x", 0)
        y = action.get("y", 0)
        clicks = action.get("clicks", 1)
        return [f"MouseClick({button}, {x}, {y}, {clicks})"]

    if action_type == "mouse_drag":
        button_name = _normalized_string_field(action, "button")
        start_x = _int_field(action, "start_x")
        start_y = _int_field(action, "start_y")
        end_x = _int_field(action, "end_x")
        end_y = _int_field(action, "end_y")
        if not button_name or None in {start_x, start_y, end_x, end_y}:
            return None
        button = _quote_string(button_name)
        duration_ms = max(0, _int_field(action, "duration_ms", default=0) or 0)
        lines = [
            f"MouseMove({start_x}, {start_y})",
            f"MouseDown({button}, {start_x}, {start_y})",
        ]
        if duration_ms > 0:
            lines.append(f"Sleep({duration_ms})")
        lines.extend(
            [
                f"MouseMove({end_x}, {end_y})",
                f"MouseUp({button}, {end_x}, {end_y})",
            ]
        )
        return lines

    if action_type == "mouse_wheel":
        delta = action.get("delta", 0)
        return [f"MouseWheel({delta})"]

    if action_type == "key_down":
        key = _quote_string(str(action.get("key", "")))
        return [f"KeyDown({key})"]

    if action_type == "key_up":
        key = _quote_string(str(action.get("key", "")))
        return [f"KeyUp({key})"]

    if action_type == "key_hold":
        key_name = _normalized_string_field(action, "key")
        if not key_name:
            return None
        key = _quote_string(key_name)
        duration_ms = max(0, _int_field(action, "duration_ms", default=0) or 0)
        lines = [f"KeyDown({key})"]
        if duration_ms > 0:
            lines.append(f"Sleep({duration_ms})")
        lines.append(f"KeyUp({key})")
        return lines

    if action_type == "hotkey":
        keys = _normalized_string_list(action.get("keys"))
        if not keys:
            trigger_key = _normalized_string_field(action, "trigger_key")
            modifiers = _normalized_string_list(action.get("modifiers"))
            keys = [*modifiers, trigger_key] if trigger_key else modifiers
        if not keys:
            return None
        rendered_args = ", ".join(_quote_string(key) for key in keys)
        return [f"Hotkey({rendered_args})"]

    if action_type == "delay":
        if config.emit_delays:
            duration_ms = max(0, int(action.get("duration_ms", 0)))
            return [f"Sleep({duration_ms})"]
        return []

    if action_type == "text":
        text = _quote_string(str(action.get("text", "")))
        return [f"SendText({text})"]

    return None


def _quote_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '""')
    return f'"{escaped}"'


def _normalized_string_field(action: ShapedAction, name: str) -> str:
    value = action.get(name)
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalized for item in value if (normalized := str(item).strip().lower())]


def _int_field(action: ShapedAction, name: str, *, default: int | None = None) -> int | None:
    value = action.get(name, default)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
