from __future__ import annotations

import os
from pathlib import Path
from typing import TypeVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtWidgets import QCheckBox  # noqa: E402
from PySide6.QtWidgets import QHBoxLayout  # noqa: E402
from PySide6.QtWidgets import QFormLayout  # noqa: E402
from PySide6.QtWidgets import QFrame  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402
from PySide6.QtWidgets import QScrollArea  # noqa: E402
from PySide6.QtWidgets import QSplitter  # noqa: E402
from PySide6.QtWidgets import QTabWidget  # noqa: E402
from PySide6.QtWidgets import QTableView  # noqa: E402
from PySide6.QtWidgets import QStyleOptionViewItem  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402
from PySide6.QtCore import QAbstractItemModel, Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from apps.desktop.preferences_dialog import PreferencesDialog  # noqa: E402
from apps.desktop.message_boxes import build_save_discard_cancel_box  # noqa: E402
from application.persistence.desktop_settings_service import DesktopSettingsService  # noqa: E402
from apps.desktop.settings import (  # noqa: E402
    DesktopApplicationSettings,
    DesktopFilesSettings,
    DesktopHotkeySettings,
    DesktopPlaybackSettings,
    DesktopRecordingSettings,
    DesktopRuntimeSettings,
    DesktopSettingsBundle,
)
from apps.desktop.theme import (  # noqa: E402
    AppearanceTheme,
    DesktopPreferences,
    DirtyIndicatorTheme,
    EditorAppearanceTheme,
    FontSettings,
    ScriptingSettings,
    SearchResultsTheme,
    SyntaxHighlightTheme,
    WorkspaceTabAttentionTheme,
)
from apps.desktop.hotkeys import default_hotkey_bindings  # noqa: E402
from apps.desktop.hotkeys import HOTKEY_DEFINITIONS  # noqa: E402
from infrastructure.input.mouse_movement_profile import MouseMovementProfile  # noqa: E402

TWidget = TypeVar("TWidget", bound=QWidget)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _layout_widget_at(layout: QHBoxLayout | None, index: int) -> QWidget:
    assert layout is not None
    item = layout.itemAt(index)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget


def _table_model(table: QTableView) -> QAbstractItemModel:
    return cast(QAbstractItemModel, table.model())


def _child_widgets(parent: QWidget, child_type: type[TWidget]) -> list[TWidget]:
    return cast(list[TWidget], parent.findChildren(child_type))


def _required_child(parent: QWidget, child_type: type[TWidget], name: str | None = None) -> TWidget:
    child = parent.findChild(child_type, name) if name is not None else parent.findChild(child_type)
    assert child is not None
    return cast(TWidget, child)


def _preferences_dialog_with_config_dir(config_dir: Path) -> tuple[QWidget, PreferencesDialog]:
    parent = QWidget()
    parent._settings_service = DesktopSettingsService(config_dir=config_dir)
    return parent, PreferencesDialog(parent)


def test_preferences_dialog_builds_expected_sections() -> None:
    app = _app()
    dialog = PreferencesDialog()
    dialog.show()
    app.processEvents()

    assert "ActionShellScript combo box readability fix" in QApplication.instance().styleSheet()
    assert dialog.windowTitle() == "Preferences"
    assert dialog.isModal() is False
    assert dialog.category_list.count() == 10
    assert dialog.category_list.item(0).text() == "General"
    assert dialog.category_list.item(1).text() == "Files"
    assert dialog.category_list.item(2).text() == "Editing"
    assert dialog.category_list.item(3).text() == "Workspace"
    assert dialog.category_list.item(4).text() == "Hotkeys"
    assert dialog.category_list.item(5).text() == "Playback"
    assert dialog.category_list.item(6).text() == "Recording"
    assert dialog.category_list.item(7).text() == "Runtime"
    assert dialog.category_list.item(8).text() == "Diagnostics"
    assert dialog.category_list.item(9).text() == "Debug"
    assert dialog.stack.count() == 10
    assert dialog.stack.currentIndex() == 0
    assert isinstance(dialog.stack.widget(1), QScrollArea)
    assert dialog.stack.widget(1).widget() is dialog._page_scroll_areas["Files"].widget()
    assert dialog.stack.widget(2).widget() is dialog._page_scroll_areas["Editing"].widget()
    assert dialog.stack.widget(3).widget() is dialog._page_scroll_areas["Workspace"].widget()
    assert dialog.dirty_indicator_label.isVisible() is False
    action_texts = {button.text() for button in _child_widgets(dialog, type(dialog.save_button))}
    assert "Restore Defaults" in action_texts
    assert "Restore All Defaults" in action_texts
    assert dialog.restore_workspace_checkbox.isChecked() is False
    assert dialog.open_debug_tab_on_pause_checkbox.isChecked() is True
    assert dialog.open_debug_tab_on_pause_checkbox.text() == "Open Run when paused"
    assert dialog.open_debug_tab_on_pause_checkbox.toolTip() == (
        "Automatically switch to the Run Sidebar when execution pauses."
    )
    assert dialog.appearance_item_list.count() == 4
    assert [dialog.appearance_item_list.item(i).text() for i in range(dialog.appearance_item_list.count())] == [
        "Dirty State",
        "Layout",
        "Search Results",
        "Search Spacing",
    ]
    assert dialog.appearance_item_stack.count() == 4
    assert dialog.show_formatted_preview_checkbox.isChecked() is True
    assert dialog.show_formatted_preview_checkbox.text() == "Show formatted preview tab"
    assert dialog.show_formatted_preview_checkbox.toolTip() == (
        "Show or hide the formatted preview tab in the workspace."
    )
    assert dialog.show_summary_sidebar_checkbox.isChecked() is True
    assert dialog.show_summary_sidebar_checkbox.text() == "Show summary sidebar on the left"
    assert dialog.hidden_workspace_tabs_strip_collapsed_checkbox.isChecked() is True
    assert dialog.hidden_workspace_tabs_strip_collapsed_checkbox.text() == (
        "Collapse hidden tab selections strip"
    )
    assert dialog.hidden_workspace_tabs_strip_collapsed_checkbox.toolTip() == (
        "Enabled by default. Start with the hidden tab selections strip collapsed whenever hidden tabs exist."
    )
    assert dialog.show_analysis_tab_checkbox.isChecked() is False
    assert dialog.show_analysis_tab_checkbox.text() == "Show Analysis tab"
    assert dialog.show_analysis_tab_checkbox.toolTip() == (
        "Show or hide the Analysis tab in the workspace."
    )
    workspace_frame = dialog.show_summary_sidebar_checkbox.parentWidget()
    assert workspace_frame is not None
    workspace_layout = workspace_frame.layout()
    assert workspace_layout is not None
    workspace_checkboxes = [
        workspace_layout.itemAt(i).widget()
        for i in range(workspace_layout.count())
        if isinstance(workspace_layout.itemAt(i).widget(), QCheckBox)
    ]
    assert workspace_checkboxes == [
        dialog.show_summary_sidebar_checkbox,
        dialog.hidden_workspace_tabs_strip_collapsed_checkbox,
        dialog.show_analysis_tab_checkbox,
        dialog.show_formatted_preview_checkbox,
        dialog.show_raw_recordings_checkbox,
        dialog.show_diagnostics_checkbox,
    ]
    assert dialog.show_raw_recordings_checkbox.text() == "Show raw recordings tab"
    assert dialog.show_raw_recordings_checkbox.toolTip() == (
        "Show or hide the Raw Recordings tab in the workspace."
    )
    assert dialog.show_diagnostics_checkbox.text() == "Show diagnostics tab"
    assert dialog.show_diagnostics_checkbox.toolTip() == (
        "Show or hide the Diagnostics tab in the workspace."
    )
    assert dialog.diagnostics_show_diagnostics_tab_checkbox.text() == "Show diagnostics tab"
    assert dialog.diagnostics_show_diagnostics_tab_checkbox.toolTip() == (
        "Show or hide the Diagnostics tab in the workspace."
    )
    assert dialog.text_editor_item_list.count() == 6
    assert [dialog.text_editor_item_list.item(i).text() for i in range(dialog.text_editor_item_list.count())] == [
        "Editor",
        "Typography",
        "Language",
        "Indentation",
        "Typing",
        "Save",
    ]
    assert dialog.text_editor_item_stack.count() == 6
    assert dialog.text_editor_item_stack.currentIndex() == 0
    assert dialog.appearance_item_list.count() == 4
    assert [dialog.appearance_item_list.item(i).text() for i in range(dialog.appearance_item_list.count())] == [
        "Dirty State",
        "Layout",
        "Search Results",
        "Search Spacing",
    ]
    assert dialog.appearance_item_stack.count() == 4
    assert dialog.appearance_item_stack.currentIndex() == 0
    assert dialog.files_tabs.count() == 4
    assert dialog.files_tabs.tabText(0) == "Raw recording"
    assert dialog.files_tabs.tabText(1) == "Converted script"
    assert dialog.files_tabs.tabText(2) == "Diagnostics"
    assert dialog.files_tabs.tabText(3) == "Configuration"
    assert dialog.scripting_extension_edit.text() == ".ass"
    assert any(label.text() == "Default script extension: .ass" for label in _child_widgets(dialog, QLabel))
    assert dialog.diagnostics_enabled_checkbox.isChecked() is False
    assert dialog.diagnostics_show_diagnostics_tab_checkbox.isChecked() is False
    assert dialog.diagnostics_min_severity_combo.currentText() == "Info"
    assert dialog.diagnostics_max_detail_combo.currentText() == "Summary"
    assert dialog.diagnostics_file_checkbox.isChecked() is False
    assert dialog.diagnostics_stdout_checkbox.isChecked() is False
    assert dialog.diagnostics_stdout_checkbox.text() == "Log to standard output"
    assert dialog.diagnostics_stdout_checkbox.toolTip() == (
        "Write diagnostics to the console as well as any file output."
    )
    assert dialog.open_debug_tab_on_pause_checkbox.isChecked() is True
    assert dialog.open_debug_tab_on_pause_checkbox.text() == "Open Run when paused"
    assert dialog.open_debug_tab_on_pause_checkbox.toolTip() == (
        "Automatically switch to the Run Sidebar when execution pauses."
    )
    assert dialog.diagnostics_log_path_title_label.text() == "Log file path"
    assert dialog.diagnostics_log_preview_label.text().startswith(
        "Diagnostics log will be saved as: "
    )
    assert "actionshellscript_diagnostics_" in dialog.diagnostics_log_path_label.text()
    assert any(
        button.text() == "Restore Defaults"
        for button in _child_widgets(dialog, QPushButton)
        if button.parent() is not None
    )
    runtime_tabs = dialog.findChild(QTabWidget, "runtimeTabs")
    assert runtime_tabs is not None
    assert runtime_tabs.count() == 3
    assert runtime_tabs.tabText(0) == "Execution"
    assert runtime_tabs.tabText(1) == "Mouse Movement Curve"
    assert runtime_tabs.tabText(2) == "Step Controls"
    runtime_restore_buttons = [
        button
        for button in _child_widgets(dialog, QPushButton)
        if button.text() == "Restore Defaults"
    ]
    assert len(runtime_restore_buttons) >= 1
    runtime_table = dialog.findChild(QTableView, "runtimeMouseMovementCurveTable")
    assert runtime_table is not None
    runtime_table_model = _table_model(runtime_table)
    assert runtime_table_model.headerData(0, Qt.Orientation.Horizontal) == "Speed"
    assert runtime_table_model.headerData(1, Qt.Orientation.Horizontal) == "Duration"
    runtime_key_header = dialog.findChild(QWidget, "runtimeMouseMovementCurveKeyTableHeaderStrip")
    assert runtime_key_header is not None
    assert [label.text() for label in _child_widgets(runtime_key_header, QLabel)] == [
        "Setting",
        "Value",
    ]
    runtime_key_table = dialog.findChild(QTableView, "runtimeMouseMovementCurveKeyTable")
    assert runtime_key_table is not None
    assert any(label.text() == "Curve Legend" for label in _child_widgets(dialog, QLabel))
    runtime_key_model = _table_model(runtime_key_table)
    assert runtime_key_model.headerData(0, Qt.Orientation.Horizontal) == "Setting"
    assert runtime_key_model.headerData(1, Qt.Orientation.Horizontal) == "Value"
    assert runtime_key_model.index(0, 0).data() == "Speed range"
    assert (
        runtime_key_model.index(0, 1).data()
        == "0 to 100; 0 is reserved for MouseMove(..., 0) and curve points start at 1"
    )
    assert runtime_key_model.index(1, 1).data() == (
        "0 = instant for MouseMove(..., 0); the curve editor starts at 1"
    )
    assert runtime_key_model.index(5, 0).data() == "Editing"
    assert runtime_key_model.index(5, 1).data() == "Use add / remove"
    assert dialog.runtime_mouse_movement_curve_preview is not None
    assert dialog.runtime_mouse_movement_curve_preview.curve_points()[0][0] == 1
    appearance_style_table = dialog.findChild(QTableView, "appearanceStyleTable")
    assert appearance_style_table is not None
    appearance_style_model = _table_model(appearance_style_table)
    assert appearance_style_model.rowCount() == 3
    dialog.category_list.setCurrentRow(3)
    dialog.text_editor_item_list.setCurrentRow(2)
    app.processEvents()
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "editingLanguagePage"
    assert appearance_style_table.horizontalHeader().isVisible() is False
    assert appearance_style_model.headerData(0, Qt.Orientation.Horizontal) == "Setting"
    assert appearance_style_model.headerData(1, Qt.Orientation.Horizontal) == "Foreground"
    assert appearance_style_model.headerData(2, Qt.Orientation.Horizontal) == "Background"
    assert appearance_style_model.index(0, 0).data() == "Editor"
    assert appearance_style_model.index(0, 1).data() == "#000000"
    assert appearance_style_model.index(0, 2).data() == "#FFFFFF"
    assert appearance_style_model.index(1, 0).data() == "Gutter"
    assert appearance_style_model.index(1, 1).data() == "#202020"
    assert appearance_style_model.index(1, 2).data() == "#F2F2F2"
    assert appearance_style_model.index(2, 0).data() == "Current line"
    assert appearance_style_model.index(2, 1).data() == "#000000"
    assert appearance_style_model.index(2, 2).data() == "#FFF4C2"
    assert dialog.formatting_indent_spin.value() == 4
    assert dialog.formatting_use_spaces_checkbox.isChecked() is True
    assert dialog.formatting_auto_indent_checkbox.isChecked() is True
    assert dialog.formatting_auto_format_checkbox.isChecked() is False
    dirty_state_table = dialog.findChild(QTableView, "dirtyStateStyleTable")
    assert dirty_state_table is not None
    dirty_state_model = _table_model(dirty_state_table)
    assert dirty_state_model.rowCount() == 4
    assert dirty_state_table.horizontalHeader().isVisible() is False
    dirty_header = dialog.findChild(QWidget, "dirtyStateStyleTableHeaderStrip")
    assert dirty_header is not None
    assert [label.text() for label in _child_widgets(dirty_header, QLabel)] == [
        "Setting",
        "Foreground",
        "Background",
    ]
    assert dirty_state_model.index(0, 0).data() == "Text"
    assert dirty_state_model.index(0, 1).data() == "#7A4A00"
    assert dirty_state_model.index(0, 2).data() == "#FFF5E3"
    assert dirty_state_model.index(1, 0).data() == "Accent"
    assert dirty_state_model.index(2, 0).data() == "Selected area"
    assert dirty_state_model.index(2, 1).data() == ""
    assert dirty_state_model.index(2, 2).data() == "#F0DDB4"
    assert dirty_state_model.index(3, 0).data() == "Border"
    assert dirty_state_model.index(3, 2).data() == "#EAD8B6"
    style_table = dialog.style_table
    style_model = _table_model(style_table)
    assert style_model.rowCount() == 4
    assert style_table.horizontalHeader().isVisible() is False
    assert style_model.headerData(0, Qt.Orientation.Horizontal) == "Setting"
    assert style_model.headerData(1, Qt.Orientation.Horizontal) == "Foreground"
    style_header = dialog.findChild(QWidget, "styleTableHeaderStrip")
    assert style_header is not None
    assert [label.text() for label in _child_widgets(style_header, QLabel)] == [
        "Setting",
        "Foreground",
    ]
    assert style_model.index(0, 0).data() == "Keyword"
    assert style_model.index(0, 1).data() == "#005CC5"
    assert style_model.index(1, 0).data() == "String"
    assert style_model.index(2, 0).data() == "Comment"
    assert style_model.index(3, 0).data() == "Number"
    button_texts = {button.text() for button in _child_widgets(dialog, type(dialog.save_button))}
    assert "Restore Editor Defaults" in button_texts
    assert "Reset Language Defaults" in button_texts
    assert "Restore Defaults" in button_texts
    assert "Restore Layout Defaults" in button_texts
    assert "Restore Syntax Colors Defaults" in button_texts
    assert dialog.typography_table.rowCount() == 4
    assert dialog.typography_table.columnCount() == 2
    assert dialog.typography_table.horizontalHeaderItem(0).text() == "Typography Setting"
    assert dialog.typography_table.horizontalHeaderItem(1).text() == "Value"
    assert dialog.typography_table.item(0, 0).text() == "Font family"
    assert dialog.typography_table.item(1, 0).text() == "Font size"
    assert dialog.typography_table.item(2, 0).text() == "Font weight"
    assert dialog.typography_table.item(3, 0).text() == "Line spacing multiplier"
    assert dialog.typography_table.cellWidget(0, 1) is dialog.font_family_combo
    assert dialog.typography_table.cellWidget(1, 1) is dialog.font_size_spin
    assert dialog.typography_table.cellWidget(2, 1) is dialog.font_weight_spin
    assert dialog.typography_table.cellWidget(3, 1) is dialog.font_line_spacing_spin


def test_preferences_dialog_appearance_item_lists_switch_pages() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()

    dialog.appearance_item_list.setCurrentRow(0)
    assert dialog.appearance_item_stack.currentIndex() == 0
    assert dialog.appearance_item_stack.currentWidget().objectName() == "appearanceDirtyStatePage"

    dialog.appearance_item_list.setCurrentRow(1)
    assert dialog.appearance_item_stack.currentIndex() == 1
    assert dialog.appearance_item_stack.currentWidget().objectName() == "workspaceTabsPage"

    dialog.text_editor_item_list.setCurrentRow(0)
    assert dialog.text_editor_item_stack.currentIndex() == 0
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "editingEditorPage"

    dialog.text_editor_item_list.setCurrentRow(1)
    assert dialog.text_editor_item_stack.currentIndex() == 1
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "appearanceTypographyPage"

    dialog.text_editor_item_list.setCurrentRow(2)
    assert dialog.text_editor_item_stack.currentIndex() == 2
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "editingLanguagePage"

    dialog.text_editor_item_list.setCurrentRow(3)
    assert dialog.text_editor_item_stack.currentIndex() == 3
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "formattingIndentationPage"

    dialog.text_editor_item_list.setCurrentRow(4)
    assert dialog.text_editor_item_stack.currentIndex() == 4
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "formattingTypingPage"

    dialog.text_editor_item_list.setCurrentRow(5)
    assert dialog.text_editor_item_stack.currentIndex() == 5
    assert dialog.text_editor_item_stack.currentWidget().objectName() == "formattingSaveTimePage"


def test_preferences_dialog_does_not_save_when_enter_is_pressed_on_appearance_item_list() -> None:
    app = _app()
    dialog = PreferencesDialog()
    dialog.show()
    app.processEvents()

    spy = QSignalSpy(dialog.saveRequested)
    dialog.appearance_item_list.setFocus()

    QTest.keyClick(dialog.appearance_item_list, Qt.Key.Key_Return)
    app.processEvents()

    assert spy.count() == 0


def test_preferences_dialog_does_not_save_when_enter_is_pressed_on_category_list() -> None:
    app = _app()
    dialog = PreferencesDialog()
    dialog.show()
    app.processEvents()

    spy = QSignalSpy(dialog.saveRequested)
    dialog.category_list.setFocus()

    QTest.keyClick(dialog.category_list, Qt.Key.Key_Return)
    app.processEvents()

    assert spy.count() == 0


def test_preferences_dialog_does_not_save_when_enter_is_pressed_on_hotkeys_table() -> None:
    app = _app()
    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    app.processEvents()

    spy = QSignalSpy(dialog.saveRequested)
    dialog.hotkeys_table.setFocus()

    QTest.keyClick(dialog.hotkeys_table, Qt.Key.Key_Return)
    app.processEvents()

    assert spy.count() == 0


def test_preferences_dialog_files_configuration_tab_shows_settings_location(tmp_path: Path) -> None:
    app = _app()
    parent, dialog = _preferences_dialog_with_config_dir(tmp_path)
    _ = parent
    dialog.show()
    app.processEvents()

    assert dialog.files_tabs.tabText(3) == "Configuration"
    assert dialog.configuration_directory_label.toolTip() == str(tmp_path)
    assert dialog.configuration_settings_path_label.text() == "desktop_settings.json"
    assert dialog.configuration_settings_path_label.toolTip() == str(
    tmp_path / "desktop_settings.json"
    )
    folder_button = next(
        button
        for button in _child_widgets(dialog, QPushButton)
        if button.text() == "Open configuration folder"
    )
    delete_button = next(
        button
        for button in _child_widgets(dialog, QPushButton)
        if button.text() == "Delete configuration file"
    )
    folder_row = folder_button.parentWidget()
    delete_row = delete_button.parentWidget()
    assert folder_row is not None
    assert delete_row is not None
    assert isinstance(folder_row.layout(), QHBoxLayout)
    assert isinstance(delete_row.layout(), QHBoxLayout)
    folder_label = _layout_widget_at(folder_row.layout(), 0)
    delete_label = _layout_widget_at(delete_row.layout(), 0)
    assert isinstance(folder_label, QLabel)
    assert isinstance(delete_label, QLabel)
    assert folder_label.text() == "Open folder"
    assert delete_label.text() == "Delete file"
    assert _layout_widget_at(folder_row.layout(), 1) is folder_button
    assert _layout_widget_at(delete_row.layout(), 1) is delete_button
    assert folder_button.mapTo(dialog, folder_button.rect().topLeft()).x() == delete_button.mapTo(
        dialog, delete_button.rect().topLeft()
    ).x()


def test_preferences_dialog_opens_configuration_folder(tmp_path: Path, monkeypatch) -> None:
    app = _app()
    parent, dialog = _preferences_dialog_with_config_dir(tmp_path)
    _ = parent
    dialog.show()
    app.processEvents()

    opened_paths: list[str] = []

    monkeypatch.setattr(os, "startfile", lambda path: opened_paths.append(path), raising=False)

    dialog._open_configuration_folder()

    assert opened_paths == [str(tmp_path)]
    assert tmp_path.exists()


def test_preferences_dialog_configuration_folder_prompt_can_cancel_creation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config_dir = tmp_path / "config"
    parent, dialog = _preferences_dialog_with_config_dir(config_dir)
    _ = parent
    dialog.show()
    app.processEvents()

    opened_paths: list[str] = []
    prompt_args: dict[str, object] = {}

    def _question(parent, title, text, buttons, default_button):
        prompt_args["title"] = title
        prompt_args["text"] = text
        prompt_args["buttons"] = buttons
        prompt_args["default_button"] = default_button
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", _question)
    monkeypatch.setattr(os, "startfile", lambda path: opened_paths.append(path), raising=False)

    dialog._open_configuration_folder()

    assert opened_paths == []
    assert not config_dir.exists()
    assert prompt_args["title"] == "Configuration folder"
    assert str(config_dir) in str(prompt_args["text"])


def test_preferences_dialog_configuration_folder_prompt_can_create_and_open(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config_dir = tmp_path / "config"
    parent, dialog = _preferences_dialog_with_config_dir(config_dir)
    _ = parent
    dialog.show()
    app.processEvents()

    opened_paths: list[str] = []
    prompt_args: dict[str, object] = {}

    def _question(parent, title, text, buttons, default_button):
        prompt_args["title"] = title
        prompt_args["text"] = text
        prompt_args["buttons"] = buttons
        prompt_args["default_button"] = default_button
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", _question)
    monkeypatch.setattr(os, "startfile", lambda path: opened_paths.append(path), raising=False)

    dialog._open_configuration_folder()

    assert opened_paths == [str(config_dir.resolve())]
    assert config_dir.exists()
    assert prompt_args["title"] == "Configuration folder"
    assert str(config_dir) in str(prompt_args["text"])


def test_preferences_dialog_delete_configuration_file_shows_info_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config_dir = tmp_path / "config"
    parent, dialog = _preferences_dialog_with_config_dir(config_dir)
    _ = parent
    dialog.show()
    app.processEvents()

    prompt_args: dict[str, object] = {}

    def _information(parent, title, text, buttons):
        prompt_args["title"] = title
        prompt_args["text"] = text
        prompt_args["buttons"] = buttons
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", _information)

    dialog._delete_configuration_file()

    assert prompt_args["title"] == "Configuration file"
    assert str(config_dir / "desktop_settings.json") in str(prompt_args["text"])
    assert not config_dir.exists()


def test_preferences_dialog_delete_configuration_file_confirms_and_deletes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_path = config_dir / "desktop_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    parent, dialog = _preferences_dialog_with_config_dir(config_dir)
    _ = parent
    dialog.show()
    app.processEvents()

    prompt_args: dict[str, object] = {}

    def _question(parent, title, text, buttons, default_button):
        prompt_args["title"] = title
        prompt_args["text"] = text
        prompt_args["buttons"] = buttons
        prompt_args["default_button"] = default_button
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", _question)

    dialog._delete_configuration_file()

    assert prompt_args["title"] == "Delete configuration file"
    assert str(settings_path.resolve()) in str(prompt_args["text"])
    assert not settings_path.exists()


def test_preferences_dialog_delete_configuration_file_cancel_keeps_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_path = config_dir / "desktop_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    parent, dialog = _preferences_dialog_with_config_dir(config_dir)
    _ = parent
    dialog.show()
    app.processEvents()

    def _question(parent, title, text, buttons, default_button):
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", _question)

    dialog._delete_configuration_file()

    assert settings_path.exists()


def test_save_discard_cancel_box_uses_dont_save_label() -> None:
    box, save_button, discard_button, cancel_button = build_save_discard_cancel_box(
        None,
        "Preferences",
        "Save preferences before closing?",
    )

    assert box.windowTitle() == "Preferences"
    assert save_button.text() == "Save"
    assert discard_button.text() == "Don't Save"
    assert cancel_button.text() == "Cancel"


def test_preferences_dialog_builds_hotkey_table() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)

    assert dialog.stack.currentIndex() == 4
    assert model.rowCount() >= 5
    assert model.index(0, 0).data() == "New"
    assert model.index(1, 0).data() == "Open..."
    assert model.index(0, 1).data() == "Ctrl+N"
    assert model.index(0, 2).data() == ""
    assert model.index(0, 3).data() == "Reset"
    assert model.columns()[1].delegate_key == "keysequence"
    assert dialog.hotkeys_table.itemDelegateForColumn(1).__class__.__name__ == "KeySequenceDelegate"
    assert dialog.hotkeys_table.editTriggers() == QTableView.EditTrigger.NoEditTriggers
    assert dialog.hotkeys_search.placeholderText() == "Search actions or shortcuts"
    assert dialog.hotkeys_search.isClearButtonEnabled() is True
    inspector_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Pixel Inspector..."
    )
    assert model.index(inspector_row, 1).data() == ""
    run_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Run..."
    )
    assert model.index(run_row, 1).data() == ""
    assert model.index(run_row, 2).data() == "Open Run"
    clear_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Clear Breakpoints"
    )
    assert model.index(clear_row, 1).data() == "Ctrl+Shift+F9"
    assert model.index(clear_row, 2).data() == "Clears all breakpoints in the current editor."


def test_preferences_dialog_shows_search_hotkeys() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)

    expected_rows = {
        "Find...": ("Ctrl+F", "Opens the find sidebar in the editor."),
        "Next": ("F3", "Moves to the next search match."),
        "Previous": ("Shift+F3", "Moves to the previous search match."),
        "Replace...": ("Ctrl+H", "Opens the replace sidebar in the editor."),
    }

    for label, (shortcut, help_text) in expected_rows.items():
        row = next(
            row
            for row in range(model.rowCount())
            if model.index(row, 0).data() == label and model.index(row, 1).data() == shortcut
        )
        assert model.index(row, 1).data() == shortcut
        assert model.index(row, 2).data() == help_text


def test_preferences_dialog_shows_cli_stop_hotkey_help_text() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)

    stop_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Stop" and model.index(row, 1).data() == "Shift+Esc"
    )
    stop_note = model.index(stop_row, 2).data()
    assert (
        "Stops recording or playback without sending Ctrl+C. Default shortcut: Shift+Esc. "
        "Use | to add alternate stop chords, such as Shift+Esc|Ctrl+C."
    ) == stop_note


def test_preferences_dialog_saves_alternate_stop_hotkey_binding() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    stop_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Stop" and model.index(row, 1).data() == "Shift+Esc"
    )
    alternate_binding = "Shift+Esc|Ctrl+C"

    assert model.setData(model.index(stop_row, 1), alternate_binding, Qt.ItemDataRole.EditRole)

    bundle = dialog.settings_bundle()
    assert bundle.application.hotkeys.bindings["stop"] == alternate_binding
    assert dialog.hotkeys().bindings["stop"] == alternate_binding


def test_preferences_dialog_warns_on_duplicate_alternate_hotkeys() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    alternate_binding = "Shift+Esc|Ctrl+C"

    assert model.setData(model.index(0, 1), alternate_binding, Qt.ItemDataRole.EditRole)
    stop_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Stop" and model.index(row, 1).data() == "Shift+Esc"
    )
    assert model.setData(model.index(stop_row, 1), alternate_binding, Qt.ItemDataRole.EditRole)
    dialog._update_hotkey_conflicts()

    assert dialog.hotkeys_warning_label.text()
    assert "conflict" in dialog.hotkeys_warning_label.text().lower()
    assert dialog.hotkeys_save_warning_label.isVisible() is True
    assert "Already used by" in model.index(stop_row, 2).data()


def test_preferences_dialog_shows_debugger_step_hotkeys() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)

    expected_rows = {
        "Step Into": ("F11", "Steps into the next expression or function call."),
        "Step Over": ("F10", "Steps over the next line or function call."),
        "Step Out": ("Shift+F11", "Runs until the current function returns."),
        "Continue": ("Ctrl+F5", "Continues execution until the next breakpoint or pause."),
        "Restart Debug": ("Ctrl+Shift+F5", "Restarts the active debug session."),
        "Stop": ("Shift+F5", "Stops the active debug session."),
        "Run Sidebar": ("", "Focuses the Run Sidebar."),
    }

    for label, (shortcut, help_text) in expected_rows.items():
        row = next(
            row
            for row in range(model.rowCount())
            if model.index(row, 0).data() == label and model.index(row, 1).data() == shortcut
        )
        assert model.index(row, 1).data() == shortcut
        assert model.index(row, 2).data() == help_text


def test_preferences_dialog_saves_debugger_tab_hotkey_binding() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    debug_tab_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Run Sidebar"
    )

    shortcut = QKeySequence("Ctrl+Alt+D").toString(QKeySequence.SequenceFormat.PortableText)
    assert model.setData(model.index(debug_tab_row, 1), shortcut, Qt.ItemDataRole.EditRole)

    bundle = dialog.settings_bundle()

    assert bundle.application.hotkeys.bindings["view_debugger_tab"] == shortcut
    assert dialog.hotkeys().bindings["view_debugger_tab"] == shortcut


def test_preferences_dialog_general_page_controls_formatted_preview_visibility() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.set_preferences(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=False,
                show_debug_tab=False,
                show_formatted_preview_tab=False,
                show_raw_recordings_tab=False,
                show_diagnostics_tab=True,
            ),
        )
    )

    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(1)
    assert dialog.show_formatted_preview_checkbox.isChecked() is False
    assert dialog.show_raw_recordings_checkbox.isChecked() is False
    assert dialog.show_diagnostics_checkbox.isChecked() is True
    assert dialog.show_analysis_tab_checkbox.isChecked() is False
    dialog.open_debug_tab_on_pause_checkbox.setChecked(False)
    dialog.show_analysis_tab_checkbox.setChecked(False)
    dialog.show_raw_recordings_checkbox.setChecked(True)
    dialog.show_diagnostics_checkbox.setChecked(False)
    assert dialog.show_analysis_tab_checkbox.isChecked() is False
    dialog.show_analysis_tab_checkbox.setChecked(True)
    assert dialog.show_analysis_tab_checkbox.isChecked() is True
    assert dialog.diagnostics_show_diagnostics_tab_checkbox.isChecked() is False
    dialog.diagnostics_show_diagnostics_tab_checkbox.setChecked(True)
    assert dialog.show_diagnostics_checkbox.isChecked() is True
    bundle = dialog.settings_bundle()
    assert bundle.application.open_debug_tab_on_pause is False
    assert bundle.application.show_debug_tab is False
    assert bundle.application.show_analysis_tab is True
    assert bundle.application.show_formatted_preview_tab is False
    assert bundle.application.show_raw_recordings_tab is True
    assert bundle.application.show_diagnostics_tab is True


def test_preferences_dialog_warns_on_duplicate_hotkeys() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    duplicate_sequence = QKeySequence("Ctrl+Shift+S").toString(QKeySequence.SequenceFormat.PortableText)

    assert model.setData(model.index(0, 1), duplicate_sequence, Qt.ItemDataRole.EditRole)
    assert model.setData(model.index(1, 1), duplicate_sequence, Qt.ItemDataRole.EditRole)
    dialog._update_hotkey_conflicts()

    expected_native = (
        QKeySequence("Ctrl+Shift+S").toString(QKeySequence.SequenceFormat.NativeText)
        or "Ctrl+Shift+S"
    )
    assert dialog.hotkeys_warning_label.text()
    assert "conflict" in dialog.hotkeys_warning_label.text().lower()
    assert dialog.hotkeys_save_warning_label.isVisible() is True
    assert dialog.hotkeys_save_warning_label.text() == "Resolve hotkey conflicts before saving"
    assert model.index(0, 2).data() == (
        f"Already used by Open... ({expected_native}), Save As... ({expected_native})"
    )
    assert model.index(1, 2).data() == (
        f"Already used by New ({expected_native}), Save As... ({expected_native})"
    )
    assert model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole).color().name() == "#fff2cc"


def test_preferences_dialog_hides_save_warning_when_conflicts_clear() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    model.setData(model.index(0, 1), "Ctrl+N", Qt.ItemDataRole.EditRole)
    model.setData(model.index(1, 1), "Ctrl+N", Qt.ItemDataRole.EditRole)
    assert dialog.hotkeys_save_warning_label.isVisible() is True

    model.setData(model.index(1, 1), "Ctrl+O", Qt.ItemDataRole.EditRole)

    assert dialog.hotkeys_save_warning_label.isVisible() is False


def test_preferences_dialog_reset_hotkey_cell_restores_default_shortcut() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    model.setData(
        model.index(0, 1),
        QKeySequence("Ctrl+Shift+S").toString(QKeySequence.SequenceFormat.PortableText),
        Qt.ItemDataRole.EditRole,
    )

    delegate = dialog.hotkeys_table.itemDelegateForColumn(3)
    assert delegate.__class__.__name__ == "ActionCellDelegate"
    option = QStyleOptionViewItem()
    option.rect = dialog.hotkeys_table.visualRect(model.index(0, 3))
    delegate.initStyleOption(option, model.index(0, 3))
    assert option.icon.isNull() is False
    assert option.features & QStyleOptionViewItem.ViewItemFeature.HasDecoration
    assert option.decorationSize.width() == 10
    assert option.decorationSize.height() == 10

    icon_rect, text_rect, text = delegate._reset_layout(option, model.index(0, 3))
    assert text == "Reset"
    assert text_rect.left() - icon_rect.right() - 1 == 4
    assert icon_rect.width() == 10
    assert text_rect.left() > icon_rect.right()

    reset_rect = dialog.hotkeys_table.visualRect(model.index(0, 3))
    QTest.mouseClick(
        dialog.hotkeys_table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        reset_rect.center(),
    )

    assert model.index(0, 1).data() == "Ctrl+N"

    model.setData(
        model.index(0, 1),
        QKeySequence("Ctrl+Shift+S").toString(QKeySequence.SequenceFormat.PortableText),
        Qt.ItemDataRole.EditRole,
    )
    reset_rect = dialog.hotkeys_table.visualRect(model.index(0, 3))
    QTest.mouseClick(
        dialog.hotkeys_table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        reset_rect.center(),
    )
    assert model.index(0, 1).data() == "Ctrl+N"


def test_preferences_dialog_reset_hotkey_cell_resolves_filtered_rows() -> None:
    app = _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    dialog.hotkeys_search.setText("save")
    app.processEvents()
    model = _table_model(dialog.hotkeys_table)

    save_row = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data() == "Save"
    )
    assert dialog.hotkeys_table.isRowHidden(save_row) is False
    model.setData(model.index(save_row, 1), "Ctrl+Alt+S", Qt.ItemDataRole.EditRole)

    reset_rect = dialog.hotkeys_table.visualRect(model.index(save_row, 3))
    QTest.mouseClick(
        dialog.hotkeys_table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        reset_rect.center(),
    )

    assert model.index(save_row, 1).data() == "Ctrl+S"


def test_preferences_dialog_restore_hotkeys_defaults_resets_rows() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)
    model.setData(
        model.index(0, 1),
        QKeySequence("Ctrl+Shift+N").toString(QKeySequence.SequenceFormat.PortableText),
        Qt.ItemDataRole.EditRole,
    )
    model.setData(
        model.index(1, 1),
        QKeySequence("Ctrl+Shift+O").toString(QKeySequence.SequenceFormat.PortableText),
        Qt.ItemDataRole.EditRole,
    )

    dialog.reset_hotkeys_settings_to_defaults()
    QApplication.processEvents()

    assert model.index(0, 1).data() == "Ctrl+N"
    assert model.index(1, 1).data() == "Ctrl+O"
    assert dialog.is_dirty() is False


def test_preferences_dialog_hotkey_restore_repaints_restored_cell() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    QApplication.processEvents()
    dialog.category_list.setCurrentRow(4)
    QApplication.processEvents()
    model = _table_model(dialog.hotkeys_table)
    shortcut_index = model.index(0, 1)
    spy = QSignalSpy(model.dataChanged)

    model.setData(shortcut_index, "", Qt.ItemDataRole.EditRole)
    QApplication.processEvents()
    assert model.index(0, 1).data() == ""
    assert spy.count() >= 1

    before_restore_count = spy.count()
    dialog.reset_hotkeys_settings_to_defaults()
    QApplication.processEvents()
    dialog.hotkeys_table.viewport().update()
    QApplication.processEvents()

    assert model.index(0, 1).data() == "Ctrl+N"
    assert spy.count() > before_restore_count


def test_preferences_dialog_hotkey_restore_clears_dirty_when_back_to_saved_state() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(4)
    model = _table_model(dialog.hotkeys_table)

    model.setData(model.index(1, 1), "Ctrl+N", Qt.ItemDataRole.EditRole)
    assert dialog.is_dirty() is True

    dialog.reset_hotkeys_settings_to_defaults()

    assert model.index(0, 1).data() == "Ctrl+N"
    assert model.index(1, 1).data() == "Ctrl+O"
    assert dialog.is_dirty() is False
    assert dialog.dirty_indicator_label.isVisible() is False


def test_preferences_dialog_filters_hotkey_rows_by_search_text() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    dialog.hotkeys_search.setText("save")

    save_row = 2
    new_row = 0
    assert dialog.hotkeys_table.isRowHidden(save_row) is False
    assert dialog.hotkeys_table.isRowHidden(new_row) is True


def test_preferences_dialog_keeps_hotkey_search_text_when_switching_pages() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    dialog.hotkeys_search.setText("save")

    dialog.category_list.setCurrentRow(0)
    dialog.category_list.setCurrentRow(4)

    assert dialog.hotkeys_search.text() == "save"
    assert dialog.hotkeys_table.isRowHidden(2) is False
    assert dialog.hotkeys_table.isRowHidden(0) is True


def test_preferences_dialog_can_restore_hotkey_search_text_programmatically() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.set_hotkeys_search_text("copy")

    dialog.category_list.setCurrentRow(0)
    dialog.category_list.setCurrentRow(4)

    assert dialog.hotkeys_search_text() == "copy"
    assert dialog.hotkeys_search.text() == "copy"
    assert dialog.hotkeys_table.isRowHidden(7) is False


def test_preferences_dialog_resets_appearance_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.set_preferences(
            DesktopSettingsBundle(
                application=DesktopApplicationSettings(
                    restore_last_workspace=True,
                    show_formatted_preview_tab=False,
                    last_workspace_path=r"C:\work\session.ass",
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
            ),
        )
    )

    dialog.category_list.setCurrentRow(0)
    dialog.restore_workspace_checkbox.setChecked(False)
    dialog.open_debug_tab_on_pause_checkbox.setChecked(True)
    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(1)
    dialog.show_formatted_preview_checkbox.setChecked(False)
    dialog.show_raw_recordings_checkbox.setChecked(False)
    dialog.show_diagnostics_checkbox.setChecked(False)
    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(0)
    dirty_state_table = dialog.findChild(QTableView, "dirtyStateStyleTable")
    assert dirty_state_table is not None
    dirty_state_model = _table_model(dirty_state_table)
    original_dirty_background = dirty_state_model.index(0, 2).data()
    dirty_state_model.setData(
        dirty_state_model.index(0, 2),
        "#101820",
        Qt.ItemDataRole.EditRole,
    )
    dialog.reset_appearance_settings_to_defaults()
    bundle = dialog.settings_bundle()

    assert bundle.application.restore_last_workspace is False
    assert bundle.application.open_debug_tab_on_pause is True
    assert bundle.application.show_formatted_preview_tab is True
    assert bundle.application.hidden_workspace_tabs_strip_collapsed is True
    assert bundle.application.show_raw_recordings_tab is False
    assert bundle.application.show_diagnostics_tab is False
    assert bundle.application.last_workspace_path == r"C:\work\session.ass"
    assert bundle.theme.appearance.dirty_indicators == DirtyIndicatorTheme()
    assert bundle.theme.appearance.workspace_tab_attention == WorkspaceTabAttentionTheme()
    assert bundle.theme.appearance.editor.background == "#101820"
    assert bundle.theme.appearance.syntax_highlighting == SyntaxHighlightTheme()
    assert bundle.theme.appearance.dirty_indicators.background == "#fff5e3"
    assert bundle.theme.appearance.dirty_indicators.selected_background == "#f0ddb4"
    assert dirty_state_model.index(0, 2).data() == original_dirty_background
    assert bundle.files == DesktopFilesSettings()
    assert dialog.is_dirty() is True


def test_preferences_dialog_exposes_search_results_appearance_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(2)

    dialog.search_results_header_active_color.setColor("#ddeeff")
    dialog.search_results_header_hovered_color.setColor("#eef5ff")
    dialog.search_results_header_active_hovered_color.setColor("#ccdfff")
    dialog.search_results_header_text_color.setColor("#445566")
    dialog.search_results_line_text_color.setColor("#112233")
    dialog.search_results_hit_text_color.setColor("#667788")
    dialog.search_results_child_border_color.setColor("#8899aa")
    dialog.search_results_header_radius_edit.setText("6px")
    dialog.search_results_header_padding_edit.setText("2px 6px")
    dialog.search_results_child_border_width_edit.setText("3px")
    dialog.search_results_child_padding_left_spin.setValue(10)
    dialog.search_results_child_margin_left_spin.setValue(6)

    bundle = dialog.settings_bundle()

    assert bundle.theme.search_results == SearchResultsTheme(
        header_active="#ddeeff",
        header_hovered="#eef5ff",
        header_active_hovered="#ccdfff",
        header_radius="6px",
        header_padding="2px 6px",
        header_text="#445566",
        line_text="#112233",
        hit_text="#667788",
        child_border_color="#8899aa",
        child_border_width="3px",
        child_padding_left=10,
        child_margin_left=6,
    )

    dialog.reset_search_results_settings_to_defaults()

    assert dialog.search_results_header_active_color.color() == "#d7e9ff"
    assert dialog.search_results_child_padding_left_spin.value() == 10
    assert dialog.search_results_child_margin_left_spin.value() == 6


def test_preferences_dialog_exposes_search_spacing_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(3)

    dialog.search_results_header_radius_edit.setText("7px")
    dialog.search_results_header_padding_edit.setText("3px 8px")
    dialog.search_results_child_border_width_edit.setText("4px")
    dialog.search_results_child_padding_left_spin.setValue(12)
    dialog.search_results_child_margin_left_spin.setValue(7)

    bundle = dialog.settings_bundle()

    assert bundle.theme.search_results == SearchResultsTheme(
        header_active="#d7e9ff",
        header_hovered="#e0efff",
        header_active_hovered="#b9d9ff",
        header_radius="7px",
        header_padding="3px 8px",
        header_text="#666666",
        line_text="#222222",
        hit_text="#666666",
        child_border_color="#8fb6e8",
        child_border_width="4px",
        child_padding_left=12,
        child_margin_left=7,
    )

    dialog.reset_search_spacing_settings_to_defaults()

    assert dialog.search_results_header_radius_edit.text() == "4px"
    assert dialog.search_results_child_border_width_edit.text() == "2px"
    assert dialog.search_results_child_padding_left_spin.value() == 8
    assert dialog.search_results_child_margin_left_spin.value() == 4


def test_preferences_dialog_resets_text_editor_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(2)
    dialog.text_editor_item_list.setCurrentRow(1)
    original_font = dialog.preferences().font
    original_scripting = dialog.preferences().scripting
    dialog.text_editor_item_list.setCurrentRow(0)
    editor_table = dialog.findChild(QTableView, "appearanceStyleTable")
    assert editor_table is not None
    editor_model = _table_model(editor_table)
    editor_model.setData(editor_model.index(0, 2), "#101820", Qt.ItemDataRole.EditRole)
    dialog.font_family_combo.setCurrentFont(QFont("Courier New", 13))
    dialog.font_size_spin.setValue(13)
    dialog.font_weight_spin.setValue(600)
    dialog.font_line_spacing_spin.setValue(1.25)
    dialog.text_editor_item_list.setCurrentRow(2)
    dialog.scripting_language_combo.setCurrentText("Custom")
    dialog.formatting_indent_spin.setValue(2)
    dialog.formatting_use_spaces_checkbox.setChecked(False)
    dialog.formatting_auto_indent_checkbox.setChecked(False)
    dialog.formatting_auto_format_checkbox.setChecked(True)

    dialog.reset_text_editor_settings_to_defaults()

    assert dialog.preferences().font == original_font
    assert dialog.preferences().scripting == original_scripting
    assert editor_model.index(0, 2).data() == "#FFFFFF"
    assert editor_model.index(2, 1).data() == "#000000"
    assert dialog.is_dirty() is False


def test_preferences_dialog_general_restore_all_defaults_resets_full_bundle() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.set_preferences(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=True,
                show_formatted_preview_tab=False,
                last_workspace_path=r"C:\work\session.ass",
                hotkeys=DesktopHotkeySettings(
                    bindings={**default_hotkey_bindings(), "save": "Ctrl+Alt+S"}
                ),
            ),
            playback=DesktopPlaybackSettings(
                repeat_count=4,
                step_mode=True,
                delay_ms=125,
                mouse_settle_ms=17,
            ),
            recording=DesktopRecordingSettings(
                recording_conversion_mode="literal",
                capture_mouse_moves=False,
                capture_mouse_buttons=False,
                capture_mouse_wheel=False,
                capture_keyboard=False,
                mouse_move_threshold_px=12,
            ),
            files=DesktopFilesSettings(
                file_extension=".foo",
                autosave_enabled=False,
                autosave_file_name="my_script",
                autosave_timestamp_suffix=False,
                autosave_output_folder=r"C:\temp\recordings",
                raw_autosave_enabled=False,
                raw_autosave_file_name="raw_capture",
                raw_autosave_timestamp_suffix=False,
                raw_autosave_output_folder=r"C:\temp\raw-recordings",
                diagnostic_log_path="logs/desktop-diagnostics.log",
            ),
            runtime=DesktopRuntimeSettings(
                max_loop_iterations=321,
                max_call_depth=45,
                default_mouse_move_speed=18,
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
                        keyword="#123456",
                        string="#234567",
                        comment="#345678",
                        number="#456789",
                    ),
                    dirty_indicators=DirtyIndicatorTheme(
                        text="#aa5500",
                        accent="#cc7700",
                        background="#fff0d9",
                        selected_background="#ffd699",
                        border="#e6b870",
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
            ),
        )
    )

    dialog.category_list.setCurrentRow(0)
    restore_button = next(
        button
        for button in _child_widgets(dialog, QPushButton)
        if button.text() == "Restore All Defaults"
    )
    restore_button.click()
    bundle = dialog.settings_bundle()
    default_sequences = default_hotkey_bindings()
    expected_hotkeys = {
        definition.action_id: QKeySequence(
            default_sequences.get(definition.action_id, "")
        ).toString(QKeySequence.SequenceFormat.PortableText)
        for definition in HOTKEY_DEFINITIONS
    }

    assert bundle.application.restore_last_workspace is False
    assert bundle.application.show_formatted_preview_tab is True
    assert bundle.application.show_debug_tab is True
    assert bundle.application.hidden_workspace_tabs_strip_collapsed is True
    assert bundle.application.last_workspace_path is None
    assert bundle.application.hotkeys.bindings == expected_hotkeys
    assert dialog.restore_workspace_checkbox.isChecked() is False
    assert dialog.open_debug_tab_on_pause_checkbox.isChecked() is True
    assert dialog.show_formatted_preview_checkbox.isChecked() is True
    assert bundle.playback == DesktopPlaybackSettings()
    assert bundle.recording == DesktopRecordingSettings()
    assert bundle.files == DesktopFilesSettings()
    assert bundle.runtime == DesktopRuntimeSettings()
    assert bundle.theme.appearance == AppearanceTheme()
    assert bundle.theme.scripting == ScriptingSettings()
    assert bundle.theme.font.size == 11
    assert bundle.theme.font.weight == 400
    assert bundle.theme.font.line_spacing_multiplier == 1.0
    assert dialog.preferences().appearance == AppearanceTheme()
    assert dialog.preferences().scripting == ScriptingSettings()
    assert dialog.hotkeys().bindings == expected_hotkeys
    assert bundle.theme.appearance.editor.background == "#ffffff"
    assert bundle.theme.appearance.editor.gutter_background == "#f2f2f2"
    assert bundle.theme.appearance.syntax_highlighting == SyntaxHighlightTheme()
    assert bundle.theme.appearance.dirty_indicators == DirtyIndicatorTheme()
    assert bundle.theme.appearance.workspace_tab_attention.enabled is True
    assert bundle.theme.appearance.workspace_tab_attention.accent == "#2b7de9"
    assert bundle.theme.search_results == SearchResultsTheme()
    assert dialog.is_dirty() is True


def test_preferences_dialog_exposes_dirty_indicator_appearance_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.appearance_item_list.setCurrentRow(0)
    dialog.dirty_indicator_text_row.setColor("#aa5500")
    dialog.dirty_indicator_accent_row.setColor("#cc7700")
    dialog.dirty_indicator_text_background_row.setColor("#fff0d9")
    dialog.dirty_indicator_selected_background_row.setColor("#ffd699")
    dialog.dirty_indicator_border_row.setColor("#e6b870")
    dialog.workspace_tab_attention_enabled_checkbox.setChecked(False)
    dialog.workspace_tab_attention_color_swatch.setColor("#3366cc")

    bundle = dialog.settings_bundle()

    assert bundle.theme.appearance.dirty_indicators == DirtyIndicatorTheme(
        text="#aa5500",
        accent="#cc7700",
        background="#fff0d9",
        selected_background="#ffd699",
        border="#e6b870",
    )
    assert bundle.theme.appearance.workspace_tab_attention == WorkspaceTabAttentionTheme(
        enabled=False,
        accent="#3366cc",
    )


def test_preferences_dialog_warns_when_theme_contrast_is_too_low() -> None:
    app = _app()

    dialog = PreferencesDialog()
    dialog.show()
    app.processEvents()
    dialog.category_list.setCurrentRow(2)

    dialog._editor_style_data["editor_text"] = "#ffffff"
    dialog._emit_preferences_changed()

    assert dialog.theme_readability_warning_label.isVisible() is True
    assert "too low to save safely" in dialog.theme_readability_warning_label.text().lower()
    assert "contrast is only" in dialog.theme_readability_warning_label.toolTip()


def test_preferences_dialog_marks_dirty_when_color_tables_are_edited() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(3)

    appearance_style_model = dialog.appearance_style_model
    style_model = dialog.style_model
    dirty_state_model = dialog.dirty_state_model

    original_appearance_background = appearance_style_model.index(0, 2).data()
    original_style_keyword = style_model.index(0, 1).data()
    original_dirty_background = dirty_state_model.index(0, 2).data()

    appearance_style_model.setData(
        appearance_style_model.index(0, 2),
        "#101820",
        Qt.ItemDataRole.EditRole,
    )
    style_model.setData(style_model.index(0, 1), "#123456", Qt.ItemDataRole.EditRole)
    dirty_state_model.setData(
        dirty_state_model.index(0, 2),
        "#f0ddb4",
        Qt.ItemDataRole.EditRole,
    )

    assert dialog.is_dirty() is True
    assert dialog.dirty_indicator_label.isVisible() is True
    assert dialog.category_list.item(2).text() == "! Editing"
    assert dialog.category_list.item(3).text() == "! Workspace"

    appearance_style_model.setData(
        appearance_style_model.index(0, 2),
        original_appearance_background,
        Qt.ItemDataRole.EditRole,
    )
    style_model.setData(
        style_model.index(0, 1),
        original_style_keyword,
        Qt.ItemDataRole.EditRole,
    )
    dirty_state_model.setData(
        dirty_state_model.index(0, 2),
        original_dirty_background,
        Qt.ItemDataRole.EditRole,
    )

    assert dialog.is_dirty() is False
    assert dialog.dirty_indicator_label.isVisible() is False
    assert dialog.category_list.item(2).text() == "Editing"
    assert dialog.category_list.item(3).text() == "Workspace"


def test_preferences_dialog_shows_dirty_indicator_for_unsaved_changes() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()

    assert dialog.dirty_indicator_label.isVisible() is False

    dialog.restore_workspace_checkbox.setChecked(True)

    assert dialog.is_dirty() is True
    assert dialog.dirty_indicator_label.isVisible() is True
    assert dialog.dirty_indicator_label.text() == "Unsaved changes"


def test_preferences_dialog_hides_dirty_indicator_after_mark_saved() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.restore_workspace_checkbox.setChecked(True)

    dialog.mark_saved()

    assert dialog.is_dirty() is False
    assert dialog.dirty_indicator_label.isVisible() is False
    assert dialog.windowTitle() == "Preferences"


def test_preferences_dialog_marks_dirty_sections_in_category_list() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()

    assert dialog.category_list.item(0).text() == "General"
    assert dialog.category_list.item(2).text() == "Editing"
    assert dialog.category_list.item(3).text() == "Workspace"
    assert dialog.category_list.item(1).text() == "Files"
    assert dialog.category_list.item(7).text() == "Runtime"
    assert dialog.category_list.item(8).text() == "Diagnostics"
    assert dialog.text_editor_item_list.item(0).text() == "Editor"
    assert dialog.appearance_item_list.item(0).text() == "Dirty State"
    assert dialog.appearance_item_list.item(1).text() == "Layout"

    dialog.restore_workspace_checkbox.setChecked(True)

    assert dialog.category_list.item(0).text() == "! General"
    assert dialog.category_list.item(0).font().bold() is True
    assert dialog.category_list.item(0).foreground().color().name() == "#7a4a00"
    assert dialog.category_list.item(0).background().color().name() == "#f0ddb4"
    assert "#f0ddb4" in dialog._page_header_frames["General"].styleSheet()
    assert "border-radius: 10px" in dialog._page_header_frames["General"].styleSheet()
    assert dialog.category_list.item(2).text() == "Editing"
    assert dialog.category_list.item(2).font().bold() is False
    assert dialog.appearance_item_list.item(0).text() == "Dirty State"

    dialog.mark_saved()

    assert dialog.category_list.item(0).text() == "General"
    assert dialog.category_list.item(0).font().bold() is False
    assert dialog.is_dirty() is False


def test_preferences_dialog_exposes_style_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(2)
    dialog.text_editor_item_list.setCurrentRow(2)
    style_model = _table_model(dialog.style_table)
    style_model.setData(style_model.index(0, 1), "#123456", Qt.ItemDataRole.EditRole)
    style_model.setData(style_model.index(1, 1), "#234567", Qt.ItemDataRole.EditRole)
    style_model.setData(style_model.index(2, 1), "#345678", Qt.ItemDataRole.EditRole)
    style_model.setData(style_model.index(3, 1), "#456789", Qt.ItemDataRole.EditRole)

    bundle = dialog.settings_bundle()

    assert bundle.theme.appearance.syntax_highlighting == SyntaxHighlightTheme(
        keyword="#123456",
        string="#234567",
        comment="#345678",
        number="#456789",
    )
    assert dialog.category_list.item(2).text() == "! Editing"


def test_preferences_dialog_exposes_files_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)
    dialog.recording_raw_autosave_checkbox.setChecked(True)
    dialog.recording_raw_autosave_file_name_edit.setText("raw_capture")
    dialog.recording_raw_autosave_timestamp_checkbox.setChecked(True)
    dialog.recording_raw_autosave_folder_edit.setText(r"C:\temp\raw-recordings")
    dialog.diagnostic_log_path_edit.setText(r"C:\temp\diagnostics\desktop.log")
    dialog.recording_autosave_checkbox.setChecked(True)
    dialog.recording_autosave_file_name_edit.setText("my_script")
    dialog.recording_autosave_timestamp_checkbox.setChecked(False)
    dialog.recording_autosave_folder_edit.setText(r"C:\temp\recordings")
    dialog.scripting_extension_edit.setText(".foo")

    bundle = dialog.settings_bundle()

    assert bundle.files == DesktopFilesSettings(
        file_extension=".foo",
        autosave_enabled=True,
        autosave_file_name="my_script",
        autosave_timestamp_suffix=False,
        autosave_output_folder=r"C:\temp\recordings",
        raw_autosave_enabled=True,
        raw_autosave_file_name="raw_capture",
        raw_autosave_timestamp_suffix=True,
        raw_autosave_output_folder=r"C:\temp\raw-recordings",
        diagnostic_log_path=r"C:\temp\diagnostics\desktop.log",
    )
    assert dialog.category_list.item(1).text() == "! Files"


def test_preferences_dialog_shows_resolved_file_folder_previews() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)

    dialog.recording_raw_autosave_folder_edit.setText(r"C:\temp\raw-recordings")
    dialog.recording_raw_autosave_file_name_edit.setText("raw_capture")
    dialog.recording_raw_autosave_timestamp_checkbox.setChecked(False)
    dialog.recording_autosave_folder_edit.setText(r"C:\temp\recordings")
    dialog.recording_autosave_file_name_edit.setText("my_script")
    dialog.recording_autosave_timestamp_checkbox.setChecked(False)
    dialog.scripting_extension_edit.setText(".ass")

    assert dialog.raw_autosave_preview_label.text() == (
        r"Raw recording will be saved as: C:\temp\raw-recordings/raw_capture.json"
    )
    assert dialog.converted_autosave_preview_label.text() == (
        r"Converted script will be saved as: C:\temp\recordings/my_script.ass"
    )


def test_preferences_dialog_resolves_default_recording_folder_against_app_root_when_config_dir_is_default(
    tmp_path: Path,
) -> None:
    _app()

    parent, dialog = _preferences_dialog_with_config_dir(tmp_path / "config")
    _ = parent
    dialog.category_list.setCurrentRow(1)

    assert dialog.raw_autosave_preview_label.text().startswith(
        f"Raw recording will be saved as: {tmp_path / 'recordings'}"
    )
    assert dialog.converted_autosave_preview_label.text().startswith(
        f"Converted script will be saved as: {tmp_path / 'recordings'}"
    )


def test_preferences_dialog_shows_resolved_diagnostics_folder_preview() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)

    assert dialog.diagnostics_log_preview_label.text().startswith(
        "Diagnostics log will be saved as: "
    )
    assert "actionshellscript_diagnostics_" in dialog.diagnostics_log_path_label.text()

    dialog.diagnostic_log_path_edit.setText(r"C:\temp\logs\desktop.log")

    assert dialog.diagnostics_log_path_label.text() == r"C:\temp\logs\desktop.log"
    assert dialog.diagnostics_log_preview_label.text() == (
        r"Diagnostics log will be saved as: C:\temp\logs\desktop.log"
    )


def test_preferences_dialog_resolves_diagnostics_label_text_for_relative_absolute_and_empty_paths() -> None:
    _app()

    parent, dialog = _preferences_dialog_with_config_dir(Path(r"C:\temp\config"))
    _ = parent
    dialog.category_list.setCurrentRow(1)

    dialog.diagnostic_log_path_edit.setText("logs/desktop.log")
    assert dialog.diagnostics_log_path_label.text() == r"C:\temp\config\logs\desktop.log"

    dialog.diagnostic_log_path_edit.setText(r"C:\temp\logs\desktop.log")
    assert dialog.diagnostics_log_path_label.text() == r"C:\temp\logs\desktop.log"

    dialog.diagnostic_log_path_edit.setText("")
    assert "actionshellscript_diagnostics_" in dialog.diagnostics_log_path_label.text()


def test_preferences_dialog_converted_browse_uses_resolved_folder_for_relative_paths_and_keeps_absolute_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()

    parent, dialog = _preferences_dialog_with_config_dir(tmp_path)
    dialog.category_list.setCurrentRow(1)

    captured_start_dirs: list[str] = []

    def fake_get_existing_directory(_parent, _title, start_dir):
        captured_start_dirs.append(start_dir)
        return str(tmp_path / "chosen-converted")

    monkeypatch.setattr(
        "apps.desktop.preferences_dialog.QFileDialog.getExistingDirectory",
        fake_get_existing_directory,
    )

    dialog.recording_autosave_folder_edit.setText("converted-recordings")
    dialog._choose_recording_autosave_folder()
    assert captured_start_dirs[0] == str(tmp_path / "converted-recordings")
    assert dialog.recording_autosave_folder_edit.text() == str(tmp_path / "chosen-converted")

    dialog.recording_autosave_folder_edit.setText(r"C:\temp\recordings")
    dialog._choose_recording_autosave_folder()
    assert captured_start_dirs[1] == r"C:\temp\recordings"
    assert dialog.recording_autosave_folder_edit.text() == str(tmp_path / "chosen-converted")


def test_preferences_dialog_diagnostic_browse_uses_resolved_start_path_for_relative_absolute_and_empty_cases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()

    parent, dialog = _preferences_dialog_with_config_dir(tmp_path / "config")
    _ = parent
    dialog.category_list.setCurrentRow(1)

    captured_start_dirs: list[str] = []

    def fake_get_save_file_name(_parent, _title, start_file, _filter):
        captured_start_dirs.append(start_file)
        return (str(tmp_path / "chosen.log"), "")

    monkeypatch.setattr(
        "apps.desktop.preferences_dialog.QFileDialog.getSaveFileName",
        fake_get_save_file_name,
    )
    monkeypatch.setattr(
        "apps.desktop.preferences_dialog.resolve_diagnostic_log_path",
        lambda: tmp_path / "default" / "actionshellscript_diagnostics_20260505.log",
    )

    dialog.diagnostic_log_path_edit.setText("logs/desktop.log")
    dialog._choose_diagnostic_log_path()
    assert captured_start_dirs[0] == str(tmp_path / "config" / "logs" / "desktop.log")
    assert dialog.diagnostic_log_path_edit.text() == str(tmp_path / "chosen.log")

    dialog.diagnostic_log_path_edit.setText(r"C:\temp\logs\desktop.log")
    dialog._choose_diagnostic_log_path()
    assert captured_start_dirs[1] == r"C:\temp\logs\desktop.log"
    assert dialog.diagnostic_log_path_edit.text() == str(tmp_path / "chosen.log")

    dialog.diagnostic_log_path_edit.setText("")
    dialog._choose_diagnostic_log_path()
    assert captured_start_dirs[2] == str(
        tmp_path / "default" / "actionshellscript_diagnostics_20260505.log"
    )
    assert dialog.diagnostic_log_path_edit.text() == str(tmp_path / "chosen.log")


def test_preferences_dialog_raw_browse_uses_resolved_folder_for_relative_paths_and_keeps_absolute_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()

    parent, dialog = _preferences_dialog_with_config_dir(tmp_path)
    dialog.category_list.setCurrentRow(1)

    captured_start_dirs: list[str] = []

    def fake_get_existing_directory(_parent, _title, start_dir):
        captured_start_dirs.append(start_dir)
        return str(tmp_path / "chosen-raw")

    monkeypatch.setattr(
        "apps.desktop.preferences_dialog.QFileDialog.getExistingDirectory",
        fake_get_existing_directory,
    )

    dialog.recording_raw_autosave_folder_edit.setText("raw-recordings")
    dialog._choose_recording_raw_autosave_folder()
    assert captured_start_dirs[0] == str(tmp_path / "raw-recordings")
    assert dialog.recording_raw_autosave_folder_edit.text() == str(tmp_path / "chosen-raw")

    dialog.recording_raw_autosave_folder_edit.setText(r"C:\temp\raw-recordings")
    dialog._choose_recording_raw_autosave_folder()
    assert captured_start_dirs[1] == r"C:\temp\raw-recordings"
    assert dialog.recording_raw_autosave_folder_edit.text() == str(tmp_path / "chosen-raw")


def test_preferences_dialog_disables_raw_autosave_preview_when_autosave_is_off() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)
    dialog.recording_raw_autosave_folder_edit.setText(r"C:\temp\raw-recordings")
    dialog.recording_raw_autosave_file_name_edit.setText("raw_capture")
    dialog.recording_raw_autosave_timestamp_checkbox.setChecked(False)

    dialog.recording_raw_autosave_checkbox.setChecked(False)

    assert (
        dialog.raw_autosave_preview_label.text()
        == "Raw recording autosave is disabled. No file will be saved automatically."
    )

    dialog.recording_raw_autosave_checkbox.setChecked(True)

    assert (
        dialog.raw_autosave_preview_label.text()
        == r"Raw recording will be saved as: C:\temp\raw-recordings/raw_capture.json"
    )


def test_preferences_dialog_disables_converted_autosave_preview_when_autosave_is_off() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)
    dialog.recording_autosave_folder_edit.setText(r"C:\temp\recordings")
    dialog.recording_autosave_file_name_edit.setText("my_script")
    dialog.recording_autosave_timestamp_checkbox.setChecked(False)
    dialog.scripting_extension_edit.setText(".foo")

    dialog.recording_autosave_checkbox.setChecked(False)

    assert (
        dialog.converted_autosave_preview_label.text()
        == "Converted script autosave is disabled. No file will be saved automatically."
    )

    dialog.recording_autosave_checkbox.setChecked(True)

    assert (
        dialog.converted_autosave_preview_label.text()
        == r"Converted script will be saved as: C:\temp\recordings/my_script.foo"
    )


def test_preferences_dialog_exposes_scripting_placeholder_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(2)
    dialog.text_editor_item_list.setCurrentRow(2)
    dialog.scripting_language_combo.setCurrentText("Custom")
    dialog.formatting_indent_spin.setValue(2)
    dialog.formatting_use_spaces_checkbox.setChecked(False)
    dialog.formatting_auto_indent_checkbox.setChecked(False)
    dialog.formatting_auto_format_checkbox.setChecked(True)

    bundle = dialog.settings_bundle()

    assert bundle.theme.scripting == ScriptingSettings(
        language="Custom",
        indent_width=2,
        use_spaces=False,
        auto_indent=False,
        auto_format_on_save=True,
    )
    assert bundle.files.file_extension == ".ass"
    assert dialog.category_list.item(2).text() == "! Editing"

    dialog.text_editor_item_list.setCurrentRow(1)
    dialog.font_size_spin.setValue(14)

    assert dialog.category_list.item(2).text() == "! Editing"
    assert dialog.text_editor_item_list.item(1).text() == "! Typography"
    assert dialog.category_list.item(2).font().bold() is True
    assert dialog.category_list.item(2).foreground().color().name() == "#7a4a00"
    assert dialog.category_list.item(2).background().color().name() == "#f0ddb4"
    assert "#f0ddb4" in dialog._page_header_frames["Editing"].styleSheet()


def test_preferences_dialog_exposes_playback_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(5)
    dialog.playback_repeat_spin.setValue(4)
    dialog.playback_step_checkbox.setChecked(True)
    dialog.playback_send_key_taps_checkbox.setChecked(True)
    dialog.playback_delay_spin.setValue(125)
    dialog.playback_mouse_settle_spin.setValue(17)
    dialog.playback_interruptible_sleep_chunk_spin.setValue(20)

    bundle = dialog.settings_bundle()

    assert bundle.playback == DesktopPlaybackSettings(
        repeat_count=4,
        step_mode=True,
        delay_ms=125,
        mouse_settle_ms=17,
        interruptible_sleep_chunk_ms=20,
        send_key_taps_instead_of_text=True,
    )


def test_preferences_dialog_resets_playback_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(5)
    dialog.playback_repeat_spin.setValue(4)
    dialog.playback_step_checkbox.setChecked(True)
    dialog.playback_send_key_taps_checkbox.setChecked(True)
    dialog.playback_delay_spin.setValue(125)
    dialog.playback_mouse_settle_spin.setValue(17)
    dialog.playback_interruptible_sleep_chunk_spin.setValue(20)

    dialog.reset_playback_settings_to_defaults()

    assert dialog.playback_repeat_spin.value() == 1
    assert dialog.playback_step_checkbox.isChecked() is False
    assert dialog.playback_send_key_taps_checkbox.isChecked() is False
    assert dialog.playback_delay_spin.value() == 0
    assert dialog.playback_mouse_settle_spin.value() == 0
    assert dialog.playback_interruptible_sleep_chunk_spin.value() == 50
    assert "stop playback faster" in dialog.playback_interruptible_sleep_chunk_spin.toolTip()
    assert dialog.is_dirty() is False


def test_preferences_dialog_exposes_recording_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    assert dialog.files_tabs.count() == 4
    assert [dialog.files_tabs.tabText(i) for i in range(dialog.files_tabs.count())] == [
        "Raw recording",
        "Converted script",
        "Diagnostics",
        "Configuration",
    ]
    capture_form = _required_child(dialog.recording_capture_tab, QFormLayout)
    assert capture_form.rowCount() == 7
    assert capture_form.itemAt(4, QFormLayout.ItemRole.LabelRole).widget().text() == (
        "Exclude main window during recording"
    )
    assert capture_form.itemAt(5, QFormLayout.ItemRole.LabelRole).widget().text() == (
        "Mouse move threshold"
    )
    assert capture_form.itemAt(6, QFormLayout.ItemRole.LabelRole).widget().text() == (
        "Recording conversion mode"
    )
    dialog.category_list.setCurrentRow(4)
    dialog.recording_capture_mouse_moves_checkbox.setChecked(False)
    dialog.recording_capture_mouse_buttons_checkbox.setChecked(True)
    dialog.recording_capture_mouse_wheel_checkbox.setChecked(False)
    dialog.recording_capture_keyboard_checkbox.setChecked(True)
    dialog.recording_exclude_main_window_checkbox.setChecked(False)
    dialog.recording_mouse_move_threshold_spin.setValue(12)

    bundle = dialog.settings_bundle()

    assert bundle.recording == DesktopRecordingSettings(
        recording_conversion_mode="promote_generated",
        capture_mouse_moves=False,
        capture_mouse_buttons=True,
        capture_mouse_wheel=False,
        capture_keyboard=True,
        mouse_move_threshold_px=12,
        exclude_main_window_during_recording=False,
    )


def test_preferences_dialog_resets_recording_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(4)
    dialog.recording_capture_mouse_moves_checkbox.setChecked(False)
    dialog.recording_capture_mouse_buttons_checkbox.setChecked(False)
    dialog.recording_capture_mouse_wheel_checkbox.setChecked(False)
    dialog.recording_capture_keyboard_checkbox.setChecked(False)
    dialog.recording_exclude_main_window_checkbox.setChecked(False)
    dialog.recording_mouse_move_threshold_spin.setValue(12)

    dialog.reset_recording_settings_to_defaults()

    assert dialog.recording_capture_mouse_moves_checkbox.isChecked() is True
    assert dialog.recording_capture_mouse_buttons_checkbox.isChecked() is True
    assert dialog.recording_capture_mouse_wheel_checkbox.isChecked() is True
    assert dialog.recording_capture_keyboard_checkbox.isChecked() is True
    assert dialog.recording_exclude_main_window_checkbox.isChecked() is True
    assert dialog.recording_exclude_main_window_checkbox.text() == (
        "Exclude main window during recording"
    )
    assert "only capture the target app" in dialog.recording_exclude_main_window_checkbox.toolTip()
    assert dialog.recording_conversion_mode_combo.count() == 2
    assert dialog.recording_conversion_mode_combo.currentData() == "promote_generated"
    assert dialog.recording_mouse_move_threshold_spin.value() == 0
    assert dialog.is_dirty() is False
    assert dialog.dirty_indicator_label.isVisible() is False


def test_preferences_dialog_resets_files_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(1)
    dialog.recording_raw_autosave_checkbox.setChecked(False)
    dialog.recording_raw_autosave_file_name_edit.setText("raw_capture")
    dialog.recording_raw_autosave_timestamp_checkbox.setChecked(False)
    dialog.recording_raw_autosave_folder_edit.setText(r"C:\temp\raw-recordings")
    dialog.diagnostic_log_path_edit.setText(r"C:\temp\diagnostics\desktop.log")
    dialog.recording_autosave_checkbox.setChecked(False)
    dialog.recording_autosave_file_name_edit.setText("my_script")
    dialog.recording_autosave_timestamp_checkbox.setChecked(False)
    dialog.recording_autosave_folder_edit.setText(r"C:\temp\recordings")
    dialog.scripting_extension_edit.setText(".foo")

    dialog.reset_files_settings_to_defaults()

    assert dialog.recording_raw_autosave_checkbox.isChecked() is True
    assert dialog.recording_raw_autosave_file_name_edit.text() == "recording"
    assert dialog.recording_raw_autosave_timestamp_checkbox.isChecked() is True
    assert dialog.recording_raw_autosave_folder_edit.text() == "recordings"
    assert dialog.recording_raw_autosave_file_name_edit.isEnabled() is True
    assert dialog.recording_autosave_checkbox.isChecked() is True
    assert dialog.recording_autosave_file_name_edit.text() == "recording"
    assert dialog.recording_autosave_timestamp_checkbox.isChecked() is True
    assert dialog.recording_autosave_folder_edit.text() == "recordings"
    assert dialog.recording_autosave_file_name_edit.isEnabled() is True
    assert dialog.diagnostic_log_path_edit.text() == ""
    assert dialog.scripting_extension_edit.text() == ".ass"
    assert dialog.is_dirty() is False
    assert dialog.windowTitle() == "Preferences"


def test_preferences_dialog_exposes_runtime_settings() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)
    dialog.runtime_max_loop_iterations_spin.setValue(321)
    dialog.runtime_max_call_depth_spin.setValue(45)
    dialog.runtime_default_mouse_move_speed_spin.setValue(18)
    dialog.runtime_mouse_movement_min_steps_spin.setValue(3)
    dialog.runtime_mouse_movement_max_steps_spin.setValue(15)
    dialog.runtime_mouse_movement_step_distance_px_spin.setValue(6)
    curve_model = dialog.runtime_mouse_movement_curve_model
    curve_model.setData(curve_model.index(0, 0), 1, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(0, 1), 320, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 0), 25, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 1), 400, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(2, 0), 50, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(2, 1), 240, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(3, 0), 75, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(3, 1), 120, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(4, 0), 90, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(4, 1), 80, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(5, 0), 100, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(5, 1), 60, Qt.ItemDataRole.EditRole)

    bundle = dialog.settings_bundle()

    assert bundle.runtime == DesktopRuntimeSettings(
        max_loop_iterations=321,
        max_call_depth=45,
        default_mouse_move_speed=18,
        show_mouse_movement_reference_curve=True,
        mouse_movement_profile=MouseMovementProfile(
            duration_curve=((1, 320), (25, 400), (50, 240), (75, 120), (90, 80), (100, 60)),
            min_steps=3,
            max_steps=15,
            step_distance_px=6,
        ),
    )


def test_preferences_dialog_loads_mouse_movement_step_settings_from_bundle() -> None:
    _app()

    dialog = PreferencesDialog()
    bundle = DesktopSettingsBundle(
        runtime=DesktopRuntimeSettings(
            show_mouse_movement_reference_curve=False,
            mouse_movement_profile=MouseMovementProfile(
                duration_curve=((1, 320), (50, 240), (100, 60)),
                min_steps=4,
                max_steps=18,
                step_distance_px=5,
            )
        )
    )

    dialog.set_preferences(bundle)

    assert dialog.runtime_mouse_movement_min_steps_spin.value() == 4
    assert dialog.runtime_mouse_movement_max_steps_spin.value() == 18
    assert dialog.runtime_mouse_movement_step_distance_px_spin.value() == 5
    assert dialog.runtime_mouse_movement_reference_checkbox.isChecked() is False
    assert dialog.runtime_mouse_movement_curve_preview.reference_curve_visible() is False
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile(
        duration_curve=((1, 320), (50, 240), (100, 60)),
        min_steps=4,
        max_steps=18,
        step_distance_px=5,
    )


def test_preferences_dialog_resets_runtime_settings_to_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)
    dialog.runtime_max_loop_iterations_spin.setValue(321)
    dialog.runtime_max_call_depth_spin.setValue(45)
    dialog.runtime_default_mouse_move_speed_spin.setValue(18)
    dialog.runtime_mouse_movement_min_steps_spin.setValue(4)
    dialog.runtime_mouse_movement_max_steps_spin.setValue(22)
    dialog.runtime_mouse_movement_step_distance_px_spin.setValue(5)
    curve_model = dialog.runtime_mouse_movement_curve_model
    curve_model.setData(curve_model.index(0, 0), 1, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(0, 1), 0, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 0), 50, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 1), 240, Qt.ItemDataRole.EditRole)

    dialog.reset_execution_settings_to_defaults()

    assert dialog.runtime_max_loop_iterations_spin.value() == 100_000
    assert dialog.runtime_max_call_depth_spin.value() == 250
    assert dialog.runtime_default_mouse_move_speed_spin.value() == 10
    assert dialog.runtime_mouse_movement_reference_checkbox.isChecked() is True
    assert dialog.runtime_mouse_movement_min_steps_spin.value() == 1
    assert dialog.runtime_mouse_movement_max_steps_spin.value() == 120
    assert dialog.runtime_mouse_movement_step_distance_px_spin.value() == 8
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile()
    assert dialog.is_dirty() is False


def test_preferences_dialog_marks_dirty_when_mouse_movement_curve_is_edited() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()
    dialog.category_list.setCurrentRow(7)
    curve_model = dialog.runtime_mouse_movement_curve_model

    curve_model.setData(curve_model.index(1, 1), 321, Qt.ItemDataRole.EditRole)

    assert dialog.is_dirty() is True
    assert dialog.dirty_indicator_label.isVisible() is True
    assert dialog.category_list.item(7).text() == "! Runtime"

    curve_model.setData(curve_model.index(1, 1), 320, Qt.ItemDataRole.EditRole)

    assert dialog.is_dirty() is False
    assert dialog.dirty_indicator_label.isVisible() is False
    assert dialog.category_list.item(7).text() == "Runtime"


def test_preferences_dialog_runtime_curve_presets_apply_expected_profiles() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)

    assert dialog.runtime_tabs.count() == 3
    assert dialog.runtime_tabs.tabText(0) == "Execution"
    assert dialog.runtime_tabs.tabText(1) == "Mouse Movement Curve"
    assert dialog.runtime_tabs.tabText(2) == "Step Controls"
    assert any(label.text() == "Mouse Movement Curve" for label in _child_widgets(dialog, QLabel))

    fast_button = next(button for button in _child_widgets(dialog, QPushButton) if button.text() == "Fast")
    slow_button = next(button for button in _child_widgets(dialog, QPushButton) if button.text() == "Slow")
    smooth_button = next(button for button in _child_widgets(dialog, QPushButton) if button.text() == "Smooth")
    balanced_button = next(
        button for button in _child_widgets(dialog, QPushButton) if button.text() == "Balanced"
    )

    fast_button.click()
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile.fast()

    slow_button.click()
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile.slow()

    smooth_button.click()
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile.smooth()

    balanced_button.click()
    assert dialog.runtime_settings().mouse_movement_profile == MouseMovementProfile.balanced()


def test_preferences_dialog_renders_mouse_movement_curve_preview_from_curve_table() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)

    curve_model = dialog.runtime_mouse_movement_curve_model
    curve_model.setData(curve_model.index(0, 0), 1, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(0, 1), 320, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 0), 25, Qt.ItemDataRole.EditRole)
    curve_model.setData(curve_model.index(1, 1), 400, Qt.ItemDataRole.EditRole)

    assert dialog.runtime_mouse_movement_curve_preview.curve_points()[:2] == ((1, 320), (25, 400))


def test_preferences_dialog_runtime_curve_presets_change_preview_shape() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)
    preview = dialog.runtime_mouse_movement_curve_preview
    assert preview is not None
    preview.resize(640, 320)

    dialog._apply_mouse_movement_curve_preset(MouseMovementProfile.fast())
    fast_points = preview._mapped_points()

    dialog._apply_mouse_movement_curve_preset(MouseMovementProfile.balanced())
    balanced_points = preview._mapped_points()

    assert fast_points[0][1] != balanced_points[0][1]
    assert fast_points[0][1] > balanced_points[0][1]


def test_preferences_dialog_runtime_curve_reference_checkbox_controls_overlay_visibility() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)

    checkbox = dialog.runtime_mouse_movement_reference_checkbox
    preview = dialog.runtime_mouse_movement_curve_preview

    assert checkbox.isChecked() is True
    assert preview.reference_curve_visible() is True
    assert dialog.runtime_settings().show_mouse_movement_reference_curve is True
    assert dialog.is_dirty() is False

    checkbox.setChecked(False)
    assert preview.reference_curve_visible() is False
    assert dialog.runtime_settings().show_mouse_movement_reference_curve is False
    assert dialog.is_dirty() is True

    checkbox.setChecked(True)
    assert preview.reference_curve_visible() is True
    assert dialog.runtime_settings().show_mouse_movement_reference_curve is True
    assert dialog.is_dirty() is False


def test_preferences_dialog_places_mouse_movement_preview_to_the_right_of_the_editor() -> None:
    app = _app()

    dialog = PreferencesDialog()
    dialog.resize(1700, 980)
    dialog.show()
    dialog.category_list.setCurrentRow(7)
    app.processEvents()

    splitter = dialog.findChild(QSplitter, "runtimeMouseMovementCurveContentSplitter")
    editor_scroll = dialog.findChild(QScrollArea, "runtimeMouseMovementCurveEditorScrollArea")
    editor_panel = dialog.findChild(QFrame, "runtimeMouseMovementCurveEditorPanel")
    info_panel = dialog.findChild(QFrame, "runtimeMouseMovementCurveInfoFrame")
    preview = dialog.findChild(QWidget, "runtimeMouseMovementCurvePreview")
    assert splitter is not None
    assert editor_scroll is not None
    assert editor_panel is not None
    assert info_panel is not None
    assert preview is not None

    assert splitter.orientation() == Qt.Orientation.Horizontal
    editor_x = editor_scroll.mapTo(dialog, editor_scroll.rect().topLeft()).x()
    info_x = info_panel.mapTo(dialog, info_panel.rect().topLeft()).x()
    editor_y = editor_scroll.mapTo(dialog, editor_scroll.rect().topLeft()).y()
    info_y = info_panel.mapTo(dialog, info_panel.rect().topLeft()).y()
    assert info_x > editor_x
    assert abs(info_y - editor_y) <= 4


def test_preferences_dialog_collapses_mouse_movement_preview_below_editor_when_narrow() -> None:
    app = _app()

    dialog = PreferencesDialog()
    dialog.resize(980, 980)
    dialog.show()
    dialog.category_list.setCurrentRow(7)
    app.processEvents()

    splitter = dialog.findChild(QSplitter, "runtimeMouseMovementCurveContentSplitter")
    editor_scroll = dialog.findChild(QScrollArea, "runtimeMouseMovementCurveEditorScrollArea")
    info_panel = dialog.findChild(QFrame, "runtimeMouseMovementCurveInfoFrame")
    assert splitter is not None
    assert editor_scroll is not None
    assert info_panel is not None

    assert splitter.orientation() == Qt.Orientation.Vertical
    editor_y = editor_scroll.mapTo(dialog, editor_scroll.rect().topLeft()).y()
    info_y = info_panel.mapTo(dialog, info_panel.rect().topLeft()).y()
    assert info_y > editor_y


def test_preferences_dialog_mouse_movement_preview_has_room_for_header_and_badges() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)

    preview = dialog.runtime_mouse_movement_curve_preview
    assert preview.minimumHeight() >= 200


def test_preferences_dialog_can_reset_runtime_reference_checkbox_to_default() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(7)
    dialog.runtime_mouse_movement_reference_checkbox.setChecked(False)

    assert dialog.is_dirty() is True

    dialog.reset_execution_settings_to_defaults()

    assert dialog.runtime_mouse_movement_reference_checkbox.isChecked() is True
    assert dialog.runtime_mouse_movement_curve_preview.reference_curve_visible() is True
    assert dialog.runtime_settings().show_mouse_movement_reference_curve is True
    assert dialog.is_dirty() is False


def test_preferences_dialog_mouse_movement_curve_preview_formats_tooltip_text() -> None:
    _app()

    dialog = PreferencesDialog()
    preview = dialog.runtime_mouse_movement_curve_preview
    preview.set_curve_points(((1, 320), (25, 400), (100, 60)))

    assert preview._point_tooltip_text(0) == "Speed: 1%\nDuration: 320 ms"
    assert preview._point_tooltip_text(1) == "Speed: 25%\nDuration: 400 ms"


def test_preferences_dialog_section_reset_buttons_restore_only_their_own_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(2)
    dialog.text_editor_item_list.setCurrentRow(0)
    editor_table = dialog.findChild(QTableView, "appearanceStyleTable")
    assert editor_table is not None
    editor_model = _table_model(editor_table)
    editor_model.setData(editor_model.index(0, 2), "#101820", Qt.ItemDataRole.EditRole)
    dialog.reset_editor_settings_to_defaults()
    assert editor_model.index(0, 2).data() == "#FFFFFF"

    dialog.category_list.setCurrentRow(3)
    dialog.appearance_item_list.setCurrentRow(1)
    dialog.show_formatted_preview_checkbox.setChecked(False)
    dialog.show_raw_recordings_checkbox.setChecked(False)
    dialog.show_diagnostics_checkbox.setChecked(False)
    dialog.diagnostics_show_diagnostics_tab_checkbox.setChecked(False)

    dialog.reset_workspace_tabs_settings_to_defaults()
    assert dialog.show_formatted_preview_checkbox.isChecked() is True
    assert dialog.show_raw_recordings_checkbox.isChecked() is False
    assert dialog.show_diagnostics_checkbox.isChecked() is False
    assert dialog.hidden_workspace_tabs_strip_collapsed_checkbox.isChecked() is True

    dialog.category_list.setCurrentRow(8)
    dialog.diagnostics_enabled_checkbox.setChecked(True)
    dialog.diagnostics_show_diagnostics_tab_checkbox.setChecked(False)

    dialog.reset_diagnostics_settings_to_defaults()
    assert dialog.diagnostics_enabled_checkbox.isChecked() is False
    assert dialog.show_diagnostics_checkbox.isChecked() is False
    assert dialog.diagnostics_show_diagnostics_tab_checkbox.isChecked() is False

    dialog.scripting_language_combo.setCurrentText("Custom")
    dialog.formatting_indent_spin.setValue(2)
    dialog.formatting_use_spaces_checkbox.setChecked(False)
    dialog.formatting_auto_indent_checkbox.setChecked(False)
    dialog.formatting_auto_format_checkbox.setChecked(True)

    dialog.reset_script_language_settings_to_defaults()
    assert dialog.scripting_language_combo.currentText() == "ActionShellScript"
    assert dialog.formatting_indent_spin.value() == 2
    assert dialog.formatting_use_spaces_checkbox.isChecked() is False
    assert dialog.formatting_auto_format_checkbox.isChecked() is True

    dialog.category_list.setCurrentRow(7)
    dialog.runtime_max_loop_iterations_spin.setValue(321)
    dialog.runtime_max_call_depth_spin.setValue(45)
    dialog.runtime_default_mouse_move_speed_spin.setValue(18)
    dialog.scripting_language_combo.setCurrentText("Custom")
    dialog.formatting_indent_spin.setValue(2)
    dialog.formatting_use_spaces_checkbox.setChecked(False)
    dialog.formatting_auto_format_checkbox.setChecked(True)

    dialog.reset_execution_settings_to_defaults()
    assert dialog.runtime_max_loop_iterations_spin.value() == 100_000
    assert dialog.runtime_max_call_depth_spin.value() == 250
    assert dialog.runtime_default_mouse_move_speed_spin.value() == 10
    assert dialog.scripting_language_combo.currentText() == "Custom"
    assert dialog.formatting_indent_spin.value() == 2
    assert dialog.formatting_use_spaces_checkbox.isChecked() is False
    assert dialog.formatting_auto_indent_checkbox.isChecked() is False
    assert dialog.formatting_auto_format_checkbox.isChecked() is True

    dialog.reset_formatting_settings_to_defaults()
    assert dialog.scripting_language_combo.currentText() == "Custom"
    assert dialog.formatting_indent_spin.value() == 4
    assert dialog.formatting_use_spaces_checkbox.isChecked() is True
    assert dialog.formatting_auto_indent_checkbox.isChecked() is True
    assert dialog.formatting_auto_format_checkbox.isChecked() is False


def test_preferences_dialog_formatting_reset_clears_dirty_state_for_formatting_only_changes() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.category_list.setCurrentRow(2)
    dialog.formatting_indent_spin.setValue(2)
    dialog.formatting_use_spaces_checkbox.setChecked(False)
    dialog.formatting_auto_indent_checkbox.setChecked(False)
    dialog.formatting_auto_format_checkbox.setChecked(True)

    assert dialog.is_dirty() is True
    assert dialog.windowTitle() == "Preferences *"

    dialog.reset_formatting_settings_to_defaults()

    assert dialog.formatting_indent_spin.value() == 4
    assert dialog.formatting_use_spaces_checkbox.isChecked() is True
    assert dialog.formatting_auto_indent_checkbox.isChecked() is True
    assert dialog.formatting_auto_format_checkbox.isChecked() is False
    assert dialog.is_dirty() is False
    assert dialog.windowTitle() == "Preferences"


def test_preferences_dialog_style_reset_restores_only_style_defaults() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.set_preferences(
        DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=True,
                last_workspace_path=r"C:\work\session.ass",
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
                        keyword="#123456",
                        string="#234567",
                        comment="#345678",
                        number="#456789",
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
            ),
        )
    )

    dialog.category_list.setCurrentRow(2)
    dialog.text_editor_item_list.setCurrentRow(2)
    style_model = _table_model(dialog.style_table)
    style_model.setData(style_model.index(0, 1), "#abcdef", Qt.ItemDataRole.EditRole)
    dialog.reset_style_settings_to_defaults()
    bundle = dialog.settings_bundle()

    assert bundle.application.restore_last_workspace is True
    assert bundle.application.last_workspace_path == r"C:\work\session.ass"
    assert bundle.theme.appearance.editor.background == "#101820"
    assert bundle.theme.appearance.syntax_highlighting == SyntaxHighlightTheme()
    assert bundle.theme.scripting.language == "Custom"
    assert bundle.theme.scripting.indent_width == 2
    assert bundle.theme.scripting.use_spaces is False
    assert bundle.theme.scripting.auto_format_on_save is True
    assert bundle.theme.font.size == 13
    assert bundle.theme.font.weight == 600
    assert bundle.theme.font.line_spacing_multiplier == 1.25
    assert dialog.is_dirty() is True


def test_preferences_dialog_title_shows_dirty_marker() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()

    assert dialog.windowTitle() == "Preferences"

    dialog.restore_workspace_checkbox.setChecked(True)

    assert dialog.is_dirty() is True
    assert dialog.windowTitle() == "Preferences *"


def test_preferences_dialog_clears_dirty_marker_when_restored_to_saved_state() -> None:
    _app()

    dialog = PreferencesDialog()
    dialog.show()

    dialog.restore_workspace_checkbox.setChecked(True)
    assert dialog.is_dirty() is True
    assert dialog.windowTitle() == "Preferences *"

    dialog.restore_workspace_checkbox.setChecked(False)

    assert dialog.is_dirty() is False
    assert dialog.windowTitle() == "Preferences"
