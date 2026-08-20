from __future__ import annotations

import os
import time
import tempfile
import threading
from pathlib import Path
from datetime import datetime as real_datetime
from typing import Protocol, TypeVar, cast, TypedDict
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QDialog,
    QDockWidget,
    QLayout,
    QRadioButton,
    QPushButton,
    QLineEdit,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QTabBar,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, QRect  # noqa: E402
from PySide6.QtGui import QCloseEvent, QKeySequence, QTextCursor  # noqa: E402
from PySide6.QtTest import QSignalSpy, QTest  # noqa: E402
from PySide6.QtWidgets import QFileDialog, QMessageBox  # noqa: E402

from apps.desktop.document_status_dialog import DocumentStatusDialog
from apps.desktop.documentation_messages import ass_help_fallback_status
from apps.desktop.window import ActionShellScriptDesktopWindow, DesktopServices, SearchCriteria
from application.debugging_service import DebugRunHandle
from application.script_document_language_service import ScriptDocumentLanguageService  # noqa: E402
from application.script_document_service import ScriptDocumentService  # noqa: E402
import apps.desktop.window as desktop_window_module  # noqa: E402
from apps.desktop.settings import (  # noqa: E402
    DesktopApplicationSettings,
    DesktopDiagnosticsSettings,
    DesktopFilesSettings,
    DesktopHotkeySettings,
    DesktopPlaybackSettings,
    DesktopRecordingSettings,
    DesktopSettingsBundle,
    DesktopRuntimeSettings,
)
from application.persistence.desktop_settings_service import DesktopSettingsService  # noqa: E402
from apps.desktop.theme import (  # noqa: E402
    AppearanceTheme,
    DesktopPreferences,
    DirtyIndicatorTheme,
    EditorAppearanceTheme,
    SearchResultsTheme,
    ScriptingSettings,
    WorkspaceTabAttentionTheme,
)
from apps.desktop.presentation import build_raw_recording_text  # noqa: E402
from application.playback_service import PlaybackService  # noqa: E402
from core.debugging.debug_event import DebugEvent  # noqa: E402
from core.scripting.diagnostics import TextSpan  # noqa: E402
from core.recording.recording_session import RecordingSession, RecordingState  # noqa: E402
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder  # noqa: E402
from core.playback.playback_mode import PlaybackMode  # noqa: E402
from core.playback.executors.preview_input_executor import PreviewInputExecutor  # noqa: E402
from core.playback.playback_builder import PlaybackBuilder  # noqa: E402
from core.playback.playback_engine import PlaybackEngine  # noqa: E402
from core.playback.playback_result import PlaybackResult  # noqa: E402
from core.runtime.script_runtime import ScriptRuntime  # noqa: E402
from core.runtime.struct_values import StructInstance  # noqa: E402
from editor.document.script_document import ScriptDocument  # noqa: E402
from editor.document.script_document import build_recording_provenance_header  # noqa: E402
from editor.language_services.formatting_service import FormattingService  # noqa: E402
import infrastructure.debug_logger as debug_logger  # noqa: E402
from infrastructure.persistence.script_document_file_store import ScriptDocumentFileStore  # noqa: E402

TWidget = TypeVar("TWidget", bound=QWidget)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _new_window(*, config_dir: Path | None = None) -> ActionShellScriptDesktopWindow:
    temp_dir = None
    should_patch_settings_service = config_dir is not None or (
        desktop_window_module.DesktopSettingsService is DesktopSettingsService
    )
    if should_patch_settings_service and config_dir is None:
        temp_dir = tempfile.TemporaryDirectory()
        config_dir = Path(temp_dir.name)
    if should_patch_settings_service:
        with patch.object(
            desktop_window_module,
            "DesktopSettingsService",
            lambda: DesktopSettingsService(config_dir=config_dir),
        ):
            window = ActionShellScriptDesktopWindow(
                services=DesktopServices(
                    document_service=ScriptDocumentService(),
                    language_service=ScriptDocumentLanguageService(),
                    formatting_service=FormattingService(),
                    document_store=ScriptDocumentFileStore(),
                )
            )
    else:
        window = ActionShellScriptDesktopWindow(
            services=DesktopServices(
                document_service=ScriptDocumentService(),
                language_service=ScriptDocumentLanguageService(),
                formatting_service=FormattingService(),
                document_store=ScriptDocumentFileStore(),
            )
        )
    window._test_settings_tempdir = temp_dir
    window.committed_settings_bundle.files = DesktopFilesSettings()
    return window


def _layout_widget_at(layout: QLayout | None, index: int) -> QWidget:
    assert layout is not None
    item = layout.itemAt(index)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget


def _required_top_level_item(tree: QTreeWidget, index: int) -> QTreeWidgetItem:
    item = tree.topLevelItem(index)
    assert item is not None
    return item


def _debug_handle(handle: object) -> DebugRunHandle:
    return cast(DebugRunHandle, handle)


class _AboutCapture(TypedDict, total=False):
    title: str
    body_text: str
    info_text: str
    extra_text: str
    info_icon_is_null: bool
    frog_icon_is_null: bool
    session_id: str
    recording_settings: DesktopRecordingSettings


class _PixelInspectorWindowLike(Protocol):
    parent: object | None
    calls: list[str]

    def show(self) -> None: ...

    def raise_(self) -> None: ...

    def activateWindow(self) -> None: ...


class _ScriptCall(TypedDict):
    kind: str
    payload: object
    mode: str | None


def _required_child(parent: QWidget, child_type: type[TWidget], name: str) -> TWidget:
    child = parent.findChild(child_type, name)
    assert child is not None
    return child


def _combo_line_edit(combo: QComboBox) -> QLineEdit:
    line_edit = combo.lineEdit()
    assert line_edit is not None
    return line_edit


def _use_real_script_playback_service(window: ActionShellScriptDesktopWindow, monkeypatch) -> None:
    def fake_build_playback_service(_stop_event, *, mode):
        runtime = ScriptRuntime()
        return PlaybackService(
            builder=PlaybackBuilder(
                from_script=PlaybackPlanFromScriptBuilder(runtime=runtime),
            ),
            live_engine=PlaybackEngine(PreviewInputExecutor()),
            preview_engine=PlaybackEngine(PreviewInputExecutor()),
        )

    monkeypatch.setattr(window.script_controller, "_build_playback_service", fake_build_playback_service)


def _run_smoke_script_and_get_playback_output(
    window: ActionShellScriptDesktopWindow,
    script_text: str,
    *,
    app: QApplication,
) -> str:
    window.editor.setPlainText(script_text)
    app.processEvents()

    assert window.play_script() is True
    thread = window.script_controller._script_operation_thread
    assert thread is not None
    deadline = time.monotonic() + 2.0
    while thread.is_alive() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    thread.join(timeout=1.0)
    window.script_controller._poll_script_operation()

    return window.playback_output_view.toPlainText()


def _open_replace_sidebar(
    window: ActionShellScriptDesktopWindow,
    *,
    find_text: str,
    replace_text: str,
    search_mode: str = "normal",
) -> tuple[QPushButton, QPushButton]:
    window.replace_action.trigger()
    widgets = window._find_sidebar_widgets
    assert widgets is not None
    assert widgets.tab_widget.currentIndex() == 1

    replace_page = widgets.pages["replace"]
    _combo_line_edit(replace_page.find_combo).setText(find_text)
    assert replace_page.replace_combo is not None
    _combo_line_edit(replace_page.replace_combo).setText(replace_text)

    replace_page.normal_radio.setChecked(search_mode == "normal")
    replace_page.extended_radio.setChecked(search_mode == "extended")
    replace_page.regex_radio.setChecked(search_mode == "regex")
    replace_button = widgets.replace_button
    assert replace_button is not None
    replace_all_button = widgets.replace_all_button
    assert replace_all_button is not None
    return replace_button, replace_all_button


def _open_find_sidebar(
    window: ActionShellScriptDesktopWindow,
    *,
    find_text: str,
    search_mode: str = "normal",
) -> tuple[QPushButton, QPushButton]:
    window.find_action.trigger()
    widgets = window._find_sidebar_widgets
    assert widgets is not None
    assert widgets.tab_widget.currentIndex() == 0

    find_page = widgets.pages["find"]
    _combo_line_edit(find_page.find_combo).setText(find_text)

    find_page.normal_radio.setChecked(search_mode == "normal")
    find_page.extended_radio.setChecked(search_mode == "extended")
    find_page.regex_radio.setChecked(search_mode == "regex")
    find_previous_button = widgets.find_previous_button
    assert find_previous_button is not None
    find_next_button = widgets.find_next_button
    assert find_next_button is not None
    return find_previous_button, find_next_button


def _assert_find_all_results_tree_active_match(
    window: ActionShellScriptDesktopWindow,
    *,
    expected_line_label: str,
    expected_start: int,
    expected_end: int,
) -> None:
    widgets = window._find_sidebar_widgets
    assert widgets is not None

    current_item = widgets.results_tree.currentItem()
    assert current_item is not None
    payload = current_item.data(0, Qt.ItemDataRole.UserRole)
    assert isinstance(payload, dict)
    assert payload["start"] == expected_start
    assert payload["end"] == expected_end

    parent_item = current_item.parent()
    assert parent_item is not None
    assert parent_item.text(0) == expected_line_label
    assert parent_item.isExpanded() is True

    for index in range(widgets.results_tree.topLevelItemCount()):
        top_item = widgets.results_tree.topLevelItem(index)
        assert top_item is not None
        if top_item.text(0) == expected_line_label:
            assert top_item.isExpanded() is True
        else:
            assert top_item.isExpanded() is False


def test_desktop_window_module_exports_window_class() -> None:
    assert ActionShellScriptDesktopWindow.__name__ == "ActionShellScriptDesktopWindow"
    assert DesktopServices.__name__ == "DesktopServices"


def test_desktop_window_uses_more_compact_default_sizing() -> None:
    _app()

    window = _new_window()

    assert "ActionShellScript combo box readability fix" in _app().styleSheet()
    assert window.size().width() == 1360
    assert window.size().height() == 840
    assert window.minimumWidth() == 1040
    assert window.minimumHeight() == 700


def test_desktop_window_hides_formatted_preview_tab_from_preferences() -> None:
    _app()

    window = _new_window()
    base_bundle = window.committed_settings_bundle
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    assert preview_index >= 0
    window.workspace_tabs.setCurrentIndex(preview_index)

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                show_formatted_preview_tab=False,
            ),
            playback=base_bundle.playback,
            recording=base_bundle.recording,
            runtime=base_bundle.runtime,
            theme=base_bundle.theme,
        )
    )

    assert window.workspace_tabs.isTabVisible(preview_index) is False
    assert window.workspace_tabs.currentIndex() == 0

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                show_formatted_preview_tab=True,
            ),
            playback=base_bundle.playback,
            recording=base_bundle.recording,
            runtime=base_bundle.runtime,
            theme=base_bundle.theme,
        )
    )

    assert window.workspace_tabs.isTabVisible(preview_index) is True


def test_desktop_window_hides_workspace_tabs_from_preferences() -> None:
    _app()

    window = _new_window()
    base_bundle = window.committed_settings_bundle
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    raw_index = window.workspace_tabs.indexOf(window.raw_recording_view)
    diagnostics_index = window.workspace_tabs.indexOf(window.diagnostics_tab)
    assert preview_index >= 0
    assert raw_index >= 0
    assert diagnostics_index >= 0
    window.workspace_tabs.setCurrentIndex(diagnostics_index)

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                show_debug_tab=False,
                show_formatted_preview_tab=False,
                show_raw_recordings_tab=False,
                show_diagnostics_tab=False,
            ),
            playback=base_bundle.playback,
            recording=base_bundle.recording,
            runtime=base_bundle.runtime,
            theme=base_bundle.theme,
        )
    )

    assert window.workspace_tabs.isTabVisible(preview_index) is False
    assert window.workspace_tabs.isTabVisible(raw_index) is False
    assert window.workspace_tabs.isTabVisible(diagnostics_index) is False
    assert window.sidebar_mode_buttons["debug"].isHidden() is True
    assert window.workspace_tabs.isTabVisible(window.workspace_tabs.currentIndex()) is True

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                show_debug_tab=True,
                show_formatted_preview_tab=True,
                show_raw_recordings_tab=True,
                show_diagnostics_tab=True,
            ),
            playback=base_bundle.playback,
            recording=base_bundle.recording,
            runtime=base_bundle.runtime,
            theme=base_bundle.theme,
        )
    )

    assert window.workspace_tabs.isTabVisible(preview_index) is True
    assert window.workspace_tabs.isTabVisible(raw_index) is True
    assert window.workspace_tabs.isTabVisible(diagnostics_index) is True
    assert window.sidebar_mode_buttons["debug"].isHidden() is False


def test_desktop_window_can_hide_and_restore_workspace_tabs_from_close_request() -> None:
    _app()

    window = _new_window()
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    assert preview_index >= 0
    assert window.workspace_tabs.isTabVisible(preview_index) is True

    window.workspace_tabs.tabCloseRequested.emit(preview_index)

    assert window.workspace_tabs.isTabVisible(preview_index) is False
    assert window.hidden_workspace_tabs_strip.isHidden() is False
    restore_button = _required_child(window, QToolButton, "restoreFormattedPreviewTabButton")

    restore_button.click()

    assert window.workspace_tabs.isTabVisible(preview_index) is True
    assert window.hidden_workspace_tabs_strip.isHidden() is False


def test_desktop_window_can_collapse_and_expand_hidden_workspace_tabs_strip() -> None:
    _app()

    window = _new_window()
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    assert preview_index >= 0

    window.workspace_tabs.tabCloseRequested.emit(preview_index)

    collapse_button = _required_child(window, QToolButton, "hiddenWorkspaceTabsCollapseButton")
    expand_button = _required_child(window, QToolButton, "hiddenWorkspaceTabsExpandButton")
    assert collapse_button.toolTip() == "Hide the hidden tabs section"
    assert expand_button.toolTip() == "Show the hidden tabs section"

    assert window.hidden_workspace_tabs_strip.isHidden() is False
    assert window.hidden_workspace_tabs_label.isHidden() is True
    assert window.hidden_workspace_tabs_buttons_host.isHidden() is True
    assert collapse_button.isHidden() is True
    assert expand_button.isHidden() is False

    collapse_button.click()

    assert window.hidden_workspace_tabs_strip.isHidden() is False
    assert window.hidden_workspace_tabs_label.isHidden() is True
    assert window.hidden_workspace_tabs_buttons_host.isHidden() is True
    assert collapse_button.isHidden() is True
    assert expand_button.isHidden() is False

    expand_button.click()

    assert window.hidden_workspace_tabs_strip.isHidden() is False
    assert window.hidden_workspace_tabs_label.isHidden() is False
    assert window.hidden_workspace_tabs_buttons_host.isHidden() is False
    assert collapse_button.isHidden() is False
    assert expand_button.isHidden() is True


def test_desktop_window_keeps_editor_tab_non_closable() -> None:
    _app()

    window = _new_window()
    editor_index = window.workspace_tabs.indexOf(window.editor)
    assert editor_index >= 0

    assert (
        window.workspace_tabs.tabBar().tabButton(editor_index, QTabBar.ButtonPosition.RightSide)
        is None
    )

    window.workspace_tabs.tabCloseRequested.emit(editor_index)

    assert window.workspace_tabs.isTabVisible(editor_index) is True
    assert window.workspace_tabs.currentWidget() is window.editor


def test_desktop_window_places_analysis_tab_after_playback_output() -> None:
    _app()

    window = _new_window()
    playback_index = window.workspace_tabs.indexOf(window.playback_output_view)
    analysis_index = window.workspace_tabs.indexOf(window.analysis_tab)
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    raw_index = window.workspace_tabs.indexOf(window.raw_recording_view)
    diagnostics_index = window.workspace_tabs.indexOf(window.diagnostics_tab)

    assert playback_index >= 0
    assert analysis_index == playback_index + 1
    assert preview_index >= 0
    assert preview_index == analysis_index + 1
    assert raw_index == preview_index + 1
    assert window.workspace_tabs.tabText(raw_index) == "Raw Recordings"
    assert diagnostics_index == raw_index + 1
    assert window.workspace_tabs.tabText(diagnostics_index) == "Diagnostics"
    assert window.workspace_tabs.tabText(analysis_index) == "Analysis"


def test_desktop_window_shows_clear_analysis_empty_state_before_analyze() -> None:
    _app()

    window = _new_window()
    sidebar = window._analysis_sidebar_widgets
    assert sidebar is not None

    assert window.analysis_summary_view.toPlainText().startswith("Analysis status: not run")
    assert "Refresh scope: current editor text only" in window.analysis_summary_view.toPlainText()
    assert "Not refreshed: saved file state or preview output" in window.analysis_summary_view.toPlainText()
    assert (
        window.analysis_diagnostics_view.toPlainText()
        == "No analysis yet. Click Analyze to scan the current editor text."
    )
    assert sidebar.summary_view.toPlainText().startswith("Analysis status: not run")
    assert (
        sidebar.diagnostics_view.toPlainText()
        == "No analysis yet. Click Analyze to scan the current editor text."
    )
    assert sidebar.status_label.text() == "Run Analyze."
    assert window._current_sidebar_mode == "debug"
    header = _required_child(window, QLabel, "analysisDiagnosticsHeader")
    assert header.text() == "Click a card to jump to the source span."


def test_desktop_window_editor_debugger_breakpoint_api_roundtrips() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("one\ntwo\nthree\n")

    window.editor.toggleDebugBreakpoint(2)
    assert window.editor.debugBreakpointLines() == {2}

    window.editor.setDebugBreakpoints({1, 3})
    assert window.editor.debugBreakpointLines() == {1, 3}

    window.editor.clearDebugBreakpoints()
    assert window.editor.debugBreakpointLines() == set()


def test_desktop_window_debugger_action_streams_events_to_debugger_tab(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    recorded_breakpoints: list[tuple[int, ...]] = []
    started = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        recorded_breakpoints.append(tuple(sorted(handle.controller.snapshot().breakpoints)))
        started.set()
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id="session-1",
                document_id=document.document_id,
            )
        )
        handle.controller.sync_from_context(
            type(
                "DebugContext",
                (),
                {
                    "current_source_line": 3,
                    "variables": {},
                    "call_stack": [],
                },
            )()
        )
        paused_snapshot = type(
            "PausedSnapshot",
            (),
            {
                "session_id": "session-1",
                "state": "paused",
                "pause_reason": "step",
                "current_line": 3,
                "breakpoints": [2],
                "call_stack": [],
                "variables": [],
            },
        )()
        handle.controller.snapshot = lambda: paused_snapshot
        window.debugEventReceived.emit(
            DebugEvent(
                kind="stopped",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
                pause_reason="step",
            )
        )
        release.wait(timeout=2.0)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_completed",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
            )
        )
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    window.editor.setPlainText('Dim x = 1\nx = x + 1\nSendText("x")\n')
    window.editor.setDebugBreakpoints({2})
    window.committed_settings_bundle.application.show_debug_tab = False
    window.committed_settings_bundle.application.open_debug_tab_on_pause = True
    window.open_preferences()
    assert window._preferences_dialog is not None
    assert not hasattr(window._preferences_dialog, "workspace_show_debug_tab_checkbox")
    assert not hasattr(window._preferences_dialog, "debug_show_debug_tab_checkbox")
    assert window._preferences_dialog.open_debug_tab_on_pause_checkbox.isChecked() is True
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    window.open_debugger_dialog()

    assert started.wait(timeout=2.0) is True
    deadline = time.monotonic() + 2.0
    while window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window._current_sidebar_mode == "debug"
    assert recorded_breakpoints == [(2,)]
    assert window.play_script_action.isEnabled() is False
    assert window.record_script_action.isEnabled() is False
    assert window.preview_play_script_action.isEnabled() is False
    assert window.debugger_action.isEnabled() is False
    assert window.committed_settings_bundle.application.show_debug_tab is True
    assert window._settings_dirty is True
    assert window._preferences_dialog.is_dirty() is False
    deadline = time.monotonic() + 2.0
    while "[stopped] line=3 reason=step" not in window.debug_event_log_view.toPlainText() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    log_lines = window.debug_event_log_view.toPlainText().splitlines()
    assert log_lines[0] == "Debug session starting..."
    assert any(line == "[session_started]" for line in log_lines[1:])
    assert any(line.startswith("[stopped] line=3 reason=step") for line in log_lines)
    assert window.editor.toPlainText().splitlines()[2] == 'SendText("x")'
    assert window.editor.highlightedLine() == 3
    assert window.editor.debugBreakpointLines() == {2}
    assert window.editor.highlightedLine() == 3
    assert window.debug_status_indicator.toolTip().startswith("Paused on step at line 3")
    assert "f59e0b" in window.debug_status_indicator.styleSheet()

    window.editor.setPlainText('Dim x = 1\nx = x + 1\nSendText("x")\nSendText("x + 1")\n')
    cursor = QTextCursor(window.editor.document().findBlockByNumber(3))
    window.editor.setTextCursor(cursor)
    app.processEvents()

    assert window.editor.currentLineNumber() == 4
    assert window.editor.highlightedLine() == 3
    assert window.debug_status_indicator.toolTip().startswith("Paused on step at line 3")

    release.set()
    deadline = time.monotonic() + 2.0
    while not window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    log_lines = window.debug_event_log_view.toPlainText().splitlines()
    assert log_lines[0] == "Debug session starting..."
    assert any(line == "[session_started]" for line in log_lines[1:])
    assert any(line.startswith("[stopped] line=3 reason=step") for line in log_lines)
    assert any(line.startswith("[session_completed] line=3") for line in log_lines)
    assert window.debugger_action.isEnabled() is True
    assert window.play_script_action.isEnabled() is True
    assert window.editor.highlightedLine() is None
    assert window.editor.debugBreakpointLines() == {2}
    assert window.committed_settings_bundle.application.show_debug_tab is False
    assert window._settings_dirty is False
    assert window._preferences_dialog.is_dirty() is False
    assert not hasattr(window._preferences_dialog, "workspace_show_debug_tab_checkbox")
    assert not hasattr(window._preferences_dialog, "debug_show_debug_tab_checkbox")


def test_desktop_window_debugger_pause_can_preserve_current_tab_when_disabled(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    started = threading.Event()
    allow_pause = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id="session-1",
                document_id=document.document_id,
            )
        )
        started.set()
        allow_pause.wait(timeout=2.0)
        paused_snapshot = type(
            "PausedSnapshot",
            (),
            {
                "session_id": "session-1",
                "state": "paused",
                "pause_reason": "step",
                "current_line": 3,
                "breakpoints": [2],
                "call_stack": [],
                "variables": [],
            },
        )()
        handle.controller.snapshot = lambda: paused_snapshot
        window.debugEventReceived.emit(
            DebugEvent(
                kind="stopped",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
                pause_reason="step",
            )
        )
        release.wait(timeout=2.0)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_completed",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
            )
        )
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    window.editor.setPlainText('Dim x = 1\nx = x + 1\nSendText("x")\n')
    window.editor.setDebugBreakpoints({2})
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    window.open_debugger_dialog()

    assert started.wait(timeout=2.0) is True
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    assert window.workspace_tabs.currentWidget() is window.preview_view

    allow_pause.set()
    deadline = time.monotonic() + 2.0
    while window.editor.highlightedLine() != 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.workspace_tabs.currentWidget() is window.preview_view
    assert window.editor.highlightedLine() == 3
    assert window.debug_status_indicator.toolTip().startswith("Paused on step at line 3")

    release.set()
    deadline = time.monotonic() + 2.0
    while not window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.debugger_action.isEnabled() is True


def test_desktop_window_debugger_banner_toggle_enables_auto_open(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    started = threading.Event()
    allow_pause = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id="session-1",
                document_id=document.document_id,
            )
        )
        started.set()
        allow_pause.wait(timeout=2.0)
        paused_snapshot = type(
            "PausedSnapshot",
            (),
            {
                "session_id": "session-1",
                "state": "paused",
                "pause_reason": "step",
                "current_line": 3,
                "breakpoints": [2],
                "call_stack": [],
                "variables": [],
            },
        )()
        handle.controller.snapshot = lambda: paused_snapshot
        window.debugEventReceived.emit(
            DebugEvent(
                kind="stopped",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
                pause_reason="step",
            )
        )
        release.wait(timeout=2.0)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_completed",
                session_id="session-1",
                document_id=document.document_id,
                line=3,
            )
        )
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    window.editor.setPlainText('Dim x = 1\nx = x + 1\nSendText("x")\n')
    window.editor.setDebugBreakpoints({2})
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    window.open_debugger_dialog()

    assert started.wait(timeout=2.0) is True
    allow_pause.set()
    deadline = time.monotonic() + 2.0
    while window.editor.highlightedLine() != 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.workspace_tabs.currentWidget() is window.preview_view
    assert window.editor.highlightedLine() == 3
    assert window.debug_status_indicator.toolTip().startswith("Paused on step at line 3")

    release.set()
    deadline = time.monotonic() + 2.0
    while not window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.debugger_action.isEnabled() is True


def test_desktop_window_debugger_restart_button_restarts_with_edited_source(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    started_texts: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        started_texts.append(document.text)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id=f"session-{len(started_texts)}",
                document_id=document.document_id,
            )
        )
        if len(started_texts) == 1:
            handle.controller.sync_from_context(
                type(
                    "DebugContext",
                    (),
                    {
                        "current_source_line": 3,
                        "variables": {},
                        "call_stack": [],
                    },
                )()
            )
            paused_snapshot = type(
                "PausedSnapshot",
                (),
                {
                    "session_id": "session-1",
                    "state": "paused",
                    "pause_reason": "step",
                    "current_line": 3,
                    "breakpoints": [2],
                    "call_stack": [],
                    "variables": [],
                },
            )()
            handle.controller.snapshot = lambda: paused_snapshot
            started.set()
            window.debugEventReceived.emit(
                DebugEvent(
                    kind="stopped",
                    session_id="session-1",
                    document_id=document.document_id,
                    line=3,
                    pause_reason="step",
                )
            )
            release.wait(timeout=2.0)
            window.debugSessionFinished.emit("completed")
            return

        started.set()
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    initial_text = 'Dim x = 1\nx = x + 1\nSendText("x")\n'
    restarted_text = 'Dim x = 1\nx = x + 1\nSendText("x")\nSendText("x + 1")\n'
    window.editor.setPlainText(initial_text)
    window.editor.setDebugBreakpoints({2})
    window.open_debugger_dialog()

    assert started.wait(timeout=2.0) is True
    window.editor.setPlainText(restarted_text)
    cursor = QTextCursor(window.editor.document().findBlockByNumber(3))
    window.editor.setTextCursor(cursor)
    app.processEvents()

    deadline = time.monotonic() + 2.0
    while window.editor.highlightedLine() != 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    assert window.editor.highlightedLine() == 3
    assert window.editor.currentLineNumber() == 4

    window.debug_restart_button.click()
    release.set()

    deadline = time.monotonic() + 2.0
    while len(started_texts) < 2 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert started_texts[0] == initial_text
    assert started_texts[1] == restarted_text
    assert window.editor.highlightedLine() is None


def test_desktop_window_routes_debugger_restart_from_action_and_toolbar(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    class FakeHandle:
        controller = object()

    window._debug_session_handle = _debug_handle(FakeHandle())
    monkeypatch.setattr(window, "stop_debug_session", lambda: calls.append("debug_stop"))
    window._update_debugger_controls_state(active=True)

    restart_button = _required_child(window.debug_toolbar_group, QToolButton, "debugRestartToolbarButton")

    window.debug_restart_action.trigger()
    restart_button.click()

    assert calls == ["debug_stop", "debug_stop"]
    assert window._pending_debug_restart is True


def test_desktop_window_debugger_tab_renders_session_snapshot() -> None:
    _app()

    window = _new_window()

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeVariable:
        def __init__(self, name: str, value: object, type_name: str) -> None:
            self.name = name
            self.value = value
            self.type_name = type_name

    class FakeSnapshot:
        session_id = "session-42"
        state = "paused"
        pause_reason = "breakpoint"
        current_line = 17
        breakpoints = [9, 17]
        call_stack = [FakeFrame("Main", 17), FakeFrame("Helper", 9)]
        variables = [FakeVariable("x", 7, "int"), FakeVariable("label", "hello", "str")]
        special_values = {
            "Error": 7,
            "CRLF": "\r\n",
            "WorkingDir": "C:\\workspace",
        }

    class FakeController:
        def snapshot(self):
            return FakeSnapshot()

    class FakeHandle:
        controller = FakeController()

    source_text = "\n".join(f"line {index}" for index in range(1, 21))
    window.editor.setPlainText(source_text)
    window._debug_session_handle = _debug_handle(FakeHandle())
    window._debug_watch_expressions = ["x + 2", "@Error", "@CRLF", "@WorkingDir", 'label & "!"']
    window._refresh_debug_snapshot()

    assert window.debug_status_indicator.toolTip() == "Paused on Breakpoint in Helper (depth 2) at line 17"
    assert "f59e0b" in window.debug_status_indicator.styleSheet()
    assert window.findChild(QToolButton, "debugRevealSourceButton") is None
    assert window.workspace_tabs.currentWidget() is window.editor
    assert window.editor.toPlainText() == source_text
    assert window.editor.highlightedLine() == 17
    assert window.editor.debugBreakpointLines() == {9, 17}
    assert window.editor.highlightedLine() == 17
    assert window.debug_call_stack_tree.topLevelItemCount() == 2
    call_stack_item_0 = _required_top_level_item(window.debug_call_stack_tree, 0)
    call_stack_item_1 = _required_top_level_item(window.debug_call_stack_tree, 1)
    assert call_stack_item_0.text(1) == "Main"
    assert call_stack_item_1.text(2) == "9"
    assert window.debug_variables_tree.topLevelItemCount() == 2
    runtime_group = _required_top_level_item(window.debug_variables_tree, 0)
    user_group = _required_top_level_item(window.debug_variables_tree, 1)
    assert runtime_group.text(0) == "Runtime Values (read-only, 3)"
    assert user_group.text(0) == "User Variables (2)"
    assert runtime_group.childCount() == 3
    assert user_group.childCount() == 2

    variables_item_0 = runtime_group.child(0)
    variables_item_1 = runtime_group.child(1)
    variables_item_2 = runtime_group.child(2)
    variables_item_3 = user_group.child(0)
    variables_item_4 = user_group.child(1)
    assert variables_item_0 is not None
    assert variables_item_1 is not None
    assert variables_item_2 is not None
    assert variables_item_3 is not None
    assert variables_item_4 is not None
    assert variables_item_0.text(0) == "@Error"
    assert variables_item_0.text(1) == "7"
    assert variables_item_0.text(2) == "int"
    assert variables_item_1.text(0) == "@CRLF"
    assert variables_item_1.text(1) == "'\\r\\n'"
    assert variables_item_1.text(2) == "str"
    assert variables_item_2.text(0) == "@WorkingDir"
    assert variables_item_2.text(1) == "'C:\\\\workspace'"
    assert variables_item_2.text(2) == "str"
    assert variables_item_3.text(0) == "x"
    assert variables_item_3.text(1) == "7"
    assert variables_item_3.text(2) == "int"
    assert variables_item_4.text(0) == "label"
    assert variables_item_4.text(1) == "'hello'"
    assert variables_item_4.text(2) == "str"
    assert window.debug_watch_tree.topLevelItemCount() == 5
    watch_item_0 = _required_top_level_item(window.debug_watch_tree, 0)
    watch_item_1 = _required_top_level_item(window.debug_watch_tree, 1)
    watch_item_2 = _required_top_level_item(window.debug_watch_tree, 2)
    watch_item_3 = _required_top_level_item(window.debug_watch_tree, 3)
    watch_item_4 = _required_top_level_item(window.debug_watch_tree, 4)
    assert watch_item_0.text(0) == "x + 2"
    assert watch_item_0.text(1) == "9"
    assert watch_item_0.text(2) == "int"
    assert watch_item_0.text(3) == "Ready"
    assert watch_item_1.text(0) == "@Error"
    assert watch_item_1.text(1) == "7"
    assert watch_item_1.text(2) == "int"
    assert watch_item_1.text(3) == "Ready"
    assert watch_item_2.text(0) == "@CRLF"
    assert watch_item_2.text(1) == "'\\r\\n'"
    assert watch_item_2.text(2) == "str"
    assert watch_item_2.text(3) == "Ready"
    assert watch_item_3.text(0) == "@WorkingDir"
    assert watch_item_3.text(1) == "'C:\\\\workspace'"
    assert watch_item_3.text(2) == "str"
    assert watch_item_3.text(3) == "Ready"
    assert watch_item_4.text(0) == 'label & "!"'
    assert watch_item_4.text(1) == "'hello!'"
    assert watch_item_4.text(2) == "str"
    assert watch_item_4.text(3) == "Ready"

    window.editor.setDebugBreakpoints({9, 17})
    window.editor.toggleDebugBreakpoint(17)

    assert window.editor.debugBreakpointLines() == {9}


def test_desktop_window_debugger_tab_renders_nested_struct_watch_values() -> None:
    _app()

    window = _new_window()
    point_a = StructInstance("Point", ("X", "Y"), (1, 2))
    point_b = StructInstance("Point", ("X", "Y"), (3, 4))
    pair = StructInstance("Pair", ("First", "Second"), (point_a, point_b))

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeVariable:
        def __init__(self, name: str, value: object, type_name: str) -> None:
            self.name = name
            self.value = value
            self.type_name = type_name

    class FakeSnapshot:
        session_id = "session-structs"
        state = "paused"
        pause_reason = "breakpoint"
        current_line = 12
        breakpoints = [12]
        call_stack = [FakeFrame("BuildPair", 9)]
        variables = [FakeVariable("pair", pair, "Pair")]

    class FakeController:
        def snapshot(self):
            return FakeSnapshot()

    class FakeHandle:
        controller = FakeController()

    window._debug_session_handle = _debug_handle(FakeHandle())
    window._debug_watch_expressions = ["pair", "pair.Second"]
    window._refresh_debug_snapshot()

    assert window.debug_variables_tree.topLevelItemCount() == 1
    variable_group = _required_top_level_item(window.debug_variables_tree, 0)
    assert variable_group.text(0) == "User Variables (1)"
    assert variable_group.childCount() == 1
    variable_item = variable_group.child(0)
    assert variable_item is not None
    assert variable_item.text(0) == "pair"
    assert variable_item.text(1) == "Pair(First=Point(X=1, Y=2), Second=Point(X=3, Y=4))"
    assert variable_item.text(2) == "Pair"

    assert window.debug_watch_tree.topLevelItemCount() == 2
    watch_item_0 = _required_top_level_item(window.debug_watch_tree, 0)
    watch_item_1 = _required_top_level_item(window.debug_watch_tree, 1)
    assert watch_item_0.text(0) == "pair"
    assert watch_item_0.text(1) == "Pair(First=Point(X=1, Y=2), Second=Point(X=3, Y=4))"
    assert watch_item_0.text(2) == "Pair"
    assert watch_item_0.text(3) == "Ready"
    assert watch_item_1.text(0) == "pair.Second"
    assert watch_item_1.text(1) == "Point(X=3, Y=4)"
    assert watch_item_1.text(2) == "Point"
    assert watch_item_1.text(3) == "Ready"


def test_desktop_window_debugger_panel_uses_split_layout() -> None:
    app = _app()

    window = _new_window()
    inspector = window.debugger_panel
    dialog = window.debugger_controls_dialog
    dialog.show()
    app.processEvents()

    assert dialog.windowTitle() == ""
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.minimumSize() == dialog.maximumSize()
    assert dialog.width() <= 244
    assert dialog.height() <= 64
    workspace_splitter = _required_child(inspector, QSplitter, "debugWorkspaceSplitter")
    assert workspace_splitter.orientation() == Qt.Orientation.Vertical
    assert workspace_splitter.widget(0) is window.debug_variables_group
    assert workspace_splitter.widget(1) is window.debug_watch_group
    assert workspace_splitter.widget(2) is window.debug_call_stack_group
    assert workspace_splitter.widget(3) is window.debug_event_log_group
    assert window.debug_status_indicator.toolTip() == "Idle"
    assert window.debugger_controls_button.text() == "Debugger Controls"
    assert window.sidebar_mode_title_label.isVisible() is False
    title_bar = _required_child(dialog, QWidget, "debugControlsTitleBar")
    close_button = _required_child(dialog, QToolButton, "debugControlsCloseButton")
    assert close_button.text() == "x"
    status_label = _required_child(dialog, QLabel, "debugControlsStatusLabel")
    assert status_label.text() == "Status:"
    assert _required_child(dialog, QLabel, "debugControlsStatusIndicator") is not None
    assert window.debug_continue_button.toolTip().startswith("Continue")
    assert window.debug_step_over_button.toolTip().startswith("Step Over")
    assert window.debug_step_button.toolTip().startswith("Step Into")
    assert window.debug_step_out_button.toolTip().startswith("Step Out")
    assert window.debug_restart_button.toolTip().startswith("Restart")
    assert window.debug_stop_button.toolTip().startswith("Stop")
    assert window.debug_continue_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_over_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_out_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_restart_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_stop_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert dialog.findChild(QSplitter, "debugWorkspaceSplitter") is None


def test_desktop_window_toggle_breakpoint_action_uses_debugger_session_current_line() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("one\ntwo\nthree\n")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.setDebugBreakpoints({2})

    class FakeSnapshot:
        session_id = "session-1"
        state = "paused"
        is_running = True
        is_paused = True
        pause_reason = "breakpoint"
        current_line = 2
        breakpoints = [2]
        call_stack = []
        variables = []
        last_exception = None

    class FakeController:
        def snapshot(self):
            return FakeSnapshot()

    class FakeHandle:
        controller = FakeController()

    window._debug_session_handle = _debug_handle(FakeHandle())
    window._refresh_debug_snapshot()

    breakpoint_present_icon = window._file_action_icon("msc.debug-breakpoint-unverified")
    toggle_breakpoint_button = window.debug_toolbar_group.findChild(
        QToolButton,
        "toggleBreakpointToolbarButton",
    )
    assert toggle_breakpoint_button is not None
    assert window.toggle_breakpoint_action.icon().cacheKey() == breakpoint_present_icon.cacheKey()
    assert toggle_breakpoint_button.icon().cacheKey() == breakpoint_present_icon.cacheKey()


def test_desktop_window_debugger_watch_controls_add_and_remove_expression() -> None:
    _app()

    window = _new_window()

    window.debug_watch_expression_edit.setText("x + 1")
    window._add_debug_watch_expression()

    assert window._debug_watch_expressions == ["x + 1"]
    assert window.debug_watch_tree.topLevelItemCount() == 1
    watch_item = _required_top_level_item(window.debug_watch_tree, 0)
    assert watch_item.text(0) == "x + 1"
    assert watch_item.text(1) == "-"
    assert watch_item.text(2) == "-"
    assert watch_item.text(3) == "Waiting"
    assert window.debug_watch_expression_edit.text() == ""

    window.debug_watch_tree.setCurrentItem(watch_item)
    window._remove_selected_debug_watch_expression()

    assert window._debug_watch_expressions == []
    assert window.debug_watch_tree.topLevelItemCount() == 0


def test_desktop_window_debugger_watch_expression_is_editable_in_place() -> None:
    _app()

    window = _new_window()

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeVariable:
        def __init__(self, name: str, value: object, type_name: str) -> None:
            self.name = name
            self.value = value
            self.type_name = type_name

    class FakeSnapshot:
        session_id = "session-watch"
        state = "paused"
        pause_reason = "breakpoint"
        current_line = 3
        breakpoints = []
        call_stack = [FakeFrame("Helper", 3)]
        variables = [FakeVariable("x", 7, "int")]

    class FakeController:
        def snapshot(self):
            return FakeSnapshot()

    class FakeHandle:
        controller = FakeController()

    window._debug_session_handle = _debug_handle(FakeHandle())
    window._debug_watch_expressions = ["x + 1"]
    window._refresh_debug_snapshot()

    item = _required_top_level_item(window.debug_watch_tree, 0)
    assert item.flags() & Qt.ItemFlag.ItemIsEditable
    assert item.text(1) == "8"

    item.setText(0, "x + 2")

    assert window._debug_watch_expressions == ["x + 2"]
    assert window.debug_watch_tree.topLevelItemCount() == 1
    watch_item = _required_top_level_item(window.debug_watch_tree, 0)
    assert watch_item.text(0) == "x + 2"
    assert watch_item.text(1) == "9"
    assert watch_item.text(3) == "Ready"


def test_desktop_window_pause_summary_formats_step_over_and_step_out() -> None:
    _app()

    window = _new_window()

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeSnapshot:
        def __init__(self, pause_reason: str) -> None:
            self.session_id = "session-99"
            self.state = "paused"
            self.pause_reason = pause_reason
            self.current_line = 4
            self.breakpoints = []
            self.call_stack = [FakeFrame("Helper", 4)]
            self.variables = []

    step_over_summary = window._debug_pause_summary(FakeSnapshot("step_over"))
    step_out_summary = window._debug_pause_summary(FakeSnapshot("step_out"))

    assert step_over_summary == "paused on Step Over in Helper (depth 1) at line 4"
    assert step_out_summary == "paused on Step Out in Helper (depth 1) at line 4"


def test_desktop_window_pause_summary_formats_breakpoint_and_exception() -> None:
    _app()

    window = _new_window()

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeSnapshot:
        def __init__(self, pause_reason: str) -> None:
            self.session_id = "session-100"
            self.state = "paused"
            self.pause_reason = pause_reason
            self.current_line = 8
            self.breakpoints = []
            self.call_stack = [FakeFrame("Main", 8)]
            self.variables = []

    breakpoint_summary = window._debug_pause_summary(FakeSnapshot("breakpoint"))
    exception_summary = window._debug_pause_summary(FakeSnapshot("exception"))

    assert breakpoint_summary == "paused on Breakpoint in Main (depth 1) at line 8"
    assert exception_summary == "paused on Exception in Main (depth 1) at line 8"


def test_desktop_window_pause_summary_falls_back_to_plain_paused_state() -> None:
    _app()

    window = _new_window()

    class FakeSnapshot:
        def __init__(self) -> None:
            self.session_id = "session-101"
            self.state = "paused"
            self.pause_reason = None
            self.current_line = 12
            self.breakpoints = []
            self.call_stack = []
            self.variables = []

    summary = window._debug_pause_summary(FakeSnapshot())
    reason = window._debug_pause_reason_text(None)

    assert summary == "paused at line 12"
    assert reason == "Paused"


def test_desktop_window_debugger_controls_resume_controller_methods() -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    class FakeController:
        def resume_step(self):
            calls.append("step")

        def resume_step_over(self):
            calls.append("step_over")

        def resume_step_out(self):
            calls.append("step_out")

        def resume_continue(self):
            calls.append("continue")

        def snapshot(self):
            return type("Snapshot", (), {
                "session_id": "session-1",
                "state": "paused",
                "pause_reason": "step",
                "current_line": 1,
                "breakpoints": [],
                "call_stack": [],
                "variables": [],
            })()

    class FakeHandle:
        controller = FakeController()

    window._debug_session_handle = _debug_handle(FakeHandle())
    window._debug_session_stop_event = threading.Event()
    window._update_debugger_controls_state(active=True)

    assert window.debug_step_button.text() == "Step Into"
    assert window.debug_step_button.objectName() == "debugStepIntoButton"
    assert window.debug_step_button.toolTip().startswith("Step Into")
    assert window.debug_step_button.icon().isNull() is False
    assert window.debug_step_over_button.icon().isNull() is False
    assert window.debug_step_out_button.icon().isNull() is False
    assert window.debug_continue_button.icon().isNull() is False
    assert window.debug_stop_button.icon().isNull() is False
    window.debug_step_button.click()
    window.debug_step_over_button.click()
    window.debug_step_out_button.click()
    window.debug_continue_button.click()
    window.debug_stop_button.click()

    assert calls == ["step", "step_over", "step_out", "continue", "continue"]
    assert window._debug_session_stop_event.is_set() is True


def test_desktop_window_emits_diagnostics_for_preferences_and_editor_changes(
    monkeypatch,
) -> None:
    app = _app()

    events: list[object] = []
    monkeypatch.setattr(
        debug_logger,
        "emit_diagnostic_event",
        lambda event: events.append(event),
    )

    window = _new_window()
    window.open_preferences()
    assert window._preferences_dialog is not None

    window._preferences_dialog.restore_workspace_checkbox.setChecked(True)
    app.processEvents()
    window.editor.setPlainText('WriteLn("hello")\n')
    app.processEvents()

    assert any(
        getattr(event, "event_id", None) == "desktop.preferences.opened"
        for event in events
    )
    assert any(
        getattr(event, "event_id", None) == "desktop.preferences.dirty_state_changed"
        and getattr(event, "fields", {}).get("dirty") is True
        for event in events
    )
    assert any(
        getattr(event, "event_id", None) == "desktop.editor.dirty_state_changed"
        and getattr(event, "fields", {}).get("editor_dirty") is True
        for event in events
    )


def test_desktop_window_clears_settings_dirty_when_preferences_match_saved_state() -> None:
    _app()

    window = _new_window()
    initial_title = window.windowTitle()
    initial_tab_text = window.workspace_tabs.tabText(0)
    window.open_preferences()
    assert window._preferences_dialog is not None

    window._preferences_dialog.restore_workspace_checkbox.setChecked(True)
    assert window._settings_dirty is True
    assert window._preferences_dialog.is_dirty() is True
    assert window.windowTitle() == initial_title
    assert window.workspace_tabs.tabText(0) == initial_tab_text


def test_desktop_window_discards_unsaved_preferences_changes_on_close(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    original_bundle = window.committed_settings_bundle
    window._settings_service.load = lambda: original_bundle

    window.open_preferences()
    assert window._preferences_dialog is not None
    dialog = window._preferences_dialog
    dialog.diagnostics_stdout_checkbox.setChecked(True)
    assert dialog.is_dirty() is True
    assert window.committed_settings_bundle.diagnostics.log_to_stdout is True

    monkeypatch.setattr(
        "apps.desktop.preferences_dialog.question_save_discard_cancel",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )

    event = QCloseEvent()
    dialog.closeEvent(event)
    app.processEvents()

    assert event.isAccepted() is True
    assert window.committed_settings_bundle.diagnostics.log_to_stdout is False

    window.open_preferences()
    assert window._preferences_dialog is dialog
    assert window._preferences_dialog.diagnostics_stdout_checkbox.isChecked() is False
    assert window._preferences_dialog.is_dirty() is False


def test_desktop_window_blocks_saving_unreadable_theme(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.open_preferences()
    assert window._preferences_dialog is not None
    dialog = window._preferences_dialog

    dialog._editor_style_data["editor_text"] = "#ffffff"
    dialog._emit_preferences_changed()

    saved_calls: list[bool] = []
    monkeypatch.setattr(window._settings_service, "save_requirements", lambda: [])
    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda *args, **kwargs: saved_calls.append(True),
    )
    critical_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, message: critical_messages.append((title, message)),
    )

    assert window.save_preferences() is False
    assert saved_calls == []
    assert critical_messages
    assert critical_messages[0][0] == "Preferences Save Blocked"
    assert "readable enough to save safely" in critical_messages[0][1].lower()


def test_desktop_window_shows_playback_output_from_controller_signal() -> None:
    _app()

    window = _new_window()

    result = PlaybackResult(
        source_kind="script_document",
        source_id="doc-1",
        executed_event_count=0,
        success=True,
        delay_ms=125,
        console_output=["hello\n"],
        diagnostics_output=["trace\n"],
    )

    window.script_controller.playbackResultReady.emit(result)

    text = window.playback_output_view.toPlainText()
    assert text.startswith(
        "Playback result:\n"
        "Source kind: script_document\n"
        "Source ID: doc-1\n"
        "Executed event count: 0\n"
        "Success: True\n"
        "Delay per event (ms): 125\n"
    )
    assert "Console output:\nhello" in text
    assert "Diagnostics output (DiagWrite/DiagWriteLn):" in text
    assert "trace" in text

    assert window.summary_view.toPlainText() == ""


def test_desktop_window_shows_write_ln_output_in_playback_tab(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    _use_real_script_playback_service(window, monkeypatch)

    text = _run_smoke_script_and_get_playback_output(
        window,
        'SetCurrentEventDelay(125)\nWriteLn("Hello World")\n',
        app=app,
    )
    assert "Console output:" in text
    assert "Hello World" in text
    assert "Executed event count: 0" in text
    assert "Delay per event (ms): 125" in text
    assert window.summary_view.toPlainText() == ""


def test_desktop_window_summary_sidebar_shows_debugger_state_and_final_outcome() -> None:
    _app()

    window = _new_window()

    class FakeFrame:
        def __init__(self, function_name: str, source_line: int | None) -> None:
            self.function_name = function_name
            self.source_line = source_line

    class FakeSnapshot:
        session_id = "session-42"
        state = "paused"
        pause_reason = "breakpoint"
        current_line = 17
        breakpoints = [9, 17]
        call_stack = [FakeFrame("Main", 17), FakeFrame("Helper", 9)]
        variables = []
        last_exception = None

    class FakeController:
        def snapshot(self):
            return FakeSnapshot()

    class FakeHandle:
        controller = FakeController()

    window._debug_session_handle = _debug_handle(FakeHandle())
    window._refresh_summary()

    assert window.summary_view.toPlainText() == ""

    window._debug_session_handle = None
    window._last_debug_session_outcome = "failed: boom"
    window._refresh_summary()

    assert window.summary_view.toPlainText() == ""


def test_desktop_window_routes_diag_write_ln_output_to_diagnostics_tab(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    base_bundle = window.committed_settings_bundle
    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=base_bundle.application,
            playback=base_bundle.playback,
            recording=base_bundle.recording,
            files=base_bundle.files,
            diagnostics=DesktopDiagnosticsSettings(
                enabled=True,
                log_to_file=False,
                log_to_stdout=False,
            ),
            runtime=base_bundle.runtime,
            theme=base_bundle.theme,
        )
    )
    _use_real_script_playback_service(window, monkeypatch)

    text = _run_smoke_script_and_get_playback_output(
        window,
        'DiagWriteLn("Trace me")\n',
        app=app,
    )
    assert "Diagnostics output (DiagWrite/DiagWriteLn):" not in text
    assert "Trace me" not in text
    assert "Executed event count: 0" in text
    assert "Trace me" in window.diagnostics_view.toPlainText()


def test_desktop_window_shows_msgbox_playback_via_gui_host(monkeypatch) -> None:
    app = _app()

    window = _new_window()

    observed: dict[str, object] = {}

    def fake_show_msgbox_dialog(*, flag, title, text, timeout):
        observed["flag"] = flag
        observed["title"] = title
        observed["text"] = text
        observed["timeout"] = timeout
        return 1

    monkeypatch.setattr(window.script_controller, "_show_msgbox_dialog", fake_show_msgbox_dialog)

    text = _run_smoke_script_and_get_playback_output(
        window,
        'MsgBox(1, "Hello", "World")\n',
        app=app,
    )
    assert observed["flag"] == 1
    assert observed["title"] == "Hello"
    assert observed["text"] == "World"
    assert observed["timeout"] == 0
    assert "Executed event count: 0" in text


def test_desktop_window_shows_keytoggle_playback_via_gui_host(monkeypatch) -> None:
    app = _app()

    window = _new_window()

    observed: dict[str, object] = {}

    def fake_toggle_lock_key(*, key, state):
        observed["key"] = key
        observed["state"] = state

    monkeypatch.setattr(
        window.script_controller._keyboard_toggle_service,
        "toggle_lock_key",
        fake_toggle_lock_key,
    )

    text = _run_smoke_script_and_get_playback_output(
        window,
        'KeyToggle("capslock", "toggle")\n',
        app=app,
    )
    assert observed["key"] == "capslock"
    assert observed["state"] == "toggle"
    assert "Executed event count: 0" in text


def test_desktop_window_shows_pixel_get_color_output_in_playback_tab(monkeypatch) -> None:
    app = _app()

    window = _new_window()

    def fake_pixel_get_color(*, x, y, hwnd):
        _ = hwnd
        assert x == 10
        assert y == 20
        return 0x112233

    monkeypatch.setattr(
        window.script_controller._screen_sampling_service,
        "get_pixel_color",
        fake_pixel_get_color,
    )

    text = _run_smoke_script_and_get_playback_output(
        window,
        'WriteLn(PixelGetColor(10, 20))\n',
        app=app,
    )
    assert "Console output:" in text
    assert str(0x112233) in text
    assert "Executed event count: 0" in text


def test_desktop_window_shows_pixel_search_output_in_playback_tab(monkeypatch) -> None:
    app = _app()

    window = _new_window()

    def fake_pixel_search(*, left, top, right, bottom, color, shade_variation, step, hwnd):
        _ = hwnd
        assert (left, top, right, bottom, color, shade_variation, step) == (1, 2, 3, 4, 5, 6, 7)
        return [9, 10]

    monkeypatch.setattr(
        window.script_controller._screen_sampling_service,
        "search_pixel",
        fake_pixel_search,
    )

    text = _run_smoke_script_and_get_playback_output(
        window,
        'WriteLn(PixelSearch(1, 2, 3, 4, 5, 6, 7, 8))\n',
        app=app,
    )
    assert "Console output:" in text
    assert "[9, 10]" in text
    assert "Executed event count: 0" in text


def test_desktop_window_starts_with_visible_summary_sidebar() -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_action.isCheckable() is False
    assert window.summary_sidebar_action.text() == "Left Sidebar"
    assert window.summary_sidebar_action.icon().isNull() is False
    assert window.summary_sidebar_toolbar_button.isChecked() is True
    assert window.summary_sidebar_toolbar_button.arrowType() == Qt.ArrowType.LeftArrow
    assert window.summary_sidebar_toolbar_button.text() == ""
    assert window.summary_sidebar_toolbar_button.toolTip() == "Hide the sidebar on the left"
    assert window.summary_sidebar_reopen_strip.isVisible() is False
    assert window.summary_sidebar_reopen_button.arrowType() == Qt.ArrowType.RightArrow
    assert window.summary_sidebar_reopen_button.toolTip() == "Show the sidebar on the left"
    assert (window.summary_dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable).value == 0
    assert window.summary_dock.titleBarWidget() is window.summary_sidebar_title_bar
    assert window.summary_sidebar_title_bar.styleSheet() == ""
    sidebar_button = _required_child(window.summary_sidebar_title_bar, QToolButton, "sidebarToolbarButton")
    assert sidebar_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert sidebar_button.minimumSize().width() <= 18
    assert sidebar_button.minimumSize().height() <= 18


def test_desktop_window_shows_editor_and_event_status_information() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("abc\ndef")
    cursor = window.editor.textCursor()
    cursor.setPosition(5)
    window.editor.setTextCursor(cursor)
    app.processEvents()

    assert window._editor_status_label.text() == "Lines: 2 | Ln: 2 | Col: 2 | Ch: 6"
    assert window._events_status_label.text() == "Events: 2"
    assert window._editor_status_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_desktop_window_shows_default_diagnostics_log_path_by_default() -> None:
    _app()
    debug_logger.reset_diagnostic_config()

    window = _new_window()

    label_text = window.diagnostics_log_path_label.text()
    printed_path = Path(label_text.removeprefix("Diagnostics log file: ").strip())

    assert label_text.startswith("Diagnostics log file: ")
    assert printed_path.parent == Path(tempfile.gettempdir())
    assert printed_path.name.startswith("actionshellscript_diagnostics_")
    assert printed_path.suffix == ".log"


def test_desktop_window_announces_runtime_diagnostics_log_override_consistently(
    tmp_path: Path,
) -> None:
    _app()
    debug_logger.reset_diagnostic_config()

    window = _new_window()
    override_path = (tmp_path / "desktop-diagnostics.log").resolve()

    window._on_preferences_changed(
        DesktopSettingsBundle(
            files=DesktopFilesSettings(diagnostic_log_path=str(override_path)),
            playback=window.committed_settings_bundle.playback,
            recording=window.committed_settings_bundle.recording,
            theme=window.committed_settings_bundle.theme,
        )
    )

    label_text = window.diagnostics_log_path_label.text()
    active_config = debug_logger.get_diagnostic_config()

    assert label_text == f"Diagnostics log file: {override_path}"
    assert active_config.log_path == override_path


def test_desktop_window_appends_live_diagnostics_to_tab_when_enabled() -> None:
    app = _app()
    debug_logger.reset_diagnostic_config()

    window = _new_window()
    try:
        base_bundle = window.committed_settings_bundle
        window._on_preferences_changed(
            DesktopSettingsBundle(
                application=base_bundle.application,
                playback=base_bundle.playback,
                recording=base_bundle.recording,
                files=base_bundle.files,
                diagnostics=DesktopDiagnosticsSettings(
                    enabled=True,
                    log_to_file=False,
                    log_to_stdout=False,
                ),
                runtime=base_bundle.runtime,
                theme=base_bundle.theme,
            )
        )

        debug_logger.get_diagnostic_logger("tests.diagnostics").info("Live diagnostic line")
        app.processEvents()

        text = window.diagnostics_view.toPlainText()
        assert "Live diagnostics:" in text
        assert "tests.diagnostics" in text
        assert "Live diagnostic line" in text
        assert window.diagnostics_view.textCursor().atEnd() is True
    finally:
        if window._diagnostics_event_unsubscribe is not None:
            window._diagnostics_event_unsubscribe()
            window._diagnostics_event_unsubscribe = None
        debug_logger.reset_diagnostic_config()


def test_desktop_window_clears_live_diagnostics_from_tab() -> None:
    app = _app()
    debug_logger.reset_diagnostic_config()

    window = _new_window()
    try:
        window.clear_diagnostics_output()
        app.processEvents()
        assert window.diagnostics_clear_button.isEnabled() is False

        base_bundle = window.committed_settings_bundle
        window._on_preferences_changed(
            DesktopSettingsBundle(
                application=base_bundle.application,
                playback=base_bundle.playback,
                recording=base_bundle.recording,
                files=base_bundle.files,
                diagnostics=DesktopDiagnosticsSettings(
                    enabled=True,
                    log_to_file=False,
                    log_to_stdout=False,
                ),
                runtime=base_bundle.runtime,
                theme=base_bundle.theme,
            )
        )

        debug_logger.get_diagnostic_logger("tests.diagnostics").info("Clear me")
        app.processEvents()

        assert "Clear me" in window.diagnostics_view.toPlainText()
        assert window.diagnostics_clear_button.isEnabled() is True

        window.diagnostics_clear_button.click()
        app.processEvents()

        assert window.diagnostics_view.toPlainText() == "<none>"
        assert window.diagnostics_clear_button.isEnabled() is False
    finally:
        if window._diagnostics_event_unsubscribe is not None:
            window._diagnostics_event_unsubscribe()
            window._diagnostics_event_unsubscribe = None
        debug_logger.reset_diagnostic_config()


def test_desktop_window_shows_activity_indicator_for_idle_recording_playback_and_debug_states() -> None:
    _app()

    window = _new_window()

    indicator = window._recording_playback_indicator
    assert indicator.toolTip() == "Idle"
    assert "background-color: #111111" in indicator.styleSheet()

    window.script_controller._script_operation_kind = "record"
    window._update_activity_indicator()
    assert indicator.toolTip() == "Recording"
    assert "background-color: #d32f2f" in indicator.styleSheet()

    window.script_controller._script_operation_kind = "play"
    window._update_activity_indicator()
    assert indicator.toolTip() == "Playback"
    assert "background-color: #39ff14" in indicator.styleSheet()

    paused_snapshot = type(
        "PausedSnapshot",
        (),
        {
            "state": "paused",
            "pause_reason": "step",
            "current_line": 3,
            "breakpoints": [],
            "call_stack": [],
            "variables": [],
        },
    )()

    class PausedController:
        def snapshot(self):
            return paused_snapshot

    class PausedHandle:
        controller = PausedController()

    window._debug_session_handle = _debug_handle(PausedHandle())
    window._update_activity_indicator()
    assert indicator.toolTip() == "Paused on step at line 3"
    assert "background-color: #f59e0b" in indicator.styleSheet()

    running_snapshot = type(
        "RunningSnapshot",
        (),
        {
            "state": "running",
            "pause_reason": None,
            "current_line": 4,
            "breakpoints": [],
            "call_stack": [],
            "variables": [],
        },
    )()

    class RunningController:
        def snapshot(self):
            return running_snapshot

    class RunningHandle:
        controller = RunningController()

    window._debug_session_handle = _debug_handle(RunningHandle())
    window._update_activity_indicator()
    assert indicator.toolTip() == "Running"
    assert "background-color: #2e7d32" in indicator.styleSheet()

    window._debug_session_handle = None
    window.script_controller._script_operation_kind = None
    window._update_activity_indicator()
    assert indicator.toolTip() == "Idle"
    assert "background-color: #111111" in indicator.styleSheet()


def test_desktop_window_toolbar_sidebar_button_toggles_summary_sidebar() -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    window.summary_sidebar_toolbar_button.click()
    app.processEvents()
    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_action.isCheckable() is False
    assert window.summary_sidebar_action.text() == "Left Sidebar"
    assert window.summary_sidebar_action.icon().isNull() is False
    assert window.summary_sidebar_toolbar_button.isChecked() is False
    assert window.summary_sidebar_toolbar_button.toolTip() == "Show the sidebar on the left"
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window.summary_sidebar_reopen_button.click()
    app.processEvents()
    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_action.isCheckable() is False
    assert window.summary_sidebar_action.text() == "Left Sidebar"
    assert window.summary_sidebar_action.icon().isNull() is False
    assert window.summary_sidebar_toolbar_button.isChecked() is True
    assert window.summary_sidebar_toolbar_button.toolTip() == "Hide the sidebar on the left"
    assert window.summary_sidebar_reopen_strip.isVisible() is False


def test_desktop_window_view_menu_summary_sidebar_action_toggles_summary_sidebar() -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    window.summary_sidebar_action.trigger()
    app.processEvents()
    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_action.isCheckable() is False
    assert window.summary_sidebar_action.text() == "Left Sidebar"
    assert window.summary_sidebar_action.icon().isNull() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window.summary_sidebar_action.trigger()
    app.processEvents()
    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_action.isCheckable() is False
    assert window.summary_sidebar_action.text() == "Left Sidebar"
    assert window.summary_sidebar_action.icon().isNull() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is False


def test_desktop_window_manual_summary_sidebar_hide_survives_resize_until_reopened() -> None:
    app = _app()

    window = _new_window()
    window.show()
    window.resize(1300, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is True

    window.summary_sidebar_toolbar_button.click()
    app.processEvents()

    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window.resize(1400, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window.summary_sidebar_reopen_button.click()
    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_reopen_strip.isVisible() is False

    window.summary_sidebar_toolbar_button.click()
    app.processEvents()

    hidden_tabs_button_x = window.hidden_workspace_tabs_collapse_button.mapTo(window, QPoint(0, 0)).x()
    reopen_button_x = window.summary_sidebar_reopen_button.mapTo(window, QPoint(0, 0)).x()
    assert window.summary_sidebar_reopen_spacer.width() == 0
    assert hidden_tabs_button_x > reopen_button_x
    assert window.hidden_workspace_tabs_anchor_spacer.width() == 0

    window.resize(1090, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window.resize(1300, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True


def test_desktop_window_auto_hides_summary_sidebar_below_threshold() -> None:
    app = _app()

    window = _new_window()
    window.show()
    window.resize(1090, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_action.isCheckable() is False

    window.resize(1300, 840)
    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_action.isCheckable() is False


def test_desktop_window_restores_summary_sidebar_when_preference_is_reenabled() -> None:
    app = _app()

    window = _new_window()
    window.show()
    window.resize(1300, 840)
    app.processEvents()

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(show_summary_sidebar_on_left=False)
        )
    )
    app.processEvents()
    assert window.summary_dock.isVisible() is False
    assert window.summary_sidebar_reopen_strip.isVisible() is True

    window._on_preferences_changed(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(show_summary_sidebar_on_left=True)
        )
    )
    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_reopen_strip.isVisible() is False


def test_desktop_window_title_reflects_document_and_dirty_state() -> None:
    _app()

    window = _new_window()

    assert window.windowTitle() == "ActionShellScript Desktop"

    window._editor_dirty = True
    window._update_window_title()
    assert window.windowTitle() == "ActionShellScript Desktop - *New"

    window.current_path = Path("SomeFile.ass")
    window._update_window_title()
    assert window.windowTitle() == "ActionShellScript Desktop - *SomeFile.ass"

    window._editor_dirty = False
    window._update_window_title()
    assert window.windowTitle() == "ActionShellScript Desktop - SomeFile.ass"


def test_desktop_window_title_reflects_dirty_preferences_state() -> None:
    _app()

    window = _new_window()

    assert window.windowTitle() == "ActionShellScript Desktop"

    window._settings_dirty = True
    window._update_window_title()

    assert window.windowTitle() == "ActionShellScript Desktop"

    window.current_path = Path("SomeFile.ass")
    window._update_window_title()
    assert window.windowTitle() == "ActionShellScript Desktop - SomeFile.ass"


def test_desktop_window_load_and_save_do_not_leave_spurious_dirty_state(tmp_path: Path) -> None:
    app = _app()
    path = tmp_path / "sample.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    window.load_script(path)
    assert window.has_unsaved_changes() is False
    assert window.windowTitle() == "ActionShellScript Desktop - sample.ass"


def test_desktop_window_save_script_formats_before_persisting_and_appends_extension(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    window = _new_window()
    window.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=2,
                use_spaces=False,
                auto_format_on_save=True,
            )
        )
    )
    window.current_path = tmp_path / "draft"
    saved: dict[str, object] = {}

    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved.update(path=path, text=document.text),
    )

    window.editor.setPlainText("Func Demo(a,b)\nCallThing(1,2)\nEndFunc\n")
    app.processEvents()

    assert window.save_script() is True
    assert saved["path"] == tmp_path / "draft.ass"
    assert saved["text"] == "Func Demo( a, b )\n\tCallThing(1, 2)\nEndFunc\n"
    assert window.editor.toPlainText() == saved["text"]
    assert window.preview_view.toPlainText() == saved["text"]
    assert window.current_path == tmp_path / "draft.ass"
    assert window.has_unsaved_changes() is False


def test_desktop_window_save_script_updates_last_workspace_when_restore_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    window = _new_window()
    window.committed_settings_bundle.application.restore_last_workspace = True
    window.current_path = tmp_path / "draft"
    saved_calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved_calls.append(("save", str(path), document.text is not None)),
    )
    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda bundle, force=False: saved_calls.append(
            ("settings", bundle.application.last_workspace_path or "", force)
        ),
    )

    window.editor.setPlainText('print("hi")\n')
    app.processEvents()

    assert window.save_script() is True
    assert window.current_path == tmp_path / "draft.ass"
    assert window.committed_settings_bundle.application.last_workspace_path == str(
        tmp_path / "draft.ass"
    )
    assert saved_calls == [
        ("save", str(tmp_path / "draft.ass"), True),
        ("settings", str(tmp_path / "draft.ass"), True),
    ]


def test_desktop_window_save_as_uses_configured_extension_for_bare_filename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window()
    window.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(),
        )
    )
    window.committed_settings_bundle.files = DesktopFilesSettings(file_extension=".foo")
    saved: dict[str, object] = {}

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "new_script"), ""),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved.update(path=path, text=document.text),
    )

    window.editor.setPlainText('print("hi")\n')
    app = QApplication.instance()
    assert app is not None
    app.processEvents()

    assert window.save_script_as() is True
    assert saved["path"] == tmp_path / "new_script.foo"
    assert window.current_path == tmp_path / "new_script.foo"
    assert window._session_last_open_directory == tmp_path


def test_desktop_window_save_as_updates_last_workspace_after_extension_resolution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window()
    window.committed_settings_bundle.application.restore_last_workspace = True
    window.committed_settings_bundle.files = DesktopFilesSettings(file_extension=".foo")
    saved_calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "new_script"), ""),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved_calls.append(("save", str(path), document.text is not None)),
    )
    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda bundle, force=False: saved_calls.append(
            ("settings", bundle.application.last_workspace_path or "", force)
        ),
    )

    window.editor.setPlainText('print("hi")\n')
    app = QApplication.instance()
    assert app is not None
    app.processEvents()

    assert window.save_script_as() is True
    assert window.current_path == tmp_path / "new_script.foo"
    assert window.committed_settings_bundle.application.last_workspace_path == str(
        tmp_path / "new_script.foo"
    )
    assert saved_calls == [
        ("save", str(tmp_path / "new_script.foo"), True),
        ("settings", str(tmp_path / "new_script.foo"), True),
    ]


def test_desktop_window_save_script_skips_last_workspace_when_restore_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    window = _new_window()
    window.committed_settings_bundle.application.restore_last_workspace = False
    window.current_path = tmp_path / "draft"
    saved_calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved_calls.append(("save", str(path), document.text is not None)),
    )
    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda bundle, force=False: saved_calls.append(
            ("settings", bundle.application.last_workspace_path or "", force)
        ),
    )

    window.editor.setPlainText('print("hi")\n')
    app.processEvents()

    assert window.save_script() is True
    assert window.current_path == tmp_path / "draft.ass"
    assert window.committed_settings_bundle.application.last_workspace_path is None
    assert saved_calls == [("save", str(tmp_path / "draft.ass"), True)]


def test_desktop_window_script_save_filter_includes_json_option() -> None:
    _app()

    window = _new_window()

    assert "JSON files (*.json)" in window._script_save_filter()


def test_desktop_window_save_script_preserves_explicit_extension_when_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    window = _new_window()
    window.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(),
        )
    )
    window.committed_settings_bundle.files = DesktopFilesSettings(file_extension=".foo")
    window.current_path = tmp_path / "draft.txt"
    saved: dict[str, object] = {}

    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved.update(path=path, text=document.text),
    )

    window.editor.setPlainText('print("hi")\n')
    app.processEvents()

    assert window.save_script() is True
    assert saved["path"] == tmp_path / "draft.txt"
    assert window.current_path == tmp_path / "draft.txt"


def test_desktop_window_apply_preferences_updates_preview_indentation_policy(
    monkeypatch,
) -> None:
    _app()
    window = _new_window()
    captured: dict[str, object] = {}

    def fake_set_options(options) -> None:
        captured["indent"] = options.indent

    def fake_refresh_preview(*, force_format: bool = False) -> None:
        captured["force_format"] = force_format

    monkeypatch.setattr(window.services.formatting_service, "set_options", fake_set_options)
    monkeypatch.setattr(window, "_refresh_preview", fake_refresh_preview)
    window.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=2,
                use_spaces=False,
            )
        )
    )

    assert captured["indent"] == "\t"
    assert captured["force_format"] is True


def test_desktop_window_apply_preferences_updates_preview_text_from_indent_policy() -> None:
    app = _app()
    window = _new_window()

    window.editor.setPlainText("Func Demo()\nCallThing()\nEndFunc\n")
    app.processEvents()

    window.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=2,
                use_spaces=True,
            )
        )
    )

    assert window.services.formatting_service.options.indent == "  "
    assert "  CallThing()" in window.preview_view.toPlainText()


def test_desktop_window_clearing_editor_back_to_blank_clears_dirty_state() -> None:
    app = _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    window.editor.setPlainText("print(\"hello\")")
    app.processEvents()
    assert window.has_unsaved_changes() is True

    assert window.refresh_preview() is True
    assert window.has_unsaved_changes() is True

    window.editor.selectAll()
    window.editor.insertPlainText("")
    app.processEvents()

    assert window.editor.toPlainText() == ""
    assert window.has_unsaved_changes() is False
    assert window.windowTitle() == "ActionShellScript Desktop"


@pytest.mark.parametrize("restore_last_workspace", [False, True])
def test_desktop_window_load_script_tracks_last_workspace_only_when_restore_enabled(
    tmp_path: Path,
    monkeypatch,
    restore_last_workspace: bool,
) -> None:
    _app()
    path = tmp_path / "sample.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    window.committed_settings_bundle.application.restore_last_workspace = restore_last_workspace
    saved_calls: list[tuple[bool, str | None, bool]] = []

    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda bundle, force=False: saved_calls.append(
            (
                bundle.application.restore_last_workspace,
                bundle.application.last_workspace_path,
                force,
            )
        ),
    )

    window.load_script(path)

    assert window.has_unsaved_changes() is False
    assert window.committed_settings_bundle.application.last_workspace_path == (
        str(path) if restore_last_workspace else None
    )
    assert saved_calls == (
        [(True, str(path), True)] if restore_last_workspace else []
    )


@pytest.mark.parametrize("restore_last_workspace", [False, True])
def test_desktop_window_open_and_close_do_not_prompt_for_preferences_when_loading_workspace(
    tmp_path: Path,
    monkeypatch,
    restore_last_workspace: bool,
) -> None:
    _app()
    path = tmp_path / "sample.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    window.committed_settings_bundle.application.restore_last_workspace = restore_last_workspace
    initial_last_open_directory = window.committed_settings_bundle.application.last_open_directory
    preference_prompts: list[bool] = []
    saved_calls: list[tuple[bool, str | None, str | None, bool]] = []
    captured_args: tuple[object, ...] | None = None
    captured_kwargs: dict[str, object] | None = None

    def fake_get_open_file_name(*args, **kwargs):
        nonlocal captured_args, captured_kwargs
        captured_args = args
        captured_kwargs = kwargs
        return (str(path), "")

    monkeypatch.setattr(
        window._settings_service,
        "save",
        lambda bundle, force=False: saved_calls.append(
            (
                bundle.application.restore_last_workspace,
                bundle.application.last_workspace_path,
                bundle.application.last_open_directory,
                force,
            )
        ),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        fake_get_open_file_name,
    )
    monkeypatch.setattr(
        window,
        "_confirm_discard_or_save_preferences",
        lambda: preference_prompts.append(True) or True,
    )

    assert window.open_script() is True
    assert captured_args is not None
    assert captured_kwargs is not None
    assert captured_args[3] == window._script_save_filter()
    assert window.current_path == path
    assert preference_prompts == []
    assert window.committed_settings_bundle.application.last_workspace_path == (
        str(path) if restore_last_workspace else None
    )
    assert window._session_last_open_directory == path.parent
    assert saved_calls == (
        [(True, str(path), initial_last_open_directory, True)]
        if restore_last_workspace
        else []
    )

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is True
    assert preference_prompts == []


@pytest.mark.parametrize("selected_name", ["note.txt", "archive.bin"])
def test_desktop_window_open_script_uses_configured_extension_filter_and_preserves_selected_path(
    tmp_path: Path,
    monkeypatch,
    selected_name: str,
) -> None:
    _app()

    path = tmp_path / selected_name
    path.write_text('print("hi")\n', encoding="utf-8")

    window = _new_window()
    window.apply_preferences(DesktopPreferences())
    window.committed_settings_bundle.application.last_open_directory = str(
        tmp_path / "stale-session-folder"
    )
    autosave_folder = tmp_path / "recordings"
    window.committed_settings_bundle.files = DesktopFilesSettings(
        file_extension=".foo",
        autosave_output_folder=str(autosave_folder),
    )
    captured_args: tuple[object, ...] | None = None
    captured_kwargs: dict[str, object] | None = None

    def fake_get_open_file_name(*args, **kwargs):
        nonlocal captured_args, captured_kwargs
        captured_args = args
        captured_kwargs = kwargs
        return (str(path), "")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    assert window.open_script() is True
    assert captured_args is not None
    assert captured_kwargs is not None
    assert captured_args[2] == str(autosave_folder)
    assert captured_args[3] == window._script_save_filter()
    assert window.current_path == path
    assert window.editor.toPlainText() == 'print("hi")\n'
    assert window._session_last_open_directory == path.parent


def test_desktop_window_open_script_ignores_persisted_last_open_directory_for_fresh_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    path = tmp_path / "fresh.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = _new_window()
    window.apply_preferences(DesktopPreferences())
    window.committed_settings_bundle.application.last_open_directory = str(
        tmp_path / "persisted-session-folder"
    )
    autosave_folder = tmp_path / "recordings"
    window.committed_settings_bundle.files = DesktopFilesSettings(
        autosave_output_folder=str(autosave_folder),
    )
    captured_args: tuple[object, ...] | None = None
    captured_kwargs: dict[str, object] | None = None

    def fake_get_open_file_name(*args, **kwargs):
        nonlocal captured_args, captured_kwargs
        captured_args = args
        captured_kwargs = kwargs
        return (str(path), "")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    assert window.open_script() is True
    assert captured_args is not None
    assert captured_kwargs is not None
    assert captured_args[2] == str(autosave_folder)
    assert window.current_path == path
    assert window._session_last_open_directory == path.parent


def test_desktop_window_save_script_as_updates_session_open_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    save_folder = tmp_path / "saved-here"
    save_folder.mkdir()
    next_path = tmp_path / "next-folder" / "followup.ass"
    next_path.parent.mkdir()
    next_path.write_text('print("later")\n', encoding="utf-8")

    window = _new_window()
    window.apply_preferences(DesktopPreferences())
    window.committed_settings_bundle.files = DesktopFilesSettings(
        file_extension=".foo",
        autosave_output_folder=str(tmp_path / "recordings"),
    )
    saved: dict[str, object] = {}
    captured_open_args: tuple[object, ...] | None = None
    captured_open_kwargs: dict[str, object] | None = None

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(save_folder / "draft"), ""),
    )
    def fake_get_open_file_name(*args, **kwargs):
        nonlocal captured_open_args, captured_open_kwargs
        captured_open_args = args
        captured_open_kwargs = kwargs
        return (str(next_path), "")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: saved.update(path=path, text=document.text),
    )
    monkeypatch.setattr(window, "_confirm_discard_or_save", lambda: True)

    window.editor.setPlainText('print("hi")\n')
    app = QApplication.instance()
    assert app is not None
    app.processEvents()

    assert window.save_script_as() is True
    assert saved["path"] == save_folder / "draft.foo"
    assert window.current_path == save_folder / "draft.foo"
    assert window._session_last_open_directory == save_folder

    assert window.open_script() is True
    assert captured_open_args is not None
    assert captured_open_kwargs is not None
    assert captured_open_args[2] == str(save_folder)
    assert window.current_path == next_path


def test_desktop_window_open_script_prefers_session_opened_directory_over_files_preferences(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    last_open_directory = tmp_path / "previous"
    last_open_directory.mkdir()
    fallback_folder = tmp_path / "recordings"
    fallback_folder.mkdir()
    path = tmp_path / "chosen.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = _new_window()
    window.apply_preferences(DesktopPreferences())
    window.committed_settings_bundle.files = DesktopFilesSettings(
        file_extension=".foo",
        autosave_output_folder=str(fallback_folder),
    )
    window._session_last_open_directory = last_open_directory
    captured_args: tuple[object, ...] | None = None
    captured_kwargs: dict[str, object] | None = None

    def fake_get_open_file_name(*args, **kwargs):
        nonlocal captured_args, captured_kwargs
        captured_args = args
        captured_kwargs = kwargs
        return (str(path), "")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    assert window.open_script() is True
    assert captured_args is not None
    assert captured_kwargs is not None
    assert captured_args[2] == str(last_open_directory)
    assert window._session_last_open_directory == path.parent


def test_desktop_window_preferences_dialog_stays_clean_after_workspace_load(
    tmp_path: Path,
) -> None:
    _app()
    path = tmp_path / "sample.ass"
    path.write_text('print("hi")\n', encoding="utf-8")

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    window.load_script(path)

    window.open_preferences()

    assert window._preferences_dialog is not None
    assert window._preferences_dialog.is_dirty() is False
    assert window._preferences_dialog.dirty_indicator_label.isVisible() is False


def test_desktop_window_status_bar_mirrors_dirty_marker() -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    window._update_status("Ready")
    assert window.statusBar().currentMessage().startswith("Ready |")

    window._editor_dirty = True
    window._update_status("Unsaved editor changes")
    assert window.statusBar().currentMessage().startswith("* Unsaved editor changes |")


def test_desktop_window_editor_tab_mirrors_dirty_marker() -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    assert window.workspace_tabs.tabText(0) == "Editor"
    assert window.workspace_tabs.tabBar().tabTextColor(0).isValid() is False

    window._editor_dirty = True
    window._update_workspace_tab_labels()
    assert window.workspace_tabs.tabText(0) == "* Editor"
    assert window.workspace_tabs.tabBar().tabTextColor(0).name() == "#8b6a2f"

    window._editor_dirty = False
    window._update_workspace_tab_labels()
    assert window.workspace_tabs.tabText(0) == "Editor"
    assert window.workspace_tabs.tabBar().tabTextColor(0).isValid() is False


def test_desktop_window_uses_configurable_dirty_indicator_theme() -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    preferences = DesktopPreferences(
        appearance=AppearanceTheme(
            editor=EditorAppearanceTheme(),
            dirty_indicators=DirtyIndicatorTheme(
                text="#aa5500",
                accent="#cc7700",
                background="#fff0d9",
                selected_background="#ffd699",
                border="#e6b870",
            )
        )
    )

    window.apply_preferences(preferences)
    window._editor_dirty = True
    window._update_workspace_tab_labels()
    window._update_status("Unsaved editor changes")

    assert window.workspace_tabs.tabBar().tabTextColor(0).name() == "#cc7700"
    assert "#cc7700" in window.statusBar().styleSheet()


def test_desktop_window_marks_unfocused_visible_workspace_tabs_for_attention_and_clears_on_select() -> None:
    _app()

    window = _new_window()
    playback_index = window.workspace_tabs.indexOf(window.playback_output_view)
    assert playback_index >= 0

    window.workspace_tabs.setCurrentWidget(window.editor)
    window._current_playback_result = PlaybackResult(
        source_kind="script_document",
        source_id="doc-1",
        executed_event_count=0,
        success=True,
        delay_ms=0,
        console_output=["new output\n"],
        diagnostics_output=[],
    )

    window._refresh_playback_output(mark_attention=True)
    assert window._workspace_tab_bar.has_tab_attention(playback_index) is True

    window.workspace_tabs.setCurrentWidget(window.playback_output_view)
    assert window._workspace_tab_bar.has_tab_attention(playback_index) is False


def test_desktop_window_does_not_mark_active_workspace_tabs_for_attention() -> None:
    _app()

    window = _new_window()
    playback_index = window.workspace_tabs.indexOf(window.playback_output_view)
    assert playback_index >= 0

    window.workspace_tabs.setCurrentWidget(window.playback_output_view)
    window._current_playback_result = PlaybackResult(
        source_kind="script_document",
        source_id="doc-2",
        executed_event_count=1,
        success=True,
        delay_ms=0,
        console_output=["active tab output\n"],
        diagnostics_output=[],
    )

    window._refresh_playback_output(mark_attention=True)
    assert window._workspace_tab_bar.has_tab_attention(playback_index) is False


def test_desktop_window_does_not_mark_hidden_workspace_tabs_for_attention() -> None:
    _app()

    window = _new_window()
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    assert preview_index >= 0

    window._set_workspace_tab_visible(window.preview_view, False)
    window._refresh_preview(force_format=True, mark_attention=True)

    assert window.workspace_tabs.isTabVisible(preview_index) is False
    assert window._workspace_tab_bar.has_tab_attention(preview_index) is False


def test_desktop_window_honors_workspace_tab_attention_preferences() -> None:
    _app()

    window = _new_window()
    playback_index = window.workspace_tabs.indexOf(window.playback_output_view)
    assert playback_index >= 0

    window.apply_preferences(
        DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(),
                dirty_indicators=DirtyIndicatorTheme(),
                workspace_tab_attention=WorkspaceTabAttentionTheme(
                    enabled=False,
                    accent="#3366cc",
                ),
            ),
            scripting=ScriptingSettings(),
            search_results=SearchResultsTheme(),
        )
    )
    window.workspace_tabs.setCurrentWidget(window.editor)
    window._current_playback_result = PlaybackResult(
        source_kind="script_document",
        source_id="doc-3",
        executed_event_count=0,
        success=True,
        delay_ms=0,
        console_output=["attention disabled\n"],
        diagnostics_output=[],
    )

    window._refresh_playback_output(mark_attention=True)
    assert window._workspace_tab_bar.has_tab_attention(playback_index) is False

    window.apply_preferences(
        DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(),
                dirty_indicators=DirtyIndicatorTheme(),
                workspace_tab_attention=WorkspaceTabAttentionTheme(
                    enabled=True,
                    accent="#3366cc",
                ),
            ),
            scripting=ScriptingSettings(),
            search_results=SearchResultsTheme(),
        )
    )
    window._refresh_playback_output(mark_attention=True)
    assert window._workspace_tab_bar.has_tab_attention(playback_index) is True


def test_desktop_window_forwards_recording_preferences_into_record_flow(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    captured: _AboutCapture = {
        "title": "",
        "text": "",
        "icon_is_null": False,
    }

    class FakeRecordingService:
        def start_recording(self, *, session_id: str):
            captured["session_id"] = session_id
            return type(
                "Session",
                (),
                {
                    "session_id": session_id,
                    "events": [],
                    "state": type("State", (), {"value": "recording"})(),
                    "started_at_ms": 1,
                    "stopped_at_ms": 2,
                    "duration_ms": lambda self: 1,
                },
            )()

        def summarize(self, session):
            _ = session
            return type(
                "Summary",
                (),
                {
                    "session_id": "session-1",
                    "state": "recording",
                    "event_count": 0,
                    "started_at_ms": 1,
                    "stopped_at_ms": 2,
                    "duration_ms": 1,
                },
            )()

    def fake_build_recording_service():
        captured["recording_settings"] = window.script_controller._recording_settings
        return FakeRecordingService()

    monkeypatch.setattr(
        window.script_controller,
        "_build_recording_service",
        fake_build_recording_service,
    )

    bundle = DesktopSettingsBundle(
        recording=DesktopRecordingSettings(
            capture_mouse_moves=False,
            capture_mouse_buttons=True,
            capture_mouse_wheel=False,
            capture_keyboard=True,
            mouse_move_threshold_px=21,
            exclude_main_window_during_recording=False,
        )
    )
    window._on_preferences_changed(bundle)

    assert window.record_script() is True
    thread = window.script_controller._script_operation_thread
    assert thread is not None
    thread.join(timeout=1.0)
    window.script_controller._poll_script_operation()

    assert "recording_settings" in captured
    recording_settings = cast(DesktopRecordingSettings, captured["recording_settings"])
    assert recording_settings.capture_mouse_moves is False
    assert recording_settings.capture_mouse_buttons is True
    assert recording_settings.capture_mouse_wheel is False
    assert recording_settings.capture_keyboard is True
    assert recording_settings.mouse_move_threshold_px == 21
    assert recording_settings.exclude_main_window_during_recording is False


def test_desktop_window_disables_editor_during_recording_and_restores_it_after_conversion(
    monkeypatch,
) -> None:
    app = _app()

    window = _new_window()
    starting_document = ScriptDocument(document_id="doc-1", text="alpha beta alpha\n")
    recorded_document = ScriptDocument(
        document_id="doc-2",
        text="alpha beta alpha\n",
        generated_from_recording=True,
        source_session_id="session-1",
        source_action_count=1,
    )
    session = RecordingSession(session_id="session-1")

    class FakeRecordingService:
        def __init__(self) -> None:
            self._session = session
            self._recording = False

        def start_recording(self, *, session_id: str):
            self._recording = True
            assert session_id
            return self._session

        def is_recording(self) -> bool:
            return self._recording

        def stop_recording(self):
            self._recording = False
            return self._session

        def summarize(self, _session):
            return type(
                "Summary",
                (),
                {
                    "session_id": "session-1",
                    "state": "recording",
                    "event_count": 1,
                    "started_at_ms": 1,
                    "stopped_at_ms": 2,
                    "duration_ms": 1,
                },
            )()

    monkeypatch.setattr(window.script_controller, "_build_recording_service", lambda: FakeRecordingService())
    monkeypatch.setattr(window, "_convert_recording_session", lambda incoming: recorded_document)
    monkeypatch.setattr(window, "_auto_save_recording_session", lambda _session: None)
    monkeypatch.setattr(window, "_auto_save_converted_recording_document", lambda _document: None)

    window.current_document = starting_document
    window._sync_saved_document_text()
    window.editor.setPlainText(starting_document.text)
    _open_replace_sidebar(
        window,
        find_text="alpha",
        replace_text="omega",
    )
    app.processEvents()

    assert window.record_script() is True
    thread = window.script_controller._script_operation_thread
    assert thread is not None
    app.processEvents()
    assert window.editor.isEnabled() is False
    assert window.undo_action.isEnabled() is False
    assert window.redo_action.isEnabled() is False
    assert window.cut_action.isEnabled() is False
    assert window.paste_action.isEnabled() is False
    assert window.delete_action.isEnabled() is False
    assert window.replace_current_action.isEnabled() is False
    assert window.replace_all_action.isEnabled() is False

    locked_text = window.editor.toPlainText()

    QTest.keyClicks(window.editor, "typed while recording")
    QTest.keyClick(window.editor, Qt.Key.Key_Backspace)
    window.replace_current_action.trigger()
    window.replace_all_action.trigger()
    assert window.editor.toPlainText() == locked_text

    assert window.stop_script() is True
    thread.join(timeout=1.0)
    window.script_controller._poll_script_operation()
    app.processEvents()

    assert window.editor.isEnabled() is True
    assert window.undo_action.isEnabled() is True
    assert window.redo_action.isEnabled() is True
    assert window.cut_action.isEnabled() is True
    assert window.paste_action.isEnabled() is True
    assert window.delete_action.isEnabled() is True
    assert window.replace_current_action.isEnabled() is True
    assert window.replace_all_action.isEnabled() is True
    assert window.current_document == recorded_document
    assert window.editor.toPlainText() == recorded_document.text
    assert window.has_unsaved_changes() is False

    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClicks(window.editor, "!")
    assert window.editor.toPlainText() == "alpha beta alpha\n!"

    window.replace_current_action.trigger()
    assert window.editor.toPlainText() == "omega beta alpha\n!"


def test_desktop_window_records_with_excluded_main_window_and_persists_provenance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _app()

    window = _new_window(config_dir=tmp_path)
    window.show()
    app.processEvents()

    saved_path = tmp_path / "recorded.ass"
    session = RecordingSession(
        session_id="session-exclusion",
        state=RecordingState.STOPPED,
        started_at_ms=10,
        stopped_at_ms=25,
        events=[
            {"type": "key_down", "key": "ctrl", "timestamp_ms": 10},
        ],
    )
    captured: dict[str, object] = {}

    class FakeRecordingService:
        def __init__(self) -> None:
            self._recording = False

        def start_recording(self, *, session_id: str):
            captured["session_id"] = session_id
            self._recording = True
            return session

        def is_recording(self) -> bool:
            return self._recording

        def stop_recording(self):
            self._recording = False
            return session

        def summarize(self, current_session):
            return type(
                "Summary",
                (),
                {
                    "session_id": current_session.session_id,
                    "state": current_session.state.value,
                    "event_count": len(current_session.events),
                    "started_at_ms": current_session.started_at_ms,
                    "stopped_at_ms": current_session.stopped_at_ms,
                    "duration_ms": current_session.duration_ms(),
                },
            )()

    def fake_build_recording_service():
        captured["excluded_window_hwnds"] = window.script_controller._recording_excluded_window_hwnds()
        return FakeRecordingService()

    monkeypatch.setattr(window.script_controller, "_build_recording_service", fake_build_recording_service)
    monkeypatch.setattr(window, "_suggested_recording_script_save_path", lambda _document: saved_path)
    monkeypatch.setattr(window, "_auto_save_recording_session", lambda _session: None)

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="direct_import",
                exclude_main_window_during_recording=True,
            ),
            files=DesktopFilesSettings(
                autosave_enabled=True,
                raw_autosave_enabled=False,
            ),
        )
    )

    assert window.record_script() is True
    thread = window.script_controller._script_operation_thread
    assert thread is not None
    app.processEvents()

    expected_hwnd = int(window.winId())
    assert captured["excluded_window_hwnds"] == (expected_hwnd,)

    assert window.stop_script() is True
    thread.join(timeout=1.0)
    window.script_controller._poll_script_operation()
    app.processEvents()

    assert window.current_path == saved_path
    assert window.current_document.source_path == str(saved_path)
    assert window.current_document.generated_from_recording is True
    assert window.current_document.recording_conversion_route == "direct_import"
    assert window.current_document.source_capture_excluded_main_window is True
    assert window.current_document.is_dirty is False
    assert window.current_document.last_saved_version == window.current_document.version.value
    assert saved_path.exists() is True
    assert saved_path.with_name(f"{saved_path.name}.meta.json").exists() is True
    assert saved_path.read_text(encoding="utf-8") == (
        build_recording_provenance_header(
            recording_conversion_route="direct_import",
            source_capture_excluded_main_window=True,
        )
        + window.current_document.text
    )

    loaded_document = window.services.document_store.load(saved_path)
    assert loaded_document.source_path == str(saved_path)
    assert loaded_document.source_capture_excluded_main_window is True
    assert loaded_document.recording_conversion_route == "direct_import"

    captured_dialog: dict[str, str] = {}

    def fake_exec(self) -> int:
        captured_dialog["text"] = self.status_view.toPlainText()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DocumentStatusDialog, "exec", fake_exec)
    window.document_status_action.trigger()

    assert captured_dialog["text"] == (
        f"Document ID: {window.current_document.document_id}\n"
        f"Path: {saved_path}\n"
        f"Version: {window.current_document.version.value}\n"
        f"Line count: {window.current_document.line_count()}\n"
        "Document dirty: False\n"
        "Editor dirty: False\n"
        "Analysis stale after edits: False\n"
        f"Last saved version: {window.current_document.last_saved_version}\n"
        f"Source session ID: {window.current_document.source_session_id}\n"
        f"Source action count: {window.current_document.source_action_count}\n"
        "Recording conversion route: Direct import\n"
        "Recording exclusion: enabled (main window excluded during recording)\n"
        "Generated from recording: True"
    )


@pytest.mark.parametrize(
    (
        "choice",
        "expected_record_calls",
        "expected_save_calls",
        "expected_text",
        "expected_dirty",
        "expected_path",
    ),
    [
        (
            QMessageBox.StandardButton.Cancel,
            0,
            0,
            "print(\"hello\")\n",
            True,
            Path("existing.ass"),
        ),
        (QMessageBox.StandardButton.Discard, 1, 0, "", False, None),
        (QMessageBox.StandardButton.Save, 1, 1, "", False, None),
    ],
)
def test_desktop_window_record_prompts_for_unsaved_editor_changes(
    monkeypatch,
    choice: QMessageBox.StandardButton,
    expected_record_calls: int,
    expected_save_calls: int,
    expected_text: str,
    expected_dirty: bool,
    expected_path: Path | None,
) -> None:
    app = _app()

    window = _new_window()
    window.current_path = Path("existing.ass")
    window.editor.setPlainText("print(\"hello\")\n")
    app.processEvents()
    assert window.has_unsaved_changes() is True

    record_calls: list[bool] = []
    save_calls: list[bool] = []

    monkeypatch.setattr(
        "apps.desktop.window.question_save_discard_cancel",
        lambda *args, **kwargs: choice,
    )
    monkeypatch.setattr(
        window,
        "save_script",
        lambda: save_calls.append(True) or True,
    )
    monkeypatch.setattr(
        window.script_controller,
        "record",
        lambda: record_calls.append(True) or True,
    )

    assert window.record_script() is (choice != QMessageBox.StandardButton.Cancel)
    assert len(record_calls) == expected_record_calls
    assert len(save_calls) == expected_save_calls
    assert window.editor.toPlainText() == expected_text
    assert window.has_unsaved_changes() is expected_dirty
    assert window.current_path == expected_path


@pytest.mark.parametrize(
    ("choice", "expected_record_calls", "expected_save_calls", "expected_text", "expected_dirty", "expected_path"),
    [
        (
            QMessageBox.StandardButton.Cancel,
            0,
            0,
            'print("hello")\n',
            True,
            Path("existing.ass"),
        ),
        (
            QMessageBox.StandardButton.Discard,
            1,
            0,
            "",
            False,
            None,
        ),
        (
            QMessageBox.StandardButton.Save,
            1,
            1,
            "",
            False,
            None,
        ),
    ],
)
def test_desktop_window_record_toolbar_button_uses_real_unsaved_changes_dialog_choices(
    choice: QMessageBox.StandardButton,
    expected_record_calls: int,
    expected_save_calls: int,
    expected_text: str,
    expected_dirty: bool,
    expected_path: Path | None,
    monkeypatch,
) -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    window.current_path = Path("existing.ass")
    window.editor.setPlainText("print(\"hello\")\n")
    app.processEvents()
    assert window.has_unsaved_changes() is True

    record_calls: list[bool] = []
    save_calls: list[bool] = []

    def fake_save_script() -> bool:
        save_calls.append(True)
        return True

    def fake_record() -> bool:
        record_calls.append(True)
        return True

    monkeypatch.setattr(window, "save_script", fake_save_script)
    monkeypatch.setattr(window.script_controller, "record", fake_record)

    def click_cancel_on_message_box() -> None:
        for widget in app.topLevelWidgets():
            if not isinstance(widget, QMessageBox) or not widget.isVisible():
                continue
            button_text = {
                QMessageBox.StandardButton.Cancel: "Cancel",
                QMessageBox.StandardButton.Discard: "Don't Save",
                QMessageBox.StandardButton.Save: "Save",
            }[choice]
            clicked_button = next((button for button in widget.buttons() if button.text() == button_text), None)
            assert clicked_button is not None
            QTest.mouseClick(clicked_button, Qt.MouseButton.LeftButton)
            return
        raise AssertionError("Unsaved changes dialog did not appear.")

    QTimer.singleShot(0, click_cancel_on_message_box)

    record_button = _required_child(window, QToolButton, "recordScriptToolbarButton")
    QTest.mouseClick(record_button, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert len(record_calls) == expected_record_calls
    assert len(save_calls) == expected_save_calls
    assert window.editor.toPlainText() == expected_text
    assert window.current_path == expected_path
    assert window.has_unsaved_changes() is expected_dirty


def test_desktop_window_auto_saves_promoted_recording_session_into_editor_document(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window()
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}
    autosave_folder = tmp_path / "recordings"

    class FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 1, 9, 8, 7)

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr("apps.desktop.window.datetime", FakeDateTime)
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda session_arg, path_arg: captured.update(
            raw_saved_session=session_arg,
            raw_saved_path=Path(path_arg),
        ),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: captured.update(saved_path=path, saved_document=document),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                file_extension=".foo",
                autosave_enabled=True,
                autosave_file_name="capture.foo",
                autosave_timestamp_suffix=True,
                autosave_output_folder=str(autosave_folder),
                raw_autosave_enabled=True,
                raw_autosave_file_name="raw_filename",
                raw_autosave_timestamp_suffix=False,
                raw_autosave_output_folder=str(autosave_folder / "raw"),
            ),
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured["raw_saved_session"] is session
    assert captured["raw_saved_path"] == autosave_folder / "raw" / "raw_filename.json"
    assert captured["saved_path"] == autosave_folder / "capture_20260501-090807.foo"
    assert captured["saved_document"] is promoted
    assert window.current_document == promoted
    assert window.editor.toPlainText() == promoted.text
    assert window.current_path == autosave_folder / "capture_20260501-090807.foo"
    assert window.current_analysis is None
    assert window.has_unsaved_changes() is False
    assert "Saved " in window.statusBar().currentMessage()


def test_desktop_window_auto_saves_promoted_recording_session_without_timestamp_suffix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window()
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}
    autosave_folder = tmp_path / "recordings"

    class FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 1, 9, 8, 7)

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr("apps.desktop.window.datetime", FakeDateTime)
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda session_arg, path_arg: captured.update(
            raw_saved_session=session_arg,
            raw_saved_path=Path(path_arg),
        ),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: captured.update(saved_path=path, saved_document=document),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                file_extension=".foo",
                autosave_enabled=True,
                autosave_file_name="capture.foo",
                autosave_timestamp_suffix=False,
                autosave_output_folder=str(autosave_folder),
                raw_autosave_enabled=True,
                raw_autosave_file_name="raw_custom_name",
                raw_autosave_timestamp_suffix=True,
                raw_autosave_output_folder=str(autosave_folder / "raw"),
            ),
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured["raw_saved_session"] is session
    assert captured["raw_saved_path"] == autosave_folder / "raw" / "raw_custom_name_20260501-090807.json"
    assert captured["saved_path"] == autosave_folder / "capture.foo"
    assert captured["saved_document"] is promoted
    assert window.current_path == autosave_folder / "capture.foo"
    assert "Saved " in window.statusBar().currentMessage()


def test_desktop_window_resolves_relative_recording_autosave_folder_against_config_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window(config_dir=tmp_path)
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}

    class FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 1, 9, 8, 7)

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr("apps.desktop.window.datetime", FakeDateTime)
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda session_arg, path_arg: captured.update(
            raw_saved_session=session_arg,
            raw_saved_path=Path(path_arg),
        ),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: captured.update(saved_path=path, saved_document=document),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                autosave_enabled=True,
                autosave_file_name="filename",
                autosave_timestamp_suffix=True,
                autosave_output_folder="recordings",
                raw_autosave_enabled=True,
                raw_autosave_file_name="raw_filename",
                raw_autosave_timestamp_suffix=True,
                raw_autosave_output_folder="raw-recordings",
            )
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured["raw_saved_path"] == tmp_path / "raw-recordings" / "raw_filename_20260501-090807.json"
    assert captured["saved_path"] == tmp_path / "recordings" / "filename_20260501-090807.ass"
    assert captured["saved_document"] is promoted
    assert window.current_path == tmp_path / "recordings" / "filename_20260501-090807.ass"


def test_desktop_window_does_not_nest_relative_recording_autosave_folder_under_last_saved_recording(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    window = _new_window(config_dir=tmp_path)
    window.current_path = tmp_path / "recordings" / "filename.ass"
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}

    class FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 1, 9, 8, 7)

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr("apps.desktop.window.datetime", FakeDateTime)
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda session_arg, path_arg: captured.update(
            raw_saved_session=session_arg,
            raw_saved_path=Path(path_arg),
        ),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: captured.update(saved_path=path, saved_document=document),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                autosave_enabled=True,
                autosave_file_name="filename",
                autosave_timestamp_suffix=True,
                autosave_output_folder="recordings",
                raw_autosave_enabled=True,
                raw_autosave_file_name="raw_filename",
                raw_autosave_timestamp_suffix=True,
                raw_autosave_output_folder="recordings",
            )
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured["raw_saved_path"] == tmp_path / "recordings" / "raw_filename_20260501-090807.json"
    assert captured["saved_path"] == tmp_path / "recordings" / "filename_20260501-090807.ass"
    assert captured["saved_document"] is promoted
    assert window.current_path == tmp_path / "recordings" / "filename_20260501-090807.ass"


def test_desktop_window_resolves_relative_recording_autosave_folder_against_app_root_when_config_dir_is_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()
    monkeypatch.setenv("APPDATA", str(tmp_path))

    window = _new_window(config_dir=tmp_path / "config")
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}

    class FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 1, 9, 8, 7)

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr("apps.desktop.window.datetime", FakeDateTime)
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda session_arg, path_arg: captured.update(
            raw_saved_session=session_arg,
            raw_saved_path=Path(path_arg),
        ),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda path, document: captured.update(saved_path=path, saved_document=document),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                autosave_enabled=True,
                autosave_file_name="filename",
                autosave_timestamp_suffix=True,
                autosave_output_folder="recordings",
                raw_autosave_enabled=True,
                raw_autosave_file_name="raw_filename",
                raw_autosave_timestamp_suffix=True,
                raw_autosave_output_folder="recordings",
            )
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured["raw_saved_path"] == tmp_path / "recordings" / "raw_filename_20260501-090807.json"
    assert captured["saved_path"] == tmp_path / "recordings" / "filename_20260501-090807.ass"
    assert captured["saved_document"] is promoted
    assert window.current_path == tmp_path / "recordings" / "filename_20260501-090807.ass"


def test_desktop_window_skips_raw_recording_autosave_when_disabled(monkeypatch) -> None:
    _app()

    window = _new_window()
    session = RecordingSession(session_id="session-1")
    promoted = ScriptDocument(
        document_id="doc-1",
        text='SendText("hello")\n',
        source_session_id="session-1",
        source_action_count=2,
        generated_from_recording=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: captured.update(session=incoming) or promoted,
    )
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda *args, **kwargs: captured.update(raw_save_called=True),
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda *args, **kwargs: captured.update(save_called=True),
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(
                autosave_enabled=True,
                autosave_output_folder=r"C:\temp\recordings",
                raw_autosave_enabled=False,
                raw_autosave_output_folder=r"C:\temp\raw-recordings",
            )
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert captured["session"] is session
    assert captured.get("raw_save_called") is None
    assert captured.get("save_called") is True
    assert window.current_document == promoted
    assert window.current_path is not None
    assert "Saved " in window.statusBar().currentMessage()
    assert window.summary_view.toPlainText() == ""


def test_desktop_window_renders_raw_recording_output_in_dedicated_tab(
    monkeypatch,
) -> None:
    _app()

    window = _new_window()
    session = RecordingSession(
        session_id="session-raw",
        state=RecordingState.STOPPED,
        started_at_ms=100,
        stopped_at_ms=180,
        events=[
            {"type": "mouse_move", "x": 10, "y": 20},
            {"type": "key_down", "key": "ctrl"},
        ],
    )
    promoted = ScriptDocument(
        document_id="doc-raw",
        text='SendText("hello")\n',
        source_session_id="session-raw",
        source_action_count=2,
        generated_from_recording=True,
    )

    monkeypatch.setattr(
        window,
        "_convert_recording_session",
        lambda incoming: promoted if incoming is session else promoted,
    )
    monkeypatch.setattr(
        window.services.document_store,
        "save",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "apps.desktop.window.save_raw_session",
        lambda *args, **kwargs: None,
    )

    window._on_preferences_changed(
        DesktopSettingsBundle(
            recording=DesktopRecordingSettings(
                recording_conversion_mode="promote_generated",
            ),
            files=DesktopFilesSettings(raw_autosave_enabled=False),
        )
    )
    window.script_controller.recordingResultReady.emit(session)

    assert window.raw_recording_view.toPlainText() == build_raw_recording_text(session)


def test_desktop_window_new_prompts_for_unsaved_preferences(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    window._settings_dirty = True
    prompted: list[bool] = []

    monkeypatch.setattr(window, "_confirm_discard_or_save", lambda: True)
    monkeypatch.setattr(
        window,
        "_confirm_discard_or_save_preferences",
        lambda: prompted.append(True) or False,
    )

    assert window.new_document() is False
    assert prompted == [True]


def test_desktop_window_restores_hotkeys_search_text_in_preferences_dialog() -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    window.open_preferences()
    assert window._preferences_dialog is not None
    window._preferences_dialog.hotkeys_search.setText("save")
    window._preferences_dialog.close()
    window._preferences_dialog = None

    window.open_preferences()

    assert window._preferences_dialog is not None
    assert window._preferences_dialog.hotkeys_search.text() == "save"
    assert window._preferences_dialog.hotkeys_table.isRowHidden(2) is False


def test_desktop_window_exposes_script_menu_actions() -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )

    menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert menu_titles[:4] == ["File", "Edit", "Search", "View"]
    assert menu_titles.index("Script") < menu_titles.index("Debug") < menu_titles.index("Tools") < menu_titles.index("Settings")
    assert "Tools" in menu_titles
    assert window.undo_action.icon().isNull() is False
    assert window.redo_action.icon().isNull() is False
    assert window.cut_action.icon().isNull() is False
    assert window.copy_action.icon().isNull() is False
    assert window.paste_action.icon().isNull() is False
    assert window.delete_action.icon().isNull() is False
    assert window.select_all_action.icon().isNull() is False
    assert window.about_action.icon().isNull() is False
    assert window.exit_action.icon().isNull() is False
    assert [action.text() for action in window.search_menu.actions()] == [
        "Find...",
        "Next",
        "Previous",
        "",
        "Select and Next",
        "Select and Previous",
        "",
        "Replace...",
        "Replace Next",
        "Replace All",
        "Go to...",
    ]
    assert window.find_next_action.icon().isNull() is False
    assert window.find_previous_action.icon().isNull() is False
    assert window.select_and_find_next_action.icon().isNull() is False
    assert window.select_and_find_previous_action.icon().isNull() is False
    assert window.replace_action.icon().isNull() is False
    assert window.replace_current_action.icon().isNull() is False
    assert window.replace_all_action.icon().isNull() is False

    assert window.find_action.isEnabled() is True
    assert window.replace_action.isEnabled() is True
    assert window.find_next_action.isEnabled() is False
    assert window.find_previous_action.isEnabled() is False
    assert window.select_and_find_next_action.isEnabled() is False
    assert window.select_and_find_previous_action.isEnabled() is False
    assert window.replace_current_action.isEnabled() is False
    assert window.replace_all_action.isEnabled() is False

    assert [action.text() for action in window.script_menu.actions()] == [
        "Preview Play",
        "Play",
        "Record",
        "Stop",
    ]
    assert [action.text() for action in window.debug_menu.actions()] == [
        "Debugger",
        "Run",
        "Continue",
        "Pause",
        "Restart",
        "Stop",
        "",
        "Toggle Breakpoint",
        "Clear Breakpoints",
        "",
        "Step Into",
        "Step Over",
        "Step Out",
    ]
    assert [action.text() for action in window.tools_menu.actions()] == [
        "Pixel Inspector...",
    ]
    assert window.preview_play_script_action.shortcut().isEmpty() is True
    assert window.play_script_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Enter"
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert window.record_script_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Shift+R"
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert window.stop_script_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Shift+Esc"
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert "Ctrl+Enter" in window.play_script_action.toolTip()
    assert "Ctrl+Shift+R" in window.record_script_action.toolTip()
    assert "Shift+Esc" in window.stop_script_action.toolTip()
    assert window.play_script_action.icon().isNull() is False
    assert window.record_script_action.icon().isNull() is False
    assert window.stop_script_action.icon().isNull() is False
    assert window.preview_play_script_action.icon().isNull() is False
    assert window.new_action.icon().isNull() is False
    assert window.open_action.icon().isNull() is False
    assert window.save_action.icon().isNull() is False
    assert window.save_as_action.icon().isNull() is False
    assert window.analyze_action.icon().isNull() is False
    assert window.preview_action.icon().isNull() is False


def test_desktop_window_about_dialog_uses_info_window_icon(monkeypatch) -> None:
    _app()

    window = _new_window()
    captured: _AboutCapture = {
        "title": "",
        "body_text": "",
        "info_text": "",
        "extra_text": "",
        "info_icon_is_null": False,
        "frog_icon_is_null": False,
        "about_icon_is_null": False,
    }

    def fake_exec(self):
        captured["title"] = self.windowTitle()
        header_row = self.layout().itemAt(0).widget()
        assert header_row is not None
        header_row_layout = header_row.layout()
        assert header_row_layout is not None
        left_column = header_row_layout.itemAt(0).widget()
        text_block = header_row_layout.itemAt(1).widget()
        assert left_column is not None
        assert text_block is not None
        left_column_layout = left_column.layout()
        assert left_column_layout is not None
        left_info_icon = left_column_layout.itemAt(0).widget()
        left_frog_icon = left_column_layout.itemAt(1).widget()
        assert left_info_icon is not None
        assert left_frog_icon is not None
        body_label = self.findChild(QLabel, "aboutBodyLabel")
        info_copy_label = self.findChild(QLabel, "aboutInfoCopyLabel")
        extra_copy_label = self.findChild(QLabel, "aboutExtraCopyLabel")
        info_icon_label = self.findChild(QLabel, "aboutInfoIconLabel")
        frog_icon_label = self.findChild(QLabel, "aboutFrogIconLabel")
        assert body_label is not None
        assert info_copy_label is not None
        assert extra_copy_label is not None
        assert info_icon_label is not None
        assert frog_icon_label is not None
        captured["body_text"] = body_label.text()
        captured["info_text"] = info_copy_label.text()
        captured["extra_text"] = extra_copy_label.text()
        captured["info_icon_is_null"] = info_icon_label.pixmap().isNull() if info_icon_label.pixmap() is not None else True
        captured["frog_icon_is_null"] = frog_icon_label.pixmap().isNull() if frog_icon_label.pixmap() is not None else True
        captured["about_icon_is_null"] = self.windowIcon().isNull()
        assert left_info_icon is info_icon_label
        assert left_frog_icon is frog_icon_label
        return 0

    monkeypatch.setattr(QDialog, "exec", fake_exec, raising=False)

    window.open_about()

    assert captured["title"] == "About ActionShellScript"
    assert "recording, editing, analyzing, and replaying" in captured["body_text"]
    assert "capture sessions" in captured["info_text"]
    assert "recording-to-script workflow" in captured["extra_text"]
    assert captured["info_icon_is_null"] is False
    assert captured["frog_icon_is_null"] is False
    assert captured["about_icon_is_null"] is False
    assert window.windowIcon().isNull() is False
    assert window.find_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        QKeySequence.StandardKey.Find
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert window.find_action.icon().isNull() is False
    assert window.debugger_action.icon().isNull() is False
    assert window.view_debugger_tab_action.icon().isNull() is False
    assert window.run_debug_menu_action.icon().isNull() is False
    assert window.restart_debug_menu_action.icon().isNull() is False
    assert window.debug_step_into_action.icon().isNull() is False
    assert window.debug_step_over_action.icon().isNull() is False
    assert window.debug_step_out_action.icon().isNull() is False
    assert window.debug_continue_action.icon().isNull() is False
    assert window.debug_pause_action.icon().isNull() is False
    assert window.debug_restart_action.icon().isNull() is False
    assert window.debug_stop_action.icon().isNull() is False
    assert window.debug_continue_button.icon().isNull() is False
    assert window.debug_pause_button.icon().isNull() is False
    assert window.debug_step_over_button.icon().isNull() is False
    assert window.debug_step_button.icon().isNull() is False
    assert window.debug_step_out_button.icon().isNull() is False
    assert window.debug_restart_button.icon().isNull() is False
    assert window.debug_stop_button.icon().isNull() is False
    assert window.preferences_action.icon().isNull() is False
    assert window.documentation_action.icon().isNull() is False
    assert window.pixel_inspector_action.icon().isNull() is False
    assert "spacing: 3px" in window.main_toolbar.styleSheet()
    assert window.file_toolbar_group.styleSheet() == ""
    assert window.analysis_toolbar_group.styleSheet() == ""
    assert window.toolbar_right_spacer.objectName() == "toolbarRightSpacer"
    assert window.toolbar_right_spacer.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert window.debug_toolbar_group.styleSheet() == ""
    assert window.debug_primary_toolbar_group.styleSheet() == ""
    assert window.settings_toolbar_group.styleSheet() == ""
    assert _layout_widget_at(window.main_toolbar.layout(), 0) is window.file_toolbar_group
    assert _layout_widget_at(window.main_toolbar.layout(), 2) is window.analysis_toolbar_group
    assert _layout_widget_at(window.main_toolbar.layout(), 4) is window.playback_toolbar_group
    assert _layout_widget_at(window.main_toolbar.layout(), 6) is window.debug_toolbar_group
    assert _layout_widget_at(window.main_toolbar.layout(), 8) is window.toolbar_right_spacer
    assert _layout_widget_at(window.main_toolbar.layout(), 9) is window.settings_toolbar_group
    new_button = _required_child(window.file_toolbar_group, QToolButton, "newScriptToolbarButton")
    open_button = _required_child(window.file_toolbar_group, QToolButton, "openScriptToolbarButton")
    save_button = _required_child(window.file_toolbar_group, QToolButton, "saveScriptToolbarButton")
    save_as_button = _required_child(window.file_toolbar_group, QToolButton, "saveAsScriptToolbarButton")
    search_button = _required_child(window.file_toolbar_group, QToolButton, "searchScriptToolbarButton")
    analyze_button = _required_child(window.analysis_toolbar_group, QToolButton, "analyzeScriptToolbarButton")
    preview_button = _required_child(window.analysis_toolbar_group, QToolButton, "previewScriptToolbarButton")
    preview_play_button = window.playback_toolbar_group.findChild(
        QToolButton,
        "previewPlayScriptToolbarButton",
    )
    debug_button = _required_child(window.debug_toolbar_group, QToolButton, "debugScriptToolbarButton")
    view_debugger_tab_button = _required_child(window.debug_toolbar_group, QToolButton, "viewDebugTabToolbarButton")
    debug_primary_group = window.debug_primary_toolbar_group
    assert debug_primary_group is not None
    breakpoint_controls_group = window.debug_breakpoint_toolbar_group
    assert breakpoint_controls_group is not None
    clear_breakpoints_button = _required_child(window.debug_toolbar_group, QToolButton, "clearBreakpointsScriptToolbarButton")
    debug_step_into_button = _required_child(window.debug_toolbar_group, QToolButton, "debugStepIntoToolbarButton")
    debug_step_over_button = _required_child(window.debug_toolbar_group, QToolButton, "debugStepOverToolbarButton")
    debug_step_out_button = _required_child(window.debug_toolbar_group, QToolButton, "debugStepOutToolbarButton")
    debug_continue_button = _required_child(window.debug_toolbar_group, QToolButton, "debugContinueToolbarButton")
    debug_pause_button = _required_child(window.debug_toolbar_group, QToolButton, "debugPauseToolbarButton")
    debug_restart_button = _required_child(window.debug_toolbar_group, QToolButton, "debugRestartToolbarButton")
    debug_stop_button = _required_child(window.debug_toolbar_group, QToolButton, "debugStopToolbarButton")
    debug_toggle_breakpoint_button = _required_child(
        window.debug_breakpoint_toolbar_group,
        QToolButton,
        "toggleBreakpointToolbarButton",
    )
    toggle_breakpoint_button = _required_child(window.debug_toolbar_group, QToolButton, "toggleBreakpointToolbarButton")
    clear_breakpoints_button = _required_child(window.debug_toolbar_group, QToolButton, "clearBreakpointsScriptToolbarButton")
    play_button = _required_child(window.playback_toolbar_group, QToolButton, "playScriptToolbarButton")
    record_button = _required_child(window.playback_toolbar_group, QToolButton, "recordScriptToolbarButton")
    stop_button = _required_child(window.playback_toolbar_group, QToolButton, "stopScriptToolbarButton")
    inspector_button = _required_child(window.settings_toolbar_group, QToolButton, "pointerProbeScriptToolbarButton")
    preferences_button = _required_child(window.settings_toolbar_group, QToolButton, "preferencesScriptToolbarButton")
    documentation_button = _required_child(window.settings_toolbar_group, QToolButton, "documentationScriptToolbarButton")
    assert new_button is not None
    assert open_button is not None
    assert save_button is not None
    assert save_as_button is not None
    assert search_button is not None
    assert analyze_button is not None
    assert preview_button is not None
    assert debug_button is not None
    assert view_debugger_tab_button is not None
    assert window.view_debugger_tab_action.text() == "Debugger"
    assert window.view_debugger_tab_action.toolTip() == "Debugger"
    assert view_debugger_tab_button.toolTip() == "Debugger"
    assert debug_step_into_button is not None
    assert debug_step_over_button is not None
    assert debug_step_out_button is not None
    assert debug_continue_button is not None
    assert debug_pause_button is not None
    assert debug_restart_button is not None
    assert debug_stop_button is not None
    assert toggle_breakpoint_button is not None
    assert clear_breakpoints_button is not None
    assert preview_play_button is not None
    assert play_button is not None
    assert record_button is not None
    assert stop_button is not None
    assert inspector_button is not None
    assert preferences_button is not None
    assert documentation_button is not None
    assert _layout_widget_at(window.settings_toolbar_group.layout(), 0) is inspector_button
    assert _layout_widget_at(window.settings_toolbar_group.layout(), 1) is preferences_button
    assert _layout_widget_at(window.settings_toolbar_group.layout(), 2) is documentation_button
    assert window.documentation_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText) != ""
    assert window.debug_continue_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_over_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_step_out_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_restart_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_stop_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.debug_continue_button.objectName() == "debugContinueButton"
    assert window.debug_step_over_button.objectName() == "debugStepOverButton"
    assert window.debug_step_button.objectName() == "debugStepIntoButton"
    assert window.debug_step_out_button.objectName() == "debugStepOutButton"
    assert window.debug_restart_button.objectName() == "debugRestartButton"
    assert window.debug_stop_button.objectName() == "debugStopButton"
    assert window.debug_continue_button.toolTip().startswith("Continue")
    assert window.debug_step_over_button.toolTip().startswith("Step Over")
    assert window.debug_step_button.toolTip().startswith("Step Into")
    assert window.debug_step_out_button.toolTip().startswith("Step Out")
    assert window.debug_restart_button.toolTip().startswith("Restart")
    assert window.debug_stop_button.toolTip().startswith("Stop")
    assert "padding: 0px 3px" in inspector_button.styleSheet()
    assert "padding: 0px 3px" in preferences_button.styleSheet()
    assert "padding: 0px 3px" in documentation_button.styleSheet()
    assert "rgba(90, 100, 112, 0.15)" in inspector_button.styleSheet()
    assert "rgba(90, 100, 112, 0.15)" in preferences_button.styleSheet()
    assert "rgba(90, 100, 112, 0.15)" in documentation_button.styleSheet()
    assert _layout_widget_at(window.file_toolbar_group.layout(), 0) is new_button
    assert _layout_widget_at(window.file_toolbar_group.layout(), 1) is open_button
    assert _layout_widget_at(window.file_toolbar_group.layout(), 2) is save_button
    assert _layout_widget_at(window.file_toolbar_group.layout(), 3) is save_as_button
    assert _layout_widget_at(window.file_toolbar_group.layout(), 4) is search_button
    assert _layout_widget_at(window.analysis_toolbar_group.layout(), 0) is analyze_button
    assert _layout_widget_at(window.analysis_toolbar_group.layout(), 1) is preview_button
    assert _layout_widget_at(window.playback_toolbar_group.layout(), 0) is preview_play_button
    assert _layout_widget_at(window.playback_toolbar_group.layout(), 1) is play_button
    assert _layout_widget_at(window.playback_toolbar_group.layout(), 2) is record_button
    assert _layout_widget_at(window.playback_toolbar_group.layout(), 3) is stop_button
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 0) is debug_primary_group
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 1) is window.debug_primary_toolbar_separator
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 2) is breakpoint_controls_group
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 3) is debug_step_into_button
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 4) is debug_step_over_button
    assert _layout_widget_at(window.debug_toolbar_group.layout(), 5) is debug_step_out_button
    assert _layout_widget_at(debug_primary_group.layout(), 0) is view_debugger_tab_button
    assert _layout_widget_at(debug_primary_group.layout(), 1) is debug_button
    assert _layout_widget_at(debug_primary_group.layout(), 2) is debug_continue_button
    assert _layout_widget_at(debug_primary_group.layout(), 3) is debug_pause_button
    assert _layout_widget_at(debug_primary_group.layout(), 4) is debug_restart_button
    assert _layout_widget_at(debug_primary_group.layout(), 5) is debug_stop_button
    assert new_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert open_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert save_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert save_as_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert search_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert analyze_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert preview_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly


def test_desktop_window_opens_help_browser_singleton(monkeypatch) -> None:
    _app()

    created_browsers: list[object] = []

    class FakeHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            self.calls: list[str] = []
            self.on_close = on_close
            created_browsers.append(self)
            self.minimized = False

        def show(self) -> None:
            self.calls.append("show")

        def showNormal(self) -> None:
            self.calls.append("showNormal")

        def raise_(self) -> None:
            self.calls.append("raise")

        def activateWindow(self) -> None:
            self.calls.append("activate")

        def isMinimized(self) -> bool:
            return self.minimized

        def close(self) -> None:
            self.calls.append("close")
            if self.on_close is not None:
                self.on_close()

    monkeypatch.setattr(desktop_window_module, "ActionShellScriptHelpBrowser", FakeHelpBrowser)

    window = _new_window()
    window.open_documentation()
    window.open_documentation()

    assert len(created_browsers) == 1
    browser = created_browsers[0]
    assert isinstance(browser, FakeHelpBrowser)
    assert browser.calls == ["show", "raise", "activate", "show", "raise", "activate"]
    assert window._help_browser_window is browser
    window.close()
    assert window._help_browser_window is browser
    assert "close" not in browser.calls


def test_desktop_window_documentation_launches_ass_help_when_help_browser_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    log_calls: list[dict[str, object]] = []
    start_calls: list[tuple[str, list[str]]] = []
    bundle_root = tmp_path / "bundle"
    ass_gui_dir = bundle_root / "ass-gui"
    ass_help_dir = bundle_root / "ass-help"
    docs_path = tmp_path / "shared-docs.md"
    ass_gui_dir.mkdir(parents=True)
    ass_help_dir.mkdir(parents=True)
    launcher_path = ass_help_dir / "ass-help.exe"
    launcher_path.write_text("", encoding="utf-8")

    class BrokenHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            raise RuntimeError("web engine unavailable")

    def fake_start_detached(program: str, arguments: list[str]) -> bool:
        start_calls.append((program, list(arguments)))
        return True

    def fake_info(message: str, *args, **kwargs) -> None:
        log_calls.append({"message": message, "kwargs": kwargs})

    monkeypatch.setattr(desktop_window_module, "ActionShellScriptHelpBrowser", BrokenHelpBrowser)
    monkeypatch.setattr(desktop_window_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(desktop_window_module.sys, "executable", str(ass_gui_dir / "ass-gui.exe"))
    monkeypatch.setattr(desktop_window_module.QProcess, "startDetached", fake_start_detached)
    monkeypatch.setattr(desktop_window_module.window_log, "info", fake_info)
    monkeypatch.setattr(desktop_window_module, "docs_index_path", lambda: docs_path)

    window = _new_window()
    window.open_documentation()

    assert len(start_calls) == 1
    assert start_calls[0][0] == str(launcher_path)
    assert start_calls[0][1][0].endswith(r"shared-docs.md")
    assert ass_help_fallback_status() in window.statusBar().currentMessage()
    matching_logs = [
        call for call in log_calls if call["kwargs"].get("event_id") == "desktop.window.documentation_ass_help_launched"
    ]
    assert matching_logs
    assert window._help_browser_window is None


def test_desktop_window_documentation_shows_warning_if_all_fallbacks_fail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    warnings: list[tuple[str, str]] = []
    opened_urls: list[str] = []
    bundle_root = tmp_path / "bundle"
    ass_gui_dir = bundle_root / "ass-gui"
    ass_help_dir = bundle_root / "ass-help"
    docs_path = tmp_path / "shared-docs.md"
    ass_gui_dir.mkdir(parents=True)
    ass_help_dir.mkdir(parents=True)
    (ass_help_dir / "ass-help.exe").write_text("", encoding="utf-8")

    class BrokenHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            raise RuntimeError("web engine unavailable")

    monkeypatch.setattr(desktop_window_module, "ActionShellScriptHelpBrowser", BrokenHelpBrowser)
    monkeypatch.setattr(desktop_window_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(desktop_window_module.sys, "executable", str(ass_gui_dir / "ass-gui.exe"))
    monkeypatch.setattr(desktop_window_module.QProcess, "startDetached", lambda program, arguments: False)
    monkeypatch.setattr(desktop_window_module, "docs_index_path", lambda: docs_path)
    monkeypatch.setattr(
        desktop_window_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url.toString()) or False,
    )
    monkeypatch.setattr(
        desktop_window_module.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    window = _new_window()
    window.open_documentation()

    assert warnings
    assert warnings[0][0] == "Documentation Unavailable"
    assert "web engine unavailable" in warnings[0][1]
    assert str(docs_path) in warnings[0][1]
    assert len(opened_urls) == 1
    assert opened_urls[0].endswith("/shared-docs.md")
    assert window._help_browser_window is None


def test_desktop_window_search_actions_enable_only_when_search_state_is_available() -> None:
    app = _app()

    window = _new_window()

    assert window.find_action.isEnabled() is True
    assert window.replace_action.isEnabled() is True
    assert window.find_next_action.isEnabled() is False
    assert window.find_previous_action.isEnabled() is False
    assert window.select_and_find_next_action.isEnabled() is False
    assert window.select_and_find_previous_action.isEnabled() is False
    assert window.replace_current_action.isEnabled() is False
    assert window.replace_all_action.isEnabled() is False

    window.find_action.trigger()
    widgets = window._find_sidebar_widgets
    assert widgets is not None
    find_page = widgets.pages["find"]
    _combo_line_edit(find_page.find_combo).setText("alpha")
    app.processEvents()

    assert window.find_next_action.isEnabled() is True
    assert window.find_previous_action.isEnabled() is True
    assert window.select_and_find_next_action.isEnabled() is False
    assert window.select_and_find_previous_action.isEnabled() is False
    assert window.replace_current_action.isEnabled() is True
    assert window.replace_all_action.isEnabled() is True

    window.editor.setPlainText("alpha beta alpha")
    window.editor.selectAll()
    app.processEvents()

    assert window.select_and_find_next_action.isEnabled() is True
    assert window.select_and_find_previous_action.isEnabled() is True


def test_desktop_window_places_breakpoint_actions_in_view_menu() -> None:
    _app()

    window = _new_window()
    assert window.document_status_action.icon().isNull() is False
    assert [action.text() for action in window.view_menu.actions()] == [
        "Analyze",
        "Refresh Preview",
        "Document Status...",
        "Left Sidebar",
        "Show Hidden Tab Selections",
    ]


def test_desktop_window_hidden_tab_selections_view_menu_action_tracks_visibility() -> None:
    _app()

    window = _new_window()
    preview_index = window.workspace_tabs.indexOf(window.preview_view)
    assert preview_index >= 0

    assert window.hidden_workspace_tabs_action.text() == "Show Hidden Tab Selections"
    assert window.hidden_workspace_tabs_action.isEnabled() is True
    assert window.hidden_workspace_tabs_action.icon().isNull() is False

    window.workspace_tabs.tabCloseRequested.emit(preview_index)

    assert window.hidden_workspace_tabs_action.isEnabled() is True
    assert window.hidden_workspace_tabs_action.text() == "Show Hidden Tab Selections"
    assert window.hidden_workspace_tabs_action.icon().isNull() is False
    assert window.hidden_workspace_tabs_action.toolTip() == "Show the hidden tab selections"
    assert window.hidden_workspace_tabs_collapse_button.isHidden() is True
    assert window.hidden_workspace_tabs_expand_button.isHidden() is False

    window.hidden_workspace_tabs_action.trigger()

    assert window.hidden_workspace_tabs_action.text() == "Hide Hidden Tab Selections"
    assert window.hidden_workspace_tabs_action.icon().isNull() is False
    assert window.hidden_workspace_tabs_action.toolTip() == "Hide the hidden tab selections"
    assert window.hidden_workspace_tabs_collapse_button.isHidden() is False
    assert window.hidden_workspace_tabs_expand_button.isHidden() is True

    window.hidden_workspace_tabs_action.trigger()

    assert window.hidden_workspace_tabs_action.text() == "Show Hidden Tab Selections"
    assert window.hidden_workspace_tabs_collapse_button.isHidden() is True
    assert window.hidden_workspace_tabs_expand_button.isHidden() is False


def test_desktop_window_restores_hidden_tab_strip_collapsed_state_after_restart(
    tmp_path,
) -> None:
    _app()

    first_window = _new_window(config_dir=tmp_path)
    preview_index = first_window.workspace_tabs.indexOf(first_window.preview_view)
    assert preview_index >= 0

    first_window.workspace_tabs.tabCloseRequested.emit(preview_index)
    first_window.hidden_workspace_tabs_action.trigger()

    assert first_window.hidden_workspace_tabs_strip_collapsed is False
    assert first_window.hidden_workspace_tabs_action.text() == "Hide Hidden Tab Selections"
    assert (tmp_path / "desktop_settings.json").exists()

    second_window = _new_window(config_dir=tmp_path)
    second_preview_index = second_window.workspace_tabs.indexOf(second_window.preview_view)
    assert second_preview_index >= 0

    second_window.workspace_tabs.tabCloseRequested.emit(second_preview_index)

    assert second_window.hidden_workspace_tabs_strip_collapsed is False
    assert second_window.hidden_workspace_tabs_action.text() == "Hide Hidden Tab Selections"
    assert second_window.hidden_workspace_tabs_collapse_button.isHidden() is False
    assert second_window.hidden_workspace_tabs_expand_button.isHidden() is True
    assert second_window.hidden_workspace_tabs_label.isHidden() is False


def test_desktop_window_shows_document_status_dialog(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.current_document = ScriptDocument(
        document_id="0ea94c50-65d0-4868-9cd7-301d1614d452",
        text="",
        is_dirty=False,
        last_saved_version=None,
        source_session_id=None,
        source_action_count=None,
        generated_from_recording=False,
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=False,
    )
    window.current_path = None
    window._analysis_stale = True
    window._editor_dirty = False

    captured: dict[str, str] = {}

    def fake_exec(self) -> int:
        captured["text"] = self.status_view.toPlainText()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DocumentStatusDialog, "exec", fake_exec)

    window.document_status_action.trigger()

    assert window.document_status_action.icon().isNull() is False

    assert captured["text"] == (
        "Document ID: 0ea94c50-65d0-4868-9cd7-301d1614d452\n"
        "Path: <unsaved>\n"
        "Version: 1\n"
        "Line count: 0\n"
        "Document dirty: False\n"
        "Editor dirty: False\n"
        "Analysis stale after edits: True\n"
        "Last saved version: None\n"
        "Source session ID: None\n"
        "Source action count: None\n"
        "Recording conversion route: Promote generated script\n"
        "Recording exclusion: disabled (main window included during recording)\n"
        "Generated from recording: False"
    )


def test_document_status_dialog_copy_button_copies_rendered_text_to_clipboard() -> None:
    app = _app()

    from apps.desktop.document_status_dialog import DocumentStatusDialog

    dialog = DocumentStatusDialog(
        None,
        lines=[
            "Document ID: doc-1",
            "Path: <unsaved>",
            "Version: 1",
        ],
    )

    assert dialog.windowIcon().isNull() is False
    dialog_layout = dialog.layout()
    assert dialog_layout is not None
    footer_item = dialog_layout.itemAt(1)
    assert footer_item is not None
    footer_layout = footer_item.layout()
    assert footer_layout is not None
    copy_button = _required_child(dialog, QToolButton, "documentStatusCopyButton")
    assert _layout_widget_at(footer_layout, 0) is copy_button

    clipboard = app.clipboard()
    previous_text = clipboard.text()
    try:
        assert copy_button.toolTip() == "Copy text to clipboard"
        original_icon_key = copy_button.icon().cacheKey()
        timeout_spy = QSignalSpy(dialog._copy_feedback_timer.timeout)
        copy_button.click()
        app.processEvents()
        assert clipboard.text() == "Document ID: doc-1\nPath: <unsaved>\nVersion: 1"
        assert copy_button.toolTip() == "Copied to clipboard"
        assert copy_button.icon().cacheKey() != original_icon_key
        assert dialog._copy_feedback_timer.isActive() is True
        assert timeout_spy.wait(2000) is True
        app.processEvents()
        assert copy_button.toolTip() == "Copy text to clipboard"
        assert copy_button.icon().cacheKey() == original_icon_key
    finally:
        clipboard.setText(previous_text)


def test_desktop_window_analyze_action_refreshes_semantic_diagnostics() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("Func CallThing()\nEndFunc\nCallThng()\n")
    app.processEvents()
    sidebar = window._analysis_sidebar_widgets
    assert sidebar is not None

    window.analyze_action.trigger()
    app.processEvents()
    assert window._current_sidebar_mode == "analysis"
    analysis_widgets = window._analysis_sidebar_widgets
    assert analysis_widgets is not None
    assert window.sidebar_mode_stack.currentWidget() is analysis_widgets.page
    assert window.workspace_tabs.isTabVisible(window.workspace_tabs.indexOf(window.analysis_tab)) is False
    assert window.workspace_tabs.currentWidget() is window.editor
    window.analysis_diagnostics_view.anchorClicked.emit(QUrl("analysis-diagnostic-0"))
    app.processEvents()

    assert window.current_analysis is not None
    assert len(window.current_analysis.diagnostics.items) == 1
    diagnostic = window.current_analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM008"
    assert diagnostic.message == "Unsupported function: CallThng. Did you mean CallThing?"
    assert diagnostic.span == TextSpan(25, 33)
    assert "Unsupported function: CallThng. Did you mean CallThing?" in window.analysis_diagnostics_view.toPlainText()
    assert "ERROR" in window.analysis_diagnostics_view.toPlainText()
    assert "SEM008" in window.analysis_diagnostics_view.toPlainText()
    assert "line 3, column 1" in window.analysis_diagnostics_view.toPlainText()
    assert window.diagnostics_view.toPlainText() == "<none>"
    assert "First diagnostic: ERROR SEM008 at line 3, column 1" in window.analysis_summary_view.toPlainText()
    assert "Preview: Unsupported function: CallThng. Did you mean CallThing?" in window.analysis_summary_view.toPlainText()
    assert "Analysis status: current" in window.analysis_summary_view.toPlainText()
    assert "Analysis phase: semantic failed" in window.analysis_summary_view.toPlainText()
    assert "Analysis reflects the current editor text." in window.analysis_summary_view.toPlainText()
    assert "Refresh scope: current editor text only" in window.analysis_summary_view.toPlainText()
    assert "Not refreshed: saved file state or preview output" in window.analysis_summary_view.toPlainText()
    assert window.summary_view.toPlainText() == ""
    assert "Analysis status: current" in sidebar.summary_view.toPlainText()
    assert "Preview: Unsupported function: CallThng. Did you mean CallThing?" in sidebar.summary_view.toPlainText()
    assert "Unsupported function: CallThng. Did you mean CallThing?" in sidebar.diagnostics_view.toPlainText()
    assert "line 3, column 1" in sidebar.diagnostics_view.toPlainText()
    assert sidebar.header_state_label.text() == "semantic failed"
    assert sidebar.header_count_label.text() == "1 semantic error"
    assert sidebar.status_label.text() == "Current. 1 diagnostic."
    assert "Analysis refreshed from current editor text with 1 error(s)" in window.statusBar().currentMessage()
    assert window.workspace_tabs.currentWidget() is window.editor
    assert window.editor.textCursor().selectionStart() == 25
    assert window.editor.textCursor().selectionEnd() == 33


def test_desktop_window_analyze_action_marks_syntax_failures_in_the_sidebar_header() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("Dim = 1\n")
    app.processEvents()
    sidebar = window._analysis_sidebar_widgets
    assert sidebar is not None

    window.analyze_action.trigger()
    app.processEvents()

    assert window.current_analysis is not None
    assert len(window.current_analysis.syntax_diagnostics.items) == 1
    assert len(window.current_analysis.semantic_diagnostics.items) == 0
    assert sidebar.header_state_label.text() == "syntax failed"
    assert sidebar.header_count_label.text() == "1 syntax error"
    assert "Syntax phase: failed" in sidebar.summary_view.toPlainText()
    assert "Semantic phase: passed" in sidebar.summary_view.toPlainText()


def test_desktop_window_marks_analysis_stale_after_editor_edits() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("Goto Inner\nIf x Then\nInner:\nEndIf\n")
    app.processEvents()
    sidebar = window._analysis_sidebar_widgets
    assert sidebar is not None

    window.analyze_action.trigger()
    app.processEvents()

    window.editor.appendPlainText("Else\n")
    app.processEvents()

    assert "Analysis status: stale after edits" in window.analysis_summary_view.toPlainText()
    assert "Analysis phase: stale" in window.analysis_summary_view.toPlainText()
    assert window.summary_view.toPlainText() == ""
    assert "Analysis status: stale after edits" in sidebar.summary_view.toPlainText()
    assert sidebar.header_state_label.text() == "stale"
    assert sidebar.header_count_label.text() == "1 semantic error"
    assert sidebar.status_label.text() == "Stale. Run Analyze."
    assert window.statusBar().currentMessage().startswith(
        "* Unsaved editor changes; analysis is stale until you click Analyze |"
    )


def test_desktop_window_view_debugger_action_focuses_debugger_tab_without_starting_debugger(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    window.committed_settings_bundle.application.show_debug_tab = False
    window._update_workspace_tab_visibility()
    window.workspace_tabs.setCurrentWidget(window.preview_view)

    assert window.view_debugger_tab_action.text() == "Debugger"
    assert window.view_debugger_tab_action.icon().isNull() is False

    window.view_debugger_tab_action.trigger()

    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window._current_sidebar_mode == "debug"
    assert window.debugger_controls_dialog.isVisible() is False

    window.view_debugger_tab_action.trigger()

    assert window.committed_settings_bundle.application.show_debug_tab is False
    app.processEvents()
    assert window.summary_dock.isVisible() is False
    assert window.debugger_controls_dialog.isVisible() is False


def test_desktop_window_toggles_analysis_tab_visibility_from_preferences() -> None:
    _app()

    window = _new_window()
    analysis_index = window.workspace_tabs.indexOf(window.analysis_tab)
    assert analysis_index >= 0
    assert window.workspace_tabs.isTabVisible(analysis_index) is False

    window.committed_settings_bundle.application.show_analysis_tab = False
    window._update_workspace_tab_visibility()

    assert window.workspace_tabs.isTabVisible(analysis_index) is False

    window.committed_settings_bundle.application.show_analysis_tab = True
    window._update_workspace_tab_visibility()

    assert window.workspace_tabs.isTabVisible(analysis_index) is True


def test_desktop_window_view_debugger_toolbar_button_focuses_debugger_tab_without_starting_debugger(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    view_debugger_tab_button = _required_child(window.debug_toolbar_group, QToolButton, "viewDebugTabToolbarButton")
    assert view_debugger_tab_button is not None
    assert view_debugger_tab_button.toolTip() == "Debugger"

    window.committed_settings_bundle.application.show_debug_tab = False
    window._update_workspace_tab_visibility()
    window.workspace_tabs.setCurrentWidget(window.preview_view)

    view_debugger_tab_button.click()

    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window._current_sidebar_mode == "debug"
    assert window.debugger_controls_dialog.isVisible() is False

    view_debugger_tab_button.click()

    assert window.committed_settings_bundle.application.show_debug_tab is False
    app.processEvents()
    assert window.summary_dock.isVisible() is False
    assert window.debugger_controls_dialog.isVisible() is False


def test_desktop_window_applies_pixel_inspector_hotkey_binding() -> None:
    _app()

    window = _new_window()
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={"pixel_inspector": "Ctrl+Alt+I"},
            )
        )
    )

    window._on_preferences_changed(bundle)

    assert window.pixel_inspector_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Alt+I"
    ).toString(QKeySequence.SequenceFormat.PortableText)


def test_desktop_window_applies_debugger_hotkey_binding() -> None:
    _app()

    window = _new_window()
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={"debugger": "Ctrl+Alt+D"},
            )
        )
    )

    window._on_preferences_changed(bundle)

    assert window.debugger_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Alt+D"
    ).toString(QKeySequence.SequenceFormat.PortableText)


def test_desktop_window_applies_search_hotkey_bindings() -> None:
    _app()

    window = _new_window()
    assert window._hotkey_actions["find"] is window.find_action
    assert window._hotkey_actions["find_next"] is window.find_next_action
    assert window._hotkey_actions["find_previous"] is window.find_previous_action
    assert window._hotkey_actions["replace"] is window.replace_action
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={
                    "find": "Ctrl+Alt+F",
                    "find_next": "Ctrl+Alt+N",
                    "find_previous": "Ctrl+Alt+P",
                    "replace": "Ctrl+Alt+R",
                },
            )
        )
    )

    window._on_preferences_changed(bundle)

    expected_bindings = {
        "find_action": ("Find...", "Ctrl+Alt+F"),
        "find_next_action": ("Next", "Ctrl+Alt+N"),
        "find_previous_action": ("Previous", "Ctrl+Alt+P"),
        "replace_action": ("Replace...", "Ctrl+Alt+R"),
    }
    for attribute_name, (label, shortcut) in expected_bindings.items():
        action = getattr(window, attribute_name)
        expected_shortcut = QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText).strip()
        assert action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(shortcut).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        assert action.toolTip() == f"{label} ({expected_shortcut})"
        assert action.statusTip() == f"{label} ({expected_shortcut})"


def test_desktop_window_applies_view_debugger_tab_hotkey_binding_and_triggers_action() -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()
    assert window._hotkey_actions["view_debugger_tab"] is window.view_debugger_tab_action
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={"view_debugger_tab": "Ctrl+Alt+T"},
            )
        )
    )
    bundle.application.show_debug_tab = False

    window.committed_settings_bundle.application.show_debug_tab = False
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    window._on_preferences_changed(bundle)

    assert window.view_debugger_tab_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Alt+T"
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert window.view_debugger_tab_action.text() == "Debugger"

    window.view_debugger_tab_action.trigger()

    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window._current_sidebar_mode == "debug"
    assert window.debugger_controls_dialog.isVisible() is False

    window.view_debugger_tab_action.trigger()

    assert window.summary_dock.isVisible() is False
    app.processEvents()
    assert window.debugger_controls_dialog.isVisible() is False


def test_desktop_window_applies_clear_breakpoints_hotkey_binding() -> None:
    _app()

    window = _new_window()
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={"clear_breakpoints": "Ctrl+Alt+Shift+F9"},
            )
        )
    )

    window._on_preferences_changed(bundle)

    assert window.clear_breakpoints_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Ctrl+Alt+Shift+F9"
    ).toString(QKeySequence.SequenceFormat.PortableText)


def test_desktop_window_applies_debugger_step_hotkey_bindings() -> None:
    _app()

    window = _new_window()
    bundle = DesktopSettingsBundle(
        application=DesktopApplicationSettings(
            hotkeys=DesktopHotkeySettings(
                bindings={
                    "debug_step_into": "Ctrl+Alt+I",
                    "debug_step_over": "Ctrl+Alt+O",
                    "debug_step_out": "Ctrl+Alt+U",
                    "debug_continue": "Ctrl+Alt+C",
                    "debug_pause": "Ctrl+Alt+P",
                    "debug_restart": "Ctrl+Alt+R",
                    "debug_stop": "Ctrl+Alt+X",
                },
            )
        )
    )

    window._on_preferences_changed(bundle)

    expected_bindings = {
        "debug_step_into_action": ("Step Into", "Ctrl+Alt+I"),
        "debug_step_over_action": ("Step Over", "Ctrl+Alt+O"),
        "debug_step_out_action": ("Step Out", "Ctrl+Alt+U"),
        "debug_continue_action": ("Continue", "Ctrl+Alt+C"),
        "debug_pause_action": ("Pause", "Ctrl+Alt+P"),
        "debug_restart_action": ("Restart Debug", "Ctrl+Alt+R"),
        "debug_stop_action": ("Stop", "Ctrl+Alt+X"),
    }
    for attribute_name, (label, shortcut) in expected_bindings.items():
        action = getattr(window, attribute_name)
        expected_shortcut = QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText).strip()
        assert action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(shortcut).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        assert action.toolTip() == f"{label} ({expected_shortcut})"
        assert action.statusTip() == f"{label} ({expected_shortcut})"


def test_desktop_window_debugger_selection_does_not_open_controls(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        window,
        "_show_debugger_controls_dialog",
        lambda: calls.append(("controls", True)),
    )
    monkeypatch.setattr(
        window,
        "_set_sidebar_visible",
        lambda visible, *, user_initiated=False, auto_hidden=False: calls.append(
            ("visible", visible)
        ),
    )
    monkeypatch.setattr(window.summary_dock, "isVisible", lambda: True)

    window._current_sidebar_mode = "debug"
    window._sidebar_user_hidden = False
    window.show_debugger_tab()

    assert calls == [("visible", False)]
    assert window.debugger_controls_dialog.isVisible() is False

    calls.clear()
    monkeypatch.setattr(window.summary_dock, "isVisible", lambda: False)
    window._sidebar_user_hidden = True
    window.show_debugger_tab()

    assert calls == [("visible", True)]


def test_desktop_window_debug_run_actions_start_debug_session(monkeypatch) -> None:
    _app()

    window = _new_window()
    called: list[str] = []

    monkeypatch.setattr(
        window,
        "open_debugger_dialog",
        lambda: called.append("open_debugger_dialog"),
    )

    window.run_debug_menu_action.trigger()
    window.debugger_action.trigger()

    assert called == ["open_debugger_dialog", "open_debugger_dialog"]


def test_desktop_window_run_starts_debug_session_and_enables_controls(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    started = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        _ = handle
        assert document.source_path == str(window.current_path)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id="session-1",
                document_id=window.current_document.document_id,
            )
        )
        started.set()
        release.wait(timeout=2.0)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_completed",
                session_id="session-1",
                document_id=window.current_document.document_id,
            )
        )
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    window.show()
    app.processEvents()
    window.current_path = Path("/tmp/source/debug.ass")
    window.current_document = ScriptDocument(
        document_id="doc-debug",
        text="Dim x = 1\nWriteLn(x)\n",
        source_path=str(window.current_path),
    )
    window.editor.setPlainText("Dim x = 1\nWriteLn(x)\n")
    window._set_sidebar_visible(False, user_initiated=True)
    window._set_sidebar_mode("analysis")
    assert window.summary_dock.isVisible() is False
    window.run_debug_menu_action.trigger()

    assert started.wait(timeout=2.0) is True

    deadline = time.monotonic() + 2.0
    while not window.summary_dock.isVisible() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert window.summary_dock.isVisible() is True

    deadline = time.monotonic() + 2.0
    while window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window._debug_session_handle is not None
    assert window._debug_session_thread is not None
    assert window._debug_session_thread.is_alive() is True
    assert window.summary_dock.isVisible() is True
    assert window._current_sidebar_mode == "debug"
    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window.debugger_action.isEnabled() is False
    assert window.run_debug_menu_action.isEnabled() is False
    assert window.debug_continue_action.isEnabled() is True
    assert window.debug_step_button.isEnabled() is True
    assert window.debug_step_over_button.isEnabled() is True
    assert window.debug_step_out_button.isEnabled() is True
    assert window.debug_stop_button.isEnabled() is True
    assert window.debug_status_indicator.toolTip().startswith("Running")
    assert "[session_started]" in window.debug_event_log_view.toPlainText()

    release.set()
    deadline = time.monotonic() + 2.0
    while not window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.debugger_action.isEnabled() is True
    assert window.debug_continue_action.isEnabled() is False
    assert window._debug_session_handle is None
    assert window._last_debug_session_outcome == "completed"


def test_desktop_window_debugger_pause_reopens_hidden_sidebar_when_auto_open_is_enabled(
    monkeypatch,
) -> None:
    app = _app()

    window = _new_window()
    started = threading.Event()
    allow_pause = threading.Event()
    release = threading.Event()

    def fake_run_debug_session(handle, document) -> None:
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_started",
                session_id="session-1",
                document_id=window.current_document.document_id,
            )
        )
        started.set()
        allow_pause.wait(timeout=2.0)
        paused_snapshot = type(
            "PausedSnapshot",
            (),
            {
                "session_id": "session-1",
                "state": "paused",
                "pause_reason": "step",
                "current_line": 3,
                "breakpoints": [2],
                "call_stack": [],
                "variables": [],
            },
        )()
        handle.controller.snapshot = lambda: paused_snapshot
        window.debugEventReceived.emit(
            DebugEvent(
                kind="stopped",
                session_id="session-1",
                document_id=window.current_document.document_id,
                line=3,
                pause_reason="step",
            )
        )
        release.wait(timeout=2.0)
        window.debugEventReceived.emit(
            DebugEvent(
                kind="session_completed",
                session_id="session-1",
                document_id=window.current_document.document_id,
                line=3,
            )
        )
        window.debugSessionFinished.emit("completed")

    monkeypatch.setattr(window, "_run_debug_session", fake_run_debug_session)

    window.show()
    app.processEvents()
    window.editor.setPlainText('Dim x = 1\nx = x + 1\nSendText("x")\n')
    window.editor.setDebugBreakpoints({2})
    window.workspace_tabs.setCurrentWidget(window.preview_view)
    window.open_debugger_dialog()

    assert started.wait(timeout=2.0) is True
    deadline = time.monotonic() + 2.0
    while not window.summary_dock.isVisible() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert window.summary_dock.isVisible() is True

    window._set_sidebar_visible(False, user_initiated=True)
    window._set_sidebar_mode("find")
    assert window.summary_dock.isVisible() is False
    assert window._current_sidebar_mode == "find"

    allow_pause.set()
    deadline = time.monotonic() + 2.0
    while not window.summary_dock.isVisible() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window._current_sidebar_mode == "debug"
    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window.debug_status_indicator.toolTip().startswith("Paused on step at line 3")

    release.set()
    deadline = time.monotonic() + 2.0
    while not window.debugger_action.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    app.processEvents()

    assert window.debugger_action.isEnabled() is True


def test_desktop_window_clear_breakpoints_action_clears_editor_breakpoints() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("one\ntwo\nthree\n")
    window.editor.setDebugBreakpoints({1, 3})

    clear_breakpoints_button = _required_child(window.debug_toolbar_group, QToolButton, "clearBreakpointsScriptToolbarButton")
    assert clear_breakpoints_button is not None
    assert window.clear_breakpoints_action.isEnabled() is True
    assert clear_breakpoints_button.isEnabled() is True

    window.clear_breakpoints_action.trigger()

    assert window.editor.debugBreakpointLines() == set()
    assert window.clear_breakpoints_action.isEnabled() is False
    assert clear_breakpoints_button.isEnabled() is False


def test_desktop_window_toggle_breakpoint_action_switches_icons_with_breakpoint_state() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("one\ntwo\nthree\n")
    window.editor.moveCursor(QTextCursor.MoveOperation.Down)
    breakpoint_icon = window._file_action_icon("msc.debug-breakpoint")
    breakpoint_present_icon = window._file_action_icon("msc.debug-breakpoint-unverified")
    toggle_breakpoint_button = _required_child(window.debug_toolbar_group, QToolButton, "toggleBreakpointToolbarButton")
    assert toggle_breakpoint_button is not None

    assert window.toggle_breakpoint_action.icon().cacheKey() == breakpoint_icon.cacheKey()
    assert toggle_breakpoint_button.icon().cacheKey() == breakpoint_icon.cacheKey()

    window.editor.toggleDebugBreakpoint(window.editor.currentLineNumber())

    assert window.editor.debugBreakpointLines() == {2}
    assert window.toggle_breakpoint_action.icon().cacheKey() == breakpoint_present_icon.cacheKey()
    assert toggle_breakpoint_button.icon().cacheKey() == breakpoint_present_icon.cacheKey()


def test_desktop_window_continue_button_routes_continue_action(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    monkeypatch.setattr(window, "continue_debug_session", lambda: calls.append("continue"))
    window._update_debugger_controls_state(active=True)

    continue_button = window.debug_continue_button
    assert continue_button is not None

    window.debug_continue_action.trigger()
    continue_button.click()

    assert calls == ["continue", "continue"]


def test_desktop_window_restart_button_routes_restart_action(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    monkeypatch.setattr(window, "restart_debug_session", lambda: calls.append("restart"))
    window._update_debugger_controls_state(active=True)

    restart_button = window.debug_restart_button
    assert restart_button is not None

    window.debug_restart_action.trigger()
    restart_button.click()

    assert calls == ["restart", "restart"]


def test_desktop_window_debugger_controls_buttons_route_actions(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    monkeypatch.setattr(window, "stop_debug_session", lambda: calls.append("stop"))
    monkeypatch.setattr(window, "step_debug_session", lambda: calls.append("step_into"))
    monkeypatch.setattr(window, "step_over_debug_session", lambda: calls.append("step_over"))
    monkeypatch.setattr(window, "step_out_debug_session", lambda: calls.append("step_out"))
    monkeypatch.setattr(window, "continue_debug_session", lambda: calls.append("continue"))
    monkeypatch.setattr(window, "pause_debug_session", lambda: calls.append("pause"))
    monkeypatch.setattr(window, "restart_debug_session", lambda: calls.append("restart"))

    window._update_debugger_controls_state(active=True)
    window.debug_continue_button.click()
    window.debug_pause_button.click()
    window.debug_step_button.click()
    window.debug_step_over_button.click()
    window.debug_step_out_button.click()
    window.debug_stop_button.click()
    window.debug_restart_button.click()
    window.debug_pause_action.trigger()
    window.restart_debug_menu_action.trigger()

    assert calls == [
        "continue",
        "pause",
        "step_into",
        "step_over",
        "step_out",
        "stop",
        "restart",
        "pause",
        "restart",
    ]


def test_desktop_window_pixel_inspector_action_reuses_inspector_window(monkeypatch) -> None:
    _app()

    window = _new_window()
    created_windows: list[object] = []

    class FakePixelInspectorWindow:
        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.calls: list[str] = []
            created_windows.append(self)

        def show(self) -> None:
            self.calls.append("show")

        def raise_(self) -> None:
            self.calls.append("raise")

        def activateWindow(self) -> None:
            self.calls.append("activate")

    monkeypatch.setattr("apps.desktop.window.PixelInspectorWindow", FakePixelInspectorWindow)

    window.pixel_inspector_action.trigger()
    first_window = cast(_PixelInspectorWindowLike, window._pixel_inspector_window)

    assert first_window is not None
    assert created_windows == [first_window]
    assert first_window.parent is None
    assert first_window.calls == ["show", "raise", "activate"]

    window.pixel_inspector_action.trigger()

    assert window._pixel_inspector_window is first_window
    assert created_windows == [first_window]
    assert first_window.calls == ["show", "raise", "activate", "show", "raise", "activate"]


def test_desktop_window_open_pixel_inspector_window_reuses_inspector_window(monkeypatch) -> None:
    _app()

    window = _new_window()
    created_windows: list[object] = []

    class FakePixelInspectorWindow:
        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.calls: list[str] = []
            created_windows.append(self)

        def show(self) -> None:
            self.calls.append("show")

        def raise_(self) -> None:
            self.calls.append("raise")

        def activateWindow(self) -> None:
            self.calls.append("activate")

    monkeypatch.setattr("apps.desktop.window.PixelInspectorWindow", FakePixelInspectorWindow)

    window.open_pixel_inspector_window()
    first_window = cast(_PixelInspectorWindowLike, window._pixel_inspector_window)
    window.open_pixel_inspector_window()

    assert first_window is not None
    assert window._pixel_inspector_window is first_window
    assert created_windows == [first_window]
    assert first_window.calls == ["show", "raise", "activate", "show", "raise", "activate"]


def test_desktop_window_closes_pixel_inspector_window_on_exit(monkeypatch) -> None:
    _app()

    window = _new_window()
    closed_windows: list[object] = []

    class FakePixelInspectorWindow:
        def __init__(self, parent=None) -> None:
            self.parent = parent

        def show(self) -> None:
            pass

        def raise_(self) -> None:
            pass

        def activateWindow(self) -> None:
            pass

        def close(self) -> None:
            closed_windows.append(self)

    monkeypatch.setattr("apps.desktop.window.PixelInspectorWindow", FakePixelInspectorWindow)

    window.open_pixel_inspector_window()
    pointer_window = window._pixel_inspector_window
    assert pointer_window is not None

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()
    assert closed_windows == [pointer_window]
    assert window._pixel_inspector_window is None


def test_desktop_window_delegates_script_actions(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(
        window.script_controller,
        "play",
        lambda document, mode=PlaybackMode.LIVE: calls.append(
            ("play", document.document_id, mode.value)
        )
        or True,
    )
    monkeypatch.setattr(
        window.script_controller,
        "record",
        lambda: calls.append(("record", None, None)) or True,
    )
    monkeypatch.setattr(
        window.script_controller,
        "stop",
        lambda: calls.append(("stop", None, None)) or True,
    )

    assert window.play_script(mode=PlaybackMode.PREVIEW) is True
    assert window.play_script() is True
    assert window.record_script() is True
    assert window.stop_script() is True
    assert calls[0][2] == "preview"
    assert calls[1][2] == "live"
    assert [kind for kind, *_ in calls] == ["play", "play", "record", "stop"]


def test_desktop_window_stop_action_routes_debugger_stop_from_toolbar_and_menu(monkeypatch) -> None:
    _app()

    window = _new_window()
    calls: list[str] = []

    monkeypatch.setattr(window, "_debug_session_is_active", lambda: True)
    monkeypatch.setattr(window, "stop_debug_session", lambda: calls.append("debug_stop"))

    window._update_script_action_state()

    stop_button = _required_child(window.playback_toolbar_group, QToolButton, "stopScriptToolbarButton")
    assert stop_button is not None
    assert window.script_menu.actions()[3] is window.stop_script_action
    assert window.stop_script_action.isEnabled() is True

    stop_button.click()
    window.script_menu.actions()[3].trigger()

    assert calls == ["debug_stop", "debug_stop"]


def test_desktop_window_shift_esc_hotkey_stops_debugger_session(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    calls: list[str] = []

    monkeypatch.setattr(window, "_debug_session_is_active", lambda: True)
    monkeypatch.setattr(window, "stop_debug_session", lambda: calls.append("debug_stop"))

    window._update_script_action_state()
    window.show()
    window.activateWindow()
    window.editor.setFocus()
    app.processEvents()

    QTest.keyClick(window.editor, Qt.Key.Key_Escape, Qt.KeyboardModifier.ShiftModifier)

    assert calls == ["debug_stop"]


def test_desktop_window_updates_playback_stop_hotkey_from_current_bindings() -> None:
    _app()

    window = _new_window()

    window._apply_hotkeys({"stop": "Shift+Esc|Ctrl+C"})

    assert window.script_controller._playback_stop_hotkey == "Shift+Esc|Ctrl+C"
    assert window.stop_script_action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == QKeySequence(
        "Shift+Esc"
    ).toString(QKeySequence.SequenceFormat.PortableText)
    assert window.stop_script_action.toolTip() == "Stop (Shift+Esc | Ctrl+C)"
    assert window.stop_script_action.statusTip() == "Stop (Shift+Esc | Ctrl+C)"


def test_desktop_window_stop_action_is_enabled_during_debugger_sessions(monkeypatch) -> None:
    _app()

    window = _new_window()

    idle_stop_icon_key = window.debug_stop_button.icon().cacheKey()
    assert idle_stop_icon_key == window.debug_stop_action.icon().cacheKey()

    window._update_script_action_state()
    assert window.play_script_action.isEnabled() is True
    assert window.preview_play_script_action.isEnabled() is True
    assert window.record_script_action.isEnabled() is True
    assert window.stop_script_action.isEnabled() is False
    assert window.debugger_action.isEnabled() is True
    assert window.debug_continue_action.isEnabled() is False

    monkeypatch.setattr(window, "_debug_session_is_active", lambda: True)
    window._update_script_action_state()
    window._update_debugger_controls_state(active=True)

    assert window.play_script_action.isEnabled() is False
    assert window.preview_play_script_action.isEnabled() is False
    assert window.record_script_action.isEnabled() is False
    assert window.stop_script_action.isEnabled() is True
    assert window.debugger_action.isEnabled() is False
    assert window.debug_continue_action.isEnabled() is True
    assert window.debug_stop_button.icon().cacheKey() != idle_stop_icon_key
    assert window.debug_stop_button.icon().cacheKey() == window.debug_stop_action.icon().cacheKey()

    window._update_debugger_controls_state(active=False)
    assert window.debug_stop_button.icon().cacheKey() == idle_stop_icon_key


def test_desktop_window_preview_play_refreshes_stale_analysis_before_execution(monkeypatch) -> None:
    app = _app()

    window = _new_window()
    bad_text = "Func CallThing()\nEndFunc\nCallThng()\n"
    clean_text = 'WriteLn("ok")\n'

    window.editor.setPlainText(bad_text)
    app.processEvents()
    window.analyze_action.trigger()
    app.processEvents()

    window.editor.setPlainText(clean_text)
    app.processEvents()

    calls: list[tuple[str, str, int]] = []

    def fake_play(document, *, mode=PlaybackMode.LIVE):
        calls.append((document.text, mode.value, document.version.value))
        return True

    monkeypatch.setattr(window.script_controller, "play", fake_play)

    assert window.preview_play_script() is True
    assert calls == [(clean_text, "preview", window.current_document.version.value)]
    assert window.current_analysis is not None
    assert window.current_analysis.document_version == window.current_document.version
    assert window.current_analysis.diagnostics.has_errors is False
    assert window._analysis_stale is False
    assert "Analysis refreshed from current editor text" in window.statusBar().currentMessage()


@pytest.mark.parametrize("invoke_name,mode_label", [("play_script", "play"), ("preview_play_script", "preview")])
def test_desktop_window_blocks_current_analysis_errors_before_playback(
    monkeypatch,
    invoke_name: str,
    mode_label: str,
) -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("Func CallThing()\nEndFunc\nCallThng()\n")
    app.processEvents()
    window.analyze_action.trigger()
    app.processEvents()

    assert window.current_analysis is not None
    first_diagnostic = window.current_analysis.diagnostics.items[0]
    assert first_diagnostic.code == "SEM008"
    assert first_diagnostic.span is not None

    def fail_if_reanalyzed() -> bool:
        raise AssertionError("current analysis should be reused when it is already current")

    monkeypatch.setattr(window, "analyze_document", fail_if_reanalyzed)

    calls: list[str] = []

    def fake_play(document, *, mode=PlaybackMode.LIVE):
        calls.append(mode.value)
        return True

    monkeypatch.setattr(window.script_controller, "play", fake_play)

    result = getattr(window, invoke_name)()

    assert result is False
    assert calls == []
    assert f"Script {mode_label} blocked: current editor text has 1 error(s);" in window.statusBar().currentMessage()
    assert "jumped to the first diagnostic" in window.statusBar().currentMessage()
    assert window.workspace_tabs.currentWidget() is window.editor
    assert window.editor.textCursor().selectionStart() == first_diagnostic.span.start
    assert window.editor.textCursor().selectionEnd() == first_diagnostic.span.end


def test_desktop_window_preview_play_surfaces_preview_status_without_live_executor(
    monkeypatch,
) -> None:
    app = _app()

    window = _new_window()

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

    window.editor.setPlainText('SendText("hello")\nWriteLn("preview")\n')
    app.processEvents()

    assert window.preview_play_script() is True
    thread = window.script_controller._script_operation_thread
    assert thread is not None
    deadline = time.monotonic() + 2.0
    while thread.is_alive() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    thread.join(timeout=1.0)
    window.script_controller._poll_script_operation()

    assert window.statusBar().currentMessage().startswith("* Script preview completed (1 events)")
    text = window.playback_output_view.toPlainText()
    assert "Console output:" in text
    assert "preview" in text


def test_desktop_window_updates_script_controller_playback_settings(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    captured: list[DesktopPlaybackSettings] = []

    monkeypatch.setattr(
        window.script_controller,
        "set_playback_settings",
        lambda settings: captured.append(settings),
    )

    bundle = DesktopSettingsBundle(
        playback=DesktopPlaybackSettings(
            repeat_count=5,
            step_mode=True,
            delay_ms=250,
            mouse_settle_ms=33,
        )
    )

    window._on_preferences_changed(bundle)

    assert captured == [bundle.playback]


def test_desktop_window_updates_script_controller_runtime_settings(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    captured: list[tuple[str, object]] = []

    monkeypatch.setattr(
        window.script_controller,
        "set_runtime_settings",
        lambda settings: captured.append(("runtime", settings)),
    )

    bundle = DesktopSettingsBundle()
    bundle.runtime.max_loop_iterations = 777
    bundle.runtime.max_call_depth = 88
    bundle.runtime.default_mouse_move_speed = 19

    window._on_preferences_changed(bundle)

    assert captured == [("runtime", bundle.runtime)]


def test_desktop_window_updates_debugger_service_runtime_settings(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    captured: list[object] = []

    monkeypatch.setattr(
        window._debugging_service,
        "set_runtime_settings",
        lambda settings: captured.append(settings),
    )

    bundle = DesktopSettingsBundle()
    bundle.runtime.max_loop_iterations = 777
    bundle.runtime.max_call_depth = 88
    bundle.runtime.default_mouse_move_speed = 19

    window._on_preferences_changed(bundle)

    assert captured == [bundle.runtime]


def test_desktop_window_discarding_dirty_preferences_exits_without_loop(monkeypatch) -> None:
    _app()

    window = ActionShellScriptDesktopWindow(
        services=DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
    )
    window._settings_dirty = True
    discarded: list[bool] = []

    monkeypatch.setattr(
        "apps.desktop.window.question_save_discard_cancel",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    monkeypatch.setattr(window, "_discard_preferences_changes", lambda: discarded.append(True))

    event = QCloseEvent()

    window.closeEvent(event)

    assert event.isAccepted() is True
    assert discarded == [True]


def test_desktop_window_find_action_opens_sidebar_mode_and_replace_action_opens_sidebar_replace_tab(monkeypatch) -> None:
    _app()

    window = _new_window()

    window.find_action.trigger()
    window.replace_action.trigger()

    assert window._current_sidebar_mode == "find"
    find_widgets = window._find_sidebar_widgets
    assert find_widgets is not None
    assert window.sidebar_mode_stack.currentWidget() is find_widgets.page
    assert find_widgets.tab_widget.currentIndex() == 1


def test_desktop_window_sidebar_modes_share_the_new_shell_layout() -> None:
    app = _app()

    window = _new_window()
    window.show()
    app.processEvents()

    shell_stylesheet = window.sidebar_shell.styleSheet()
    assert "QWidget#findSidebarPage" in shell_stylesheet
    assert "QWidget#analysisSidebarPage" in shell_stylesheet
    assert "QTabWidget::pane" in shell_stylesheet
    assert window.sidebar_mode_title_label.isVisible() is False

    window.find_action.trigger()
    app.processEvents()

    find_widgets = window._find_sidebar_widgets
    assert find_widgets is not None
    assert window._current_sidebar_mode == "find"
    assert window.sidebar_mode_stack.currentWidget() is find_widgets.page
    assert window.sidebar_mode_title_label.isVisible() is True
    assert window.sidebar_mode_title_label.text() == "Find"

    window.analyze_action.trigger()
    app.processEvents()

    analysis_widgets = window._analysis_sidebar_widgets
    assert analysis_widgets is not None
    assert window._current_sidebar_mode == "analysis"
    assert window.sidebar_mode_stack.currentWidget() is analysis_widgets.page
    assert window.sidebar_mode_title_label.isVisible() is True
    assert window.sidebar_mode_title_label.text() == "Analysis"

    window.view_debugger_tab_action.trigger()
    app.processEvents()

    assert window._current_sidebar_mode == "debug"
    assert window.sidebar_mode_stack.currentWidget() is window.debugger_panel
    assert window.sidebar_mode_title_label.isVisible() is False


def test_desktop_window_keeps_hidden_sidebar_reopen_affordance_aligned_during_resize() -> None:
    app = _app()

    window = _new_window()
    window.show()
    window.resize(1300, 840)
    app.processEvents()

    visible_sidebar_width = window.summary_dock.width()
    assert visible_sidebar_width > 0
    hidden_tabs_button_x_before = window.hidden_workspace_tabs_collapse_button.mapTo(window, QPoint(0, 0)).x()

    window.summary_sidebar_toolbar_button.click()
    app.processEvents()

    hidden_spacer_width = window.summary_sidebar_reopen_spacer.width()
    assert window.summary_sidebar_reopen_strip.isVisible() is True
    assert hidden_spacer_width == 0
    reopen_button_x = window.summary_sidebar_reopen_button.mapTo(window, QPoint(0, 0)).x()
    assert reopen_button_x < hidden_tabs_button_x_before
    assert window.hidden_workspace_tabs_collapse_button.mapTo(window, QPoint(0, 0)).x() > reopen_button_x
    assert window.hidden_workspace_tabs_anchor_spacer.width() == 0

    window.resize(1500, 840)
    app.processEvents()

    assert window.summary_sidebar_reopen_strip.isVisible() is True
    assert window.summary_sidebar_reopen_spacer.width() == 0
    assert window.summary_sidebar_reopen_button.mapTo(window, QPoint(0, 0)).x() == reopen_button_x

    window.summary_sidebar_reopen_button.click()
    app.processEvents()

    assert window.summary_dock.isVisible() is True
    assert window.summary_sidebar_reopen_strip.isVisible() is False


def test_desktop_window_replace_button_replaces_single_match() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha")

    replace_button, _ = _open_replace_sidebar(
        window,
        find_text="alpha",
        replace_text="omega",
    )
    assert replace_button is not None
    widgets = window._find_sidebar_widgets
    assert widgets is not None
    replace_page = widgets.pages["replace"]
    assert replace_button.text() == "Replace Next"
    assert widgets.replace_button is not None
    assert widgets.replace_button.text() == "Replace Next"
    assert window.replace_current_action.text() == "Replace Next"
    assert replace_page.backward_check.text() == "Previous direction"

    replace_button.click()

    assert window.editor.toPlainText() == "omega beta alpha"
    assert widgets.status_label.text() == "Replaced 1 match."
    assert widgets.results_summary_label.text() == "Search results will appear here."
    assert replace_page.find_combo.currentText() == "alpha"
    assert replace_page.replace_combo is not None
    assert replace_page.replace_combo.currentText() == "omega"


def test_desktop_window_replace_button_and_action_follow_previous_direction_checkbox() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)

    replace_button, _ = _open_replace_sidebar(
        window,
        find_text="alpha",
        replace_text="omega",
    )
    assert replace_button is not None

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    replace_page = widgets.pages["replace"]
    replace_page.backward_check.setChecked(True)

    assert replace_button.text() == "Replace Previous"
    assert widgets.replace_button is not None
    assert widgets.replace_button.text() == "Replace Previous"
    assert window.replace_current_action.text() == "Replace Previous"

    replace_button.click()

    assert window.editor.toPlainText() == "alpha beta omega"
    assert widgets.status_label.text() == "Replaced 1 match."


def test_desktop_window_replace_all_button_replaces_every_match() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha\nalpha\n")

    _, replace_all_button = _open_replace_sidebar(
        window,
        find_text="alpha",
        replace_text="omega",
    )
    assert replace_all_button is not None

    replace_all_button.click()

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    assert window.editor.toPlainText() == "omega beta omega\nomega\n"
    assert widgets.status_label.text() == "Replaced 3 matches."
    assert widgets.results_summary_label.text() == "Search results will appear here."


@pytest.mark.parametrize(
    ("find_text", "replace_text", "search_mode", "expected_status"),
    [
        ("zzz", "omega", "normal", "No matches found."),
        ("(", "omega", "regex", "Invalid regular expression:"),
    ],
)
def test_desktop_window_replace_actions_report_no_match_and_regex_errors(
    find_text: str,
    replace_text: str,
    search_mode: str,
    expected_status: str,
) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha")

    replace_button, replace_all_button = _open_replace_sidebar(
        window,
        find_text=find_text,
        replace_text=replace_text,
        search_mode=search_mode,
    )
    assert replace_button is not None
    assert replace_all_button is not None

    if search_mode == "regex":
        replace_all_button.click()
    else:
        replace_button.click()

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    assert window.editor.toPlainText() == "alpha beta alpha"
    assert widgets.status_label.text().startswith(expected_status)
    assert widgets.results_summary_label.text() == "Search results will appear here."


def test_desktop_window_find_all_populates_sidebar_results(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\nalpha\n")

    window.find_action.trigger()
    widgets = window._find_sidebar_widgets
    assert widgets is not None

    find_page = widgets.pages["find"]
    _combo_line_edit(find_page.find_combo).setText("alpha")
    widgets.find_all_button.click()

    assert widgets.status_label.text() == "Find All: 2 matches shown in the sidebar."
    assert widgets.results_summary_label.text() == 'Search "alpha" (2 hits in 1 file)'
    assert widgets.results_tree.topLevelItemCount() == 2
    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )
    first_group = _required_top_level_item(widgets.results_tree, 0)
    assert first_group.text(0) == "Line 1"
    assert first_group.childCount() == 1
    second_group = _required_top_level_item(widgets.results_tree, 1)
    assert second_group.text(0) == "Line 3"
    assert second_group.childCount() == 1


def test_desktop_window_find_all_keyboard_navigation_keeps_results_tree_in_sync() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\nalpha\n")
    window.show()
    window.activateWindow()
    window.editor.setFocus()
    app.processEvents()

    _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    widgets.find_all_button.click()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )

    QTest.keyClick(window.editor, Qt.Key.Key_F3)

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 3",
        expected_start=11,
        expected_end=16,
    )

    QTest.keyClick(window.editor, Qt.Key.Key_F3, Qt.KeyboardModifier.ShiftModifier)

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )


def test_desktop_window_find_all_menu_navigation_keeps_results_tree_in_sync() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\nalpha\n")

    _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    widgets.find_all_button.click()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )

    window.find_next_action.trigger()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 3",
        expected_start=11,
        expected_end=16,
    )

    window.find_previous_action.trigger()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )


def test_desktop_window_find_all_sidebar_navigation_keeps_results_tree_in_sync() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\nalpha\n")

    previous_button, next_button = _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    widgets.find_all_button.click()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )

    next_button.click()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 3",
        expected_start=11,
        expected_end=16,
    )

    previous_button.click()

    _assert_find_all_results_tree_active_match(
        window,
        expected_line_label="Line 1",
        expected_start=0,
        expected_end=5,
    )


def test_desktop_window_find_buttons_preserve_backward_direction_checkbox_state() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha gamma alpha")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)

    previous_button, next_button = _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    find_page = widgets.pages["find"]
    find_page.backward_check.setChecked(True)

    next_button.click()

    assert find_page.backward_check.isChecked() is True
    assert window.editor.textCursor().selectionStart() == 23
    assert window.editor.textCursor().selectionEnd() == 28

    previous_button.click()

    assert find_page.backward_check.isChecked() is True
    assert window.editor.textCursor().selectionStart() == 11
    assert window.editor.textCursor().selectionEnd() == 16


def test_desktop_window_previous_menu_action_preserves_backward_direction_checkbox() -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha gamma alpha")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)

    _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    find_page = widgets.pages["find"]
    assert find_page.backward_check.isChecked() is False

    window.find_previous_action.trigger()

    assert find_page.backward_check.isChecked() is False
    assert window.editor.textCursor().selectionStart() == 23
    assert window.editor.textCursor().selectionEnd() == 28

    window.find_next_action.trigger()

    assert find_page.backward_check.isChecked() is False
    assert window.editor.textCursor().selectionStart() == 0
    assert window.editor.textCursor().selectionEnd() == 5


def test_desktop_window_shift_f3_preserves_backward_direction_checkbox() -> None:
    app = _app()

    window = _new_window()
    window.editor.setPlainText("alpha beta alpha gamma alpha")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.show()
    window.activateWindow()
    window.editor.setFocus()
    app.processEvents()

    _open_find_sidebar(
        window,
        find_text="alpha",
    )

    widgets = window._find_sidebar_widgets
    assert widgets is not None
    find_page = widgets.pages["find"]
    assert find_page.backward_check.isChecked() is False

    QTest.keyClick(window.editor, Qt.Key.Key_F3, Qt.KeyboardModifier.ShiftModifier)

    assert find_page.backward_check.isChecked() is False
    assert window.editor.textCursor().selectionStart() == 23
    assert window.editor.textCursor().selectionEnd() == 28

    window.find_next_action.trigger()

    assert find_page.backward_check.isChecked() is False
    assert window.editor.textCursor().selectionStart() == 0
    assert window.editor.textCursor().selectionEnd() == 5


def test_desktop_window_go_to_action_opens_go_to_dialog(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\ngamma")
    monkeypatch.setattr(window._settings_service, "save", lambda *args, **kwargs: None)
    opened_dialogs: list[QDialog] = []

    monkeypatch.setattr(
        QDialog,
        "exec",
        lambda self: opened_dialogs.append(self) or 0,
    )

    window.go_to_action.trigger()

    assert len(opened_dialogs) == 1
    dialog = opened_dialogs[0]
    assert dialog.windowTitle() == "Go to"
    _required_child(dialog, QRadioButton, "goToLineModeButton")
    _required_child(dialog, QRadioButton, "goToOffsetModeButton")
    _required_child(dialog, QSpinBox, "goToSpinBox")

    info_label = _required_child(dialog, QLabel, "goToInfoLabel")
    assert "Current line: 1 of 3" in info_label.text()
    limit_text = _required_child(dialog, QLabel, "goToLimitLabel").text()
    assert limit_text.startswith("Line mode cannot exceed 3 lines.")
    assert "Offset mode cannot exceed " in limit_text


def test_desktop_window_go_to_action_moves_cursor_to_selected_line(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\ngamma")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    monkeypatch.setattr(window._settings_service, "save", lambda *args, **kwargs: None)

    def fake_exec(self) -> int:
        _required_child(self, QRadioButton, "goToLineModeButton").setChecked(True)
        _required_child(self, QRadioButton, "goToOffsetModeButton").setChecked(False)
        _required_child(self, QSpinBox, "goToSpinBox").setValue(2)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window.go_to_action.trigger()

    assert window.editor.currentLineNumber() == 2
    assert window.editor.textCursor().position() == window.editor.document().findBlockByNumber(1).position()


def test_desktop_window_go_to_action_moves_cursor_to_selected_offset(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\ngamma")
    window.editor.moveCursor(QTextCursor.MoveOperation.Start)
    monkeypatch.setattr(window._settings_service, "save", lambda *args, **kwargs: None)

    def fake_exec(self) -> int:
        _required_child(self, QRadioButton, "goToLineModeButton").setChecked(False)
        _required_child(self, QRadioButton, "goToOffsetModeButton").setChecked(True)
        _required_child(self, QSpinBox, "goToSpinBox").setValue(7)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window.go_to_action.trigger()

    assert window.editor.textCursor().position() == 7


def test_desktop_window_go_to_action_remembers_last_mode_and_value(monkeypatch) -> None:
    _app()

    window = _new_window()
    window.editor.setPlainText("alpha\nbeta\ngamma")
    monkeypatch.setattr(window._settings_service, "save", lambda *args, **kwargs: None)
    dialogs: list[QDialog] = []
    entry_geometries: list[QRect] = []
    first_geometry: QRect | None = None
    second_geometry: QRect | None = None

    def fake_exec(self) -> int:
        nonlocal first_geometry, second_geometry
        dialogs.append(self)
        entry_geometries.append(self.geometry())
        dialog_index = len(dialogs)
        if dialog_index == 1:
            self.setGeometry(123, 234, 456, 321)
            first_geometry = self.geometry()
            _required_child(self, QRadioButton, "goToLineModeButton").setChecked(False)
            _required_child(self, QRadioButton, "goToOffsetModeButton").setChecked(True)
            _required_child(self, QSpinBox, "goToSpinBox").setValue(7)
            return int(QDialog.DialogCode.Accepted)

        if dialog_index == 2:
            self.setGeometry(222, 333, 444, 555)
            second_geometry = self.geometry()
            _required_child(self, QRadioButton, "goToLineModeButton").setChecked(True)
            _required_child(self, QRadioButton, "goToOffsetModeButton").setChecked(False)
            _required_child(self, QSpinBox, "goToSpinBox").setValue(2)
            return int(QDialog.DialogCode.Rejected)

        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window.go_to_action.trigger()
    window.go_to_action.trigger()
    window.go_to_action.trigger()

    second_dialog = dialogs[1]
    third_dialog = dialogs[2]

    assert _required_child(second_dialog, QRadioButton, "goToLineModeButton").isChecked() is True
    assert _required_child(second_dialog, QSpinBox, "goToSpinBox").value() == 2
    assert entry_geometries[1] == first_geometry
    assert _required_child(third_dialog, QRadioButton, "goToOffsetModeButton").isChecked() is True
    assert _required_child(third_dialog, QSpinBox, "goToSpinBox").value() == 7
    assert second_geometry is not None
    assert entry_geometries[2].width() == second_geometry.width()
    assert entry_geometries[2].height() == second_geometry.height()
    assert entry_geometries[2].x() == second_geometry.x()
    assert abs(entry_geometries[2].y() - second_geometry.y()) <= 100


def test_desktop_window_persists_go_to_dialog_state_across_restarts(tmp_path, monkeypatch) -> None:
    _app()

    from application.persistence.desktop_settings_service import DesktopSettingsService

    monkeypatch.setattr(
        "apps.desktop.window.DesktopSettingsService",
        lambda: DesktopSettingsService(config_dir=tmp_path),
    )

    first_window = _new_window()
    first_window.editor.setPlainText("alpha\nbeta\ngamma")
    dialogs: list[QDialog] = []
    entry_geometries: list[QRect] = []

    def first_exec(self) -> int:
        dialogs.append(self)
        entry_geometries.append(self.geometry())
        self.setGeometry(123, 234, 456, 321)
        _required_child(self, QRadioButton, "goToLineModeButton").setChecked(False)
        _required_child(self, QRadioButton, "goToOffsetModeButton").setChecked(True)
        _required_child(self, QSpinBox, "goToSpinBox").setValue(7)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(QDialog, "exec", first_exec)

    first_window.go_to_action.trigger()

    second_window = _new_window()
    second_window.editor.setPlainText("alpha\nbeta\ngamma")

    def second_exec(self) -> int:
        dialogs.append(self)
        entry_geometries.append(self.geometry())
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(QDialog, "exec", second_exec)

    second_window.go_to_action.trigger()

    second_dialog = dialogs[1]
    assert _required_child(second_dialog, QRadioButton, "goToOffsetModeButton").isChecked() is True
    assert _required_child(second_dialog, QSpinBox, "goToSpinBox").value() == 7
    assert entry_geometries[1].width() == 456
    assert entry_geometries[1].height() == 321
