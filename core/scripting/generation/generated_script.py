from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GeneratedScript:
    source_session_id: str
    source_action_count: int
    text: str

    def line_count(self) -> int:
        if not self.text:
            return 0
        return len(self.text.splitlines())
