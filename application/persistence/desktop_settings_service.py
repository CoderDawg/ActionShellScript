from __future__ import annotations

import base64
import os
from dataclasses import asdict
from pathlib import Path

from apps.desktop.hotkeys import default_hotkey_bindings, hotkey_conflict_groups
from apps.desktop.settings import (
    DesktopApplicationSettings,
    DesktopDiagnosticsSettings,
    DesktopFilesSettings,
    DesktopHotkeySettings,
    DesktopSettingsBundle,
    DesktopPlaybackSettings,
    DesktopRecordingSettings,
    DesktopRuntimeSettings,
)
from apps.desktop.theme import (
    AppearanceTheme,
    DesktopPreferences,
    EditorAppearanceTheme,
    DirtyIndicatorTheme,
    FontSettings,
    SearchResultsTheme,
    ScriptingSettings,
    SyntaxHighlightTheme,
    WorkspaceTabAttentionTheme,
)
from application.persistence.persistence_errors import (
    PersistenceLoadError,
    PersistenceSaveError,
)
from core.persistence.file_reference import FileReference
from core.persistence.save_result import SaveResult
from core.persistence.persistence_models import PendingAction, SaveRequirement
from application.persistence.unsaved_changes_service import UnsavedChangesService
from infrastructure.input.mouse_movement_profile import MouseMovementProfile
from infrastructure.persistence.json_file_store import JsonFileStore


def _default_config_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        return Path(base) / "ActionShellScript" / "config"
    return Path.home() / ".actionshellscript" / "config"


class DesktopSettingsService:
    def __init__(
        self,
        *,
        config_dir: Path | None = None,
        file_store: JsonFileStore | None = None,
        unsaved_changes_service: UnsavedChangesService | None = None,
    ) -> None:
        self._config_dir = Path(config_dir) if config_dir is not None else _default_config_dir()
        self._file_store = file_store or JsonFileStore()
        self._unsaved_changes_service = unsaved_changes_service or UnsavedChangesService()

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def settings_path(self) -> Path:
        return self._config_dir / "desktop_settings.json"

    @property
    def application_settings_path(self) -> Path:
        return self.settings_path

    @property
    def theme_settings_path(self) -> Path:
        return self.settings_path

    def load(self) -> DesktopSettingsBundle:
        if self.settings_path.exists():
            payload = self._load_settings_payload(self.settings_path)
            application = self._load_application_settings_from_payload(payload.get("application", {}))
            playback = self._load_playback_settings_from_payload(payload.get("playback", {}))
            recording = self._load_recording_settings_from_payload(payload.get("recording", {}))
            files = self._load_files_settings_from_payload(
                payload.get("files", {}),
                fallback_recording=payload.get("recording", {}),
                fallback_runtime=payload.get("runtime", {}),
                fallback_theme=payload.get("theme", {}),
            )
            diagnostics = self._load_diagnostics_settings_from_payload(
                payload.get("diagnostics", {})
            )
            runtime = self._load_runtime_settings_from_payload(payload.get("runtime", {}))
            theme = self._load_theme_settings_from_payload(payload.get("theme", {}))
            return DesktopSettingsBundle(
                application=application,
                playback=playback,
                recording=recording,
                files=files,
                diagnostics=diagnostics,
                runtime=runtime,
                theme=theme,
            )

        application = self._load_legacy_application_settings()
        playback = DesktopPlaybackSettings()
        runtime = DesktopRuntimeSettings()
        theme = DesktopPreferences()
        files = self._load_files_settings_from_payload(
            {},
            fallback_recording={},
            fallback_runtime={},
            fallback_theme={},
        )
        bundle = DesktopSettingsBundle(
            application=application,
            playback=playback,
            recording=DesktopRecordingSettings(),
            files=files,
            diagnostics=DesktopDiagnosticsSettings(),
            runtime=runtime,
            theme=theme,
        )
        if self._legacy_application_settings_path.exists():
            try:
                self.save(bundle, force=True)
            except PersistenceSaveError:
                pass
        return bundle

    def save(
        self,
        bundle: DesktopSettingsBundle,
        *,
        force: bool = False,
    ) -> tuple[SaveResult, SaveResult]:
        conflict_groups = hotkey_conflict_groups(bundle.application.hotkeys.bindings)
        if conflict_groups:
            details = "\n".join(
                "- "
                + sequence_text
                + ": "
                + ", ".join(definition.label for definition in definitions)
                for sequence_text, definitions in conflict_groups
            )
            raise PersistenceSaveError(
                "Resolve hotkey conflicts before saving preferences:\n"
                f"{details}"
            )
        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "application": self._serialize_application_settings(bundle.application),
            "playback": self._serialize_playback_settings(bundle.playback),
            "recording": self._serialize_recording_settings(bundle.recording),
            "files": self._serialize_files_settings(bundle.files),
            "diagnostics": self._serialize_diagnostics_settings(bundle.diagnostics),
            "runtime": self._serialize_runtime_settings(bundle.runtime),
            "theme": self._serialize_theme_settings(bundle.theme),
        }
        try:
            self._file_store.save(self.settings_path, payload)
        except (OSError, TypeError, ValueError) as exc:
            raise PersistenceSaveError(
                f"Could not save desktop settings to {self.settings_path}."
            ) from exc
        result = SaveResult(
            target=FileReference(path=self.settings_path),
            version=1,
        )
        return result, result

    def save_requirements(self) -> list[tuple[Path, SaveRequirement, str]]:
        return [
            (
                self.settings_path,
                self._unsaved_changes_service.requires_resolution_for_existing_target(
                    target=self.settings_path,
                    action=PendingAction.REPLACE_EXISTING_OUTPUT,
                    target_description="Desktop settings file",
                ),
                "Desktop settings file",
            ),
        ]

    def _load_settings_payload(self, path: Path) -> dict[str, object]:
        try:
            payload = self._file_store.load(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise PersistenceLoadError(
                f"Could not load desktop settings from {path}."
            ) from exc
        if not isinstance(payload, dict):
            raise PersistenceLoadError(f"Could not load desktop settings from {path}.")
        return payload

    def _load_application_settings_from_payload(
        self,
        payload: object,
    ) -> DesktopApplicationSettings:
        if not isinstance(payload, dict):
            return DesktopApplicationSettings()
        last_open_directory = payload.get("last_open_directory")
        if not isinstance(last_open_directory, str) or not last_open_directory.strip():
            last_open_directory = None
        go_to_last_mode = payload.get("go_to_last_mode")
        if go_to_last_mode not in {"line", "offset"}:
            go_to_last_mode = "line"
        go_to_last_value = payload.get("go_to_last_value", 1)
        try:
            go_to_last_value = max(1, int(go_to_last_value)) if go_to_last_mode == "line" else max(0, int(go_to_last_value))
        except (TypeError, ValueError):
            go_to_last_value = 1 if go_to_last_mode == "line" else 0
        go_to_last_geometry = payload.get("go_to_last_geometry")
        if isinstance(go_to_last_geometry, str):
            go_to_last_geometry = go_to_last_geometry.strip() or None
            if go_to_last_geometry is not None:
                try:
                    base64.b64decode(go_to_last_geometry.encode("ascii"), validate=True)
                except (ValueError, UnicodeError):
                    go_to_last_geometry = None
        else:
            go_to_last_geometry = None
        return DesktopApplicationSettings(
            restore_last_workspace=bool(payload.get("restore_last_workspace", False)),
            open_debug_tab_on_pause=bool(
                payload.get("open_debug_tab_on_pause", payload.get("auto_open_debug_tab_on_pause", True))
            ),
            show_analysis_tab=bool(payload.get("show_analysis_tab", False)),
            show_debug_tab=bool(payload.get("show_debug_tab", True)),
            show_formatted_preview_tab=bool(payload.get("show_formatted_preview_tab", True)),
            show_raw_recordings_tab=bool(payload.get("show_raw_recordings_tab", False)),
            show_diagnostics_tab=bool(payload.get("show_diagnostics_tab", False)),
            hidden_workspace_tabs_strip_collapsed=bool(
                payload.get("hidden_workspace_tabs_strip_collapsed", True)
            ),
            last_workspace_path=payload.get("last_workspace_path"),
            last_open_directory=last_open_directory,
            go_to_last_mode=go_to_last_mode,
            go_to_last_value=go_to_last_value,
            go_to_last_geometry=go_to_last_geometry,
            hotkeys=self._load_hotkey_settings(payload.get("hotkeys", {})),
        )

    def _load_playback_settings_from_payload(self, payload: object) -> DesktopPlaybackSettings:
        if not isinstance(payload, dict):
            return DesktopPlaybackSettings()
        return DesktopPlaybackSettings(
            repeat_count=max(1, int(payload.get("repeat_count", 1))),
            step_mode=bool(payload.get("step_mode", False)),
            delay_ms=max(0, int(payload.get("delay_ms", 0))),
            mouse_settle_ms=max(0, int(payload.get("mouse_settle_ms", 0))),
            interruptible_sleep_chunk_ms=max(
                1,
                int(payload.get("interruptible_sleep_chunk_ms", 50)),
            ),
            send_key_taps_instead_of_text=bool(
                payload.get("send_key_taps_instead_of_text", False)
            ),
        )

    def _load_recording_settings_from_payload(self, payload: object) -> DesktopRecordingSettings:
        if not isinstance(payload, dict):
            return DesktopRecordingSettings()
        return DesktopRecordingSettings(
            recording_conversion_mode=self._normalize_recording_conversion_mode(
                payload.get("recording_conversion_mode")
            ),
            capture_mouse_moves=bool(payload.get("capture_mouse_moves", True)),
            capture_mouse_buttons=bool(payload.get("capture_mouse_buttons", True)),
            capture_mouse_wheel=bool(payload.get("capture_mouse_wheel", True)),
            capture_keyboard=bool(payload.get("capture_keyboard", True)),
            mouse_move_threshold_px=max(0, int(payload.get("mouse_move_threshold_px", 0))),
            exclude_main_window_during_recording=bool(
                payload.get("exclude_main_window_during_recording", True)
            ),
        )

    def _load_files_settings_from_payload(
        self,
        payload: object,
        *,
        fallback_recording: object,
        fallback_theme: object,
        fallback_runtime: object | None = None,
    ) -> DesktopFilesSettings:
        if isinstance(payload, dict):
            source = payload
        else:
            source = {}
        legacy_recording = fallback_recording if isinstance(fallback_recording, dict) else {}
        legacy_runtime = fallback_runtime if isinstance(fallback_runtime, dict) else {}
        theme_source = fallback_theme if isinstance(fallback_theme, dict) else {}
        theme_scripting = {}
        if isinstance(theme_source, dict):
            theme_scripting = theme_source.get("scripting", theme_source.get("runtime", {}))
        if not isinstance(theme_scripting, dict):
            theme_scripting = {}
        autosave_enabled = bool(
            source.get("autosave_enabled", legacy_recording.get("autosave_enabled", True))
        )
        autosave_file_name = str(
            source.get("autosave_file_name")
            or legacy_recording.get("autosave_file_name")
            or "recording"
        )
        autosave_timestamp_suffix = bool(
            source.get(
                "autosave_timestamp_suffix",
                legacy_recording.get("autosave_timestamp_suffix", True),
            )
        )
        autosave_output_folder = str(
            source.get("autosave_output_folder")
            or legacy_recording.get("autosave_output_folder")
            or "recordings"
        )
        raw_autosave_enabled = bool(
            source.get(
                "raw_autosave_enabled",
                legacy_recording.get("raw_autosave_enabled", autosave_enabled),
            )
        )
        raw_autosave_file_name = str(
            source.get("raw_autosave_file_name")
            or legacy_recording.get("raw_autosave_file_name")
            or autosave_file_name
        )
        raw_autosave_timestamp_suffix = bool(
            source.get(
                "raw_autosave_timestamp_suffix",
                legacy_recording.get("raw_autosave_timestamp_suffix", autosave_timestamp_suffix),
            )
        )
        raw_autosave_output_folder = str(
            source.get("raw_autosave_output_folder")
            or legacy_recording.get("raw_autosave_output_folder")
            or autosave_output_folder
        )
        diagnostic_log_path = str(
            source.get("diagnostic_log_path")
            or legacy_runtime.get("diagnostic_log_path")
            or ""
        ).strip()
        file_extension = str(
            source.get("file_extension")
            or theme_scripting.get("file_extension")
            or ".ass"
        )
        return DesktopFilesSettings(
            file_extension=file_extension,
            autosave_enabled=autosave_enabled,
            autosave_file_name=autosave_file_name,
            autosave_timestamp_suffix=autosave_timestamp_suffix,
            autosave_output_folder=autosave_output_folder,
            raw_autosave_enabled=raw_autosave_enabled,
            raw_autosave_file_name=raw_autosave_file_name,
            raw_autosave_timestamp_suffix=raw_autosave_timestamp_suffix,
            raw_autosave_output_folder=raw_autosave_output_folder,
            diagnostic_log_path=diagnostic_log_path or None,
        )

    def _load_diagnostics_settings_from_payload(
        self,
        payload: object,
    ) -> DesktopDiagnosticsSettings:
        if not isinstance(payload, dict):
            return DesktopDiagnosticsSettings()
        return DesktopDiagnosticsSettings(
            enabled=bool(payload.get("enabled", False)),
            min_severity=str(payload.get("min_severity", "info")),
            max_detail=str(payload.get("max_detail", "summary")),
            log_to_file=bool(payload.get("log_to_file", False)),
            log_to_stdout=bool(payload.get("log_to_stdout", False)),
        )

    def _load_runtime_settings_from_payload(self, payload: object) -> DesktopRuntimeSettings:
        if not isinstance(payload, dict):
            return DesktopRuntimeSettings()
        return DesktopRuntimeSettings(
            max_loop_iterations=max(1, int(payload.get("max_loop_iterations", 100_000))),
            max_call_depth=max(1, int(payload.get("max_call_depth", 250))),
            default_mouse_move_speed=max(0, min(100, int(payload.get("default_mouse_move_speed", 10)))),
            show_mouse_movement_reference_curve=bool(
                payload.get("show_mouse_movement_reference_curve", True)
            ),
            mouse_movement_profile=self._load_mouse_movement_profile_from_payload(
                payload.get("mouse_movement_profile", {})
            ),
        )

    def _load_theme_settings_from_payload(self, payload: object) -> DesktopPreferences:
        if not isinstance(payload, dict):
            return DesktopPreferences()
        appearance = payload.get("appearance", {})
        scripting = payload.get("scripting", {})
        runtime = payload.get("runtime", {})
        font = payload.get("font", {})
        search_results = payload.get("search_results", {})
        if isinstance(appearance, dict) and "editor" in appearance:
            editor = appearance.get("editor", {})
            syntax = appearance.get("syntax_highlighting", {})
            dirty = appearance.get("dirty_indicators", {})
            attention = appearance.get("workspace_tab_attention", {})
        else:
            editor = appearance
            syntax = {}
            dirty = appearance.get("dirty_indicators", {}) if isinstance(appearance, dict) else {}
            attention = (
                appearance.get("workspace_tab_attention", {})
                if isinstance(appearance, dict)
                else {}
            )
        return DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(
                    background=str(editor.get("background", "#ffffff")),
                    text=str(editor.get("text", "#000000")),
                    gutter_background=str(editor.get("gutter_background", "#f2f2f2")),
                    gutter_text=str(editor.get("gutter_text", "#202020")),
                    current_line_foreground=str(
                        editor.get("current_line_foreground", editor.get("text", "#000000"))
                    ),
                    current_line_highlight=str(
                        editor.get("current_line_highlight", "#fff4c2")
                    ),
                ),
                syntax_highlighting=SyntaxHighlightTheme(
                    keyword=str(syntax.get("keyword", "#005cc5")),
                    string=str(syntax.get("string", "#0b7a75")),
                    comment=str(syntax.get("comment", "#6a737d")),
                    number=str(syntax.get("number", "#b31d28")),
                ),
                dirty_indicators=DirtyIndicatorTheme(
                    text=str(dirty.get("text", "#7a4a00")),
                    accent=str(dirty.get("accent", "#8b6a2f")),
                    background=str(dirty.get("background", "#fff5e3")),
                    selected_background=str(
                        dirty.get("selected_background", "#f0ddb4")
                    ),
                    border=str(dirty.get("border", "#ead8b6")),
                ),
                workspace_tab_attention=WorkspaceTabAttentionTheme(
                    enabled=bool(attention.get("enabled", True)),
                    accent=str(attention.get("accent", "#2b7de9")),
                ),
            ),
            scripting=self._load_scripting_settings_from_payload(scripting, fallback=runtime),
            font=FontSettings(
                family=str(font.get("family", "Consolas")),
                size=max(1, int(font.get("size", 11))),
                weight=int(font.get("weight", 400)),
                line_spacing_multiplier=float(font.get("line_spacing_multiplier", 1.0)),
            ),
            search_results=SearchResultsTheme(
                header_active=str(search_results.get("header_active", "#d7e9ff")),
                header_hovered=str(search_results.get("header_hovered", "#e0efff")),
                header_active_hovered=str(
                    search_results.get("header_active_hovered", "#b9d9ff")
                ),
                header_radius=str(search_results.get("header_radius", "4px")),
                header_padding=str(search_results.get("header_padding", "1px 4px")),
                header_text=str(search_results.get("header_text", "#666666")),
                line_text=str(search_results.get("line_text", "#222222")),
                hit_text=str(search_results.get("hit_text", "#666666")),
                child_border_color=str(search_results.get("child_border_color", "#8fb6e8")),
                child_border_width=str(search_results.get("child_border_width", "2px")),
                child_padding_left=int(search_results.get("child_padding_left", 8)),
                child_margin_left=int(search_results.get("child_margin_left", 4)),
            ),
        )

    def _serialize_application_settings(
        self,
        settings: DesktopApplicationSettings,
    ) -> dict[str, object]:
        return {
            "restore_last_workspace": bool(settings.restore_last_workspace),
            "open_debug_tab_on_pause": bool(settings.open_debug_tab_on_pause),
            "auto_open_debug_tab_on_pause": bool(settings.open_debug_tab_on_pause),
            "show_analysis_tab": bool(settings.show_analysis_tab),
            "show_debug_tab": bool(settings.show_debug_tab),
            "show_formatted_preview_tab": bool(settings.show_formatted_preview_tab),
            "show_raw_recordings_tab": bool(settings.show_raw_recordings_tab),
            "show_diagnostics_tab": bool(settings.show_diagnostics_tab),
            "hidden_workspace_tabs_strip_collapsed": bool(
                settings.hidden_workspace_tabs_strip_collapsed
            ),
            "last_workspace_path": settings.last_workspace_path,
            "last_open_directory": settings.last_open_directory,
            "go_to_last_mode": settings.go_to_last_mode,
            "go_to_last_value": int(settings.go_to_last_value),
            "go_to_last_geometry": settings.go_to_last_geometry,
            "hotkeys": {"bindings": dict(settings.hotkeys.bindings)},
        }

    def _serialize_playback_settings(
        self,
        settings: DesktopPlaybackSettings,
    ) -> dict[str, object]:
        return {
            "repeat_count": max(1, int(settings.repeat_count)),
            "step_mode": bool(settings.step_mode),
            "delay_ms": max(0, int(settings.delay_ms)),
            "mouse_settle_ms": max(0, int(settings.mouse_settle_ms)),
            "interruptible_sleep_chunk_ms": max(
                1,
                int(settings.interruptible_sleep_chunk_ms),
            ),
            "send_key_taps_instead_of_text": bool(settings.send_key_taps_instead_of_text),
        }

    def _load_mouse_movement_profile_from_payload(self, payload: object) -> MouseMovementProfile:
        if not isinstance(payload, dict):
            return MouseMovementProfile()

        raw_curve = payload.get("duration_curve", MouseMovementProfile().duration_curve)
        duration_curve: list[tuple[int, int]] = []
        if isinstance(raw_curve, list):
            for point in raw_curve:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    continue
                try:
                    duration_curve.append((int(point[0]), int(point[1])))
                except (TypeError, ValueError):
                    continue

        min_steps = max(1, int(payload.get("min_steps", 1))) if "min_steps" in payload else 1
        max_steps = (
            max(min_steps, int(payload.get("max_steps", 120)))
            if "max_steps" in payload
            else 120
        )

        kwargs: dict[str, object] = {}
        if duration_curve:
            kwargs["duration_curve"] = tuple(duration_curve)
        kwargs["min_steps"] = min_steps
        kwargs["max_steps"] = max_steps
        if "step_distance_px" in payload:
            kwargs["step_distance_px"] = max(1, int(payload.get("step_distance_px", 8)))
        return MouseMovementProfile(**kwargs)

    def _serialize_recording_settings(
        self,
        settings: DesktopRecordingSettings,
    ) -> dict[str, object]:
        return {
            "recording_conversion_mode": settings.recording_conversion_mode,
            "capture_mouse_moves": bool(settings.capture_mouse_moves),
            "capture_mouse_buttons": bool(settings.capture_mouse_buttons),
            "capture_mouse_wheel": bool(settings.capture_mouse_wheel),
            "capture_keyboard": bool(settings.capture_keyboard),
            "mouse_move_threshold_px": max(0, int(settings.mouse_move_threshold_px)),
            "exclude_main_window_during_recording": bool(
                settings.exclude_main_window_during_recording
            ),
        }

    def _serialize_files_settings(
        self,
        settings: DesktopFilesSettings,
    ) -> dict[str, object]:
        return {
            "file_extension": settings.file_extension,
            "autosave_enabled": bool(settings.autosave_enabled),
            "autosave_file_name": settings.autosave_file_name,
            "autosave_timestamp_suffix": bool(settings.autosave_timestamp_suffix),
            "autosave_output_folder": settings.autosave_output_folder,
            "raw_autosave_enabled": bool(settings.raw_autosave_enabled),
            "raw_autosave_file_name": settings.raw_autosave_file_name,
            "raw_autosave_timestamp_suffix": bool(settings.raw_autosave_timestamp_suffix),
            "raw_autosave_output_folder": settings.raw_autosave_output_folder,
            "diagnostic_log_path": settings.diagnostic_log_path,
        }

    def _serialize_diagnostics_settings(
        self,
        settings: DesktopDiagnosticsSettings,
    ) -> dict[str, object]:
        return {
            "enabled": bool(settings.enabled),
            "min_severity": str(settings.min_severity),
            "max_detail": str(settings.max_detail),
            "log_to_file": bool(settings.log_to_file),
            "log_to_stdout": bool(settings.log_to_stdout),
        }

    @staticmethod
    def _normalize_recording_conversion_mode(value: object) -> str:
        mode = str(value or "promote_generated")
        if mode not in {"promote_generated", "direct_import"}:
            return "promote_generated"
        return mode

    def _serialize_runtime_settings(
        self,
        settings: DesktopRuntimeSettings,
    ) -> dict[str, object]:
        return {
            "max_loop_iterations": max(1, int(settings.max_loop_iterations)),
            "max_call_depth": max(1, int(settings.max_call_depth)),
            "default_mouse_move_speed": max(0, min(100, int(settings.default_mouse_move_speed))),
            "show_mouse_movement_reference_curve": bool(
                settings.show_mouse_movement_reference_curve
            ),
            "mouse_movement_profile": {
                "duration_curve": [
                    [int(speed), int(duration_ms)]
                    for speed, duration_ms in settings.mouse_movement_profile.duration_curve
                ],
                "min_steps": max(1, int(settings.mouse_movement_profile.min_steps)),
                "max_steps": max(
                    max(1, int(settings.mouse_movement_profile.min_steps)),
                    int(settings.mouse_movement_profile.max_steps),
                ),
                "step_distance_px": max(1, int(settings.mouse_movement_profile.step_distance_px)),
            },
        }

    def _serialize_theme_settings(self, preferences: DesktopPreferences) -> dict[str, object]:
        return {
            "appearance": asdict(preferences.appearance),
            "scripting": asdict(preferences.scripting),
            "font": asdict(preferences.font),
            "search_results": asdict(preferences.search_results),
        }

    def _load_scripting_settings_from_payload(
        self,
        payload: object,
        *,
        fallback: object,
    ) -> ScriptingSettings:
        if isinstance(payload, dict) and payload:
            source = payload
        elif isinstance(fallback, dict):
            source = fallback
        else:
            source = {}
        return ScriptingSettings(
            language=str(source.get("language", "ActionShellScript")),
            indent_width=int(source.get("indent_width", 4)),
            use_spaces=bool(source.get("use_spaces", True)),
            auto_indent=bool(source.get("auto_indent", True)),
            auto_format_on_save=bool(source.get("auto_format_on_save", False)),
        )

    def _load_hotkey_settings(self, payload: object) -> DesktopHotkeySettings:
        bindings = default_hotkey_bindings()
        if not isinstance(payload, dict):
            return DesktopHotkeySettings(bindings=bindings)
        raw_bindings = payload.get("bindings", {})
        if isinstance(raw_bindings, dict):
            for action_id, shortcut in raw_bindings.items():
                canonical_action_id = str(action_id)
                if canonical_action_id == "run":
                    canonical_action_id = "play"
                if canonical_action_id == "search":
                    canonical_action_id = "find"
                bindings[canonical_action_id] = str(shortcut)
        return DesktopHotkeySettings(bindings=bindings)

    @property
    def _legacy_application_settings_path(self) -> Path:
        return self._config_dir / "application_settings.json"

    def _load_legacy_application_settings(self) -> DesktopApplicationSettings:
        if not self._legacy_application_settings_path.exists():
            return DesktopApplicationSettings()
        payload = self._load_settings_payload(self._legacy_application_settings_path)
        return self._load_application_settings_from_payload(payload)
