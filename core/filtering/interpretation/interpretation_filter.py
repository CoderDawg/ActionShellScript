from __future__ import annotations

from typing import Protocol

from core.interpretation.interpreted_recording import InterpretedRecording

from ..filter_profile import FilterProfile


class InterpretationFilter(Protocol):
    filter_id: str

    def apply(
        self,
        source: InterpretedRecording,
        profile: FilterProfile,
    ) -> InterpretedRecording: ...
