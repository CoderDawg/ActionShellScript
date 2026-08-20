from __future__ import annotations

from core.interpretation.interpreted_recording import InterpretedRecording
from .click_shaper import shape_click_actions
from .delay_shaper import shape_delays
from .keyboard_shaper import shape_keyboard_actions
from .mouse_shaper import shape_mouse_actions
from .shaped_action_sequence import ShapedActionSequence
from .shaping_config import ShapingConfig


class ShapingPipeline:
    def __init__(
        self,
        *,
        config: ShapingConfig | None = None,
    ) -> None:
        self._config = config or ShapingConfig()

    def shape(self, interpreted: InterpretedRecording) -> ShapedActionSequence:
        actions = [dict(event) for event in interpreted.events]

        # Phase 3 is intentionally ordered from broad structural cleanup toward
        # the representation decisions that later script generation depends on.
        actions = shape_mouse_actions(actions, config=self._config)
        actions = shape_click_actions(actions, config=self._config)
        actions = shape_keyboard_actions(actions, config=self._config)
        actions = shape_delays(actions, config=self._config)

        return ShapedActionSequence(
            source_session_id=interpreted.source_session_id,
            source_interpreted_event_count=interpreted.event_count(),
            actions=actions,
        )
