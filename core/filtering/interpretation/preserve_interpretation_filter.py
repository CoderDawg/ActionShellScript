from __future__ import annotations

from core.interpretation.interpreted_recording import InterpretedRecording

from ..filter_profile import FilterProfile


class PreserveInterpretationFilter:
    filter_id = "preserve_interpretation"

    def apply(
        self,
        source: InterpretedRecording,
        profile: FilterProfile,
    ) -> InterpretedRecording:
        del profile
        return InterpretedRecording(
            source_session_id=source.source_session_id,
            source_event_count=source.source_event_count,
            events=[dict(event) for event in source.events],
        )
