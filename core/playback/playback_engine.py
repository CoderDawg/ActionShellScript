from __future__ import annotations

import json
import sys
import threading
import time

from core.playback.playback_plan import PlaybackPlan
from core.playback.playback_request import PlaybackRequest
from core.playback.playback_result import PlaybackResult
from core.playback.playback_events import (
    playback_event_source_line,
    playback_event_to_dict,
)
from core.playback.playback_sleep import sleep_ms_interruptibly
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("playback.engine")


class PlaybackEngine:
    def __init__(
        self,
        executor,
        stop_event: threading.Event | None = None,
        *,
        sleep_chunk_ms: int = 50,
    ) -> None:
        self._executor = executor
        self._stop_event = stop_event
        self._sleep_chunk_ms = max(1, int(sleep_chunk_ms))

    def play(self, plan: PlaybackPlan, *, request: PlaybackRequest) -> PlaybackResult:
        executed_count = 0
        event_index = 0
        event: object | None = None
        normalized_repeat_count = max(1, int(request.repeat_count))
        normalized_delay_ms = max(0, int(request.delay_ms))
        step_mode = bool(request.step_mode)

        if step_mode and not sys.stdin.isatty():
            raise RuntimeError(
                "Playback step mode requires an interactive terminal."
            )

        log.info(
            "Playback engine starting execution",
            event_id="playback.engine.started",
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            event_count=plan.event_count,
            repeat_count=normalized_repeat_count,
            step_mode=step_mode,
            delay_ms=normalized_delay_ms,
        )

        try:
            for repeat_index in range(normalized_repeat_count):
                log.decision(
                    "Starting playback repeat iteration",
                    event_id="playback.engine.repeated",
                    repeat_index=repeat_index + 1,
                    repeat_count=normalized_repeat_count,
                )
                for event_index, event in enumerate(plan.events, start=1):
                    event_payload = playback_event_to_dict(event)
                    source_line = self._event_source_line(
                        plan,
                        event=event,
                        event_index=event_index,
                    )
                    log.trace(
                        "Dispatching playback event to executor",
                        event_id="playback.engine.dispatched",
                        event_type=event_payload.get("type"),
                        repeat_index=repeat_index + 1,
                        event_index=event_index,
                        source_line=source_line,
                        event_payload=event_payload,
                    )
                    self._before_event(
                        event_payload,
                        repeat_index=repeat_index + 1,
                        event_index=event_index,
                        event_count=plan.event_count,
                        step_mode=step_mode,
                        delay_ms=normalized_delay_ms,
                    )
                    self._executor.execute(event)
                    executed_count += 1

            result = PlaybackResult(
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                executed_event_count=executed_count,
                success=True,
                delay_ms=normalized_delay_ms,
                playback_mode=request.mode.value,
                sendkeys_transport=request.sendkeys_transport,
                console_output=list(plan.console_output),
                diagnostics_output=list(plan.diagnostics_output),
            )
            log.info(
                "Playback engine finished execution successfully",
                event_id="playback.engine.completed",
                source_kind=result.source_kind,
                source_id=result.source_id,
                executed_event_count=result.executed_event_count,
            )
            return result

        except KeyboardInterrupt:
            log.warning(
                "Playback interrupted by user",
                event_id="playback.engine.interrupted",
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                executed_event_count=executed_count,
            )
            return PlaybackResult(
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                executed_event_count=executed_count,
                success=False,
                delay_ms=normalized_delay_ms,
                playback_mode=request.mode.value,
                sendkeys_transport=request.sendkeys_transport,
                console_output=list(plan.console_output),
                diagnostics_output=list(plan.diagnostics_output),
                error_line=None,
                error_message="Playback interrupted by user.",
            )
        except Exception as exc:
            error_line = self._event_source_line(
                plan,
                event=event,
                event_index=event_index,
            )
            log.exception(
                "Playback engine executor raised an exception",
                exc,
                event_id="playback.engine.failed",
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                executed_event_count=executed_count,
                error_line=error_line,
            )
            return PlaybackResult(
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                executed_event_count=executed_count,
                success=False,
                delay_ms=normalized_delay_ms,
                playback_mode=request.mode.value,
                sendkeys_transport=request.sendkeys_transport,
                console_output=list(plan.console_output),
                diagnostics_output=list(plan.diagnostics_output),
                error_line=error_line,
                error_message=str(exc),
            )

    def _before_event(
        self,
        event_payload: dict[str, object],
        *,
        repeat_index: int,
        event_index: int,
        event_count: int,
        step_mode: bool,
        delay_ms: int,
    ) -> None:
        if delay_ms > 0:
            log.decision(
                "Applying global playback delay",
                event_id="playback.engine.delayed",
                repeat_index=repeat_index,
                event_index=event_index,
                delay_ms=delay_ms,
            )
            self._sleep_interruptibly(delay_ms)

        if not step_mode:
            return

        event_json = json.dumps(event_payload, sort_keys=True)
        prompt = (
            f"Step {event_index}/{event_count} (repeat {repeat_index}): "
            f"{event_json}  Press Enter to continue, or Ctrl-C to quit."
        )
        print(prompt, flush=True)
        input()

    def _sleep_interruptibly(self, duration_ms: int) -> None:
        if sleep_ms_interruptibly(
            duration_ms,
            stop_event=self._stop_event,
            sleep_fn=time.sleep,
            chunk_ms=self._sleep_chunk_ms,
        ):
            raise KeyboardInterrupt

    def _event_source_line(
        self,
        plan: PlaybackPlan,
        *,
        event: object | None,
        event_index: int,
    ) -> int | None:
        plan_lines = plan.event_source_lines
        if 1 <= event_index <= len(plan_lines):
            source_line = plan_lines[event_index - 1]
            if isinstance(source_line, int) and source_line > 0:
                return source_line
        if event is not None:
            source_line = playback_event_source_line(event)
            if isinstance(source_line, int) and source_line > 0:
                return source_line
        return None

