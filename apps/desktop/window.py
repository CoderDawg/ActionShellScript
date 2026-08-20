from __future__ import annotations

import base64
import codecs
import os
import copy
import html
import sys
import uuid
import re
import threading
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

import qtawesome as qta
from qtawesome.iconic_font import IconicFont
from PySide6.QtCore import (
    QUrl,
    Qt,
    QSize,
    Signal,
    QByteArray,
    QEvent,
    QTimer,
    QSignalBlocker,
    QPoint,
    QProcess,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QIcon,
    QFont,
    QKeySequence,
    QColor,
    QDesktopServices,
    QPixmap,
    QTextDocument,
    QPalette,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QFrame,
    QLineEdit,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QStyleOptionTab,
    QToolBar,
    QToolButton,
    QStackedWidget,
    QSizePolicy,
    QPushButton,
    QSplitter,
    QHeaderView,
    QVBoxLayout,
    QStyle,
    QStylePainter,
    QTabBar,
    QTextEdit,
    QWidget,
)

from application.script_document_language_service import ScriptDocumentLanguageService
from application.script_generation_service import ScriptGenerationService
from application.shaping_service import ShapingService
from application.interpretation_service import InterpretationService
from application.debugging_service import DebuggingService, DebugRunHandle
from application.persistence.desktop_settings_service import DesktopSettingsService
from application.script_document_service import ScriptDocumentService
from apps.cli.session_json import save_raw_session
from apps.desktop.bootstrap import apply_desktop_widget_styles
from apps.desktop.documentation_messages import (
    ass_help_fallback_status,
    docs_index_path,
    documentation_unavailable_message,
    documentation_unavailable_status,
    system_viewer_fallback_status,
)
from apps.desktop.icon_assets import DesktopAsset, desktop_asset_path
from apps.desktop.help_browser import ActionShellScriptHelpBrowser
from apps.desktop.document_status_dialog import DocumentStatusDialog
from apps.desktop.editor_widget import CodeEditor
from apps.shared_notices import load_attribution_notice_text
from apps.desktop.hotkeys import (
    HOTKEY_DEFINITIONS,
    default_hotkey_bindings,
    display_hotkey_clauses,
    primary_hotkey_clause,
)
from apps.desktop.message_boxes import question_save_discard_cancel
from apps.desktop.preferences_dialog import PreferencesDialog
from apps.desktop.pixel_inspector_window import PixelInspectorWindow
from apps.desktop.script_action_controller import DesktopScriptActionController
from apps.desktop.presentation import (
    build_analysis_summary_lines,
    build_diagnostics_html,
    build_document_summary_lines,
    build_formatted_preview_text,
    build_playback_output_text,
    build_raw_recording_text,
)
from apps.desktop.settings import DesktopSettingsBundle
from apps.desktop.theme import DesktopPreferences, ScriptingSettings, validate_desktop_preferences_readability
from apps.desktop.theme import SearchResultsTheme
from editor.document.script_document import ScriptDocument
from core.debugging.debug_event import DebugEvent
from core.debugging.debug_request import DebugRequest
from core.recording.recording_session import RecordingSession
from core.scripting.diagnostics import TextSpan
from core.scripting.formatter import FormatOptions
from core.playback.playback_mode import PlaybackMode
from editor.language_services.formatting_service import FormattingService
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis
from core.playback.playback_result import PlaybackResult
from core.runtime.execution_context import ExecutionContext
from core.runtime.script_runtime import ScriptRuntimeCancelled
from core.runtime.script_runtime import ScriptRuntime
from core.runtime.struct_values import format_debugger_value, describe_debugger_value_type
from infrastructure.debug_logger import (
    DiagnosticEvent,
    get_diagnostic_config,
    get_diagnostic_logger,
    format_diagnostic_event,
    load_diagnostic_config_from_env,
    resolve_diagnostic_log_path,
    subscribe_diagnostic_events,
    set_diagnostic_config,
)
from infrastructure.persistence.script_document_file_store import ScriptDocumentFileStore


@dataclass(slots=True)
class DesktopServices:
    document_service: ScriptDocumentService
    language_service: ScriptDocumentLanguageService
    formatting_service: FormattingService
    document_store: ScriptDocumentFileStore


@dataclass(slots=True)
class SearchCriteria:
    find_text: str = ""
    replace_text: str = ""
    backward: bool = False
    whole_word: bool = False
    match_case: bool = False
    wrap_around: bool = True
    in_selection: bool = False
    search_mode: str = "normal"
    regex_matches_newline: bool = False
    active_tab: str = "find"


@dataclass(slots=True)
class SearchResult:
    found: bool
    count: int
    index: int | None = None
    start: int | None = None
    end: int | None = None


@dataclass(slots=True)
class SearchPageWidgets:
    page: QWidget
    find_combo: QComboBox
    replace_combo: QComboBox | None
    replace_button: QPushButton | None
    replace_all_button: QPushButton | None
    backward_check: QCheckBox
    whole_word_check: QCheckBox
    match_case_check: QCheckBox
    wrap_check: QCheckBox
    selection_check: QCheckBox
    normal_radio: QRadioButton
    extended_radio: QRadioButton
    regex_radio: QRadioButton
    regex_newline_check: QCheckBox


@dataclass(slots=True)
class SearchSidebarWidgets:
    page: QWidget
    tab_widget: QTabWidget
    pages: dict[str, SearchPageWidgets]
    results_summary_label: QLabel
    results_tree: QTreeWidget
    find_previous_button: QPushButton
    find_next_button: QPushButton
    count_button: QPushButton
    find_all_button: QPushButton
    replace_button: QPushButton | None
    replace_all_button: QPushButton | None
    status_label: QLabel


@dataclass(slots=True)
class AnalysisSidebarWidgets:
    page: QWidget
    header_state_label: QLabel
    header_count_label: QLabel
    summary_view: QPlainTextEdit
    diagnostics_view: QTextBrowser
    status_label: QLabel


class WorkspaceAttentionTabBar(QTabBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._attention_tabs: set[int] = set()
        self._attention_enabled = True
        self._attention_color = QColor("#2b7de9")

    def set_attention_settings(self, *, enabled: bool, accent_color: str) -> None:
        self._attention_enabled = bool(enabled)
        self._attention_color = QColor(accent_color)
        if not self._attention_enabled:
            self._attention_tabs.clear()
        self.update()

    def set_tab_attention(self, index: int, attention: bool) -> None:
        if index < 0:
            return
        if attention:
            if index in self._attention_tabs:
                return
            self._attention_tabs.add(index)
        else:
            if index not in self._attention_tabs:
                return
            self._attention_tabs.remove(index)
        self.update()

    def clear_tab_attention(self, index: int) -> None:
        self.set_tab_attention(index, False)

    def has_tab_attention(self, index: int) -> bool:
        return index in self._attention_tabs

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QStylePainter(self)
        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            if (
                self._attention_enabled
                and index in self._attention_tabs
                and not (option.state & QStyle.StateFlag.State_Selected)
            ):
                painter.save()
                fill_color = QColor(self._attention_color)
                fill_color.setAlpha(80)
                accent_color = QColor(self._attention_color)
                accent_color.setAlpha(210)
                painter.fillRect(option.rect.adjusted(1, 1, -1, -1), fill_color)
                accent_height = min(4, max(1, option.rect.height() - 2))
                accent_rect = option.rect.adjusted(
                    1,
                    1,
                    -1,
                    -(option.rect.height() - 2 - accent_height),
                )
                painter.fillRect(accent_rect, accent_color)
                painter.restore()
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabLabel, option)


window_log = get_diagnostic_logger("desktop.window")
editor_log = get_diagnostic_logger("desktop.editor")
preferences_log = get_diagnostic_logger("desktop.preferences")


class ActionShellScriptDesktopWindow(QMainWindow):
    diagnosticEventReceived = Signal(object)
    debugEventReceived = Signal(object)
    debugMessageReceived = Signal(str)
    debugSessionFinished = Signal(str)

    def __init__(
        self,
        *,
        services: DesktopServices | None = None,
        initial_path: Path | None = None,
    ) -> None:
        super().__init__()
        apply_desktop_widget_styles()
        self._base_window_title = "ActionShellScript Desktop"
        self.setWindowTitle(self._base_window_title)
        self.setWindowIcon(self._frog_icon())
        self.resize(1360, 840)
        self.setMinimumSize(1040, 700)

        self.services = services or DesktopServices(
            document_service=ScriptDocumentService(),
            language_service=ScriptDocumentLanguageService(),
            formatting_service=FormattingService(),
            document_store=ScriptDocumentFileStore(),
        )
        self._settings_service = DesktopSettingsService()
        self._committed_settings_bundle = self._settings_service.load()
        self._session_last_open_directory: Path | None = None

        self.current_path: Path | None = None
        self.current_document = ScriptDocument(
            document_id=str(uuid.uuid4()),
            text="",
        )
        self.current_analysis: ScriptDocumentAnalysis | None = None
        self._editor_dirty = False
        self._analysis_stale = False
        self._loading_document = False
        self._saved_document_text = self.current_document.text
        self._last_preview_text = ""
        self._search_criteria = SearchCriteria()
        self._recent_find_terms: list[str] = []
        self._recent_replace_terms: list[str] = []
        self._go_to_last_mode = "line"
        self._go_to_last_value = 1
        self._go_to_last_geometry: QByteArray | None = None
        self._analysis_diagnostic_spans: dict[str, TextSpan] = {}
        self._diagnostics_live_lines: list[str] = []
        self._diagnostics_event_unsubscribe: Callable[[], None] | None = None
        self._current_recording_session = None
        self._current_playback_result: PlaybackResult | None = None
        self._preferences = self._committed_settings_bundle.theme
        self._settings_dirty = False
        self._hotkeys_search_text = ""
        self._current_hotkey_bindings = default_hotkey_bindings()
        self._preferences_dialog: PreferencesDialog | None = None
        self._help_browser_window: ActionShellScriptHelpBrowser | None = None
        self._pixel_inspector_window: PixelInspectorWindow | None = None
        self._find_sidebar_widgets: SearchSidebarWidgets | None = None
        self._analysis_sidebar_widgets: AnalysisSidebarWidgets | None = None
        self._debugging_service = DebuggingService(
            self._committed_settings_bundle.runtime,
            self._committed_settings_bundle.playback,
        )
        self._debug_watch_runtime = ScriptRuntime()
        self._debug_watch_expressions: list[str] = []
        self._debug_watch_tree_syncing = False
        self._debug_session_handle: DebugRunHandle | None = None
        self._debug_session_stop_event: threading.Event | None = None
        self._debug_session_thread: threading.Thread | None = None
        self._last_debug_session_outcome: str | None = None
        self._debug_session_previous_show_debug_tab: bool | None = None
        self._pending_debug_restart = False
        self._sidebar_auto_hidden = False
        self._sidebar_user_hidden = False
        self._summary_sidebar_auto_hidden = self._sidebar_auto_hidden
        self._summary_sidebar_user_hidden = self._sidebar_user_hidden
        self._search_results_last_criteria = SearchCriteria()
        self._search_results_hover_top_item: QTreeWidgetItem | None = None
        self._file_icon_font = self._build_file_icon_font()
        self._playback_icon_font = self._build_playback_icon_font()
        self.script_controller = DesktopScriptActionController(self)
        self.script_controller.set_playback_settings(self._committed_settings_bundle.playback)
        self.script_controller.set_recording_settings(self._committed_settings_bundle.recording)
        self.script_controller.set_runtime_settings(self._committed_settings_bundle.runtime)
        self.script_controller.set_playback_stop_hotkey(
            self._committed_settings_bundle.application.hotkeys.bindings.get("stop", "")
        )

        self._bind_actions()
        self._apply_hotkeys(self._committed_settings_bundle.application.hotkeys.bindings)
        self._update_file_action_affordances()
        self._update_search_action_affordances()
        self._update_analysis_action_affordances()
        self._update_breakpoint_action_affordances()
        self._update_debug_step_action_affordances()
        self._update_settings_action_affordances()
        self._update_playback_action_affordances()

        self.summary_view = QPlainTextEdit()
        self.summary_view.setReadOnly(True)
        self.summary_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        self.editor = CodeEditor()
        self.editor.textChanged.connect(self._on_editor_text_changed)
        self.editor.breakpointLinesChanged.connect(self._on_breakpoints_changed)
        self.editor.cursorPositionChanged.connect(self._update_editor_status_details)
        self.editor.cursorPositionChanged.connect(self._update_breakpoint_action_affordances)
        self.editor.cursorPositionChanged.connect(self._update_search_action_affordances)
        self._update_breakpoint_action_affordances()

        self.diagnostics_view = QTextBrowser()
        self.diagnostics_view.setOpenExternalLinks(False)
        self.diagnostics_view.setOpenLinks(False)
        self.diagnostics_view.anchorClicked.connect(self._handle_diagnostics_anchor_clicked)
        self.diagnostics_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.diagnostics_log_path_label = QLabel()
        self.diagnostics_log_path_label.setObjectName("diagnosticsLogPathLabel")
        self.diagnostics_log_path_label.setWordWrap(True)
        self.diagnostics_log_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.diagnostics_log_path_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.diagnostics_clear_button = QPushButton("Clear diagnostics")
        self.diagnostics_clear_button.setObjectName("diagnosticsClearButton")
        self.diagnostics_clear_button.clicked.connect(self.clear_diagnostics_output)
        self.diagnostics_clear_button.setEnabled(False)
        self.diagnostics_tab = QWidget()
        diagnostics_layout = QVBoxLayout(self.diagnostics_tab)
        diagnostics_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_layout.setSpacing(6)
        diagnostics_header = QWidget()
        diagnostics_header_layout = QHBoxLayout(diagnostics_header)
        diagnostics_header_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_header_layout.setSpacing(8)
        diagnostics_header_layout.addWidget(self.diagnostics_log_path_label, 1)
        diagnostics_header_layout.addWidget(self.diagnostics_clear_button, 0)
        diagnostics_layout.addWidget(diagnostics_header)
        diagnostics_layout.addWidget(self.diagnostics_view, 1)

        self.playback_output_view = QPlainTextEdit()
        self.playback_output_view.setReadOnly(True)
        self.playback_output_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        self.analysis_workspace_tab = QWidget()
        self.analysis_tab = self.analysis_workspace_tab
        analysis_layout = QVBoxLayout(self.analysis_workspace_tab)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(6)

        analysis_summary_group = QGroupBox("Analysis Summary")
        analysis_summary_layout = QVBoxLayout(analysis_summary_group)
        analysis_summary_layout.setContentsMargins(8, 8, 8, 8)
        analysis_summary_layout.setSpacing(6)
        self.analysis_summary_view = QPlainTextEdit()
        self.analysis_summary_view.setReadOnly(True)
        self.analysis_summary_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        analysis_summary_layout.addWidget(self.analysis_summary_view)

        analysis_diagnostics_group = QGroupBox("Analysis Diagnostics")
        analysis_diagnostics_layout = QVBoxLayout(analysis_diagnostics_group)
        analysis_diagnostics_layout.setContentsMargins(8, 8, 8, 8)
        analysis_diagnostics_layout.setSpacing(6)
        analysis_diagnostics_header = QLabel("Click a card to jump to the source span.")
        analysis_diagnostics_header.setObjectName("analysisDiagnosticsHeader")
        analysis_diagnostics_header.setWordWrap(True)
        analysis_diagnostics_header.setStyleSheet("color: #666666; font-size: 11px;")
        analysis_diagnostics_layout.addWidget(analysis_diagnostics_header)
        self.analysis_diagnostics_view = QTextBrowser()
        self.analysis_diagnostics_view.setOpenExternalLinks(False)
        self.analysis_diagnostics_view.setOpenLinks(False)
        self.analysis_diagnostics_view.anchorClicked.connect(
            self._handle_diagnostics_anchor_clicked
        )
        self.analysis_diagnostics_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        analysis_diagnostics_layout.addWidget(self.analysis_diagnostics_view)

        analysis_layout.addWidget(analysis_summary_group, 0)
        analysis_layout.addWidget(analysis_diagnostics_group, 1)

        self.debugger_panel = QWidget()
        self.debugger_panel.setObjectName("debugInspectorView")
        debug_layout = QVBoxLayout(self.debugger_panel)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_layout.setSpacing(6)

        debug_header = QWidget()
        debug_header.setObjectName("debugInspectorHeader")
        debug_header_layout = QHBoxLayout(debug_header)
        debug_header_layout.setContentsMargins(6, 4, 6, 4)
        debug_header_layout.setSpacing(6)

        debug_header_copy = QWidget()
        debug_header_copy_layout = QVBoxLayout(debug_header_copy)
        debug_header_copy_layout.setContentsMargins(0, 0, 0, 0)
        debug_header_copy_layout.setSpacing(0)
        self.debug_header_title_label = QLabel("Debugger")
        self.debug_header_title_label.setObjectName("debugInspectorTitleLabel")
        self.debug_header_subtitle_label = QLabel("Variables, watches, call stack, and event log")
        self.debug_header_subtitle_label.setObjectName("debugInspectorSubtitleLabel")
        self.debug_header_subtitle_label.setWordWrap(True)
        debug_header_copy_layout.addWidget(self.debug_header_title_label)
        debug_header_copy_layout.addWidget(self.debug_header_subtitle_label)

        self.debug_status_indicator = QLabel()
        self.debug_status_indicator.setObjectName("debugStatusIndicator")
        self.debug_status_indicator.setFixedSize(10, 8)
        self.debug_status_indicator.setToolTip("Idle")
        self.debug_status_indicator.setStyleSheet(self._debug_status_indicator_stylesheet("#9ea7af"))
        self.debug_status_text_label = QLabel("Idle")
        self.debug_status_text_label.setObjectName("debugInspectorStatusLabel")
        self.debug_status_text_label.setStyleSheet("font-size: 9px; font-weight: 600; color: #52606d;")
        debug_status_chip = QWidget()
        debug_status_chip.setObjectName("debugStatusChip")
        debug_status_chip_layout = QHBoxLayout(debug_status_chip)
        debug_status_chip_layout.setContentsMargins(6, 2, 6, 2)
        debug_status_chip_layout.setSpacing(4)
        debug_status_chip_layout.addWidget(self.debug_status_indicator, 0)
        debug_status_chip_layout.addWidget(self.debug_status_text_label, 0)
        debug_status_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        debug_header_layout.addWidget(debug_header_copy, 1)
        self.debugger_controls_button = QToolButton()
        self.debugger_controls_button.setObjectName("debugControlsButton")
        self.debugger_controls_button.setText("Debugger Controls")
        self.debugger_controls_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.debugger_controls_button.setAutoRaise(False)
        self.debugger_controls_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.debugger_controls_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.debugger_controls_button.setMinimumHeight(22)
        self.debugger_controls_button.clicked.connect(self._show_debugger_controls_dialog)
        debug_header_layout.addWidget(debug_status_chip, 0)
        debug_header_layout.addWidget(self.debugger_controls_button, 0)
        debug_layout.addWidget(debug_header)

        stack_group = QGroupBox("Call Stack")
        stack_group.setFlat(True)
        stack_group_layout = QVBoxLayout(stack_group)
        stack_group_layout.setContentsMargins(6, 6, 6, 4)
        stack_group_layout.setSpacing(4)
        self.debug_call_stack_tree = QTreeWidget()
        self.debug_call_stack_tree.setObjectName("debugCallStackTree")
        self.debug_call_stack_tree.setHeaderLabels(["Depth", "Function", "Line"])
        self.debug_call_stack_tree.setRootIsDecorated(False)
        self.debug_call_stack_tree.setAlternatingRowColors(True)
        self.debug_call_stack_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_call_stack_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_call_stack_tree.setUniformRowHeights(True)
        self.debug_call_stack_tree.header().setStretchLastSection(False)
        self.debug_call_stack_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_call_stack_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.debug_call_stack_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_call_stack_empty_label = self._build_debug_tree_empty_state_label(
            "Call stack is empty"
        )
        self.debug_call_stack_stack = QStackedWidget()
        self.debug_call_stack_stack.setObjectName("debugCallStackStack")
        self.debug_call_stack_stack.addWidget(self.debug_call_stack_empty_label)
        self.debug_call_stack_stack.addWidget(self.debug_call_stack_tree)
        stack_group_layout.addWidget(self.debug_call_stack_stack)

        variables_group = QGroupBox("Variables")
        variables_group.setFlat(True)
        variables_group_layout = QVBoxLayout(variables_group)
        variables_group_layout.setContentsMargins(6, 6, 6, 4)
        variables_group_layout.setSpacing(4)
        self.debug_variables_tree = QTreeWidget()
        self.debug_variables_tree.setObjectName("debugVariablesTree")
        self.debug_variables_tree.setHeaderLabels(["Name", "Value", "Type"])
        self.debug_variables_tree.setRootIsDecorated(True)
        self.debug_variables_tree.setAlternatingRowColors(True)
        self.debug_variables_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_variables_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_variables_tree.setUniformRowHeights(True)
        self.debug_variables_tree.header().setStretchLastSection(False)
        self.debug_variables_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_variables_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.debug_variables_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_variables_empty_label = self._build_debug_tree_empty_state_label(
            "No variables to show"
        )
        self.debug_variables_stack = QStackedWidget()
        self.debug_variables_stack.setObjectName("debugVariablesStack")
        self.debug_variables_stack.addWidget(self.debug_variables_empty_label)
        self.debug_variables_stack.addWidget(self.debug_variables_tree)
        variables_group_layout.addWidget(self.debug_variables_stack)

        watch_group = QGroupBox("Watch Expressions")
        watch_group.setFlat(True)
        watch_group_layout = QVBoxLayout(watch_group)
        watch_group_layout.setContentsMargins(6, 6, 6, 4)
        watch_group_layout.setSpacing(3)
        watch_input_row = QWidget()
        watch_input_layout = QHBoxLayout(watch_input_row)
        watch_input_layout.setContentsMargins(0, 0, 0, 0)
        watch_input_layout.setSpacing(3)
        watch_input_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.debug_watch_expression_edit = QLineEdit()
        self.debug_watch_expression_edit.setObjectName("debugWatchExpressionEdit")
        self.debug_watch_expression_edit.setPlaceholderText("Type an expression and press Add")
        self.debug_watch_expression_edit.returnPressed.connect(self._add_debug_watch_expression)
        self.debug_watch_expression_edit.setMinimumHeight(24)
        self.debug_add_watch_button = QPushButton("Add")
        self.debug_add_watch_button.setObjectName("debugAddWatchButton")
        self.debug_add_watch_button.clicked.connect(self._add_debug_watch_expression)
        self.debug_remove_watch_button = QPushButton("Remove")
        self.debug_remove_watch_button.setObjectName("debugRemoveWatchButton")
        self.debug_remove_watch_button.clicked.connect(self._remove_selected_debug_watch_expression)
        for widget in (
            self.debug_watch_expression_edit,
            self.debug_add_watch_button,
            self.debug_remove_watch_button,
        ):
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            widget.setMinimumHeight(22)
        watch_input_layout.addWidget(self.debug_watch_expression_edit, 1)
        watch_input_layout.addWidget(self.debug_add_watch_button)
        watch_input_layout.addWidget(self.debug_remove_watch_button)
        watch_group_layout.addWidget(watch_input_row)
        self.debug_watch_tree = QTreeWidget()
        self.debug_watch_tree.setObjectName("debugWatchTree")
        self.debug_watch_tree.setHeaderLabels(["Expression", "Value", "Type", "Status"])
        self.debug_watch_tree.setRootIsDecorated(False)
        self.debug_watch_tree.setAlternatingRowColors(True)
        self.debug_watch_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_watch_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_watch_tree.setUniformRowHeights(True)
        self.debug_watch_tree.header().setStretchLastSection(False)
        self.debug_watch_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.debug_watch_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_watch_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_watch_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.debug_watch_tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.debug_watch_tree.itemChanged.connect(self._on_debug_watch_item_changed)
        self.debug_watch_empty_label = self._build_debug_tree_empty_state_label(
            "Add a watch expression to get started"
        )
        self.debug_watch_stack = QStackedWidget()
        self.debug_watch_stack.setObjectName("debugWatchStack")
        self.debug_watch_stack.addWidget(self.debug_watch_empty_label)
        self.debug_watch_stack.addWidget(self.debug_watch_tree)
        watch_group_layout.addWidget(self.debug_watch_stack)

        log_group = QGroupBox("Event Log")
        log_group.setFlat(True)
        log_group_layout = QVBoxLayout(log_group)
        log_group_layout.setContentsMargins(6, 6, 6, 4)
        log_group_layout.setSpacing(4)
        self.debug_event_log_view = QPlainTextEdit()
        self.debug_event_log_view.setObjectName("debugEventLogView")
        self.debug_event_log_view.setReadOnly(True)
        self.debug_event_log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.debug_event_log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_event_log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.debug_event_log_view.setPlaceholderText("Debug events will appear here.")
        log_group_layout.addWidget(self.debug_event_log_view)
        self.debug_call_stack_group = stack_group
        self.debug_variables_group = variables_group
        self.debug_watch_group = watch_group
        self.debug_event_log_group = log_group

        self.debug_workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.debug_workspace_splitter.setObjectName("debugWorkspaceSplitter")
        self.debug_workspace_splitter.setChildrenCollapsible(False)
        self.debug_workspace_splitter.setHandleWidth(8)
        self.debug_workspace_splitter.addWidget(self.debug_variables_group)
        self.debug_workspace_splitter.addWidget(self.debug_watch_group)
        self.debug_workspace_splitter.addWidget(self.debug_call_stack_group)
        self.debug_workspace_splitter.addWidget(self.debug_event_log_group)
        self.debug_workspace_splitter.setStretchFactor(0, 1)
        self.debug_workspace_splitter.setStretchFactor(1, 1)
        self.debug_workspace_splitter.setStretchFactor(2, 1)
        self.debug_workspace_splitter.setStretchFactor(3, 1)
        self.debug_workspace_splitter.setMinimumWidth(220)
        self.debug_workspace_splitter.setSizes([120, 120, 120, 120])
        debug_layout.addWidget(self.debug_workspace_splitter, 1)
        self.debugger_panel.setStyleSheet(self._debug_sidebar_stylesheet())
        self._refresh_debug_tree_empty_states()

        self._build_debugger_controls_dialog()

        self.preview_view = QPlainTextEdit()
        self.preview_view.setReadOnly(True)
        self.preview_view.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.raw_recording_view = QPlainTextEdit()
        self.raw_recording_view.setReadOnly(True)
        self.raw_recording_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        self._build_ui()
        self.apply_preferences(self._preferences)
        self._load_go_to_dialog_state_from_settings()
        self._sync_diagnostics_log_surface()
        self.diagnosticEventReceived.connect(self._append_diagnostic_event)
        self._diagnostics_event_unsubscribe = subscribe_diagnostic_events(
            self.diagnosticEventReceived.emit
        )
        self.debugEventReceived.connect(self._append_debug_event)
        self.debugMessageReceived.connect(self._append_debug_message)
        self.debugSessionFinished.connect(self._on_debug_session_finished)
        self._update_workspace_tab_visibility()
        self._refresh_all_views()
        self._update_script_action_state()
        self._update_status("Ready")
        self._update_window_title()
        self._update_workspace_tab_labels()

        if initial_path is not None:
            self.load_script(initial_path)
        elif self.committed_settings_bundle.application.restore_last_workspace and self.committed_settings_bundle.application.last_workspace_path:
                last_path = Path(self.committed_settings_bundle.application.last_workspace_path)
                if last_path.exists():
                    self.load_script(last_path)

        window_log.info(
            "Desktop window initialized",
            event_id="desktop.window.started",
            current_path=str(self.current_path) if self.current_path is not None else None,
            editor_dirty=self._editor_dirty,
            settings_dirty=self._settings_dirty,
            restore_last_workspace=self.committed_settings_bundle.application.restore_last_workspace,
            show_formatted_preview_tab=self.committed_settings_bundle.application.show_formatted_preview_tab,
        )

    @property
    def committed_settings_bundle(self) -> DesktopSettingsBundle:
        return self._committed_settings_bundle

    @committed_settings_bundle.setter
    def committed_settings_bundle(self, value: DesktopSettingsBundle) -> None:
        self._committed_settings_bundle = value
        if hasattr(self, "hidden_workspace_tabs_strip_collapsed"):
            self.hidden_workspace_tabs_strip_collapsed = bool(
                value.application.hidden_workspace_tabs_strip_collapsed
            )
            self._update_hidden_workspace_tabs_strip()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 0, 8, 8)
        root_layout.setSpacing(0)

        self.sidebar_reopen_button = QToolButton()
        self.sidebar_reopen_button.setObjectName("sidebarReopenButton")
        self.sidebar_reopen_button.setAutoRaise(True)
        self.sidebar_reopen_button.setArrowType(Qt.ArrowType.RightArrow)
        self.sidebar_reopen_button.setIconSize(QSize(11, 11))
        self.sidebar_reopen_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.sidebar_reopen_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_reopen_button.setMinimumSize(18, 18)
        self.sidebar_reopen_button.setMaximumWidth(22)
        self.sidebar_reopen_button.setToolTip("Show the sidebar on the left")
        self.sidebar_reopen_button.setStatusTip("Show the sidebar on the left")
        self.sidebar_reopen_button.clicked.connect(
            lambda: self._set_sidebar_visible(True, user_initiated=True)
        )
        self.summary_sidebar_reopen_spacer = QWidget()
        self.summary_sidebar_reopen_spacer.setObjectName("summarySidebarReopenSpacer")
        self.summary_sidebar_reopen_spacer.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.summary_sidebar_reopen_spacer.setFixedWidth(260)
        self.summary_sidebar_reopen_spacer.setFixedHeight(1)
        self.summary_sidebar_reopen_strip = QWidget()
        self.summary_sidebar_reopen_strip.setObjectName("summarySidebarReopenStrip")
        summary_reopen_layout = QHBoxLayout(self.summary_sidebar_reopen_strip)
        summary_reopen_layout.setContentsMargins(0, 0, 0, 0)
        summary_reopen_layout.setSpacing(4)
        summary_reopen_layout.addWidget(self.summary_sidebar_reopen_spacer, 0)
        summary_reopen_layout.addWidget(self.sidebar_reopen_button, 0)
        summary_reopen_layout.addStretch(1)
        self.summary_sidebar_reopen_strip.setVisible(False)
        self.hidden_workspace_tabs_anchor_spacer = QWidget()
        self.hidden_workspace_tabs_anchor_spacer.setObjectName("hiddenWorkspaceTabsAnchorSpacer")
        self.hidden_workspace_tabs_anchor_spacer.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.hidden_workspace_tabs_anchor_spacer.setFixedWidth(0)
        self.hidden_workspace_tabs_anchor_spacer.setFixedHeight(1)
        self.hidden_workspace_tabs_strip = QWidget()
        self.hidden_workspace_tabs_strip.setObjectName("hiddenWorkspaceTabsStrip")
        hidden_tabs_layout = QHBoxLayout(self.hidden_workspace_tabs_strip)
        hidden_tabs_layout.setContentsMargins(0, 0, 0, 0)
        hidden_tabs_layout.setSpacing(2)
        self.hidden_workspace_tabs_strip_collapsed = bool(
            self.committed_settings_bundle.application.hidden_workspace_tabs_strip_collapsed
        )
        self.hidden_workspace_tabs_collapse_button = QToolButton()
        self.hidden_workspace_tabs_collapse_button.setObjectName("hiddenWorkspaceTabsCollapseButton")
        self.hidden_workspace_tabs_collapse_button.setAutoRaise(True)
        self.hidden_workspace_tabs_collapse_button.setArrowType(Qt.ArrowType.RightArrow)
        self.hidden_workspace_tabs_collapse_button.setIconSize(QSize(11, 11))
        self.hidden_workspace_tabs_collapse_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.hidden_workspace_tabs_collapse_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.hidden_workspace_tabs_collapse_button.setMinimumSize(12, 12)
        self.hidden_workspace_tabs_collapse_button.setMaximumWidth(14)
        self.hidden_workspace_tabs_collapse_button.setToolTip(
            "Hide the hidden tabs section"
        )
        self.hidden_workspace_tabs_collapse_button.setStatusTip(
            "Hide the hidden tabs section"
        )
        self.hidden_workspace_tabs_collapse_button.clicked.connect(
            lambda: self._set_hidden_workspace_tabs_strip_collapsed(True)
        )
        self.hidden_workspace_tabs_expand_button = QToolButton()
        self.hidden_workspace_tabs_expand_button.setObjectName("hiddenWorkspaceTabsExpandButton")
        self.hidden_workspace_tabs_expand_button.setAutoRaise(True)
        self.hidden_workspace_tabs_expand_button.setArrowType(Qt.ArrowType.LeftArrow)
        self.hidden_workspace_tabs_expand_button.setIconSize(QSize(11, 11))
        self.hidden_workspace_tabs_expand_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.hidden_workspace_tabs_expand_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.hidden_workspace_tabs_expand_button.setMinimumSize(12, 12)
        self.hidden_workspace_tabs_expand_button.setMaximumWidth(14)
        self.hidden_workspace_tabs_expand_button.setToolTip(
            "Show the hidden tabs section"
        )
        self.hidden_workspace_tabs_expand_button.setStatusTip(
            "Show the hidden tabs section"
        )
        self.hidden_workspace_tabs_expand_button.clicked.connect(
            lambda: self._set_hidden_workspace_tabs_strip_collapsed(False)
        )
        hidden_tabs_layout.addWidget(self.hidden_workspace_tabs_anchor_spacer, 0)
        hidden_tabs_layout.addWidget(self.hidden_workspace_tabs_collapse_button, 0)
        self.hidden_workspace_tabs_label = QLabel("Hidden tabs:")
        self.hidden_workspace_tabs_label.setObjectName("hiddenWorkspaceTabsLabel")
        hidden_tabs_layout.addWidget(self.hidden_workspace_tabs_label, 0)
        self.hidden_workspace_tabs_buttons_host = QWidget()
        self.hidden_workspace_tabs_buttons_host.setObjectName("hiddenWorkspaceTabsButtonsHost")
        self.hidden_workspace_tabs_buttons_layout = QHBoxLayout(
            self.hidden_workspace_tabs_buttons_host
        )
        self.hidden_workspace_tabs_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.hidden_workspace_tabs_buttons_layout.setSpacing(2)
        hidden_tabs_layout.addWidget(self.hidden_workspace_tabs_buttons_host, 1)
        hidden_tabs_layout.addStretch(1)
        hidden_tabs_layout.addWidget(self.hidden_workspace_tabs_expand_button, 0)
        self.hidden_workspace_tabs_expand_button.setVisible(False)
        self.hidden_workspace_tabs_strip.setFixedHeight(14)
        self.hidden_workspace_tabs_strip.setVisible(False)
        self.top_controls_strip = QWidget()
        self.top_controls_strip.setObjectName("topControlsStrip")
        top_controls_layout = QHBoxLayout(self.top_controls_strip)
        top_controls_layout.setContentsMargins(0, 0, 0, 0)
        top_controls_layout.setSpacing(4)
        top_controls_layout.addWidget(self.summary_sidebar_reopen_strip, 0)
        top_controls_layout.addWidget(self.hidden_workspace_tabs_strip, 1)

        self.workspace_tabs = QTabWidget()
        self._workspace_tab_bar = WorkspaceAttentionTabBar(self.workspace_tabs)
        self.workspace_tabs.setTabBar(self._workspace_tab_bar)
        self.workspace_tabs.addTab(self.editor, "Editor")
        self.workspace_tabs.addTab(self.playback_output_view, "Playback Output")
        self.workspace_tabs.addTab(self.analysis_workspace_tab, "Analysis")
        self.workspace_tabs.addTab(self.preview_view, "Formatted Preview")
        self.workspace_tabs.addTab(self.raw_recording_view, "Raw Recordings")
        self.workspace_tabs.addTab(self.diagnostics_tab, "Diagnostics")
        self.workspace_tabs.currentChanged.connect(self._on_workspace_tab_changed)
        self.workspace_tabs.setTabsClosable(True)
        self.workspace_tabs.tabCloseRequested.connect(self._handle_workspace_tab_close_requested)
        self._configure_workspace_tab_close_buttons()
        self._sync_workspace_tab_attention_colors()
        root_layout.addWidget(self.top_controls_strip)
        root_layout.addWidget(self.workspace_tabs)
        self.setCentralWidget(central)

        self.summary_view.setMinimumWidth(0)

        self.sidebar_shell = self._build_sidebar_shell()

        self.summary_dock = QDockWidget("Sidebar", self)
        self.summary_dock.setObjectName("summarySidebarDock")
        self.summary_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.summary_dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.summary_dock.setWidget(self.sidebar_shell)
        self.sidebar_toolbar_button = QToolButton()
        self.sidebar_toolbar_button.setAutoRaise(True)
        self.sidebar_toolbar_button.setCheckable(True)
        self.sidebar_toolbar_button.setChecked(True)
        self.sidebar_toolbar_button.setToolTip("Hide the sidebar on the left")
        self.sidebar_toolbar_button.setStatusTip("Hide the sidebar on the left")
        self.sidebar_toolbar_button.clicked.connect(
            lambda checked=False: self._set_sidebar_visible(
                bool(checked),
                user_initiated=True,
            )
        )
        self.summary_dock.visibilityChanged.connect(
            self.sidebar_toolbar_button.setChecked
        )
        self.summary_dock.visibilityChanged.connect(
            self._update_sidebar_reopen_visibility
        )
        self.summary_dock.visibilityChanged.connect(
            self._update_hidden_workspace_tabs_alignment
        )
        self._update_sidebar_toolbar_icon(True)
        self.sidebar_toolbar_button.toggled.connect(
            self._update_sidebar_toolbar_icon
        )
        self.sidebar_title_bar = self._build_sidebar_title_bar()
        self.summary_dock.setTitleBarWidget(self.sidebar_title_bar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.summary_dock)
        self.resizeDocks([self.summary_dock], [260], Qt.Orientation.Horizontal)
        self.sidebar_action = QAction("Left Sidebar", self)
        self.sidebar_action.triggered.connect(self._toggle_sidebar)
        self.summary_dock.visibilityChanged.connect(self._update_sidebar_action_label)
        self._update_sidebar_action_label(True)
        self.sidebar_dock = self.summary_dock
        self.summary_sidebar_action = self.sidebar_action
        self.summary_sidebar_toolbar_button = self.sidebar_toolbar_button
        self.summary_sidebar_reopen_button = self.sidebar_reopen_button
        self.summary_sidebar_title_bar = self.sidebar_title_bar
        self.hidden_workspace_tabs_action = QAction("", self)
        self.hidden_workspace_tabs_action.triggered.connect(
            self._toggle_hidden_workspace_tabs_strip
        )
        self._update_hidden_workspace_tabs_alignment()
        self._update_hidden_workspace_tabs_strip()

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self._editor_status_label = self._build_status_detail_label("Lines: 0 | Ln: 1 | Col: 1 | Ch: 1")
        self._events_status_label = self._build_status_detail_label("Events: 0")
        self._recording_playback_indicator = self._build_activity_indicator()
        status_bar.addPermanentWidget(self._editor_status_label)
        status_bar.addPermanentWidget(self._events_status_label)
        status_bar.addPermanentWidget(self._recording_playback_indicator)

        self._build_menus()
        self._build_toolbar()
        self._bind_script_controller()
        self._update_sidebar_reopen_visibility(True)
        self._apply_sidebar_visibility()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_sidebar_visibility()
        self._update_sidebar_reopen_alignment()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        tree = getattr(self, "search_results_tree", None)
        if tree is not None and obj is tree.viewport() and event.type() == QEvent.Type.Leave:
            if self._search_results_hover_top_item is not None:
                self._search_results_hover_top_item = None
                self._refresh_all_search_group_headers()
        title_bar = getattr(self, "debugger_controls_title_bar", None)
        dialog = getattr(self, "debugger_controls_dialog", None)
        if title_bar is not None and dialog is not None and obj is title_bar:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._debug_controls_drag_offset = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
                title_bar.setCursor(Qt.CursorShape.ClosedHandCursor)
                return True
            if (
                event.type() == QEvent.Type.MouseMove
                and getattr(self, "_debug_controls_drag_offset", None) is not None
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                drag_offset = getattr(self, "_debug_controls_drag_offset")
                dialog.move(event.globalPosition().toPoint() - drag_offset)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and getattr(self, "_debug_controls_drag_offset", None) is not None:
                self._debug_controls_drag_offset = None
                title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
                return True
        return super().eventFilter(obj, event)

    def _apply_sidebar_visibility(self) -> None:
        if not hasattr(self, "summary_dock"):
            return

        enabled = bool(self.committed_settings_bundle.application.show_summary_sidebar_on_left)
        if not enabled:
            self._sidebar_auto_hidden = False
            self._sidebar_user_hidden = False
            self._summary_sidebar_auto_hidden = self._sidebar_auto_hidden
            self._summary_sidebar_user_hidden = self._sidebar_user_hidden
            if self.summary_dock.isVisible():
                self.summary_dock.hide()
            self._update_sidebar_reopen_visibility(self.summary_dock.isVisible())
            return

        available_width = self.width()
        if available_width <= 0:
            return

        if available_width < 1100:
            if self.summary_dock.isVisible():
                self._set_sidebar_visible(False, auto_hidden=True)
        else:
            if not self._sidebar_user_hidden and not self.summary_dock.isVisible():
                self.summary_dock.show()
            self._sidebar_auto_hidden = False
            self._summary_sidebar_auto_hidden = self._sidebar_auto_hidden

        self._update_sidebar_reopen_visibility(self.summary_dock.isVisible())
        self._update_sidebar_reopen_alignment()

    def _update_sidebar_reopen_visibility(self, visible: bool) -> None:
        if hasattr(self, "summary_sidebar_reopen_strip"):
            self.summary_sidebar_reopen_strip.setVisible(not visible)
        self._update_sidebar_reopen_alignment()

    def _update_sidebar_reopen_alignment(self) -> None:
        if not hasattr(self, "summary_sidebar_reopen_spacer"):
            return

        if hasattr(self, "summary_dock") and self.summary_dock.isVisible():
            current_width = self.summary_dock.width()
            if current_width > 0:
                self._summary_sidebar_last_visible_width = current_width
            width = getattr(self, "_summary_sidebar_last_visible_width", 260)
        else:
            width = 0
        self.summary_sidebar_reopen_spacer.setFixedWidth(max(width, 0))
        self._update_hidden_workspace_tabs_alignment()

    def _update_hidden_workspace_tabs_alignment(self) -> None:
        if not hasattr(self, "hidden_workspace_tabs_anchor_spacer"):
            return

        self.hidden_workspace_tabs_anchor_spacer.setFixedWidth(0)

    def _set_sidebar_visible(
        self,
        visible: bool,
        *,
        user_initiated: bool = False,
        auto_hidden: bool = False,
    ) -> None:
        if not hasattr(self, "summary_dock"):
            return

        if visible:
            self._sidebar_auto_hidden = False
            if user_initiated:
                self._sidebar_user_hidden = False
        else:
            if user_initiated:
                self._sidebar_user_hidden = True
                self._sidebar_auto_hidden = False
            else:
                self._sidebar_auto_hidden = auto_hidden

        self._summary_sidebar_auto_hidden = self._sidebar_auto_hidden
        self._summary_sidebar_user_hidden = self._sidebar_user_hidden

        self.summary_dock.setVisible(visible)
        self._update_sidebar_reopen_alignment()

    def _toggle_sidebar(self) -> None:
        self._set_sidebar_visible(not self.summary_dock.isVisible(), user_initiated=True)

    def _request_sidebar(
        self,
        mode: str,
        *,
        toggle_if_current: bool = False,
        user_initiated: bool = True,
        auto_hidden: bool = False,
    ) -> bool:
        if not hasattr(self, "summary_dock"):
            return False
        if toggle_if_current and self._current_sidebar_mode == mode and self.summary_dock.isVisible():
            self._set_sidebar_visible(False, user_initiated=user_initiated)
            return False
        if not self.summary_dock.isVisible():
            self._set_sidebar_visible(
                True,
                user_initiated=user_initiated,
                auto_hidden=auto_hidden,
            )
        self._set_sidebar_mode(mode)
        self.summary_dock.raise_()
        return True

    def _update_sidebar_action_label(self, visible: bool) -> None:
        self.sidebar_action.setText("Left Sidebar")
        self.sidebar_action.setIcon(
            self._file_action_icon("msc.chevron-left" if visible else "msc.chevron-right")
        )
        self.sidebar_action.setToolTip(
            "Hide the left sidebar" if visible else "Show the left sidebar"
        )
        self.sidebar_action.setStatusTip(
            "Hide the left sidebar" if visible else "Show the left sidebar"
        )

    def _toggle_hidden_workspace_tabs_strip(self) -> None:
        if not hasattr(self, "hidden_workspace_tabs_strip_collapsed"):
            return
        self._set_hidden_workspace_tabs_strip_collapsed(
            not self.hidden_workspace_tabs_strip_collapsed
        )

    def _update_hidden_workspace_tabs_action_label(
        self,
        has_hidden_tabs: bool,
        collapsed: bool,
    ) -> None:
        if not hasattr(self, "hidden_workspace_tabs_action"):
            return

        if has_hidden_tabs and not collapsed:
            self.hidden_workspace_tabs_action.setText("Hide Hidden Tab Selections")
            self.hidden_workspace_tabs_action.setIcon(
                self._file_action_icon("msc.chevron-left")
            )
            self.hidden_workspace_tabs_action.setToolTip(
                "Hide the hidden tab selections"
            )
            self.hidden_workspace_tabs_action.setStatusTip(
                "Hide the hidden tab selections"
            )
        else:
            self.hidden_workspace_tabs_action.setText("Show Hidden Tab Selections")
            self.hidden_workspace_tabs_action.setIcon(
                self._file_action_icon("msc.chevron-right")
            )
            self.hidden_workspace_tabs_action.setToolTip(
                "Show the hidden tab selections"
            )
            self.hidden_workspace_tabs_action.setStatusTip(
                "Show the hidden tab selections"
            )
        self.hidden_workspace_tabs_action.setEnabled(has_hidden_tabs)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)

        self.search_menu = self.menuBar().addMenu("&Search")
        self.search_menu.addAction(self.find_action)
        self.search_menu.addAction(self.find_next_action)
        self.search_menu.addAction(self.find_previous_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.select_and_find_next_action)
        self.search_menu.addAction(self.select_and_find_previous_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.replace_action)
        self.search_menu.addAction(self.replace_current_action)
        self.search_menu.addAction(self.replace_all_action)
        self.search_menu.addAction(self.go_to_action)

        self.view_menu = self.menuBar().addMenu("&View")
        self.view_menu.addAction(self.analyze_action)
        self.view_menu.addAction(self.preview_action)
        self.view_menu.addAction(self.document_status_action)
        self.view_menu.addAction(self.summary_sidebar_action)
        self.view_menu.addAction(self.hidden_workspace_tabs_action)

        self.script_menu = self.menuBar().addMenu("&Script")
        self.script_menu.addAction(self.preview_play_script_action)
        self.script_menu.addAction(self.play_script_action)
        self.script_menu.addAction(self.record_script_action)
        self.script_menu.addAction(self.stop_script_action)

        self.debug_menu = self.menuBar().addMenu("&Debug")
        self.debug_menu.addAction(self.view_debugger_tab_action)
        self.debug_menu.addAction(self.run_debug_menu_action)
        self.debug_menu.addAction(self.debug_continue_action)
        self.debug_menu.addAction(self.debug_pause_action)
        self.debug_menu.addAction(self.restart_debug_menu_action)
        self.debug_menu.addAction(self.debug_stop_action)
        self.debug_menu.addSeparator()
        self.debug_menu.addAction(self.toggle_breakpoint_action)
        self.debug_menu.addAction(self.clear_breakpoints_action)
        self.debug_menu.addSeparator()
        self.debug_menu.addAction(self.debug_step_into_action)
        self.debug_menu.addAction(self.debug_step_over_action)
        self.debug_menu.addAction(self.debug_step_out_action)

        self.tools_menu = self.menuBar().addMenu("&Tools")
        self.tools_menu.addAction(self.pixel_inspector_action)

        settings_menu = self.menuBar().addMenu("&Settings")
        settings_menu.addAction(self.preferences_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.documentation_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

    def find_in_editor(self) -> None:
        self._request_sidebar("find")
        self._activate_find_sidebar_tab("find", focus=True)

    def _find_sidebar_find_previous(self) -> None:
        widgets = self._find_sidebar_widgets
        if widgets is None:
            return
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._request_sidebar("find")
            self._activate_find_sidebar_tab("find")
            self._set_find_sidebar_status("Enter text to find.")
            return
        search_criteria = replace(criteria, backward=True)
        result, message = self._find_next_from_criteria(search_criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._sync_find_results_tree_to_current_match(criteria, result)
        self._set_find_sidebar_status(message)
        if result.found:
            self.editor.setFocus()
        self._update_status(message)

    def find_next_in_editor(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._request_sidebar("find")
            self._activate_find_sidebar_tab("find")
            self._set_find_sidebar_status("Enter text to find.")
            return
        result, message = self._find_next_from_criteria(criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._sync_find_results_tree_to_current_match(criteria, result)
        self._set_find_sidebar_status(message)
        if result.found:
            self.editor.setFocus()
        self._update_status(message)

    def find_previous_in_editor(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._request_sidebar("find")
            self._activate_find_sidebar_tab("find")
            self._set_find_sidebar_status("Enter text to find.")
            return
        search_criteria = replace(criteria, backward=True)
        result, message = self._find_next_from_criteria(search_criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._sync_find_results_tree_to_current_match(criteria, result)
        self._set_find_sidebar_status(message)
        if result.found:
            self.editor.setFocus()
        self._update_status(message)

    def select_and_find_next_in_editor(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._request_sidebar("find")
            self._activate_find_sidebar_tab("find")
            self._set_find_sidebar_status("Enter text to find.")
            return
        criteria.in_selection = True
        result, message = self._find_next_from_criteria(criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._sync_find_results_tree_to_current_match(criteria, result)
        self._set_find_sidebar_status(message)
        if result.found:
            self.editor.setFocus()
        self._update_status(message)

    def select_and_find_previous_in_editor(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._request_sidebar("find")
            self._activate_find_sidebar_tab("find")
            self._set_find_sidebar_status("Enter text to find.")
            return
        criteria.in_selection = True
        search_criteria = replace(criteria, backward=True)
        result, message = self._find_next_from_criteria(search_criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._sync_find_results_tree_to_current_match(criteria, result)
        self._set_find_sidebar_status(message)
        if result.found:
            self.editor.setFocus()
        self._update_status(message)

    def replace_in_editor(self) -> None:
        self._request_sidebar("find")
        self._activate_find_sidebar_tab("replace", focus=True)

    def show_go_to_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Go to")
        dialog.setModal(True)
        dialog.setObjectName("goToDialog")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        if self._go_to_last_geometry is not None:
            dialog.restoreGeometry(self._go_to_last_geometry)

        current_line = self.editor.currentLineNumber()
        line_count = self.editor.blockCount()
        current_offset = self.editor.textCursor().position()
        max_offset = max(0, self.editor.document().characterCount() - 1)

        info_label = QLabel(
            f"Current line: {current_line} of {line_count} | Current offset: {current_offset} of {max_offset}"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("goToInfoLabel")
        layout.addWidget(info_label)

        mode_group = QButtonGroup(dialog)
        mode_group.setExclusive(True)
        line_mode_button = QRadioButton("Line")
        line_mode_button.setChecked(True)
        line_mode_button.setObjectName("goToLineModeButton")
        offset_mode_button = QRadioButton("Offset")
        offset_mode_button.setObjectName("goToOffsetModeButton")
        mode_group.addButton(line_mode_button)
        mode_group.addButton(offset_mode_button)

        mode_row = QHBoxLayout()
        mode_row.addWidget(line_mode_button)
        mode_row.addWidget(offset_mode_button)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        go_to_spin = QSpinBox()
        go_to_spin.setObjectName("goToSpinBox")
        go_to_spin.setMinimum(1)
        go_to_spin.setMaximum(max(1, line_count))
        go_to_spin.setValue(current_line)
        go_to_spin.setKeyboardTracking(False)
        go_to_label = QLabel("Line number")
        go_to_label.setObjectName("goToModeLabel")

        def update_go_to_mode(is_line_mode: bool, *, preserve_value: bool = False) -> None:
            if is_line_mode:
                go_to_label.setText("Line number")
                go_to_spin.setMinimum(1)
                go_to_spin.setMaximum(max(1, line_count))
                if not preserve_value:
                    go_to_spin.setValue(min(max(1, current_line), max(1, line_count)))
            else:
                go_to_label.setText("Offset")
                go_to_spin.setMinimum(0)
                go_to_spin.setMaximum(max_offset)
                if not preserve_value:
                    go_to_spin.setValue(min(max(0, current_offset), max_offset))

        line_mode_button.toggled.connect(update_go_to_mode)
        if self._go_to_last_mode == "offset":
            offset_mode_button.setChecked(True)
            update_go_to_mode(False, preserve_value=True)
            go_to_spin.setValue(min(max(0, self._go_to_last_value), max_offset))
        else:
            line_mode_button.setChecked(True)
            update_go_to_mode(True, preserve_value=True)
            go_to_spin.setValue(min(max(1, self._go_to_last_value), max(1, line_count)))

        form = QFormLayout()
        form.addRow("Go to:", go_to_spin)
        form.addRow("", go_to_label)
        limit_label = QLabel(
            f"Line mode cannot exceed {line_count} lines. Offset mode cannot exceed {max_offset}."
        )
        limit_label.setObjectName("goToLimitLabel")
        form.addRow("Limit:", limit_label)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        result = dialog.exec()
        self._go_to_last_geometry = dialog.saveGeometry()
        if result != QDialog.DialogCode.Accepted:
            self._persist_go_to_dialog_state(save_mode_value=False)
            return

        if line_mode_button.isChecked():
            self._go_to_last_mode = "line"
            self._go_to_last_value = go_to_spin.value()
            self._go_to_line(go_to_spin.value())
        else:
            self._go_to_last_mode = "offset"
            self._go_to_last_value = go_to_spin.value()
            self._go_to_offset(go_to_spin.value())
        self._persist_go_to_dialog_state(save_mode_value=True)

    def _go_to_line(self, line_number: int) -> None:
        line_number = max(1, min(int(line_number), self.editor.blockCount()))
        cursor = self.editor.textCursor()
        block = self.editor.document().findBlockByNumber(line_number - 1)
        if not block.isValid():
            return
        cursor.setPosition(block.position())
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _go_to_offset(self, offset: int) -> None:
        offset = max(0, min(int(offset), max(0, self.editor.document().characterCount() - 1)))
        cursor = self.editor.textCursor()
        cursor.setPosition(offset)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _load_go_to_dialog_state_from_settings(self) -> None:
        application = self.committed_settings_bundle.application
        self._go_to_last_mode = application.go_to_last_mode if application.go_to_last_mode in {"line", "offset"} else "line"
        if self._go_to_last_mode == "offset":
            self._go_to_last_value = max(0, int(application.go_to_last_value))
        else:
            self._go_to_last_value = max(1, int(application.go_to_last_value))
        self._go_to_last_geometry = self._decode_go_to_geometry(application.go_to_last_geometry)

    def _persist_go_to_dialog_state(self, *, save_mode_value: bool) -> None:
        application = self.committed_settings_bundle.application
        application.go_to_last_geometry = self._encode_go_to_geometry(self._go_to_last_geometry)
        if save_mode_value:
            application.go_to_last_mode = self._go_to_last_mode
            application.go_to_last_value = self._go_to_last_value
        try:
            self._settings_service.save(copy.deepcopy(self.committed_settings_bundle), force=True)
        except Exception as exc:
            preferences_log.exception(
                "Go to dialog state save failed",
                exc,
                event_id="desktop.preferences.go_to_state_save_failed",
            )

    def _encode_go_to_geometry(self, geometry: QByteArray | None) -> str | None:
        if geometry is None or geometry.isEmpty():
            return None
        return base64.b64encode(geometry.data()).decode("ascii")

    def _decode_go_to_geometry(self, geometry_text: str | None) -> QByteArray | None:
        if not geometry_text:
            return None
        try:
            return QByteArray.fromBase64(geometry_text.encode("ascii"))
        except (ValueError, UnicodeError):
            return None

    def _combo_text(self, combo: QComboBox) -> str:
        line_edit = combo.lineEdit()
        if line_edit is not None:
            return line_edit.text()
        return combo.currentText()

    def _set_combo_history(self, combo: QComboBox, history: list[str], current_text: str) -> None:
        combo.blockSignals(True)
        try:
            combo.clear()
            for item in history[:10]:
                combo.addItem(item)
            if current_text and current_text not in history[:10]:
                combo.insertItem(0, current_text)
                while combo.count() > 10:
                    combo.removeItem(combo.count() - 1)
        finally:
            combo.blockSignals(False)
        line_edit = combo.lineEdit()
        if line_edit is not None:
            line_edit.setText(current_text)

    def _sync_find_sidebar_widgets(self, widgets: SearchSidebarWidgets | None = None) -> None:
        widgets = widgets or self._find_sidebar_widgets
        if widgets is None:
            return
        for tab_name, page in widgets.pages.items():
            tab_criteria = self._search_criteria if self._search_criteria.active_tab == tab_name else replace(self._search_criteria, active_tab=tab_name)
            self._set_combo_history(page.find_combo, self._recent_find_terms, tab_criteria.find_text)
            if page.replace_combo is not None:
                self._set_combo_history(page.replace_combo, self._recent_replace_terms, tab_criteria.replace_text)
            page.backward_check.setChecked(tab_criteria.backward)
            page.whole_word_check.setChecked(tab_criteria.whole_word)
            page.match_case_check.setChecked(tab_criteria.match_case)
            page.wrap_check.setChecked(tab_criteria.wrap_around)
            page.selection_check.setChecked(tab_criteria.in_selection)
            page.normal_radio.setChecked(tab_criteria.search_mode == "normal")
            page.extended_radio.setChecked(tab_criteria.search_mode == "extended")
            page.regex_radio.setChecked(tab_criteria.search_mode == "regex")
            page.regex_newline_check.setEnabled(page.regex_radio.isChecked())
            page.regex_newline_check.setChecked(tab_criteria.regex_matches_newline)
        self._update_search_action_affordances()

    def _capture_find_sidebar_criteria(self) -> SearchCriteria:
        widgets = self._find_sidebar_widgets
        if widgets is None:
            return replace(self._search_criteria)
        current_tab = "replace" if widgets.tab_widget.currentIndex() == 1 else "find"
        page = widgets.pages[current_tab]
        criteria = replace(self._search_criteria, active_tab=current_tab)
        criteria.find_text = self._combo_text(page.find_combo).strip()
        if page.replace_combo is not None:
            criteria.replace_text = self._combo_text(page.replace_combo).strip()
        criteria.backward = page.backward_check.isChecked()
        criteria.whole_word = page.whole_word_check.isChecked()
        criteria.match_case = page.match_case_check.isChecked()
        criteria.wrap_around = page.wrap_check.isChecked()
        criteria.in_selection = page.selection_check.isChecked()
        if page.extended_radio.isChecked():
            criteria.search_mode = "extended"
        elif page.regex_radio.isChecked():
            criteria.search_mode = "regex"
        else:
            criteria.search_mode = "normal"
        criteria.regex_matches_newline = page.regex_newline_check.isChecked()
        return criteria

    def _set_find_sidebar_status(self, text: str) -> None:
        widgets = self._find_sidebar_widgets
        if widgets is not None:
            widgets.status_label.setText(text)

    def _update_find_sidebar_results_state(self, text: str) -> None:
        self._set_find_sidebar_status(text)
        self._update_status(text)

    def _replace_text_in_range(self, start: int, end: int, replacement_text: str) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        cursor = QTextCursor(self.editor.document())
        cursor.beginEditBlock()
        try:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(replacement_text)
        finally:
            cursor.endEditBlock()
        self.editor.setTextCursor(cursor)

    def _on_find_sidebar_tab_changed(self, index: int) -> None:
        widgets = self._find_sidebar_widgets
        if widgets is None:
            return
        tab_name = "replace" if index == 1 else "find"
        self._search_criteria = self._capture_find_sidebar_criteria()
        self._search_criteria.active_tab = tab_name
        self._sync_find_sidebar_widgets()
        if tab_name == "find":
            self._set_find_sidebar_status("Find text in the current editor.")
        else:
            self._set_find_sidebar_status("Replace text in the current editor.")
        self._update_search_action_affordances()

    def _activate_find_sidebar_tab(self, tab_name: str, *, focus: bool = False) -> None:
        widgets = self._find_sidebar_widgets
        if widgets is None:
            return
        index = 1 if tab_name == "replace" else 0
        widgets.tab_widget.blockSignals(True)
        try:
            widgets.tab_widget.setCurrentIndex(index)
        finally:
            widgets.tab_widget.blockSignals(False)
        self._on_find_sidebar_tab_changed(index)
        if not focus:
            return
        page = widgets.pages[tab_name]
        line_edit = page.find_combo.lineEdit()
        if line_edit is not None:
            line_edit.selectAll()
            line_edit.setFocus()
        else:
            page.find_combo.setFocus()

    def _show_find_sidebar_for_empty_query(
        self,
        tab_name: str,
        status_text: str,
        *,
        update_status: bool = False,
    ) -> None:
        self._request_sidebar("find")
        self._activate_find_sidebar_tab(tab_name)
        self._set_find_sidebar_status(status_text)
        if update_status:
            self._update_status(status_text)

    def _find_sidebar_count_matches(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._show_find_sidebar_for_empty_query(
                criteria.active_tab,
                "Enter text to find.",
                update_status=True,
            )
            return
        count, message = self._count_matches_from_criteria(criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._set_find_sidebar_status(message if count >= 0 else "No matches found.")
        self._update_status(message if count >= 0 else "No matches found.")

    def _find_sidebar_find_all(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._show_find_sidebar_for_empty_query(
                criteria.active_tab,
                "Enter text to find.",
                update_status=True,
            )
            return
        count, message = self._show_find_all_results_from_criteria(criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        self._set_find_sidebar_status(message if count >= 0 else "No matches found.")
        self._update_status(message if count >= 0 else "No matches found.")

    def _replace_sidebar_replace(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._show_find_sidebar_for_empty_query("replace", "Enter text to find.")
            return

        result, error_message = self._search_text_matches(criteria)
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        if error_message is not None:
            self._clear_search_results()
            self._update_find_sidebar_results_state(error_message)
            return
        if not result.found or result.start is None or result.end is None:
            self._clear_search_results()
            self._remember_search_term(criteria.find_text, self._recent_find_terms)
            self._remember_search_term(criteria.replace_text, self._recent_replace_terms)
            self._update_find_sidebar_results_state("No matches found.")
            return

        self._replace_text_in_range(result.start, result.end, criteria.replace_text)
        self._clear_search_results()
        self._remember_search_term(criteria.find_text, self._recent_find_terms)
        self._remember_search_term(criteria.replace_text, self._recent_replace_terms)
        message = "Replaced 1 match."
        self._update_find_sidebar_results_state(message)
        self.editor.setFocus()

    def _replace_sidebar_replace_all(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        if not criteria.find_text:
            self._show_find_sidebar_for_empty_query("replace", "Enter text to find.")
            return

        try:
            pattern, flags = self._compile_search_pattern(criteria)
        except ValueError as exc:
            self._search_criteria = criteria
            self._sync_find_sidebar_widgets()
            self._clear_search_results()
            self._update_find_sidebar_results_state(str(exc))
            return

        source_text = self.editor.toPlainText()
        range_start, range_end = self._find_all_search_range(criteria)
        scoped_text = source_text[range_start:range_end]
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            self._search_criteria = criteria
            self._sync_find_sidebar_widgets()
            self._clear_search_results()
            self._update_find_sidebar_results_state(f"Invalid regular expression: {exc}")
            return

        replaced_text, replacement_count = compiled.subn(
            lambda _match: criteria.replace_text,
            scoped_text,
        )
        self._search_criteria = criteria
        self._sync_find_sidebar_widgets()
        if replacement_count == 0:
            self._clear_search_results()
            self._remember_search_term(criteria.find_text, self._recent_find_terms)
            self._remember_search_term(criteria.replace_text, self._recent_replace_terms)
            self._update_find_sidebar_results_state("No matches found.")
            return

        self._replace_text_in_range(range_start, range_end, replaced_text)
        self._clear_search_results()
        self._remember_search_term(criteria.find_text, self._recent_find_terms)
        self._remember_search_term(criteria.replace_text, self._recent_replace_terms)
        message = f"Replaced {replacement_count} matches."
        self._update_find_sidebar_results_state(message)
        self.editor.setFocus()

    def _set_recent_search_terms(self, terms: list[str]) -> None:
        self._recent_find_terms = list(terms[:10])

    def _remember_search_term(self, search_text: str, history: list[str]) -> None:
        cleaned = search_text.strip()
        if not cleaned:
            return
        if cleaned in history:
            history.remove(cleaned)
        history.insert(0, cleaned)
        del history[10:]

    def _find_next_from_criteria(self, criteria: SearchCriteria) -> tuple[SearchResult, str]:
        result, error_message = self._search_text_matches(criteria)
        if error_message is not None:
            return SearchResult(found=False, count=0), error_message
        if result.count == 0:
            return result, "No matches found."
        if result.start is None or result.end is None:
            return result, "No matches found."
        self._select_text_range(result.start, result.end)
        self._remember_search_term(criteria.find_text, self._recent_find_terms)
        message = f"Match {result.index + 1} of {result.count}" if result.index is not None else f"{result.count} matches"
        return result, message

    def _count_matches_from_criteria(self, criteria: SearchCriteria) -> tuple[int, str]:
        result, error_message = self._search_text_matches(criteria, count_only=True)
        if error_message is not None:
            return 0, error_message
        self._remember_search_term(criteria.find_text, self._recent_find_terms)
        if result.count == 0:
            return 0, "No matches found."
        return result.count, f"Count: {result.count} matches"

    def _show_find_all_results_from_criteria(self, criteria: SearchCriteria) -> tuple[int, str]:
        matches, error_message = self._find_all_matches_from_criteria(criteria)
        if error_message is not None:
            self._clear_search_results()
            return 0, error_message
        self._remember_search_term(criteria.find_text, self._recent_find_terms)
        if not matches:
            self._clear_search_results()
            return 0, "No matches found."
        self._populate_search_results(criteria, matches)
        return len(matches), f"Find All: {len(matches)} matches shown in the sidebar."

    def _find_all_matches_from_criteria(
        self,
        criteria: SearchCriteria,
    ) -> tuple[list[SearchResult], str | None]:
        if not criteria.find_text.strip():
            return [], "Enter text to find."
        if criteria.in_selection and not self.editor.textCursor().hasSelection():
            return [], "Select text before searching within a selection."

        try:
            pattern, flags = self._compile_search_pattern(criteria)
        except ValueError as exc:
            return [], str(exc)

        source_text = self.editor.toPlainText()
        range_start, range_end = self._find_all_search_range(criteria)
        scoped_text = source_text[range_start:range_end]
        try:
            matches = list(re.finditer(pattern, scoped_text, flags))
        except re.error as exc:
            return [], f"Invalid regular expression: {exc}"
        if not matches:
            return [], None

        results = [
            SearchResult(
                found=True,
                count=len(matches),
                index=index,
                start=range_start + match.start(),
                end=range_start + match.end(),
            )
            for index, match in enumerate(matches)
        ]
        return results, None

    def _search_text_matches(
        self,
        criteria: SearchCriteria,
        *,
        count_only: bool = False,
    ) -> tuple[SearchResult, str | None]:
        if not criteria.find_text.strip():
            return SearchResult(found=False, count=0), "Enter text to find."
        if criteria.in_selection and not self.editor.textCursor().hasSelection():
            return SearchResult(found=False, count=0), "Select text before searching within a selection."

        try:
            pattern, flags = self._compile_search_pattern(criteria)
        except ValueError as exc:
            return SearchResult(found=False, count=0), str(exc)

        source_text = self.editor.toPlainText()
        range_start, range_end = (
            self._count_search_range(criteria) if count_only else self._search_range(criteria)
        )
        scoped_text = source_text[range_start:range_end]
        try:
            matches = list(re.finditer(pattern, scoped_text, flags))
        except re.error as exc:
            return SearchResult(found=False, count=0), f"Invalid regular expression: {exc}"
        if not matches:
            return SearchResult(found=False, count=0), None

        anchor = self._search_anchor(criteria, range_start, range_end)
        chosen = self._choose_match(matches, anchor, criteria.backward, criteria.wrap_around)
        if chosen is None:
            return SearchResult(found=False, count=len(matches)), "No matches found."

        start = range_start + chosen.start()
        end = range_start + chosen.end()
        return SearchResult(
            found=True,
            count=len(matches),
            index=matches.index(chosen),
            start=start,
            end=end,
        ), None

    def _compile_search_pattern(self, criteria: SearchCriteria) -> tuple[str, int]:
        query = criteria.find_text
        if criteria.search_mode == "extended":
            try:
                query = codecs.decode(query.encode("utf-8"), "unicode_escape")
            except UnicodeDecodeError as exc:
                raise ValueError("Extended search text contains an invalid escape sequence.") from exc
            except UnicodeEncodeError as exc:
                raise ValueError("Extended search text contains an invalid escape sequence.") from exc
        elif criteria.search_mode == "normal":
            query = re.escape(query)
        elif criteria.search_mode != "regex":
            raise ValueError("Unsupported search mode.")

        if criteria.whole_word:
            query = rf"\b(?:{query})\b"

        flags = 0 if criteria.match_case else re.IGNORECASE
        if criteria.search_mode == "regex" and criteria.regex_matches_newline:
            flags |= re.DOTALL
        return query, flags

    def _search_range(self, criteria: SearchCriteria) -> tuple[int, int]:
        cursor = self.editor.textCursor()
        if criteria.in_selection and cursor.hasSelection():
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            return start, end
        return 0, len(self.editor.toPlainText())

    def _find_all_search_range(self, criteria: SearchCriteria) -> tuple[int, int]:
        cursor = self.editor.textCursor()
        if criteria.in_selection and cursor.hasSelection():
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            return start, end
        return 0, len(self.editor.toPlainText())

    def _count_search_range(self, criteria: SearchCriteria) -> tuple[int, int]:
        text_length = len(self.editor.toPlainText())
        cursor = self.editor.textCursor()
        if criteria.in_selection and cursor.hasSelection():
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            return start, end
        if criteria.wrap_around:
            return 0, text_length
        anchor = max(0, min(cursor.position(), text_length))
        if criteria.backward:
            return 0, anchor
        return anchor, text_length

    def _search_anchor(self, criteria: SearchCriteria, range_start: int, range_end: int) -> int:
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            anchor = cursor.selectionStart() if criteria.backward else cursor.selectionEnd()
        else:
            anchor = cursor.position()
        return max(range_start, min(anchor, range_end))

    def _choose_match(
        self,
        matches: list[re.Match[str]],
        anchor: int,
        backward: bool,
        wrap_around: bool,
    ) -> re.Match[str] | None:
        if backward:
            for match in reversed(matches):
                if match.end() <= anchor:
                    return match
            return matches[-1] if wrap_around else None
        for match in matches:
            if match.start() >= anchor:
                return match
        return matches[0] if wrap_around else None

    def _select_text_range(self, start: int, end: int) -> None:
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _clear_search_results(self) -> None:
        self.search_results_tree.clear()
        self.search_results_summary_label.setText("Search results will appear here.")

    def _sync_find_results_tree_to_current_match(
        self,
        criteria: SearchCriteria,
        result: SearchResult,
    ) -> None:
        if not result.found or result.start is None or result.end is None:
            return
        if not self._search_results_match_criteria(criteria):
            return
        item = self._search_result_item_for_range(result.start, result.end)
        if item is None:
            return
        self._activate_search_result_item(item, 0)
        self.search_results_tree.scrollToItem(item)

    def _search_results_match_criteria(self, criteria: SearchCriteria) -> bool:
        return self._search_results_criteria_key(criteria) == self._search_results_criteria_key(
            self._search_results_last_criteria
        )

    def _search_results_criteria_key(self, criteria: SearchCriteria) -> tuple[object, ...]:
        return (
            criteria.find_text,
            criteria.whole_word,
            criteria.match_case,
            criteria.wrap_around,
            criteria.in_selection,
            criteria.search_mode,
            criteria.regex_matches_newline,
        )

    def _search_result_item_for_range(self, start: int, end: int) -> QTreeWidgetItem | None:
        for top_index in range(self.search_results_tree.topLevelItemCount()):
            top_item = self.search_results_tree.topLevelItem(top_index)
            if top_item is None:
                continue
            for child_index in range(top_item.childCount()):
                child_item = top_item.child(child_index)
                payload = child_item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(payload, dict) and payload.get("start") == start and payload.get("end") == end:
                    return child_item
        return None

    def _populate_search_results(self, criteria: SearchCriteria, matches: list[SearchResult]) -> None:
        self.search_results_tree.clear()
        search_text = criteria.find_text.strip()
        summary_text = f'Search "{search_text}" ({len(matches)} hits in 1 file)'
        self.search_results_summary_label.setText(summary_text)
        grouped_results = self._group_search_results_by_line(matches)
        for line_number in sorted(grouped_results):
            line_info = grouped_results[line_number]
            hit_count = len(line_info["matches"])
            top_item = QTreeWidgetItem([f"Line {line_number}"])
            top_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "line_number": line_number,
                    "line_text": line_info["line_text"],
                    "hit_count": hit_count,
                },
            )
            self.search_results_tree.addTopLevelItem(top_item)

            line_label = QLabel()
            line_label.setTextFormat(Qt.TextFormat.RichText)
            line_label.setWordWrap(True)
            line_label.setText(
                self._build_line_summary_html(
                    line_number,
                    line_info["line_text"],
                    hit_count,
                    active=False,
                    hovered=False,
                )
            )
            self.search_results_tree.setItemWidget(top_item, 0, line_label)

            for hit_index, match in enumerate(line_info["matches"], start=1):
                child_item = QTreeWidgetItem()
                child_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"start": match["start"], "end": match["end"]},
                )
                top_item.addChild(child_item)

                child_label = QLabel()
                child_label.setTextFormat(Qt.TextFormat.RichText)
                child_label.setWordWrap(True)
                child_label.setStyleSheet(self._search_result_child_style(depth=1))
                child_label.setText(
                    self._build_search_result_html(
                        hit_index=hit_index,
                        line_text=line_info["line_text"],
                        match_start=match["start"],
                        match_end=match["end"],
                        line_start=line_info["line_start"],
                    )
                )
                self.search_results_tree.setItemWidget(child_item, 0, child_label)

            top_item.setExpanded(False)
        first_top = self.search_results_tree.topLevelItem(0)
        if first_top is not None and first_top.childCount() > 0:
            self._activate_search_result_item(first_top.child(0), 0)
        self._search_results_last_criteria = replace(criteria)

    def _activate_search_result_item(self, item: QTreeWidgetItem, column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            parent = item.parent()
            if parent is not None and parent.childCount() > 0:
                first_child = parent.child(0)
                if first_child is not None:
                    self._expand_active_search_group(first_child)
                    self._activate_search_result_item(first_child, column)
            return
        if "line_number" in payload:
            if item.childCount() > 0:
                first_child = item.child(0)
                if first_child is not None:
                    self._expand_active_search_group(first_child)
                    self._activate_search_result_item(first_child, column)
            return
        self._expand_active_search_group(item)
        start = payload.get("start")
        end = payload.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            return
        self._select_text_range(start, end)

    def _expand_active_search_group(self, item: QTreeWidgetItem) -> None:
        top_item = item
        while top_item.parent() is not None:
            top_item = top_item.parent()
        for index in range(self.search_results_tree.topLevelItemCount()):
            current_top = self.search_results_tree.topLevelItem(index)
            if current_top is not None:
                current_top.setExpanded(current_top is top_item)
                self._refresh_search_group_header(
                    current_top,
                    active=current_top is top_item,
                    hovered=current_top is self._search_results_hover_top_item,
                )
        self.search_results_tree.setCurrentItem(item)

    def _refresh_search_group_header(
        self,
        top_item: QTreeWidgetItem,
        *,
        active: bool,
        hovered: bool,
    ) -> None:
        payload = top_item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        line_number = payload.get("line_number")
        line_text = payload.get("line_text")
        hit_count = payload.get("hit_count")
        if not isinstance(line_number, int) or not isinstance(line_text, str) or not isinstance(hit_count, int):
            return
        widget = self.search_results_tree.itemWidget(top_item, 0)
        if widget is None:
            return
        if isinstance(widget, QLabel):
            widget.setText(
                self._build_line_summary_html(
                    line_number,
                    line_text,
                    hit_count,
                    active=active,
                    hovered=hovered,
                )
            )

    def _handle_search_result_current_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        if current is None:
            return
        self._refresh_all_search_group_headers()

    def _handle_search_result_item_entered(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        top_item = item
        while top_item.parent() is not None:
            top_item = top_item.parent()
        if top_item is self._search_results_hover_top_item:
            return
        self._search_results_hover_top_item = top_item
        self._refresh_all_search_group_headers()

    def _refresh_all_search_group_headers(self) -> None:
        current_item = self.search_results_tree.currentItem()
        active_top = self._search_results_top_item(current_item)
        for index in range(self.search_results_tree.topLevelItemCount()):
            top_item = self.search_results_tree.topLevelItem(index)
            if top_item is not None:
                self._refresh_search_group_header(
                    top_item,
                    active=top_item is active_top,
                    hovered=top_item is self._search_results_hover_top_item,
                )

    def _search_results_top_item(self, item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
        if item is None:
            return None
        top_item = item
        while top_item.parent() is not None:
            top_item = top_item.parent()
        return top_item

    def _group_search_results_by_line(self, matches: list[SearchResult]) -> dict[int, dict[str, object]]:
        grouped: dict[int, dict[str, object]] = {}
        document = self.editor.document()
        source_text = self.editor.toPlainText()
        for match in matches:
            if match.start is None or match.end is None:
                continue
            block = document.findBlock(match.start)
            line_number = block.blockNumber() + 1 if block.isValid() else 1
            line_start = block.position() if block.isValid() else 0
            line_text = block.text() if block.isValid() else source_text[match.start:match.end]
            entry = grouped.setdefault(
                line_number,
                {
                    "line_start": line_start,
                    "line_text": line_text,
                    "matches": [],
                },
            )
            entry["matches"].append({"start": match.start, "end": match.end})
        return grouped

    def _build_search_result_html(
        self,
        *,
        hit_index: int,
        line_text: str,
        match_start: int,
        match_end: int,
        line_start: int,
    ) -> str:
        palette = self._search_results_theme()
        line_text = line_text.rstrip("\n")
        relative_start = max(0, match_start - line_start)
        relative_end = max(relative_start, match_end - line_start)
        prefix = html.escape(line_text[:relative_start])
        match_text = html.escape(line_text[relative_start:relative_end])
        suffix = html.escape(line_text[relative_end:])
        context_limit = 64
        if len(prefix) > context_limit:
            prefix = "…" + prefix[-context_limit:]
        if len(suffix) > context_limit:
            suffix = suffix[:context_limit] + "…"
        return (
            f'<span style="color:{palette.header_text};">{hit_index}.</span> '
            f'<span style="color:{palette.line_text}; padding-left:2px;">{prefix}</span>'
            f'<span style="background-color:#ffe08a; color:{palette.hit_text}; font-weight:600;">{match_text}</span>'
            f'<span style="color:{palette.line_text};">{suffix}</span>'
        )

    def _search_result_child_style(self, *, depth: int) -> str:
        palette = self._search_results_theme()
        indent = max(0, depth - 1) * 14
        return (
            f"border-left: {palette.child_border_width} solid {palette.child_border_color}; "
            f"padding-left: {palette.child_padding_left}px; "
            f"margin-left: {palette.child_margin_left + indent}px;"
        )

    def _search_results_theme(self) -> SearchResultsTheme:
        return self._preferences.search_results

    def _build_line_summary_html(
        self,
        line_number: int,
        line_text: str,
        hit_count: int,
        *,
        active: bool,
        hovered: bool,
    ) -> str:
        palette = self._search_results_theme()
        hit_label = "hit" if hit_count == 1 else "hits"
        if active and hovered:
            background = (
                f"background-color:{palette.header_active_hovered}; "
                f"border-radius:{palette.header_radius}; "
                f"padding:{palette.header_padding};"
            )
        elif active:
            background = (
                f"background-color:{palette.header_active}; "
                f"border-radius:{palette.header_radius}; "
                f"padding:{palette.header_padding};"
            )
        elif hovered:
            background = (
                f"background-color:{palette.header_hovered}; "
                f"border-radius:{palette.header_radius}; "
                f"padding:{palette.header_padding};"
            )
        else:
            background = ""
        return (
            f'<span style="color:{palette.header_text}; font-weight:600; {background}">Line {line_number}:</span> '
            f'<span style="color:{palette.line_text};">{html.escape(line_text)}</span> '
            f'<span style="color:{palette.hit_text};">({hit_count} {hit_label})</span>'
        )

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet(
            "QToolBar {"
            " spacing: 3px;"
            " padding: 0px;"
            " margin: 0px;"
            " }"
            "QToolBar::separator {"
            " width: 4px;"
            " margin: 0px 1px;"
            " }"
        )
        self.file_toolbar_group = self._build_file_toolbar_group()
        toolbar.addWidget(self.file_toolbar_group)
        toolbar.addSeparator()
        self.analysis_toolbar_group = self._build_analysis_toolbar_group()
        toolbar.addWidget(self.analysis_toolbar_group)
        toolbar.addSeparator()
        self.playback_toolbar_group = self._build_playback_toolbar_group()
        toolbar.addWidget(self.playback_toolbar_group)
        toolbar.addSeparator()
        self.debug_toolbar_group = self._build_debug_toolbar_group()
        toolbar.addWidget(self.debug_toolbar_group)
        toolbar.addSeparator()
        self.toolbar_right_spacer = self._build_toolbar_right_spacer()
        toolbar.addWidget(self.toolbar_right_spacer)
        self.settings_toolbar_group = self._build_settings_toolbar_group()
        toolbar.addWidget(self.settings_toolbar_group)
        self.main_toolbar = toolbar
        self.addToolBar(toolbar)

    def _update_sidebar_toolbar_icon(self, visible: bool) -> None:
        self.sidebar_toolbar_button.setArrowType(
            Qt.ArrowType.LeftArrow if visible else Qt.ArrowType.RightArrow
        )
        self.sidebar_toolbar_button.setToolTip(
            "Hide the sidebar on the left" if visible else "Show the sidebar on the left"
        )
        self.sidebar_toolbar_button.setStatusTip(
            "Hide the sidebar on the left" if visible else "Show the sidebar on the left"
        )
        self.sidebar_toolbar_button.setText("")

    def _build_playback_icon_font(self) -> IconicFont:
        fonts_directory = Path(qta.__file__).resolve().parent / "fonts"
        return IconicFont(
            (
                "mdi6",
                "materialdesignicons6-webfont-6.9.96.ttf",
                "materialdesignicons6-webfont-charmap-6.9.96.json",
                str(fonts_directory),
            )
        )

    def _build_file_icon_font(self) -> IconicFont:
        fonts_directory = Path(qta.__file__).resolve().parent / "fonts"
        return IconicFont(
            (
                "msc",
                "codicon-0.0.36.ttf",
                "codicon-charmap-0.0.36.json",
                str(fonts_directory),
            ),
            (
                "ph",
                "phosphor-1.3.0.ttf",
                "phosphor-charmap-1.3.0.json",
                str(fonts_directory),
            ),
        )

    def _build_playback_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("playbackToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._build_playback_toolbar_button(
            self.preview_play_script_action,
            "previewPlayScriptToolbarButton",
        ))
        layout.addWidget(self._build_playback_toolbar_button(
            self.play_script_action,
            "playScriptToolbarButton",
        ))
        layout.addWidget(self._build_playback_toolbar_button(
            self.record_script_action,
            "recordScriptToolbarButton",
        ))
        layout.addWidget(self._build_playback_toolbar_button(
            self.stop_script_action,
            "stopScriptToolbarButton",
        ))
        return group

    def _build_file_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("fileToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._build_file_toolbar_button(self.new_action, "newScriptToolbarButton"))
        layout.addWidget(self._build_file_toolbar_button(self.open_action, "openScriptToolbarButton"))
        layout.addWidget(self._build_file_toolbar_button(self.save_action, "saveScriptToolbarButton"))
        layout.addWidget(self._build_file_toolbar_button(self.save_as_action, "saveAsScriptToolbarButton"))
        layout.addWidget(self._build_file_toolbar_button(self.find_action, "searchScriptToolbarButton"))
        return group

    def _build_analysis_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("analysisToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._build_analysis_toolbar_button(self.analyze_action, "analyzeScriptToolbarButton"))
        layout.addWidget(self._build_analysis_toolbar_button(self.preview_action, "previewScriptToolbarButton"))
        return group

    def _build_debug_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("debugToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.debug_primary_toolbar_group = self._build_debug_primary_toolbar_group()
        layout.addWidget(self.debug_primary_toolbar_group)
        self.debug_primary_toolbar_separator = self._build_toolbar_separator("debugPrimaryToolbarSeparator")
        layout.addWidget(self.debug_primary_toolbar_separator)
        self.debug_breakpoint_toolbar_group = self._build_debug_breakpoint_toolbar_group()
        layout.addWidget(self.debug_breakpoint_toolbar_group)
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_step_into_action,
                "debugStepIntoToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_step_over_action,
                "debugStepOverToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_step_out_action,
                "debugStepOutToolbarButton",
            )
        )
        return group

    def _build_debug_breakpoint_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("debugBreakpointToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.toggle_breakpoint_action,
                "toggleBreakpointToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.clear_breakpoints_action,
                "clearBreakpointsScriptToolbarButton",
            )
        )
        layout.addWidget(self._build_toolbar_separator("debugBreakpointToolbarSeparator"))
        return group

    def _build_debug_primary_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("debugPrimaryToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.view_debugger_tab_action,
                "viewDebugTabToolbarButton",
            )
        )
        layout.addWidget(self._build_analysis_toolbar_button(self.debugger_action, "debugScriptToolbarButton"))
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_continue_action,
                "debugContinueToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_pause_action,
                "debugPauseToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_restart_action,
                "debugRestartToolbarButton",
            )
        )
        layout.addWidget(
            self._build_analysis_toolbar_button(
                self.debug_stop_action,
                "debugStopToolbarButton",
            )
        )
        return group

    def _build_settings_toolbar_group(self) -> QWidget:
        group = QWidget()
        group.setObjectName("settingsToolbarGroup")

        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(
            self._build_settings_toolbar_button(
                self.pixel_inspector_action,
                "pointerProbeScriptToolbarButton",
            )
        )
        layout.addWidget(
            self._build_settings_toolbar_button(
                self.preferences_action,
                "preferencesScriptToolbarButton",
            )
        )
        layout.addWidget(
            self._build_settings_toolbar_button(
                self.documentation_action,
                "documentationScriptToolbarButton",
            )
        )
        return group

    def _build_toolbar_right_spacer(self) -> QWidget:
        spacer = QWidget()
        spacer.setObjectName("toolbarRightSpacer")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setMinimumWidth(0)
        spacer.setMaximumWidth(16777215)
        return spacer

    def _build_sidebar_title_bar(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("sidebarTitleBar")

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(self._build_sidebar_toolbar_button())
        widget.setFixedHeight(14)
        return widget

    def _build_sidebar_toolbar_button(self) -> QToolButton:
        button = self.sidebar_toolbar_button
        button.setObjectName("sidebarToolbarButton")
        button.setAutoRaise(True)
        button.setIconSize(QSize(9, 9))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(12, 12)
        button.setMaximumWidth(14)
        button.setStyleSheet(self._sidebar_toolbar_button_stylesheet())
        return button

    def _build_sidebar_shell(self) -> QWidget:
        shell = QWidget()
        shell.setObjectName("sidebarShell")

        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        mode_rail = QWidget()
        mode_rail.setObjectName("sidebarModeRail")
        mode_rail.setFixedWidth(50)
        mode_rail_layout = QVBoxLayout(mode_rail)
        mode_rail_layout.setContentsMargins(6, 0, 6, 10)
        mode_rail_layout.setSpacing(8)
        mode_rail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.sidebar_mode_button_group = QButtonGroup(self)
        self.sidebar_mode_button_group.setExclusive(True)
        self.sidebar_mode_buttons: dict[str, QToolButton] = {}

        self.sidebar_mode_buttons["find"] = self._build_sidebar_mode_button(
            mode="find",
            text="Find",
            icon=self._sidebar_mode_icon("find"),
            enabled=True,
        )
        self.sidebar_mode_buttons["debug"] = self._build_sidebar_mode_button(
            mode="debug",
            text="Debugger",
            icon=self._sidebar_mode_icon("debug"),
            enabled=True,
        )
        self.sidebar_mode_buttons["analysis"] = self._build_sidebar_mode_button(
            mode="analysis",
            text="Analysis",
            icon=self._sidebar_mode_icon("analysis"),
            enabled=True,
        )
        for mode_name in ("find", "debug", "analysis"):
            mode_rail_layout.addWidget(self.sidebar_mode_buttons[mode_name])
        mode_rail_layout.addStretch(1)

        content_shell = QWidget()
        content_shell.setObjectName("sidebarModeContentShell")
        content_shell_layout = QVBoxLayout(content_shell)
        content_shell_layout.setContentsMargins(12, 0, 12, 10)
        content_shell_layout.setSpacing(6)

        self.sidebar_mode_title_label = QLabel("Debugger")
        self.sidebar_mode_title_label.setObjectName("sidebarModeTitleLabel")
        self.sidebar_mode_stack = QStackedWidget()
        self.sidebar_mode_stack.setObjectName("sidebarModeStack")

        self._find_sidebar_widgets = self._build_find_sidebar_page()
        self.sidebar_mode_pages: dict[str, QWidget] = {
            "find": self._find_sidebar_widgets.page,
            "debug": self.debugger_panel,
            "analysis": self._build_analysis_sidebar_page().page,
        }
        for mode_name in ("find", "debug", "analysis"):
            self.sidebar_mode_stack.addWidget(self.sidebar_mode_pages[mode_name])

        content_shell_layout.addWidget(self.sidebar_mode_title_label, 0)
        content_shell_layout.addWidget(self.sidebar_mode_stack, 1)

        shell_layout.addWidget(mode_rail)
        shell_layout.addWidget(content_shell, 1)
        shell.setStyleSheet(self._debug_sidebar_stylesheet())
        self._set_sidebar_mode("debug")
        return shell

    def _build_find_sidebar_page(self) -> SearchSidebarWidgets:
        page = QWidget()
        page.setObjectName("findSidebarPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        intro_label = QLabel("Search the current editor text without leaving the sidebar.")
        intro_label.setObjectName("findSidebarIntroLabel")
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("color: #666666;")
        layout.addWidget(intro_label)

        self._find_sidebar_tab_widget = QTabWidget(page)
        self._find_sidebar_tab_widget.setObjectName("findSidebarTabWidget")
        self._find_sidebar_pages = {
            "find": self._build_search_page("find"),
            "replace": self._build_search_page("replace"),
        }
        self._find_sidebar_tab_widget.addTab(self._find_sidebar_pages["find"].page, "Find")
        self._find_sidebar_tab_widget.addTab(self._find_sidebar_pages["replace"].page, "Replace")
        self._find_sidebar_tab_widget.currentChanged.connect(self._on_find_sidebar_tab_changed)
        layout.addWidget(self._find_sidebar_tab_widget)

        button_row = QWidget()
        button_row_layout = QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.setSpacing(4)
        find_previous_button = QPushButton("Previous")
        find_previous_button.setObjectName("findSidebarPreviousButton")
        find_previous_button.setCursor(Qt.CursorShape.PointingHandCursor)
        find_previous_button.clicked.connect(self._find_sidebar_find_previous)
        find_next_button = QPushButton("Next")
        find_next_button.setObjectName("findSidebarFindNextButton")
        find_next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        find_next_button.clicked.connect(self.find_next_in_editor)
        count_button = QPushButton("Count")
        count_button.setObjectName("findSidebarCountButton")
        count_button.setCursor(Qt.CursorShape.PointingHandCursor)
        count_button.clicked.connect(self._find_sidebar_count_matches)
        find_all_button = QPushButton("Find All")
        find_all_button.setObjectName("findSidebarFindAllButton")
        find_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        find_all_button.clicked.connect(self._find_sidebar_find_all)
        replace_button = self._find_sidebar_pages["replace"].replace_button
        replace_all_button = self._find_sidebar_pages["replace"].replace_all_button
        button_row_layout.addWidget(find_previous_button)
        button_row_layout.addWidget(find_next_button)
        button_row_layout.addWidget(count_button)
        button_row_layout.addWidget(find_all_button)
        button_row_layout.addStretch(1)
        layout.addWidget(button_row)

        results_group = QGroupBox("Results")
        results_group.setObjectName("findSidebarResultsGroup")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(8, 8, 8, 8)
        results_layout.setSpacing(6)
        results_summary_label = QLabel("Search results will appear here.")
        results_summary_label.setObjectName("searchResultsSummaryLabel")
        results_summary_label.setWordWrap(True)
        results_summary_label.setStyleSheet("color: #666666; font-size: 11px;")
        results_layout.addWidget(results_summary_label)
        results_tree = QTreeWidget()
        results_tree.setObjectName("searchResultsTree")
        results_tree.setHeaderHidden(True)
        results_tree.setAnimated(False)
        results_tree.setRootIsDecorated(True)
        results_tree.setMouseTracking(True)
        results_tree.viewport().setMouseTracking(True)
        results_tree.itemActivated.connect(self._activate_search_result_item)
        results_tree.itemClicked.connect(self._activate_search_result_item)
        results_tree.itemEntered.connect(self._handle_search_result_item_entered)
        results_tree.currentItemChanged.connect(self._handle_search_result_current_changed)
        results_tree.viewport().installEventFilter(self)
        results_layout.addWidget(results_tree, 1)
        layout.addWidget(results_group, 1)
        self.search_results_summary_label = results_summary_label
        self.search_results_tree = results_tree

        status_label = QLabel("Search results will be shown below in the sidebar.")
        status_label.setObjectName("findSidebarStatusLabel")
        status_label.setWordWrap(True)
        status_label.setMinimumHeight(36)
        status_label.setStyleSheet("color: #666666;")
        layout.addWidget(status_label)
        layout.addStretch(1)

        widgets = SearchSidebarWidgets(
            page=page,
            tab_widget=self._find_sidebar_tab_widget,
            pages=self._find_sidebar_pages,
            results_summary_label=results_summary_label,
            results_tree=results_tree,
            find_previous_button=find_previous_button,
            find_next_button=find_next_button,
            count_button=count_button,
            find_all_button=find_all_button,
            replace_button=replace_button,
            replace_all_button=replace_all_button,
            status_label=status_label,
        )
        self._sync_find_sidebar_widgets(widgets)
        return widgets

    def _build_search_page(self, tab_name: str) -> SearchPageWidgets:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        search_row = QFormLayout()
        find_combo = QComboBox()
        find_combo.setEditable(True)
        find_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        find_combo.setObjectName(f"findSidebar{tab_name.capitalize()}FindCombo")
        find_line_edit = find_combo.lineEdit()
        if find_line_edit is not None:
            find_line_edit.setPlaceholderText("Find text")
            find_line_edit.textChanged.connect(self._update_search_action_affordances)
        search_row.addRow("Find:", find_combo)

        replace_combo: QComboBox | None = None
        if tab_name == "replace":
            replace_combo = QComboBox()
            replace_combo.setEditable(True)
            replace_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            replace_combo.setObjectName("findSidebarReplaceReplaceCombo")
            replace_line_edit = replace_combo.lineEdit()
            if replace_line_edit is not None:
                replace_line_edit.setPlaceholderText("Replace text")
                replace_line_edit.textChanged.connect(self._update_search_action_affordances)
            search_row.addRow("Replace:", replace_combo)

        layout.addLayout(search_row)

        options_group = QGroupBox("Options")
        options_group.setObjectName(f"findSidebar{tab_name.capitalize()}OptionsGroup")
        options_layout = QGridLayout(options_group)
        backward_check = QCheckBox("Previous direction")
        backward_check.setObjectName(f"findSidebar{tab_name.capitalize()}BackwardCheck")
        backward_check.toggled.connect(self._update_search_action_affordances)
        whole_word_check = QCheckBox("Match whole word only")
        whole_word_check.setObjectName(f"findSidebar{tab_name.capitalize()}WholeWordCheck")
        whole_word_check.toggled.connect(self._update_search_action_affordances)
        match_case_check = QCheckBox("Match case")
        match_case_check.setObjectName(f"findSidebar{tab_name.capitalize()}MatchCaseCheck")
        match_case_check.toggled.connect(self._update_search_action_affordances)
        wrap_check = QCheckBox("Wrap around")
        wrap_check.setObjectName(f"findSidebar{tab_name.capitalize()}WrapCheck")
        wrap_check.toggled.connect(self._update_search_action_affordances)
        selection_check = QCheckBox("In selection")
        selection_check.setObjectName(f"findSidebar{tab_name.capitalize()}SelectionCheck")
        selection_check.toggled.connect(self._update_search_action_affordances)
        options_layout.addWidget(backward_check, 0, 0, 1, 2)
        options_layout.addWidget(whole_word_check, 1, 0, 1, 2)
        options_layout.addWidget(match_case_check, 2, 0, 1, 2)
        options_layout.addWidget(wrap_check, 3, 0, 1, 2)
        options_layout.addWidget(selection_check, 4, 0, 1, 2)
        layout.addWidget(options_group)

        mode_group = QGroupBox("Search Mode")
        mode_group.setObjectName(f"findSidebar{tab_name.capitalize()}ModeGroup")
        mode_layout = QVBoxLayout(mode_group)
        normal_radio = QRadioButton("Normal")
        normal_radio.setObjectName(f"findSidebar{tab_name.capitalize()}NormalModeRadio")
        normal_radio.toggled.connect(self._update_search_action_affordances)
        extended_radio = QRadioButton("Extended (\\n, \\r, \\t, \\x...)")
        extended_radio.setObjectName(f"findSidebar{tab_name.capitalize()}ExtendedModeRadio")
        extended_radio.toggled.connect(self._update_search_action_affordances)
        regex_radio = QRadioButton("Regular Expression")
        regex_radio.setObjectName(f"findSidebar{tab_name.capitalize()}RegexModeRadio")
        regex_radio.toggled.connect(self._update_search_action_affordances)
        regex_newline_check = QCheckBox("Matches newline")
        regex_newline_check.setObjectName(f"findSidebar{tab_name.capitalize()}RegexNewlineCheck")
        regex_newline_check.toggled.connect(self._update_search_action_affordances)
        mode_buttons = QButtonGroup(mode_group)
        mode_buttons.addButton(normal_radio)
        mode_buttons.addButton(extended_radio)
        mode_buttons.addButton(regex_radio)
        mode_layout.addWidget(normal_radio)
        mode_layout.addWidget(extended_radio)
        mode_layout.addWidget(regex_radio)
        mode_layout.addWidget(regex_newline_check)
        regex_radio.toggled.connect(regex_newline_check.setEnabled)
        layout.addWidget(mode_group)

        replace_button: QPushButton | None = None
        replace_all_button: QPushButton | None = None
        if tab_name == "replace":
            action_row = QWidget()
            action_row_layout = QHBoxLayout(action_row)
            action_row_layout.setContentsMargins(0, 0, 0, 0)
            action_row_layout.setSpacing(4)

            replace_button = QPushButton("Replace Next")
            replace_button.setObjectName("findSidebarReplaceButton")
            replace_button.setCursor(Qt.CursorShape.PointingHandCursor)
            replace_button.clicked.connect(lambda _checked=False: self.replace_current_action.trigger())

            replace_all_button = QPushButton("Replace All")
            replace_all_button.setObjectName("findSidebarReplaceAllButton")
            replace_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
            replace_all_button.clicked.connect(lambda _checked=False: self.replace_all_action.trigger())

            action_row_layout.addWidget(replace_button)
            action_row_layout.addWidget(replace_all_button)
            action_row_layout.addStretch(1)
            layout.addWidget(action_row)

        return SearchPageWidgets(
            page=page,
            find_combo=find_combo,
            replace_combo=replace_combo,
            replace_button=replace_button,
            replace_all_button=replace_all_button,
            backward_check=backward_check,
            whole_word_check=whole_word_check,
            match_case_check=match_case_check,
            wrap_check=wrap_check,
            selection_check=selection_check,
            normal_radio=normal_radio,
            extended_radio=extended_radio,
            regex_radio=regex_radio,
            regex_newline_check=regex_newline_check,
        )

    def _build_analysis_sidebar_page(self) -> AnalysisSidebarWidgets:
        page = QWidget()
        page.setObjectName("analysisSidebarPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        header_row = QWidget()
        header_row.setObjectName("analysisSidebarHeaderRow")
        header_row_layout = QHBoxLayout(header_row)
        header_row_layout.setContentsMargins(8, 6, 8, 6)
        header_row_layout.setSpacing(8)
        header_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        header_title = QLabel("Analysis")
        header_title.setStyleSheet("font-weight: 600;")
        header_title.setObjectName("analysisSidebarHeaderTitle")
        header_state_label = QLabel("syntax passed")
        header_state_label.setObjectName("analysisSidebarHeaderState")
        header_state_label.setStyleSheet(
            "padding: 2px 8px; border-radius: 999px; background: rgba(46, 125, 50, 0.14);"
            "color: #2f6f3e; font-size: 10px; font-weight: 600; text-transform: uppercase;"
        )
        header_count_label = QLabel("0 diagnostics")
        header_count_label.setObjectName("analysisSidebarHeaderCount")
        header_count_label.setStyleSheet("color: #555555; font-size: 10px; font-weight: 600;")
        header_row_layout.addWidget(header_title)
        header_row_layout.addWidget(header_state_label)
        header_row_layout.addWidget(header_count_label)
        header_row_layout.addStretch(1)
        layout.addWidget(header_row)

        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(8, 6, 8, 6)
        summary_layout.setSpacing(4)
        summary_hint = QLabel("Snapshot.")
        summary_hint.setWordWrap(True)
        summary_hint.setStyleSheet("color: #666666; font-size: 10px;")
        summary_layout.addWidget(summary_hint)
        summary_view = QPlainTextEdit()
        summary_view.setObjectName("analysisSidebarSummaryView")
        summary_view.setReadOnly(True)
        summary_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        summary_view.setMaximumHeight(132)
        summary_layout.addWidget(summary_view)

        diagnostics_group = QGroupBox("Diagnostics")
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        diagnostics_layout.setContentsMargins(8, 6, 8, 6)
        diagnostics_layout.setSpacing(4)
        diagnostics_hint = QLabel("Jump to source.")
        diagnostics_hint.setObjectName("analysisSidebarDiagnosticsHeader")
        diagnostics_hint.setWordWrap(True)
        diagnostics_hint.setStyleSheet("color: #666666; font-size: 10px;")
        diagnostics_layout.addWidget(diagnostics_hint)
        diagnostics_view = QTextBrowser()
        diagnostics_view.setObjectName("analysisSidebarDiagnosticsView")
        diagnostics_view.setOpenExternalLinks(False)
        diagnostics_view.setOpenLinks(False)
        diagnostics_view.anchorClicked.connect(self._handle_diagnostics_anchor_clicked)
        diagnostics_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        diagnostics_layout.addWidget(diagnostics_view, 1)

        analysis_splitter = QSplitter(Qt.Orientation.Vertical)
        analysis_splitter.setObjectName("analysisSidebarSplitter")
        analysis_splitter.setChildrenCollapsible(False)
        analysis_splitter.addWidget(summary_group)
        analysis_splitter.addWidget(diagnostics_group)
        analysis_splitter.setStretchFactor(0, 0)
        analysis_splitter.setStretchFactor(1, 1)
        layout.addWidget(analysis_splitter, 1)

        status_label = QLabel("Run Analyze.")
        status_label.setObjectName("analysisSidebarStatusLabel")
        status_label.setWordWrap(True)
        status_label.setMinimumHeight(28)
        status_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(status_label)

        widgets = AnalysisSidebarWidgets(
            page=page,
            header_state_label=header_state_label,
            header_count_label=header_count_label,
            summary_view=summary_view,
            diagnostics_view=diagnostics_view,
            status_label=status_label,
        )
        self._analysis_sidebar_widgets = widgets
        self._refresh_analysis_sidebar()
        return widgets

    def _build_debugger_controls_dialog(self) -> None:
        self.debugger_controls_dialog = QDialog(self)
        self.debugger_controls_dialog.setObjectName("debugControlsDialog")
        self.debugger_controls_dialog.setWindowTitle("")
        self.debugger_controls_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.debugger_controls_dialog.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.debugger_controls_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.debugger_controls_dialog.setFixedSize(244, 64)
        dialog_layout = QVBoxLayout(self.debugger_controls_dialog)
        dialog_layout.setContentsMargins(2, 2, 2, 2)
        dialog_layout.setSpacing(0)

        self.debugger_controls_title_bar = QWidget()
        self.debugger_controls_title_bar.setObjectName("debugControlsTitleBar")
        self.debugger_controls_title_bar.setFixedHeight(14)
        self.debugger_controls_title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
        self.debugger_controls_title_bar.installEventFilter(self)
        title_bar_layout = QGridLayout(self.debugger_controls_title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setHorizontalSpacing(2)
        title_bar_layout.setVerticalSpacing(0)
        title_bar_layout.setColumnStretch(0, 1)
        title_bar_layout.setColumnStretch(1, 0)
        title_bar_layout.setColumnStretch(2, 1)
        self.debugger_controls_title_label = QLabel("Debugger Controls")
        self.debugger_controls_title_label.setObjectName("debugControlsTitleLabel")
        title_font = QFont()
        title_font.setFamily("Segoe UI")
        title_font.setPointSize(9)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.debugger_controls_title_label.setFont(title_font)
        self.debugger_controls_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar_layout.addWidget(self.debugger_controls_title_label, 0, 1)
        self.debugger_controls_close_button = QToolButton(self.debugger_controls_title_bar)
        self.debugger_controls_close_button.setObjectName("debugControlsCloseButton")
        self.debugger_controls_close_button.setText("x")
        self.debugger_controls_close_button.setAutoRaise(False)
        self.debugger_controls_close_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.debugger_controls_close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.debugger_controls_close_button.setFixedSize(14, 14)
        self.debugger_controls_close_button.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.debugger_controls_close_button.clicked.connect(self.debugger_controls_dialog.hide)
        title_bar_layout.addWidget(self.debugger_controls_close_button, 0, 2, Qt.AlignmentFlag.AlignRight)
        dialog_layout.addWidget(self.debugger_controls_title_bar)

        controls_row = QWidget()
        controls_row.setObjectName("debugControlsRow")
        controls_row_layout = QHBoxLayout(controls_row)
        controls_row_layout.setContentsMargins(0, 0, 0, 0)
        controls_row_layout.setSpacing(1)
        controls_row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.debug_continue_button = self._build_debug_control_button(
            action=self.debug_continue_action,
            object_name="debugContinueButton",
            tooltip="Continue",
        )
        self.debug_pause_button = self._build_debug_control_button(
            action=self.debug_pause_action,
            object_name="debugPauseButton",
            tooltip="Pause",
        )
        self.debug_step_over_button = self._build_debug_control_button(
            action=self.debug_step_over_action,
            object_name="debugStepOverButton",
            tooltip="Step Over",
        )
        self.debug_step_button = self._build_debug_control_button(
            action=self.debug_step_into_action,
            object_name="debugStepIntoButton",
            tooltip="Step Into",
        )
        self.debug_step_out_button = self._build_debug_control_button(
            action=self.debug_step_out_action,
            object_name="debugStepOutButton",
            tooltip="Step Out",
        )
        self.debug_restart_button = self._build_debug_control_button(
            action=self.debug_restart_action,
            object_name="debugRestartButton",
            tooltip="Restart",
        )
        self.debug_stop_button = self._build_debug_control_button(
            action=self.debug_stop_action,
            object_name="debugStopButton",
            tooltip="Debug Stop",
        )
        for button in (
            self.debug_continue_button,
            self.debug_pause_button,
            self.debug_step_over_button,
            self.debug_step_button,
            self.debug_step_out_button,
            self.debug_restart_button,
            self.debug_stop_button,
        ):
            controls_row_layout.addWidget(button)
        status_spacer = QWidget()
        status_spacer.setObjectName("debugControlsStatusSpacer")
        status_spacer.setFixedWidth(2)
        controls_row_layout.addWidget(status_spacer, 0)

        status_label = QLabel("Status:")
        status_label.setObjectName("debugControlsStatusLabel")
        status_label.setStyleSheet("font-size: 9px; font-weight: 600;")
        controls_row_layout.addWidget(status_label, 0)

        self.debugger_controls_status_indicator = QLabel()
        self.debugger_controls_status_indicator.setObjectName("debugControlsStatusIndicator")
        self.debugger_controls_status_indicator.setFixedSize(10, 8)
        self.debugger_controls_status_indicator.setToolTip("Idle")
        self.debugger_controls_status_indicator.setStyleSheet(
            self._debug_status_indicator_stylesheet("#9ea7af")
        )
        controls_row_layout.addWidget(self.debugger_controls_status_indicator, 0)
        controls_row_layout.addStretch(1)
        dialog_layout.addWidget(controls_row)

    def _show_debugger_controls_dialog(self) -> None:
        dialog = getattr(self, "debugger_controls_dialog", None)
        if dialog is None:
            return
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _build_sidebar_mode_button(
        self,
        *,
        mode: str,
        text: str,
        icon: QIcon,
        enabled: bool,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName(f"{mode}SidebarModeButton")
        button.setCheckable(True)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icon)
        button.setToolTip(text)
        button.setStatusTip(text)
        button.setEnabled(enabled)
        button.setMinimumSize(34, 34)
        button.setIconSize(QSize(15, 15))
        button.setStyleSheet(self._sidebar_mode_button_stylesheet())
        button.clicked.connect(lambda checked=False, mode_name=mode: self._set_sidebar_mode(mode_name))
        self.sidebar_mode_button_group.addButton(button)
        return button

    def _sidebar_mode_icon(self, mode: str) -> QIcon:
        color = QColor("#334155")
        if mode == "find":
            return qta.icon("mdi6.magnify", color=color)
        if mode == "debug":
            return qta.icon("mdi6.bug-outline", color=color)
        if mode == "analysis":
            return qta.icon("mdi6.chart-box-outline", color=color)
        return qta.icon("mdi6.circle-outline", color=color)

    def _build_sidebar_placeholder_page(
        self,
        title: str,
        description: str,
        *,
        action_label: str | None = None,
        action_callback: Callable[[], None] | None = None,
    ) -> QWidget:
        page = QWidget()
        page.setObjectName(f"{title.lower()}SidebarPlaceholderPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        layout.addStretch(1)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #666666;")
        layout.addWidget(description_label)

        if action_label is not None and action_callback is not None:
            action_button = QPushButton(action_label)
            action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            action_button.clicked.connect(action_callback)
            layout.addWidget(action_button, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(2)
        return page

    def _build_debug_tree_empty_state_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("debugTreeEmptyStateLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setMinimumHeight(36)
        label.setStyleSheet(
            "QLabel#debugTreeEmptyStateLabel {"
            " color: #798796;"
            " font-size: 10px;"
            " font-style: italic;"
            " padding: 4px 6px;"
            " border: 1px dashed rgba(137, 152, 170, 0.35);"
            " border-radius: 8px;"
            " background-color: #fbfcfe;"
            " }"
        )
        return label

    def _build_debug_control_button(
        self,
        *,
        action: QAction,
        object_name: str,
        tooltip: str,
    ) -> QToolButton:
        button = QToolButton(self.debugger_controls_dialog)
        button.setObjectName(object_name)
        button.setDefaultAction(action)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setText("")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(22, 22)
        button.setIconSize(QSize(12, 12))
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        return button

    def _sidebar_mode_button_stylesheet(self) -> str:
        return (
            "QToolButton {"
            " min-width: 34px;"
            " min-height: 34px;"
            " padding: 6px;"
            " border-radius: 11px;"
            " border: 1px solid #d8e0ea;"
            " background-color: #fbfcfe;"
            " }"
            "QToolButton:hover:enabled {"
            " background-color: #f4f8fc;"
            " border-color: #b6c4d6;"
            " }"
            "QToolButton:checked:enabled {"
            " background-color: #eaf3fb;"
            " border-color: #88acd4;"
            " border-left: 3px solid #2f6fb6;"
            " padding-left: 4px;"
            " padding-right: 6px;"
            " font-weight: 600;"
            " }"
            "QToolButton:checked:enabled:hover {"
            " background-color: #e3effa;"
            " border-color: #709fcd;"
            " border-left: 4px solid #2b67aa;"
            " }"
            "QToolButton:checked:enabled, QToolButton:checked:enabled:hover {"
            " color: #234a73;"
            " }"
            "QToolButton:pressed:enabled {"
            " background-color: #eef4f9;"
            " border-color: #b5c3d4;"
            " }"
            "QToolButton:pressed:checked:enabled {"
            " background-color: #dceaf8;"
            " border-color: #6e9dca;"
            " }"
            "QToolButton:disabled {"
            " background-color: #f1f4f8;"
            " border-color: #dde3ea;"
            " }"
        )

    def _debug_sidebar_stylesheet(self) -> str:
        return (
            "QWidget#debugInspectorView {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#findSidebarPage {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#analysisSidebarPage {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#sidebarModeContentShell {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#sidebarShell {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#sidebarTitleBar {"
            " background-color: #f4f7fb;"
            " }"
            "QWidget#sidebarModeRail {"
            " background-color: #edf2f7;"
            " border-right: 1px solid rgba(130, 144, 162, 0.20);"
            " }"
            "QLabel#sidebarModeTitleLabel {"
            " background-color: transparent;"
            " }"
            "QWidget#debugInspectorHeader {"
            " background-color: #ffffff;"
            " border: 1px solid #d9e1eb;"
            " border-radius: 10px;"
            " }"
            "QWidget#analysisSidebarHeaderRow {"
            " background-color: #ffffff;"
            " border: 1px solid #d9e1eb;"
            " border-radius: 10px;"
            " }"
            "QWidget#debugStatusChip {"
            " background-color: #f7f9fc;"
            " border: 1px solid #dbe3ee;"
            " border-radius: 8px;"
            " }"
            "QLabel#debugInspectorTitleLabel {"
            " color: #23313f;"
            " font-size: 14px;"
            " font-weight: 700;"
            " }"
            "QLabel#debugInspectorSubtitleLabel {"
            " color: #657281;"
            " font-size: 9px;"
            " }"
            "QLabel#findSidebarIntroLabel, QLabel#findSidebarStatusLabel, QLabel#analysisSidebarStatusLabel, QLabel#analysisSidebarDiagnosticsHeader, QLabel#searchResultsSummaryLabel {"
            " color: #666666;"
            " font-size: 10px;"
            " }"
            "QLabel#sidebarModeTitleLabel {"
            " color: #23313f;"
            " font-size: 13px;"
            " font-weight: 700;"
            " }"
            "QToolButton#debugControlsButton {"
            " padding: 2px 8px;"
            " border-radius: 8px;"
            " border: 1px solid #d7e0ea;"
            " background-color: #ffffff;"
            " color: #314052;"
            " font-size: 10px;"
            " font-weight: 600;"
            " }"
            "QToolButton#debugControlsButton:hover:enabled {"
            " background-color: #f7fafc;"
            " border-color: #b8c5d4;"
            " }"
            "QLabel#debugControlsTitleLabel {"
            " color: #223041;"
            " }"
            "QGroupBox {"
            " background-color: #ffffff;"
            " border: 1px solid #d9e1eb;"
            " border-radius: 10px;"
            " margin-top: 5px;"
            " padding: 4px 4px 4px 4px;"
            " }"
            "QGroupBox#findSidebarResultsGroup {"
            " margin-top: 7px;"
            " }"
            "QGroupBox::title {"
            " subcontrol-origin: margin;"
            " subcontrol-position: top left;"
            " left: 8px;"
            " padding: 0 4px;"
            " color: #2f3e4d;"
            " font-size: 9px;"
            " font-weight: 700;"
            " }"
            "QTreeWidget, QPlainTextEdit {"
            " background-color: #ffffff;"
            " border: 1px solid #e0e7ef;"
            " border-radius: 6px;"
            " padding: 1px;"
            " selection-background-color: #dce9f8;"
            " selection-color: #18212b;"
            " font-size: 10px;"
            " color: #23313f;"
            " }"
            "QLineEdit, QComboBox {"
            " background-color: #ffffff;"
            " border: 1px solid #cfd8e3;"
            " border-radius: 6px;"
            " padding: 2px 8px;"
            " min-height: 20px;"
            " color: #23313f;"
            " }"
            "QLineEdit:focus, QComboBox:focus {"
            " border-color: #1976d2;"
            " }"
            "QComboBox::drop-down {"
            " border: 0;"
            " width: 16px;"
            " }"
            "QCheckBox, QRadioButton {"
            " color: #324152;"
            " font-size: 10px;"
            " }"
            "QPushButton {"
            " background-color: #ffffff;"
            " border: 1px solid #d1dbe8;"
            " border-radius: 6px;"
            " padding: 2px 8px;"
            " min-height: 20px;"
            " color: #314052;"
            " font-weight: 600;"
            " }"
            "QPushButton:hover:enabled {"
            " background-color: #f7fafc;"
            " border-color: #b8c5d4;"
            " }"
            "QPlainTextEdit {"
            " font-family: Consolas, 'Courier New', monospace;"
            " }"
            "QTreeWidget {"
            " alternate-background-color: #f8fafc;"
            " }"
            "QTabWidget::pane {"
            " border: 1px solid #d9e1eb;"
            " border-radius: 8px;"
            " top: -3px;"
            " background-color: #ffffff;"
            " }"
            "QTabBar::tab {"
            " background-color: #edf2f7;"
            " border: 1px solid #d9e1eb;"
            " border-bottom: none;"
            " padding: 0px 7px;"
            " margin-right: 2px;"
            " color: #425162;"
            " font-size: 10px;"
            " }"
            "QTabBar::tab:selected {"
            " background-color: #ffffff;"
            " color: #23313f;"
            " font-weight: 600;"
            " }"
            "QLabel#debugTreeEmptyStateLabel {"
            " color: #798796;"
            " font-size: 10px;"
            " font-style: italic;"
            " padding: 4px 6px;"
            " border: 1px dashed rgba(137, 152, 170, 0.35);"
            " border-radius: 6px;"
            " background-color: #fbfcfe;"
            " }"
            "QTreeWidget::item {"
            " padding: 1px 2px;"
            " min-height: 16px;"
            " }"
            "QTreeWidget::item:selected, QTreeWidget::item:selected:active {"
            " background-color: #dce9f8;"
            " color: #18212b;"
            " }"
            "QHeaderView::section {"
            " background-color: #f7f9fc;"
            " color: #445062;"
            " border: none;"
            " border-bottom: 1px solid #e0e6ef;"
            " padding: 3px 6px;"
            " font-size: 9px;"
            " font-weight: 700;"
            " }"
            "QLineEdit#debugWatchExpressionEdit {"
            " background-color: #ffffff;"
            " border: 1px solid #cfd8e3;"
            " border-radius: 6px;"
            " padding: 2px 8px;"
            " min-height: 20px;"
            " }"
            "QLineEdit#debugWatchExpressionEdit:focus {"
            " border-color: #1976d2;"
            " }"
            "QPushButton#debugAddWatchButton, QPushButton#debugRemoveWatchButton {"
            " background-color: #ffffff;"
            " border: 1px solid #d1dbe8;"
            " border-radius: 6px;"
            " padding: 2px 8px;"
            " min-height: 20px;"
            " color: #314052;"
            " font-weight: 600;"
            " }"
            "QPushButton#debugAddWatchButton:hover:enabled, QPushButton#debugRemoveWatchButton:hover:enabled {"
            " background-color: #f7fafc;"
            " border-color: #b8c5d4;"
            " }"
            "QSplitter::handle {"
            " background-color: rgba(130, 144, 162, 0.12);"
            " margin: 5px 18px;"
            " border-radius: 3px;"
            " }"
        )

    def _debug_status_indicator_stylesheet(self, color: str) -> str:
        return (
            "QLabel#debugStatusIndicator, QLabel#debugControlsStatusIndicator {"
            " margin: 0px;"
            " padding: 0px;"
            " border-radius: 4px;"
            " border: 1px solid rgba(90, 100, 112, 0.28);"
            f" background-color: {color};"
            " }"
        )

    def _set_sidebar_mode(self, mode: str) -> None:
        if not hasattr(self, "sidebar_mode_stack"):
            return
        if mode not in self.sidebar_mode_pages:
            return

        self._current_sidebar_mode = mode
        self.sidebar_mode_stack.setCurrentWidget(self.sidebar_mode_pages[mode])
        if hasattr(self, "sidebar_mode_title_label"):
            self.sidebar_mode_title_label.setVisible(mode != "debug")
            self.sidebar_mode_title_label.setText("Debugger" if mode == "debug" else mode.capitalize())
        if hasattr(self, "sidebar_mode_buttons"):
            for mode_name, button in self.sidebar_mode_buttons.items():
                button.setChecked(mode_name == mode)

    def _set_sidebar_mode_button_visible(self, mode: str, visible: bool) -> None:
        button = getattr(self, "sidebar_mode_buttons", {}).get(mode)
        if button is None:
            return
        button.setVisible(visible)
        if visible:
            return
        if getattr(self, "_current_sidebar_mode", None) != mode:
            return
        for fallback_mode in ("find", "analysis", "debug"):
            fallback_button = self.sidebar_mode_buttons.get(fallback_mode)
            if fallback_button is None or not fallback_button.isVisible():
                continue
            self._set_sidebar_mode(fallback_mode)
            break

    def _build_playback_toolbar_button(self, action: QAction, object_name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setDefaultAction(action)
        button.setAutoRaise(False)
        button.setIconSize(QSize(13, 13))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(24, 24)
        button.setStyleSheet(self._playback_toolbar_button_stylesheet(object_name))
        return button

    def _build_file_toolbar_button(self, action: QAction, object_name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setDefaultAction(action)
        button.setAutoRaise(False)
        button.setIconSize(QSize(16, 16))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(24, 24)
        button.setStyleSheet(self._file_toolbar_button_stylesheet())
        return button

    def _build_analysis_toolbar_button(self, action: QAction, object_name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setDefaultAction(action)
        if action.toolTip():
            button.setToolTip(action.toolTip())
        if action.statusTip():
            button.setStatusTip(action.statusTip())
        button.setAutoRaise(False)
        button.setIconSize(QSize(16, 16))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(24, 24)
        button.setStyleSheet(self._file_toolbar_button_stylesheet())
        return button

    def _build_settings_toolbar_button(self, action: QAction, object_name: str) -> QToolButton:
        button = self._build_analysis_toolbar_button(action, object_name)
        button.setStyleSheet(self._settings_toolbar_button_stylesheet())
        return button

    def _build_toolbar_separator(self, object_name: str) -> QWidget:
        separator = QWidget()
        separator.setObjectName(object_name)
        separator.setFixedWidth(4)
        separator.setStyleSheet(
            "background: transparent;"
            "border-left: 1px solid rgba(90, 100, 112, 0.18);"
            "margin: 0px 1px;"
        )
        return separator

    def _update_playback_action_affordances(self) -> None:
        for action_id, action in (
            ("preview", self.preview_play_script_action),
            ("play", self.play_script_action),
            ("record", self.record_script_action),
            ("stop", self.stop_script_action),
        ):
            shortcut = self._action_shortcut_display_text(action_id, action)
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")

    def _update_editor_edit_action_affordances(self) -> None:
        recording_active = self.script_controller.current_operation_kind == "record"
        for action in (
            self.undo_action,
            self.redo_action,
            self.cut_action,
            self.paste_action,
            self.delete_action,
        ):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")
            action.setEnabled(not recording_active)

    def _update_file_action_affordances(self) -> None:
        for action in (self.new_action, self.open_action, self.save_action, self.save_as_action):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")

    def _update_search_action_affordances(self) -> None:
        criteria = self._capture_find_sidebar_criteria()
        has_query = bool(criteria.find_text.strip())
        has_selection = hasattr(self, "editor") and self.editor.textCursor().hasSelection()
        replace_label = "Replace Previous" if criteria.backward else "Replace Next"
        replace_action = getattr(self, "replace_current_action", None)
        if replace_action is not None:
            replace_action.setText(replace_label)
        widgets = getattr(self, "_find_sidebar_widgets", None)
        if widgets is not None and widgets.replace_button is not None:
            widgets.replace_button.setText(replace_label)
        for action in (
            self.find_action,
            self.replace_action,
        ):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")
            action.setEnabled(True)

        for action in (
            self.find_next_action,
            self.find_previous_action,
            self.replace_current_action,
            self.replace_all_action,
        ):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")
            action.setEnabled(has_query and self.script_controller.current_operation_kind != "record")

        for action in (self.select_and_find_next_action, self.select_and_find_previous_action):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")
            action.setEnabled(has_query and has_selection)

    def _update_analysis_action_affordances(self) -> None:
        for action in (self.analyze_action, self.preview_action):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            if action is self.analyze_action:
                help_text = (
                    "Analyze the current editor text and refresh the analysis summary and diagnostics. "
                    "Does not save the file or update the preview."
                )
                action.setToolTip(f"{action.text()}{suffix} - {help_text}")
                action.setStatusTip(help_text)
            else:
                action.setToolTip(f"{action.text()}{suffix}")
                action.setStatusTip(f"{action.text()}{suffix}")
        self.debugger_action.setToolTip("Run")
        self.debugger_action.setStatusTip("Run")

    def _update_breakpoint_action_affordances(self) -> None:
        for action in (self.toggle_breakpoint_action, self.clear_breakpoints_action):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")
        if not hasattr(self, "editor"):
            return
        snapshot = self._current_debug_session_state()
        if snapshot is not None and getattr(snapshot, "state", None) in {"running", "paused"}:
            current_line = getattr(snapshot, "current_line", None)
        else:
            current_line = self.editor.currentLineNumber()
        if not isinstance(current_line, int) or current_line < 1:
            return
        breakpoint_lines = self.editor.debugBreakpointLines()
        has_breakpoint = current_line in breakpoint_lines
        icon = self._toggle_breakpoint_action_icon(has_breakpoint)
        self.toggle_breakpoint_action.setIcon(icon)
        if hasattr(self, "debug_toggle_breakpoint_button"):
            self.debug_toggle_breakpoint_button.setIcon(icon)

    def _toggle_breakpoint_action_icon(self, has_breakpoint: bool):
        return (
            self._file_action_icon("msc.debug-breakpoint-unverified")
            if has_breakpoint
            else self._file_action_icon("msc.debug-breakpoint")
        )

    def _update_debug_step_action_affordances(self) -> None:
        for action in (
            self.debug_step_into_action,
            self.debug_step_over_action,
            self.debug_step_out_action,
            self.debug_continue_action,
            self.debug_pause_action,
            self.debug_restart_action,
            self.debug_stop_action,
        ):
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()
            suffix = f" ({shortcut})" if shortcut else ""
            action.setToolTip(f"{action.text()}{suffix}")
            action.setStatusTip(f"{action.text()}{suffix}")

    def _update_settings_action_affordances(self) -> None:
        preferences_shortcut = self.preferences_action.shortcut().toString(
            QKeySequence.SequenceFormat.NativeText
        ).strip()
        preferences_suffix = f" ({preferences_shortcut})" if preferences_shortcut else ""
        self.preferences_action.setToolTip(f"{self.preferences_action.text()}{preferences_suffix}")
        self.preferences_action.setStatusTip(f"{self.preferences_action.text()}{preferences_suffix}")

        self.documentation_action.setToolTip(self.documentation_action.text())
        self.documentation_action.setStatusTip(self.documentation_action.text())

    def _playback_toolbar_button_stylesheet(self, object_name: str) -> str:
        preview_blue = "#1565c0"
        play_green = "#2e7d32"
        record_red = "#c62828"
        stop_red = "#b71c1c"
        if object_name == "previewPlayScriptToolbarButton":
            return (
                "QToolButton#previewPlayScriptToolbarButton { padding: 1px 6px; border-radius: 4px; }"
                "QToolButton#previewPlayScriptToolbarButton:enabled {"
                f" background-color: rgba(21, 101, 192, 0.12);"
                f" border: 1px solid {preview_blue};"
                f" color: {preview_blue};"
                " font-weight: 600;"
                " }"
                "QToolButton#previewPlayScriptToolbarButton:enabled:hover {"
                f" background-color: rgba(21, 101, 192, 0.20);"
                " }"
                "QToolButton#previewPlayScriptToolbarButton:disabled {"
                " background-color: transparent;"
                " color: #888888;"
                " border: 1px solid #cccccc;"
                " }"
            )
        if object_name == "playScriptToolbarButton":
            return (
                "QToolButton#playScriptToolbarButton { padding: 1px 6px; border-radius: 4px; }"
                "QToolButton#playScriptToolbarButton:enabled {"
                f" background-color: rgba(46, 125, 50, 0.12);"
                f" border: 1px solid {play_green};"
                f" color: {play_green};"
                " font-weight: 600;"
                " }"
                "QToolButton#playScriptToolbarButton:enabled:hover {"
                f" background-color: rgba(46, 125, 50, 0.20);"
                " }"
                "QToolButton#playScriptToolbarButton:disabled {"
                " background-color: transparent;"
                " color: #888888;"
                " border: 1px solid #cccccc;"
                " }"
            )
        if object_name == "recordScriptToolbarButton":
            return (
                "QToolButton#recordScriptToolbarButton { padding: 1px 6px; border-radius: 4px; }"
                "QToolButton#recordScriptToolbarButton:enabled {"
                f" background-color: rgba(198, 40, 40, 0.12);"
                f" border: 1px solid {record_red};"
                f" color: {record_red};"
                " font-weight: 600;"
                " }"
                "QToolButton#recordScriptToolbarButton:enabled:hover {"
                f" background-color: rgba(198, 40, 40, 0.20);"
                " }"
                "QToolButton#recordScriptToolbarButton:disabled {"
                " background-color: transparent;"
                " color: #888888;"
                " border: 1px solid #cccccc;"
                " }"
            )
        return (
            "QToolButton#stopScriptToolbarButton { padding: 1px 6px; border-radius: 4px; }"
            "QToolButton#stopScriptToolbarButton:enabled {"
            f" background-color: {stop_red};"
            " border: 1px solid #8e0000;"
            " color: #ffffff;"
            " font-weight: 700;"
            " }"
            "QToolButton#stopScriptToolbarButton:enabled:hover {"
            " background-color: #d32f2f;"
            " }"
            "QToolButton#stopScriptToolbarButton:disabled {"
            " background-color: transparent;"
            " color: #888888;"
            " border: 1px solid #cccccc;"
            " }"
        )

    def _sidebar_toolbar_button_stylesheet(self) -> str:
        accent = "#4a5568"
        return (
            "QToolButton { padding: 0px; border: 0; background: transparent; }"
            "QToolButton:enabled {"
            f" color: {accent};"
            " }"
            "QToolButton:enabled:hover {"
            " background-color: transparent;"
            " border: 0;"
            " }"
            "QToolButton:checked:enabled {"
            " background-color: transparent;"
            " border: 0;"
            " }"
            "QToolButton:disabled {"
            " background-color: transparent;"
            " color: #888888;"
            " border: 0;"
            " }"
        )

    def _file_toolbar_button_stylesheet(self) -> str:
        return (
            "QToolButton { padding: 1px; border-radius: 4px; }"
            "QToolButton:enabled {"
            " background-color: transparent;"
            " border: 1px solid transparent;"
            " }"
            "QToolButton:enabled:hover {"
            " background-color: rgba(90, 100, 112, 0.10);"
            " border: 1px solid rgba(90, 100, 112, 0.25);"
            " }"
            "QToolButton:disabled {"
            " background-color: transparent;"
            " border: 1px solid transparent;"
            " }"
        )

    def _settings_toolbar_button_stylesheet(self) -> str:
        return (
            "QToolButton { padding: 0px 3px; border-radius: 4px; }"
            "QToolButton:enabled {"
            " background-color: transparent;"
            " border: 1px solid transparent;"
            " }"
            "QToolButton:enabled:hover {"
            " background-color: rgba(90, 100, 112, 0.15);"
            " border: 1px solid rgba(90, 100, 112, 0.30);"
            " }"
            "QToolButton:disabled {"
            " background-color: transparent;"
            " border: 1px solid transparent;"
            " }"
        )

    def _playback_action_icon(self, icon_name: str):
        if icon_name == "mdi6.record":
            return self._playback_icon_font.icon("mdi6.record", color=QColor("#c62828"))
        if icon_name == "play":
            return self.style().standardIcon(QStyle.SP_MediaPlay)
        if icon_name == "stop":
            return self.style().standardIcon(QStyle.SP_MediaStop)
        return self._playback_icon_font.icon(
            icon_name,
            color=self.palette().color(QPalette.ColorRole.ButtonText),
        )

    def _mdi6_action_icon(self, icon_name: str):
        return self._playback_icon_font.icon(
            icon_name,
            color=self.palette().color(QPalette.ColorRole.ButtonText),
        )

    def _fa6s_action_icon(self, icon_name: str):
        return qta.icon(
            icon_name,
            color=self.palette().color(QPalette.ColorRole.ButtonText),
        )

    def _file_action_icon(self, icon_name: str, *, color: QColor | None = None):
        return self._file_icon_font.icon(
            icon_name,
            color=color or self.palette().color(QPalette.ColorRole.ButtonText),
        )

    def _bind_actions(self) -> None:
        self.new_action = QAction("New", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self.new_document)
        self.new_action.setIcon(self._file_action_icon("msc.new-file"))

        self.open_action = QAction("Open...", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_script)
        self.open_action.setIcon(self._file_action_icon("msc.folder-opened"))

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_script)
        self.save_action.setIcon(self._file_action_icon("msc.save"))

        self.save_as_action = QAction("Save As...", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.save_script_as)
        self.save_as_action.setIcon(self._file_action_icon("msc.save-all"))

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.editor_undo)
        self.undo_action.setIcon(self._mdi6_action_icon("mdi6.undo"))

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.editor_redo)
        self.redo_action.setIcon(self._mdi6_action_icon("mdi6.redo"))

        self.cut_action = QAction("Cut", self)
        self.cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self.cut_action.triggered.connect(self.editor_cut)
        self.cut_action.setIcon(self._mdi6_action_icon("mdi6.scissors-cutting"))

        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self.editor_copy)
        self.copy_action.setIcon(self._file_action_icon("msc.clippy"))

        self.paste_action = QAction("Paste", self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.triggered.connect(self.editor_paste)
        self.paste_action.setIcon(self._mdi6_action_icon("mdi6.content-paste"))

        self.delete_action = QAction("Delete", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.triggered.connect(self.editor_delete_selection)
        self.delete_action.setIcon(self._fa6s_action_icon("fa6s.text-slash"))

        self.select_all_action = QAction("Select All", self)
        self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.select_all_action.triggered.connect(self.editor_select_all)
        self.select_all_action.setIcon(self._mdi6_action_icon("mdi6.content-copy"))

        self.analyze_action = QAction("Analyze", self)
        self.analyze_action.setShortcut("F5")
        self.analyze_action.triggered.connect(self.analyze_document)
        self.analyze_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )

        self.preview_action = QAction("Refresh Preview", self)
        self.preview_action.setShortcut("F6")
        self.preview_action.triggered.connect(self.refresh_preview)
        self.preview_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self.document_status_action = QAction("Document Status...", self)
        self.document_status_action.triggered.connect(self.show_document_status_dialog)
        self.document_status_action.setIcon(self._mdi6_action_icon("mdi6.file-document-check-outline"))

        self.view_debugger_tab_action = QAction("Debugger", self)
        self.view_debugger_tab_action.triggered.connect(self.show_debugger_tab)
        self.view_debugger_tab_action.setIcon(self._file_action_icon("msc.debug"))
        self.view_debugger_tab_action.setToolTip("Debugger")
        self.view_debugger_tab_action.setStatusTip("Debugger")

        self.find_action = QAction("Find...", self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(self.find_in_editor)
        self.find_action.setIcon(self._mdi6_action_icon("mdi6.binoculars"))

        self.find_next_action = QAction("Next", self)
        self.find_next_action.setShortcut(QKeySequence.StandardKey.FindNext)
        self.find_next_action.triggered.connect(self.find_next_in_editor)
        self.find_next_action.setIcon(self._mdi6_action_icon("mdi6.redo-variant"))
        self.find_next_action.setIconVisibleInMenu(True)

        self.find_previous_action = QAction("Previous", self)
        self.find_previous_action.setShortcut(QKeySequence.StandardKey.FindPrevious)
        self.find_previous_action.triggered.connect(self.find_previous_in_editor)
        self.find_previous_action.setIcon(self._mdi6_action_icon("mdi6.undo-variant"))
        self.find_previous_action.setIconVisibleInMenu(True)

        self.select_and_find_next_action = QAction("Select and Next", self)
        self.select_and_find_next_action.triggered.connect(self.select_and_find_next_in_editor)
        self.select_and_find_next_action.setIcon(self._mdi6_action_icon("mdi6.select-search"))
        self.select_and_find_next_action.setIconVisibleInMenu(True)

        self.select_and_find_previous_action = QAction("Select and Previous", self)
        self.select_and_find_previous_action.triggered.connect(self.select_and_find_previous_in_editor)
        self.select_and_find_previous_action.setIcon(self._mdi6_action_icon("mdi6.page-previous"))
        self.select_and_find_previous_action.setIconVisibleInMenu(True)

        self.replace_action = QAction("Replace...", self)
        self.replace_action.setShortcut(QKeySequence.StandardKey.Replace)
        self.replace_action.triggered.connect(self.replace_in_editor)
        self.replace_action.setIcon(self._mdi6_action_icon("mdi6.find-replace"))
        self.replace_action.setIconVisibleInMenu(True)

        self.replace_current_action = QAction("Replace Next", self)
        self.replace_current_action.triggered.connect(self._replace_sidebar_replace)
        self.replace_current_action.setIcon(self._file_action_icon("msc.replace"))
        self.replace_current_action.setIconVisibleInMenu(True)

        self.replace_all_action = QAction("Replace All", self)
        self.replace_all_action.triggered.connect(self._replace_sidebar_replace_all)
        self.replace_all_action.setIcon(self._file_action_icon("msc.replace-all"))
        self.replace_all_action.setIconVisibleInMenu(True)

        self.go_to_action = QAction("Go to...", self)
        self.go_to_action.triggered.connect(self.show_go_to_dialog)
        self.go_to_action.setIcon(self._file_action_icon("msc.clone"))
        self.go_to_action.setIconVisibleInMenu(True)

        self.preview_play_script_action = QAction("Preview Play", self)
        self.preview_play_script_action.triggered.connect(lambda _checked=False: self.preview_play_script())
        self.preview_play_script_action.setIcon(self._playback_action_icon("mdi6.eye"))

        self.play_script_action = QAction("Play", self)
        self.play_script_action.triggered.connect(lambda _checked=False: self.play_script())
        self.play_script_action.setIcon(self._playback_action_icon("play"))

        self.record_script_action = QAction("Record", self)
        self.record_script_action.triggered.connect(self.record_script)
        self.record_script_action.setIcon(self._playback_action_icon("mdi6.record"))

        self.stop_script_action = QAction("Stop", self)
        self.stop_script_action.triggered.connect(self.stop_script)
        self.stop_script_action.setIcon(self._playback_action_icon("stop"))

        self.toggle_breakpoint_action = QAction("Toggle Breakpoint", self)
        self.toggle_breakpoint_action.setShortcut("F9")
        self.toggle_breakpoint_action.triggered.connect(self.toggle_current_line_breakpoint)

        self.clear_breakpoints_action = QAction("Clear Breakpoints", self)
        self.clear_breakpoints_action.setShortcut("Ctrl+Shift+F9")
        self.clear_breakpoints_action.triggered.connect(self.clear_all_breakpoints)
        self.clear_breakpoints_action.setIcon(self._file_action_icon("msc.activate-breakpoints"))
        self.clear_breakpoints_action.setEnabled(False)

        self.debug_step_into_action = QAction("Step Into", self)
        self.debug_step_into_action.triggered.connect(self.step_debug_session)
        self.debug_step_into_action.setIcon(self._file_action_icon("msc.debug-step-into"))

        self.debug_step_over_action = QAction("Step Over", self)
        self.debug_step_over_action.triggered.connect(self.step_over_debug_session)
        self.debug_step_over_action.setIcon(self._file_action_icon("msc.debug-step-over"))

        self.debug_step_out_action = QAction("Step Out", self)
        self.debug_step_out_action.triggered.connect(self.step_out_debug_session)
        self.debug_step_out_action.setIcon(self._file_action_icon("msc.debug-step-out"))

        self.debug_continue_action = QAction("Continue", self)
        self.debug_continue_action.triggered.connect(self.continue_debug_session)
        self.debug_continue_action.setIcon(self._file_action_icon("msc.debug-continue"))

        self.debug_pause_action = QAction("Pause", self)
        self.debug_pause_action.triggered.connect(self.pause_debug_session)
        self.debug_pause_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        )

        self.debug_restart_action = QAction("Restart Debug", self)
        self.debug_restart_action.setShortcut("Ctrl+Shift+F5")
        self.debug_restart_action.triggered.connect(self.restart_debug_session)
        self.debug_restart_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )

        self.debug_stop_action = QAction("Stop", self)
        self.debug_stop_action.triggered.connect(self.stop_debug_session)
        self.debug_stop_action.setIcon(self._file_action_icon("ph.stop-light"))

        self.pixel_inspector_action = QAction("Pixel Inspector...", self)
        self.pixel_inspector_action.triggered.connect(self.open_pixel_inspector_window)
        self.pixel_inspector_action.setIcon(self._file_action_icon("msc.inspect"))

        self.preferences_action = QAction("Preferences...", self)
        self.preferences_action.triggered.connect(self.open_preferences)
        self.preferences_action.setIcon(self._file_action_icon("msc.gear"))

        self.documentation_action = QAction("Documentation", self)
        self.documentation_action.triggered.connect(self.open_documentation)
        self.documentation_action.setShortcut(QKeySequence.HelpContents)
        self.documentation_action.setIcon(self._file_action_icon("msc.question"))

        self.debugger_action = QAction("Run", self)
        self.debugger_action.triggered.connect(self.open_debugger_dialog)
        self.debugger_action.setIcon(self._file_action_icon("msc.debug-alt"))
        self.debugger_action.setToolTip("Run")
        self.debugger_action.setStatusTip("Run")

        self.run_debug_menu_action = QAction("Run", self)
        self.run_debug_menu_action.triggered.connect(self.open_debugger_dialog)
        self.run_debug_menu_action.setIcon(self.debugger_action.icon())
        self.run_debug_menu_action.setToolTip("Run")
        self.run_debug_menu_action.setStatusTip("Run")

        self.restart_debug_menu_action = QAction("Restart", self)
        self.restart_debug_menu_action.triggered.connect(self.restart_debug_session)
        self.restart_debug_menu_action.setIcon(self.debug_restart_action.icon())
        self.restart_debug_menu_action.setEnabled(False)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.open_about)
        self.about_action.setIcon(self._file_action_icon("msc.info"))

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)
        self.exit_action.setIcon(self._mdi6_action_icon("mdi6.exit-run"))

        self._hotkey_actions = {
            "new": self.new_action,
            "open": self.open_action,
            "save": self.save_action,
            "save_as": self.save_as_action,
            "undo": self.undo_action,
            "redo": self.redo_action,
            "cut": self.cut_action,
            "copy": self.copy_action,
            "paste": self.paste_action,
            "delete": self.delete_action,
            "select_all": self.select_all_action,
            "find": self.find_action,
            "search": self.find_action,
            "find_next": self.find_next_action,
            "find_previous": self.find_previous_action,
            "replace": self.replace_action,
            "analyze": self.analyze_action,
            "preview": self.preview_action,
            "document_status": self.document_status_action,
            "play": self.play_script_action,
            "record": self.record_script_action,
            "stop": self.stop_script_action,
            "toggle_breakpoint": self.toggle_breakpoint_action,
            "clear_breakpoints": self.clear_breakpoints_action,
            "debug_step_into": self.debug_step_into_action,
            "debug_step_over": self.debug_step_over_action,
            "debug_step_out": self.debug_step_out_action,
            "debug_continue": self.debug_continue_action,
            "debug_pause": self.debug_pause_action,
            "debug_restart": self.debug_restart_action,
            "debug_stop": self.debug_stop_action,
            "view_debugger_tab": self.view_debugger_tab_action,
            "pixel_inspector": self.pixel_inspector_action,
            "preferences": self.preferences_action,
            "documentation": self.documentation_action,
            "debugger": self.debugger_action,
            "about": self.about_action,
            "exit": self.exit_action,
        }

    def _set_plain_text(self, widget: QPlainTextEdit, text: str) -> None:
        widget.blockSignals(True)
        try:
            widget.setPlainText(text)
        finally:
            widget.blockSignals(False)

    def _refresh_summary(self) -> None:
        self._set_plain_text(self.summary_view, "")

    def _document_status_lines(self) -> list[str]:
        return build_document_summary_lines(
            self.current_document,
            path=self.current_path,
            analysis_stale=self._analysis_stale,
            editor_dirty=self._editor_dirty,
        )

    def _refresh_analysis(
        self,
        *,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        summary_lines = build_analysis_summary_lines(
            self.current_analysis,
            analysis_stale=self._analysis_stale,
            source_text=self.current_document.text,
        )
        self._set_plain_text(self.analysis_summary_view, "\n".join(summary_lines))
        analysis_items = self.current_analysis.diagnostics.items if self.current_analysis is not None else []
        self._analysis_diagnostic_spans = {
            f"analysis-diagnostic-{index}": diagnostic.span
            for index, diagnostic in enumerate(analysis_items)
            if diagnostic.span is not None
        }
        diagnostics_html = build_diagnostics_html(
            self.current_analysis,
            source_text=self.current_document.text,
        )
        if diagnostics_html is None:
            self.analysis_diagnostics_view.setPlainText(
                self._analysis_empty_state_text()
            )
        else:
            self.analysis_diagnostics_view.setHtml(diagnostics_html)
        self._refresh_analysis_sidebar()
        self._sync_workspace_tab_attention(
            self.analysis_tab,
            mark_attention=mark_attention,
            clear_attention=clear_attention,
        )

    def _refresh_analysis_sidebar(self) -> None:
        widgets = self._analysis_sidebar_widgets
        if widgets is None:
            return
        summary_lines = build_analysis_summary_lines(
            self.current_analysis,
            analysis_stale=self._analysis_stale,
            source_text=self.current_document.text,
        )
        self._set_plain_text(widgets.summary_view, "\n".join(summary_lines))
        diagnostics_html = build_diagnostics_html(
            self.current_analysis,
            source_text=self.current_document.text,
        )
        if diagnostics_html is None:
            widgets.diagnostics_view.setPlainText(self._analysis_empty_state_text())
        else:
            widgets.diagnostics_view.setHtml(diagnostics_html)
        header_state_text, header_count_text, header_style = self._analysis_sidebar_header_status()
        widgets.header_state_label.setText(header_state_text)
        widgets.header_state_label.setStyleSheet(header_style)
        widgets.header_count_label.setText(header_count_text)
        if self.current_analysis is None:
            widgets.status_label.setText("Run Analyze.")
        elif self._analysis_stale:
            widgets.status_label.setText("Stale. Run Analyze.")
        else:
            diagnostic_count = len(self.current_analysis.diagnostics.items)
            widgets.status_label.setText(
                f"Current. {diagnostic_count} diagnostic{'s' if diagnostic_count != 1 else ''}."
            )

    def _analysis_sidebar_header_status(self) -> tuple[str, str, str]:
        if self.current_analysis is None:
            return (
                "not run",
                "0 diagnostics",
                self._analysis_sidebar_header_stylesheet("#7f8a96", "rgba(127, 138, 150, 0.16)"),
            )

        syntax_errors = len(self.current_analysis.syntax_diagnostics.items)
        semantic_errors = len(self.current_analysis.semantic_diagnostics.items)
        total_errors = len(self.current_analysis.diagnostics.items)

        if self._analysis_stale:
            return (
                "stale",
                self._analysis_sidebar_diagnostic_count_text(total_errors, syntax_errors, semantic_errors),
                self._analysis_sidebar_header_stylesheet("#8a6d3b", "rgba(186, 136, 20, 0.18)"),
            )

        if syntax_errors > 0:
            return (
                "syntax failed",
                self._analysis_sidebar_diagnostic_count_text(total_errors, syntax_errors, semantic_errors),
                self._analysis_sidebar_header_stylesheet("#a94442", "rgba(211, 47, 47, 0.16)"),
            )

        if semantic_errors > 0:
            return (
                "semantic failed",
                self._analysis_sidebar_diagnostic_count_text(total_errors, syntax_errors, semantic_errors),
                self._analysis_sidebar_header_stylesheet("#8e5b00", "rgba(249, 168, 37, 0.20)"),
            )

        return (
            "syntax passed",
            self._analysis_sidebar_diagnostic_count_text(total_errors, syntax_errors, semantic_errors),
            self._analysis_sidebar_header_stylesheet("#2f6f3e", "rgba(46, 125, 50, 0.14)"),
        )

    @staticmethod
    def _analysis_sidebar_header_stylesheet(foreground: str, background: str) -> str:
        return (
            f"padding: 2px 8px; border-radius: 999px; background: {background};"
            f"color: {foreground}; font-size: 10px; font-weight: 600; text-transform: uppercase;"
        )

    @staticmethod
    def _analysis_sidebar_diagnostic_count_text(
        total_count: int,
        syntax_errors: int,
        semantic_errors: int,
    ) -> str:
        if total_count == 0:
            return "0 diagnostics"

        parts: list[str] = []
        if syntax_errors > 0:
            parts.append(
                f"{syntax_errors} syntax error{'s' if syntax_errors != 1 else ''}"
            )
        if semantic_errors > 0:
            parts.append(
                f"{semantic_errors} semantic error{'s' if semantic_errors != 1 else ''}"
            )
        if not parts:
            return f"{total_count} diagnostic{'s' if total_count != 1 else ''}"
        return ", ".join(parts)

    def _refresh_diagnostics(
        self,
        *,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        diagnostics_html = build_diagnostics_html(None, live_lines=self._diagnostics_live_lines)
        if diagnostics_html is None:
            self.diagnostics_view.setPlainText("<none>")
        else:
            self.diagnostics_view.setHtml(diagnostics_html)
        self._update_diagnostics_clear_button_state()
        if self._diagnostics_live_lines:
            self._scroll_diagnostics_to_end()
        self._sync_workspace_tab_attention(
            self.diagnostics_tab,
            mark_attention=mark_attention,
            clear_attention=clear_attention,
        )

    def _analysis_empty_state_text(self) -> str:
        if self.current_analysis is None:
            return "No analysis yet. Click Analyze to scan the current editor text."
        return "No analysis diagnostics found. The script parsed cleanly."

    def _refresh_playback_output(
        self,
        *,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        self._set_plain_text(
            self.playback_output_view,
            build_playback_output_text(self._current_playback_result),
        )
        self._sync_workspace_tab_attention(
            self.playback_output_view,
            mark_attention=mark_attention,
            clear_attention=clear_attention,
        )

    def _refresh_debug_output(self) -> None:
        if self._debug_session_is_active():
            return
        self._reset_debug_tab()

    def _debug_session_is_active(self) -> bool:
        return self._debug_session_thread is not None and self._debug_session_thread.is_alive()

    def _append_debug_output_line(self, line: str) -> None:
        self.debug_event_log_view.appendPlainText(line)
        cursor = self.debug_event_log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.debug_event_log_view.setTextCursor(cursor)
        self.debug_event_log_view.ensureCursorVisible()

    def _append_debug_event(self, event: object) -> None:
        if not isinstance(event, DebugEvent):
            return
        self._append_debug_output_line(self._format_debug_event(event))
        self._refresh_debug_snapshot()
        if event.kind == "session_started":
            self._show_debug_sidebar_for_debugging()
        elif event.kind == "stopped":
            self._schedule_debug_tab_focus()

    def _append_debug_message(self, message: str) -> None:
        text = message.strip()
        if not text:
            return
        self._append_debug_output_line(text)

    def _on_debug_session_finished(self, status: str) -> None:
        self._refresh_debug_snapshot()
        snapshot = self._current_debug_session_state()
        if status == "failed" and snapshot is not None and snapshot.last_exception:
            self._last_debug_session_outcome = f"failed: {snapshot.last_exception}"
        else:
            self._last_debug_session_outcome = status
        self._debug_session_thread = None
        self._debug_session_handle = None
        self._debug_session_stop_event = None
        self._sync_editor_source_state(None)
        self._update_debugger_controls_state(active=False)
        if not self._pending_debug_restart:
            self._restore_debug_tab_visibility_after_debugging()
        self._update_script_action_state()
        self._update_activity_indicator()
        self._refresh_summary()
        if self._pending_debug_restart:
            self._pending_debug_restart = False
            QTimer.singleShot(0, self._start_debug_session)
        if status == "completed":
            self._update_status("Debug session finished")
        elif status == "stopped":
            self._update_status("Debug session stopped")
        else:
            self._update_status("Debug session failed")

    def _ensure_debug_tab_visible_for_debugging(self) -> None:
        if self.committed_settings_bundle.application.show_debug_tab:
            return
        if self._debug_session_previous_show_debug_tab is None:
            self._debug_session_previous_show_debug_tab = False
        self.committed_settings_bundle.application.show_debug_tab = True
        if self._preferences_dialog is not None:
            self._preferences_dialog.set_debug_tab_visible(True)
        self._set_settings_dirty(True, reason="debug session enabled Debugger visibility")
        self._update_workspace_tab_visibility()
        self._update_window_title()

    def _show_debug_sidebar_for_debugging(self) -> None:
        if not hasattr(self, "summary_dock"):
            return
        self._request_sidebar("debug", user_initiated=False, auto_hidden=True)

    def _restore_debug_tab_visibility_after_debugging(self) -> None:
        previous_show_debug_tab = self._debug_session_previous_show_debug_tab
        self._debug_session_previous_show_debug_tab = None
        if previous_show_debug_tab is None:
            return
        self.committed_settings_bundle.application.show_debug_tab = previous_show_debug_tab
        if self._preferences_dialog is not None:
            self._preferences_dialog.set_debug_tab_visible(previous_show_debug_tab)
            settings_dirty = self._preferences_dialog.is_dirty()
        else:
            settings_dirty = False
        self._set_settings_dirty(
            settings_dirty,
            reason="debug session restored Debugger visibility",
        )
        self._update_workspace_tab_visibility()
        self._update_window_title()

    def _refresh_debug_snapshot(self) -> None:
        snapshot = self._current_debug_session_state()
        if snapshot is None:
            self._sync_editor_source_state(None)
            self._update_debugger_controls_state(active=False)
            self._update_activity_indicator()
            self._refresh_summary()
            return

        self._sync_editor_source_state(snapshot.current_line)
        snapshot_breakpoints = set(snapshot.breakpoints)
        if self.editor.debugBreakpointLines() != snapshot_breakpoints:
            with QSignalBlocker(self.editor):
                self.editor.setDebugBreakpoints(snapshot_breakpoints)
        self._update_breakpoint_action_affordances()
        self._ensure_debug_tab_visible_for_debugging()
        session_state = snapshot.state
        pause_summary = self._debug_pause_summary(snapshot)
        if session_state == "paused":
            status_text = self._title_case_pause_summary(pause_summary) if pause_summary else "Paused"
            self._set_debug_status_indicator("paused", status_text, "#f59e0b")
        elif session_state == "running":
            self._set_debug_status_indicator("running", "Running", "#2e7d32")
        else:
            self._set_debug_status_indicator(session_state, session_state.capitalize(), "#9ea7af")

        self._populate_debug_call_stack(snapshot.call_stack)
        self._populate_debug_variables(snapshot)
        self._refresh_debug_watch_list(snapshot)
        self._update_debugger_controls_state(active=session_state in {"running", "paused"})
        self._update_activity_indicator()
        self._refresh_summary()

    def _current_debug_session_state(self):
        handle = self._debug_session_handle
        if handle is None:
            return None
        return handle.controller.snapshot()

    def _populate_debug_call_stack(self, frames) -> None:
        self.debug_call_stack_tree.clear()
        for depth, frame in enumerate(frames, start=1):
            item = QTreeWidgetItem(
                [
                    str(depth),
                    frame.function_name,
                    str(frame.source_line) if frame.source_line is not None else "-",
                ]
            )
            self.debug_call_stack_tree.addTopLevelItem(item)
        self.debug_call_stack_tree.resizeColumnToContents(0)
        self.debug_call_stack_tree.resizeColumnToContents(1)
        self.debug_call_stack_tree.resizeColumnToContents(2)
        self._refresh_debug_tree_empty_states()

    def _format_debug_value(self, value: object) -> str:
        return format_debugger_value(value, max_length=120)

    def _populate_debug_variables(self, snapshot) -> None:
        self.debug_variables_tree.clear()
        special_values = getattr(snapshot, "special_values", None) or {}
        special_items: list[tuple[str, object, str]] = []
        if isinstance(special_values, dict):
            for name, value in special_values.items():
                if not isinstance(name, str) or not name.strip():
                    continue
                special_items.append(
                    (
                        f"@{name.strip()}",
                        value,
                        describe_debugger_value_type(value),
                    )
                )

        special_group = self._build_debug_variable_group(
            f"Runtime Values (read-only, {len(special_items)})"
        )
        for name, value, type_name in special_items:
            self._add_debug_variable_item(special_group, name, value, type_name)

        user_variables = getattr(snapshot, "variables", None) or []
        user_group = self._build_debug_variable_group(
            f"User Variables ({len(user_variables)})"
        )
        for variable in user_variables:
            self._add_debug_variable_item(
                user_group,
                variable.name,
                variable.value,
                variable.type_name,
            )

        for group in (special_group, user_group):
            if group.childCount() > 0:
                self.debug_variables_tree.addTopLevelItem(group)
                group.setExpanded(True)

        self.debug_variables_tree.resizeColumnToContents(0)
        self.debug_variables_tree.resizeColumnToContents(1)
        self.debug_variables_tree.resizeColumnToContents(2)
        self._refresh_debug_tree_empty_states()

    def _build_debug_variable_group(self, title: str) -> QTreeWidgetItem:
        group = QTreeWidgetItem([title, "", ""])
        group.setFirstColumnSpanned(True)
        group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        return group

    def _add_debug_variable_item(
        self,
        group: QTreeWidgetItem,
        name: str,
        value: object,
        type_name: str,
    ) -> None:
        item = QTreeWidgetItem(
            [
                name,
                self._format_debug_value(value),
                type_name,
            ]
        )
        group.addChild(item)

    def _debug_watch_context(self, snapshot) -> ExecutionContext:
        context = ExecutionContext()
        if snapshot is None:
            return context

        variables = getattr(snapshot, "variables", None) or []
        for variable in variables:
            name = getattr(variable, "name", None)
            if isinstance(name, str) and name.strip():
                context.set_global(name, getattr(variable, "value", None))

        special_values = getattr(snapshot, "special_values", None) or {}
        if isinstance(special_values, dict):
            for name, value in special_values.items():
                if isinstance(name, str) and name.strip():
                    context.set_special_value(name, value)

        frames = getattr(snapshot, "call_stack", None) or []
        if frames:
            top_frame = frames[-1]
            locals_dict: dict[str, object] = {}
            for variable in getattr(top_frame, "locals", None) or []:
                name = getattr(variable, "name", None)
                if isinstance(name, str) and name.strip():
                    locals_dict[name] = getattr(variable, "value", None)
            function_name = getattr(top_frame, "function_name", None)
            if not isinstance(function_name, str) or not function_name.strip():
                function_name = "<debug>"
            context.push_call_frame(
                function_name,
                locals_dict=locals_dict,
                line=getattr(top_frame, "source_line", None),
            )

        current_line = getattr(snapshot, "current_line", None)
        if isinstance(current_line, int) and current_line >= 1:
            context.set_current_source_line(current_line)
        return context

    def _refresh_debug_watch_list(self, snapshot) -> None:
        paused = snapshot is not None and getattr(snapshot, "state", None) == "paused"
        context = self._debug_watch_context(snapshot) if paused else None

        self._debug_watch_tree_syncing = True
        try:
            self.debug_watch_tree.clear()
            if not self._debug_watch_expressions:
                self.debug_watch_tree.resizeColumnToContents(0)
                self.debug_watch_tree.resizeColumnToContents(1)
                self.debug_watch_tree.resizeColumnToContents(2)
                self.debug_watch_tree.resizeColumnToContents(3)
                return

            for expression in self._debug_watch_expressions:
                value_text = "-"
                type_text = "-"
                status_text = "Waiting"
                if paused and context is not None:
                    try:
                        value = self._debug_watch_runtime.evaluate_debug_expression(expression, context)
                    except BaseException as exc:
                        value_text = " ".join(str(exc).split())
                        type_text = "error"
                        status_text = "Error"
                    else:
                        value_text = self._format_debug_value(value)
                        type_text = describe_debugger_value_type(value)
                        status_text = "Ready"
                item = QTreeWidgetItem([expression, value_text, type_text, status_text])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setData(0, Qt.ItemDataRole.UserRole, expression)
                self.debug_watch_tree.addTopLevelItem(item)

            self.debug_watch_tree.resizeColumnToContents(0)
            self.debug_watch_tree.resizeColumnToContents(1)
            self.debug_watch_tree.resizeColumnToContents(2)
            self.debug_watch_tree.resizeColumnToContents(3)
            self._refresh_debug_tree_empty_states()
        finally:
            self._debug_watch_tree_syncing = False

    def _refresh_debug_tree_empty_states(self) -> None:
        for stack, tree in (
            (getattr(self, "debug_variables_stack", None), getattr(self, "debug_variables_tree", None)),
            (getattr(self, "debug_call_stack_stack", None), getattr(self, "debug_call_stack_tree", None)),
            (getattr(self, "debug_watch_stack", None), getattr(self, "debug_watch_tree", None)),
        ):
            if stack is None or tree is None:
                continue
            stack.setCurrentIndex(1 if tree.topLevelItemCount() > 0 else 0)

    def _add_debug_watch_expression(self) -> None:
        expression = self.debug_watch_expression_edit.text().strip()
        if not expression:
            return
        self._debug_watch_expressions.append(expression)
        self.debug_watch_expression_edit.clear()
        self._refresh_debug_watch_list(self._current_debug_session_state())

    def _remove_selected_debug_watch_expression(self) -> None:
        current_item = self.debug_watch_tree.currentItem()
        if current_item is None:
            return
        index = self.debug_watch_tree.indexOfTopLevelItem(current_item)
        if index < 0 or index >= len(self._debug_watch_expressions):
            return
        del self._debug_watch_expressions[index]
        self._refresh_debug_watch_list(self._current_debug_session_state())

    def _on_debug_watch_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._debug_watch_tree_syncing or column != 0:
            return

        index = self.debug_watch_tree.indexOfTopLevelItem(item)
        if index < 0 or index >= len(self._debug_watch_expressions):
            return

        new_expression = item.text(0).strip()
        if not new_expression:
            self._debug_watch_tree_syncing = True
            try:
                item.setText(0, self._debug_watch_expressions[index])
            finally:
                self._debug_watch_tree_syncing = False
            return

        self._debug_watch_expressions[index] = new_expression
        self._refresh_debug_watch_list(self._current_debug_session_state())

    def _sync_editor_source_state(self, current_line: int | None) -> None:
        if current_line is None:
            self.editor.clearHighlightedLine()
            if hasattr(self, "debug_reveal_source_button"):
                self.debug_reveal_source_button.setEnabled(False)
            return
        self.editor.setDebugCurrentLine(current_line)
        if hasattr(self, "debug_reveal_source_button"):
            self.debug_reveal_source_button.setEnabled(True)

    def _reveal_debug_source_in_editor(self) -> None:
        current_line = self.editor.highlightedLine()
        if current_line is None:
            snapshot = self._current_debug_session_state()
            if snapshot is not None:
                current_line = snapshot.current_line
        if current_line is None:
            return

        self._go_to_line(current_line)
        self.workspace_tabs.setCurrentWidget(self.editor)

    def _schedule_debug_tab_focus(self) -> None:
        QTimer.singleShot(0, self._focus_debug_tab_if_requested)

    def _focus_debug_tab_if_requested(self) -> None:
        if not self.committed_settings_bundle.application.open_debug_tab_on_pause:
            return
        snapshot = self._current_debug_session_state()
        if snapshot is None:
            return
        if self._debug_session_handle is None:
            return
        self._show_debug_sidebar_for_debugging()

    def _debug_paused_function_name_and_depth(self, snapshot) -> tuple[str | None, int | None]:
        frames = getattr(snapshot, "call_stack", None)
        if not frames:
            return None, None
        stack_depth = len(frames)
        last_frame = frames[-1]
        function_name = getattr(last_frame, "function_name", None)
        if isinstance(function_name, str):
            function_name = function_name.strip()
            return (function_name or None, stack_depth)
        return None, stack_depth

    def _debug_pause_summary(self, snapshot) -> str:
        pause_reason = getattr(snapshot, "pause_reason", None)
        reason_text = self._debug_pause_reason_text(pause_reason)
        function_name, stack_depth = self._debug_paused_function_name_and_depth(snapshot)
        line_text = str(snapshot.current_line) if getattr(snapshot, "current_line", None) is not None else "?"
        if pause_reason is None:
            if function_name:
                if stack_depth is not None:
                    return f"paused in {function_name} (depth {stack_depth}) at line {line_text}"
                return f"paused in {function_name} at line {line_text}"
            return f"paused at line {line_text}"
        if function_name:
            if stack_depth is not None:
                return f"paused on {reason_text} in {function_name} (depth {stack_depth}) at line {line_text}"
            return f"paused on {reason_text} in {function_name} at line {line_text}"
        return f"paused on {reason_text} at line {line_text}"

    def _title_case_pause_summary(self, summary: str) -> str:
        if not summary:
            return summary
        return summary[0].upper() + summary[1:]

    def _debug_pause_reason_text(self, pause_reason: object) -> str:
        if pause_reason == "breakpoint":
            return "Breakpoint"
        if pause_reason == "step":
            return "step"
        if pause_reason == "step_over":
            return "Step Over"
        if pause_reason == "step_out":
            return "Step Out"
        if pause_reason == "exception":
            return "Exception"
        if pause_reason is None:
            return "Paused"
        return str(pause_reason).replace("_", " ").title()

    def _update_debugger_controls_state(self, *, active: bool) -> None:
        self._update_debug_stop_icon(active)
        self.debug_step_button.setEnabled(active)
        self.debug_step_over_button.setEnabled(active)
        self.debug_step_out_button.setEnabled(active)
        self.debug_continue_button.setEnabled(active)
        self.debug_pause_button.setEnabled(active)
        self.debug_restart_button.setEnabled(active)
        self.restart_debug_menu_action.setEnabled(active)
        self.debug_stop_button.setEnabled(active)
        self.debug_step_into_action.setEnabled(active)
        self.debug_step_over_action.setEnabled(active)
        self.debug_step_out_action.setEnabled(active)
        self.debug_continue_action.setEnabled(active)
        self.debug_pause_action.setEnabled(active)
        self.debug_restart_action.setEnabled(active)
        self.debug_stop_action.setEnabled(active)

    def _set_debug_status_indicator(self, state: str, tooltip: str, color: str) -> None:
        display_tooltip = tooltip
        display_label = {
            "idle": "Idle",
            "running": "Running",
            "paused": "Paused",
        }.get(state, state.capitalize())
        for indicator in (
            getattr(self, "debug_status_indicator", None),
            getattr(self, "debugger_controls_status_indicator", None),
        ):
            if indicator is None:
                continue
            indicator.setToolTip(display_tooltip)
            indicator.setStatusTip(display_tooltip)
            indicator.setStyleSheet(self._debug_status_indicator_stylesheet(color))
        status_label = getattr(self, "debug_status_text_label", None)
        if status_label is not None:
            status_label.setText(display_label)

    def _update_debug_stop_icon(self, active: bool) -> None:
        icon_name = "ph.stop-fill" if active else "ph.stop-light"
        icon = self._file_action_icon(icon_name)
        self.debug_stop_button.setIcon(icon)
        self.debug_stop_action.setIcon(icon)

    def _reset_debug_tab(self) -> None:
        self._pending_debug_restart = False
        self._sync_editor_source_state(None)
        self.debug_call_stack_tree.clear()
        self.debug_variables_tree.clear()
        self._refresh_debug_watch_list(None)
        self.debug_event_log_view.clear()
        self._set_debug_status_indicator("idle", "Idle", "#9ea7af")
        self._update_debugger_controls_state(active=False)
        self._update_activity_indicator()

    def _format_debug_event(self, event: DebugEvent) -> str:
        parts = [f"[{event.kind}]"]
        if event.line is not None:
            parts.append(f"line={event.line}")
        if event.function_name:
            parts.append(f"function={event.function_name}")
        if event.pause_reason:
            parts.append(f"reason={event.pause_reason}")
        if event.message:
            parts.append(f"message={event.message}")
        if event.payload:
            parts.append(f"payload={event.payload}")
        return " ".join(parts)

    def _refresh_raw_recording_output(
        self,
        *,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        self._set_plain_text(
            self.raw_recording_view,
            build_raw_recording_text(getattr(self, "_current_recording_session", None)),
        )
        self._sync_workspace_tab_attention(
            self.raw_recording_view,
            mark_attention=mark_attention,
            clear_attention=clear_attention,
        )

    def _refresh_preview(
        self,
        *,
        force_format: bool = False,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        if force_format or not self._last_preview_text:
            self._last_preview_text = self.services.formatting_service.format_document(
                self.current_document
            )
        self._set_plain_text(
            self.preview_view,
            build_formatted_preview_text(self._last_preview_text),
        )
        self._sync_workspace_tab_attention(
            self.preview_view,
            mark_attention=mark_attention,
            clear_attention=clear_attention,
        )

    def _refresh_all_views(self) -> None:
        self._loading_document = True
        try:
            self.editor.setPlainText(self.current_document.text)
            self.editor.clearDebugBreakpoints()
        finally:
            self._loading_document = False
        self._current_playback_result = None
        self._current_recording_session = None
        self._refresh_summary()
        self._refresh_analysis(clear_attention=True)
        self._refresh_diagnostics(clear_attention=True)
        self._refresh_playback_output(clear_attention=True)
        self._refresh_debug_output()
        self._refresh_preview(force_format=True, clear_attention=True)
        self._refresh_raw_recording_output(clear_attention=True)
        self._update_editor_status_details()
        self._update_status("Ready")

    def _sync_saved_document_text(self) -> None:
        self._saved_document_text = self.current_document.text

    def _update_status(self, message: str) -> None:
        path = str(self.current_path) if self.current_path is not None else "<unsaved>"
        dirty = "dirty" if (self._editor_dirty or self.current_document.is_dirty) else "saved"
        dirty_marker = "* " if self.has_unsaved_changes() else ""
        self._update_status_style(dirty == "dirty")
        self.statusBar().showMessage(
            f"{dirty_marker}{message} | {path} | {dirty} | v{self.current_document.version.value}"
        )

    def _update_window_title(self) -> None:
        is_dirty = self.has_unsaved_changes()
        if self.current_path is None and not is_dirty:
            self.setWindowTitle(self._base_window_title)
            return

        document_label = self.current_path.name if self.current_path is not None else "New"
        prefix = "*" if is_dirty else ""
        self.setWindowTitle(f"{self._base_window_title} - {prefix}{document_label}")

    def _update_workspace_tab_labels(self) -> None:
        editor_is_dirty = self.has_unsaved_changes()
        editor_label = "* Editor" if editor_is_dirty else "Editor"
        self.workspace_tabs.setTabText(0, editor_label)
        dirty_indicators = self._preferences.appearance.dirty_indicators
        self.workspace_tabs.tabBar().setTabTextColor(
            0, QColor(dirty_indicators.accent) if editor_is_dirty else QColor()
        )

    def _sync_workspace_tab_attention_colors(self) -> None:
        attention = self._preferences.appearance.workspace_tab_attention
        self._workspace_tab_bar.set_attention_settings(
            enabled=attention.enabled,
            accent_color=attention.accent,
        )

    def _on_workspace_tab_changed(self, index: int) -> None:
        self._workspace_tab_bar.clear_tab_attention(index)

    def _sync_workspace_tab_attention(
        self,
        widget: QWidget,
        *,
        mark_attention: bool = False,
        clear_attention: bool = False,
    ) -> None:
        index = self.workspace_tabs.indexOf(widget)
        if index < 0:
            return

        if not self.workspace_tabs.isTabVisible(index):
            self._workspace_tab_bar.clear_tab_attention(index)
            return

        if self.workspace_tabs.currentIndex() == index:
            self._workspace_tab_bar.clear_tab_attention(index)
            return

        if not self._preferences.appearance.workspace_tab_attention.enabled:
            if clear_attention:
                self._workspace_tab_bar.clear_tab_attention(index)
            return

        if mark_attention:
            self._workspace_tab_bar.set_tab_attention(index, True)
        elif clear_attention:
            self._workspace_tab_bar.clear_tab_attention(index)

    def _update_workspace_tab_visibility(self) -> None:
        self._update_debug_tab_visibility()
        self._update_analysis_tab_visibility()
        self._update_formatted_preview_tab_visibility()
        self._update_raw_recording_tab_visibility()
        self._update_diagnostics_tab_visibility()
        self._update_hidden_workspace_tabs_strip()

    def _update_analysis_tab_visibility(self) -> None:
        analysis_index = self.workspace_tabs.indexOf(self.analysis_tab)
        if analysis_index < 0:
            return

        visible = bool(self.committed_settings_bundle.application.show_analysis_tab)
        current_index = self.workspace_tabs.currentIndex()
        self.workspace_tabs.setTabVisible(analysis_index, visible)
        if visible:
            return

        if current_index == analysis_index:
            self.workspace_tabs.setCurrentIndex(0)
        self._workspace_tab_bar.clear_tab_attention(analysis_index)

    def _update_debug_tab_visibility(self) -> None:
        self._set_sidebar_mode_button_visible("debug", bool(self.committed_settings_bundle.application.show_debug_tab))

    def _update_formatted_preview_tab_visibility(self) -> None:
        preview_index = self.workspace_tabs.indexOf(self.preview_view)
        if preview_index < 0:
            return

        visible = bool(self.committed_settings_bundle.application.show_formatted_preview_tab)
        current_index = self.workspace_tabs.currentIndex()
        self.workspace_tabs.setTabVisible(preview_index, visible)
        if visible:
            return

        if current_index == preview_index:
            self.workspace_tabs.setCurrentIndex(0)
        self._workspace_tab_bar.clear_tab_attention(preview_index)

    def _update_raw_recording_tab_visibility(self) -> None:
        raw_index = self.workspace_tabs.indexOf(self.raw_recording_view)
        if raw_index < 0:
            return

        visible = bool(self.committed_settings_bundle.application.show_raw_recordings_tab)
        current_index = self.workspace_tabs.currentIndex()
        self.workspace_tabs.setTabVisible(raw_index, visible)
        if visible:
            return

        if current_index == raw_index:
            self.workspace_tabs.setCurrentIndex(0)
        self._workspace_tab_bar.clear_tab_attention(raw_index)

    def _update_diagnostics_tab_visibility(self) -> None:
        diagnostics_index = self.workspace_tabs.indexOf(self.diagnostics_tab)
        if diagnostics_index < 0:
            return

        visible = bool(self.committed_settings_bundle.application.show_diagnostics_tab)
        current_index = self.workspace_tabs.currentIndex()
        self.workspace_tabs.setTabVisible(diagnostics_index, visible)
        if visible:
            return

        if current_index == diagnostics_index:
            self.workspace_tabs.setCurrentIndex(0)
        self._workspace_tab_bar.clear_tab_attention(diagnostics_index)

    def _workspace_tab_specs(self) -> tuple[tuple[QWidget, str, bool], ...]:
        return (
            (self.editor, "Editor", False),
            (self.playback_output_view, "Playback Output", True),
            (self.analysis_tab, "Analysis", True),
            (self.preview_view, "Formatted Preview", True),
            (self.raw_recording_view, "Raw Recordings", True),
            (self.diagnostics_tab, "Diagnostics", True),
        )

    def _configure_workspace_tab_close_buttons(self) -> None:
        editor_index = self.workspace_tabs.indexOf(self.editor)
        if editor_index < 0:
            return

        self.workspace_tabs.tabBar().setTabButton(
            editor_index,
            QTabBar.ButtonPosition.RightSide,
            None,
        )

    def _handle_workspace_tab_close_requested(self, index: int) -> None:
        widget = self.workspace_tabs.widget(index)
        if widget is None or widget is self.editor:
            return

        self._set_workspace_tab_visible(widget, False)

    def _set_workspace_tab_visible(self, widget: QWidget, visible: bool) -> None:
        index = self.workspace_tabs.indexOf(widget)
        if index < 0:
            return
        if widget is self.editor and not visible:
            return

        current_widget = self.workspace_tabs.currentWidget()
        self.workspace_tabs.setTabVisible(index, visible)
        if not visible and current_widget is widget:
            self._focus_first_visible_workspace_tab()
        if not visible:
            self._workspace_tab_bar.clear_tab_attention(index)
        self._update_hidden_workspace_tabs_strip()

    def _focus_first_visible_workspace_tab(self) -> None:
        for widget, _, _ in self._workspace_tab_specs():
            index = self.workspace_tabs.indexOf(widget)
            if index >= 0 and self.workspace_tabs.isTabVisible(index):
                self.workspace_tabs.setCurrentIndex(index)
                return

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_hidden_workspace_tabs_strip_collapsed(self, collapsed: bool) -> None:
        collapsed = bool(collapsed)
        if self.hidden_workspace_tabs_strip_collapsed == collapsed:
            return
        self.hidden_workspace_tabs_strip_collapsed = collapsed
        self.committed_settings_bundle.application.hidden_workspace_tabs_strip_collapsed = collapsed
        if self._preferences_dialog is not None:
            self._preferences_dialog.set_hidden_workspace_tabs_strip_collapsed(collapsed)
        try:
            self._settings_service.save(copy.deepcopy(self.committed_settings_bundle), force=True)
        except Exception as exc:
            window_log.exception(
                "Hidden tab selections strip state save failed",
                exc,
                event_id="desktop.window.hidden_tabs_strip_save_failed",
            )
        self._update_hidden_workspace_tabs_strip()

    def _update_hidden_workspace_tabs_strip(self) -> None:
        if not hasattr(self, "hidden_workspace_tabs_buttons_layout"):
            return

        self._clear_layout(self.hidden_workspace_tabs_buttons_layout)
        hidden_tabs: list[tuple[QWidget, str]] = []
        for widget, label, closable in self._workspace_tab_specs():
            if not closable:
                continue
            index = self.workspace_tabs.indexOf(widget)
            if index >= 0 and not self.workspace_tabs.isTabVisible(index):
                hidden_tabs.append((widget, label))

        for widget, label in hidden_tabs:
            button = QToolButton()
            button.setObjectName(f"restore{label.replace(' ', '')}TabButton")
            button.setAutoRaise(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.clicked.connect(
                lambda checked=False, tab_widget=widget: self._set_workspace_tab_visible(
                    tab_widget, True
                )
            )
            self.hidden_workspace_tabs_buttons_layout.addWidget(button)

        self.hidden_workspace_tabs_buttons_layout.addStretch(1)
        has_hidden_tabs = bool(hidden_tabs)
        collapsed = self.hidden_workspace_tabs_strip_collapsed and has_hidden_tabs
        self.hidden_workspace_tabs_collapse_button.setVisible(has_hidden_tabs and not collapsed)
        self.hidden_workspace_tabs_label.setVisible(has_hidden_tabs and not collapsed)
        self.hidden_workspace_tabs_buttons_host.setVisible(has_hidden_tabs and not collapsed)
        self.hidden_workspace_tabs_expand_button.setVisible(has_hidden_tabs and collapsed)
        self.hidden_workspace_tabs_strip.setVisible(has_hidden_tabs)
        self._update_hidden_workspace_tabs_action_label(has_hidden_tabs, collapsed)

    def _update_status_style(self, is_dirty: bool) -> None:
        if is_dirty:
            accent = self._preferences.appearance.dirty_indicators.accent
            self.statusBar().setStyleSheet(f"QStatusBar {{ color: {accent}; }}")
        else:
            self.statusBar().setStyleSheet("")

    def _set_editor_dirty(self, dirty: bool, *, reason: str) -> None:
        dirty = bool(dirty)
        previous = self._editor_dirty
        self._editor_dirty = dirty
        if previous == dirty:
            return

        editor_log.trace(
            "Editor dirty state changed",
            event_id="desktop.editor.dirty_state_changed",
            reason=reason,
            editor_dirty=dirty,
            document_dirty=self.current_document.is_dirty,
            has_unsaved_changes=self.has_unsaved_changes(),
            current_path=str(self.current_path) if self.current_path is not None else None,
        )

    def _set_settings_dirty(self, dirty: bool, *, reason: str) -> None:
        _ = reason
        self._settings_dirty = bool(dirty)

    def _build_status_detail_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("statusDetailLabel")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(
            "QLabel#statusDetailLabel {"
            " padding: 0 6px;"
            " color: #5b6470;"
            " }"
        )
        return label

    def _build_activity_indicator(self) -> QLabel:
        indicator = QLabel()
        indicator.setObjectName("activityIndicator")
        indicator.setFixedSize(14, 14)
        indicator.setToolTip("Idle")
        indicator.setStatusTip("Idle")
        indicator.setStyleSheet(
            "QLabel#activityIndicator {"
            " border: 1px solid #222222;"
            " border-radius: 7px;"
            " background-color: #111111;"
            " }"
        )
        return indicator

    def _update_activity_indicator(self) -> None:
        snapshot = self._current_debug_session_state()
        if snapshot is not None and snapshot.state in {"running", "paused"}:
            if snapshot.state == "paused":
                tooltip = self._title_case_pause_summary(self._debug_pause_summary(snapshot))
                border_color = "#8a5f00"
                color = "#f59e0b"
            else:
                tooltip = "Running"
                border_color = "#0d3b1f"
                color = "#2e7d32"
            self._set_activity_indicator(tooltip, border_color, color)
            return

        kind = self.script_controller.current_operation_kind
        if kind == "record":
            self._set_activity_indicator("Recording", "#5a1010", "#d32f2f")
            return

        if kind == "play":
            self._set_activity_indicator("Playback", "#1a6b1a", "#39ff14")
            return

        self._set_activity_indicator("Idle", "#222222", "#111111")

    def _set_activity_indicator(self, tooltip: str, border_color: str, color: str) -> None:
        self._recording_playback_indicator.setToolTip(tooltip)
        self._recording_playback_indicator.setStatusTip(tooltip)
        self._recording_playback_indicator.setStyleSheet(
            "QLabel#activityIndicator {"
            f" border: 1px solid {border_color};"
            " border-radius: 7px;"
            f" background-color: {color};"
            " }"
        )

    def _current_event_count(self) -> int:
        if self.current_document.source_action_count is not None:
            return max(0, int(self.current_document.source_action_count))

        if self.current_analysis is not None and not self._analysis_stale:
            root = self.current_analysis.root
            statements = getattr(root, "statements", None)
            if statements is not None:
                return len(statements)

        return max(0, self.current_document.line_count())

    def _update_editor_status_details(self) -> None:
        cursor = self.editor.textCursor()
        line_count = self.current_document.line_count()
        line_number = cursor.blockNumber() + 1
        column_number = cursor.positionInBlock() + 1
        char_position = cursor.position() + 1
        self._editor_status_label.setText(
            f"Lines: {line_count} | Ln: {line_number} | Col: {column_number} | Ch: {char_position}"
        )
        self._events_status_label.setText(f"Events: {self._current_event_count()}")

    def _update_script_action_state(self) -> None:
        script_active = self.script_controller.is_active
        debug_active = self._debug_session_is_active()
        active = script_active or debug_active
        recording_active = self.script_controller.current_operation_kind == "record"
        self.play_script_action.setEnabled(not active)
        self.preview_play_script_action.setEnabled(not active)
        self.record_script_action.setEnabled(not active)
        self.stop_script_action.setEnabled(script_active or debug_active)
        self.debugger_action.setEnabled(not active)
        self.run_debug_menu_action.setEnabled(not active)
        self.editor.setEnabled(not recording_active)
        self.editor.set_mutations_locked(recording_active)
        self._update_editor_edit_action_affordances()
        self._update_search_action_affordances()
        self._update_debugger_controls_state(active=debug_active)

    def _on_editor_text_changed(self) -> None:
        if self._loading_document:
            return
        text = self.editor.toPlainText()
        if text != self.current_document.text:
            self.services.document_service.update_text(self.current_document, text)

        if text == self._saved_document_text:
            if self.current_document.is_dirty:
                self.services.document_service.mark_saved(self.current_document)
            self._set_editor_dirty(False, reason="editor text matched saved document")
        else:
            self._set_editor_dirty(True, reason="editor text diverged from saved document")
            self._current_playback_result = None
            self._refresh_playback_output(clear_attention=True)

        self._analysis_stale = True
        self._refresh_summary()
        self._refresh_analysis()
        self._update_editor_status_details()
        self._update_status("Unsaved editor changes; analysis is stale until you click Analyze")
        self._update_window_title()
        self._update_workspace_tab_labels()

    def _on_breakpoints_changed(self) -> None:
        has_breakpoints = bool(self.editor.debugBreakpointLines())
        self.clear_breakpoints_action.setEnabled(has_breakpoints)
        self._update_breakpoint_action_affordances()
        handle = self._debug_session_handle
        if handle is not None and hasattr(handle.controller, "set_breakpoints"):
            handle.controller.set_breakpoints(sorted(self.editor.debugBreakpointLines()))
            self._refresh_debug_snapshot()
        self._update_status("Breakpoints updated")

    def editor_undo(self) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        self.editor.undo()

    def editor_redo(self) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        self.editor.redo()

    def editor_cut(self) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        self.editor.cut()

    def editor_copy(self) -> None:
        self.editor.copy()

    def editor_paste(self) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        self.editor.paste()

    def editor_delete_selection(self) -> None:
        if self.script_controller.current_operation_kind == "record":
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
            self.editor.setTextCursor(cursor)
            return
        cursor.deleteChar()
        self.editor.setTextCursor(cursor)

    def editor_select_all(self) -> None:
        self.editor.selectAll()

    def open_preferences(self) -> None:
        preferences_log.info(
            "Preferences dialog opened",
            event_id="desktop.preferences.opened",
            settings_dirty=self._settings_dirty,
        )
        if self._preferences_dialog is None:
            self._preferences_dialog = PreferencesDialog(self)
            self._preferences_dialog.saveRequested.connect(self.save_preferences)
            self._preferences_dialog.discardRequested.connect(self._discard_preferences_changes)
            self._preferences_dialog.preferencesChanged.connect(self._on_preferences_changed)
            self._preferences_dialog.hotkeysSearchTextChanged.connect(
                self._on_hotkeys_search_text_changed
            )
        self._preferences_dialog.set_preferences(copy.deepcopy(self.committed_settings_bundle))
        self._preferences_dialog.set_hotkeys_search_text(self._hotkeys_search_text)
        self._preferences_dialog.show()
        self._preferences_dialog.raise_()
        self._preferences_dialog.activateWindow()

    def apply_preferences(self, preferences: DesktopPreferences) -> None:
        self._preferences = preferences
        self._sync_workspace_tab_attention_colors()
        self.services.formatting_service.set_options(
            self._format_options_from_scripting(preferences.scripting)
        )
        self.editor.apply_preferences(preferences)
        font = preferences.font.to_qfont()
        self.summary_view.setFont(font)
        self.analysis_summary_view.setFont(font)
        self.analysis_diagnostics_view.setFont(font)
        self.diagnostics_view.setFont(font)
        self.playback_output_view.setFont(font)
        self.debugger_panel.setFont(font)
        self.preview_view.setFont(font)
        self.raw_recording_view.setFont(font)
        self._update_status_style(self.has_unsaved_changes())
        self._refresh_summary()
        self._refresh_analysis()
        self._refresh_diagnostics()
        self._refresh_preview(force_format=True)
        self._refresh_raw_recording_output()
        self._update_editor_status_details()
        self._update_workspace_tab_visibility()

    def _sync_diagnostics_log_surface(self) -> None:
        active_path = self._sync_diagnostic_logger_config()
        self.diagnostics_log_path_label.setText(f"Diagnostics log file: {active_path}")

    def _append_diagnostic_event(self, event: object) -> None:
        if not isinstance(event, DiagnosticEvent):
            return

        formatted = format_diagnostic_event(
            event,
            timestamp_format=get_diagnostic_config().timestamp_format,
        )
        self._diagnostics_live_lines.append(formatted)
        self._refresh_diagnostics(mark_attention=True)

    def _scroll_diagnostics_to_end(self) -> None:
        cursor = self.diagnostics_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.diagnostics_view.setTextCursor(cursor)
        self.diagnostics_view.ensureCursorVisible()

    def _handle_diagnostics_anchor_clicked(self, url: QUrl) -> None:
        anchor = url.toString()
        match = re.fullmatch(r"analysis-diagnostic-(\d+)", anchor)
        if match is None:
            return

        anchor_id = f"analysis-diagnostic-{match.group(1)}"
        span = self._analysis_diagnostic_spans.get(anchor_id)
        if span is None:
            return

        self._focus_diagnostic_span(span)

    def _focus_diagnostic_span(self, span: TextSpan) -> None:
        text_length = len(self.current_document.text)
        start = max(0, min(span.start, text_length))
        end = max(start + 1, min(span.end, text_length))
        self.workspace_tabs.setCurrentWidget(self.editor)
        self._select_text_range(start, end)
        self.editor.setFocus()

    def clear_diagnostics_output(self) -> None:
        self._diagnostics_live_lines.clear()
        self._refresh_diagnostics(clear_attention=True)

    def _update_diagnostics_clear_button_state(self) -> None:
        self.diagnostics_clear_button.setEnabled(bool(self._diagnostics_live_lines))

    def _sync_diagnostic_logger_config(self) -> Path:
        config = load_diagnostic_config_from_env()
        diagnostics = self.committed_settings_bundle.diagnostics
        env = os.environ

        merged = replace(
            config,
            enabled=config.enabled if "ASS_DIAGNOSTICS" in env else diagnostics.enabled,
            min_severity=(
                config.min_severity
                if "ASS_DIAGNOSTIC_MIN_SEVERITY" in env
                else diagnostics.min_severity
            ),
            max_detail=(
                config.max_detail if "ASS_DIAGNOSTIC_MAX_DETAIL" in env else diagnostics.max_detail
            ),
            log_to_stdout=(
                config.log_to_stdout if "ASS_DIAGNOSTIC_STDOUT" in env else diagnostics.log_to_stdout
            ),
            log_to_file=(
                config.log_to_file if "ASS_DIAGNOSTIC_FILE" in env else diagnostics.log_to_file
            ),
        )

        diagnostic_log_path = self.committed_settings_bundle.files.diagnostic_log_path
        if diagnostic_log_path and "ASS_DIAGNOSTIC_PATH" not in env:
            resolved_path = self._resolve_diagnostic_log_path(diagnostic_log_path)
            merged = replace(merged, log_path=resolved_path)
        set_diagnostic_config(merged)
        return resolve_diagnostic_log_path(merged)

    def _resolve_diagnostic_log_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (self._settings_service.config_dir / candidate).resolve()

    def _on_preferences_changed(self, bundle: DesktopSettingsBundle) -> None:
        self.committed_settings_bundle = copy.deepcopy(bundle)
        self.apply_preferences(bundle.theme)
        self._apply_hotkeys(bundle.application.hotkeys.bindings)
        self._debugging_service.set_runtime_settings(bundle.runtime)
        self._debugging_service.set_playback_settings(bundle.playback)
        self.script_controller.set_playback_settings(bundle.playback)
        self.script_controller.set_recording_settings(bundle.recording)
        self.script_controller.set_runtime_settings(bundle.runtime)
        self._sync_diagnostics_log_surface()
        self._apply_sidebar_visibility()
        dialog = self._preferences_dialog
        self._set_settings_dirty(
            dialog.is_dirty() if dialog is not None else True,
            reason="preferences dialog changed",
        )
        self._update_status("Preferences updated")
        self._update_window_title()
        self._update_workspace_tab_labels()
        self._update_workspace_tab_visibility()

    def _apply_hotkeys(self, bindings: dict[str, str]) -> None:
        active_bindings = default_hotkey_bindings()
        active_bindings.update(bindings)
        if "search" in bindings and "find" not in bindings:
            active_bindings["find"] = active_bindings.get("search", "")
        self._current_hotkey_bindings = active_bindings
        for definition in HOTKEY_DEFINITIONS:
            action = self._hotkey_actions.get(definition.action_id)
            if action is None:
                continue
            shortcut_text = active_bindings.get(definition.action_id, "")
            if definition.action_id == "stop":
                shortcut_text = primary_hotkey_clause(shortcut_text)
            action.setShortcut(QKeySequence(shortcut_text))
        self.script_controller.set_playback_stop_hotkey(active_bindings.get("stop", ""))
        self._update_file_action_affordances()
        self._update_search_action_affordances()
        self._update_analysis_action_affordances()
        self._update_breakpoint_action_affordances()
        self._update_debug_step_action_affordances()
        self._update_settings_action_affordances()
        self._update_playback_action_affordances()

    def _on_hotkeys_search_text_changed(self, text: str) -> None:
        self._hotkeys_search_text = text

    def _action_shortcut_display_text(self, action_id: str, action: QAction) -> str:
        if action_id == "stop":
            binding_text = display_hotkey_clauses(self._current_hotkey_bindings.get("stop", ""))
            if binding_text:
                return binding_text
        return action.shortcut().toString(QKeySequence.SequenceFormat.NativeText).strip()

    def _format_options_from_scripting(self, scripting: ScriptingSettings) -> FormatOptions:
        indent = " " * max(1, int(scripting.indent_width)) if scripting.use_spaces else "\t"
        return FormatOptions(indent=indent)

    def _configured_script_extension(self) -> str:
        extension = self.committed_settings_bundle.files.file_extension.strip()
        if not extension:
            return ".ass"
        if not extension.startswith("."):
            extension = f".{extension.lstrip('.')}"
        return extension

    def _script_save_filter(self) -> str:
        extension = self._configured_script_extension()
        return (
            f"ActionShellScript documents (*{extension});;"
            "JSON files (*.json);;"
            "Text files (*.txt);;"
            "All files (*.*)"
        )

    def _script_open_directory(self) -> Path:
        remembered_directory = self._session_last_open_directory
        if remembered_directory is not None and remembered_directory.exists() and remembered_directory.is_dir():
            return remembered_directory
        return self._recording_autosave_output_folder()

    def _remember_last_open_directory(self, path: Path) -> None:
        directory = Path(path).expanduser().resolve()
        if self._session_last_open_directory == directory:
            return
        self._session_last_open_directory = directory

    def _suggested_script_save_path(self) -> Path:
        extension = self._configured_script_extension()
        if self.current_path is not None:
            return self._resolve_script_save_path(self.current_path)
        return Path(f"Untitled{extension}")

    def _suggested_recording_script_save_path(self, _document: ScriptDocument) -> Path:
        return self._suggested_recording_autosave_path(
            base_name=self._recording_autosave_file_name(),
            output_folder=self._recording_autosave_output_folder(),
            include_timestamp=self.committed_settings_bundle.files.autosave_timestamp_suffix,
            extension=self._configured_script_extension(),
        )

    def _suggested_recording_session_save_path(self, _session: RecordingSession) -> Path:
        return self._suggested_recording_autosave_path(
            base_name=self._recording_raw_autosave_file_name(),
            output_folder=self._recording_raw_autosave_output_folder(),
            include_timestamp=self.committed_settings_bundle.files.raw_autosave_timestamp_suffix,
            extension=".json",
        )

    def _recording_autosave_output_folder(self) -> Path:
        return self._resolve_recording_autosave_output_folder(
            self.committed_settings_bundle.files.autosave_output_folder
        )

    def _recording_raw_autosave_output_folder(self) -> Path:
        return self._resolve_recording_autosave_output_folder(
            self.committed_settings_bundle.files.raw_autosave_output_folder
        )

    def _resolve_recording_autosave_output_folder(self, folder: str) -> Path:
        folder = str(folder).strip()
        base_directory = self._recording_autosave_base_directory()
        if not folder:
            return base_directory / "recordings"

        candidate = Path(folder).expanduser()
        if candidate.is_absolute():
            return candidate
        return base_directory / candidate

    def _recording_autosave_base_directory(self) -> Path:
        # Keep autosave folders anchored to the app's recording root so relative
        # settings like "recordings" do not keep nesting under the last saved file.
        return self._recording_output_base_directory()

    def _recording_output_base_directory(self) -> Path:
        config_dir = self._settings_service.config_dir
        if config_dir.name == "config":
            return config_dir.parent
        return config_dir

    def _recording_autosave_file_name(self) -> str:
        return self._normalize_recording_autosave_file_name(
            self.committed_settings_bundle.files.autosave_file_name,
            self._configured_script_extension(),
        )

    def _recording_raw_autosave_file_name(self) -> str:
        return self._normalize_recording_autosave_file_name(
            self.committed_settings_bundle.files.raw_autosave_file_name,
            ".json",
        )

    def _normalize_recording_autosave_file_name(self, raw_name: str, extension: str) -> str:
        normalized = str(raw_name).strip()
        if not normalized:
            normalized = "recording"
        normalized = re.sub(r'[<>:"/\\\\|?*]+', "_", normalized)
        normalized = normalized.strip(" .")
        if not normalized:
            normalized = "recording"

        normalized_extension = extension.strip()
        if normalized_extension:
            if not normalized_extension.startswith("."):
                normalized_extension = f".{normalized_extension.lstrip('.')}"
            if normalized.lower().endswith(normalized_extension.lower()):
                normalized = normalized[: -len(normalized_extension)].rstrip(" .") or "recording"

        return normalized

    def _suggested_recording_autosave_path(
        self,
        *,
        base_name: str,
        output_folder: Path,
        include_timestamp: bool,
        extension: str,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_stem = f"{base_name}_{timestamp}" if include_timestamp else base_name
        candidate = self._resolve_script_save_path(output_folder / f"{file_stem}{extension}")
        return self._unique_script_save_path(candidate)

    def _resolve_script_save_path(self, path: Path) -> Path:
        if path.suffix:
            return path
        return path.with_suffix(self._configured_script_extension())

    def _unique_script_save_path(self, path: Path) -> Path:
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        index = 1
        while True:
            candidate = parent / f"{stem}-{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _auto_format_current_document(self) -> None:
        formatted_text = self.services.formatting_service.format_document(self.current_document)
        if formatted_text == self.current_document.text:
            return

        self.current_document = self.services.document_service.update_text(
            self.current_document,
            formatted_text,
        )
        self._loading_document = True
        try:
            self.editor.setPlainText(formatted_text)
        finally:
            self._loading_document = False

    def _remember_last_workspace(self, path: Path) -> None:
        if not self.committed_settings_bundle.application.restore_last_workspace:
            return
        last_path = str(path)
        if self.committed_settings_bundle.application.last_workspace_path != last_path:
            # Track the last workspace path only when restore-on-startup is enabled.
            self.committed_settings_bundle.application.last_workspace_path = last_path
            try:
                self._settings_service.save(self.committed_settings_bundle, force=True)
            except Exception:
                # Restoring the last workspace should stay best-effort and never block
                # normal open/load flows.
                pass

    def save_preferences(self) -> bool:
        requirements = self._settings_service.save_requirements()
        existing = [item for item in requirements if item[1].requires_save]
        if existing:
            paths = "\n".join(f"- {path}" for path, _, _ in existing)
            choice = question_save_discard_cancel(
                self,
                "Preferences",
                "One or more configuration files already exist and will be overwritten:\n\n"
                f"{paths}\n\nSave preferences anyway?",
            )
            if choice != QMessageBox.StandardButton.Save:
                return False

        draft_bundle = (
            self._preferences_dialog.settings_bundle()
            if self._preferences_dialog is not None
            else self.committed_settings_bundle
        )
        theme_issues = validate_desktop_preferences_readability(draft_bundle.theme)
        if theme_issues:
            QMessageBox.critical(
                self,
                "Preferences Save Blocked",
                "The selected color scheme is not readable enough to save safely:\n\n"
                + "\n".join(f"- {issue}" for issue in theme_issues),
            )
            return False
        self.committed_settings_bundle = copy.deepcopy(draft_bundle)
        try:
            self._settings_service.save(copy.deepcopy(self.committed_settings_bundle), force=True)
        except Exception as exc:
            QMessageBox.critical(self, "Preferences Save Failed", str(exc))
            preferences_log.exception(
                "Preferences save failed",
                exc,
                event_id="desktop.preferences.save_failed",
            )
            return False

        self._set_settings_dirty(False, reason="preferences saved")
        if self._preferences_dialog is not None:
            self._preferences_dialog.mark_saved()
        preferences_log.info(
            "Preferences saved",
            event_id="desktop.preferences.saved",
            settings_path=str(self._settings_service.settings_path),
        )
        self._update_status("Preferences saved")
        self._update_window_title()
        self._update_workspace_tab_labels()
        return True

    def _discard_preferences_changes(self) -> None:
        persisted_bundle = self._settings_service.load()
        self.committed_settings_bundle = copy.deepcopy(persisted_bundle)
        self.apply_preferences(persisted_bundle.theme)
        self._apply_hotkeys(persisted_bundle.application.hotkeys.bindings)
        self._debugging_service.set_runtime_settings(persisted_bundle.runtime)
        self._debugging_service.set_playback_settings(persisted_bundle.playback)
        self.script_controller.set_playback_settings(persisted_bundle.playback)
        self.script_controller.set_recording_settings(persisted_bundle.recording)
        self.script_controller.set_runtime_settings(persisted_bundle.runtime)
        self._load_go_to_dialog_state_from_settings()
        self._sync_diagnostics_log_surface()
        self._set_settings_dirty(False, reason="preferences discarded")
        if self._preferences_dialog is not None:
            self._preferences_dialog.set_preferences(copy.deepcopy(persisted_bundle))
            self._preferences_dialog.mark_saved()
        preferences_log.info(
            "Preferences discarded",
            event_id="desktop.preferences.discarded",
            settings_path=str(self._settings_service.settings_path),
        )
        self._update_status("Preferences discarded")
        self._update_window_title()
        self._update_workspace_tab_labels()
        self._update_workspace_tab_visibility()

    def open_documentation(self) -> None:
        try:
            if self._help_browser_window is None:
                self._help_browser_window = ActionShellScriptHelpBrowser(
                    on_close=self._clear_help_browser_window,
                )
            if self._help_browser_window.isMinimized():
                self._help_browser_window.showNormal()
            else:
                self._help_browser_window.show()
            self._help_browser_window.raise_()
            self._help_browser_window.activateWindow()
        except Exception as exc:
            self._help_browser_window = None
            self._open_documentation_fallback(exc)

    def _clear_help_browser_window(self) -> None:
        self._help_browser_window = None

    def _launch_ass_help_fallback(self, target_path: Path) -> bool:
        program: str | None = None
        arguments: list[str] = []

        if getattr(sys, "frozen", False):
            executable_root = Path(sys.executable).resolve().parent
            launcher_path = executable_root.parent / "ass-help" / "ass-help.exe"
            if launcher_path.exists():
                program = str(launcher_path)
                arguments = [str(target_path)]
        else:
            program = sys.executable
            arguments = ["-m", "apps.desktop.help_main", str(target_path)]

        if program is None:
            return False

        started = QProcess.startDetached(program, arguments)
        if started:
            window_log.info(
                "Documentation fallback launched ass-help",
                event_id="desktop.window.documentation_ass_help_launched",
                docs_path=str(target_path),
                launcher_path=program,
            )
            self._update_status(ass_help_fallback_status())
            return True
        return False

    def _open_documentation_fallback(self, error: Exception) -> None:
        docs_index = docs_index_path()
        if self._launch_ass_help_fallback(docs_index):
            return

        docs_index_url = QUrl.fromLocalFile(str(docs_index))
        if QDesktopServices.openUrl(docs_index_url):
            self._update_status(system_viewer_fallback_status())
            return

        QMessageBox.warning(
            self,
            "Documentation Unavailable",
            documentation_unavailable_message(error, docs_index),
        )
        self._update_status(documentation_unavailable_status())

    def open_about(self) -> None:
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About ActionShellScript")
        about_dialog.setWindowIcon(self._frog_icon())
        about_dialog.setModal(True)

        layout = QVBoxLayout(about_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header_row = QWidget(about_dialog)
        header_row_layout = QHBoxLayout(header_row)
        header_row_layout.setContentsMargins(0, 0, 0, 0)
        header_row_layout.setSpacing(14)

        left_column = QWidget(header_row)
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(10)

        info_icon_label = QLabel(left_column)
        info_icon_label.setObjectName("aboutInfoIconLabel")
        info_icon_label.setPixmap(
            about_dialog.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(42, 42)
        )
        info_icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        left_column_layout.addWidget(info_icon_label, 0)

        frog_label = QLabel(left_column)
        frog_label.setObjectName("aboutFrogIconLabel")
        frog_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        frog_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        frog_pixmap = self._about_frog_pixmap()
        if not frog_pixmap.isNull():
            frog_label.setPixmap(frog_pixmap)
        left_column_layout.addWidget(frog_label, 0)

        header_row_layout.addWidget(left_column, 0, Qt.AlignmentFlag.AlignTop)

        text_block = QWidget(header_row)
        text_block_layout = QVBoxLayout(text_block)
        text_block_layout.setContentsMargins(0, 0, 0, 0)
        text_block_layout.setSpacing(6)

        title_label = QLabel("ActionShellScript", text_block)
        title_label.setObjectName("aboutTitleLabel")
        title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        text_block_layout.addWidget(title_label)

        body_label = QLabel(
            "A desktop workbench for recording, editing, analyzing, and replaying "
            "ActionShellScript automation.",
            text_block,
        )
        body_label.setObjectName("aboutBodyLabel")
        body_label.setWordWrap(True)
        body_label.setStyleSheet("color: #4f5b66; font-size: 11px;")
        text_block_layout.addWidget(body_label)

        info_copy_label = QLabel(
            "Use it to capture sessions, refine generated scripts, inspect pixels, "
            "review diagnostics, and run scripts with breakpoint-aware debugging.",
            text_block,
        )
        info_copy_label.setObjectName("aboutInfoCopyLabel")
        info_copy_label.setWordWrap(True)
        info_copy_label.setStyleSheet("color: #4f5b66; font-size: 11px;")
        text_block_layout.addWidget(info_copy_label)

        extra_copy_label = QLabel(
            "Designed around the recording-to-script workflow, with built-in help, "
            "preferences, and replay tools.",
            text_block,
        )
        extra_copy_label.setObjectName("aboutExtraCopyLabel")
        extra_copy_label.setWordWrap(True)
        extra_copy_label.setStyleSheet("color: #4f5b66; font-size: 11px;")
        text_block_layout.addWidget(extra_copy_label)

        attribution_group = QGroupBox("Attribution", text_block)
        attribution_layout = QVBoxLayout(attribution_group)
        attribution_layout.setContentsMargins(12, 12, 12, 12)
        attribution_layout.setSpacing(8)

        attribution_view = QTextBrowser(attribution_group)
        attribution_view.setObjectName("aboutAttributionView")
        attribution_view.setFrameShape(QFrame.Shape.StyledPanel)
        attribution_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        attribution_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        attribution_view.setMaximumHeight(230)
        attribution_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        attribution_font = QFont()
        attribution_font.setStyleHint(QFont.StyleHint.Monospace)
        attribution_font.setFamily("Consolas")
        attribution_view.setFont(attribution_font)
        attribution_view.setStyleSheet(
            "QTextBrowser#aboutAttributionView {"
            "  background: rgba(255, 255, 255, 0.72);"
            "  border: 1px solid rgba(80, 80, 80, 0.18);"
            "  border-radius: 8px;"
            "  padding: 10px;"
            "  font-size: 10.5px;"
            "  line-height: 1.3;"
            "}"
        )
        attribution_view.setPlainText(load_attribution_notice_text().strip())
        attribution_layout.addWidget(attribution_view)
        text_block_layout.addWidget(attribution_group)

        header_row_layout.addWidget(text_block, 1)

        layout.addWidget(header_row)

        button_row = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, about_dialog)
        button_row.accepted.connect(about_dialog.accept)
        layout.addWidget(button_row)

        about_dialog.exec()

    def _about_frog_pixmap(self) -> QPixmap:
        cache = getattr(self, "_about_frog_pixmap_cache", None)
        if cache is not None:
            return cache
        icon = self._frog_icon()
        pixmap = icon.pixmap(128, 128)
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(128, Qt.TransformationMode.SmoothTransformation)
        if pixmap.isNull():
            frog_path = desktop_asset_path(DesktopAsset.FROG_ICON)
            pixmap = QPixmap(str(frog_path))
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(128, Qt.TransformationMode.SmoothTransformation)
        self._about_frog_pixmap_cache = pixmap
        return pixmap

    def _frog_icon(self) -> QIcon:
        cache = getattr(self, "_frog_icon_cache", None)
        if cache is not None:
            return cache
        icon = QIcon(str(desktop_asset_path(DesktopAsset.FROG_ICON_ICO)))
        if icon.isNull():
            icon = QIcon(str(desktop_asset_path(DesktopAsset.FROG_ICON)))
        self._frog_icon_cache = icon
        return icon

    def show_debugger_tab(self) -> None:
        self._request_sidebar("debug", toggle_if_current=True)

    def show_debug_sidebar(self) -> None:
        self._request_sidebar("debug", toggle_if_current=False)

    def open_pixel_inspector_window(self) -> None:
        if self._pixel_inspector_window is None:
            self._pixel_inspector_window = PixelInspectorWindow()
        self._pixel_inspector_window.show()
        self._pixel_inspector_window.raise_()
        self._pixel_inspector_window.activateWindow()

    def show_document_status_dialog(self) -> None:
        dialog = DocumentStatusDialog(self, lines=self._document_status_lines())
        dialog.exec()

    def open_debugger_dialog(self) -> None:
        if self.script_controller.is_active or self._debug_session_is_active():
            self._update_status("Another script operation is already running")
            return

        self._start_debug_session()

    def _start_debug_session(self) -> None:
        self._reset_debug_tab()
        self._append_debug_output_line("Debug session starting...")
        self._ensure_debug_tab_visible_for_debugging()
        self._show_debug_sidebar_for_debugging()
        self._last_debug_session_outcome = None

        document_snapshot = ScriptDocument(
            document_id=self.current_document.document_id,
            text=self.current_document.text,
            version=self.current_document.version,
            is_dirty=self.current_document.is_dirty,
            last_saved_version=self.current_document.last_saved_version,
            source_session_id=self.current_document.source_session_id,
            source_action_count=self.current_document.source_action_count,
            generated_from_recording=self.current_document.generated_from_recording,
            recording_conversion_route=self.current_document.recording_conversion_route,
            source_capture_excluded_main_window=(
                self.current_document.source_capture_excluded_main_window
            ),
            source_path=self.current_document.source_path,
        )
        breakpoints = tuple(sorted(self.editor.debugBreakpointLines()))
        self._sync_editor_source_state(None)
        stop_event = threading.Event()
        request = DebugRequest(
            document_id=document_snapshot.document_id,
            stop_mode="step",
            breakpoints=breakpoints,
        )
        handle = self._debugging_service.start_debug_session(
            document_snapshot,
            request,
            emit_event=self.debugEventReceived.emit,
            stop_event=stop_event,
        )
        self._debug_session_handle = handle
        self._debug_session_stop_event = stop_event
        self._refresh_debug_snapshot()
        self._update_debugger_controls_state(active=True)

        thread = threading.Thread(
            target=self._run_debug_session,
            args=(handle, document_snapshot),
            daemon=True,
        )
        self._debug_session_thread = thread
        thread.start()
        self._update_script_action_state()

    def _run_debug_session(self, handle: DebugRunHandle, document: ScriptDocument) -> None:
        status = "completed"
        context = None
        try:
            context = handle.runtime.compile(
                document.text,
                source_path=document.source_path,
            )
        except ScriptRuntimeCancelled:
            status = "stopped"
            self.debugMessageReceived.emit("Debug session stopped.")
        except BaseException as exc:
            status = "failed"
            self.debugMessageReceived.emit(f"Debug session failed: {exc}")
        finally:
            if status == "completed":
                handle.controller.sync_from_context(context)
                if handle.session.state not in {"completed", "failed"}:
                    handle.controller.complete()
            self.debugSessionFinished.emit(status)

    def step_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        handle.controller.resume_step()
        self._refresh_debug_snapshot()

    def step_over_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        handle.controller.resume_step_over()
        self._refresh_debug_snapshot()

    def step_out_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        handle.controller.resume_step_out()
        self._refresh_debug_snapshot()

    def continue_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        handle.controller.resume_continue()
        self._refresh_debug_snapshot()

    def pause_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        snapshot = handle.controller.snapshot()
        if getattr(snapshot, "state", None) != "running":
            return
        handle.controller.request_pause()
        self._refresh_debug_snapshot()

    def stop_debug_session(self) -> None:
        handle = self._debug_session_handle
        if handle is None:
            return
        if self._debug_session_stop_event is not None:
            self._debug_session_stop_event.set()
        handle.controller.resume_continue()
        self.debugMessageReceived.emit("Stopping debug session...")
        self._refresh_debug_snapshot()

    def restart_debug_session(self) -> None:
        if self._debug_session_handle is None:
            return
        self._pending_debug_restart = True
        self.stop_debug_session()

    def _commit_editor_changes(self) -> None:
        text = self.editor.toPlainText()
        if text != self.current_document.text:
            self.current_document = self.services.document_service.update_text(
                self.current_document,
                text,
            )
        self._set_editor_dirty(False, reason="editor changes committed")

    def has_unsaved_changes(self) -> bool:
        return self._editor_dirty or self.current_document.is_dirty

    def _confirm_discard_or_save(self, prompt: str = "Save changes before continuing?") -> bool:
        if not self.has_unsaved_changes():
            return True

        choice = question_save_discard_cancel(
            self,
            "Unsaved Changes",
            prompt,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self.save_script()
        return True

    def _reset_editor_for_recording(self) -> None:
        self.current_path = None
        self.current_document = ScriptDocument(
            document_id=str(uuid.uuid4()),
            text="",
        )
        self.current_analysis = None
        self._set_editor_dirty(False, reason="recording started with blank editor")
        self._analysis_stale = False
        self._last_preview_text = ""
        self._sync_saved_document_text()
        self._refresh_all_views()
        self._update_window_title()
        self._update_workspace_tab_labels()

    def _discard_editor_changes(self) -> None:
        # The caller has already decided to throw away the current edit session.
        self._set_editor_dirty(False, reason="editor changes discarded")
        self._analysis_stale = False

    def new_document(self) -> bool:
        if not self._confirm_discard_or_save():
            return False
        if self._settings_dirty and not self._confirm_discard_or_save_preferences():
            return False

        self.current_path = None
        self.current_document = ScriptDocument(
            document_id=str(uuid.uuid4()),
            text="",
        )
        self.current_analysis = None
        self._set_editor_dirty(False, reason="new document created")
        self._analysis_stale = False
        self._last_preview_text = ""
        self._sync_saved_document_text()
        self._refresh_all_views()
        window_log.info(
            "New document created",
            event_id="desktop.window.document_created",
            current_path=None,
            document_id=self.current_document.document_id,
        )
        self._update_status("Created new document")
        self._update_window_title()
        self._update_workspace_tab_labels()
        return True

    def open_script(self) -> bool:
        if not self._confirm_discard_or_save():
            return False
        if self._settings_dirty and not self._confirm_discard_or_save_preferences():
            return False

        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Open Script Document",
            str(self._script_open_directory()),
            self._script_save_filter(),
        )
        if not path_text:
            return False

        selected_path = Path(path_text)
        self.load_script(selected_path)
        self._remember_last_open_directory(selected_path.parent)
        return True

    def load_script(self, path: Path) -> None:
        document = self.services.document_store.load(path)
        self.current_path = Path(path)
        self.current_document = document
        self.current_analysis = None
        self._set_editor_dirty(False, reason="script loaded")
        self._analysis_stale = False
        self._last_preview_text = ""
        self._sync_saved_document_text()
        self._remember_last_workspace(self.current_path)
        self._refresh_all_views()
        window_log.info(
            "Script document loaded",
            event_id="desktop.window.document_loaded",
            current_path=str(self.current_path),
            document_id=self.current_document.document_id,
            version=self.current_document.version.value,
            line_count=self.current_document.line_count(),
        )
        self._update_status(f"Loaded {path}")
        self._update_window_title()
        self._update_workspace_tab_labels()

    def save_script(self) -> bool:
        if self.current_path is None:
            return self.save_script_as()

        self._commit_editor_changes()
        if self._preferences.scripting.auto_format_on_save:
            try:
                self._auto_format_current_document()
            except Exception as exc:
                QMessageBox.critical(self, "Save Failed", str(exc))
                self._update_status("Save failed")
                return False

        self.current_path = self._resolve_script_save_path(self.current_path)
        self.current_document.source_path = str(self.current_path)
        try:
            self.services.document_store.save(self.current_path, self.current_document)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            window_log.exception(
                "Document save failed",
                exc,
                event_id="desktop.window.document_save_failed",
                current_path=str(self.current_path),
            )
            self._update_status("Save failed")
            return False

        self.services.document_service.mark_saved(self.current_document)
        self._sync_saved_document_text()
        self._set_editor_dirty(False, reason="script saved")
        self._analysis_stale = False
        self._refresh_summary()
        self._refresh_preview(force_format=True)
        self._remember_last_workspace(self.current_path)
        window_log.info(
            "Script document saved",
            event_id="desktop.window.document_saved",
            current_path=str(self.current_path),
            document_id=self.current_document.document_id,
            version=self.current_document.version.value,
            line_count=self.current_document.line_count(),
        )
        self._update_status(f"Saved {self.current_path}")
        self._update_window_title()
        self._update_workspace_tab_labels()
        return True

    def save_script_as(self) -> bool:
        suggested_path = self._suggested_script_save_path()
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "Save Script Document As",
            str(suggested_path),
            self._script_save_filter(),
        )
        if not path_text:
            return False

        self.current_path = self._resolve_script_save_path(Path(path_text))
        if not self.save_script():
            return False

        self._remember_last_open_directory(self.current_path.parent)
        return True

    def analyze_document(self) -> bool:
        self._commit_editor_changes()
        try:
            self.current_analysis = self.services.language_service.analyze(self.current_document)
        except Exception as exc:
            QMessageBox.critical(self, "Analyze Failed", str(exc))
            self._update_status("Analysis failed")
            return False

        self._analysis_stale = False
        self._refresh_summary()
        self._refresh_analysis(mark_attention=True)
        self._refresh_diagnostics()
        self._update_editor_status_details()
        error_count = sum(
            1 for diagnostic in self.current_analysis.diagnostics.items if diagnostic.severity.value == "error"
        )
        self._request_sidebar("analysis")
        if error_count:
            self._update_status(f"Analysis refreshed from current editor text with {error_count} error(s)")
        else:
            self._update_status("Analysis refreshed from current editor text")
        self._update_window_title()
        self._update_workspace_tab_labels()
        return True

    def refresh_preview(self) -> bool:
        self._commit_editor_changes()
        try:
            self._last_preview_text = self.services.formatting_service.format_document(
                self.current_document
            )
        except Exception as exc:
            QMessageBox.critical(self, "Preview Failed", str(exc))
            self._update_status("Preview failed")
            return False

        self._refresh_preview(force_format=False, mark_attention=True)
        self._update_status("Preview refreshed")
        self._update_window_title()
        self._update_workspace_tab_labels()
        return True

    def toggle_current_line_breakpoint(self) -> None:
        line = self.editor.currentLineNumber()
        self.editor.toggleDebugBreakpoint(line)

    def clear_all_breakpoints(self) -> None:
        self.editor.clearDebugBreakpoints()

    def play_script(self, *, mode: PlaybackMode = PlaybackMode.LIVE) -> bool:
        self._commit_editor_changes()
        if not self._ensure_current_analysis_for_playback(mode=mode):
            return False
        self._current_playback_result = None
        self._refresh_summary()
        self._refresh_playback_output(clear_attention=True)
        return self.script_controller.play(self.current_document, mode=mode)

    def preview_play_script(self) -> bool:
        return self.play_script(mode=PlaybackMode.PREVIEW)

    def _ensure_current_analysis_for_playback(self, *, mode: PlaybackMode) -> bool:
        analysis_refreshed = False
        if (
            self.current_analysis is None
            or self._analysis_stale
            or self.current_analysis.is_stale_for(self.current_document)
        ):
            if not self.analyze_document():
                return False
            analysis_refreshed = True

        analysis = self.current_analysis
        if analysis is None:
            return True

        error_diagnostics = [
            diagnostic
            for diagnostic in analysis.diagnostics.items
            if diagnostic.severity.value == "error"
        ]
        if not error_diagnostics:
            return True

        first_error = error_diagnostics[0]
        if first_error.span is not None:
            self._focus_diagnostic_span(first_error.span)

        status_prefix = (
            "Script preview blocked"
            if mode == PlaybackMode.PREVIEW
            else "Script play blocked"
        )
        if analysis_refreshed:
            status_prefix += " after refreshing analysis"
        status_text = f"{status_prefix}: current editor text has {len(error_diagnostics)} error(s)"
        if first_error.span is not None:
            status_text += "; jumped to the first diagnostic"
        self._update_status(status_text)
        return False

    def record_script(self) -> bool:
        if not self._confirm_discard_or_save("Save changes before recording?"):
            return False

        started = self.script_controller.record()
        if not started:
            return False

        self._reset_editor_for_recording()
        self._update_script_action_state()
        return True

    def stop_script(self) -> bool:
        if self._debug_session_is_active():
            self.stop_debug_session()
            return True
        return self.script_controller.stop()

    def _bind_script_controller(self) -> None:
        self.script_controller.playbackResultReady.connect(self._on_playback_result_ready)
        self.script_controller.recordingResultReady.connect(self._on_recording_result_ready)
        self.script_controller.statusChanged.connect(self._update_status)
        self.script_controller.busyChanged.connect(
            lambda _busy: self._update_script_action_state()
        )
        self.script_controller.busyChanged.connect(
            lambda _busy: self._update_activity_indicator()
        )
        self.script_controller.errorOccurred.connect(self._report_script_error)
        self._update_activity_indicator()

    def _on_playback_result_ready(self, result: object) -> None:
        self._current_playback_result = result if isinstance(result, PlaybackResult) else None
        self._refresh_summary()
        self._refresh_playback_output(mark_attention=True)

    def _on_recording_result_ready(self, result: object) -> None:
        if not isinstance(result, RecordingSession):
            return

        try:
            raw_saved_path = self._auto_save_recording_session(result)
            converted_document = self._convert_recording_session(result)
            saved_path = self._auto_save_converted_recording_document(converted_document)
        except Exception as exc:
            QMessageBox.critical(self, "Recording Conversion Failed", str(exc))
            return

        self._load_document_from_recording(converted_document, path=saved_path)
        self._current_recording_session = result
        self._refresh_raw_recording_output(mark_attention=True)
        route_label = self._recording_conversion_route_label(converted_document)
        if raw_saved_path is not None and saved_path is not None:
            self._update_status(
                f"Saved raw session {raw_saved_path} and script {saved_path} after {route_label}"
            )
        elif raw_saved_path is not None:
            self._update_status(f"Saved raw session {raw_saved_path} after {route_label}")
        elif saved_path is not None:
            self._update_status(f"Saved {saved_path} after {route_label}")
        else:
            self._update_status(f"Recording converted via {route_label}")

    def _convert_recording_session(self, session: RecordingSession) -> ScriptDocument:
        mode = self.committed_settings_bundle.recording.recording_conversion_mode
        if mode == "direct_import":
            return self.services.document_service.import_recording_session(
                session,
                recording_conversion_route="direct_import",
                source_capture_excluded_main_window=(
                    self.committed_settings_bundle.recording.exclude_main_window_during_recording
                ),
            )

        interpretation_service = InterpretationService()
        shaping_service = ShapingService()
        generation_service = ScriptGenerationService()

        interpreted = interpretation_service.interpret_recording(session)
        shaped = shaping_service.shape_recording(interpreted)
        generated = generation_service.generate_script(shaped)
        return self.services.document_service.promote_generated_script(
            generated,
            recording_conversion_route="promote_generated",
            source_capture_excluded_main_window=(
                self.committed_settings_bundle.recording.exclude_main_window_during_recording
            ),
        )

    def _auto_save_converted_recording_document(self, document: ScriptDocument) -> Path | None:
        if not self.committed_settings_bundle.files.autosave_enabled:
            return None

        suggested_path = self._suggested_recording_script_save_path(document)
        try:
            self.services.document_store.save(suggested_path, document)
            document.source_path = str(suggested_path)
            self.services.document_service.mark_saved(document)
        except Exception as exc:
            QMessageBox.critical(self, "Recording Save Failed", str(exc))
            return None
        return suggested_path

    def _auto_save_recording_session(self, session: RecordingSession) -> Path | None:
        if not self.committed_settings_bundle.files.raw_autosave_enabled:
            return None

        suggested_path = self._suggested_recording_session_save_path(session)
        try:
            save_raw_session(session, str(suggested_path))
        except Exception as exc:
            QMessageBox.critical(self, "Recording Save Failed", str(exc))
            return None
        return suggested_path

    def _load_document_from_recording(self, document: ScriptDocument, *, path: Path | None) -> None:
        self.current_path = path
        if path is not None:
            document.source_path = str(path)
        self.current_document = document
        self.current_analysis = None
        self._set_editor_dirty(False, reason="recording promoted")
        self._analysis_stale = False
        self._last_preview_text = ""
        self._sync_saved_document_text()
        self._refresh_all_views()
        window_log.info(
            "Recording converted to script document",
            event_id="desktop.window.recording_converted",
            current_path=str(self.current_path) if self.current_path is not None else None,
            document_id=self.current_document.document_id,
            version=self.current_document.version.value,
            line_count=self.current_document.line_count(),
            recording_conversion_route=self.current_document.recording_conversion_route,
            source_capture_excluded_main_window=(
                self.current_document.source_capture_excluded_main_window
            ),
        )
        self._update_window_title()
        self._update_workspace_tab_labels()

    def _recording_conversion_route_label(self, document: ScriptDocument | None = None) -> str:
        route = (
            document.recording_conversion_route
            if document is not None
            else self.current_document.recording_conversion_route
        )
        if route == "direct_import":
            return "Direct import"
        if route == "promote_generated":
            return "Promote generated script"
        if route is not None:
            return route
        return "<unknown>"

    def _report_script_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        discard_editor_changes = False
        if not self._confirm_discard_or_save():
            event.ignore()
            return
        if self.has_unsaved_changes():
            discard_editor_changes = True

        if self._settings_dirty and not self._confirm_discard_or_save_preferences():
            event.ignore()
            return

        if discard_editor_changes:
            self._discard_editor_changes()

        if self._diagnostics_event_unsubscribe is not None:
            self._diagnostics_event_unsubscribe()
            self._diagnostics_event_unsubscribe = None
        if self._pixel_inspector_window is not None:
            self._pixel_inspector_window.close()
            self._pixel_inspector_window = None

        window_log.info(
            "Desktop window closing",
            event_id="desktop.window.closing",
            editor_dirty=self._editor_dirty,
            settings_dirty=self._settings_dirty,
            has_unsaved_changes=self.has_unsaved_changes(),
        )
        event.accept()

    def _confirm_discard_or_save_preferences(self) -> bool:
        if not self._settings_dirty:
            return True

        choice = question_save_discard_cancel(
            self,
            "Preferences",
            "Save preferences before closing?",
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self.save_preferences()

        self._discard_preferences_changes()
        return True
