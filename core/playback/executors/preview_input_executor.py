from __future__ import annotations

from dataclasses import dataclass, field

from core.playback.playback_events import PlaybackEvent


@dataclass(slots=True)
class PreviewInputExecutor:
    executed_events: list[PlaybackEvent] = field(default_factory=list)

    def execute(self, event: PlaybackEvent) -> None:
        self.executed_events.append(event)
