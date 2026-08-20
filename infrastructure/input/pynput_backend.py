# infrastructure/input/pynput_backend.py
from __future__ import annotations

import contextlib
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QPoint
from pynput import keyboard, mouse

from core.recording.input_capture import RawEventHandler
from core.recording.recorder_config import RecorderConfig
from apps.desktop.hotkeys import split_hotkey_clauses
from infrastructure.debug_logger import get_diagnostic_logger
from infrastructure.input.window_exclusion import (
    active_window_is_excluded,
    point_hits_excluded_window,
)


log = get_diagnostic_logger("recording.pynput")


def _install_macos_listener_keycode_context_workaround() -> bool:
    if sys.platform != "darwin":
        return False

    listener_type = getattr(keyboard, "Listener", None)
    if getattr(listener_type, "__module__", None) != "pynput.keyboard._darwin":
        return False

    keyboard_darwin_module = sys.modules.get("pynput.keyboard._darwin")
    if keyboard_darwin_module is None:
        return False
    if getattr(
        keyboard_darwin_module,
        "_actionshellscript_listener_keycode_context_workaround",
        False,
    ):
        return False

    original_context = getattr(keyboard_darwin_module, "keycode_context", None)
    if original_context is None:
        return False

    @contextlib.contextmanager
    def listener_keycode_context():
        yield (None, None)

    setattr(
        keyboard_darwin_module,
        "_actionshellscript_original_keycode_context",
        original_context,
    )
    setattr(keyboard_darwin_module, "keycode_context", listener_keycode_context)
    setattr(
        keyboard_darwin_module,
        "_actionshellscript_listener_keycode_context_workaround",
        True,
    )
    return True


@dataclass(slots=True)
class PynputCaptureBackend:
    config: RecorderConfig
    suppress: bool = False
    stop_hotkey: str = "Shift+Esc"
    on_stop_requested: Callable[[], None] | None = None
    debug_stop_hotkey: bool = False

    _mouse_listener: mouse.Listener | None = field(default=None, init=False)
    _keyboard_listener: keyboard.Listener | None = field(default=None, init=False)
    _on_event: RawEventHandler | None = field(default=None, init=False)
    _started: bool = field(default=False, init=False)
    _base_time_ns: int = field(default=0, init=False)
    _last_mouse_pos: tuple[int, int] | None = field(default=None, init=False)
    _hotkey_parts: tuple[frozenset[str], ...] = field(default_factory=tuple, init=False)
    _pressed_hotkey_keys: set[str] = field(default_factory=set, init=False)
    _stop_hotkey_active: bool = field(default=False, init=False)
    _pending_hotkey_events: list[dict[str, object]] = field(default_factory=list, init=False)

    def start(self, on_event: RawEventHandler) -> None:
        if self._started:
            log.warning(
                "Capture backend start rejected because it is already running",
                event_id="recording.pynput.start_already_running",
                suppress=self.suppress,
                stop_hotkey=self.stop_hotkey,
            )
            raise RuntimeError("Capture backend is already running.")

        self._on_event = on_event
        self._base_time_ns = time.perf_counter_ns()
        self._last_mouse_pos = None
        self._hotkey_parts = self._parse_hotkey(self.stop_hotkey)
        self._pressed_hotkey_keys.clear()
        self._stop_hotkey_active = False
        self._pending_hotkey_events.clear()
        log.info(
            "Capture backend start requested",
            event_id="recording.pynput.start_started",
            suppress=self.suppress,
            stop_hotkey=self.stop_hotkey,
            normalized_stop_hotkey=[sorted(hotkey) for hotkey in self._hotkey_parts],
            capture_mouse_moves=self.config.capture_mouse_moves,
            capture_mouse_buttons=self.config.capture_mouse_buttons,
            capture_mouse_wheel=self.config.capture_mouse_wheel,
            capture_keyboard=self.config.capture_keyboard,
            mouse_move_threshold_px=self.config.mouse_move_threshold_px,
            debug_stop_hotkey=self.debug_stop_hotkey,
        )

        try:
            if _install_macos_listener_keycode_context_workaround():
                log.info(
                    "Installed macOS keyboard listener context workaround",
                    event_id="recording.pynput.macos_keycode_context_workaround",
                )

            mouse_listener = self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll,
                suppress=self.suppress,
            )
            keyboard_listener = self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=self.suppress,
            )

            mouse_listener.start()
            keyboard_listener.start()
            self._started = True
            log.info(
                "Capture backend listeners ready",
                event_id="recording.pynput.listeners_ready",
            )
            mouse_listener.wait()
            keyboard_listener.wait()
        except Exception as exc:
            log.exception(
                "Capture backend failed during startup",
                exc,
                event_id="recording.pynput.start_failed",
                suppress=self.suppress,
                stop_hotkey=self.stop_hotkey,
            )
            self._started = False
            raise

    def stop(self) -> None:
        log.info(
            "Capture backend stop requested",
            event_id="recording.pynput.stop_requested",
            started=self._started,
            stop_hotkey=self.stop_hotkey,
        )
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        log.info(
            "Capture backend listeners stopped",
            event_id="recording.pynput.listeners_stopped",
            stopped=self._started,
        )
        self._on_event = None
        self._started = False
        self._last_mouse_pos = None
        self._hotkey_parts = tuple()
        self._pressed_hotkey_keys.clear()
        self._stop_hotkey_active = False
        self._pending_hotkey_events.clear()
        log.info(
            "Capture backend stop completed",
            event_id="recording.pynput.stop_completed",
        )

    def _emit(self, event: dict[str, object]) -> None:
        log.trace(
            "Captured raw event emitted to recorder",
            event_id="recording.pynput.raw_event_emitted",
            event_type=event.get("type"),
            timestamp_ms=event.get("timestamp_ms"),
            event=event,
        )
        if self._on_event is not None:
            self._on_event(event)

    def _timestamp_ms(self) -> int:
        return (time.perf_counter_ns() - self._base_time_ns) // 1_000_000

    def _on_mouse_move(self, x: int, y: int) -> None:
        if point_hits_excluded_window(
            QPoint(int(x), int(y)),
            self.config.excluded_window_hwnds,
        ):
            log.trace(
                "Ignored mouse move because it targeted an excluded window",
                event_id="recording.pynput.mouse_move_excluded",
                excluded_window_hwnds=list(self.config.excluded_window_hwnds),
                x=int(x),
                y=int(y),
            )
            return

        if not self.config.capture_mouse_moves:
            log.trace(
                "Ignored mouse move because capture is disabled",
                event_id="recording.pynput.mouse_move_ignored",
                capture_mouse_moves=False,
            )
            return

        point = (int(x), int(y))
        threshold = self.config.mouse_move_threshold_px

        if self._last_mouse_pos is not None and threshold > 0:
            last_x, last_y = self._last_mouse_pos
            if abs(point[0] - last_x) < threshold and abs(point[1] - last_y) < threshold:
                log.decision(
                    "Suppressed mouse move because it fell below the configured threshold",
                    event_id="recording.pynput.mouse_move_suppressed",
                    x=point[0],
                    y=point[1],
                    last_x=last_x,
                    last_y=last_y,
                    threshold_px=threshold,
                )
                return

        self._last_mouse_pos = point
        event = {
            "type": "mouse_move",
            "x": point[0],
            "y": point[1],
            "timestamp_ms": self._timestamp_ms(),
        }
        log.trace(
            "Captured mouse move",
            event_id="recording.pynput.mouse_move",
            x=point[0],
            y=point[1],
            threshold_px=threshold,
        )
        self._emit(event)

    def _on_mouse_click(
        self,
        x: int,
        y: int,
        button: mouse.Button,
        pressed: bool,
    ) -> None:
        if point_hits_excluded_window(
            QPoint(int(x), int(y)),
            self.config.excluded_window_hwnds,
        ):
            log.trace(
                "Ignored mouse click because it targeted an excluded window",
                event_id="recording.pynput.mouse_button_excluded",
                excluded_window_hwnds=list(self.config.excluded_window_hwnds),
                button=self._mouse_button_name(button),
                pressed=pressed,
                x=int(x),
                y=int(y),
            )
            return

        if not self.config.capture_mouse_buttons:
            log.trace(
                "Ignored mouse click because capture is disabled",
                event_id="recording.pynput.mouse_button_ignored",
                capture_mouse_buttons=False,
            )
            return

        event = {
            "type": "mouse_down" if pressed else "mouse_up",
            "button": self._mouse_button_name(button),
            "x": int(x),
            "y": int(y),
            "timestamp_ms": self._timestamp_ms(),
        }
        log.trace(
            "Captured mouse button transition",
            event_id="recording.pynput.mouse_button",
            pressed=pressed,
            button=event["button"],
            x=event["x"],
            y=event["y"],
        )
        self._emit(event)

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if point_hits_excluded_window(
            QPoint(int(x), int(y)),
            self.config.excluded_window_hwnds,
        ):
            log.trace(
                "Ignored mouse wheel because it targeted an excluded window",
                event_id="recording.pynput.mouse_wheel_excluded",
                excluded_window_hwnds=list(self.config.excluded_window_hwnds),
                x=int(x),
                y=int(y),
                dx=int(dx),
                dy=int(dy),
            )
            return

        if not self.config.capture_mouse_wheel:
            log.trace(
                "Ignored mouse wheel because capture is disabled",
                event_id="recording.pynput.mouse_wheel_ignored",
                capture_mouse_wheel=False,
            )
            return

        event = {
            "type": "mouse_wheel",
            "x": int(x),
            "y": int(y),
            "dx": int(dx),
            "dy": int(dy),
            "delta": int(dy),
            "timestamp_ms": self._timestamp_ms(),
        }
        log.trace(
            "Captured mouse wheel event",
            event_id="recording.pynput.mouse_wheel",
            x=event["x"],
            y=event["y"],
            delta=event["delta"],
        )
        self._emit(event)

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        hotkey_name = self._hotkey_key_name(key)
        if hotkey_name is not None:
            self._pressed_hotkey_keys.add(hotkey_name)
            self._debug_stop_hotkey_event(
                "press",
                raw=self._describe_key(key),
                normalized=hotkey_name,
                pressed=sorted(self._pressed_hotkey_keys),
                target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                subset_matched=self._hotkey_subset_matched(),
                already_active=self._stop_hotkey_active,
            )
            self._maybe_trigger_stop_hotkey(
                action="press",
                key=key,
                normalized=hotkey_name,
            )
        else:
            self._debug_stop_hotkey_event(
                "press-ignored",
                raw=self._describe_key(key),
                normalized=None,
                pressed=sorted(self._pressed_hotkey_keys),
                target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                subset_matched=self._hotkey_subset_matched(),
                already_active=self._stop_hotkey_active,
            )

        if active_window_is_excluded(self.config.excluded_window_hwnds):
            log.trace(
                "Ignored key press because the active window is excluded",
                event_id="recording.pynput.key_press_excluded",
                excluded_window_hwnds=list(self.config.excluded_window_hwnds),
                key=self._key_name(key),
            )
            self._pending_hotkey_events.clear()
            return

        key_name = self._key_name(key)

        if not self.config.capture_keyboard:
            log.trace(
                "Ignored key press because capture is disabled",
                event_id="recording.pynput.key_press_ignored",
                capture_keyboard=False,
                key=key_name,
            )
            return

        event = {
            "type": "key_down",
            "key": key_name,
            "timestamp_ms": self._timestamp_ms(),
        }
        if hotkey_name is not None and any(hotkey_name in hotkey for hotkey in self._hotkey_parts):
            log.decision(
                "Buffered key press because it is part of the stop hotkey",
                event_id="recording.pynput.key_press_buffered",
                key=key_name,
                hotkey_name=hotkey_name,
                stop_hotkey=self.stop_hotkey,
            )
            self._pending_hotkey_events.append(event)
            return

        self._flush_pending_hotkey_events()
        log.trace(
            "Captured key press",
            event_id="recording.pynput.key_press",
            key=key_name,
        )
        self._emit(event)

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        hotkey_name = self._hotkey_key_name(key)
        if hotkey_name is not None:
            if hotkey_name not in self._pressed_hotkey_keys:
                self._pressed_hotkey_keys.add(hotkey_name)
                self._debug_stop_hotkey_event(
                    "release-recovered",
                    raw=self._describe_key(key),
                    normalized=hotkey_name,
                    pressed=sorted(self._pressed_hotkey_keys),
                    target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                    subset_matched=self._hotkey_subset_matched(),
                    already_active=self._stop_hotkey_active,
                )
            self._maybe_trigger_stop_hotkey(
                action="release",
                key=key,
                normalized=hotkey_name,
            )
            self._pressed_hotkey_keys.discard(hotkey_name)
            if self._matched_hotkey() is None:
                self._stop_hotkey_active = False
            self._debug_stop_hotkey_event(
                "release",
                raw=self._describe_key(key),
                normalized=hotkey_name,
                pressed=sorted(self._pressed_hotkey_keys),
                target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                subset_matched=self._hotkey_subset_matched(),
                already_active=self._stop_hotkey_active,
            )
        else:
            self._debug_stop_hotkey_event(
                "release-ignored",
                raw=self._describe_key(key),
                normalized=None,
                pressed=sorted(self._pressed_hotkey_keys),
                target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                subset_matched=self._hotkey_subset_matched(),
                already_active=self._stop_hotkey_active,
            )

        if active_window_is_excluded(self.config.excluded_window_hwnds):
            log.trace(
                "Ignored key release because the active window is excluded",
                event_id="recording.pynput.key_release_excluded",
                excluded_window_hwnds=list(self.config.excluded_window_hwnds),
                key=self._key_name(key),
            )
            self._pending_hotkey_events.clear()
            return

        key_name = self._key_name(key)

        if not self.config.capture_keyboard:
            log.trace(
                "Ignored key release because capture is disabled",
                event_id="recording.pynput.key_release_ignored",
                capture_keyboard=False,
                key=key_name,
            )
            return

        if hotkey_name is not None and any(hotkey_name in hotkey for hotkey in self._hotkey_parts):
            if self._stop_hotkey_active:
                if not self._pressed_hotkey_keys:
                    self._pending_hotkey_events.clear()
                    log.decision(
                        "Cleared pending hotkey events after stop hotkey completed",
                        event_id="recording.pynput.hotkey_pending_cleared",
                        stop_hotkey=self.stop_hotkey,
                    )
                return

            self._flush_pending_hotkey_events()
            event = {
                "type": "key_up",
                "key": key_name,
                "timestamp_ms": self._timestamp_ms(),
            }
            log.trace(
                "Captured hotkey key release as keyboard input",
                event_id="recording.pynput.hotkey_release",
                key=key_name,
            )
            self._emit(event)
            return

        self._flush_pending_hotkey_events()
        event = {
            "type": "key_up",
            "key": key_name,
            "timestamp_ms": self._timestamp_ms(),
        }
        log.trace(
            "Captured key release",
            event_id="recording.pynput.key_release",
            key=key_name,
        )
        self._emit(event)

    @classmethod
    def _parse_hotkey(cls, hotkey: str) -> tuple[frozenset[str], ...]:
        clauses: list[frozenset[str]] = []
        for clause in split_hotkey_clauses(hotkey):
            parts = [cls._normalize_hotkey_part(part) for part in clause.split("+")]
            filtered = [part for part in parts if part]
            if filtered:
                clauses.append(frozenset(filtered))

        if not clauses:
            raise ValueError("stop_hotkey must contain at least one key.")

        return tuple(clauses)

    def _handle_stop_hotkey(self) -> None:
        log.decision(
            "Stop hotkey callback triggered",
            event_id="recording.pynput.stop_hotkey_callback",
            pressed=sorted(self._pressed_hotkey_keys),
            normalized_stop_hotkey=[sorted(hotkey) for hotkey in self._hotkey_parts],
        )
        if self.on_stop_requested is not None:
            self.on_stop_requested()

    def _maybe_trigger_stop_hotkey(
        self,
        *,
        action: str,
        key: keyboard.Key | keyboard.KeyCode | None,
        normalized: str,
    ) -> None:
        hotkey_subset_matched = self._hotkey_subset_matched()
        if (
            self._hotkey_parts
            and hotkey_subset_matched
            and not self._stop_hotkey_active
        ):
            self._stop_hotkey_active = True
            self._debug_stop_hotkey_event(
                "match",
                event_action=action,
                raw=self._describe_key(key),
                normalized=normalized,
                pressed=sorted(self._pressed_hotkey_keys),
                target=[sorted(hotkey) for hotkey in self._hotkey_parts],
                subset_matched=hotkey_subset_matched,
                already_active=self._stop_hotkey_active,
            )
            self._handle_stop_hotkey()

    def _flush_pending_hotkey_events(self) -> None:
        if not self._pending_hotkey_events:
            return

        for event in self._pending_hotkey_events:
            self._emit(event)
        self._pending_hotkey_events.clear()

    def _hotkey_subset_matched(self) -> bool:
        return self._matched_hotkey() is not None

    def _matched_hotkey(self) -> frozenset[str] | None:
        for hotkey in self._hotkey_parts:
            if hotkey and all(part in self._pressed_hotkey_keys for part in hotkey):
                return hotkey
        return None

    def _debug_stop_hotkey_event(
        self,
        action: str,
        *,
        raw: str,
        normalized: str | None,
        pressed: list[str],
        target: list[list[str]],
        subset_matched: bool,
        already_active: bool,
        event_action: str | None = None,
    ) -> None:
        if not self.debug_stop_hotkey:
            return

        log.trace(
            f"Stop-hotkey {action}",
            event_id="recording.pynput.stop_hotkey_detail",
            action=action,
            raw=raw,
            normalized=normalized,
            pressed=pressed,
            target=target,
            subset_matched=subset_matched,
            already_active=already_active,
            event_action=event_action,
        )

    @staticmethod
    def _describe_key(key: keyboard.Key | keyboard.KeyCode | None) -> str:
        if key is None:
            return "None"

        char = getattr(key, "char", None)
        vk = getattr(key, "vk", None)
        name = getattr(key, "name", None)
        return f"type={type(key).__name__} value={key!r} char={char!r} vk={vk!r} name={name!r}"

    @staticmethod
    def _hotkey_key_name(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
        if key is None:
            return None

        if key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
            return "ctrl"
        if key in {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}:
            return "shift"
        if key in {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r}:
            return "alt"
        if key in {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r}:
            return "cmd"

        char = getattr(key, "char", None)
        if isinstance(char, str) and char:
            if char.isprintable():
                return char.lower()

        vk = getattr(key, "vk", None)
        if isinstance(vk, int) and 32 <= vk <= 126:
            return chr(vk).lower()

        name = getattr(key, "name", None)
        if isinstance(name, str) and name:
            return name.lower()

        return None

    @staticmethod
    def _normalize_hotkey_part(part: str) -> str:
        normalized = part.strip().lower().replace(" ", "")
        aliases = {
            "control": "ctrl",
            "ctrl_l": "ctrl",
            "ctrl_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "alt_l": "alt",
            "alt_r": "alt",
            "cmd": "cmd",
            "command": "cmd",
            "super": "cmd",
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _mouse_button_name(button: mouse.Button) -> str:
        mapping = {
            mouse.Button.left: "left",
            mouse.Button.right: "right",
            mouse.Button.middle: "middle",
        }
        return mapping.get(button, str(button).split(".")[-1].lower())

    @staticmethod
    def _key_name(key: keyboard.Key | keyboard.KeyCode | None) -> str:
        if key is None:
            return "unknown"

        char = getattr(key, "char", None)
        if isinstance(char, str) and char:
            if char.isprintable():
                return char.lower()

        vk = getattr(key, "vk", None)
        if isinstance(vk, int) and 32 <= vk <= 126:
            return chr(vk).lower()

        name = getattr(key, "name", None)
        if isinstance(name, str) and name:
            lowered = name.lower()
            if lowered.startswith("ctrl"):
                return "ctrl"
            if lowered.startswith("shift"):
                return "shift"
            if lowered.startswith("alt"):
                return "alt"
            if lowered in {"cmd", "cmd_l", "cmd_r"}:
                return "cmd"
            return lowered

        return str(key).replace("Key.", "").replace("'", "").lower()
