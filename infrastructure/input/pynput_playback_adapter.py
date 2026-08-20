from __future__ import annotations

import threading

from pynput import keyboard, mouse

from core.playback.playback_sleep import sleep_seconds_interruptibly
from infrastructure.debug_logger import get_diagnostic_logger
from infrastructure.input.mouse_movement_profile import MouseMovementProfile


log = get_diagnostic_logger("playback.pynput")


class PynputPlaybackAdapter:
    def __init__(
        self,
        *,
        mouse_movement_profile: MouseMovementProfile | None = None,
        stop_event: threading.Event | None = None,
        sleep_chunk_ms: int = 50,
    ) -> None:
        self._mouse = mouse.Controller()
        self._keyboard = keyboard.Controller()
        self._mouse_movement_profile = mouse_movement_profile or MouseMovementProfile()
        self._stop_event = stop_event
        self._sleep_chunk_ms = max(1, int(sleep_chunk_ms))

    def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
        target_x = int(x)
        target_y = int(y)
        speed_value = None if speed is None else max(0, min(100, int(speed)))
        log.trace(
            "Applying mouse move via pynput",
            event_id="playback.pynput.mouse_move",
            x=target_x,
            y=target_y,
            speed=speed_value,
        )
        if speed_value is None or speed_value <= 0:
            self._mouse.position = (target_x, target_y)
            return

        start_x, start_y = self._mouse.position
        distance = ((target_x - start_x) ** 2 + (target_y - start_y) ** 2) ** 0.5
        if distance <= 0:
            self._mouse.position = (target_x, target_y)
            return

        duration_ms = self._mouse_movement_profile.duration_ms_for_speed(speed_value)
        steps = self._mouse_movement_profile.steps_for_distance(distance)
        if duration_ms <= 0:
            self._mouse.position = (target_x, target_y)
            return

        step_delay = duration_ms / steps / 1000.0

        for index in range(1, steps + 1):
            fraction = index / steps
            current_x = int(round(start_x + (target_x - start_x) * fraction))
            current_y = int(round(start_y + (target_y - start_y) * fraction))
            self._mouse.position = (current_x, current_y)
            if index < steps:
                if sleep_seconds_interruptibly(
                    step_delay,
                    stop_event=self._stop_event,
                    chunk_seconds=self._sleep_chunk_ms / 1000.0,
                ):
                    raise RuntimeError("Playback stopped.")

    def mouse_down(self, button: str) -> None:
        resolved = self._resolve_button(button)
        log.trace(
            "Applying mouse press via pynput",
            event_id="playback.pynput.mouse_down",
            button=str(button),
        )
        self._mouse.press(resolved)

    def mouse_up(self, button: str) -> None:
        resolved = self._resolve_button(button)
        log.trace(
            "Applying mouse release via pynput",
            event_id="playback.pynput.mouse_up",
            button=str(button),
        )
        self._mouse.release(resolved)

    def mouse_click(self, button: str, clicks: int) -> None:
        resolved = self._resolve_button(button)
        for click_index in range(1, max(1, int(clicks)) + 1):
            log.trace(
                "Applying mouse click via pynput",
                event_id="playback.pynput.mouse_click",
                button=str(button),
                click_index=click_index,
            )
            self._mouse.press(resolved)
            self._mouse.release(resolved)

    def mouse_wheel(self, delta: int) -> None:
        log.trace(
            "Applying mouse wheel via pynput",
            event_id="playback.pynput.mouse_wheel",
            delta=int(delta),
        )
        self._mouse.scroll(0, int(delta))

    def key_down(self, key: str) -> None:
        resolved = self._resolve_key(key)
        log.trace(
            "Applying key press via pynput",
            event_id="playback.pynput.key_down",
            key=str(key),
        )
        self._keyboard.press(resolved)

    def key_up(self, key: str) -> None:
        resolved = self._resolve_key(key)
        log.trace(
            "Applying key release via pynput",
            event_id="playback.pynput.key_up",
            key=str(key),
        )
        self._keyboard.release(resolved)

    def send_text(self, text: str) -> None:
        log.trace(
            "Applying text input via pynput",
            event_id="playback.pynput.text",
            text_length=len(str(text)),
        )
        self._keyboard.type(str(text))

    def sleep_ms(self, duration_ms: int) -> None:
        log.trace(
            "Sleeping via pynput adapter",
            event_id="playback.pynput.sleep",
            duration_ms=max(0, int(duration_ms)),
        )
        if sleep_seconds_interruptibly(
            max(0, int(duration_ms)) / 1000.0,
            stop_event=self._stop_event,
            chunk_seconds=self._sleep_chunk_ms / 1000.0,
        ):
            raise RuntimeError("Playback stopped.")

    def _resolve_button(self, button: str) -> mouse.Button:
        normalized = str(button).strip().lower()
        mapping = {
            "left": mouse.Button.left,
            "right": mouse.Button.right,
            "middle": mouse.Button.middle,
        }
        if normalized not in mapping:
            raise RuntimeError(f"Unsupported mouse button: {button}")
        return mapping[normalized]

    def _resolve_key(
        self,
        key: str,
    ) -> keyboard.Key | str:
        raw_key = str(key).strip()
        if len(raw_key) == 1:
            return raw_key

        normalized = raw_key.lower()
        special_keys = {
            "alt": keyboard.Key.alt,
            "backspace": keyboard.Key.backspace,
            "capslock": keyboard.Key.caps_lock,
            "cmd": keyboard.Key.cmd,
            "ctrl": keyboard.Key.ctrl,
            "delete": keyboard.Key.delete,
            "down": keyboard.Key.down,
            "end": keyboard.Key.end,
            "enter": keyboard.Key.enter,
            "esc": keyboard.Key.esc,
            "escape": keyboard.Key.esc,
            "home": keyboard.Key.home,
            "insert": keyboard.Key.insert,
            "left": keyboard.Key.left,
            "pagedown": keyboard.Key.page_down,
            "pageup": keyboard.Key.page_up,
            "right": keyboard.Key.right,
            "shift": keyboard.Key.shift,
            "space": keyboard.Key.space,
            "tab": keyboard.Key.tab,
            "up": keyboard.Key.up,
        }
        if normalized in special_keys:
            return special_keys[normalized]
        if len(normalized) == 1:
            return normalized
        return normalized

