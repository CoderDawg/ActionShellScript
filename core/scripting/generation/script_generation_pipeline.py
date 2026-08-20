from __future__ import annotations

from infrastructure.debug_logger import get_diagnostic_logger

from .action_to_script_renderer import render_actions_to_lines
from .generated_script import GeneratedScript
from .header_comment_renderer import render_header_comments
from .script_generation_config import ScriptGenerationConfig
from core.shaping.shaped_action_sequence import ShapedActionSequence


log = get_diagnostic_logger("script_generation_pipeline")


class ScriptGenerationPipeline:
    def __init__(
        self,
        *,
        config: ScriptGenerationConfig | None = None,
    ) -> None:
        self._config = config or ScriptGenerationConfig()

    def generate(self, shaped: ShapedActionSequence) -> GeneratedScript:
        log.info(
            "Script generation pipeline started",
            event_id="generation.pipeline.started",
            source_session_id=shaped.source_session_id,
            source_interpreted_event_count=shaped.source_interpreted_event_count,
            action_count=shaped.action_count(),
            include_header_comments=self._config.include_header_comments,
            include_source_summary=self._config.include_source_summary,
            emit_delays=self._config.emit_delays,
            line_ending=repr(self._config.line_ending),
        )

        lines: list[str] = []

        header_lines = render_header_comments(shaped, config=self._config)
        if header_lines:
            log.decision(
                "Rendered header comments for generated script",
                event_id="generation.pipeline.header_rendered",
                header_line_count=len(header_lines),
            )
            lines.extend(header_lines)
        else:
            log.decision(
                "Skipped header comments for generated script",
                event_id="generation.pipeline.header_skipped",
                include_header_comments=self._config.include_header_comments,
            )

        body_lines = render_actions_to_lines(
            shaped.actions,
            config=self._config,
        )
        if header_lines and body_lines:
            lines.append("")
            log.trace(
                "Inserted blank separator line between generated header and body",
                event_id="generation.pipeline.separator_inserted",
            )
        lines.extend(body_lines)
        log.trace(
            "Rendered generated script body",
            event_id="generation.pipeline.body_rendered",
            body_line_count=len(body_lines),
            total_line_count=len(lines),
        )

        text = self._config.line_ending.join(lines)
        if lines:
            text += self._config.line_ending

        generated = GeneratedScript(
            source_session_id=shaped.source_session_id,
            source_action_count=shaped.action_count(),
            text=text,
        )
        log.info(
            "Script generation pipeline completed",
            event_id="generation.pipeline.completed",
            source_session_id=generated.source_session_id,
            source_action_count=generated.source_action_count,
            line_count=generated.line_count(),
        )
        return generated
