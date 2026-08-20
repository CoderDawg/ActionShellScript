from __future__ import annotations

from .click_interpreter import collapse_mouse_button_sequences_to_clicks
from .drag_interpreter import annotate_drag_sequences
from .interpreted_recording import InterpretedRecording
from .interpretation_config import InterpretationConfig
from .keyboard_interpreter import annotate_hotkey_sequences, annotate_key_holds
from core.recording.recording_session import RecordingSession
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("recording_interpreter")


class RecordingInterpreter:
    def __init__(
        self,
        *,
        config: InterpretationConfig | None = None,
    ) -> None:
        self._config = config or InterpretationConfig()

    def interpret(self, session: RecordingSession) -> InterpretedRecording:
        raw_events = [dict(event) for event in session.events]
        log.info(
            "Interpretation pipeline starting",
            event_id="interpretation.pipeline.started",
            source_session_id=session.session_id,
            raw_event_count=len(raw_events),
        )

        # Click collapse runs before drag recognition so simple click spans are removed
        # from later passes while drag-like spans stay available as raw mouse events.
        click_events = collapse_mouse_button_sequences_to_clicks(
            raw_events,
            config=self._config,
        )
        log.decision(
            "Completed click interpretation pass",
            event_id="interpretation.pass.click",
            input_event_count=len(raw_events),
            output_event_count=len(click_events),
        )
        drag_events = annotate_drag_sequences(
            click_events,
            config=self._config,
        )
        log.decision(
            "Completed drag interpretation pass",
            event_id="interpretation.pass.drag",
            input_event_count=len(click_events),
            output_event_count=len(drag_events),
        )
        key_hold_events = annotate_key_holds(drag_events)
        log.decision(
            "Completed key-hold interpretation pass",
            event_id="interpretation.pass.key_hold",
            input_event_count=len(drag_events),
            output_event_count=len(key_hold_events),
        )
        final_events = annotate_hotkey_sequences(key_hold_events)
        log.decision(
            "Completed hotkey interpretation pass",
            event_id="interpretation.pass.hotkey",
            input_event_count=len(key_hold_events),
            output_event_count=len(final_events),
        )

        interpreted = InterpretedRecording(
            source_session_id=session.session_id,
            source_event_count=len(session.events),
            events=final_events,
        )
        log.info(
            "Interpretation pipeline completed",
            event_id="interpretation.pipeline.completed",
            source_session_id=interpreted.source_session_id,
            source_event_count=interpreted.source_event_count,
            interpreted_event_count=interpreted.event_count(),
        )
        return interpreted
