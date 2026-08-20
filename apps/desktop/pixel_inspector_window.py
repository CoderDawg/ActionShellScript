"""A compact window for inspecting the pointer position and nearby UI state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, QSignalBlocker
from PySide6.QtCore import Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QMessageBox,
    QStyle,
    QSlider,
    QToolBar,
    QToolButton,
    QSpinBox,
    QToolTip,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from apps.desktop.documentation_messages import pixel_inspector_guide_path
from apps.desktop.help_browser import ActionShellScriptHelpBrowser
from infrastructure.input.window_exclusion import normalize_window_handles, window_info_from_point
from pynput import mouse


class NumericBase(StrEnum):
    HEX = "hex"
    DECIMAL = "decimal"
    OCTAL = "octal"


@dataclass(slots=True)
class PixelInspectorSnapshot:
    pointer_x: int
    pointer_y: int
    screen_index: int | None
    screen_count: int
    screen_name: str | None
    pixel_color: QColor | None
    window_handle: int | None
    window_title: str | None


@dataclass(slots=True)
class PixelInspectorFrame:
    point: QPoint
    source_rect: QRect | None
    source: QPixmap | None


def format_numeric(value: int, base: NumericBase, *, width: int | None = None) -> str:
    if base == NumericBase.DECIMAL:
        return str(value)
    if base == NumericBase.OCTAL:
        return f"0o{value:o}"
    if width is None:
        return f"0x{value:X}"
    return f"0x{value:0{width}X}"


def format_component(value: int, base: NumericBase) -> str:
    if base == NumericBase.HEX:
        return format_numeric(value, base, width=2)
    if base == NumericBase.OCTAL:
        return format_numeric(value, base, width=3)
    return format_numeric(value, base)


def format_color_summary(color: QColor | None, base: NumericBase) -> list[str]:
    if color is None or not color.isValid():
        return ["Pixel: unavailable"]

    red, green, blue, alpha = color.red(), color.green(), color.blue(), color.alpha()
    packed_argb = (alpha << 24) | (red << 16) | (green << 8) | blue
    return [
        "Pixel:",
        f"  ARGB: A={format_component(alpha, base)} R={format_component(red, base)} G={format_component(green, base)} B={format_component(blue, base)}",
        f"  Packed: {format_numeric(packed_argb, base, width=8 if base == NumericBase.HEX else None)}",
        f"  Hex: #{red:02X}{green:02X}{blue:02X}",
    ]


def format_color_indicator(color: QColor | None, base: NumericBase) -> str:
    if color is None or not color.isValid():
        return "Selected Color: unavailable"
    return (
        "Selected Color: "
        f"A={format_component(color.alpha(), base)} "
        f"R={format_component(color.red(), base)} "
        f"G={format_component(color.green(), base)} "
        f"B={format_component(color.blue(), base)}"
    )


def format_pixel_inspector_snapshot(
    snapshot: PixelInspectorSnapshot | None,
    *,
    base: NumericBase,
    capture_enabled: bool,
    extra_lines: list[str] | None = None,
) -> str:
    if snapshot is None:
        return "\n".join(
            [
                "Pixel Inspector",
                "State: no sample captured yet",
                "Pointer: unavailable",
                "Monitor: unavailable",
                "Pixel: unavailable",
                "Window: unavailable",
            ]
        )

    monitor_text = "Monitor: unavailable"
    if snapshot.screen_index is not None:
        monitor_parts = [
            f"Monitor: {snapshot.screen_index + 1} of {snapshot.screen_count}",
        ]
        if snapshot.screen_name:
            monitor_parts.append(f"({snapshot.screen_name})")
        monitor_text = " ".join(monitor_parts)

    window_handle_text = "Window: unavailable"
    if snapshot.window_handle is not None or snapshot.window_title:
        handle_text = (
            format_numeric(snapshot.window_handle, base)
            if snapshot.window_handle is not None
            else "<unknown>"
        )
        title_text = snapshot.window_title if snapshot.window_title else "<untitled>"
        window_handle_text = f"Window: HWND={handle_text} Title={title_text}"

    lines = [
        "Pixel Inspector",
        f"State: {'live' if capture_enabled else 'paused'}",
        f"Pointer: X={snapshot.pointer_x} Y={snapshot.pointer_y}",
        monitor_text,
        *format_color_summary(snapshot.pixel_color, base),
        window_handle_text,
    ]
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def _sample_pixel_color(screen, point: QPoint) -> QColor | None:
    if screen is None:
        return None
    try:
        image = screen.grabWindow(0, point.x(), point.y(), 1, 1).toImage()
        if image.isNull():
            return None
        return image.pixelColor(0, 0)
    except Exception:
        return None


def capture_magnifier_frame(screen, point: QPoint, *, zoom_factor: int = 4) -> PixelInspectorFrame:
    if screen is None:
        return PixelInspectorFrame(point=QPoint(point), source_rect=None, source=None)

    try:
        zoom_factor = max(1, int(zoom_factor))
        output_size = 100
        source_size = max(1, round(output_size / zoom_factor))
        geometry = screen.geometry()
        left = max(point.x() - source_size // 2, geometry.left())
        top = max(point.y() - source_size // 2, geometry.top())
        right = min(left + source_size - 1, geometry.right())
        bottom = min(top + source_size - 1, geometry.bottom())
        width = max(1, right - left + 1)
        height = max(1, bottom - top + 1)
        source = screen.grabWindow(0, left, top, width, height)
        if source.isNull():
            return PixelInspectorFrame(
                point=QPoint(point),
                source_rect=QRect(left, top, width, height),
                source=None,
            )
        return PixelInspectorFrame(
            point=QPoint(point),
            source_rect=QRect(left, top, width, height),
            source=source,
        )
    except Exception:
        return PixelInspectorFrame(point=QPoint(point), source_rect=None, source=None)


def render_magnifier_pixmap(
    frame: PixelInspectorFrame | None,
    *,
    zoom_factor: int = 4,
    output_size: int = 100,
) -> QPixmap | None:
    if frame is None or frame.source is None:
        return None

    zoom_factor = max(1, int(zoom_factor))
    source_width = frame.source.width()
    source_height = frame.source.height()
    if source_width <= 0 or source_height <= 0:
        return None

    try:
        pixmap = frame.source.scaled(
            output_size,
            output_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            source_rect = frame.source_rect
            if source_rect is not None and source_rect.width() > 0 and source_rect.height() > 0:
                point_x = frame.point.x() - source_rect.left()
                point_y = frame.point.y() - source_rect.top()
            else:
                point_x = source_width // 2
                point_y = source_height // 2

            center_x = round(point_x * (output_size - 1) / max(1, source_width - 1))
            center_y = round(point_y * (output_size - 1) / max(1, source_height - 1))
            center_x = max(0, min(output_size - 1, center_x))
            center_y = max(0, min(output_size - 1, center_y))

            # Red crosshair lines
            cross_pen = QPen(QColor(255, 64, 64, 220))
            cross_pen.setWidth(1)
            painter.setPen(cross_pen)
            painter.drawLine(center_x, 0, center_x, output_size - 1)
            painter.drawLine(0, center_y, output_size - 1, center_y)

            frame_pen = QPen(QColor(255, 255, 255, 200))
            frame_pen.setWidth(2)
            painter.setPen(frame_pen)
            painter.drawRect(1, 1, output_size - 3, output_size - 3)

            overlay_font = QFont()
            overlay_font.setPointSize(6)
            painter.setFont(overlay_font)
            painter.setPen(QColor(12, 12, 12, 250))
            painter.drawText(
                QRect(4, 4, 44, 10),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"X = {frame.point.x()}",
            )
            painter.drawText(
                QRect(4, 15, 44, 10),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"Y = {frame.point.y()}",
            )

            image = frame.source.toImage()
            pixel_center = image.pixelColor(
                max(0, min(image.width() - 1, point_x)),
                max(0, min(image.height() - 1, point_y)),
            )
            # The small "reticle" marker on top of the crosshair intersection
            highlight_pen = QPen(QColor(255, 255, 255, 230))
            highlight_pen.setWidth(2)
            painter.setPen(highlight_pen)
            painter.drawEllipse(center_x - 4, center_y - 4, 8, 8)
            painter.fillRect(center_x - 1, center_y - 1, 3, 3, QColor(255, 255, 255, 230))

            swatch_rect = QRect(output_size - 30, output_size - 28, 22, 18)
            painter.fillRect(swatch_rect, pixel_center)
            painter.setPen(QColor(0, 0, 0, 220))
            painter.drawRect(swatch_rect)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(
                QRect(6, output_size - 22, output_size - 40, 16),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"Pixel #{pixel_center.red():02X}{pixel_center.green():02X}{pixel_center.blue():02X}",
            )
            painter.drawText(
                QRect(output_size - 30, output_size - 44, 24, 14),
                Qt.AlignmentFlag.AlignCenter,
                "SW",
            )
        finally:
            painter.end()
        return pixmap
    except Exception:
        return None


def build_magnifier_pixmap(
    screen,
    point: QPoint,
    *,
    zoom_factor: int = 4,
    output_size: int = 100,
) -> QPixmap | None:
    frame = capture_magnifier_frame(screen, point, zoom_factor=zoom_factor)
    return render_magnifier_pixmap(frame, zoom_factor=zoom_factor, output_size=output_size)


def _window_info_from_point(
    point: QPoint,
    *,
    excluded_window_hwnds: tuple[int, ...] = (),
) -> tuple[int | None, str | None]:
    try:
        return window_info_from_point(
            point,
            excluded_window_hwnds=excluded_window_hwnds,
        )
    except Exception:
        return None, None


def collect_pixel_inspector_snapshot(
    *,
    excluded_window_hwnds: tuple[int, ...] = (),
) -> PixelInspectorSnapshot:
    point = QCursor.pos()
    screens = QGuiApplication.screens()
    screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
    screen_index = None
    screen_name = None
    if screen is not None:
        try:
            screen_index = screens.index(screen)
        except ValueError:
            screen_index = None
        screen_name = screen.name() or None

    pixel_color = _sample_pixel_color(screen, point)
    window_handle, window_title = _window_info_from_point(
        point,
        excluded_window_hwnds=excluded_window_hwnds,
    )
    return PixelInspectorSnapshot(
        pointer_x=point.x(),
        pointer_y=point.y(),
        screen_index=screen_index,
        screen_count=len(screens),
        screen_name=screen_name,
        pixel_color=pixel_color,
        window_handle=window_handle,
        window_title=window_title,
    )


class PixelInspectorWindow(QMainWindow):
    coordinate_capture_requested = Signal(str, int, int)

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        snapshot_provider: Callable[[], PixelInspectorSnapshot] | None = None,
    ) -> None:
        super().__init__(parent)
        self._snapshot_provider = snapshot_provider or (
            lambda: collect_pixel_inspector_snapshot(
                excluded_window_hwnds=self._excluded_window_hwnds(),
            )
        )
        self._current_snapshot: PixelInspectorSnapshot | None = None
        self._current_magnifier_frame: PixelInspectorFrame | None = None
        self._display_base = NumericBase.HEX
        self._zoom_factor = 4
        self._zoom_mode = "manual"
        self._zoom_presets = (2, 4, 6, 8, 10, 12, 14, 16)
        self._help_browser_window: ActionShellScriptHelpBrowser | None = None
        self._mouse_click_notes: list[str] = []
        self._auto_follow_coordinate_capture = True
        self._coordinate_capture_filter_installed = False
        self._coordinate_capture_enabled = False
        self._coordinate_capture_listener = None
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.refresh_snapshot)
        self._tooltip_coordinates_timer = QTimer(self)
        self._tooltip_coordinates_timer.setInterval(100)
        self._tooltip_coordinates_timer.timeout.connect(self._update_tooltip_coordinates)
        self.coordinate_capture_requested.connect(self._record_coordinate_capture_note)

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Pixel Inspector")
        try:
            self.setWindowIcon(qta.icon("msc.inspect"))
        except Exception:
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.resize(460, 320)
        self.setMinimumSize(400, 280)
        self._default_window_size = QSize(self.size())
        self.setMaximumSize(self._default_window_size)

        self._build_actions()
        self._build_ui()

        self._update_zoom_state()
        self.refresh_snapshot(force=True)

    def _icon_or_fallback(
        self,
        icon_name: str,
        fallback: QStyle.StandardPixmap,
        *,
        color: QColor | tuple[str, int] | str | None = None,
    ) -> QIcon:
        try:
            if color is None:
                return qta.icon(icon_name)
            return qta.icon(icon_name, color=color)
        except Exception:
            return self.style().standardIcon(fallback)

    def _update_capture_action_icon(self) -> None:
        if self.capture_action.isChecked():
            icon = self._icon_or_fallback(
                "mdi6.magnify-remove-outline",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
                color=("#c62828", 255),
            )
        else:
            icon = self._icon_or_fallback(
                "mdi6.magnify-plus-cursor",
                QStyle.StandardPixmap.SP_DialogCancelButton,
                color=("#2e7d32", 255),
            )
        self.capture_action.setIcon(icon)

    def _update_tooltip_coordinates_icons(self) -> None:
        if self.tooltip_coordinates_action.isChecked():
            icon_name = "mdi6.cursor-default-click-outline"
            fallback = QStyle.StandardPixmap.SP_DialogApplyButton
            color = ("#c62828", 255)
        else:
            icon_name = "mdi6.cursor-default-click"
            fallback = QStyle.StandardPixmap.SP_DialogResetButton
            color = ("#2e7d32", 255)

        icon = self._icon_or_fallback(icon_name, fallback, color=color)
        self.tooltip_coordinates_action.setIcon(icon)
        if hasattr(self, "tooltip_coordinates_menu_action"):
            self.tooltip_coordinates_menu_action.setIcon(icon)

    def _update_coordinate_capture_icon(self) -> None:
        if self.coordinate_capture_action.isChecked():
            icon = self._icon_or_fallback(
                "mdi6.button-pointer",
                QStyle.StandardPixmap.SP_DialogApplyButton,
                color=("#c62828", 255),
            )
        else:
            icon = self._icon_or_fallback(
                "mdi6.button-pointer",
                QStyle.StandardPixmap.SP_DialogResetButton,
                color=("#2e7d32", 255),
            )
        self.coordinate_capture_action.setIcon(icon)

    def _build_actions(self) -> None:
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_to_clipboard)
        self.copy_action.setIcon(self._icon_or_fallback("msc.clippy", QStyle.StandardPixmap.SP_DialogSaveButton))

        self.capture_action = QAction("Capture", self)
        self.capture_action.setCheckable(True)
        self.capture_action.setChecked(True)
        self.capture_action.toggled.connect(self._on_capture_toggled)
        self.capture_action.setToolTip("Toggle live sampling. When off, the current view stays frozen.")
        self.capture_action.setStatusTip(self.capture_action.toolTip())
        self.capture_action.setText("Disable Capture")
        self._update_capture_action_icon()

        self.tooltip_coordinates_action = QAction("Enable Pointer Coordinates", self)
        self.tooltip_coordinates_action.setCheckable(True)
        self.tooltip_coordinates_action.setChecked(False)
        self.tooltip_coordinates_action.toggled.connect(self._on_tooltip_coordinates_toggled)
        self.tooltip_coordinates_action.setToolTip(
            "Show the cursor coordinates in a tooltip beside the pointer."
        )
        self.tooltip_coordinates_action.setStatusTip(self.tooltip_coordinates_action.toolTip())
        self._update_tooltip_coordinates_icons()

        self.tooltip_coordinates_menu_action = QAction("Enable Pointer Coordinates", self)
        self.tooltip_coordinates_menu_action.setCheckable(True)
        self.tooltip_coordinates_menu_action.setChecked(False)
        self.tooltip_coordinates_menu_action.toggled.connect(self._on_tooltip_coordinates_toggled)
        self.tooltip_coordinates_menu_action.setToolTip(
            "Show the cursor coordinates in a tooltip beside the pointer."
        )
        self.tooltip_coordinates_menu_action.setStatusTip(self.tooltip_coordinates_menu_action.toolTip())
        self.tooltip_coordinates_menu_action.setText("Enable Pointer Coordinates")
        self._update_tooltip_coordinates_icons()

        self.coordinate_capture_action = QAction("Enable Coordinate Capture", self)
        self.coordinate_capture_action.setCheckable(True)
        self.coordinate_capture_action.setChecked(False)
        self.coordinate_capture_action.toggled.connect(self._on_coordinate_capture_toggled)
        self.coordinate_capture_action.setToolTip(
            "Record mouse clicks as coordinate notes in the output pane."
        )
        self.coordinate_capture_action.setStatusTip(self.coordinate_capture_action.toolTip())
        self.coordinate_capture_action.setText("Enable Coordinate Capture")
        self._update_coordinate_capture_icon()

        self.auto_follow_coordinate_capture_action = QAction("Auto-follow Coordinate Capture", self)
        self.auto_follow_coordinate_capture_action.setCheckable(True)
        self.auto_follow_coordinate_capture_action.setChecked(True)
        self.auto_follow_coordinate_capture_action.toggled.connect(
            self._on_auto_follow_coordinate_capture_toggled
        )
        self.auto_follow_coordinate_capture_action.setToolTip(
            "Keep the output scrolled to the newest coordinate notes when you are already at the bottom."
        )
        self.auto_follow_coordinate_capture_action.setStatusTip(
            self.auto_follow_coordinate_capture_action.toolTip()
        )
        self.auto_follow_coordinate_capture_action.setText("Disable Auto-follow Coordinate Capture")

        self.refresh_output_action = QAction("Refresh Output", self)
        self.refresh_output_action.triggered.connect(self.refresh_output)
        self.refresh_output_action.setToolTip(
            "Clear click notes and redraw the current Pixel Inspector output."
        )
        self.refresh_output_action.setStatusTip(self.refresh_output_action.toolTip())
        self.refresh_output_action.setIcon(
            self._icon_or_fallback("mdi6.file-refresh-outline", QStyle.StandardPixmap.SP_BrowserReload)
        )

        self.stay_on_top_action = QAction("Stay on top", self)
        self.stay_on_top_action.setCheckable(True)
        self.stay_on_top_action.setChecked(True)
        self.stay_on_top_action.toggled.connect(self._apply_stay_on_top)
        self.stay_on_top_action.setIcon(
            self._icon_or_fallback("mdi6.format-align-top", QStyle.StandardPixmap.SP_TitleBarMaxButton)
        )

        self.restore_defaults_action = QAction("Restore Defaults", self)
        self.restore_defaults_action.triggered.connect(self.restore_defaults)
        self.restore_defaults_action.setToolTip("Restore the Pixel Inspector to its default settings.")
        self.restore_defaults_action.setStatusTip(self.restore_defaults_action.toolTip())
        self.restore_defaults_action.setIcon(
            self._icon_or_fallback("msc.clear-all", QStyle.StandardPixmap.SP_BrowserReload)
        )

        self.close_action = QAction("Close", self)
        self.close_action.setShortcut(QKeySequence.Close)
        self.close_action.triggered.connect(self.close)
        self.close_action.setIcon(
            self._icon_or_fallback(
                "msc.close",
                QStyle.StandardPixmap.SP_DialogCloseButton,
                color=("#c62828", 255),
            )
        )

        self.documentation_action = QAction("Documentation", self)
        self.documentation_action.triggered.connect(self.open_documentation)
        self.documentation_action.setToolTip("Open the Pixel Inspector user guide.")
        self.documentation_action.setStatusTip(self.documentation_action.toolTip())
        self.documentation_action.setIcon(
            self._icon_or_fallback(
                "msc.question",
                QStyle.StandardPixmap.SP_MessageBoxQuestion,
            )
        )

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.open_about)
        self.about_action.setToolTip("Show information about Pixel Inspector.")
        self.about_action.setStatusTip(self.about_action.toolTip())

        self.display_base_group = QActionGroup(self)
        self.display_base_group.setExclusive(True)
        self.hex_base_action = QAction("Hexadecimal", self)
        self.hex_base_action.setCheckable(True)
        self.hex_base_action.setChecked(True)
        self.hex_base_action.toggled.connect(
            lambda checked: checked and self.set_display_base(NumericBase.HEX)
        )
        self.dec_base_action = QAction("Decimal", self)
        self.dec_base_action.setCheckable(True)
        self.dec_base_action.toggled.connect(
            lambda checked: checked and self.set_display_base(NumericBase.DECIMAL)
        )
        self.oct_base_action = QAction("Octal", self)
        self.oct_base_action.setCheckable(True)
        self.oct_base_action.toggled.connect(
            lambda checked: checked and self.set_display_base(NumericBase.OCTAL)
        )
        for action in (self.hex_base_action, self.dec_base_action, self.oct_base_action):
            self.display_base_group.addAction(action)

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setToolTip("Increase the magnifier zoom level.")
        self.zoom_in_action.setStatusTip(self.zoom_in_action.toolTip())
        self.zoom_in_action.setIcon(
            self._icon_or_fallback(
                "ph.magnifying-glass-plus",
                QStyle.StandardPixmap.SP_ArrowUp,
            )
        )

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setToolTip("Decrease the magnifier zoom level.")
        self.zoom_out_action.setStatusTip(self.zoom_out_action.toolTip())
        self.zoom_out_action.setIcon(
            self._icon_or_fallback(
                "ph.magnifying-glass-minus",
                QStyle.StandardPixmap.SP_ArrowDown,
            )
        )

        self.zoom_fit_action = QAction("Fit", self)
        self.zoom_fit_action.setCheckable(True)
        self.zoom_fit_action.triggered.connect(self.fit_zoom)
        self.zoom_fit_action.setToolTip("Auto-fit the magnifier to the available screen space.")
        self.zoom_fit_action.setStatusTip(self.zoom_fit_action.toolTip())

        self.zoom_preset_actions: list[QAction] = []
        self.zoom_preset_group = QActionGroup(self)
        self.zoom_preset_group.setExclusive(True)
        for preset in self._zoom_presets:
            action = QAction(f"{preset}x", self)
            action.setCheckable(True)
            action.setData(preset)
            action.toggled.connect(
                lambda checked, value=preset: checked and self.set_zoom_factor(value)
            )
            self.zoom_preset_group.addAction(action)
            self.zoom_preset_actions.append(action)

        self.zoom_custom_action = QAction("Custom...", self)
        self.zoom_custom_action.setCheckable(True)
        self.zoom_custom_action.triggered.connect(self.specify_custom_zoom)
        self.zoom_custom_action.setToolTip("Enter an exact zoom value.")
        self.zoom_custom_action.setStatusTip(self.zoom_custom_action.toolTip())

    def _build_ui(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.copy_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_action)

        self.zoom_menu = self.menuBar().addMenu("&Magnifier")
        self.zoom_menu.addAction(self.zoom_in_action)
        self.zoom_menu.addAction(self.zoom_out_action)
        self.zoom_menu.addSeparator()
        self.zoom_menu.addAction(self.zoom_fit_action)
        self.zoom_menu.addSeparator()
        self.zoom_presets_menu = self.zoom_menu.addMenu("Presets")
        for action in self.zoom_preset_actions:
            self.zoom_presets_menu.addAction(action)
        self.zoom_menu.addSeparator()
        self.zoom_menu.addAction(self.zoom_custom_action)

        options_menu = self.menuBar().addMenu("&Options")
        self.options_menu = options_menu
        base_menu = options_menu.addMenu("Display &Base")
        base_menu.setIcon(self._icon_or_fallback("mdi6.numeric", QStyle.StandardPixmap.SP_DialogResetButton))
        options_menu.addSeparator()
        options_menu.addAction(self.capture_action)
        options_menu.addAction(self.tooltip_coordinates_menu_action)
        options_menu.addSeparator()
        options_menu.addAction(self.coordinate_capture_action)
        options_menu.addAction(self.auto_follow_coordinate_capture_action)
        options_menu.addSeparator()
        options_menu.addAction(self.stay_on_top_action)
        options_menu.addAction(self.refresh_output_action)
        options_menu.addSeparator()
        options_menu.addAction(self.restore_defaults_action)
        base_menu.addAction(self.hex_base_action)
        base_menu.addAction(self.dec_base_action)
        base_menu.addAction(self.oct_base_action)

        self.help_menu = self.menuBar().addMenu("&Help")
        self.help_menu.addAction(self.documentation_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_action)

        toolbar = QToolBar("Pixel Inspector", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.addAction(self.copy_action)
        self.capture_toolbar_button = self._build_capture_toolbar_button()
        toolbar.addWidget(self.capture_toolbar_button)
        self.tooltip_coordinates_toolbar_button = self._build_tooltip_coordinates_toolbar_button()
        toolbar.addWidget(self.tooltip_coordinates_toolbar_button)
        self.coordinate_capture_toolbar_button = self._build_coordinate_capture_toolbar_button()
        toolbar.addWidget(self.coordinate_capture_toolbar_button)
        toolbar.addSeparator()
        toolbar.addAction(self.zoom_out_action)
        toolbar.addAction(self.zoom_in_action)
        toolbar.addSeparator()
        toolbar.addAction(self.close_action)
        self.help_toolbar_spacer = self._build_toolbar_right_spacer()
        toolbar.addWidget(self.help_toolbar_spacer)
        self.help_toolbar_button = self._build_help_toolbar_button()
        toolbar.addWidget(self.help_toolbar_button)
        self.addToolBar(toolbar)

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(3, 3, 3, 3)
        root_layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)
        self.stay_on_top_checkbox = QCheckBox("Stay on top", central)
        self.stay_on_top_checkbox.setChecked(True)
        self.stay_on_top_checkbox.toggled.connect(self._apply_stay_on_top)
        self.stay_on_top_action.toggled.connect(self.stay_on_top_checkbox.setChecked)
        self.stay_on_top_checkbox.toggled.connect(self.stay_on_top_action.setChecked)
        self.stay_on_top_checkbox.setToolTip(
            "Keep the probe above other windows while inspecting the screen."
        )
        top_row.addWidget(self.stay_on_top_checkbox)
        top_row.addStretch(1)
        base_label = QLabel("Base: Hexadecimal", central)
        base_label.setObjectName("pointerProbeBaseLabel")
        self.base_label = base_label
        top_row.addWidget(base_label)
        zoom_label = QLabel("Zoom:", central)
        self.zoom_label = zoom_label
        top_row.addWidget(zoom_label)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal, central)
        self.zoom_slider.setRange(2, 16)
        self.zoom_slider.setValue(self._zoom_factor)
        self.zoom_slider.setFixedWidth(104)
        self.zoom_slider.setSingleStep(1)
        self.zoom_slider.setPageStep(2)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self.zoom_slider.setToolTip("Set the magnifier zoom level.")
        top_row.addWidget(self.zoom_slider)
        self.zoom_value_label = QLabel(f"{self._zoom_factor}x", central)
        self.zoom_value_label.setMinimumWidth(24)
        self.zoom_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_value_label.setToolTip(self.zoom_slider.toolTip())
        top_row.addWidget(self.zoom_value_label)
        root_layout.addLayout(top_row)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(3)
        legend = QLabel(
            "Legend: live = sampling, frozen = locked. Zoom adjusts the 100x100 view.",
            central,
        )
        legend.setWordWrap(True)
        legend.setStyleSheet("QLabel { color: #666666; font-size: 10px; }")
        self.magnifier_legend_label = legend
        legend_row.addWidget(legend)
        root_layout.addLayout(legend_row)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(4)

        magnifier_column = QVBoxLayout()
        magnifier_column.setContentsMargins(0, 0, 0, 0)
        magnifier_column.setSpacing(4)

        self.magnifier_placeholder = QLabel("100x100\nMagnifier", central)
        self.magnifier_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.magnifier_placeholder.setFixedSize(100, 100)
        self.magnifier_placeholder.setScaledContents(True)
        self.magnifier_placeholder.setStyleSheet(
            "QLabel { border: 1px solid #8c8c8c; background: #f6f6f6; color: #666666; }"
        )
        magnifier_column.addWidget(self.magnifier_placeholder, 0, Qt.AlignmentFlag.AlignTop)

        self.pixel_color_indicator = QLabel("Selected Color: unavailable", central)
        self.pixel_color_indicator.setFixedSize(100, 26)
        self.pixel_color_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pixel_color_indicator.setWordWrap(True)
        self.pixel_color_indicator.setStyleSheet(
            "QLabel { border: 1px solid #8c8c8c; background: rgba(255, 255, 255, 180); color: #444444; font-size: 9px; }"
        )
        magnifier_column.addWidget(self.pixel_color_indicator, 0, Qt.AlignmentFlag.AlignTop)

        content_row.addLayout(magnifier_column)

        self.output_view = QPlainTextEdit(central)
        self.output_view.setReadOnly(True)
        self.output_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.output_view.setMinimumSize(280, 160)
        self.output_view.setStyleSheet(
            "QPlainTextEdit { font-family: Consolas, 'Courier New', monospace; }"
        )
        content_row.addWidget(self.output_view, 1)
        root_layout.addLayout(content_row)

        self.setCentralWidget(central)

        self._update_window_flags()
        self._update_display_base_state()

    def _excluded_window_hwnds(self) -> tuple[int, ...]:
        try:
            hwnd = int(self.winId())
        except Exception:
            return ()
        return normalize_window_handles((hwnd,))

    def _build_capture_toolbar_button(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("captureToolbarButton")
        button.setDefaultAction(self.capture_action)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(26, 26)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton#captureToolbarButton { padding: 1px 6px; border-radius: 4px; }"
            "QToolButton#captureToolbarButton:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.62);"
            " }"
            "QToolButton#captureToolbarButton:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#captureToolbarButton:checked:enabled {"
            " background-color: rgba(198, 40, 40, 0.14);"
            " border: 1px solid rgba(198, 40, 40, 0.70);"
            " }"
            "QToolButton#captureToolbarButton:checked:enabled:hover {"
            " background-color: rgba(198, 40, 40, 0.20);"
            " }"
            "QToolButton#captureToolbarButton:checked:pressed {"
            " background-color: rgba(198, 40, 40, 0.24);"
            " }"
            "QToolButton#captureToolbarButton:unchecked:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.62);"
            " }"
            "QToolButton#captureToolbarButton:unchecked:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#captureToolbarButton:unchecked:pressed {"
            " background-color: rgba(46, 125, 50, 0.18);"
            " }"
        )
        return button

    def _build_tooltip_coordinates_toolbar_button(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("tooltipCoordinatesToolbarButton")
        button.setDefaultAction(self.tooltip_coordinates_action)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(26, 26)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton#tooltipCoordinatesToolbarButton { padding: 1px 6px; border-radius: 4px; }"
            "QToolButton#tooltipCoordinatesToolbarButton:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.52);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:checked:enabled {"
            " background-color: rgba(198, 40, 40, 0.14);"
            " border: 1px solid rgba(198, 40, 40, 0.70);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:checked:enabled:hover {"
            " background-color: rgba(198, 40, 40, 0.20);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:checked:pressed {"
            " background-color: rgba(198, 40, 40, 0.24);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:unchecked:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.52);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:unchecked:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#tooltipCoordinatesToolbarButton:unchecked:pressed {"
            " background-color: rgba(46, 125, 50, 0.18);"
            " }"
        )
        return button

    def _build_coordinate_capture_toolbar_button(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("coordinateCaptureToolbarButton")
        button.setDefaultAction(self.coordinate_capture_action)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(26, 26)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton#coordinateCaptureToolbarButton { padding: 1px 6px; border-radius: 4px; }"
            "QToolButton#coordinateCaptureToolbarButton:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.52);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:checked:enabled {"
            " background-color: rgba(198, 40, 40, 0.14);"
            " border: 1px solid rgba(198, 40, 40, 0.70);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:checked:enabled:hover {"
            " background-color: rgba(198, 40, 40, 0.20);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:checked:pressed {"
            " background-color: rgba(198, 40, 40, 0.24);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:unchecked:enabled {"
            " background-color: rgba(46, 125, 50, 0.08);"
            " border: 1px solid rgba(46, 125, 50, 0.52);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:unchecked:enabled:hover {"
            " background-color: rgba(46, 125, 50, 0.14);"
            " }"
            "QToolButton#coordinateCaptureToolbarButton:unchecked:pressed {"
            " background-color: rgba(46, 125, 50, 0.18);"
            " }"
        )
        return button

    def _build_help_toolbar_button(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("helpToolbarButton")
        button.setDefaultAction(self.documentation_action)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(26, 26)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton#helpToolbarButton {"
            " padding: 0px;"
            " border: 0;"
            " background-color: transparent;"
            " }"
            "QToolButton#helpToolbarButton:hover {"
            " background-color: rgba(90, 90, 90, 0.06);"
            " }"
            "QToolButton#helpToolbarButton:pressed {"
            " background-color: rgba(90, 90, 90, 0.10);"
            " }"
        )
        return button

    def _build_toolbar_right_spacer(self) -> QWidget:
        spacer = QWidget()
        spacer.setObjectName("helpToolbarSpacer")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setMinimumWidth(0)
        spacer.setMaximumWidth(16777215)
        return spacer

    def _update_window_flags(self) -> None:
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            self.stay_on_top_checkbox.isChecked(),
        )

    def _sync_capture_state(self) -> None:
        if self.capture_action.isChecked():
            self.capture_action.setText("Disable Capture")
        else:
            self.capture_action.setText("Capture")
        self._update_capture_action_icon()
        if self.capture_action.isChecked():
            self._timer.start()
        else:
            self._timer.stop()

    def _update_display_base_state(self) -> None:
        label = {
            NumericBase.HEX: "Hexadecimal",
            NumericBase.DECIMAL: "Decimal",
            NumericBase.OCTAL: "Octal",
        }[self._display_base]
        self.base_label.setText(f"Base: {label}")

    def _update_zoom_state(self) -> None:
        self.zoom_label.setText("Zoom:")
        self.zoom_slider.blockSignals(True)
        try:
            self.zoom_slider.setValue(self._zoom_factor)
        finally:
            self.zoom_slider.blockSignals(False)
        self.zoom_value_label.setText(f"{self._zoom_factor}x")
        self.zoom_fit_action.setChecked(self._zoom_mode == "fit")
        for action in self.zoom_preset_actions:
            action.setChecked(int(action.data()) == self._zoom_factor)
        self.zoom_custom_action.setChecked(
            self._zoom_mode == "manual"
            and all(int(action.data()) != self._zoom_factor for action in self.zoom_preset_actions)
        )

    def _render_snapshot(self) -> None:
        scrollbar = self.output_view.verticalScrollBar()
        scroll_value = scrollbar.value()
        at_bottom = scroll_value == scrollbar.maximum()
        self.output_view.setPlainText(
            format_pixel_inspector_snapshot(
                self._current_snapshot,
                base=self._display_base,
                capture_enabled=self.capture_action.isChecked(),
                extra_lines=self._mouse_click_notes,
            )
        )
        if at_bottom and self._auto_follow_coordinate_capture:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(scroll_value, scrollbar.maximum()))
        self._update_pixel_color_indicator()

    def _update_pixel_color_indicator(self) -> None:
        color = self._current_snapshot.pixel_color if self._current_snapshot is not None else None
        self.pixel_color_indicator.setText(format_color_indicator(color, self._display_base))
        if color is None or not color.isValid():
            self.pixel_color_indicator.setStyleSheet(
                "QLabel { border: 1px solid #8c8c8c; background: rgba(255, 255, 255, 180); color: #444444; font-size: 9px; }"
            )
            return

        luminance = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        text_color = "#1c1c1c" if luminance > 160 else "#f7f7f7"
        self.pixel_color_indicator.setStyleSheet(
            "QLabel { "
            f"border: 1px solid #8c8c8c; background: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()}); "
            f"color: {text_color}; font-size: 9px; "
            "}"
        )

    def open_documentation(self) -> None:
        if self._help_browser_window is None:
            self._help_browser_window = ActionShellScriptHelpBrowser(
                on_close=self._clear_help_browser_window,
            )
        self._help_browser_window.open_at_section(
            pixel_inspector_guide_path(),
            "main-controls",
            anchor_text="Main Controls",
        )
        if self._help_browser_window.isMinimized():
            self._help_browser_window.showNormal()
        else:
            self._help_browser_window.show()
        self._help_browser_window.raise_()
        self._help_browser_window.activateWindow()

    def _clear_help_browser_window(self) -> None:
        self._help_browser_window = None

    def open_about(self) -> None:
        QMessageBox.about(
            self,
            "About Pixel Inspector",
            "Pixel Inspector\n\n"
            "A compact pointer and pixel inspection tool for screen sampling, "
            "window lookup, and zoomed magnifier review. On Windows, it uses "
            "Win32 APIs to resolve the window handle and title beneath the pointer.",
        )

    def _update_magnifier_preview(self) -> None:
        pixmap = render_magnifier_pixmap(
            self._current_magnifier_frame,
            zoom_factor=self._zoom_factor,
        )
        if pixmap is None:
            self.magnifier_placeholder.setPixmap(QPixmap())
            self.magnifier_placeholder.setText("100x100\nMagnifier")
            return

        self.magnifier_placeholder.setPixmap(pixmap)
        self.magnifier_placeholder.setText("")

    def _on_capture_toggled(self, checked: bool) -> None:
        self._sync_capture_state()
        if checked:
            self.refresh_snapshot(force=True)
        else:
            self._render_snapshot()

    def _on_tooltip_coordinates_toggled(self, checked: bool) -> None:
        with QSignalBlocker(self.tooltip_coordinates_action), QSignalBlocker(self.tooltip_coordinates_menu_action):
            self.tooltip_coordinates_action.setChecked(checked)
            self.tooltip_coordinates_menu_action.setChecked(checked)

        if checked:
            self.tooltip_coordinates_action.setText("Disable Pointer Coordinates")
            self.tooltip_coordinates_menu_action.setText("Disable Pointer Coordinates")
            self._tooltip_coordinates_timer.start()
            self._update_tooltip_coordinates()
            self._update_tooltip_coordinates_icons()
            return

        self.tooltip_coordinates_action.setText("Enable Pointer Coordinates")
        self.tooltip_coordinates_menu_action.setText("Enable Pointer Coordinates")
        self._tooltip_coordinates_timer.stop()
        QToolTip.hideText()
        self._update_tooltip_coordinates_icons()

    def _update_tooltip_coordinates(self) -> None:
        if not self.tooltip_coordinates_action.isChecked():
            QToolTip.hideText()
            return

        point = QCursor.pos()
        QToolTip.showText(point, f"X:{point.x()}, Y:{point.y()}", self)

    def _on_coordinate_capture_toggled(self, checked: bool) -> None:
        self._coordinate_capture_enabled = checked
        if checked:
            self.coordinate_capture_action.setText("Disable Coordinate Capture")
        else:
            self.coordinate_capture_action.setText("Enable Coordinate Capture")
        self._update_coordinate_capture_icon()

        if checked:
            if not self._start_coordinate_capture_listener():
                self._show_coordinate_capture_status_message(
                    "Coordinate Capture: desktop listener unavailable on this machine; "
                    "local clicks only."
                )
            self._install_coordinate_capture_event_filter()
            return

        self._stop_coordinate_capture_listener()
        self._remove_coordinate_capture_event_filter()

    def _install_coordinate_capture_event_filter(self) -> None:
        if self._coordinate_capture_filter_installed:
            return

        app = QApplication.instance()
        if app is None:
            return

        app.installEventFilter(self)
        self._coordinate_capture_filter_installed = True

    def _remove_coordinate_capture_event_filter(self) -> None:
        if not self._coordinate_capture_filter_installed:
            return

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._coordinate_capture_filter_installed = False

    def _show_coordinate_capture_status_message(self, message: str, timeout_ms: int = 5000) -> None:
        self.statusBar().showMessage(message, timeout_ms)
        QToolTip.showText(QCursor.pos(), message, self)

    def _start_coordinate_capture_listener(self) -> bool:
        if self._coordinate_capture_listener is not None:
            return True

        try:
            listener = mouse.Listener(on_click=self._on_global_mouse_click)
            listener.start()
        except Exception:
            self._coordinate_capture_listener = None
            return False

        self._coordinate_capture_listener = listener
        return True

    def _stop_coordinate_capture_listener(self) -> None:
        listener = self._coordinate_capture_listener
        self._coordinate_capture_listener = None
        if listener is None:
            return

        try:
            listener.stop()
        except Exception:
            pass

    def _on_auto_follow_coordinate_capture_toggled(self, checked: bool) -> None:
        self._auto_follow_coordinate_capture = checked
        if checked:
            self.auto_follow_coordinate_capture_action.setText("Disable Auto-follow Coordinate Capture")
        else:
            self.auto_follow_coordinate_capture_action.setText("Enable Auto-follow Coordinate Capture")

    @staticmethod
    def _mouse_button_name(button: Qt.MouseButton) -> str | None:
        return {
            Qt.MouseButton.LeftButton: "left",
            Qt.MouseButton.RightButton: "right",
            Qt.MouseButton.MiddleButton: "middle",
            Qt.MouseButton.XButton1: "x1",
            Qt.MouseButton.XButton2: "x2",
        }.get(button)

    def _mouse_event_global_point(self, event) -> QPoint | None:
        if hasattr(event, "globalPosition"):
            try:
                return event.globalPosition().toPoint()
            except Exception:
                return None
        if hasattr(event, "globalPos"):
            try:
                return event.globalPos()
            except Exception:
                return None
        return None

    def _should_skip_coordinate_capture(self, event) -> bool:
        point = self._mouse_event_global_point(event)
        if point is None:
            return False
        return self.frameGeometry().contains(point)

    def _is_primary_mouse_event_target(self, obj, event) -> bool:
        point = self._mouse_event_global_point(event)
        if point is None:
            return True

        if not self.frameGeometry().contains(point):
            return True

        target = QApplication.widgetAt(point)
        if target is None:
            return True

        return obj is target

    def _record_mouse_click(self, *, button: str, point: QPoint) -> None:
        self._mouse_click_notes.append(f'MouseClick("{button}", {point.x()}, {point.y()}, 1)')
        self._render_snapshot()

    def _record_coordinate_capture_note(self, button: str, x: int, y: int) -> None:
        self._record_mouse_click(button=button, point=QPoint(int(x), int(y)))

    def _on_global_mouse_click(self, x, y, button, pressed) -> None:
        if not pressed or not self._coordinate_capture_enabled:
            return

        point = QPoint(int(x), int(y))
        if self.frameGeometry().contains(point):
            return

        button_name = getattr(button, "name", None)
        if button_name is None:
            button_name = self._mouse_button_name(button)
        if button_name is None:
            return

        self.coordinate_capture_requested.emit(str(button_name), point.x(), point.y())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (
            self._coordinate_capture_enabled
            and event.type() == QEvent.Type.MouseButtonPress
            and not self._should_skip_coordinate_capture(event)
            and self._is_primary_mouse_event_target(obj, event)
        ):
            button_name = self._mouse_button_name(event.button())
            if button_name is not None:
                point = self._mouse_event_global_point(event) or QCursor.pos()
                self._record_mouse_click(button=button_name, point=point)
        return False

    def closeEvent(self, event) -> None:  # noqa: N802
        self._coordinate_capture_enabled = False
        self._remove_coordinate_capture_event_filter()
        self._stop_coordinate_capture_listener()
        super().closeEvent(event)

    def _apply_stay_on_top(self, checked: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        if self.isVisible():
            self.show()
            self.raise_()

    def set_display_base(self, base: NumericBase) -> None:
        if base == self._display_base:
            return
        self._display_base = base
        self.hex_base_action.setChecked(base == NumericBase.HEX)
        self.dec_base_action.setChecked(base == NumericBase.DECIMAL)
        self.oct_base_action.setChecked(base == NumericBase.OCTAL)
        self._update_display_base_state()
        self._render_snapshot()

    def set_zoom_factor(self, zoom_factor: int) -> None:
        self._set_zoom_factor(zoom_factor, mode="manual")

    def restore_defaults(self) -> None:
        self.capture_action.setChecked(True)
        self.tooltip_coordinates_action.setChecked(False)
        self.tooltip_coordinates_menu_action.setChecked(False)
        self.coordinate_capture_action.setChecked(False)
        self.auto_follow_coordinate_capture_action.setChecked(True)
        self.stay_on_top_action.setChecked(True)
        self.set_display_base(NumericBase.HEX)
        self._set_zoom_factor(4, mode="manual")
        self._restore_default_geometry()
        self._current_magnifier_frame = None
        self.refresh_snapshot(force=True)

    def refresh_output(self) -> None:
        self._mouse_click_notes.clear()
        if self.capture_action.isChecked() or self._current_snapshot is None:
            self.refresh_snapshot(force=True)
            return

        self._render_snapshot()

    def _restore_default_geometry(self) -> None:
        if self._default_window_size.isValid():
            self.resize(self._default_window_size)

    def _set_zoom_factor(self, zoom_factor: int, *, mode: str) -> None:
        zoom_factor = max(2, min(16, int(zoom_factor)))
        self._zoom_mode = mode
        if zoom_factor == self._zoom_factor:
            self._update_zoom_state()
            return
        self._zoom_factor = zoom_factor
        self._update_zoom_state()
        self._render_snapshot()
        self._update_magnifier_preview()

    def zoom_in(self) -> None:
        self._set_zoom_factor(self._zoom_factor + 1, mode="manual")

    def zoom_out(self) -> None:
        self._set_zoom_factor(self._zoom_factor - 1, mode="manual")

    def _on_zoom_changed(self, value: int) -> None:
        self._set_zoom_factor(value, mode="manual")

    def _fit_zoom_factor(self) -> int:
        point = QCursor.pos()
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        if screen is None:
            return self._zoom_factor

        geometry = screen.geometry()
        left_space = max(0, point.x() - geometry.left())
        right_space = max(0, geometry.right() - point.x())
        top_space = max(0, point.y() - geometry.top())
        bottom_space = max(0, geometry.bottom() - point.y())
        horizontal_span = 2 * min(left_space, right_space) + 1
        vertical_span = 2 * min(top_space, bottom_space) + 1
        square_span = max(1, min(horizontal_span, vertical_span))
        return max(2, min(16, round(100 / square_span)))

    def fit_zoom(self) -> None:
        self._set_zoom_factor(self._fit_zoom_factor(), mode="fit")

    def _prompt_custom_zoom(self) -> int | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom Zoom")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        label = QLabel("Enter a zoom level between 2x and 16x:", dialog)
        layout.addWidget(label)

        spin = QSpinBox(dialog)
        spin.setRange(2, 16)
        spin.setValue(self._zoom_factor)
        spin.setSuffix("x")
        layout.addWidget(spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return spin.value()
        return None

    def specify_custom_zoom(self) -> None:
        value = self._prompt_custom_zoom()
        if value is not None:
            self._set_zoom_factor(value, mode="manual")

    def refresh_snapshot(self, *, force: bool = False) -> None:
        if self._zoom_mode == "fit":
            self._set_zoom_factor(self._fit_zoom_factor(), mode="fit")
        if force or self.capture_action.isChecked() or self._current_snapshot is None:
            try:
                if self.capture_action.isChecked() or force:
                    self._current_snapshot = self._snapshot_provider()
                    point = QCursor.pos()
                    screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
                    self._current_magnifier_frame = capture_magnifier_frame(
                        screen,
                        point,
                        zoom_factor=self._zoom_factor,
                    )
            except Exception:
                self._current_snapshot = None
                self._current_magnifier_frame = None

        self._render_snapshot()
        if force or self.capture_action.isChecked() or self._current_magnifier_frame is not None:
            self._update_magnifier_preview()

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.output_view.toPlainText())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_capture_state()
        if self.tooltip_coordinates_action.isChecked():
            self._tooltip_coordinates_timer.start()
            self._update_tooltip_coordinates()
        if self.coordinate_capture_action.isChecked():
            self._install_coordinate_capture_event_filter()
        self._update_zoom_state()
        self.refresh_snapshot(force=self.capture_action.isChecked())

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._tooltip_coordinates_timer.stop()
        self._remove_coordinate_capture_event_filter()
        QToolTip.hideText()
        super().hideEvent(event)


# Backward-compatible aliases for older imports.
PointerProbeSnapshot = PixelInspectorSnapshot
MagnifierFrame = PixelInspectorFrame
PointerProbeWindow = PixelInspectorWindow
format_pointer_probe_snapshot = format_pixel_inspector_snapshot
collect_pointer_probe_snapshot = collect_pixel_inspector_snapshot
