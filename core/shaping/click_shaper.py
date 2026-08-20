from __future__ import annotations

from .shaping_config import ShapingConfig
from .shaped_action_sequence import common_fields_from_action


ShapedAction = dict[str, object]


def shape_click_actions(
    actions: list[ShapedAction],
    *,
    config: ShapingConfig,
) -> list[ShapedAction]:
    if not config.collapse_simple_click_sequences:
        return [dict(action) for action in actions]

    shaped: list[ShapedAction] = []
    for action in actions:
        current = dict(action)
        action_type = str(current.get("type", "")).strip().lower()
        if action_type != "mouse_click":
            shaped.append(current)
            continue

        if not _is_simple_click(current, config=config):
            shaped.append(current)
            continue

        shaped.append(
            {
                "type": "mouse_click",
                "button": str(current.get("button", "left")).strip().lower() or "left",
                "clicks": int(current.get("clicks", 1)),
                "x": int(current.get("x", current.get("release_x", 0))),
                "y": int(current.get("y", current.get("release_y", 0))),
                **common_fields_from_action(current),
            }
        )

    return shaped


def _is_simple_click(
    action: ShapedAction,
    *,
    config: ShapingConfig,
) -> bool:
    max_move_distance_px = int(action.get("max_move_distance_px", 0))
    duration_ms = int(action.get("duration_ms", 0))
    return (
        max_move_distance_px <= config.click_collapse_distance_px
        and duration_ms <= config.click_collapse_max_duration_ms
    )
