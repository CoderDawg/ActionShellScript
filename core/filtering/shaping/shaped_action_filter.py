from __future__ import annotations

from typing import Protocol

from core.shaping.shaped_action_sequence import ShapedActionSequence

from ..filter_profile import FilterProfile


class ShapedActionFilter(Protocol):
    filter_id: str

    def apply(
        self,
        source: ShapedActionSequence,
        profile: FilterProfile,
    ) -> ShapedActionSequence: ...
