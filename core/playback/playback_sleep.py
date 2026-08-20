from __future__ import annotations

import time
import threading
from collections.abc import Callable


def sleep_seconds_interruptibly(
    duration_seconds: float,
    *,
    stop_event: threading.Event | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    chunk_seconds: float = 0.05,
) -> bool:
    remaining_seconds = max(0.0, float(duration_seconds))
    if remaining_seconds <= 0:
        return False

    if stop_event is None:
        sleep_fn(remaining_seconds)
        return False

    chunk_seconds = max(0.001, float(chunk_seconds))
    while remaining_seconds > 0:
        if stop_event.is_set():
            return True

        sleep_seconds = min(chunk_seconds, remaining_seconds)
        sleep_fn(sleep_seconds)
        remaining_seconds -= sleep_seconds

    return stop_event.is_set()


def sleep_ms_interruptibly(
    duration_ms: int,
    *,
    stop_event: threading.Event | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    chunk_ms: int = 50,
) -> bool:
    return sleep_seconds_interruptibly(
        max(0, int(duration_ms)) / 1000.0,
        stop_event=stop_event,
        sleep_fn=sleep_fn,
        chunk_seconds=max(1, int(chunk_ms)) / 1000.0,
    )
