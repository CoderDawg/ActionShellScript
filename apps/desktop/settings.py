from __future__ import annotations

from dataclasses import dataclass, field

from apps.desktop.hotkeys import default_hotkey_bindings
from apps.desktop.theme import DesktopPreferences
from infrastructure.input.mouse_movement_profile import MouseMovementProfile


@dataclass(slots=True)
class DesktopHotkeySettings:
    bindings: dict[str, str] = field(default_factory=default_hotkey_bindings)


@dataclass(slots=True)
class DesktopPlaybackSettings:
    repeat_count: int = 1
    step_mode: bool = False
    delay_ms: int = 0
    mouse_settle_ms: int = 0
    interruptible_sleep_chunk_ms: int = 50
    send_key_taps_instead_of_text: bool = False

    def runtime_special_values(self) -> dict[str, object]:
        return {
            "PlaybackRepeatCount": int(self.repeat_count),
            "PlaybackEventPause": bool(self.step_mode),
            "PlaybackEventDelay": int(self.delay_ms),
            "PlaybackMouseSettle": int(self.mouse_settle_ms),
            "PlaybackSendKeyTapsInsteadOfText": bool(self.send_key_taps_instead_of_text),
        }


@dataclass(slots=True)
class DesktopRecordingSettings:
    recording_conversion_mode: str = "promote_generated"
    capture_mouse_moves: bool = True
    capture_mouse_buttons: bool = True
    capture_mouse_wheel: bool = True
    capture_keyboard: bool = True
    mouse_move_threshold_px: int = 0
    exclude_main_window_during_recording: bool = True


@dataclass(slots=True)
class DesktopFilesSettings:
    file_extension: str = ".ass"
    autosave_enabled: bool = True
    autosave_file_name: str = "recording"
    autosave_timestamp_suffix: bool = True
    autosave_output_folder: str = "recordings"
    raw_autosave_enabled: bool = True
    raw_autosave_file_name: str = "recording"
    raw_autosave_timestamp_suffix: bool = True
    raw_autosave_output_folder: str = "recordings"
    diagnostic_log_path: str | None = None


@dataclass(slots=True)
class DesktopDiagnosticsSettings:
    enabled: bool = False
    min_severity: str = "info"
    max_detail: str = "summary"
    log_to_file: bool = False
    log_to_stdout: bool = False


@dataclass(slots=True)
class DesktopRuntimeSettings:
    max_loop_iterations: int = 100_000
    max_call_depth: int = 250
    default_mouse_move_speed: int = 10
    show_mouse_movement_reference_curve: bool = True
    mouse_movement_profile: MouseMovementProfile = field(
        default_factory=MouseMovementProfile
    )


@dataclass(slots=True)
class DesktopApplicationSettings:
    restore_last_workspace: bool = False
    open_debug_tab_on_pause: bool = True
    show_summary_sidebar_on_left: bool = True
    hidden_workspace_tabs_strip_collapsed: bool = True
    show_analysis_tab: bool = False
    show_debug_tab: bool = True
    show_formatted_preview_tab: bool = True
    show_raw_recordings_tab: bool = False
    show_diagnostics_tab: bool = False
    last_workspace_path: str | None = None
    last_open_directory: str | None = None
    go_to_last_mode: str = "line"
    go_to_last_value: int = 1
    go_to_last_geometry: str | None = None
    hotkeys: DesktopHotkeySettings = field(default_factory=DesktopHotkeySettings)


@dataclass(slots=True)
class DesktopSettingsBundle:
    application: DesktopApplicationSettings = field(default_factory=DesktopApplicationSettings)
    playback: DesktopPlaybackSettings = field(default_factory=DesktopPlaybackSettings)
    recording: DesktopRecordingSettings = field(default_factory=DesktopRecordingSettings)
    files: DesktopFilesSettings = field(default_factory=DesktopFilesSettings)
    diagnostics: DesktopDiagnosticsSettings = field(default_factory=DesktopDiagnosticsSettings)
    runtime: DesktopRuntimeSettings = field(default_factory=DesktopRuntimeSettings)
    theme: DesktopPreferences = field(default_factory=DesktopPreferences)
