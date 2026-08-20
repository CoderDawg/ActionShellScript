from __future__ import annotations

from dataclasses import dataclass, field
from core.playback.playback_events import PlaybackEvent


@dataclass(slots=True)
class PlaybackPlan:
    source_kind: str
    source_id: str
    event_count: int
    delay_ms_override: int | None = None
    events: list[PlaybackEvent] = field(default_factory=list)
    event_source_lines: list[int | None] = field(default_factory=list)
    console_output: list[str] = field(default_factory=list)
    diagnostics_output: list[str] = field(default_factory=list)
