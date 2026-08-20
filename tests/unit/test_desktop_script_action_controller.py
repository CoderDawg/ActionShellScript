from __future__ import annotations

import os
import threading
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from apps.desktop.script_action_controller import DesktopScriptActionController  # noqa: E402
from apps.desktop.settings import (  # noqa: E402
    DesktopPlaybackSettings,
    DesktopRecordingSettings,
    DesktopRuntimeSettings,
)
from core.playback.executors.preview_input_executor import PreviewInputExecutor  # noqa: E402
from core.playback.playback_mode import PlaybackMode  # noqa: E402
from core.playback.playback_plan import PlaybackPlan  # noqa: E402
from core.playback.playback_request import PlaybackRequest  # noqa: E402
from core.recording.recording_session import RecordingSession  # noqa: E402
from editor.document.script_document import ScriptDocument  # noqa: E402
from infrastructure.input.mouse_movement_profile import MouseMovementProfile  # noqa: E402
from core.playback.playback_engine import PlaybackEngine  # noqa: E402
from core.playback.playback_events import TextPlaybackEvent  # noqa: E402


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_desktop_script_action_controller_plays_and_stops_playback(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    document = ScriptDocument(document_id="doc-1", text='SendText("hello")\n')
    started = threading.Event()
    status_messages: list[str] = []
    busy_states: list[bool] = []
    captured: dict[str, object] = {}

    controller.statusChanged.connect(status_messages.append)
    controller.busyChanged.connect(busy_states.append)

    def fake_build_playback_service(stop_event, *, mode):
        class FakePlaybackService:
            def build_plan_from_script(self, document):
                captured["plan_document"] = document
                captured["mode"] = mode
                return PlaybackPlan(
                    source_kind="script_document",
                    source_id=document.document_id,
                    event_count=1,
                    events=[object()],
                )

            def play_plan(self, plan, request):
                captured["plan"] = plan
                captured["request"] = request
                captured["stop_event"] = stop_event
                started.set()
                stop_event.wait(1.0)
                return SimpleNamespace(
                    success=False,
                    executed_event_count=0,
                    error_message="Playback stopped.",
                )

        return FakePlaybackService()

    monkeypatch.setattr(controller, "_build_playback_service", fake_build_playback_service)

    assert controller.play(document) is True
    assert started.wait(timeout=1.0) is True
    assert controller.stop() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert status_messages[-1] == "Script play stopped"
    assert busy_states == [True, False]
    assert controller.is_active is False


def test_desktop_script_action_controller_uses_global_stop_hotkey_listener_for_playback(monkeypatch) -> None:
    _app()

    listener_started = threading.Event()
    playback_started = threading.Event()
    backend_instances: list[object] = []

    class FakeHotkeyBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.config = config
            self.suppress = suppress
            self.stop_hotkey = stop_hotkey
            self.on_stop_requested = on_stop_requested
            self.debug_stop_hotkey = debug_stop_hotkey
            self.stop_called = False
            self._stop_event = threading.Event()
            backend_instances.append(self)

        def start(self, on_event) -> None:
            self.on_event = on_event
            listener_started.set()
            self._stop_event.wait(1.0)

        def stop(self) -> None:
            self.stop_called = True
            self._stop_event.set()

    controller = DesktopScriptActionController()
    controller.set_playback_stop_hotkey("Shift+Esc|Ctrl+C")
    status_messages: list[str] = []
    controller.statusChanged.connect(status_messages.append)

    def fake_build_playback_service(stop_event, *, mode):
        class FakePlaybackService:
            def build_plan_from_script(self, document):
                return PlaybackPlan(
                    source_kind="script_document",
                    source_id=document.document_id,
                    event_count=1,
                    events=[object()],
                )

            def play_plan(self, plan, request):
                playback_started.set()
                stop_event.wait(1.0)
                return SimpleNamespace(
                    success=False,
                    executed_event_count=0,
                    error_message="Playback stopped.",
                )

        return FakePlaybackService()

    monkeypatch.setattr("apps.desktop.script_action_controller.PynputCaptureBackend", FakeHotkeyBackend)
    monkeypatch.setattr(controller, "_build_playback_service", fake_build_playback_service)

    document = ScriptDocument(document_id="doc-1", text='SendText("hello")\n')

    assert controller.play(document) is True
    assert listener_started.wait(timeout=1.0) is True
    assert playback_started.wait(timeout=1.0) is True
    assert backend_instances[0].stop_hotkey == "Shift+Esc|Ctrl+C"

    backend_instances[0].on_stop_requested()

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert backend_instances[0].stop_called is True
    assert status_messages[-1] == "Script play stopped"
    assert controller.is_active is False


def test_desktop_script_action_controller_uses_saved_playback_request_settings(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_playback_settings(
        DesktopPlaybackSettings(
            repeat_count=3,
            step_mode=True,
            delay_ms=125,
            mouse_settle_ms=17,
            interruptible_sleep_chunk_ms=20,
        )
    )
    document = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_path="/tmp/source/playback.ass",
    )
    captured: dict[str, object] = {}

    def fake_build_playback_service(stop_event, *, mode):
        class FakePlaybackService:
            def build_plan_from_script(self, document):
                captured["plan_document"] = document
                captured["mode"] = mode
                return PlaybackPlan(
                    source_kind="script_document",
                    source_id=document.document_id,
                    event_count=1,
                    events=[object()],
                )

            def play_plan(self, plan, request):
                captured["plan"] = plan
                captured["request"] = request
                captured["stop_event"] = stop_event
                return SimpleNamespace(
                    success=True,
                    executed_event_count=1,
                    error_message=None,
                )

        return FakePlaybackService()

    monkeypatch.setattr(controller, "_build_playback_service", fake_build_playback_service)

    assert controller.play(document) is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    request = captured["request"]
    assert request.source_kind == "script_document"
    assert request.source_id == document.document_id
    assert request.repeat_count == 3
    assert request.step_mode is True
    assert request.delay_ms == 125
    assert captured["plan"].event_count == 1
    assert captured["plan_document"].source_path == document.source_path


def test_desktop_script_action_controller_reports_playback_setup_failures(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    status_messages: list[str] = []
    errors: list[tuple[str, str]] = []

    controller.statusChanged.connect(status_messages.append)
    controller.errorOccurred.connect(lambda title, message: errors.append((title, message)))

    monkeypatch.setattr(
        controller,
        "_build_playback_service",
        lambda stop_event, *, mode: (_ for _ in ()).throw(RuntimeError("backend unavailable")),
    )

    document = ScriptDocument(document_id="doc-1", text="MsgBox \"hello\"\n")

    assert controller.play(document) is False
    assert status_messages[-1] == "Script play failed"
    assert errors == [("Script Play Failed", "backend unavailable")]
    assert controller.is_active is False


def test_desktop_script_action_controller_allows_empty_playback_plans(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    status_messages: list[str] = []
    captured: dict[str, object] = {}

    controller.statusChanged.connect(status_messages.append)

    class FakePlaybackService:
        def build_plan_from_script(self, document):
            return PlaybackPlan(
                source_kind="script_document",
                source_id=document.document_id,
                event_count=0,
                events=[],
            )

        def play_plan(self, plan, request):
            captured["plan"] = plan
            captured["request"] = request
            return SimpleNamespace(
                success=True,
                executed_event_count=0,
                error_message=None,
            )

    monkeypatch.setattr(
        controller,
        "_build_playback_service",
        lambda stop_event, *, mode: FakePlaybackService(),
    )

    document = ScriptDocument(document_id="doc-1", text='WriteLn("hello")\n')

    assert controller.play(document) is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert captured["plan"].event_count == 0
    assert status_messages[0] == "Playing script (0 events)"
    assert status_messages[-1] == "Script play completed (0 events)"


def test_desktop_script_action_controller_preview_mode_uses_preview_executor_only(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_playback_settings(
        DesktopPlaybackSettings(
            interruptible_sleep_chunk_ms=17,
        )
    )
    status_messages: list[str] = []
    busy_states: list[bool] = []
    controller.statusChanged.connect(status_messages.append)
    controller.busyChanged.connect(busy_states.append)

    def fail_if_live_adapter_created(*args, **kwargs):
        raise AssertionError("live pynput adapter should not be created in preview mode")

    def fail_if_live_executor_created(*args, **kwargs):
        raise AssertionError("live executor should not be created in preview mode")

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PynputPlaybackAdapter",
        fail_if_live_adapter_created,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.LiveInputExecutor",
        fail_if_live_executor_created,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.PREVIEW,
    )
    document = ScriptDocument(
        document_id="doc-preview",
        text='SendText("hello")\nWriteLn("preview")\n',
    )

    plan = service.build_plan_from_script(document)
    result = service.play_plan(
        plan,
        PlaybackRequest(
            source_kind=plan.source_kind,
            source_id=plan.source_id,
            mode=PlaybackMode.PREVIEW,
        ),
    )
    assert result.success is True
    assert isinstance(service._preview_engine._executor, PreviewInputExecutor)
    assert service._preview_engine._stop_event is not None
    assert service._preview_engine._sleep_chunk_ms == 17
    assert service._preview_engine._executor.executed_events
    assert service._live_engine._executor.__class__.__name__ == "_UnavailableLiveExecutor"

    assert controller.play(document, mode=PlaybackMode.PREVIEW) is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert status_messages[0] == "Previewing script (1 events)"
    assert status_messages[-1] == "Script preview completed (1 events)"
    assert busy_states == [True, False]
    assert controller.is_active is False


def test_desktop_script_action_controller_stops_preview_playback_from_stop_button(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_playback_settings(
        DesktopPlaybackSettings(
            delay_ms=30000,
            interruptible_sleep_chunk_ms=1,
        )
    )
    status_messages: list[str] = []
    busy_states: list[bool] = []
    playback_started = threading.Event()

    controller.statusChanged.connect(status_messages.append)
    controller.busyChanged.connect(busy_states.append)

    def fake_build_playback_service(stop_event, *, mode):
        preview_engine = PlaybackEngine(
            PreviewInputExecutor(),
            stop_event=stop_event,
            sleep_chunk_ms=1,
        )

        class FakePlaybackService:
            def build_plan_from_script(self, document):
                return PlaybackPlan(
                    source_kind="script_document",
                    source_id=document.document_id,
                    event_count=1,
                    events=[TextPlaybackEvent(text="done")],
                )

            def play_plan(self, plan, request):
                playback_started.set()
                return preview_engine.play(plan, request=request)

        return FakePlaybackService()

    monkeypatch.setattr(controller, "_build_playback_service", fake_build_playback_service)

    document = ScriptDocument(document_id="doc-preview-stop", text='SendText("hello")\n')

    assert controller.play(document, mode=PlaybackMode.PREVIEW) is True
    assert playback_started.wait(timeout=1.0) is True
    assert controller.stop() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert status_messages[-1] == "Script preview stopped"
    assert busy_states == [True, False]
    assert controller.is_active is False


def test_desktop_script_action_controller_stops_preview_playback_from_global_hotkey_listener(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_playback_settings(
        DesktopPlaybackSettings(
            delay_ms=30000,
            interruptible_sleep_chunk_ms=1,
        )
    )
    controller.set_playback_stop_hotkey("Shift+Esc")
    status_messages: list[str] = []
    busy_states: list[bool] = []
    playback_started = threading.Event()
    listener_started = threading.Event()
    backend_instances: list[object] = []

    controller.statusChanged.connect(status_messages.append)
    controller.busyChanged.connect(busy_states.append)

    class FakeHotkeyBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.config = config
            self.suppress = suppress
            self.stop_hotkey = stop_hotkey
            self.on_stop_requested = on_stop_requested
            self.debug_stop_hotkey = debug_stop_hotkey
            self.stop_called = False
            self._stop_event = threading.Event()
            backend_instances.append(self)

        def start(self, on_event) -> None:
            self.on_event = on_event
            listener_started.set()
            self._stop_event.wait(1.0)

        def stop(self) -> None:
            self.stop_called = True
            self._stop_event.set()

    def fake_build_playback_service(stop_event, *, mode):
        preview_engine = PlaybackEngine(
            PreviewInputExecutor(),
            stop_event=stop_event,
            sleep_chunk_ms=1,
        )

        class FakePlaybackService:
            def build_plan_from_script(self, document):
                return PlaybackPlan(
                    source_kind="script_document",
                    source_id=document.document_id,
                    event_count=1,
                    events=[TextPlaybackEvent(text="done")],
                )

            def play_plan(self, plan, request):
                playback_started.set()
                return preview_engine.play(plan, request=request)

        return FakePlaybackService()

    monkeypatch.setattr("apps.desktop.script_action_controller.PynputCaptureBackend", FakeHotkeyBackend)
    monkeypatch.setattr(controller, "_build_playback_service", fake_build_playback_service)

    document = ScriptDocument(document_id="doc-preview-hotkey", text='SendText("hello")\n')

    assert controller.play(document, mode=PlaybackMode.PREVIEW) is True
    assert listener_started.wait(timeout=1.0) is True
    assert playback_started.wait(timeout=1.0) is True
    assert backend_instances[0].stop_hotkey == "Shift+Esc"

    backend_instances[0].on_stop_requested()

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert backend_instances[0].stop_called is True
    assert status_messages[-1] == "Script preview stopped"
    assert busy_states == [True, False]
    assert controller.is_active is False


def test_desktop_script_action_controller_uses_saved_mouse_settle_setting_for_live_executor_with_legacy_zero_boundary_curve(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_playback_settings(
        DesktopPlaybackSettings(
            repeat_count=1,
            step_mode=False,
            delay_ms=0,
            mouse_settle_ms=37,
            interruptible_sleep_chunk_ms=20,
        )
    )
    controller.set_runtime_settings(
        DesktopRuntimeSettings(
            max_loop_iterations=100_000,
            max_call_depth=250,
            default_mouse_move_speed=10,
            # Legacy compatibility coverage: this ensures older zero-boundary
            # profiles still flow through playback setup unchanged. It is not the
            # preferred/default curve shape.
            mouse_movement_profile=MouseMovementProfile(
                duration_curve=((0, 0), (100, 60)),
                min_steps=1,
                max_steps=12,
                step_distance_px=6,
            ),
        )
    )
    captured: dict[str, object] = {}

    class FakeLiveInputExecutor:
        def __init__(
            self,
            host,
            *,
            mouse_settle_ms: int = 0,
            stop_event=None,
            sleep_chunk_ms: int = 50,
        ) -> None:
            captured["host"] = host
            captured["mouse_settle_ms"] = mouse_settle_ms
            captured["stop_event"] = stop_event
            captured["sleep_chunk_ms"] = sleep_chunk_ms
            self._mouse_settle_ms = mouse_settle_ms

        def execute(self, event) -> None:
            _ = event

    class FakePynputPlaybackAdapter:
        def __init__(self, **kwargs) -> None:
            captured["adapter_kwargs"] = kwargs

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PynputPlaybackAdapter",
        FakePynputPlaybackAdapter,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.LiveInputExecutor",
        FakeLiveInputExecutor,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.LIVE,
    )

    assert captured["mouse_settle_ms"] == 37
    assert captured["stop_event"] is not None
    assert captured["adapter_kwargs"]["sleep_chunk_ms"] == 20
    assert captured["adapter_kwargs"]["mouse_movement_profile"] == controller._runtime_settings.mouse_movement_profile
    assert captured["sleep_chunk_ms"] == 20
    assert service._live_engine._executor._executor._mouse_settle_ms == 37


def test_desktop_script_action_controller_uses_saved_runtime_settings_for_script_builder(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_runtime_settings(
        DesktopRuntimeSettings(
            max_loop_iterations=1234,
            max_call_depth=77,
            default_mouse_move_speed=19,
        )
    )
    captured: dict[str, object] = {}

    class FakeScriptRuntime:
        def __init__(self, **kwargs) -> None:
            captured["runtime_kwargs"] = kwargs

    class FakePlaybackPlanFromScriptBuilder:
        def __init__(self, *, runtime) -> None:
            captured["runtime"] = runtime

    class FakePlaybackBuilder:
        def __init__(self, *, from_recording=None, from_script=None) -> None:
            captured["from_recording"] = from_recording
            captured["from_script"] = from_script

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.ScriptRuntime",
        FakeScriptRuntime,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PlaybackPlanFromScriptBuilder",
        FakePlaybackPlanFromScriptBuilder,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PlaybackBuilder",
        FakePlaybackBuilder,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.LIVE,
    )

    runtime_kwargs = captured["runtime_kwargs"]
    assert runtime_kwargs["max_loop_iterations"] == 1234
    assert runtime_kwargs["max_call_depth"] == 77
    assert runtime_kwargs["default_mouse_move_speed"] == 19
    assert set(runtime_kwargs["host_services"]) == {
        "getcursorpos",
        "getclientrect",
        "getclassname",
        "getmonitorinfo",
        "getmonitorinfoex",
        "getwindowplacement",
        "getwindowrect",
        "getwindowtext",
        "getwindowlongptr",
        "getparent",
        "msgbox",
        "keytoggle",
        "iszoomed",
        "isiconic",
        "iswindowvisible",
        "iswindowenabled",
        "pixelgetcolor",
        "pixelsearch",
    }
    assert captured["from_recording"] is None
    assert isinstance(captured["from_script"], FakePlaybackPlanFromScriptBuilder)
    assert service._builder is not None


def test_desktop_script_action_controller_injects_pixel_get_color_host_service(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    captured: dict[str, object] = {}

    class FakeScriptRuntime:
        def __init__(self, **kwargs) -> None:
            captured["runtime_kwargs"] = kwargs

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.ScriptRuntime",
        FakeScriptRuntime,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.LIVE,
    )

    runtime_kwargs = captured["runtime_kwargs"]
    assert set(runtime_kwargs["host_services"]) == {
        "getcursorpos",
        "getclientrect",
        "getclassname",
        "getmonitorinfo",
        "getmonitorinfoex",
        "getwindowplacement",
        "getwindowrect",
        "getwindowtext",
        "getwindowlongptr",
        "getparent",
        "msgbox",
        "keytoggle",
        "iszoomed",
        "isiconic",
        "iswindowvisible",
        "iswindowenabled",
        "pixelgetcolor",
        "pixelsearch",
    }
    assert service._builder is not None


def test_desktop_script_action_controller_injects_pixel_search_host_service(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    captured: dict[str, object] = {}

    class FakeScriptRuntime:
        def __init__(self, **kwargs) -> None:
            captured["runtime_kwargs"] = kwargs

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.ScriptRuntime",
        FakeScriptRuntime,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.LIVE,
    )

    runtime_kwargs = captured["runtime_kwargs"]
    assert set(runtime_kwargs["host_services"]) == {
        "getcursorpos",
        "getclientrect",
        "getclassname",
        "getmonitorinfo",
        "getmonitorinfoex",
        "getwindowplacement",
        "getwindowrect",
        "getwindowtext",
        "getwindowlongptr",
        "getparent",
        "msgbox",
        "keytoggle",
        "iszoomed",
        "isiconic",
        "iswindowvisible",
        "iswindowenabled",
        "pixelgetcolor",
        "pixelsearch",
    }
    assert service._builder is not None


def test_desktop_script_action_controller_injects_msgbox_host_service(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    captured: dict[str, object] = {}

    class FakeScriptRuntime:
        def __init__(self, **kwargs) -> None:
            captured["runtime_kwargs"] = kwargs

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.ScriptRuntime",
        FakeScriptRuntime,
    )

    service = controller._build_playback_service(
        threading.Event(),
        mode=PlaybackMode.LIVE,
    )

    runtime_kwargs = captured["runtime_kwargs"]
    assert set(runtime_kwargs["host_services"]) == {
        "getcursorpos",
        "getclientrect",
        "getclassname",
        "getmonitorinfo",
        "getmonitorinfoex",
        "getwindowplacement",
        "getwindowrect",
        "getwindowtext",
        "getwindowlongptr",
        "getparent",
        "msgbox",
        "keytoggle",
        "iszoomed",
        "isiconic",
        "iswindowvisible",
        "iswindowenabled",
        "pixelgetcolor",
        "pixelsearch",
    }
    assert service._builder is not None


def test_desktop_script_action_controller_uses_saved_recording_settings_for_recording_config(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    controller.set_recording_settings(
        DesktopRecordingSettings(
            capture_mouse_moves=False,
            capture_mouse_buttons=True,
            capture_mouse_wheel=False,
            capture_keyboard=True,
            mouse_move_threshold_px=19,
        )
    )
    captured: dict[str, object] = {}

    class FakePynputCaptureBackend:
        def __init__(self, *, config, **kwargs) -> None:
            captured["backend_config"] = config
            captured["backend_kwargs"] = kwargs

    class FakeInputCapture:
        def __init__(self, *, backend) -> None:
            captured["capture_backend"] = backend

    class FakeSessionRecorder:
        def __init__(self, *, config, capture) -> None:
            captured["recorder_config"] = config
            captured["recorder_capture"] = capture

        def start(self, *, session_id: str):
            captured["session_id"] = session_id
            return SimpleNamespace(
                session_id=session_id,
                events=[],
                state=SimpleNamespace(value="recording"),
                started_at_ms=1,
                stopped_at_ms=2,
                duration_ms=lambda: 1,
            )

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PynputCaptureBackend",
        FakePynputCaptureBackend,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.InputCapture",
        FakeInputCapture,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.SessionRecorder",
        FakeSessionRecorder,
    )

    assert controller.record() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    recorder_config = captured["recorder_config"]
    assert recorder_config.capture_mouse_moves is False
    assert recorder_config.capture_mouse_buttons is True
    assert recorder_config.capture_mouse_wheel is False
    assert recorder_config.capture_keyboard is True
    assert recorder_config.mouse_move_threshold_px == 19
    assert recorder_config.excluded_window_hwnds == ()
    assert captured["backend_config"] is recorder_config
    assert captured["capture_backend"] is not None


def test_desktop_script_action_controller_excludes_parent_window_while_recording(
    monkeypatch,
) -> None:
    _app()

    parent = QWidget()
    parent.show()

    controller = DesktopScriptActionController(parent)
    controller.set_recording_settings(DesktopRecordingSettings())
    captured: dict[str, object] = {}

    class FakePynputCaptureBackend:
        def __init__(self, *, config, **kwargs) -> None:
            captured["backend_config"] = config
            captured["backend_kwargs"] = kwargs

    class FakeInputCapture:
        def __init__(self, *, backend) -> None:
            captured["capture_backend"] = backend

    class FakeSessionRecorder:
        def __init__(self, *, config, capture) -> None:
            captured["recorder_config"] = config
            captured["recorder_capture"] = capture

        def start(self, *, session_id: str):
            captured["session_id"] = session_id
            return SimpleNamespace(
                session_id=session_id,
                events=[],
                state=SimpleNamespace(value="recording"),
                started_at_ms=1,
                stopped_at_ms=2,
                duration_ms=lambda: 1,
            )

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PynputCaptureBackend",
        FakePynputCaptureBackend,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.InputCapture",
        FakeInputCapture,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.SessionRecorder",
        FakeSessionRecorder,
    )

    assert controller.record() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    recorder_config = captured["recorder_config"]
    assert recorder_config.excluded_window_hwnds == (int(parent.winId()),)
    assert captured["backend_config"].excluded_window_hwnds == (int(parent.winId()),)


def test_desktop_script_action_controller_reports_excluding_main_window_in_recording_status(
    monkeypatch,
) -> None:
    _app()

    parent = QWidget()
    parent.show()

    controller = DesktopScriptActionController(parent)
    status_messages: list[str] = []
    controller.statusChanged.connect(status_messages.append)

    completed_session = RecordingSession(session_id="session-4")
    completed_session.start(400)
    completed_session.stop(411)

    class FakeRecordingService:
        def __init__(self) -> None:
            self._recording = False

        def start_recording(self, *, session_id: str):
            _ = session_id
            self._recording = False
            return completed_session

        def stop_recording(self):
            self._recording = False
            return completed_session

        def is_recording(self) -> bool:
            return self._recording

        def summarize(self, session):
            assert session is completed_session
            return SimpleNamespace(event_count=1, duration_ms=11)

    monkeypatch.setattr(controller, "_build_recording_service", lambda: FakeRecordingService())

    assert controller.record() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert status_messages[0] == "Recording started (excluding main window)"
    assert status_messages[-1] == "Recording stopped (1 events, 11 ms; excluding main window)"


def test_desktop_script_action_controller_stops_recording_once_for_quick_stop(monkeypatch) -> None:
    _app()

    controller = DesktopScriptActionController()
    started = threading.Event()
    released = threading.Event()
    status_messages: list[str] = []
    busy_states: list[bool] = []
    results: list[RecordingSession] = []

    controller.statusChanged.connect(status_messages.append)
    controller.busyChanged.connect(busy_states.append)
    controller.recordingResultReady.connect(results.append)

    started_session = RecordingSession(session_id="session-1")
    started_session.start(100)
    stopped_session = RecordingSession(session_id="session-1")
    stopped_session.start(100)
    stopped_session.events.append({"type": "key_down", "key": "shift"})
    stopped_session.stop(142)

    class FakeRecordingService:
        def __init__(self) -> None:
            self._recording = False
            self.stop_calls = 0

        def start_recording(self, *, session_id: str):
            _ = session_id
            self._recording = True
            started.set()
            released.wait(1.0)
            return started_session

        def stop_recording(self):
            self.stop_calls += 1
            self._recording = False
            released.set()
            return stopped_session

        def is_recording(self) -> bool:
            return self._recording

        def summarize(self, session):
            assert session is stopped_session
            return SimpleNamespace(event_count=len(session.events), duration_ms=session.duration_ms())

    service = FakeRecordingService()
    monkeypatch.setattr(controller, "_build_recording_service", lambda: service)

    assert controller.record() is True
    assert started.wait(timeout=1.0) is True
    assert controller.stop() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert service.stop_calls == 1
    assert results == [stopped_session]
    assert status_messages[-1].startswith("Recording stopped")
    assert busy_states == [True, False]
    assert controller.is_active is False
    assert len(results) == 1


def test_desktop_script_action_controller_stops_recording_once_for_backend_requested_stop(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    started = threading.Event()
    released = threading.Event()
    status_messages: list[str] = []
    results: list[RecordingSession] = []

    controller.statusChanged.connect(status_messages.append)
    controller.recordingResultReady.connect(results.append)

    started_session = RecordingSession(session_id="session-2")
    started_session.start(200)
    stopped_session = RecordingSession(session_id="session-2")
    stopped_session.start(200)
    stopped_session.events.append({"type": "key_up", "key": "esc"})
    stopped_session.stop(247)

    captured: dict[str, object] = {}

    class FakePynputCaptureBackend:
        def __init__(self, *, config, on_stop_requested=None, **kwargs) -> None:
            _ = config
            _ = kwargs
            self.on_stop_requested = on_stop_requested
            captured["on_stop_requested"] = on_stop_requested

    class FakeInputCapture:
        def __init__(self, *, backend) -> None:
            captured["backend"] = backend

    class FakeSessionRecorder:
        def __init__(self, *, config, capture) -> None:
            _ = config
            captured["capture"] = capture
            self._recording = False
            self.stop_calls = 0
            captured["recorder"] = self

        @property
        def is_recording(self) -> bool:
            return self._recording

        def start(self, *, session_id: str):
            _ = session_id
            self._recording = True
            started.set()
            backend = captured["backend"]
            backend.on_stop_requested()
            released.wait(1.0)
            return started_session

        def stop(self):
            self.stop_calls += 1
            self._recording = False
            released.set()
            return stopped_session

    monkeypatch.setattr(
        "apps.desktop.script_action_controller.PynputCaptureBackend",
        FakePynputCaptureBackend,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.InputCapture",
        FakeInputCapture,
    )
    monkeypatch.setattr(
        "apps.desktop.script_action_controller.SessionRecorder",
        FakeSessionRecorder,
    )

    assert controller.record() is True
    assert started.wait(timeout=1.0) is True

    thread = controller._script_operation_thread
    assert thread is not None
    controller._poll_script_operation()
    assert released.wait(timeout=1.0) is True
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    session_recorder = captured["recorder"]
    assert isinstance(session_recorder, FakeSessionRecorder)
    assert session_recorder.stop_calls == 1
    assert results == [stopped_session]
    assert status_messages[-1].startswith("Recording stopped")
    assert controller.is_active is False
    assert len(results) == 1


def test_desktop_script_action_controller_emits_recording_result_for_normal_completion(
    monkeypatch,
) -> None:
    _app()

    controller = DesktopScriptActionController()
    status_messages: list[str] = []
    results: list[RecordingSession] = []

    controller.statusChanged.connect(status_messages.append)
    controller.recordingResultReady.connect(results.append)

    completed_session = RecordingSession(session_id="session-3")
    completed_session.start(300)
    completed_session.events.append({"type": "mouse_move", "x": 5, "y": 9})
    completed_session.stop(311)

    class FakeRecordingService:
        def __init__(self) -> None:
            self._recording = False
            self.stop_calls = 0

        def start_recording(self, *, session_id: str):
            _ = session_id
            self._recording = False
            return completed_session

        def stop_recording(self):
            self.stop_calls += 1
            raise AssertionError("stop_recording() should not be called for normal completion")

        def is_recording(self) -> bool:
            return self._recording

        def summarize(self, session):
            assert session is completed_session
            return SimpleNamespace(event_count=len(session.events), duration_ms=session.duration_ms())

    service = FakeRecordingService()
    monkeypatch.setattr(controller, "_build_recording_service", lambda: service)

    assert controller.record() is True

    thread = controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    controller._poll_script_operation()

    assert service.stop_calls == 0
    assert results == [completed_session]
    assert status_messages[-1] == "Recording stopped (1 events, 11 ms)"
    assert controller.is_active is False
    assert len(results) == 1
