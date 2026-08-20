import os
from pathlib import Path
from types import SimpleNamespace
from typing import TypeVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QCloseEvent, QHideEvent, QIcon, QPixmap, QShowEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QSizePolicy, QLayout, QToolBar, QWidget  # noqa: E402

import apps.desktop.pixel_inspector_window as pixel_inspector_module  # noqa: E402
from apps.desktop.pixel_inspector_window import (  # noqa: E402
    NumericBase,
    PixelInspectorFrame,
    PixelInspectorSnapshot,
    PixelInspectorWindow,
    build_magnifier_pixmap,
    format_pixel_inspector_snapshot,
    render_magnifier_pixmap,
)

TWidget = TypeVar("TWidget")


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _layout_widget_at(layout: QLayout | None, index: int) -> QWidget:
    assert layout is not None
    item = layout.itemAt(index)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget


def _required_child(parent: QWidget, child_type: type[TWidget], name: str | None = None) -> TWidget:
    child = parent.findChild(child_type, name) if name is not None else parent.findChild(child_type)
    assert child is not None
    return cast(TWidget, child)


def test_pixel_inspector_window_renders_snapshot_and_copies_to_clipboard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()

    calls: list[int] = []
    snapshot = PixelInspectorSnapshot(
        pointer_x=12,
        pointer_y=34,
        screen_index=1,
        screen_count=3,
        screen_name="DISPLAY2",
        pixel_color=QColor(1, 2, 3, 255),
        window_handle=0x1234,
        window_title="Example Window",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: calls.append(1) or snapshot)
    initial_size = window.size()

    menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert menu_titles[:4] == ["File", "Magnifier", "Options", "Help"]
    zoom_actions = [action for action in window.zoom_menu.actions() if not action.isSeparator()]
    assert [action.text() for action in zoom_actions] == [
        "Zoom In",
        "Zoom Out",
        "Fit",
        "Presets",
        "Custom...",
    ]
    assert [action.text() for action in window.zoom_presets_menu.actions()] == [
        "2x",
        "4x",
        "6x",
        "8x",
        "10x",
        "12x",
        "14x",
        "16x",
    ]
    help_actions = [action for action in window.help_menu.actions()]
    assert [action.text() for action in help_actions if not action.isSeparator()] == [
        "Documentation",
        "About",
    ]
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == ["4x"]
    assert window.restore_defaults_action.text() == "Restore Defaults"
    assert window.copy_action.text() == "Copy"
    assert window.refresh_output_action.text() == "Refresh Output"
    assert window.refresh_output_action.icon().isNull() is False
    assert window.restore_defaults_action.icon().isNull() is False
    assert window.windowIcon().isNull() is False
    assert window.copy_action.icon().isNull() is False
    assert window.capture_action.icon().isNull() is False
    assert window.capture_action.text() == "Disable Capture"
    assert window.tooltip_coordinates_action.isChecked() is False
    assert window.tooltip_coordinates_action.text() == "Enable Pointer Coordinates"
    assert window.tooltip_coordinates_action.icon().isNull() is False
    assert window.tooltip_coordinates_menu_action.icon().isNull() is False
    assert window.coordinate_capture_action.isChecked() is False
    assert window.coordinate_capture_action.text() == "Enable Coordinate Capture"
    assert window.coordinate_capture_action.icon().isNull() is False
    assert window.auto_follow_coordinate_capture_action.isChecked() is True
    assert window.auto_follow_coordinate_capture_action.text() == "Disable Auto-follow Coordinate Capture"
    assert window.stay_on_top_action.icon().isNull() is False
    assert window.zoom_out_action.icon().isNull() is False
    assert window.zoom_in_action.icon().isNull() is False
    assert window.close_action.icon().isNull() is False
    assert window.documentation_action.icon().isNull() is False
    assert window.help_toolbar_spacer.objectName() == "helpToolbarSpacer"
    assert window.help_toolbar_spacer.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert window.windowModality() == Qt.WindowModality.NonModal
    assert window.capture_toolbar_button.defaultAction() is window.capture_action
    assert window.tooltip_coordinates_toolbar_button.defaultAction() is window.tooltip_coordinates_action
    assert window.coordinate_capture_toolbar_button.defaultAction() is window.coordinate_capture_action
    assert window.help_toolbar_button.defaultAction() is window.documentation_action
    capture_icon_live = window.capture_action.icon().cacheKey()

    assert window.capture_action.isChecked() is True
    assert window.stay_on_top_checkbox.isChecked() is True
    assert len(calls) == 1
    assert "live = sampling" in window.magnifier_legend_label.text()
    assert "frozen = locked" in window.magnifier_legend_label.text()
    assert "magnifier zoom level" in window.zoom_in_action.toolTip()
    assert "magnifier zoom level" in window.zoom_out_action.toolTip()
    assert "live sampling" in window.capture_action.toolTip()
    assert "user guide" in window.documentation_action.toolTip()
    assert "Pixel Inspector" in window.about_action.toolTip()
    options_menu = window.options_menu
    assert options_menu is not None
    separator_indices = [index for index, action in enumerate(options_menu.actions()) if action.isSeparator()]
    assert separator_indices == [1, 4, 7, 10]
    assert [action.text().replace("&", "") for action in options_menu.actions() if action.text()] == [
        "Display Base",
        "Disable Capture",
        "Enable Pointer Coordinates",
        "Enable Coordinate Capture",
        "Disable Auto-follow Coordinate Capture",
        "Stay on top",
        "Refresh Output",
        "Restore Defaults",
    ]
    assert window.zoom_slider.value() == 4
    assert window.zoom_value_label.text() == "4x"
    assert window.pixel_color_indicator.text() == "Selected Color: A=0xFF R=0x01 G=0x02 B=0x03"

    help_button = _required_child(window, type(window.help_toolbar_button), "helpToolbarButton")
    assert help_button.defaultAction() is window.documentation_action
    assert "padding: 0px" in help_button.styleSheet()
    assert "border: 0" in help_button.styleSheet()
    toolbar = help_button.parentWidget()
    assert toolbar is not None
    assert _layout_widget_at(toolbar.layout(), toolbar.layout().count() - 2) is window.help_toolbar_spacer
    assert _layout_widget_at(toolbar.layout(), toolbar.layout().count() - 1) is help_button

    opened_docs: list[Path] = []
    opened_anchors: list[str | None] = []
    opened_sections: list[str | None] = []

    class FakeHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            self.on_close = on_close
            self.opened_paths: list[Path] = []
            self.shown = 0
            self.raised = 0
            self.activated = 0
            self.minimized = False

        def open_document(
            self,
            path: Path,
            *,
            anchor_id: str | None = None,
            anchor_text: str | None = None,
        ) -> bool:
            self.opened_paths.append(path)
            opened_anchors.append(anchor_text)
            opened_docs.append(path)
            opened_sections.append(anchor_id)
            return True

        def open_at_section(
            self,
            path: Path,
            section_id: str,
            *,
            anchor_text: str | None = None,
        ) -> bool:
            return self.open_document(path, anchor_id=section_id, anchor_text=anchor_text)

        def show(self) -> None:
            self.shown += 1

        def showNormal(self) -> None:
            self.shown += 1

        def raise_(self) -> None:
            self.raised += 1

        def activateWindow(self) -> None:
            self.activated += 1

        def isMinimized(self) -> bool:
            return self.minimized

        def close(self) -> None:
            if self.on_close is not None:
                self.on_close()
                return
            return True

    monkeypatch.setattr(pixel_inspector_module, "ActionShellScriptHelpBrowser", FakeHelpBrowser)
    docs_path = tmp_path / "shared-pixel-inspector-guide.md"
    docs_path.write_text("# Pixel Inspector\n", encoding="utf-8")
    monkeypatch.setattr(pixel_inspector_module, "pixel_inspector_guide_path", lambda: docs_path)

    window.documentation_action.trigger()
    assert len(opened_docs) == 1
    expected_docs_path = docs_path.resolve()
    assert opened_docs[0].resolve() == expected_docs_path
    assert opened_anchors[0] == "Main Controls"
    assert opened_sections[0] == "main-controls"
    assert window._help_browser_window is not None
    assert window._help_browser_window.opened_paths[0].resolve() == expected_docs_path
    assert window._help_browser_window.shown == 1
    assert window._help_browser_window.raised == 1
    assert window._help_browser_window.activated == 1

    about_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "about",
        lambda parent, title, text: about_calls.append((title, text)),
    )
    window.about_action.trigger()
    assert about_calls
    assert about_calls[0][0] == "About Pixel Inspector"
    assert "Pixel Inspector" in about_calls[0][1]

    text = window.output_view.toPlainText()
    assert "Pointer: X=12 Y=34" in text
    assert "Monitor: 2 of 3 (DISPLAY2)" in text
    assert "ARGB: A=0xFF R=0x01 G=0x02 B=0x03" in text
    assert "Packed: 0xFF010203" in text
    assert "Window: HWND=0x1234 Title=Example Window" in text

    window.copy_to_clipboard()
    assert QApplication.clipboard().text() == text

    window.set_display_base(NumericBase.DECIMAL)
    text = window.output_view.toPlainText()
    assert "ARGB: A=255 R=1 G=2 B=3" in text
    assert "Packed: 4278256131" in text
    assert "Window: HWND=4660 Title=Example Window" in text
    assert window.pixel_color_indicator.text() == "Selected Color: A=255 R=1 G=2 B=3"

    window.capture_action.setChecked(False)
    window.refresh_snapshot()
    assert len(calls) == 1
    paused_text = window.output_view.toPlainText()
    assert "State: paused" in paused_text
    assert "Pointer: X=12 Y=34" in paused_text
    assert window.capture_action.text() == "Capture"
    capture_icon_paused = window.capture_action.icon().cacheKey()
    assert capture_icon_paused != capture_icon_live

    window.capture_action.setChecked(True)
    assert window.capture_action.text() == "Disable Capture"
    assert window.capture_action.icon().cacheKey() != capture_icon_paused

    window.zoom_slider.setValue(6)
    assert window.zoom_slider.value() == 6
    assert window.zoom_value_label.text() == "6x"
    assert len(calls) == 2
    assert window.magnifier_placeholder.pixmap() is not None
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == ["6x"]

    window.zoom_presets_menu.actions()[3].trigger()
    assert window.zoom_slider.value() == 8
    assert window.zoom_value_label.text() == "8x"
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == ["8x"]

    monkeypatch.setattr(window, "_fit_zoom_factor", lambda: 11)
    window.zoom_fit_action.trigger()
    assert window.zoom_slider.value() == 11
    assert window.zoom_value_label.text() == "11x"
    assert window.zoom_fit_action.isChecked() is True
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == []

    monkeypatch.setattr(window, "_prompt_custom_zoom", lambda: 9)
    window.zoom_custom_action.trigger()
    assert window.zoom_slider.value() == 9
    assert window.zoom_value_label.text() == "9x"
    assert window.zoom_custom_action.isChecked() is True
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == []

    window.resize(initial_size.width() + 80, initial_size.height() + 40)
    window.move(window.x() + 25, window.y() + 35)
    moved_position = window.pos()

    window.capture_action.setChecked(False)
    window.stay_on_top_action.setChecked(False)
    window.set_display_base(NumericBase.OCTAL)
    window.zoom_fit_action.trigger()
    window.restore_defaults_action.trigger()

    assert window.capture_action.isChecked() is True
    assert window.stay_on_top_action.isChecked() is True
    assert window.stay_on_top_checkbox.isChecked() is True
    assert window.pos() == moved_position
    assert window.size() == initial_size
    assert window.zoom_slider.value() == 4
    assert window.zoom_value_label.text() == "4x"
    assert window.zoom_fit_action.isChecked() is False
    assert [action.text() for action in window.zoom_presets_menu.actions() if action.isChecked()] == ["4x"]
    assert window.output_view.toPlainText().startswith("Pixel Inspector")
    assert "Base: Hexadecimal" in window.base_label.text()

    assert options_menu.actions()[9] is window.refresh_output_action


def test_collect_pixel_inspector_snapshot_passes_excluded_window_handles(monkeypatch) -> None:
    _app()

    captured: list[tuple[int, ...]] = []
    monkeypatch.setattr(pixel_inspector_module.QCursor, "pos", lambda: QPoint(1, 2))
    monkeypatch.setattr(pixel_inspector_module.QGuiApplication, "screens", lambda: [])
    monkeypatch.setattr(pixel_inspector_module.QGuiApplication, "screenAt", lambda _point: None)
    monkeypatch.setattr(pixel_inspector_module.QGuiApplication, "primaryScreen", lambda: None)
    monkeypatch.setattr(pixel_inspector_module, "_sample_pixel_color", lambda screen, point: None)
    monkeypatch.setattr(
        pixel_inspector_module,
        "_window_info_from_point",
        lambda point, *, excluded_window_hwnds=(): captured.append(excluded_window_hwnds) or (None, None),
    )

    snapshot = pixel_inspector_module.collect_pixel_inspector_snapshot(
        excluded_window_hwnds=(321,),
    )

    assert snapshot.window_handle is None
    assert snapshot.window_title is None
    assert captured == [(321,)]


def test_pixel_inspector_window_refresh_output_clears_mouse_click_notes_and_respects_capture_state(monkeypatch) -> None:
    _app()

    snapshots = [
        PixelInspectorSnapshot(
            pointer_x=12,
            pointer_y=34,
            screen_index=0,
            screen_count=1,
            screen_name="DISPLAY1",
            pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
            window_handle=0x56079E,
            window_title="Codex",
        ),
        PixelInspectorSnapshot(
            pointer_x=21,
            pointer_y=43,
            screen_index=0,
            screen_count=1,
            screen_name="DISPLAY1",
            pixel_color=QColor(0xAA, 0xBB, 0xCC, 0xFF),
            window_handle=0x56079E,
            window_title="Codex (updated)",
        ),
    ]
    calls: list[int] = []

    def snapshot_provider() -> PixelInspectorSnapshot:
        calls.append(1)
        return snapshots[min(len(calls) - 1, len(snapshots) - 1)]

    window = PixelInspectorWindow(snapshot_provider=snapshot_provider)
    window._record_mouse_click(button="left", point=QPoint(643, 399))
    assert "MouseClick(\"left\", 643, 399, 1)" in window.output_view.toPlainText()

    window.refresh_output_action.trigger()

    text = window.output_view.toPlainText()
    assert len(calls) == 2
    assert "Pointer: X=21 Y=43" in text
    assert "Window: HWND=0x56079E Title=Codex (updated)" in text
    assert "MouseClick(" not in text

    window._record_mouse_click(button="right", point=QPoint(700, 353))
    assert "MouseClick(\"right\", 700, 353, 1)" in window.output_view.toPlainText()

    window.capture_action.setChecked(False)
    paused_snapshot = window.output_view.toPlainText()
    window._record_mouse_click(button="left", point=QPoint(836, 386))
    assert "MouseClick(\"left\", 836, 386, 1)" in window.output_view.toPlainText()

    window.refresh_output_action.trigger()

    text = window.output_view.toPlainText()
    assert len(calls) == 2
    assert "MouseClick(" not in text
    assert "State: paused" in text
    assert "Pointer: X=21 Y=43" in text
    assert "Window: HWND=0x56079E Title=Codex (updated)" in text
    assert paused_snapshot.startswith("Pixel Inspector")


def test_pixel_inspector_window_tooltip_coordinates_toggle_shows_cursor_position(monkeypatch) -> None:
    _app()

    tooltip_calls: list[tuple[QPoint, str, object]] = []
    hide_calls: list[bool] = []

    monkeypatch.setattr(pixel_inspector_module.QCursor, "pos", lambda: QPoint(17, 29))
    monkeypatch.setattr(
        pixel_inspector_module.QToolTip,
        "showText",
        lambda pos, text, widget=None: tooltip_calls.append((pos, text, widget)),
    )
    monkeypatch.setattr(
        pixel_inspector_module.QToolTip,
        "hideText",
        lambda: hide_calls.append(True),
    )

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    window.tooltip_coordinates_action.setChecked(True)
    assert window.tooltip_coordinates_action.text() == "Disable Pointer Coordinates"
    assert tooltip_calls[-1][1] == "X:17, Y:29"
    assert tooltip_calls[-1][2] is window

    window.tooltip_coordinates_action.setChecked(False)
    assert window.tooltip_coordinates_action.text() == "Enable Pointer Coordinates"
    assert hide_calls


def test_pixel_inspector_window_coordinate_capture_appends_mouse_click_notes(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    target = object()
    monkeypatch.setattr(pixel_inspector_module.QApplication, "widgetAt", lambda point: target)
    window.coordinate_capture_action.setChecked(True)
    assert window.coordinate_capture_action.text() == "Disable Coordinate Capture"

    left_event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(643, 399)),
    )
    right_event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.RightButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(700, 353)),
    )

    window.eventFilter(target, left_event)
    window.eventFilter(window, left_event)
    window.eventFilter(target, right_event)

    text = window.output_view.toPlainText()
    assert "MouseClick(\"left\", 643, 399, 1)" in text
    assert "MouseClick(\"right\", 700, 353, 1)" in text
    assert text.splitlines()[-2:] == [
        'MouseClick("left", 643, 399, 1)',
        'MouseClick("right", 700, 353, 1)',
    ]

    window.coordinate_capture_action.setChecked(False)
    assert window.coordinate_capture_action.text() == "Enable Coordinate Capture"


def test_pixel_inspector_window_coordinate_capture_ignores_clicks_inside_itself(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    window.coordinate_capture_action.setChecked(True)
    monkeypatch.setattr(window, "frameGeometry", lambda: QRect(0, 0, 500, 500))

    inside_event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(250, 250)),
    )
    outside_event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(700, 700)),
    )

    window.eventFilter(window, inside_event)
    assert window.output_view.toPlainText().splitlines()[-1] == "Window: HWND=0x56079E Title=Codex"

    window.eventFilter(window, outside_event)
    assert window.output_view.toPlainText().splitlines()[-1] == 'MouseClick("left", 700, 700, 1)'


def test_pixel_inspector_window_coordinate_capture_starts_global_listener_and_records_desktop_clicks(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    started: list[object] = []
    stopped: list[object] = []

    class FakeListener:
        def __init__(self, *, on_click) -> None:
            self.on_click = on_click

        def start(self):
            started.append(self)
            return self

        def stop(self):
            stopped.append(self)

    monkeypatch.setattr(pixel_inspector_module.mouse, "Listener", FakeListener)

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    monkeypatch.setattr(window, "frameGeometry", lambda: QRect(0, 0, 500, 500))

    window.coordinate_capture_action.setChecked(True)
    assert started
    assert window._coordinate_capture_listener is started[0]

    window._on_global_mouse_click(700, 700, SimpleNamespace(name="left"), True)
    assert window.output_view.toPlainText().splitlines()[-1] == 'MouseClick("left", 700, 700, 1)'

    window._on_global_mouse_click(250, 250, SimpleNamespace(name="left"), True)
    assert window.output_view.toPlainText().splitlines()[-1] == 'MouseClick("left", 700, 700, 1)'

    window.coordinate_capture_action.setChecked(False)
    assert stopped == [started[0]]
    assert window._coordinate_capture_listener is None


def test_pixel_inspector_window_coordinate_capture_stops_listener_on_close(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    started: list[object] = []
    stopped: list[object] = []
    installs: list[object] = []
    removals: list[object] = []

    class FakeListener:
        def __init__(self, *, on_click) -> None:
            self.on_click = on_click

        def start(self):
            started.append(self)
            return self

        def stop(self):
            stopped.append(self)

    app = _app()
    monkeypatch.setattr(app, "installEventFilter", lambda obj: installs.append(obj))
    monkeypatch.setattr(app, "removeEventFilter", lambda obj: removals.append(obj))
    monkeypatch.setattr(pixel_inspector_module.mouse, "Listener", FakeListener)

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    monkeypatch.setattr(window, "frameGeometry", lambda: QRect(0, 0, 500, 500))
    window.coordinate_capture_action.setChecked(True)

    window.closeEvent(QCloseEvent())

    assert started
    assert stopped == [started[0]]
    assert removals == [window]
    assert window._coordinate_capture_listener is None
    assert window._coordinate_capture_enabled is False

    before = window.output_view.toPlainText()
    window._on_global_mouse_click(700, 700, SimpleNamespace(name="left"), True)
    assert window.output_view.toPlainText() == before


def test_pixel_inspector_window_coordinate_capture_shows_status_when_listener_start_fails(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    class FakeListener:
        def __init__(self, *, on_click) -> None:
            self.on_click = on_click

        def start(self):
            raise RuntimeError("listener unavailable")

    status_messages: list[tuple[str, int]] = []
    tooltip_messages: list[tuple[str, object]] = []

    monkeypatch.setattr(pixel_inspector_module.mouse, "Listener", FakeListener)
    monkeypatch.setattr(
        pixel_inspector_module.QToolTip,
        "showText",
        lambda point, message, widget=None, *args, **kwargs: tooltip_messages.append((message, widget)),
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    monkeypatch.setattr(
        window,
        "statusBar",
        lambda: SimpleNamespace(showMessage=lambda message, timeout: status_messages.append((message, timeout))),
    )

    window.coordinate_capture_action.setChecked(True)

    assert status_messages == [
        (
            "Coordinate Capture: desktop listener unavailable on this machine; local clicks only.",
            5000,
        )
    ]
    assert tooltip_messages == [
        (
            "Coordinate Capture: desktop listener unavailable on this machine; local clicks only.",
            window,
        )
    ]
    assert window._coordinate_capture_listener is None


def test_pixel_inspector_window_coordinate_capture_ignores_propagated_parent_delivery(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    window.coordinate_capture_action.setChecked(True)
    monkeypatch.setattr(window, "frameGeometry", lambda: QRect(0, 0, 1200, 900))
    monkeypatch.setattr(window, "_should_skip_coordinate_capture", lambda event: False)
    target = object()
    monkeypatch.setattr(pixel_inspector_module.QApplication, "widgetAt", lambda point: target)

    event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(951, 376)),
    )

    window.eventFilter(target, event)
    window.eventFilter(window, event)

    notes = [line for line in window.output_view.toPlainText().splitlines() if line.startswith("MouseClick(")]
    assert notes == ['MouseClick("left", 951, 376, 1)']


def test_pixel_inspector_window_coordinate_capture_keeps_single_note_across_child_parent_chain(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    window.coordinate_capture_action.setChecked(True)

    child_widget = SimpleNamespace(objectName=lambda: "childWidget")
    parent_widget = SimpleNamespace(objectName=lambda: "parentWidget")
    monkeypatch.setattr(window, "frameGeometry", lambda: QRect(0, 0, 1200, 900))
    monkeypatch.setattr(window, "_should_skip_coordinate_capture", lambda event: False)
    monkeypatch.setattr(pixel_inspector_module.QApplication, "widgetAt", lambda point: child_widget)

    press_event = SimpleNamespace(
        type=lambda: QEvent.Type.MouseButtonPress,
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: SimpleNamespace(toPoint=lambda: QPoint(951, 376)),
    )

    window.eventFilter(child_widget, press_event)
    window.eventFilter(parent_widget, press_event)

    notes = [line for line in window.output_view.toPlainText().splitlines() if line.startswith("MouseClick(")]
    assert notes == ['MouseClick("left", 951, 376, 1)']


def test_pixel_inspector_window_refresh_keeps_output_scroll_position(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    for index in range(60):
        window._record_mouse_click(
            button="left",
            point=QPoint(643 + index, 399 + index),
        )

    scrollbar = window.output_view.verticalScrollBar()
    scrollbar.setValue(max(0, scrollbar.maximum() // 2))
    middle_value = scrollbar.value()

    monkeypatch.setattr(
        window,
        "_snapshot_provider",
        lambda: PixelInspectorSnapshot(
            pointer_x=644,
            pointer_y=400,
            screen_index=0,
            screen_count=1,
            screen_name="DISPLAY1",
            pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
            window_handle=0x56079E,
            window_title="Codex",
        ),
    )

    window.refresh_snapshot(force=True)

    assert scrollbar.value() == middle_value


def test_pixel_inspector_window_coordinate_capture_event_filter_is_not_installed_twice(monkeypatch) -> None:
    _app()

    installs: list[object] = []
    removals: list[object] = []
    app = _app()
    monkeypatch.setattr(app, "installEventFilter", lambda obj: installs.append(obj))
    monkeypatch.setattr(app, "removeEventFilter", lambda obj: removals.append(obj))

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    window.coordinate_capture_action.setChecked(True)
    window.showEvent(QShowEvent())
    window.hideEvent(QHideEvent())
    window.coordinate_capture_action.setChecked(False)

    assert installs == [window]
    assert removals == [window]


def test_pixel_inspector_window_auto_follow_coordinate_capture_controls_tail_behavior(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=643,
        pointer_y=399,
        screen_index=0,
        screen_count=1,
        screen_name="DISPLAY1",
        pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
        window_handle=0x56079E,
        window_title="Codex",
    )

    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    for index in range(60):
        window._record_mouse_click(
            button="left",
            point=QPoint(643 + index, 399 + index),
        )

    scrollbar = window.output_view.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())

    monkeypatch.setattr(
        window,
        "_snapshot_provider",
        lambda: PixelInspectorSnapshot(
            pointer_x=644,
            pointer_y=400,
            screen_index=0,
            screen_count=1,
            screen_name="DISPLAY1",
            pixel_color=QColor(0xF3, 0xF3, 0xF3, 0xFF),
            window_handle=0x56079E,
            window_title="Codex",
        ),
    )

    window.refresh_snapshot(force=True)
    assert scrollbar.value() == scrollbar.maximum()

    window.auto_follow_coordinate_capture_action.setChecked(False)
    assert window.auto_follow_coordinate_capture_action.text() == "Enable Auto-follow Coordinate Capture"
    scrollbar.setValue(scrollbar.maximum())
    window.refresh_snapshot(force=True)
    assert scrollbar.value() == scrollbar.maximum()

    scrollbar.setValue(max(0, scrollbar.maximum() // 2))
    middle_value = scrollbar.value()
    window.refresh_snapshot(force=True)
    assert scrollbar.value() == middle_value

    window.auto_follow_coordinate_capture_action.setChecked(True)
    assert window.auto_follow_coordinate_capture_action.text() == "Disable Auto-follow Coordinate Capture"


def test_pixel_inspector_window_limits_resize_to_default_size() -> None:
    _app()

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    default_size = window.size()

    assert window.maximumSize() == default_size

    window.resize(default_size.width() + 120, default_size.height() + 80)

    assert window.size() == default_size


def test_pixel_inspector_window_uses_ph_magnifier_icons_for_zoom_actions(monkeypatch) -> None:
    _app()

    calls: list[tuple[str, object]] = []

    def fake_icon(name: str, *args, **kwargs):
        calls.append((name, kwargs.get("color")))
        return QIcon()

    monkeypatch.setattr(pixel_inspector_module.qta, "icon", fake_icon)

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    assert ("ph.magnifying-glass-plus", None) in calls
    assert ("ph.magnifying-glass-minus", None) in calls
    assert window.zoom_menu.actions()[0] is window.zoom_in_action
    assert window.zoom_menu.actions()[1] is window.zoom_out_action
    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    toolbar_actions = toolbar.actions()
    assert window.zoom_out_action in toolbar_actions
    assert window.zoom_in_action in toolbar_actions
    assert toolbar_actions.index(window.zoom_out_action) < toolbar_actions.index(window.zoom_in_action)
    capture_widget_action = next(
        action for action in toolbar_actions if toolbar.widgetForAction(action) is window.capture_toolbar_button
    )
    coordinates_widget_action = next(
        action for action in toolbar_actions if toolbar.widgetForAction(action) is window.tooltip_coordinates_toolbar_button
    )
    coordinate_capture_widget_action = next(
        action for action in toolbar_actions if toolbar.widgetForAction(action) is window.coordinate_capture_toolbar_button
    )
    assert toolbar_actions.index(capture_widget_action) < toolbar_actions.index(coordinates_widget_action)
    assert toolbar_actions.index(coordinates_widget_action) < toolbar_actions.index(coordinate_capture_widget_action)
    style_sheet = window.tooltip_coordinates_toolbar_button.styleSheet()
    assert "198, 40, 40" in style_sheet
    assert "46, 125, 50" in style_sheet
    coordinate_style_sheet = window.coordinate_capture_toolbar_button.styleSheet()
    assert "198, 40, 40" in coordinate_style_sheet
    assert "46, 125, 50" in coordinate_style_sheet


def test_pixel_inspector_window_uses_swapped_capture_icons(monkeypatch) -> None:
    _app()

    calls: list[str] = []

    def fake_icon(name: str, *args, **kwargs):
        calls.append(name)
        return QIcon()

    monkeypatch.setattr(pixel_inspector_module.qta, "icon", fake_icon)

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    assert "mdi6.magnify-remove-outline" in calls
    assert "mdi6.magnify-plus-cursor" not in calls

    window.capture_action.setChecked(False)

    assert "mdi6.magnify-plus-cursor" in calls
    assert calls.index("mdi6.magnify-remove-outline") < calls.index("mdi6.magnify-plus-cursor")

    window.capture_action.setChecked(True)

    assert calls[-1] == "mdi6.magnify-remove-outline"


def test_pixel_inspector_window_uses_pointer_coordinates_toolbar_icons(monkeypatch) -> None:
    _app()

    calls: list[tuple[str, object]] = []

    def fake_icon(name: str, *args, **kwargs):
        calls.append((name, kwargs.get("color")))
        return QIcon()

    monkeypatch.setattr(pixel_inspector_module.qta, "icon", fake_icon)

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    assert ("mdi6.numeric", None) in calls
    assert ("mdi6.cursor-default-click", ("#2e7d32", 255)) in calls
    assert ("mdi6.cursor-default-click-outline", ("#c62828", 255)) not in calls
    assert ("mdi6.button-pointer", ("#2e7d32", 255)) in calls
    assert ("mdi6.button-pointer", ("#c62828", 255)) not in calls
    assert ("mdi6.file-refresh-outline", None) in calls
    assert ("mdi6.format-align-top", None) in calls
    assert ("mdi6.cursor-default", ("#2e7d32", 255)) not in calls
    assert ("mdi6.cursor-default-outline", ("#c62828", 255)) not in calls
    assert window.tooltip_coordinates_toolbar_button.defaultAction() is window.tooltip_coordinates_action
    assert window.coordinate_capture_toolbar_button.defaultAction() is window.coordinate_capture_action

    window.tooltip_coordinates_action.setChecked(True)

    assert ("mdi6.cursor-default-click-outline", ("#c62828", 255)) in calls
    assert calls.index(("mdi6.cursor-default-click", ("#2e7d32", 255))) < calls.index(
        ("mdi6.cursor-default-click-outline", ("#c62828", 255))
    )

    window.tooltip_coordinates_action.setChecked(False)

    cursor_default_indices = [
        index for index, call in enumerate(calls) if call == ("mdi6.cursor-default-click", ("#2e7d32", 255))
    ]
    cursor_outline_indices = [
        index for index, call in enumerate(calls) if call == ("mdi6.cursor-default-click-outline", ("#c62828", 255))
    ]
    assert cursor_default_indices[-1] > cursor_outline_indices[-1]
    assert calls[-1] == ("mdi6.cursor-default-click", ("#2e7d32", 255))


def test_pixel_inspector_window_uses_coordinate_capture_toolbar_icons(monkeypatch) -> None:
    _app()

    calls: list[tuple[str, object]] = []

    def fake_icon(name: str, *args, **kwargs):
        calls.append((name, kwargs.get("color")))
        return QIcon()

    monkeypatch.setattr(pixel_inspector_module.qta, "icon", fake_icon)

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    assert ("mdi6.button-pointer", ("#2e7d32", 255)) in calls
    assert window.coordinate_capture_toolbar_button.defaultAction() is window.coordinate_capture_action

    window.coordinate_capture_action.setChecked(True)

    assert ("mdi6.button-pointer", ("#c62828", 255)) in calls
    assert calls.index(("mdi6.button-pointer", ("#2e7d32", 255))) < calls.index(
        ("mdi6.button-pointer", ("#c62828", 255))
    )

    window.coordinate_capture_action.setChecked(False)

    button_green_indices = [
        index for index, call in enumerate(calls) if call == ("mdi6.button-pointer", ("#2e7d32", 255))
    ]
    button_red_indices = [
        index for index, call in enumerate(calls) if call == ("mdi6.button-pointer", ("#c62828", 255))
    ]
    assert button_green_indices[-1] > button_red_indices[-1]
    assert calls[-1] == ("mdi6.button-pointer", ("#2e7d32", 255))


def test_pixel_inspector_window_uses_red_close_icon(monkeypatch) -> None:
    _app()

    calls: list[tuple[str, object]] = []

    def fake_icon(name: str, *args, **kwargs):
        calls.append((name, kwargs.get("color")))
        return QIcon()

    monkeypatch.setattr(pixel_inspector_module.qta, "icon", fake_icon)

    window = PixelInspectorWindow(
        snapshot_provider=lambda: PixelInspectorSnapshot(
            pointer_x=0,
            pointer_y=0,
            screen_index=None,
            screen_count=1,
            screen_name=None,
            pixel_color=None,
            window_handle=None,
            window_title=None,
        )
    )

    assert ("msc.close", ("#c62828", 255)) in calls


def test_restore_defaults_clears_cached_magnifier_frame_before_refresh(monkeypatch) -> None:
    _app()

    snapshot = PixelInspectorSnapshot(
        pointer_x=12,
        pointer_y=34,
        screen_index=None,
        screen_count=1,
        screen_name=None,
        pixel_color=None,
        window_handle=None,
        window_title=None,
    )
    window = PixelInspectorWindow(snapshot_provider=lambda: snapshot)
    window._current_magnifier_frame = PixelInspectorFrame(
        point=QPoint(1, 1),
        source_rect=QRect(0, 0, 2, 2),
        source=QPixmap(2, 2),
    )

    observed_frames: list[PixelInspectorFrame | None] = []
    original_refresh_snapshot = window.refresh_snapshot

    def _capture_refresh(*, force: bool = False) -> None:
        observed_frames.append(window._current_magnifier_frame)
        original_refresh_snapshot(force=force)

    monkeypatch.setattr(window, "refresh_snapshot", _capture_refresh)

    window.restore_defaults()

    assert observed_frames[0] is None
    assert window._current_magnifier_frame is not None


def test_pixel_inspector_snapshot_formatter_handles_missing_data() -> None:
    text = format_pixel_inspector_snapshot(None, base=NumericBase.HEX, capture_enabled=False)

    assert "Pixel Inspector" in text
    assert "no sample captured yet" in text
    assert "Window: unavailable" in text


def test_build_magnifier_pixmap_scales_a_screen_grab_to_a_square_preview() -> None:
    source = QPixmap(8, 8)
    source.fill(QColor(20, 40, 60))

    class FakeScreen:
        def geometry(self) -> QRect:
            return QRect(0, 0, 100, 100)

        def grabWindow(self, *_args):
            return source

    pixmap = build_magnifier_pixmap(FakeScreen(), QPoint(4, 4))

    assert pixmap is not None
    assert pixmap.size().width() == 100
    assert pixmap.size().height() == 100
    border_color = pixmap.toImage().pixelColor(1, 1)
    overlay_color = pixmap.toImage().pixelColor(70, 6)
    sample_color = pixmap.toImage().pixelColor(90, 40)
    swatch_color = pixmap.toImage().pixelColor(75, 76)
    assert border_color != QColor(20, 40, 60)
    assert overlay_color == QColor(20, 40, 60)
    assert sample_color == QColor(20, 40, 60)
    assert swatch_color == QColor(20, 40, 60)


def test_render_magnifier_pixmap_places_crosshair_at_sampled_point() -> None:
    source = QPixmap(5, 5)
    source.fill(QColor(120, 120, 120))

    frame = PixelInspectorFrame(
        point=QPoint(12, 23),
        source_rect=QRect(10, 20, 5, 5),
        source=source,
    )

    pixmap = render_magnifier_pixmap(frame, zoom_factor=8)
    assert pixmap is not None

    image = pixmap.toImage()
    assert image.pixelColor(50, 74).red() > image.pixelColor(50, 74).green()
    assert image.pixelColor(50, 74).red() > image.pixelColor(50, 74).blue()
