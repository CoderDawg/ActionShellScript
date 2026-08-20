from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShapingConfig:
    emit_delays: bool = True
    min_delay_ms: int = 1
    max_delay_ms: int | None = None
    collapse_consecutive_delays: bool = True

    emit_mouse_moves: bool = True
    emit_only_click_positions: bool = False
    collapse_consecutive_mouse_moves: bool = True

    collapse_simple_click_sequences: bool = True
    click_collapse_distance_px: int = 3
    click_collapse_max_duration_ms: int = 250

    collapse_text_input: bool = True
    keyboard_output_style: str = "structured"

    def __post_init__(self) -> None:
        if self.min_delay_ms < 0:
            raise ValueError("min_delay_ms must be >= 0.")
        if self.max_delay_ms is not None and self.max_delay_ms < 0:
            raise ValueError("max_delay_ms must be >= 0 when provided.")
        if self.click_collapse_distance_px < 0:
            raise ValueError("click_collapse_distance_px must be >= 0.")
        if self.click_collapse_max_duration_ms < 0:
            raise ValueError("click_collapse_max_duration_ms must be >= 0.")
        if self.keyboard_output_style not in {"structured", "text"}:
            raise ValueError(
                "keyboard_output_style must be 'structured' or 'text'."
            )
