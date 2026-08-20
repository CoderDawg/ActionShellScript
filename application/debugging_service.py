from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Callable

from editor.document.script_document import ScriptDocument

from core.debugging.debug_controller import DebugController
from core.debugging.debug_event import DebugEvent
from core.debugging.debug_request import DebugRequest
from core.debugging.debug_session import DebugSession
from core.debugging.runtime_debug_hooks import RuntimeDebugHooks
from core.runtime.script_runtime import ScriptRuntime
from apps.desktop.settings import DesktopPlaybackSettings
from apps.desktop.settings import DesktopRuntimeSettings


@dataclass(frozen=True, slots=True)
class DebugRunHandle:
    session: DebugSession
    runtime: ScriptRuntime
    controller: DebugController


class DebuggingService:
    def __init__(
        self,
        runtime_settings: DesktopRuntimeSettings | None = None,
        playback_settings: DesktopPlaybackSettings | None = None,
    ) -> None:
        self._runtime_settings = runtime_settings or DesktopRuntimeSettings()
        self._playback_settings = playback_settings or DesktopPlaybackSettings()

    def set_runtime_settings(self, runtime_settings: DesktopRuntimeSettings) -> None:
        self._runtime_settings = runtime_settings

    def set_playback_settings(self, playback_settings: DesktopPlaybackSettings) -> None:
        self._playback_settings = playback_settings

    def start_debug_session(
        self,
        document: ScriptDocument,
        request: DebugRequest,
        *,
        emit_event: Callable[[DebugEvent], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> DebugRunHandle:
        controller = DebugController(
            document=document,
            request=request,
            emit_event=emit_event,
        )
        hooks = RuntimeDebugHooks(
            source_map=controller.source_map,
            sink=controller,
        )
        runtime = ScriptRuntime(
            debugger=hooks,
            stop_event=stop_event,
            max_loop_iterations=self._runtime_settings.max_loop_iterations,
            max_call_depth=self._runtime_settings.max_call_depth,
            default_mouse_move_speed=self._runtime_settings.default_mouse_move_speed,
            special_values=self._playback_settings.runtime_special_values(),
        )
        controller.start()
        return DebugRunHandle(
            session=controller.session,
            runtime=runtime,
            controller=controller,
        )

    def run_debug_session(
        self,
        document: ScriptDocument,
        request: DebugRequest,
        *,
        emit_event: Callable[[DebugEvent], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> DebugRunHandle:
        handle = self.start_debug_session(
            document,
            request,
            emit_event=emit_event,
            stop_event=stop_event,
        )

        runtime_result: dict[str, object] = {}
        runtime_error: dict[str, BaseException] = {}

        def run_runtime() -> None:
            try:
                runtime_result["context"] = handle.runtime.compile(
                    document.text,
                    source_path=document.source_path,
                )
            except Exception as exc:  # pragma: no cover - surfaced below
                runtime_error["exc"] = exc

        worker = threading.Thread(target=run_runtime, daemon=True)
        worker.start()

        while worker.is_alive():
            if not handle.controller.wait_for_pause(timeout=0.1):
                continue

            snapshot = handle.controller.snapshot()
            if snapshot.state != "paused":
                continue

            if request.stop_mode == "step":
                handle.controller.resume_step()
            else:
                handle.controller.resume_continue()

        worker.join()

        if "exc" in runtime_error:
            raise runtime_error["exc"]

        if "context" in runtime_result:
            handle.controller.sync_from_context(runtime_result["context"])
        if handle.session.state not in {"completed", "failed"}:
            handle.controller.complete()
        return handle
