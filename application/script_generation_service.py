from __future__ import annotations

from dataclasses import dataclass

from core.scripting.generation.generated_script import GeneratedScript
from core.scripting.generation.script_generation_config import ScriptGenerationConfig
from core.scripting.generation.script_generation_pipeline import ScriptGenerationPipeline
from core.shaping.shaped_action_sequence import ShapedActionSequence
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("script_generation_service")


@dataclass(frozen=True, slots=True)
class ScriptGenerationSummary:
    source_session_id: str
    source_action_count: int
    line_count: int


class ScriptGenerationService:
    def __init__(
        self,
        pipeline: ScriptGenerationPipeline | None = None,
        *,
        config: ScriptGenerationConfig | None = None,
    ) -> None:
        self._pipeline = pipeline or ScriptGenerationPipeline(config=config)

    def generate_script(
        self,
        shaped: ShapedActionSequence,
    ) -> GeneratedScript:
        log.info(
            "Script generation started",
            event_id="generation.service.started",
            source_session_id=shaped.source_session_id,
            source_action_count=shaped.action_count(),
        )
        script = self._pipeline.generate(shaped)
        log.info(
            "Script generation completed",
            event_id="generation.service.completed",
            source_session_id=script.source_session_id,
            source_action_count=script.source_action_count,
            line_count=script.line_count(),
        )
        return script

    def summarize(self, script: GeneratedScript) -> ScriptGenerationSummary:
        summary = ScriptGenerationSummary(
            source_session_id=script.source_session_id,
            source_action_count=script.source_action_count,
            line_count=script.line_count(),
        )
        log.trace(
            "Script generation summary created",
            event_id="generation.service.summary",
            source_session_id=summary.source_session_id,
            source_action_count=summary.source_action_count,
            line_count=summary.line_count,
        )
        return summary
