from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterpretationConfig:
    click_max_move_distance_px: int = 4

    double_click_max_interval_ms: int = 500
    double_click_max_distance_px: int = 4
    double_click_max_pause_ms: int = 350
    double_click_max_inter_click_move_distance_px: int = 4

    drag_min_distance_px: int = 8
    drag_min_duration_ms: int = 0

    def __post_init__(self) -> None:
        numeric_fields = (
            self.click_max_move_distance_px,
            self.double_click_max_interval_ms,
            self.double_click_max_distance_px,
            self.double_click_max_pause_ms,
            self.double_click_max_inter_click_move_distance_px,
            self.drag_min_distance_px,
            self.drag_min_duration_ms,
        )
        if any(value < 0 for value in numeric_fields):
            raise ValueError("Interpretation thresholds must be >= 0.")
