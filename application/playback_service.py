from __future__ import annotations

from dataclasses import dataclass, field

from core.playback.playback_builder import PlaybackBuilder
from core.playback.playback_engine import PlaybackEngine
from core.playback.playback_mode import PlaybackMode
from core.playback.playback_plan import PlaybackPlan
from core.playback.playback_request import PlaybackRequest
from core.playback.playback_result import PlaybackResult
from core.playback.playback_result_bus import publish_playback_result
from core.playback.playback_result_formatter import playback_failure_details
from core.recording.recording_session import RecordingSession
from editor.document.script_document import ScriptDocument
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("playback_service")


@dataclass(frozen=True, slots=True)
class PlaybackSummary:
    source_kind: str
    source_id: str
    event_count: int
    console_output: list[str] = field(default_factory=list)
    diagnostics_output: list[str] = field(default_factory=list)


class PlaybackService:
    def __init__(
        self,
        *,
        builder: PlaybackBuilder,
        live_engine: PlaybackEngine,
        preview_engine: PlaybackEngine,
    ) -> None:
        self._builder = builder
        self._live_engine = live_engine
        self._preview_engine = preview_engine

    def build_plan_from_recording(
        self,
        session: RecordingSession,
    ) -> PlaybackPlan:
        log.info(
            "Building playback plan from recording authority",
            event_id="playback.plan.recording_started",
            source_kind="recording_session",
            source_id=session.session_id,
        )
        plan = self._builder.build_from_recording(session)
        log.info(
            "Built playback plan from recording authority",
            event_id="playback.plan.recording_completed",
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            event_count=plan.event_count,
        )
        return plan

    def build_plan_from_script(
        self,
        document: ScriptDocument,
    ) -> PlaybackPlan:
        log.info(
            "Building playback plan from script authority",
            event_id="playback.plan.script_started",
            source_kind="script_document",
            source_id=document.document_id,
        )
        plan = self._builder.build_from_script(document)
        log.info(
            "Built playback plan from script authority",
            event_id="playback.plan.script_completed",
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            event_count=plan.event_count,
        )
        return plan

    def play_recording(
        self,
        session: RecordingSession,
        request: PlaybackRequest,
    ) -> PlaybackResult:
        self._validate_request(
            request,
            expected_source_kind="recording_session",
            expected_source_id=session.session_id,
        )
        plan = self.build_plan_from_recording(session)
        return self._play_plan_for_request(plan, request)

    def play_script(
        self,
        document: ScriptDocument,
        request: PlaybackRequest,
    ) -> PlaybackResult:
        self._validate_request(
            request,
            expected_source_kind="script_document",
            expected_source_id=document.document_id,
        )
        plan = self.build_plan_from_script(document)
        return self._play_plan_for_request(plan, request)

    def play_plan(
        self,
        plan: PlaybackPlan,
        request: PlaybackRequest,
    ) -> PlaybackResult:
        self._validate_request(
            request,
            expected_source_kind=plan.source_kind,
            expected_source_id=plan.source_id,
        )
        return self._play_plan_for_request(plan, request)

    def summarize_plan(self, plan: PlaybackPlan) -> PlaybackSummary:
        return PlaybackSummary(
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            event_count=plan.event_count,
            console_output=list(plan.console_output),
            diagnostics_output=list(plan.diagnostics_output),
        )

    def _play_plan_for_request(
        self,
        plan: PlaybackPlan,
        request: PlaybackRequest,
    ) -> PlaybackResult:
        engine = self._engine_for_mode(request.mode)
        log.info(
            "Executing playback plan",
            event_id="playback.execute.started",
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            mode=request.mode.value,
            repeat_count=request.repeat_count,
            event_count=plan.event_count,
        )
        result = engine.play(plan, request=request)
        if result.success:
            log.info(
                "Playback plan executed successfully",
                event_id="playback.execute.completed",
                source_kind=result.source_kind,
                source_id=result.source_id,
                executed_event_count=result.executed_event_count,
            )
        else:
            failure_details = playback_failure_details(result)
            if failure_details.error_line is not None and failure_details.error_message is not None:
                log.error(
                    "Playback plan execution failed",
                    event_id="playback.execute.failed",
                    source_kind=result.source_kind,
                    source_id=result.source_id,
                    executed_event_count=result.executed_event_count,
                    error_line=failure_details.error_line,
                    error_message=failure_details.error_message,
                )
            elif failure_details.error_line is not None:
                log.error(
                    "Playback plan execution failed",
                    event_id="playback.execute.failed",
                    source_kind=result.source_kind,
                    source_id=result.source_id,
                    executed_event_count=result.executed_event_count,
                    error_line=failure_details.error_line,
                )
            elif failure_details.error_message is not None:
                log.error(
                    "Playback plan execution failed",
                    event_id="playback.execute.failed",
                    source_kind=result.source_kind,
                    source_id=result.source_id,
                    executed_event_count=result.executed_event_count,
                    error_message=failure_details.error_message,
                )
            else:
                log.error(
                    "Playback plan execution failed",
                    event_id="playback.execute.failed",
                    source_kind=result.source_kind,
                    source_id=result.source_id,
                    executed_event_count=result.executed_event_count,
                )
        publish_playback_result(result)
        return result

    def _engine_for_mode(self, mode: PlaybackMode) -> PlaybackEngine:
        if mode == PlaybackMode.PREVIEW:
            log.decision(
                "Selected preview playback engine",
                event_id="playback.engine.selected",
                mode=mode.value,
            )
            return self._preview_engine
        log.decision(
            "Selected live playback engine",
            event_id="playback.engine.selected",
            mode=mode.value,
        )
        return self._live_engine

    def _validate_request(
        self,
        request: PlaybackRequest,
        *,
        expected_source_kind: str,
        expected_source_id: str,
    ) -> None:
        if request.source_kind != expected_source_kind:
            log.error(
                "Playback request source kind validation failed",
                event_id="playback.request.invalid_source_kind",
                expected_source_kind=expected_source_kind,
                actual_source_kind=request.source_kind,
                source_id=request.source_id,
            )
            raise ValueError(
                f"PlaybackRequest source_kind mismatch: expected "
                f"{expected_source_kind}, got {request.source_kind}"
            )
        if request.source_id != expected_source_id:
            log.error(
                "Playback request source id validation failed",
                event_id="playback.request.invalid_source_id",
                expected_source_id=expected_source_id,
                actual_source_id=request.source_id,
                source_kind=request.source_kind,
            )
            raise ValueError(
                f"PlaybackRequest source_id mismatch: expected "
                f"{expected_source_id}, got {request.source_id}"
            )

