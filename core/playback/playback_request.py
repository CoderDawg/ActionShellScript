from __future__ import annotations

from dataclasses import dataclass

from .playback_mode import PlaybackMode


@dataclass(frozen=True, slots=True)
class PlaybackRequest:
    source_kind: str
    source_id: str
    mode: PlaybackMode = PlaybackMode.LIVE
    repeat_count: int = 1
    step_mode: bool = False
    delay_ms: int = 0
    sendkeys_transport: str = "text events"

    def __post_init__(self) -> None:
        if not str(self.source_kind).strip():
            raise ValueError("PlaybackRequest source_kind must not be empty.")
        if not str(self.source_id).strip():
            raise ValueError("PlaybackRequest source_id must not be empty.")
        if int(self.repeat_count) < 1:
            raise ValueError("PlaybackRequest repeat_count must be >= 1.")
        if int(self.delay_ms) < 0:
            raise ValueError("PlaybackRequest delay_ms must be >= 0.")
        if not str(self.sendkeys_transport).strip():
            raise ValueError("PlaybackRequest sendkeys_transport must not be empty.")
