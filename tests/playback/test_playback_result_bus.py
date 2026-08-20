from __future__ import annotations

from core.playback.playback_result import PlaybackResult
from core.playback.playback_result_bus import (
    get_latest_playback_result,
    publish_playback_result,
    reset_playback_result_bus,
    subscribe_playback_result,
)


def test_playback_result_bus_replays_latest_result_to_late_subscribers() -> None:
    reset_playback_result_bus()
    try:
        result = PlaybackResult(
            source_kind="script_document",
            source_id="script-1",
            executed_event_count=2,
            success=False,
            error_line=8,
            error_message="boom",
        )

        publish_playback_result(result)
        assert get_latest_playback_result() == result

        received: list[PlaybackResult] = []
        unsubscribe = subscribe_playback_result(received.append)

        assert received == [result]

        next_result = PlaybackResult(
            source_kind="script_document",
            source_id="script-2",
            executed_event_count=3,
            success=True,
        )
        publish_playback_result(next_result)

        assert received == [result, next_result]
        unsubscribe()
    finally:
        reset_playback_result_bus()
