from __future__ import annotations

from dataclasses import dataclass

from core.shaping.shaped_action_sequence import ShapedActionSequence

from ..filter_profile import FilterProfile
from ..filter_registry import FilterRegistry, build_default_filter_registry
from ..filter_result import FilterResult
from ..filter_stage import FilterStage


@dataclass(slots=True)
class ShapedActionFilterPipeline:
    registry: FilterRegistry

    def __init__(self, registry: FilterRegistry | None = None) -> None:
        self.registry = registry or build_default_filter_registry()

    def apply(
        self,
        source: ShapedActionSequence,
        profile: FilterProfile,
    ) -> FilterResult[ShapedActionSequence]:
        if profile.target_stage is not FilterStage.SHAPING:
            raise ValueError(
                f"Profile {profile.profile_id!r} targets {profile.target_stage.value!r}, not shaping."
            )

        current = ShapedActionSequence(
            source_session_id=source.source_session_id,
            source_interpreted_event_count=source.source_interpreted_event_count,
            actions=[dict(action) for action in source.actions],
        )
        applied_filters: list[str] = []
        notes: list[str] = []

        for filter_id in profile.enabled_filters:
            filter_impl = self.registry.get_filter(filter_id)
            current = filter_impl.apply(current, profile)
            applied_filters.append(filter_id)

        notes.append("Shaped actions were copied into a derived result before filtering.")
        return FilterResult(value=current, applied_filters=applied_filters, notes=notes)
