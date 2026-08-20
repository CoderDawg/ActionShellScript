from __future__ import annotations

"""
Desktop script actions are UI entry points into the application workflow.

This controller must treat playback as a derived execution step from the current
authoritative source. It must not redefine workflow validity based on whether a
plan contains executable playback events.

Required behavior:
- Build a playback plan from the current authoritative source.
- Allow plans with zero executable events if they still carry valid derived
  output such as console_output.
- Start playback only after plan construction succeeds.
- Surface build or playback failures to the UI.
- Forward derived console output to the desktop UI when available.
- Let diagnostics-stream output flow through the shared diagnostics logger
  surfaces instead of the playback transcript.

Non-goals:
- Do not treat event_count == 0 as an automatic error.
- Do not use the controller to decide whether a script is "valid" in the
  architectural sense.
- Do not silently discard derived output produced during playback planning or
  execution.

The controller consumes services and artifacts. It does not own workflow
semantics.
"""

import threading
import uuid

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QMessageBox

from application.playback_service import PlaybackService
from application.recording_service import RecordingService
from core.playback.executors.live_input_executor import LiveInputExecutor
from core.playback.executors.preview_input_executor import PreviewInputExecutor
from core.playback.playback_builder import PlaybackBuilder
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from core.playback.playback_engine import PlaybackEngine
from core.playback.playback_mode import PlaybackMode
from core.playback.playback_request import PlaybackRequest
from core.recording.input_capture import InputCapture
from core.recording.recorder_config import RecorderConfig
from core.recording.recording_session import RecordingSession
from core.recording.session_recorder import SessionRecorder
from core.runtime.script_runtime import ScriptRuntime
from editor.document.script_document import ScriptDocument
from infrastructure.debug_logger import get_diagnostic_logger
from infrastructure.input.window_exclusion import normalize_window_handles
from infrastructure.input.pynput_backend import PynputCaptureBackend
from infrastructure.input.pynput_playback_adapter import PynputPlaybackAdapter
from apps.desktop.runtime_host_services import (
    DesktopRuntimeHostServices,
    DesktopRuntimeCursorPosService,
    DesktopRuntimeMonitorInfoService,
    DesktopRuntimeKeyboardToggleService,
    DesktopRuntimeWindowRectService,
    DesktopRuntimeWindowPlacementService,
    DesktopRuntimeScreenSamplingService,
)
from apps.desktop.settings import (
    DesktopPlaybackSettings,
    DesktopRecordingSettings,
    DesktopRuntimeSettings,
)

log = get_diagnostic_logger("desktop.script_action_controller")


class _StoppablePlaybackExecutor:
    def __init__(self, executor, stop_event: threading.Event) -> None:
        self._executor = executor
        self._stop_event = stop_event

    def execute(self, event) -> None:
        if self._stop_event.is_set():
            raise RuntimeError("Playback stopped.")
        self._executor.execute(event)
        if self._stop_event.is_set():
            raise RuntimeError("Playback stopped.")


class _UnavailableLiveExecutor:
    def execute(self, event) -> None:
        raise RuntimeError(
            "Live playback executor is unavailable for preview playback."
        )


class DesktopScriptActionController(QObject):
    playbackResultReady = Signal(object)
    recordingResultReady = Signal(object)
    statusChanged = Signal(str)
    busyChanged = Signal(bool)
    errorOccurred = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._script_operation_kind: str | None = None
        self._script_operation_mode: PlaybackMode | None = None
        self._script_operation_thread: threading.Thread | None = None
        self._script_operation_stop_event: threading.Event | None = None
        self._script_operation_result: object | None = None
        self._script_operation_error: BaseException | None = None
        self._recording_service: RecordingService | None = None
        self._recording_stop_event: threading.Event | None = None
        self._recording_stop_requested = False
        self._recording_stop_lock = threading.Lock()
        self._recording_stop_finalized = False
        self._playback_settings = DesktopPlaybackSettings()
        self._recording_settings = DesktopRecordingSettings()
        self._runtime_settings = DesktopRuntimeSettings()
        self._playback_stop_hotkey = ""
        self._playback_stop_hotkey_backend: PynputCaptureBackend | None = None
        self._playback_stop_hotkey_thread: threading.Thread | None = None
        self._screen_sampling_service = DesktopRuntimeScreenSamplingService()
        self._keyboard_toggle_service = DesktopRuntimeKeyboardToggleService()
        self._cursor_pos_service = DesktopRuntimeCursorPosService()
        self._window_rect_service = DesktopRuntimeWindowRectService()
        self._window_placement_service = DesktopRuntimeWindowPlacementService()
        self._runtime_host_services = DesktopRuntimeHostServices(
            controller=self,
            cursor_pos_service=self._cursor_pos_service,
            window_rect_service=self._window_rect_service,
            window_placement_service=self._window_placement_service,
            screen_sampling_service=self._screen_sampling_service,
            keyboard_toggle_service=self._keyboard_toggle_service,
            monitor_info_service=DesktopRuntimeMonitorInfoService(),
        )
        self._script_operation_timer = QTimer(self)
        self._script_operation_timer.setInterval(100)
        self._script_operation_timer.timeout.connect(self._poll_script_operation)

    @property
    def is_active(self) -> bool:
        return self._script_operation_kind is not None

    @property
    def current_operation_kind(self) -> str | None:
        return self._script_operation_kind

    def set_playback_settings(self, settings: DesktopPlaybackSettings) -> None:
        self._playback_settings = settings

    def set_recording_settings(self, settings: DesktopRecordingSettings) -> None:
        self._recording_settings = settings

    def set_runtime_settings(self, settings: DesktopRuntimeSettings) -> None:
        self._runtime_settings = settings

    def set_playback_stop_hotkey(self, hotkey: str) -> None:
        self._playback_stop_hotkey = str(hotkey).strip()

    def play(
        self,
        document: ScriptDocument,
        *,
        mode: PlaybackMode = PlaybackMode.LIVE,
    ) -> bool:
        if self._script_operation_kind is not None:
            self.statusChanged.emit("Another script operation is already running")
            return False

        try:
            document_snapshot = ScriptDocument(
                document_id=document.document_id,
                text=document.text,
                version=document.version,
                is_dirty=document.is_dirty,
                last_saved_version=document.last_saved_version,
                source_session_id=document.source_session_id,
                source_action_count=document.source_action_count,
                generated_from_recording=document.generated_from_recording,
                recording_conversion_route=document.recording_conversion_route,
                source_capture_excluded_main_window=(
                    document.source_capture_excluded_main_window
                ),
                source_path=document.source_path,
            )
            stop_event = threading.Event()
            service = self._build_playback_service(stop_event, mode=mode)
            plan = service.build_plan_from_script(document_snapshot)
            request = PlaybackRequest(
                source_kind="script_document",
                source_id=document_snapshot.document_id,
                mode=mode,
                repeat_count=self._playback_settings.repeat_count,
                step_mode=self._playback_settings.step_mode,
                delay_ms=(
                    plan.delay_ms_override
                    if plan.delay_ms_override is not None
                    else self._playback_settings.delay_ms
                ),
                sendkeys_transport=(
                    "key taps"
                    if self._playback_settings.send_key_taps_instead_of_text
                    else "text events"
                ),
            )
        except BaseException as exc:
            self.errorOccurred.emit("Script Play Failed", str(exc))
            self.statusChanged.emit("Script play failed")
            return False

        def worker() -> None:
            try:
                self._script_operation_result = service.play_plan(plan, request)
            except BaseException as exc:  # pragma: no cover - surfaced by polling
                self._script_operation_error = exc

        thread = threading.Thread(target=worker, daemon=True)
        self._begin_script_operation(
            "play",
            thread=thread,
            stop_event=stop_event,
            mode=mode,
        )
        self._start_playback_stop_hotkey_listener(stop_event)
        thread.start()
        self.statusChanged.emit(f"{self._playback_status_label(mode, started=True)} ({plan.event_count} events)")
        return True

    def record(self) -> bool:
        if self._script_operation_kind is not None:
            self.statusChanged.emit("Another script operation is already running")
            return False

        recording_stop_event = threading.Event()
        self._recording_stop_event = recording_stop_event
        service = self._build_recording_service()
        session_id = str(uuid.uuid4())

        def worker() -> None:
            try:
                session = service.start_recording(session_id=session_id)
                is_recording = getattr(service, "is_recording", None)
                stop_recording = getattr(service, "stop_recording", None)
                if callable(is_recording) and callable(stop_recording):
                    while is_recording() and not recording_stop_event.is_set():
                        recording_stop_event.wait(0.05)

                    if is_recording():
                        stopped_session = self._stop_recording_once()
                        if stopped_session is not None:
                            session = stopped_session

                if self._script_operation_result is None:
                    self._script_operation_result = session
            except BaseException as exc:  # pragma: no cover - surfaced by polling
                self._script_operation_error = exc

        thread = threading.Thread(target=worker, daemon=True)
        self._begin_script_operation("record", thread=thread, recording_service=service)
        thread.start()
        recording_status_hint = self._recording_status_hint()
        if recording_status_hint is None:
            self.statusChanged.emit("Recording started")
        else:
            self.statusChanged.emit(f"Recording started ({recording_status_hint})")
        return True

    def stop(self) -> bool:
        kind = self._script_operation_kind
        if kind is None:
            self.statusChanged.emit("No script operation is active")
            return False

        if kind == "play":
            if self._script_operation_stop_event is not None:
                self._script_operation_stop_event.set()
            self._stop_playback_stop_hotkey_listener()
            self.statusChanged.emit("Stopping script play")
            return True

        if kind == "record":
            self._recording_stop_requested = True
            if self._recording_stop_event is not None:
                self._recording_stop_event.set()
            self.statusChanged.emit("Stopping recording")
            self._poll_script_operation()
            return True

        return False

    def _build_playback_service(
        self,
        stop_event: threading.Event,
        *,
        mode: PlaybackMode,
    ) -> PlaybackService:
        runtime = ScriptRuntime(
            max_loop_iterations=self._runtime_settings.max_loop_iterations,
            max_call_depth=self._runtime_settings.max_call_depth,
            default_mouse_move_speed=self._runtime_settings.default_mouse_move_speed,
            default_current_event_delay_ms=self._playback_settings.delay_ms,
            special_values=self._playback_settings.runtime_special_values(),
            host_services=self._build_runtime_host_services(),
        )
        if mode == PlaybackMode.LIVE:
            live_executor = _StoppablePlaybackExecutor(
                LiveInputExecutor(
                    PynputPlaybackAdapter(
                        mouse_movement_profile=self._runtime_settings.mouse_movement_profile,
                        sleep_chunk_ms=self._playback_settings.interruptible_sleep_chunk_ms,
                    ),
                    mouse_settle_ms=self._playback_settings.mouse_settle_ms,
                    stop_event=stop_event,
                    sleep_chunk_ms=self._playback_settings.interruptible_sleep_chunk_ms,
                ),
                stop_event,
            )
        else:
            live_executor = _UnavailableLiveExecutor()
        return PlaybackService(
            builder=PlaybackBuilder(
                from_script=PlaybackPlanFromScriptBuilder(runtime=runtime),
            ),
            live_engine=PlaybackEngine(
                live_executor,
                stop_event=stop_event,
                sleep_chunk_ms=self._playback_settings.interruptible_sleep_chunk_ms,
            ),
            preview_engine=PlaybackEngine(
                PreviewInputExecutor(),
                stop_event=stop_event,
                sleep_chunk_ms=self._playback_settings.interruptible_sleep_chunk_ms,
            ),
        )

    def _build_runtime_host_services(self) -> dict[str, object]:
        return self._runtime_host_services.as_mapping()

    def _show_msgbox_dialog(self, *, flag: int, title: str, text: str, timeout: int) -> int:
        dialog = QMessageBox()
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setTextFormat(Qt.PlainText)

        icon, buttons, default_button = self._msgbox_dialog_presentation(flag)
        if icon is not None:
            dialog.setIcon(icon)
        dialog.setStandardButtons(buttons)
        if default_button is not None:
            dialog.setDefaultButton(default_button)

        if timeout > 0:
            QTimer.singleShot(timeout * 1000, dialog.reject)

        return self._msgbox_result_code(dialog.exec())

    @staticmethod
    def _msgbox_dialog_presentation(
        flag: int,
    ) -> tuple[QMessageBox.Icon | None, QMessageBox.StandardButtons, QMessageBox.StandardButton | None]:
        button_kind = int(flag) & 0xF
        icon_kind = int(flag) & 0xF0

        icon_map = {
            0x10: QMessageBox.Question,
            0x20: QMessageBox.Warning,
            0x30: QMessageBox.Information,
            0x40: QMessageBox.Critical,
        }
        icon = icon_map.get(icon_kind)

        if button_kind == 1:
            return icon, QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok
        if button_kind == 2:
            return icon, QMessageBox.Abort | QMessageBox.Retry | QMessageBox.Ignore, QMessageBox.Abort
        if button_kind == 3:
            return icon, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
        if button_kind == 4:
            return icon, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        if button_kind == 5:
            return icon, QMessageBox.Retry | QMessageBox.Cancel, QMessageBox.Retry
        if button_kind == 6:
            return icon, QMessageBox.Cancel | QMessageBox.Help, QMessageBox.Cancel
        return icon, QMessageBox.Ok, QMessageBox.Ok

    @staticmethod
    def _msgbox_result_code(result: int) -> int:
        standard = QMessageBox.StandardButton(result)
        if standard == QMessageBox.Ok:
            return 1
        if standard == QMessageBox.Cancel:
            return 2
        if standard == QMessageBox.Abort:
            return 3
        if standard == QMessageBox.Retry:
            return 4
        if standard == QMessageBox.Ignore:
            return 5
        if standard == QMessageBox.Yes:
            return 6
        if standard == QMessageBox.No:
            return 7
        if standard == QMessageBox.Help:
            return 9
        return int(result)

    def _build_recording_service(self) -> RecordingService:
        config = RecorderConfig(
            capture_mouse_moves=self._recording_settings.capture_mouse_moves,
            capture_mouse_buttons=self._recording_settings.capture_mouse_buttons,
            capture_mouse_wheel=self._recording_settings.capture_mouse_wheel,
            capture_keyboard=self._recording_settings.capture_keyboard,
            mouse_move_threshold_px=self._recording_settings.mouse_move_threshold_px,
            excluded_window_hwnds=self._recording_excluded_window_hwnds(),
        )
        backend = PynputCaptureBackend(
            config=config,
            on_stop_requested=(
                self._recording_stop_event.set if self._recording_stop_event is not None else None
            ),
        )
        capture = InputCapture(backend=backend)
        recorder = SessionRecorder(config=config, capture=capture)
        return RecordingService(recorder)

    def _recording_excluded_window_hwnds(self) -> tuple[int, ...]:
        if not self._recording_settings.exclude_main_window_during_recording:
            return ()

        parent = self.parent()
        if parent is None or not hasattr(parent, "winId"):
            return ()

        try:
            hwnd = int(parent.winId())
        except Exception:
            return ()
        return normalize_window_handles((hwnd,))

    def _recording_status_hint(self) -> str | None:
        if not self._recording_settings.exclude_main_window_during_recording:
            return None

        if not self._recording_excluded_window_hwnds():
            return None

        return "excluding main window"

    def _begin_script_operation(
        self,
        kind: str,
        *,
        thread: threading.Thread,
        stop_event: threading.Event | None = None,
        mode: PlaybackMode | None = None,
        recording_service: RecordingService | None = None,
    ) -> None:
        self._script_operation_kind = kind
        self._script_operation_mode = mode
        self._script_operation_thread = thread
        self._script_operation_stop_event = stop_event
        self._script_operation_result = None
        self._script_operation_error = None
        self._recording_service = recording_service
        self._recording_stop_requested = False
        self._recording_stop_finalized = False
        self.busyChanged.emit(True)
        self._script_operation_timer.start()

    def _clear_script_operation_state(self) -> None:
        self._script_operation_kind = None
        self._script_operation_thread = None
        self._script_operation_stop_event = None
        self._script_operation_result = None
        self._script_operation_error = None
        self._script_operation_mode = None
        self._recording_service = None
        self._recording_stop_event = None
        self._recording_stop_requested = False
        self._recording_stop_finalized = False
        self.busyChanged.emit(False)

    def _start_playback_stop_hotkey_listener(self, stop_event: threading.Event) -> None:
        hotkey = self._playback_stop_hotkey.strip()
        if not hotkey:
            return

        self._stop_playback_stop_hotkey_listener()

        backend = PynputCaptureBackend(
            config=RecorderConfig(
                capture_mouse_moves=False,
                capture_mouse_buttons=False,
                capture_mouse_wheel=False,
                capture_keyboard=False,
            ),
            suppress=False,
            stop_hotkey=hotkey,
            on_stop_requested=stop_event.set,
        )
        thread = threading.Thread(
            target=self._run_playback_stop_hotkey_listener,
            args=(backend,),
            daemon=True,
        )
        self._playback_stop_hotkey_backend = backend
        self._playback_stop_hotkey_thread = thread
        thread.start()

    def _run_playback_stop_hotkey_listener(self, backend: PynputCaptureBackend) -> None:
        try:
            backend.start(lambda _event: None)
        except BaseException as exc:  # pragma: no cover - defensive fallback
            log.warning(
                "Playback stop hotkey listener failed",
                event_id="desktop.script_action_controller.playback_stop_hotkey_listener_failed",
                error=str(exc),
            )

    def _stop_playback_stop_hotkey_listener(self) -> None:
        backend = self._playback_stop_hotkey_backend
        thread = self._playback_stop_hotkey_thread
        self._playback_stop_hotkey_backend = None
        self._playback_stop_hotkey_thread = None

        if backend is None and thread is None:
            return

        if backend is not None:
            try:
                backend.stop()
            except BaseException as exc:  # pragma: no cover - defensive fallback
                log.warning(
                    "Playback stop hotkey listener shutdown failed",
                    event_id="desktop.script_action_controller.playback_stop_hotkey_listener_stop_failed",
                    error=str(exc),
                )

        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _poll_script_operation(self) -> None:
        thread = self._script_operation_thread
        if thread is None:
            self._script_operation_timer.stop()
            return
        if thread.is_alive():
            if (
                self._script_operation_kind == "record"
                and self._recording_stop_event is not None
                and self._recording_stop_event.is_set()
                and self._recording_service is not None
                and self._recording_service.is_recording()
            ):
                try:
                    self._stop_recording_once()
                except Exception as exc:
                    self._script_operation_error = exc
            return

        thread.join(timeout=0)
        self._script_operation_timer.stop()
        self._stop_playback_stop_hotkey_listener()

        kind = self._script_operation_kind
        mode = self._script_operation_mode
        stop_event = self._script_operation_stop_event
        result = self._script_operation_result
        error = self._script_operation_error
        recording_service = self._recording_service
        self._clear_script_operation_state()

        if error is not None:
            title = (
                self._playback_status_title(mode, failed=True)
                if kind == "play"
                else "Recording Failed"
            )
            self.errorOccurred.emit(title, str(error))
            self.statusChanged.emit(
                self._playback_status_label(mode, failed=True)
                if kind == "play"
                else f"{kind.title() if kind else 'Operation'} failed"
            )
            return

        if kind == "play":
            if result is not None:
                self.playbackResultReady.emit(result)
            if getattr(result, "success", False):
                executed_event_count = getattr(result, "executed_event_count", 0)
                self.statusChanged.emit(
                    f"{self._playback_status_label(mode, completed=True)} ({executed_event_count} events)"
                )
                return

            if stop_event is not None and stop_event.is_set():
                self.statusChanged.emit(self._playback_status_label(mode, stopped=True))
                return

            error_message = getattr(result, "error_message", "Script play failed.")
            self.errorOccurred.emit(self._playback_status_title(mode, failed=True), str(error_message))
            self.statusChanged.emit(self._playback_status_label(mode, failed=True))
            return

        if kind == "record":
            session = result
            if session is None:
                self.statusChanged.emit("Recording stopped")
                return

            if recording_service is not None:
                summary = recording_service.summarize(session)
                recording_status_hint = self._recording_status_hint()
                if recording_status_hint is None:
                    self.statusChanged.emit(
                        f"Recording stopped ({summary.event_count} events, {summary.duration_ms} ms)"
                    )
                else:
                    self.statusChanged.emit(
                        f"Recording stopped ({summary.event_count} events, {summary.duration_ms} ms; {recording_status_hint})"
                    )
            else:
                self.statusChanged.emit("Recording stopped")

            self.recordingResultReady.emit(session)
            return

        self.statusChanged.emit("Script operation completed")

    def _stop_recording_once(self) -> RecordingSession | None:
        recording_service = self._recording_service
        if recording_service is None:
            return None

        with self._recording_stop_lock:
            if self._recording_stop_finalized:
                return None

            self._recording_stop_finalized = True
            session = recording_service.stop_recording()
            self._script_operation_result = session
            return session

    @staticmethod
    def _playback_status_label(
        mode: PlaybackMode | None,
        *,
        started: bool = False,
        completed: bool = False,
        stopped: bool = False,
        failed: bool = False,
    ) -> str:
        mode_label = "preview" if mode == PlaybackMode.PREVIEW else "play"
        if started:
            return f"Previewing script" if mode == PlaybackMode.PREVIEW else "Playing script"
        if completed:
            return f"Script {mode_label} completed"
        if stopped:
            return f"Script {mode_label} stopped"
        if failed:
            return f"Script {mode_label} failed"
        return f"Script {mode_label}"

    @staticmethod
    def _playback_status_title(mode: PlaybackMode | None, *, failed: bool = False) -> str:
        if failed and mode == PlaybackMode.PREVIEW:
            return "Script Preview Failed"
        if failed:
            return "Script Play Failed"
        return "Script Play"
