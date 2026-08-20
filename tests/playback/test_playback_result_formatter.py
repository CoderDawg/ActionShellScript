from __future__ import annotations

from core.playback.playback_result import PlaybackResult
from core.playback.playback_result_formatter import (
    format_playback_failure,
    playback_failure_fields,
)


def test_playback_failure_formatter_emits_consistent_text_and_fields() -> None:
    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=3,
        success=False,
        error_line=12,
        error_message="boom",
    )

    assert format_playback_failure(result) == [
        "Playback error line    : 12",
        "Playback error         : boom",
    ]
    assert playback_failure_fields(result) == {
        "error_line": 12,
        "error_message": "boom",
    }


def test_playback_failure_formatter_skips_empty_details() -> None:
    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=0,
        success=False,
    )

    assert format_playback_failure(result) == []
    assert playback_failure_fields(result) == {}
