from __future__ import annotations

from dataclasses import dataclass

from core.filtering import FilterResult, FilterStage, build_default_filter_registry
from core.filtering.shaping.shaped_action_filter_pipeline import (
    ShapedActionFilterPipeline,
)
from core.interpretation.interpreted_recording import InterpretedRecording
from core.recording.recording_session import RecordingSession
from core.shaping.shaped_action_sequence import ShapedActionSequence

from application.interpretation_service import InterpretationService
from application.shaping_service import ShapingService
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("shaping_filter_service")


@dataclass(frozen=True, slots=True)
class ShapingFilterSummary:
    profile_id: str
    source_session_id: str
    source_interpreted_event_count: int
    filtered_action_count: int
    applied_filters: tuple[str, ...]


class ShapingFilterService:
    def __init__(
        self,
        pipeline: ShapedActionFilterPipeline | None = None,
        interpretation_service: InterpretationService | None = None,
        shaping_service: ShapingService | None = None,
    ) -> None:
        self._pipeline = pipeline or ShapedActionFilterPipeline(
            registry=build_default_filter_registry()
        )
        self._interpretation_service = interpretation_service or InterpretationService()
        self._shaping_service = shaping_service or ShapingService()

    def list_profile_ids(self) -> tuple[str, ...]:
        return self._pipeline.registry.list_profile_ids(FilterStage.SHAPING)

    def apply_filter(
        self,
        source: RecordingSession | InterpretedRecording | ShapedActionSequence,
        profile_id: str,
    ) -> FilterResult[ShapedActionSequence]:
        source_kind = (
            "recording_session"
            if isinstance(source, RecordingSession)
            else "interpreted_recording"
            if isinstance(source, InterpretedRecording)
            else "shaped_action_sequence"
        )
        log.info(
            "Shaping filter service started",
            event_id="filter.shaping.started",
            profile_id=profile_id,
            source_kind=source_kind,
        )
        if isinstance(source, RecordingSession):
            interpreted = self._interpretation_service.interpret_recording(source)
            shaped = self._shaping_service.shape_recording(interpreted)
        elif isinstance(source, InterpretedRecording):
            interpreted = source
            shaped = self._shaping_service.shape_recording(interpreted)
        else:
            shaped = source
        profile = self._pipeline.registry.get_profile(FilterStage.SHAPING, profile_id)
        result = self._pipeline.apply(shaped, profile)
        log.info(
            "Shaping filter service completed",
            event_id="filter.shaping.completed",
            profile_id=profile_id,
            source_kind=source_kind,
            input_action_count=len(shaped.actions),
            output_action_count=len(result.value.actions),
            applied_filters=result.applied_filters,
        )
        return result

    def summarize(
        self,
        result: FilterResult[ShapedActionSequence],
        *,
        profile_id: str,
        source_session_id: str,
        source_interpreted_event_count: int,
    ) -> ShapingFilterSummary:
        summary = ShapingFilterSummary(
            profile_id=profile_id,
            source_session_id=source_session_id,
            source_interpreted_event_count=source_interpreted_event_count,
            filtered_action_count=len(result.value.actions),
            applied_filters=tuple(result.applied_filters),
        )
        log.trace(
            "Shaping filter summary created",
            event_id="filter.shaping.summary",
            profile_id=summary.profile_id,
            source_session_id=summary.source_session_id,
            source_interpreted_event_count=summary.source_interpreted_event_count,
            filtered_action_count=summary.filtered_action_count,
            applied_filters=summary.applied_filters,
        )
        return summary

    def source_session_id(
        self,
        source: RecordingSession | InterpretedRecording | ShapedActionSequence,
    ) -> str:
        if isinstance(source, RecordingSession):
            return source.session_id
        return source.source_session_id

    def source_interpreted_event_count(
        self,
        source: RecordingSession | InterpretedRecording | ShapedActionSequence,
    ) -> int:
        if isinstance(source, RecordingSession):
            interpreted = self._interpretation_service.interpret_recording(source)
            return interpreted.event_count()
        if isinstance(source, InterpretedRecording):
            return source.event_count()
        return source.source_interpreted_event_count
