from __future__ import annotations

import pytest

from core.recording.recorder_config import RecorderConfig


def test_valid_defaults() -> None:
    config = RecorderConfig()

    assert config.capture_mouse_moves is True
    assert config.capture_mouse_buttons is True
    assert config.capture_mouse_wheel is True
    assert config.capture_keyboard is True
    assert config.mouse_move_threshold_px == 0
    assert config.excluded_window_hwnds == ()


def test_threshold_validation() -> None:
    with pytest.raises(ValueError, match="mouse_move_threshold_px must be >= 0."):
        RecorderConfig(mouse_move_threshold_px=-1)
