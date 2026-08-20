from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from core.interpretation.interpreted_recording import InterpretedRecording
from core.interpretation.interpretation_config import InterpretationConfig
from core.interpretation.recording_interpreter import RecordingInterpreter
from core.recording.recording_session import RecordingSession
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("interpretation_service")


@dataclass(frozen=True, slots=True)
class InterpretationSummary:
    source_session_id: str
    source_event_count: int
    interpreted_event_count: int
    interpreted_event_types: dict[str, int]


class InterpretationService:
    def __init__(
        self,
        interpreter: RecordingInterpreter | None = None,
        *,
        config: InterpretationConfig | None = None,
    ) -> None:
        self._interpreter = interpreter or RecordingInterpreter(config=config)

    def interpret_recording(self, session: RecordingSession) -> InterpretedRecording:
        log.info(
            "Interpretation service started",
            event_id="interpretation.service.started",
            source_session_id=session.session_id,
            source_event_count=len(session.events),
        )
        interpreted = self._interpreter.interpret(session)
        log.info(
            "Interpretation service completed",
            event_id="interpretation.service.completed",
            source_session_id=interpreted.source_session_id,
            source_event_count=interpreted.source_event_count,
            interpreted_event_count=interpreted.event_count(),
        )
        return interpreted

    def summarize(self, interpreted: InterpretedRecording) -> InterpretationSummary:
        counts = Counter(str(event.get("type", "")).strip().lower() for event in interpreted.events)
        summary = InterpretationSummary(
            source_session_id=interpreted.source_session_id,
            source_event_count=interpreted.source_event_count,
            interpreted_event_count=interpreted.event_count(),
            interpreted_event_types=dict(sorted(counts.items())),
        )
        log.trace(
            "Interpretation summary created",
            event_id="interpretation.service.summary",
            source_session_id=summary.source_session_id,
            source_event_count=summary.source_event_count,
            interpreted_event_count=summary.interpreted_event_count,
            interpreted_event_types=summary.interpreted_event_types,
        )
        return summary
