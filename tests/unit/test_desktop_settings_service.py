from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from application.persistence.desktop_settings_service import DesktopSettingsService
from application.persistence.persistence_errors import PersistenceLoadError, PersistenceSaveError
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
    validate_desktop_preferences_readability,
)
from infrastructure.input.mouse_movement_profile import MouseMovementProfile


def test_desktop_settings_service_defaults_to_config_subdirectory(
    monkeypatch,
    tmp_path,
) -> None:
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))

    service = DesktopSettingsService()

    assert service.config_dir == appdata / "ActionShellScript" / "config"
    assert service.settings_path == Path(
        appdata / "ActionShellScript" / "config" / "desktop_settings.json"
    )


def test_playback_settings_expose_runtime_special_values() -> None:
    settings = DesktopPlaybackSettings(
        repeat_count=3,
        step_mode=True,
        delay_ms=125,
        mouse_settle_ms=17,
        interruptible_sleep_chunk_ms=25,
    )

    assert settings.runtime_special_values() == {
        "PlaybackRepeatCount": 3,
        "PlaybackEventPause": True,
        "PlaybackEventDelay": 125,
        "PlaybackMouseSettle": 17,
        "PlaybackSendKeyTapsInsteadOfText": False,
    }


def test_desktop_settings_service_round_trips_unified_settings_file_with_legacy_zero_boundary_curve(
    tmp_path,
) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            restore_last_workspace=True,
            open_debug_tab_on_pause=True,
            show_analysis_tab=False,
            show_debug_tab=False,
            show_formatted_preview_tab=False,
            show_raw_recordings_tab=False,
            show_diagnostics_tab=True,
            hidden_workspace_tabs_strip_collapsed=True,
            last_workspace_path=r"C:\temp\sample.ass",
            last_open_directory=r"C:\temp\workspace",
            go_to_last_mode="offset",
            go_to_last_value=42,
            go_to_last_geometry=base64.b64encode(b"fake-go-to-geometry").decode("ascii"),
            hotkeys=DesktopHotkeySettings(
                bindings={"save": "Ctrl+Shift+S", "preferences": "Ctrl+Alt+P"}
            ),
        ),
        playback=DesktopPlaybackSettings(
            repeat_count=3,
            step_mode=True,
            delay_ms=125,
            mouse_settle_ms=17,
            interruptible_sleep_chunk_ms=25,
            send_key_taps_instead_of_text=True,
        ),
        recording=DesktopRecordingSettings(
            recording_conversion_mode="direct_import",
            capture_mouse_moves=False,
            capture_mouse_buttons=True,
            capture_mouse_wheel=False,
            capture_keyboard=True,
            mouse_move_threshold_px=12,
            exclude_main_window_during_recording=False,
        ),
        files=DesktopFilesSettings(
            file_extension=".foo",
            autosave_enabled=True,
            autosave_file_name="recording",
            autosave_timestamp_suffix=True,
            autosave_output_folder=r"C:\temp\recordings",
            raw_autosave_enabled=True,
            raw_autosave_file_name="raw_recording",
            raw_autosave_timestamp_suffix=False,
            raw_autosave_output_folder=r"C:\temp\raw-recordings",
            diagnostic_log_path=r"C:\temp\diagnostics\desktop.log",
        ),
        diagnostics=DesktopDiagnosticsSettings(
            enabled=True,
            min_severity="debug",
            max_detail="trace",
            log_to_file=True,
            log_to_stdout=True,
        ),
        runtime=DesktopRuntimeSettings(
            max_loop_iterations=321,
            max_call_depth=45,
            default_mouse_move_speed=18,
            show_mouse_movement_reference_curve=False,
            # Legacy compatibility coverage: keep a zero-speed point here to verify
            # older persisted settings still round-trip correctly. This is not the
            # preferred/default editor curve shape.
            mouse_movement_profile=MouseMovementProfile(
                duration_curve=((0, 0), (25, 400), (100, 80)),
                min_steps=2,
                max_steps=40,
                step_distance_px=4,
            ),
        ),
        theme=DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(
                    background="#101820",
                    text="#f5f7fa",
                    gutter_background="#22303c",
                    gutter_text="#f5f7fa",
                    current_line_foreground="#112233",
                    current_line_highlight="#ffeeaa",
                ),
                syntax_highlighting=SyntaxHighlightTheme(
                    keyword="#112233",
                    string="#223344",
                    comment="#334455",
                    number="#445566",
                ),
                dirty_indicators=DirtyIndicatorTheme(
                    text="#aa5500",
                    accent="#cc7700",
                    background="#fff0d9",
                    selected_background="#ffd699",
                    border="#e6b870",
                ),
                workspace_tab_attention=WorkspaceTabAttentionTheme(
                    enabled=False,
                    accent="#3366cc",
                ),
            ),
            scripting=ScriptingSettings(
                language="Custom",
                indent_width=2,
                use_spaces=False,
                auto_format_on_save=True,
            ),
            font=FontSettings(
                family="Courier New",
                size=13,
                weight=600,
                line_spacing_multiplier=1.25,
            ),
            search_results=SearchResultsTheme(
                header_active="#ddeeff",
                child_border_color="#334455",
            ),
        ),
    )

    service.save(bundle, force=True)
    loaded = service.load()
    payload = service.settings_path.read_text(encoding="utf-8")

    assert service.settings_path.exists()
    assert service.application_settings_path == service.theme_settings_path == service.settings_path
    assert loaded.application.restore_last_workspace is True
    assert loaded.application.open_debug_tab_on_pause is True
    assert loaded.application.show_analysis_tab is False
    assert loaded.application.show_debug_tab is False
    assert loaded.application.show_formatted_preview_tab is False
    assert loaded.application.show_raw_recordings_tab is False
    assert loaded.application.show_diagnostics_tab is True
    assert loaded.application.hidden_workspace_tabs_strip_collapsed is True
    assert loaded.application.last_workspace_path == r"C:\temp\sample.ass"
    assert loaded.application.last_open_directory == r"C:\temp\workspace"
    assert loaded.application.go_to_last_mode == "offset"
    assert loaded.application.go_to_last_value == 42
    assert loaded.application.go_to_last_geometry == base64.b64encode(b"fake-go-to-geometry").decode("ascii")
    assert loaded.application.hotkeys.bindings["save"] == "Ctrl+Shift+S"
    application_payload = json.loads(payload)["application"]
    assert application_payload["open_debug_tab_on_pause"] is True
    assert application_payload["show_analysis_tab"] is False
    assert application_payload["show_debug_tab"] is False
    assert application_payload["show_raw_recordings_tab"] is False
    assert application_payload["show_diagnostics_tab"] is True
    assert application_payload["hidden_workspace_tabs_strip_collapsed"] is True
    assert application_payload["go_to_last_mode"] == "offset"
    assert application_payload["go_to_last_value"] == 42
    assert application_payload["go_to_last_geometry"] == base64.b64encode(b"fake-go-to-geometry").decode("ascii")
    theme_payload = json.loads(payload)["theme"]["appearance"]["workspace_tab_attention"]
    assert theme_payload["enabled"] is False
    assert theme_payload["accent"] == "#3366cc"
    assert loaded.application.hotkeys.bindings["preferences"] == "Ctrl+Alt+P"
    assert loaded.application.hotkeys.bindings["play"] == "Ctrl+Enter"
    assert loaded.application.hotkeys.bindings["record"] == "Ctrl+Shift+R"
    assert loaded.application.hotkeys.bindings["stop"] == "Shift+Esc"
    assert loaded.playback.repeat_count == 3
    assert loaded.playback.step_mode is True
    assert loaded.playback.delay_ms == 125
    assert loaded.playback.mouse_settle_ms == 17
    assert loaded.playback.interruptible_sleep_chunk_ms == 25
    assert loaded.playback.send_key_taps_instead_of_text is True
    assert json.loads(payload)["playback"]["interruptible_sleep_chunk_ms"] == 25
    assert loaded.runtime.mouse_movement_profile.duration_curve == ((0, 0), (25, 400), (100, 80))
    assert loaded.runtime.mouse_movement_profile.min_steps == 2
    assert loaded.runtime.mouse_movement_profile.max_steps == 40
    assert loaded.runtime.mouse_movement_profile.step_distance_px == 4
    assert loaded.recording.capture_mouse_moves is False
    assert loaded.recording.capture_mouse_buttons is True
    assert loaded.recording.capture_mouse_wheel is False
    assert loaded.recording.capture_keyboard is True
    assert loaded.recording.recording_conversion_mode == "direct_import"
    assert loaded.recording.mouse_move_threshold_px == 12
    assert loaded.recording.exclude_main_window_during_recording is False
    assert loaded.files.file_extension == ".foo"
    assert loaded.files.autosave_enabled is True
    assert loaded.files.autosave_file_name == "recording"
    assert loaded.files.autosave_timestamp_suffix is True
    assert loaded.files.autosave_output_folder == r"C:\temp\recordings"
    assert loaded.files.raw_autosave_enabled is True
    assert loaded.files.raw_autosave_file_name == "raw_recording"
    assert loaded.files.raw_autosave_timestamp_suffix is False
    assert loaded.files.raw_autosave_output_folder == r"C:\temp\raw-recordings"
    assert loaded.files.diagnostic_log_path == r"C:\temp\diagnostics\desktop.log"
    assert loaded.diagnostics.enabled is True
    assert loaded.diagnostics.min_severity == "debug"
    assert loaded.diagnostics.max_detail == "trace"
    assert loaded.diagnostics.log_to_file is True
    assert loaded.diagnostics.log_to_stdout is True
    assert loaded.runtime.max_loop_iterations == 321
    assert loaded.runtime.max_call_depth == 45
    assert loaded.runtime.default_mouse_move_speed == 18
    assert loaded.runtime.show_mouse_movement_reference_curve is False
    assert loaded.theme.appearance.editor.background == "#101820"
    assert loaded.theme.appearance.editor.current_line_foreground == "#112233"
    assert loaded.theme.appearance.editor.current_line_highlight == "#ffeeaa"
    assert loaded.theme.appearance.syntax_highlighting.keyword == "#112233"
    assert loaded.theme.appearance.syntax_highlighting.number == "#445566"
    assert loaded.theme.appearance.dirty_indicators.accent == "#cc7700"
    assert loaded.theme.appearance.dirty_indicators.border == "#e6b870"
    assert loaded.theme.appearance.workspace_tab_attention.enabled is False
    assert loaded.theme.appearance.workspace_tab_attention.accent == "#3366cc"
    assert loaded.theme.scripting.language == "Custom"
    assert loaded.theme.scripting.indent_width == 2
    assert loaded.theme.scripting.use_spaces is False
    assert loaded.theme.scripting.auto_indent is True
    assert loaded.theme.scripting.auto_format_on_save is True
    assert loaded.theme.font.family == "Courier New"
    assert loaded.theme.font.size == 13
    assert loaded.theme.font.weight == 600
    assert loaded.theme.font.line_spacing_multiplier == 1.25
    assert loaded.theme.search_results.header_active == "#ddeeff"
    assert loaded.theme.search_results.child_border_color == "#334455"
    payload_json = json.loads(payload)
    assert "application" in payload_json
    assert "playback" in payload_json
    assert "mouse_movement_profile" not in payload_json["playback"]
    assert payload_json["application"]["last_open_directory"] == r"C:\temp\workspace"
    assert payload_json["runtime"]["mouse_movement_profile"]["duration_curve"] == [
        [0, 0],
        [25, 400],
        [100, 80],
    ]
    assert payload_json["runtime"]["show_mouse_movement_reference_curve"] is False
    assert payload_json["runtime"]["mouse_movement_profile"]["min_steps"] == 2
    assert payload_json["runtime"]["mouse_movement_profile"]["max_steps"] == 40
    assert payload_json["runtime"]["mouse_movement_profile"]["step_distance_px"] == 4
    assert payload_json["theme"]["scripting"]["auto_indent"] is True
    assert payload_json["theme"]["search_results"]["header_active"] == "#ddeeff"
    assert "recording" in payload_json
    assert "runtime" in payload_json
    assert "theme" in payload_json
    assert "files" in payload_json
    assert "autosave_enabled" in payload
    assert "recording_conversion_mode" in payload
    assert "autosave_file_name" in payload
    assert "autosave_timestamp_suffix" in payload
    assert "raw_autosave_enabled" in payload
    assert "raw_autosave_file_name" in payload
    assert "raw_autosave_timestamp_suffix" in payload
    assert "raw_autosave_output_folder" in payload
    assert "diagnostic_log_path" in payload
    assert "diagnostics" in payload_json
    assert payload_json["diagnostics"]["enabled"] is True
    assert payload_json["diagnostics"]["min_severity"] == "debug"
    assert payload_json["diagnostics"]["max_detail"] == "trace"
    assert payload_json["diagnostics"]["log_to_file"] is True
    assert payload_json["diagnostics"]["log_to_stdout"] is True
    assert payload_json["recording"]["exclude_main_window_during_recording"] is False
    assert "scripting" in payload_json["theme"]
    assert "runtime" not in payload_json["theme"]
    assert payload_json["files"]["file_extension"] == ".foo"
    assert payload_json["files"]["diagnostic_log_path"] == r"C:\temp\diagnostics\desktop.log"
    assert "diagnostic_log_path" not in payload_json["runtime"]


def test_desktop_settings_service_round_trips_last_open_directory_without_touching_defaults(
    tmp_path,
) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            last_open_directory=r"C:\temp\workspace",
        )
    )

    service.save(bundle, force=True)
    loaded = service.load()
    payload_json = json.loads(service.settings_path.read_text(encoding="utf-8"))

    assert loaded.application.last_open_directory == r"C:\temp\workspace"
    assert payload_json["application"]["last_open_directory"] == r"C:\temp\workspace"
    assert loaded.application.restore_last_workspace is False
    assert loaded.application.open_debug_tab_on_pause is True
    assert loaded.application.show_debug_tab is True
    assert loaded.application.last_workspace_path is None


def test_desktop_settings_service_reports_existing_targets_after_save(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    service.save(DesktopSettingsBundle(), force=True)

    requirements = service.save_requirements()

    assert len(requirements) == 1
    assert requirements[0][0] == service.settings_path
    assert requirements[0][1].requires_save is True


def test_desktop_settings_service_rejects_conflicting_hotkeys(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={
                    "new": "Ctrl+N",
                    "open": "Ctrl+N",
                }
            )
        )
    )

    with pytest.raises(PersistenceSaveError, match="hotkey conflicts"):
        service.save(bundle, force=True)

    assert not service.settings_path.exists()


def test_desktop_settings_service_migrates_legacy_run_hotkey_to_play(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    service._legacy_application_settings_path.parent.mkdir(parents=True, exist_ok=True)
    service._legacy_application_settings_path.write_text(
        '{"restore_last_workspace": false, "last_workspace_path": null, "hotkeys": {"bindings": {"run": "Ctrl+Enter", "stop": "Shift+Esc"}}}',
        encoding="utf-8",
    )

    loaded = service.load()
    migrated_payload = service.settings_path.read_text(encoding="utf-8")

    assert loaded.application.hotkeys.bindings["play"] == "Ctrl+Enter"
    assert "run" not in loaded.application.hotkeys.bindings
    assert loaded.application.open_debug_tab_on_pause is True
    assert loaded.application.show_debug_tab is True
    assert loaded.application.show_formatted_preview_tab is True
    assert loaded.application.show_raw_recordings_tab is False
    assert loaded.application.show_diagnostics_tab is False
    assert service.settings_path.exists()
    assert loaded.theme.appearance.syntax_highlighting.keyword == "#005cc5"
    assert loaded.runtime.max_loop_iterations == 100000
    assert loaded.runtime.max_call_depth == 250
    assert loaded.runtime.default_mouse_move_speed == 10
    assert loaded.theme.scripting.language == "ActionShellScript"
    assert loaded.theme.font.weight == 400
    assert loaded.theme.font.line_spacing_multiplier == 1.0
    migrated_json = json.loads(migrated_payload)
    assert "application" in migrated_json
    assert "theme" in migrated_json


def test_desktop_settings_service_migrates_legacy_search_hotkey_to_find(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    service._legacy_application_settings_path.parent.mkdir(parents=True, exist_ok=True)
    service._legacy_application_settings_path.write_text(
        '{"restore_last_workspace": false, "last_workspace_path": null, "hotkeys": {"bindings": {"search": "Ctrl+Alt+F", "stop": "Shift+Esc"}}}',
        encoding="utf-8",
    )

    loaded = service.load()

    assert loaded.application.hotkeys.bindings["find"] == "Ctrl+Alt+F"
    assert "search" not in loaded.application.hotkeys.bindings


def test_desktop_settings_service_migrates_diagnostic_log_path_to_files(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    service.settings_path.parent.mkdir(parents=True, exist_ok=True)
    service.settings_path.write_text(
        json.dumps(
            {
                "application": {},
                "playback": {},
                "recording": {},
                "files": {},
                "runtime": {
                    "max_loop_iterations": 123,
                    "max_call_depth": 45,
                    "default_mouse_move_speed": 19,
                    "diagnostic_log_path": r"C:\temp\diagnostics\legacy.log",
                },
                "theme": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = service.load()

    assert loaded.files.diagnostic_log_path == r"C:\temp\diagnostics\legacy.log"
    assert loaded.runtime.max_loop_iterations == 123
    assert loaded.runtime.max_call_depth == 45
    assert loaded.runtime.default_mouse_move_speed == 19


def test_desktop_settings_service_loads_legacy_theme_runtime_in_desktop_settings_file(
    tmp_path,
) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    legacy_payload = {
        "application": {},
        "playback": {},
        "recording": {},
        "runtime": {},
        "theme": {
            "appearance": {
                "editor": {
                    "background": "#101820",
                    "text": "#f5f7fa",
                    "gutter_background": "#22303c",
                    "gutter_text": "#f5f7fa",
                    "current_line_foreground": "#112233",
                    "current_line_highlight": "#ffeeaa",
                },
                "syntax_highlighting": {
                    "keyword": "#112233",
                    "string": "#223344",
                    "comment": "#334455",
                    "number": "#445566",
                },
                "dirty_indicators": {
                    "text": "#aa5500",
                    "accent": "#cc7700",
                    "background": "#fff0d9",
                    "selected_background": "#ffd699",
                    "border": "#e6b870",
                },
            },
            "runtime": {
                "language": "Custom",
                "file_extension": ".foo",
                "indent_width": 2,
                "use_spaces": False,
                "auto_format_on_save": True,
            },
            "font": {"family": "Courier New", "size": 13},
        },
    }
    service.settings_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    loaded = service.load()

    assert loaded.theme.scripting.language == "Custom"
    assert loaded.theme.scripting.indent_width == 2
    assert loaded.theme.scripting.use_spaces is False
    assert loaded.theme.scripting.auto_indent is True
    assert loaded.theme.scripting.auto_format_on_save is True
    assert loaded.theme.appearance.workspace_tab_attention == WorkspaceTabAttentionTheme()
    assert loaded.application.hidden_workspace_tabs_strip_collapsed is True


def test_desktop_preferences_readability_validator_flags_low_contrast_scheme() -> None:
    issues = validate_desktop_preferences_readability(
        DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(
                    background="#ffffff",
                    text="#ffffff",
                    gutter_background="#ffffff",
                    gutter_text="#ffffff",
                    current_line_foreground="#ffffff",
                    current_line_highlight="#ffffff",
                ),
                syntax_highlighting=SyntaxHighlightTheme(
                    keyword="#ffffff",
                    string="#ffffff",
                    comment="#ffffff",
                    number="#ffffff",
                ),
                dirty_indicators=DirtyIndicatorTheme(
                    text="#ffffff",
                    accent="#ffffff",
                    background="#ffffff",
                    selected_background="#ffffff",
                    border="#ffffff",
                ),
            ),
            search_results=SearchResultsTheme(
                header_active="#ffffff",
                header_hovered="#ffffff",
                header_active_hovered="#ffffff",
                header_text="#ffffff",
                line_text="#ffffff",
                hit_text="#ffffff",
                child_border_color="#ffffff",
            ),
        )
    )

    assert issues
    assert any("Editor text" in issue for issue in issues)
    assert any("Keyword color" in issue for issue in issues)
    assert any("Search-results header text" in issue for issue in issues)


def test_desktop_settings_service_wraps_invalid_json_load_errors(tmp_path) -> None:
    service = DesktopSettingsService(config_dir=tmp_path)
    service.settings_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(PersistenceLoadError):
        service.load()
