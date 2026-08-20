from __future__ import annotations

from core.playback.playback_result import PlaybackResult


def test_playback_result_tracks_mode_and_sendkeys_transport() -> None:
    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=4,
        success=True,
        playback_mode="preview",
        sendkeys_transport="key taps",
    )

    assert result.playback_mode == "preview"
    assert result.sendkeys_transport == "key taps"
