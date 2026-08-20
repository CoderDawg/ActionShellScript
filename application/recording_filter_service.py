from __future__ import annotations

from dataclasses import dataclass

from core.filtering import FilterResult, FilterStage, build_default_filter_registry
from core.filtering.recording.recording_filter_pipeline import RecordingFilterPipeline
from core.recording.recording_session import RecordingSession
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("recording_filter_service")


@dataclass(frozen=True, slots=True)
class RecordingFilterSummary:
    profile_id: str
    source_session_id: str
    source_event_count: int
    filtered_event_count: int
    applied_filters: tuple[str, ...]


class RecordingFilterService:
    def __init__(self, pipeline: RecordingFilterPipeline | None = None) -> None:
        self._pipeline = pipeline or RecordingFilterPipeline(
            registry=build_default_filter_registry()
        )

    def list_profile_ids(self) -> tuple[str, ...]:
        return self._pipeline.registry.list_profile_ids(FilterStage.RECORDING)

    def apply_filter(
        self,
        session: RecordingSession,
        profile_id: str,
    ) -> FilterResult[RecordingSession]:
        log.info(
            "Recording filter service started",
            event_id="filter.recording.started",
            profile_id=profile_id,
            source_session_id=session.session_id,
            source_event_count=len(session.events),
        )
        profile = self._pipeline.registry.get_profile(FilterStage.RECORDING, profile_id)
        result = self._pipeline.apply(session, profile)
        log.info(
            "Recording filter service completed",
            event_id="filter.recording.completed",
            profile_id=profile_id,
            source_session_id=session.session_id,
            source_event_count=len(session.events),
            filtered_event_count=len(result.value.events),
            applied_filters=result.applied_filters,
        )
        return result

    def summarize(
        self,
        result: FilterResult[RecordingSession],
        *,
        profile_id: str,
        source_session_id: str,
        source_event_count: int,
    ) -> RecordingFilterSummary:
        summary = RecordingFilterSummary(
            profile_id=profile_id,
            source_session_id=source_session_id,
            source_event_count=source_event_count,
            filtered_event_count=len(result.value.events),
            applied_filters=tuple(result.applied_filters),
        )
        log.trace(
            "Recording filter summary created",
            event_id="filter.recording.summary",
            profile_id=summary.profile_id,
            source_session_id=summary.source_session_id,
            source_event_count=summary.source_event_count,
            filtered_event_count=summary.filtered_event_count,
            applied_filters=summary.applied_filters,
        )
        return summary
