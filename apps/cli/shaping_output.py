from __future__ import annotations

from core.interpretation.event_vocabulary import event_type
from core.shaping.shaped_action_sequence import ShapedAction


def format_shaped_action(action: ShapedAction, *, index: int) -> str:
    normalized_type = event_type(action)
    detail = _action_detail(action)
    timing = _timing_detail(action)
    provenance = _provenance_detail(action)
    parts = [f"[{index:02d}] {normalized_type}"]
    if detail:
        parts.append(detail)
    parts.append(timing)
    parts.append(provenance)
    return " | ".join(parts)


def _action_detail(action: ShapedAction) -> str:
    match event_type(action):
        case "mouse_click":
            return (
                f"{int(action.get('clicks', 1))}x "
                f"{str(action.get('button', 'left'))} "
                f"at ({int(action.get('x', 0))}, {int(action.get('y', 0))})"
            )
        case "mouse_drag":
            return (
                f"{str(action.get('button', 'left'))} "
                f"from ({int(action.get('start_x', 0))}, {int(action.get('start_y', 0))}) "
                f"to ({int(action.get('end_x', 0))}, {int(action.get('end_y', 0))})"
            )
        case "mouse_move":
            return f"to ({int(action.get('x', 0))}, {int(action.get('y', 0))})"
        case "hotkey":
            return " + ".join(str(key) for key in action.get("keys", []))
        case "key_down" | "key_up" | "key_hold":
            return f"key={str(action.get('key', ''))}"
        case "text":
            return f"text={str(action.get('text', ''))!r}"
        case "delay":
            return f"{int(action.get('duration_ms', 0))}ms"
        case _:
            return ""


def _timing_detail(action: ShapedAction) -> str:
    start = int(action.get("timestamp_ms", 0))
    end = int(action.get("end_timestamp_ms", start))
    duration = int(action.get("duration_ms", max(0, end - start)))
    if start == end:
        return f"t={start}ms"
    return f"t={start}-{end}ms duration={duration}ms"


def _provenance_detail(action: ShapedAction) -> str:
    start = int(action.get("source_start_index", 0))
    end = int(action.get("source_end_index", start))
    count = int(action.get("source_event_count", max(1, end - start + 1)))
    return f"source={start}-{end} ({count} events)"
