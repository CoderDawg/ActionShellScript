from __future__ import annotations

from dataclasses import dataclass

from core.recording.recording_session import RecordingSession, RecordingState

from ..filter_profile import FilterProfile
from ..filter_registry import FilterRegistry, build_default_filter_registry
from ..filter_result import FilterResult
from ..filter_stage import FilterStage


@dataclass(slots=True)
class RecordingFilterPipeline:
    registry: FilterRegistry

    def __init__(self, registry: FilterRegistry | None = None) -> None:
        self.registry = registry or build_default_filter_registry()

    def apply(self, source: RecordingSession, profile: FilterProfile) -> FilterResult[RecordingSession]:
        if profile.target_stage is not FilterStage.RECORDING:
            raise ValueError(
                f"Profile {profile.profile_id!r} targets {profile.target_stage.value!r}, not recording."
            )

        current = RecordingSession(
            session_id=source.session_id,
            state=RecordingState(source.state.value),
            started_at_ms=source.started_at_ms,
            stopped_at_ms=source.stopped_at_ms,
            events=[dict(event) for event in source.events],
        )
        applied_filters: list[str] = []
        notes: list[str] = []

        for filter_id in profile.enabled_filters:
            filter_impl = self.registry.get_filter(filter_id)
            current = filter_impl.apply(current, profile)
            applied_filters.append(filter_id)

        notes.append("Recording source was copied into a derived session before filtering.")
        return FilterResult(value=current, applied_filters=applied_filters, notes=notes)
