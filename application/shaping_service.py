from __future__ import annotations

from dataclasses import dataclass

from core.interpretation.interpreted_recording import InterpretedRecording
from core.shaping.shaped_action_sequence import ShapedActionSequence
from core.shaping.shaping_config import ShapingConfig
from core.shaping.shaping_pipeline import ShapingPipeline
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("shaping_service")


@dataclass(frozen=True, slots=True)
class ShapingSummary:
    source_session_id: str
    source_interpreted_event_count: int
    shaped_action_count: int


class ShapingService:
    def __init__(
        self,
        pipeline: ShapingPipeline | None = None,
        *,
        config: ShapingConfig | None = None,
    ) -> None:
        self._pipeline = pipeline or ShapingPipeline(config=config)

    def shape_recording(
        self,
        interpreted: InterpretedRecording,
    ) -> ShapedActionSequence:
        log.info(
            "Shaping service started",
            event_id="shaping.service.started",
            source_session_id=interpreted.source_session_id,
            source_interpreted_event_count=interpreted.event_count(),
        )
        shaped = self._pipeline.shape(interpreted)
        log.info(
            "Shaping service completed",
            event_id="shaping.service.completed",
            source_session_id=shaped.source_session_id,
            source_interpreted_event_count=shaped.source_interpreted_event_count,
            shaped_action_count=shaped.action_count(),
        )
        return shaped

    def summarize(self, shaped: ShapedActionSequence) -> ShapingSummary:
        summary = ShapingSummary(
            source_session_id=shaped.source_session_id,
            source_interpreted_event_count=shaped.source_interpreted_event_count,
            shaped_action_count=shaped.action_count(),
        )
        log.trace(
            "Shaping summary created",
            event_id="shaping.service.summary",
            source_session_id=summary.source_session_id,
            source_interpreted_event_count=summary.source_interpreted_event_count,
            shaped_action_count=summary.shaped_action_count,
        )
        return summary
