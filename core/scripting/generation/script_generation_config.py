from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScriptGenerationConfig:
    include_header_comments: bool = True
    include_source_summary: bool = True
    line_ending: str = "\n"

    emit_delays: bool = True
    emit_metadata_comments: bool = False
