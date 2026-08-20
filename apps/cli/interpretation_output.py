from __future__ import annotations

from core.interpretation.event_vocabulary import InterpretedEvent, event_type


def format_interpreted_event(event: InterpretedEvent, *, index: int) -> str:
    normalized_type = event_type(event)
    detail = _event_detail(event)
    timing = _timing_detail(event)
    provenance = _provenance_detail(event)
    parts = [f"[{index:02d}] {normalized_type}"]
    if detail:
        parts.append(detail)
    parts.append(timing)
    parts.append(provenance)
    return " | ".join(parts)


def _event_detail(event: InterpretedEvent) -> str:
    match event_type(event):
        case "mouse_click":
            clicks = int(event.get("clicks", 1))
            button = str(event.get("button", "left"))
            x = int(event.get("x", 0))
            y = int(event.get("y", 0))
            return f"{clicks}x {button} at ({x}, {y})"
        case "mouse_drag":
            button = str(event.get("button", "left"))
            start_x = int(event.get("start_x", event.get("x", 0)))
            start_y = int(event.get("start_y", event.get("y", 0)))
            end_x = int(event.get("end_x", event.get("x", 0)))
            end_y = int(event.get("end_y", event.get("y", 0)))
            distance = int(event.get("distance_px", 0))
            return (
                f"{button} from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                f" distance={distance}px"
            )
        case "key_hold":
            key = str(event.get("key", "unknown"))
            return f"key={key}"
        case "hotkey":
            keys = event.get("keys", [])
            if isinstance(keys, list) and keys:
                return " + ".join(str(key) for key in keys)
            modifiers = event.get("modifiers", [])
            trigger = str(event.get("trigger_key", "unknown"))
            if isinstance(modifiers, list) and modifiers:
                return " + ".join([*(str(key) for key in modifiers), trigger])
            return f"trigger={trigger}"
        case "mouse_move":
            x = int(event.get("x", 0))
            y = int(event.get("y", 0))
            return f"to ({x}, {y})"
        case "mouse_down" | "mouse_up":
            button = str(event.get("button", "left"))
            x = int(event.get("x", 0))
            y = int(event.get("y", 0))
            return f"{button} at ({x}, {y})"
        case "mouse_wheel":
            delta = int(event.get("delta", 0))
            x = event.get("x")
            y = event.get("y")
            if x is None or y is None:
                return f"delta={delta}"
            return f"delta={delta} at ({int(x)}, {int(y)})"
        case "key_down" | "key_up":
            key = str(event.get("key", "unknown"))
            return f"key={key}"
        case _:
            return ""


def _timing_detail(event: InterpretedEvent) -> str:
    start = int(event.get("timestamp_ms", 0))
    end = int(event.get("end_timestamp_ms", start))
    duration = int(event.get("duration_ms", max(0, end - start)))
    if start == end:
        return f"t={start}ms"
    return f"t={start}-{end}ms duration={duration}ms"


def _provenance_detail(event: InterpretedEvent) -> str:
    start = int(event.get("source_start_index", 0))
    end = int(event.get("source_end_index", start))
    count = int(event.get("source_event_count", max(1, end - start + 1)))
    return f"source={start}-{end} ({count} events)"
