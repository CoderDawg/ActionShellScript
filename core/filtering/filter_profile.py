from __future__ import annotations

from dataclasses import dataclass, field

from .filter_stage import FilterStage


@dataclass(frozen=True, slots=True)
class FilterProfile:
    profile_id: str
    target_stage: FilterStage
    enabled_filters: tuple[str, ...]
    settings: dict[str, object] = field(default_factory=dict)
