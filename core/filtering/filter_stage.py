from __future__ import annotations

from enum import Enum


class FilterStage(str, Enum):
    RECORDING = "recording"
    INTERPRETATION = "interpretation"
    SHAPING = "shaping"
    DOCUMENT = "document"
