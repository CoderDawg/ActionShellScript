from __future__ import annotations

from .shaping_config import ShapingConfig
from .shaped_action_sequence import combined_common_fields, common_fields_from_action


ShapedAction = dict[str, object]


def shape_mouse_actions(
    actions: list[ShapedAction],
    *,
    config: ShapingConfig,
) -> list[ShapedAction]:
    if not config.emit_mouse_moves:
        return [
            dict(action)
            for action in actions
            if str(action.get("type", "")).strip().lower() != "mouse_move"
        ]

    if not config.emit_only_click_positions:
        if not config.collapse_consecutive_mouse_moves:
            return [dict(action) for action in actions]
        return _collapse_consecutive_mouse_moves(actions)

    shaped: list[ShapedAction] = []
    for action in actions:
        current = dict(action)
        action_type = str(current.get("type", "")).strip().lower()

        if action_type == "mouse_move":
            continue

        shaped.append(current)

    return shaped


def _collapse_consecutive_mouse_moves(
    actions: list[ShapedAction],
) -> list[ShapedAction]:
    shaped: list[ShapedAction] = []
    pending_moves: list[ShapedAction] = []

    for action in actions:
        current = dict(action)
        action_type = str(current.get("type", "")).strip().lower()

        if action_type == "mouse_move":
            pending_moves.append(current)
            continue

        _flush_pending_moves(shaped, pending_moves)
        shaped.append(current)

    _flush_pending_moves(shaped, pending_moves)
    return shaped


def _flush_pending_moves(
    shaped: list[ShapedAction],
    pending_moves: list[ShapedAction],
) -> None:
    if not pending_moves:
        return

    if len(pending_moves) == 1:
        shaped.append(dict(pending_moves[0]))
        pending_moves.clear()
        return

    last_move = dict(pending_moves[-1])
    last_move.update(common_fields_from_action(last_move))
    last_move.update(combined_common_fields(pending_moves))
    shaped.append(last_move)
    pending_moves.clear()
