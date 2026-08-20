from __future__ import annotations

from .shaping_config import ShapingConfig
from .shaped_action_sequence import combined_common_fields, common_fields_from_action


ShapedAction = dict[str, object]


def shape_keyboard_actions(
    actions: list[ShapedAction],
    *,
    config: ShapingConfig,
) -> list[ShapedAction]:
    normalized = [_normalize_keyboard_action(action) for action in actions]
    if not config.collapse_text_input or config.keyboard_output_style != "text":
        return normalized

    shaped: list[ShapedAction] = []
    pending_text_actions: list[ShapedAction] = []

    for action in normalized:
        action_type = str(action.get("type", "")).strip().lower()

        if action_type == "key_hold" and _is_text_key_hold(action):
            pending_text_actions.append(action)
            continue

        if action_type == "hotkey" and _is_shift_printable_hotkey(action):
            pending_text_actions.append(_hotkey_as_text_action(action))
            continue

        _flush_text_actions(shaped, pending_text_actions)
        shaped.append(action)

    _flush_text_actions(shaped, pending_text_actions)
    return shaped


def _normalize_keyboard_action(action: ShapedAction) -> ShapedAction:
    current = dict(action)
    action_type = str(current.get("type", "")).strip().lower()

    if action_type in {"key_down", "key_up", "key_hold"}:
        return {
            "type": action_type,
            "key": str(current.get("key", "")).strip().lower(),
            **common_fields_from_action(current),
        }

    if action_type == "hotkey":
        modifiers = [str(key).strip().lower() for key in current.get("modifiers", [])]
        trigger_key = str(current.get("trigger_key", "")).strip().lower()
        keys = [str(key).strip().lower() for key in current.get("keys", [])]
        return {
            "type": "hotkey",
            "modifiers": modifiers,
            "trigger_key": trigger_key,
            "keys": keys or [*modifiers, trigger_key],
            **common_fields_from_action(current),
        }

    return current


def _is_text_key_hold(action: ShapedAction) -> bool:
    key = str(action.get("key", ""))
    return len(key) == 1 and key.isprintable()


def _is_shift_printable_hotkey(action: ShapedAction) -> bool:
    modifiers = [
        str(key).strip().lower()
        for key in action.get("modifiers", [])
        if str(key).strip()
    ]
    trigger_key = str(action.get("trigger_key", "")).strip()
    if modifiers != ["shift"]:
        return False
    return len(trigger_key) == 1 and trigger_key.isalpha()


def _hotkey_as_text_action(action: ShapedAction) -> ShapedAction:
    trigger_key = str(action.get("trigger_key", "")).strip()
    return {
        "type": "text",
        "text": trigger_key.upper(),
        **common_fields_from_action(action),
    }


def _flush_text_actions(
    shaped: list[ShapedAction],
    pending_text_actions: list[ShapedAction],
) -> None:
    if not pending_text_actions:
        return

    if len(pending_text_actions) == 1:
        only_action = pending_text_actions[0]
        shaped.append(
            {
                "type": "text",
                "text": str(only_action.get("text", only_action.get("key", ""))),
                **common_fields_from_action(only_action),
            }
        )
        pending_text_actions.clear()
        return

    shaped.append(
        {
            "type": "text",
            "text": "".join(
                str(action.get("text", action.get("key", "")))
                for action in pending_text_actions
            ),
            **combined_common_fields(pending_text_actions),
        }
    )
    pending_text_actions.clear()
