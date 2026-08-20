from __future__ import annotations

from core.interpretation.recording_interpreter import RecordingInterpreter
from core.playback.playback_events import normalize_shaped_action_to_playback_events
from core.recording.recording_session import RecordingSession
from core.shaping.shaping_pipeline import ShapingPipeline
from core.playback.playback_plan import PlaybackPlan


class PlaybackPlanFromRecordingBuilder:
    def __init__(
        self,
        *,
        interpreter: RecordingInterpreter | None = None,
        shaping_pipeline: ShapingPipeline | None = None,
    ) -> None:
        self._interpreter = interpreter or RecordingInterpreter()
        self._shaping_pipeline = shaping_pipeline or ShapingPipeline()

    def build(self, session: RecordingSession) -> PlaybackPlan:
        interpreted = self._interpreter.interpret(session)
        shaped = self._shaping_pipeline.shape(interpreted)

        events = []
        for action in shaped.actions:
            normalized = normalize_shaped_action_to_playback_events(action)
            if normalized is None:
                action_type = str(action.get("type", "<missing>"))
                raise RuntimeError(
                    f"Unsupported recording playback action contract: {action_type}"
                )
            events.extend(normalized)

        return PlaybackPlan(
            source_kind="recording_session",
            source_id=session.session_id,
            event_count=len(events),
            events=events,
        )
