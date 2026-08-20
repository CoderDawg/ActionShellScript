from __future__ import annotations

from editor.document.script_document import ScriptDocument
from core.playback.playback_events import (
    normalize_shaped_action_to_playback_events,
    playback_event_source_line,
)
from core.playback.playback_plan import PlaybackPlan
from core.runtime.script_runtime import ScriptRuntime


class PlaybackPlanFromScriptBuilder:
    def __init__(
        self,
        *,
        runtime: ScriptRuntime | None = None,
    ) -> None:
        self._runtime = runtime or ScriptRuntime()

    def build(self, document: ScriptDocument) -> PlaybackPlan:
        context = self._runtime.compile(document.text, source_path=document.source_path)
        events = []
        event_source_lines: list[int | None] = []
        for action in context.playback_events:
            normalized = normalize_shaped_action_to_playback_events(action)
            if normalized is None:
                continue
            source_line = playback_event_source_line(action)
            events.extend(normalized)
            event_source_lines.extend([source_line] * len(normalized))

        return PlaybackPlan(
            source_kind="script_document",
            source_id=document.document_id,
            event_count=len(events),
            delay_ms_override=context.get_current_event_delay_override(),
            events=events,
            event_source_lines=event_source_lines,
            console_output=list(context.console_output),
            diagnostics_output=list(context.diagnostics),
        )
