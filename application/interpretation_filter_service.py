from __future__ import annotations

from dataclasses import dataclass

from core.filtering import FilterResult, FilterStage, build_default_filter_registry
from core.filtering.interpretation.interpretation_filter_pipeline import (
    InterpretationFilterPipeline,
)
from core.interpretation.interpreted_recording import InterpretedRecording
from core.recording.recording_session import RecordingSession

from application.interpretation_service import InterpretationService
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("interpretation_filter_service")


@dataclass(frozen=True, slots=True)
class InterpretationFilterSummary:
    profile_id: str
    source_session_id: str
    source_event_count: int
    filtered_event_count: int
    applied_filters: tuple[str, ...]


class InterpretationFilterService:
    def __init__(
        self,
        pipeline: InterpretationFilterPipeline | None = None,
        interpretation_service: InterpretationService | None = None,
    ) -> None:
        self._pipeline = pipeline or InterpretationFilterPipeline(
            registry=build_default_filter_registry()
        )
        self._interpretation_service = interpretation_service or InterpretationService()

    def list_profile_ids(self) -> tuple[str, ...]:
        return self._pipeline.registry.list_profile_ids(FilterStage.INTERPRETATION)

    def apply_filter(
        self,
        source: RecordingSession | InterpretedRecording,
        profile_id: str,
    ) -> FilterResult[InterpretedRecording]:
        source_kind = (
            "recording_session"
            if isinstance(source, RecordingSession)
            else "interpreted_recording"
        )
        log.info(
            "Interpretation filter service started",
            event_id="filter.interpretation.started",
            profile_id=profile_id,
            source_kind=source_kind,
        )
        if isinstance(source, RecordingSession):
            interpreted = self._interpretation_service.interpret_recording(source)
        else:
            interpreted = source
        profile = self._pipeline.registry.get_profile(
            FilterStage.INTERPRETATION,
            profile_id,
        )
        result = self._pipeline.apply(interpreted, profile)
        log.info(
            "Interpretation filter service completed",
            event_id="filter.interpretation.completed",
            profile_id=profile_id,
            source_kind=source_kind,
            source_session_id=interpreted.source_session_id,
            source_event_count=interpreted.source_event_count,
            filtered_event_count=len(result.value.events),
            applied_filters=result.applied_filters,
        )
        return result

    def summarize(
        self,
        result: FilterResult[InterpretedRecording],
        *,
        profile_id: str,
        source_session_id: str,
        source_event_count: int,
    ) -> InterpretationFilterSummary:
        summary = InterpretationFilterSummary(
            profile_id=profile_id,
            source_session_id=source_session_id,
            source_event_count=source_event_count,
            filtered_event_count=len(result.value.events),
            applied_filters=tuple(result.applied_filters),
        )
        log.trace(
            "Interpretation filter summary created",
            event_id="filter.interpretation.summary",
            profile_id=summary.profile_id,
            source_session_id=summary.source_session_id,
            source_event_count=summary.source_event_count,
            filtered_event_count=summary.filtered_event_count,
            applied_filters=summary.applied_filters,
        )
        return summary

    def source_session_id(self, source: RecordingSession | InterpretedRecording) -> str:
        if isinstance(source, RecordingSession):
            return source.session_id
        return source.source_session_id

    def source_event_count(self, source: RecordingSession | InterpretedRecording) -> int:
        if isinstance(source, RecordingSession):
            return len(source.events)
        return source.source_event_count
