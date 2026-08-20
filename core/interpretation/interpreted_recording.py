from __future__ import annotations

from dataclasses import dataclass, field

from .event_vocabulary import InterpretedEvent


@dataclass(slots=True)
class InterpretedRecording:
    source_session_id: str
    source_event_count: int
    events: list[InterpretedEvent] = field(default_factory=list)

    def event_count(self) -> int:
        return len(self.events)
