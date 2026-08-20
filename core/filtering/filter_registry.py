from __future__ import annotations

from dataclasses import dataclass, field

from .filter_profile import FilterProfile
from .filter_stage import FilterStage


@dataclass(slots=True)
class FilterRegistry:
    profiles: dict[FilterStage, dict[str, FilterProfile]] = field(default_factory=dict)
    filters: dict[str, object] = field(default_factory=dict)

    def register_profile(self, profile: FilterProfile) -> None:
        self.profiles.setdefault(profile.target_stage, {})[profile.profile_id] = profile

    def register_filter(self, filter_id: str, filter_impl: object) -> None:
        self.filters[filter_id] = filter_impl

    def get_profile(self, stage: FilterStage, profile_id: str) -> FilterProfile:
        try:
            return self.profiles[stage][profile_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown filter profile {profile_id!r} for stage {stage.value!r}."
            ) from exc

    def list_profile_ids(self, stage: FilterStage) -> tuple[str, ...]:
        return tuple(sorted(self.profiles.get(stage, {}).keys()))

    def get_filter(self, filter_id: str) -> object:
        try:
            return self.filters[filter_id]
        except KeyError as exc:
            raise KeyError(f"Unknown filter id {filter_id!r}.") from exc


def build_default_filter_registry() -> FilterRegistry:
    from .documents.document_normalization_filter import DocumentNormalizationFilter
    from .interpretation.text_run_refinement_filter import TextRunRefinementFilter
    from .recording.mouse_jitter_cleanup_filter import MouseJitterCleanupFilter
    from .shaping.mouse_smoothing_filter import MouseSmoothingFilter
    from .documents.preserve_document_filter import PreserveDocumentFilter
    from .interpretation.preserve_interpretation_filter import (
        PreserveInterpretationFilter,
    )
    from .recording.preserve_recording_filter import PreserveRecordingFilter
    from .shaping.preserve_shaping_filter import PreserveShapingFilter

    registry = FilterRegistry()
    registry.register_filter("mouse_jitter_cleanup", MouseJitterCleanupFilter())
    registry.register_filter("text_run_refinement", TextRunRefinementFilter())
    registry.register_filter("smooth_mouse", MouseSmoothingFilter())
    registry.register_filter("preserve_recording", PreserveRecordingFilter())
    registry.register_filter("preserve_interpretation", PreserveInterpretationFilter())
    registry.register_filter("preserve_shaping", PreserveShapingFilter())
    registry.register_filter("preserve_document", PreserveDocumentFilter())
    registry.register_filter("normalize_document", DocumentNormalizationFilter())

    registry.register_profile(
        FilterProfile(
            profile_id="mouse_jitter_cleanup",
            target_stage=FilterStage.RECORDING,
            enabled_filters=("mouse_jitter_cleanup",),
            settings={"move_distance_threshold_px": 1},
        )
    )
    registry.register_profile(
        FilterProfile(
            profile_id="text_run_refinement",
            target_stage=FilterStage.INTERPRETATION,
            enabled_filters=("text_run_refinement",),
        )
    )
    registry.register_profile(
        FilterProfile(
            profile_id="smooth_mouse",
            target_stage=FilterStage.SHAPING,
            enabled_filters=("smooth_mouse",),
            settings={"move_distance_threshold_px": 2},
        )
    )
    registry.register_profile(
        FilterProfile(
            profile_id="normalize_document",
            target_stage=FilterStage.DOCUMENT,
            enabled_filters=("normalize_document",),
            settings={
                "indent": "    ",
                "newline": "\n",
                "max_blank_lines": 1,
                "final_newline": True,
            },
        )
    )
    return registry
