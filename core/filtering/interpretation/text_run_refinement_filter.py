from __future__ import annotations

from core.shaping.shaped_action_sequence import (
    combined_common_fields,
    common_fields_from_action,
)
from core.interpretation.interpreted_recording import InterpretedRecording

from ..filter_profile import FilterProfile


class TextRunRefinementFilter:
    filter_id = "text_run_refinement"

    def apply(
        self,
        source: InterpretedRecording,
        profile: FilterProfile,
    ) -> InterpretedRecording:
        del profile

        refined_events: list[dict[str, object]] = []
        pending_text_sources: list[dict[str, object]] = []

        for event in source.events:
            current = dict(event)
            event_type = str(current.get("type", "")).strip().lower()

            if event_type == "key_hold" and _is_printable_text_key(current):
                pending_text_sources.append(current)
                continue

            if event_type == "hotkey" and _is_shift_printable_hotkey(current):
                pending_text_sources.append(
                    {
                        **current,
                        "type": "text",
                        "text": str(current.get("trigger_key", "")).strip().upper(),
                    }
                )
                continue

            _flush_pending_text_runs(refined_events, pending_text_sources)
            refined_events.append(current)

        _flush_pending_text_runs(refined_events, pending_text_sources)

        return InterpretedRecording(
            source_session_id=source.source_session_id,
            source_event_count=source.source_event_count,
            events=refined_events,
        )


def _is_printable_text_key(event: dict[str, object]) -> bool:
    key = str(event.get("key", "")).strip()
    return len(key) == 1 and key.isprintable()


def _is_shift_printable_hotkey(event: dict[str, object]) -> bool:
    modifiers = [
        str(key).strip().lower()
        for key in event.get("modifiers", [])
        if str(key).strip()
    ]
    trigger_key = str(event.get("trigger_key", "")).strip()
    return modifiers == ["shift"] and len(trigger_key) == 1 and trigger_key.isalpha()


def _flush_pending_text_runs(
    refined_events: list[dict[str, object]],
    pending_text_sources: list[dict[str, object]],
) -> None:
    if not pending_text_sources:
        return

    if len(pending_text_sources) == 1:
        only_event = pending_text_sources[0]
        refined_events.append(
            {
                "type": "text",
                "text": str(
                    only_event.get("text", only_event.get("key", ""))
                ),
                **common_fields_from_action(only_event),
            }
        )
        pending_text_sources.clear()
        return

    refined_events.append(
        {
            "type": "text",
            "text": "".join(
                str(event.get("text", event.get("key", "")))
                for event in pending_text_sources
            ),
            **combined_common_fields(pending_text_sources),
        }
    )
    pending_text_sources.clear()
