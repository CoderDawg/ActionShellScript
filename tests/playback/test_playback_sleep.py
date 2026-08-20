from __future__ import annotations

import threading

from core.playback.playback_sleep import (
    sleep_ms_interruptibly,
    sleep_seconds_interruptibly,
)


def test_sleep_ms_interruptibly_uses_single_sleep_without_stop_event(monkeypatch) -> None:
    calls: list[float] = []

    assert sleep_ms_interruptibly(250, sleep_fn=lambda seconds: calls.append(seconds)) is False
    assert calls == [0.25]


def test_sleep_seconds_interruptibly_stops_after_first_chunk(monkeypatch) -> None:
    calls: list[float] = []
    stop_event = threading.Event()

    def fake_sleep(seconds: float) -> None:
        calls.append(seconds)
        stop_event.set()

    assert sleep_seconds_interruptibly(
        30.0,
        stop_event=stop_event,
        sleep_fn=fake_sleep,
    ) is True
    assert calls == [0.05]


def test_sleep_ms_interruptibly_honors_custom_chunk_size() -> None:
    calls: list[float] = []
    stop_event = threading.Event()

    assert sleep_ms_interruptibly(
        120,
        stop_event=stop_event,
        sleep_fn=lambda seconds: calls.append(seconds),
        chunk_ms=30,
    ) is False

    assert calls == [0.03, 0.03, 0.03, 0.03]
