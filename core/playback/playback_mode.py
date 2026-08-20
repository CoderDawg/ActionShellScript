from __future__ import annotations

from enum import Enum


class PlaybackMode(str, Enum):
    LIVE = "live"
    PREVIEW = "preview"
