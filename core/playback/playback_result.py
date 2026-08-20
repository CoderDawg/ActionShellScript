from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True, slots=True)
class PlaybackResult:
    source_kind: str
    source_id: str
    executed_event_count: int
    success: bool
    delay_ms: int = 0
    playback_mode: str = ""
    sendkeys_transport: str = "text events"
    console_output: list[str] = field(default_factory=list)
    diagnostics_output: list[str] = field(default_factory=list)
    error_line: int | None = None
    error_message: str | None = None
