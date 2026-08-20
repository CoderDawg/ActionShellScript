from __future__ import annotations

from typing import Protocol

from core.playback.playback_events import PlaybackEvent


class InputExecutor(Protocol):
    def execute(self, event: PlaybackEvent) -> None: ...
