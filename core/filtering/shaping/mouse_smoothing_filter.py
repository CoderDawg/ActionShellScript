from __future__ import annotations

from core.shaping.shaped_action_sequence import ShapedActionSequence

from ..filter_profile import FilterProfile


class MouseSmoothingFilter:
    filter_id = "smooth_mouse"

    def apply(
        self,
        source: ShapedActionSequence,
        profile: FilterProfile,
    ) -> ShapedActionSequence:
        threshold_px = int(profile.settings.get("move_distance_threshold_px", 2))
        threshold_sq = threshold_px * threshold_px

        smoothed_actions: list[dict[str, object]] = []
        last_mouse_move_x: int | None = None
        last_mouse_move_y: int | None = None

        for action in source.actions:
            current = dict(action)
            action_type = str(current.get("type", "")).strip().lower()

            if action_type != "mouse_move":
                smoothed_actions.append(current)
                continue

            x = _extract_int(current, ("x", "end_x"))
            y = _extract_int(current, ("y", "end_y"))

            if last_mouse_move_x is not None and last_mouse_move_y is not None:
                dx = x - last_mouse_move_x
                dy = y - last_mouse_move_y
                if (dx * dx) + (dy * dy) <= threshold_sq:
                    continue

            smoothed_actions.append(current)
            last_mouse_move_x = x
            last_mouse_move_y = y

        return ShapedActionSequence(
            source_session_id=source.source_session_id,
            source_interpreted_event_count=source.source_interpreted_event_count,
            actions=smoothed_actions,
        )


def _extract_int(action: dict[str, object], keys: tuple[str, str]) -> int:
    for key in keys:
        if key in action and action[key] is not None:
            return int(action[key])
    return 0
