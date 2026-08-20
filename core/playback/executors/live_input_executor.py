from __future__ import annotations

import threading
from typing import Protocol

from core.playback.playback_events import PlaybackEvent
from core.playback.playback_sleep import sleep_ms_interruptibly
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("playback.live")


class PlaybackHost(Protocol):
    def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None: ...

    def mouse_down(self, button: str) -> None: ...

    def mouse_up(self, button: str) -> None: ...

    def mouse_click(self, button: str, clicks: int) -> None: ...

    def mouse_wheel(self, delta: int) -> None: ...

    def key_down(self, key: str) -> None: ...

    def key_up(self, key: str) -> None: ...

    def send_text(self, text: str) -> None: ...

    def sleep_ms(self, duration_ms: int) -> None: ...


class LiveInputExecutor:
    def __init__(
        self,
        host: PlaybackHost,
        *,
        mouse_settle_ms: int = 0,
        stop_event: threading.Event | None = None,
        sleep_chunk_ms: int = 50,
    ) -> None:
        self._host = host
        self._mouse_settle_ms = max(0, int(mouse_settle_ms))
        self._stop_event = stop_event
        self._sleep_chunk_ms = max(1, int(sleep_chunk_ms))

    def execute(self, event: PlaybackEvent) -> None:
        event_type = str(event.type).strip().lower()
        log.trace(
            "Dispatching playback event to live host",
            event_id="playback.live.event_dispatched",
            event_type=event_type or "<missing>",
            event=event,
        )

        if event_type == "delay":
            duration_ms = max(0, int(event.duration_ms))
            log.decision(
                "Dispatching delay event to live host",
                event_id="playback.live.delayed",
                duration_ms=duration_ms,
            )
            self._sleep_interruptibly(duration_ms)
            return

        if event_type == "mouse_move":
            x = int(event.x)
            y = int(event.y)
            speed = getattr(event, "speed", None)
            log.trace(
                "Live playback moving mouse",
                event_id="playback.live.mouse_move_executed",
                x=x,
                y=y,
                speed=speed,
            )
            self._host.move_mouse(x, y, speed=int(speed) if speed is not None else None)
            return

        if event_type == "mouse_down":
            x = int(event.x)
            y = int(event.y)
            button = str(event.button)
            log.trace(
                "Live playback pressing mouse button",
                event_id="playback.live.mouse_down_executed",
                x=x,
                y=y,
                button=button,
            )
            self._host.move_mouse(x, y)
            if self._mouse_settle_ms > 0:
                self._sleep_interruptibly(self._mouse_settle_ms)
            self._host.mouse_down(button)
            return

        if event_type == "mouse_up":
            x = int(event.x)
            y = int(event.y)
            button = str(event.button)
            log.trace(
                "Live playback releasing mouse button",
                event_id="playback.live.mouse_up_executed",
                x=x,
                y=y,
                button=button,
            )
            self._host.move_mouse(x, y)
            if self._mouse_settle_ms > 0:
                self._sleep_interruptibly(self._mouse_settle_ms)
            self._host.mouse_up(button)
            return

        if event_type == "mouse_click":
            x = int(event.x)
            y = int(event.y)
            button = str(event.button)
            clicks = max(1, int(event.clicks))
            speed = getattr(event, "speed", None)
            log.trace(
                "Live playback clicking mouse button",
                event_id="playback.live.mouse_click_executed",
                x=x,
                y=y,
                button=button,
                clicks=clicks,
                speed=speed,
            )
            self._host.move_mouse(x, y, speed=int(speed) if speed is not None else None)
            if self._mouse_settle_ms > 0:
                self._sleep_interruptibly(self._mouse_settle_ms)
            self._host.mouse_click(
                button,
                clicks,
            )
            return

        if event_type == "mouse_wheel":
            delta = int(event.delta)
            log.trace(
                "Live playback scrolling mouse wheel",
                event_id="playback.live.mouse_wheel_executed",
                delta=delta,
            )
            self._host.mouse_wheel(delta)
            return

        if event_type == "key_down":
            key = str(event.key)
            log.trace(
                "Live playback pressing key",
                event_id="playback.live.key_down_executed",
                key=key,
            )
            self._host.key_down(key)
            return

        if event_type == "key_up":
            key = str(event.key)
            log.trace(
                "Live playback releasing key",
                event_id="playback.live.key_up_executed",
                key=key,
            )
            self._host.key_up(key)
            return

        if event_type == "hotkey":
            keys = [str(key) for key in event.keys]
            if not keys:
                log.error(
                    "Rejected hotkey playback event without keys",
                    event_id="playback.live.hotkey_missing_keys",
                )
                raise RuntimeError("Playback hotkey event must include at least one key.")
            pressed_keys: list[str] = []
            log.decision(
                "Live playback dispatching hotkey chord",
                event_id="playback.live.hotkey_started",
                key_count=len(keys),
                keys=keys,
            )
            try:
                for key in keys:
                    log.trace(
                        "Live playback pressing hotkey key",
                        event_id="playback.live.hotkey_key_down",
                        key=key,
                    )
                    self._host.key_down(key)
                    pressed_keys.append(key)
                for key in reversed(keys):
                    log.trace(
                        "Live playback releasing hotkey key",
                        event_id="playback.live.hotkey_key_up",
                        key=key,
                    )
                    self._host.key_up(key)
                    pressed_keys.pop()
            except Exception as exc:
                log.exception(
                    "Hotkey dispatch failed; attempting to release pressed keys",
                    exc,
                    event_id="playback.live.hotkey_failed",
                    pressed_keys=list(pressed_keys),
                )
                for key in reversed(pressed_keys):
                    try:
                        self._host.key_up(key)
                    except Exception:
                        continue
                log.warning(
                    "Hotkey dispatch failed after partial key presses",
                    event_id="playback.live.hotkey_partial_failure",
                    pressed_keys=list(pressed_keys),
                )
                raise
            return

        if event_type == "text":
            text = str(event.text)
            log.trace(
                "Live playback typing text",
                event_id="playback.live.text_executed",
                text_length=len(text),
            )
            self._host.send_text(text)
            return

        log.error(
            "Unsupported playback event type for live executor",
            event_id="playback.live.unsupported",
            event_type=event_type or "<missing>",
        )
        raise RuntimeError(f"Unsupported playback event type: {event_type or '<missing>'}")

    def _sleep_interruptibly(self, duration_ms: int) -> None:
        if sleep_ms_interruptibly(
            duration_ms,
            stop_event=self._stop_event,
            sleep_fn=lambda seconds: self._host.sleep_ms(int(round(seconds * 1000))),
            chunk_ms=self._sleep_chunk_ms,
        ):
            raise RuntimeError("Playback stopped.")

