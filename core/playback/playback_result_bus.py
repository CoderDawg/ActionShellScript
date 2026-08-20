from __future__ import annotations

import threading
from collections.abc import Callable

from core.playback.playback_result import PlaybackResult


_lock = threading.RLock()
_latest_result: PlaybackResult | None = None
_listeners: list[Callable[[PlaybackResult], None]] = []


def publish_playback_result(result: PlaybackResult) -> None:
    with _lock:
        global _latest_result
        _latest_result = result
        listeners = list(_listeners)

    for listener in listeners:
        try:
            listener(result)
        except Exception:
            continue


def subscribe_playback_result(
    listener: Callable[[PlaybackResult], None],
) -> Callable[[], None]:
    with _lock:
        _listeners.append(listener)
        latest_result = _latest_result

    if latest_result is not None:
        try:
            listener(latest_result)
        except Exception:
            pass

    def unsubscribe() -> None:
        with _lock:
            try:
                _listeners.remove(listener)
            except ValueError:
                pass

    return unsubscribe


def get_latest_playback_result() -> PlaybackResult | None:
    with _lock:
        return _latest_result


def reset_playback_result_bus() -> None:
    with _lock:
        global _latest_result
        _latest_result = None
        _listeners.clear()
