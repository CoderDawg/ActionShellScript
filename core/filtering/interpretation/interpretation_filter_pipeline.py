from __future__ import annotations

from dataclasses import dataclass

from core.interpretation.interpreted_recording import InterpretedRecording

from ..filter_profile import FilterProfile
from ..filter_registry import FilterRegistry, build_default_filter_registry
from ..filter_result import FilterResult
from ..filter_stage import FilterStage


@dataclass(slots=True)
class InterpretationFilterPipeline:
    registry: FilterRegistry

    def __init__(self, registry: FilterRegistry | None = None) -> None:
        self.registry = registry or build_default_filter_registry()

    def apply(
        self,
        source: InterpretedRecording,
        profile: FilterProfile,
    ) -> FilterResult[InterpretedRecording]:
        if profile.target_stage is not FilterStage.INTERPRETATION:
            raise ValueError(
                f"Profile {profile.profile_id!r} targets {profile.target_stage.value!r}, not interpretation."
            )

        current = InterpretedRecording(
            source_session_id=source.source_session_id,
            source_event_count=source.source_event_count,
            events=[dict(event) for event in source.events],
        )
        applied_filters: list[str] = []
        notes: list[str] = []

        for filter_id in profile.enabled_filters:
            filter_impl = self.registry.get_filter(filter_id)
            current = filter_impl.apply(current, profile)
            applied_filters.append(filter_id)

        notes.append("Interpreted events were copied into a derived result before filtering.")
        return FilterResult(value=current, applied_filters=applied_filters, notes=notes)
