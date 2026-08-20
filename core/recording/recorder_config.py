# recording/core/recorder_config.py
"""
Recorder configuration.

Purpose:
    hold recording options only
    no runtime, UI, playback, or script concerns
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecorderConfig:
    capture_mouse_moves: bool = True
    capture_mouse_buttons: bool = True
    capture_mouse_wheel: bool = True
    capture_keyboard: bool = True

    mouse_move_threshold_px: int = 0
    excluded_window_hwnds: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.mouse_move_threshold_px < 0:
            raise ValueError("mouse_move_threshold_px must be >= 0.")
        normalized: list[int] = []
        for hwnd in self.excluded_window_hwnds:
            try:
                value = int(hwnd)
            except (TypeError, ValueError) as exc:
                raise ValueError("excluded_window_hwnds must contain integers.") from exc
            if value <= 0:
                continue
            if value not in normalized:
                normalized.append(value)
        object.__setattr__(self, "excluded_window_hwnds", tuple(normalized))
