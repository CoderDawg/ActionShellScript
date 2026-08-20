from __future__ import annotations

from core.shaping.shaped_action_sequence import ShapedActionSequence

from ..filter_profile import FilterProfile


class PreserveShapingFilter:
    filter_id = "preserve_shaping"

    def apply(
        self,
        source: ShapedActionSequence,
        profile: FilterProfile,
    ) -> ShapedActionSequence:
        del profile
        return ShapedActionSequence(
            source_session_id=source.source_session_id,
            source_interpreted_event_count=source.source_interpreted_event_count,
            actions=[dict(action) for action in source.actions],
        )
