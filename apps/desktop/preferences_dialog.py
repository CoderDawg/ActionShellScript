from __future__ import annotations

import copy
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, ClassVar, Protocol, cast

from PySide6.QtCore import Qt, QSignalBlocker, Signal, QSize, QUrl, QRect
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPalette,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QCheckBox,
    QColorDialog,
    QDialog,
    QHeaderView,
    QDoubleSpinBox,
    QComboBox,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QFrame,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QHBoxLayout,
    QSpinBox,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QTextEdit,
    QPlainTextEdit,
    QWidget,
)

from apps.desktop.hotkeys import (
    HOTKEY_DEFINITIONS,
    default_hotkey_bindings,
    display_hotkey_clauses,
    normalized_hotkey_binding,
)
from apps.desktop.message_boxes import question_save_discard_cancel
from application.persistence.desktop_settings_service import DesktopSettingsService
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
from apps.desktop.table_api import (
    ActionCellDelegate,
    ColorCellDelegate,
    CellStyle,
    ColumnSpec,
    color_cell_value,
    contrast_color,
    TableAPI,
    TableOptions,
    KeySequenceDelegate,
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
from apps.desktop.bootstrap import apply_desktop_widget_styles
from infrastructure.input.mouse_movement_profile import MouseMovementProfile
from infrastructure.debug_logger import get_diagnostic_logger, resolve_diagnostic_log_path


log = get_diagnostic_logger("desktop.preferences")


@dataclass(frozen=True)
class TableColumnSpec:
    title: str
    width_mode: str
    fixed_width: int | None = None


@dataclass(frozen=True)
class TableRowSpec:
    key: str
    label: str
    kind: str
    default_value: object | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class PreferencesTableModel:
    table_name: str
    columns: list[TableColumnSpec]
    rows: list[TableRowSpec]


class TableModelColorRow:
    def __init__(
        self,
        model,
        row_index: int,
        column_index: int,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._model = model
        self._row_index = row_index
        self._column_index = column_index
        self._on_changed = on_changed

    def color(self) -> str:
        index = self._model.index(self._row_index, self._column_index)
        return str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip().lower()

    def setColor(self, color: str) -> None:  # noqa: N802
        index = self._model.index(self._row_index, self._column_index)
        qcolor = QColor(color)
        hex_color = qcolor.name().upper()
        self._model.setData(index, hex_color, Qt.ItemDataRole.EditRole)
        self._model.setData(index, qcolor, Qt.ItemDataRole.BackgroundRole)
        self._model.setData(
            index,
            QColor(contrast_color(hex_color)),
            Qt.ItemDataRole.ForegroundRole,
        )
        if self._on_changed is not None:
            self._on_changed()


@dataclass(frozen=True)
class PreferenceSectionSnapshots:
    general: tuple[bool]
    debug: tuple[bool]
    workspace_tabs: tuple[bool, bool, bool, bool, bool, bool]
    appearance_editor: tuple[EditorAppearanceTheme, FontSettings]
    appearance_syntax: SyntaxHighlightTheme
    appearance_dirty_state: DirtyIndicatorTheme
    appearance_tab_attention: WorkspaceTabAttentionTheme
    search_results_colors: tuple[str, str, str, str, str, str, str]
    search_results_spacing: tuple[str, str, str, int, int]
    playback: DesktopPlaybackSettings
    recording: DesktopRecordingSettings
    files: DesktopFilesSettings
    diagnostics: DesktopDiagnosticsSettings
    script: ScriptingSettings
    runtime: DesktopRuntimeSettings
    hotkeys: tuple[tuple[str, str], ...]

    def diff(self, other: "PreferenceSectionSnapshots") -> "PreferenceSectionDirtyState":
        return PreferenceSectionDirtyState(
            general=self.general != other.general,
            debug=self.debug != other.debug,
            workspace_tabs=self.workspace_tabs != other.workspace_tabs,
            appearance_editor=self.appearance_editor != other.appearance_editor,
            appearance_syntax=self.appearance_syntax != other.appearance_syntax,
            appearance_dirty_state=self.appearance_dirty_state != other.appearance_dirty_state,
            appearance_tab_attention=self.appearance_tab_attention != other.appearance_tab_attention,
            search_results_colors=self.search_results_colors != other.search_results_colors,
            search_results_spacing=self.search_results_spacing != other.search_results_spacing,
            appearance=(
                self.appearance_editor != other.appearance_editor
                or self.appearance_syntax != other.appearance_syntax
                or self.appearance_dirty_state != other.appearance_dirty_state
                or self.appearance_tab_attention != other.appearance_tab_attention
                or self.search_results_colors != other.search_results_colors
                or self.search_results_spacing != other.search_results_spacing
            ),
            playback=self.playback != other.playback,
            recording=self.recording != other.recording,
            files=self.files != other.files,
            diagnostics=self.diagnostics != other.diagnostics,
            script=self.script != other.script,
            runtime=self.runtime != other.runtime,
            hotkeys=self.hotkeys != other.hotkeys,
        )


@dataclass(frozen=True)
class PreferenceSectionDirtyState:
    general: bool
    debug: bool
    workspace_tabs: bool
    appearance: bool
    appearance_editor: bool
    appearance_syntax: bool
    appearance_dirty_state: bool
    appearance_tab_attention: bool
    search_results_colors: bool
    search_results_spacing: bool
    playback: bool
    recording: bool
    files: bool
    diagnostics: bool
    script: bool
    runtime: bool
    hotkeys: bool

    def any_dirty(self) -> bool:
        return (
            self.general
            or self.debug
            or self.workspace_tabs
            or self.appearance
            or self.search_results_colors
            or self.search_results_spacing
            or self.playback
            or self.recording
            or self.files
            or self.diagnostics
            or self.script
            or self.runtime
            or self.hotkeys
        )
DEBUG_PREFERENCES_SECTION = "debug"


@dataclass(frozen=True)
class PreferenceSectionDefaultSpec:
    section_name: str
    build_bundle: Callable[["PreferencesDialog"], DesktopSettingsBundle]


class PreferencesTableAdapter(Protocol):
    def build_row(self, table: QTableWidget, row_index: int, row_spec: TableRowSpec) -> None: ...


class StyleTableAdapter:
    def __init__(self, on_color_changed: Callable[[str], None]) -> None:
        self._on_color_changed = on_color_changed

    def build_row(
        self,
        table: QTableWidget,
        row_index: int,
        row_spec: TableRowSpec,
        controls: dict[str, ColorSwatchButton],
    ) -> None:
        label_item = QTableWidgetItem(row_spec.label)
        label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 0, label_item)

        type_item = QTableWidgetItem(str(row_spec.kind).title())
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row_index, 1, type_item)

        default_color = str(row_spec.default_value or "#000000")
        button = ColorSwatchButton(default_color)
        button.colorChanged.connect(self._on_color_changed)
        controls[row_spec.key] = button
        table.setCellWidget(row_index, 2, button)

    def populate_table(
        self,
        table: QTableWidget,
        row_specs: list[TableRowSpec],
        controls: dict[str, ColorSwatchButton],
    ) -> None:
        table.setRowCount(len(row_specs))
        for row_index, row_spec in enumerate(row_specs):
            self.build_row(table, row_index, row_spec, controls)


class ColorRow(QWidget):
    colorChanged = Signal(str)

    def __init__(self, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._button = QPushButton(color.upper())
        self._button.clicked.connect(self._pick_color)
        self._color = QColor(color)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(label))
        layout.addWidget(self._button)
        layout.addStretch(1)
        self._sync_button()

    def _sync_button(self) -> None:
        self._button.setText(self._color.name().upper())
        self._apply_color_palette(self._button, self._color)

    @staticmethod
    def _apply_color_palette(button: QPushButton, color: QColor) -> None:
        palette = button.palette()
        palette.setColor(QPalette.ColorRole.Button, color)
        palette.setColor(
            QPalette.ColorRole.ButtonText,
            QColor("white") if color.lightness() < 128 else QColor("black"),
        )
        button.setAutoFillBackground(True)
        button.setPalette(palette)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Choose Color")
        if not color.isValid():
            return
        self._color = color
        self._sync_button()
        self.colorChanged.emit(self.color())

    def color(self) -> str:
        return self._color.name()

    def setColor(self, color: str) -> None:  # noqa: N802
        self._color = QColor(color)
        self._sync_button()
        self.colorChanged.emit(self.color())


class ColorSwatchButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(96)
        self.clicked.connect(self._pick_color)
        self._sync_button()

    def _sync_button(self) -> None:
        self.setText(self._color.name().upper())
        self._apply_color_palette(self, self._color)

    @staticmethod
    def _apply_color_palette(button: QPushButton, color: QColor) -> None:
        palette = button.palette()
        palette.setColor(QPalette.ColorRole.Button, color)
        palette.setColor(
            QPalette.ColorRole.ButtonText,
            QColor("white") if color.lightness() < 128 else QColor("black"),
        )
        button.setAutoFillBackground(True)
        button.setPalette(palette)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Choose Color")
        if not color.isValid():
            return
        self._color = color
        self._sync_button()
        self.colorChanged.emit(self.color())

    def color(self) -> str:
        return self._color.name()

    def setColor(self, color: str) -> None:  # noqa: N802
        self._color = QColor(color)
        self._sync_button()
        self.colorChanged.emit(self.color())


class MouseMovementCurvePreview(QWidget):
    _min_display_duration_ms = 1_000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._curve_points: tuple[tuple[int, int], ...] = ()
        self._show_reference_curve = True
        self._hover_point_index: int | None = None
        self.setObjectName("runtimeMouseMovementCurvePreview")
        self.setMinimumHeight(200)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_curve_points(self, points: tuple[tuple[int, int], ...]) -> None:
        normalized: list[tuple[int, int]] = []
        for speed, duration_ms in points:
            try:
                normalized_speed = max(1, min(100, int(speed)))
                normalized_duration = max(0, int(duration_ms))
            except (TypeError, ValueError):
                continue
            if normalized and normalized[-1][0] == normalized_speed:
                normalized[-1] = (normalized_speed, normalized_duration)
            else:
                normalized.append((normalized_speed, normalized_duration))
        self._curve_points = tuple(normalized)
        self.update()

    def curve_points(self) -> tuple[tuple[int, int], ...]:
        return self._curve_points

    def set_reference_curve_visible(self, visible: bool) -> None:
        self._show_reference_curve = bool(visible)
        self.update()

    def reference_curve_visible(self) -> bool:
        return self._show_reference_curve

    @staticmethod
    def _default_curve_points() -> tuple[tuple[int, int], ...]:
        return MouseMovementProfile().duration_curve

    def _chart_rect(self) -> QRect:
        return self.rect().adjusted(38, 54, -12, -40)

    def _max_duration(self) -> int:
        durations = [duration for _speed, duration in self._curve_points]
        if self._show_reference_curve:
            durations.extend(duration for _speed, duration in self._default_curve_points())
        max_duration = max(durations, default=0)
        # Keep a shared scale floor so the built-in presets render with visibly different shapes.
        return max(self._min_display_duration_ms, max_duration)

    def _map_speed_to_x(self, chart_rect: QRect, speed: int) -> int:
        normalized_speed = max(1, min(100, speed))
        if chart_rect.width() <= 0:
            return chart_rect.left()
        fraction = 0.0 if normalized_speed <= 1 else (normalized_speed - 1) / 99
        return chart_rect.left() + round(fraction * chart_rect.width())

    def _map_duration_to_y(self, chart_rect: QRect, duration_ms: int, max_duration: int) -> int:
        normalized_duration = max(0, min(max_duration, duration_ms))
        if chart_rect.height() <= 0:
            return chart_rect.bottom()
        fraction = normalized_duration / max_duration
        return chart_rect.bottom() - round(fraction * chart_rect.height())

    def _mapped_points(self) -> list[tuple[int, int]]:
        return self._mapped_points_for(self._curve_points)

    def _mapped_points_for(
        self,
        points: tuple[tuple[int, int], ...],
    ) -> list[tuple[int, int]]:
        chart_rect = self._chart_rect()
        max_duration = self._max_duration()
        return [
            (
                self._map_speed_to_x(chart_rect, speed),
                self._map_duration_to_y(chart_rect, duration_ms, max_duration),
            )
            for speed, duration_ms in points
        ]

    def _nearest_point_index(self, position) -> int | None:
        if not self._curve_points:
            return None
        chart_rect = self._chart_rect()
        if not chart_rect.contains(position):
            return None
        mapped_points = self._mapped_points()
        if not mapped_points:
            return None
        best_index: int | None = None
        best_distance_sq: int | None = None
        for index, (x, y) in enumerate(mapped_points):
            dx = position.x() - x
            dy = position.y() - y
            distance_sq = dx * dx + dy * dy
            if distance_sq > 144:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_index = index
                best_distance_sq = distance_sq
        return best_index

    def _point_tooltip_text(self, index: int) -> str:
        speed, duration_ms = self._curve_points[index]
        return f"Speed: {speed}%\nDuration: {duration_ms:,} ms"

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        position = event.position().toPoint()
        index = self._nearest_point_index(position)
        if index != self._hover_point_index:
            self._hover_point_index = index
            self.update()
        if index is None:
            QToolTip.hideText()
            return
        QToolTip.showText(event.globalPosition().toPoint(), self._point_tooltip_text(index), self)

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        if self._hover_point_index is not None:
            self._hover_point_index = None
            self.update()
        QToolTip.hideText()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(0, 0, -1, -1)
        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        background.setColorAt(0.0, QColor("#1a2331"))
        background.setColorAt(1.0, QColor("#111927"))
        painter.fillRect(rect, background)
        painter.setPen(QPen(QColor("#314055")))
        painter.drawRoundedRect(rect, 8, 8)

        title_rect = rect.adjusted(12, 8, -12, -8)
        painter.setPen(QColor("#f3f5f8"))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "Curve Preview")

        subtitle_rect = rect.adjusted(12, 28, -12, -8)
        painter.setPen(QColor("#97a6bb"))
        painter.drawText(
            subtitle_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Duration (ms) vs speed (%)",
        )

        chart_rect = self._chart_rect()
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            painter.end()
            return

        points = self._curve_points
        max_duration = self._max_duration()
        reference_points = self._default_curve_points() if self._show_reference_curve else ()

        if not points:
            empty_rect = chart_rect.adjusted(-18, -18, 18, 18)
            painter.setPen(QColor("#263244"))
            painter.setBrush(QColor("#18212f"))
            painter.drawRoundedRect(empty_rect, 10, 10)
            painter.setPen(QColor("#8b98ad"))
            painter.drawText(empty_rect, Qt.AlignmentFlag.AlignCenter, "No curve points")
            painter.end()
            return

        mapped_reference_points = self._mapped_points_for(reference_points) if reference_points else []
        mapped_points = self._mapped_points_for(points)

        grid_pen = QPen(QColor("#263244"))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        speed_ticks = [1, 25, 50, 75, 100]
        duration_ticks = sorted(
            {
                0,
                round(max_duration * 0.25),
                round(max_duration * 0.5),
                round(max_duration * 0.75),
                max_duration,
            }
        )
        tick_font = painter.font()
        tick_point_size = tick_font.pointSize()
        if tick_point_size <= 0:
            tick_point_size = 8
        tick_font.setPointSize(max(7, tick_point_size - 1))
        painter.setFont(tick_font)
        for tick in duration_ticks:
            y = self._map_duration_to_y(chart_rect, tick, max_duration)
            painter.drawLine(chart_rect.left(), y, chart_rect.right(), y)
        for tick in speed_ticks:
            x = self._map_speed_to_x(chart_rect, tick)
            painter.drawLine(x, chart_rect.top(), x, chart_rect.bottom())

        axis_pen = QPen(QColor("#60708a"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(chart_rect.left(), chart_rect.top(), chart_rect.left(), chart_rect.bottom())
        painter.drawLine(chart_rect.left(), chart_rect.bottom(), chart_rect.right(), chart_rect.bottom())

        painter.setPen(QColor("#aeb9ca"))
        painter.drawText(
            chart_rect.adjusted(-36, -4, -8, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            "Duration",
        )
        painter.drawText(
            chart_rect.adjusted(0, 6, 0, 22),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            "Speed",
        )

        painter.setPen(QColor("#7f8ea5"))
        for tick in duration_ticks:
            y = self._map_duration_to_y(chart_rect, tick, max_duration)
            label_rect = QRect(rect.left() + 6, y - 8, chart_rect.left() - rect.left() - 12, 16)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{tick:,}",
            )
        for tick in speed_ticks:
            x = self._map_speed_to_x(chart_rect, tick)
            label_rect = QRect(x - 12, chart_rect.bottom() + 8, 24, 16)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                str(tick),
            )

        painter.setPen(QPen(QColor("#8b98ad")))
        painter.drawText(
            QRect(rect.left() + 8, chart_rect.top() - 16, 20, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "ms",
        )
        painter.drawText(
            QRect(chart_rect.right() - 16, chart_rect.bottom() + 6, 16, 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            "%",
        )

        min_duration = min(duration for _speed, duration in points)
        max_duration_value = max(duration for _speed, duration in points)
        badge_specs = [
            ("Min", f"{min_duration:,} ms", QColor("#1d3552"), QColor("#7fc0ff")),
            ("Max", f"{max_duration_value:,} ms", QColor("#2d2642"), QColor("#d7b8ff")),
            ("Pts", f"{len(points)}", QColor("#233423"), QColor("#a6e3a1")),
        ]
        badge_metrics = QFontMetrics(painter.font())
        badge_y = rect.top() + 38
        badge_right = rect.right() - 12
        for label, value, fill_color, accent_color in reversed(badge_specs):
            text = f"{label} {value}"
            badge_width = badge_metrics.horizontalAdvance(text) + 18
            badge_rect = QRect(badge_right - badge_width, badge_y, badge_width, 18)
            painter.setPen(QPen(accent_color))
            painter.setBrush(fill_color)
            painter.drawRoundedRect(badge_rect, 9, 9)
            painter.setPen(accent_color)
            painter.drawText(badge_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter, text)
            badge_right -= badge_width + 6

        if mapped_reference_points:
            reference_pen = QPen(QColor("#c9d2df"))
            reference_pen.setWidth(2)
            reference_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(reference_pen)
            painter.setBrush(QColor("#c9d2df"))
            previous_point: tuple[int, int] | None = None
            for x, y in mapped_reference_points:
                if previous_point is not None:
                    painter.drawLine(previous_point[0], previous_point[1], x, y)
                previous_point = (x, y)
            for x, y in mapped_reference_points:
                painter.drawEllipse(x - 3, y - 3, 6, 6)

        if len(mapped_points) >= 2:
            fill_path = QPainterPath()
            fill_path.moveTo(mapped_points[0][0], chart_rect.bottom())
            fill_path.lineTo(mapped_points[0][0], mapped_points[0][1])
            for x, y in mapped_points[1:]:
                fill_path.lineTo(x, y)
            fill_path.lineTo(mapped_points[-1][0], chart_rect.bottom())
            fill_path.closeSubpath()
            painter.fillPath(fill_path, QColor(106, 166, 255, 48))

        curve_pen = QPen(QColor("#6aa6ff"))
        curve_pen.setWidth(3)
        painter.setPen(curve_pen)
        previous_point: tuple[int, int] | None = None
        for x, y in mapped_points:
            if previous_point is not None:
                painter.drawLine(previous_point[0], previous_point[1], x, y)
            previous_point = (x, y)

        for index, (x, y) in enumerate(mapped_points):
            painter.setBrush(QColor("#6aa6ff"))
            if index == self._hover_point_index:
                painter.setPen(QPen(QColor("#ffffff"), 2))
                radius = 7
            else:
                painter.setPen(QPen(QColor("#eef4ff"), 1))
                radius = 5 if index in (0, len(mapped_points) - 1) else 4
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

        painter.end()


class _PreferencesHost(Protocol):
    def save_preferences(self) -> bool: ...


class PreferencesDialog(QDialog):
    preferencesChanged = Signal(object)
    hotkeysSearchTextChanged = Signal(str)
    saveRequested = Signal()
    discardRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_desktop_widget_styles()
        self.setWindowTitle("Preferences")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(900, 560)
        self._files_preview_base_directory = self._resolve_files_preview_base_directory(parent)
        self._draft_bundle: DesktopSettingsBundle = DesktopSettingsBundle()
        self._committed_bundle: DesktopSettingsBundle = copy.deepcopy(self._draft_bundle)
        self._dirty = False
        self._loading_preferences = False
        self._preferences_batch_depth = 0
        self._hotkeys_search_text = ""
        self._category_titles = [
            "General",
            "Files",
            "Editing",
            "Workspace",
            "Hotkeys",
            "Playback",
            "Recording",
            "Runtime",
            "Diagnostics",
            "Debug",
        ]
        self._page_header_frames: dict[str, QFrame] = {}
        self._page_scroll_areas: dict[str, QScrollArea] = {}
        self._text_editor_item_titles = [
            "Editor",
            "Typography",
            "Language",
            "Indentation",
            "Typing",
            "Save",
        ]
        self._appearance_style_fields = [
            ("Editor", "editor_text", "editor_background", "#000000", "#ffffff"),
            ("Gutter", "gutter_text", "gutter_background", "#202020", "#f2f2f2"),
            (
                "Current line",
                "current_line_foreground",
                "current_line_highlight",
                "#000000",
                "#fff4c2",
            ),
        ]
        self._dirty_state_style_fields = [
            ("Text", "dirty_text", "foreground", "#7a4a00"),
            ("Accent", "dirty_accent", "foreground", "#8b6a2f"),
            ("Selected area", "dirty_selected_background", "background", "#f0ddb4"),
            ("Border", "dirty_border", "background", "#ead8b6"),
        ]
        self._workspace_tab_attention_default_color = "#2b7de9"
        self._appearance_style_controls: dict[str, ColorSwatchButton] = {}
        self._style_fields = [
            ("Keyword", "keyword", "#005cc5"),
            ("String", "string", "#0b7a75"),
            ("Comment", "comment", "#6a737d"),
            ("Number", "number", "#b31d28"),
        ]
        self._table_api = TableAPI(TableOptions(editable=True, sortable=False, filterable=False))
        self._editor_style_data = self._default_editor_style_values()
        self.category_list = QListWidget()
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.category_list.setIconSize(QSize(12, 12))
        self.category_list.setFixedWidth(170)
        self.category_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.category_list.currentRowChanged.connect(self._on_category_changed)

        self.stack = QStackedWidget()
        self.stack.setObjectName("preferencesStack")

        self.right_frame = QFrame()
        self.right_frame.setObjectName("preferencesOutline")
        self.right_frame.setFrameShape(QFrame.Shape.Box)
        self.right_frame.setFrameShadow(QFrame.Shadow.Plain)
        self.right_frame.setStyleSheet(
            "#preferencesOutline { border: 1px solid #8a8a8a; border-radius: 6px; }"
        )
        right_layout = QVBoxLayout(self.right_frame)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.addWidget(self.stack)

        self._build_pages()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.addWidget(self.category_list, 0)
        content_layout.addWidget(self.right_frame, 1)
        root_layout.addLayout(content_layout)

        footer = QDialogButtonBox()
        self.save_button = footer.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        self.close_button = footer.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)
        footer.accepted.connect(self.saveRequested.emit)
        footer.rejected.connect(self.close)

        self.dirty_indicator_label = QLabel("Unsaved changes")
        self.dirty_indicator_label.setObjectName("preferencesDirtyIndicator")
        self.dirty_indicator_label.setStyleSheet(
            "QLabel {"
            " color: #7a3f00;"
            " font-size: 11px;"
            " font-weight: 800;"
            " padding: 3px 10px;"
            " border: 1px solid #c9821f;"
            " border-radius: 10px;"
            " background-color: #ffe1a8;"
            " }"
        )
        self.dirty_indicator_label.setVisible(False)

        self.hotkeys_save_warning_label = QLabel("Resolve hotkey conflicts before saving")
        self.hotkeys_save_warning_label.setObjectName("hotkeysSaveWarning")
        self.hotkeys_save_warning_label.setStyleSheet(
            "QLabel {"
            " color: #8a1f11;"
            " font-size: 11px;"
            " font-weight: 800;"
            " padding: 5px 10px;"
            " border: 1px solid #d66b55;"
            " border-radius: 10px;"
            " background-color: #ffe1db;"
            " }"
        )
        self.hotkeys_save_warning_label.setVisible(False)

        self.theme_readability_warning_label = QLabel("Theme contrast is too low to save safely")
        self.theme_readability_warning_label.setObjectName("themeReadabilityWarning")
        self.theme_readability_warning_label.setStyleSheet(
            "QLabel {"
            " color: #5f3b00;"
            " font-size: 11px;"
            " font-weight: 800;"
            " padding: 5px 10px;"
            " border: 1px solid #d2a23d;"
            " border-radius: 10px;"
            " background-color: #fff2cd;"
            " }"
        )
        self.theme_readability_warning_label.setVisible(False)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.addWidget(self.dirty_indicator_label)
        footer_row.addStretch(1)
        footer_row.addWidget(self.theme_readability_warning_label)
        footer_row.addWidget(self.hotkeys_save_warning_label)
        footer_row.addWidget(footer)
        root_layout.addLayout(footer_row)

        self.set_preferences(self.draft_bundle)
        self.category_list.setCurrentRow(0)

    def _build_pages(self) -> None:
        self._add_category("General", self._build_general_page())
        self._add_category("Files", self._build_files_page())
        self._add_category("Editing", self._build_text_editor_page())
        self._add_category("Workspace", self._build_appearance_page())
        self._add_category("Hotkeys", self._build_hotkeys_page())
        self._add_category("Playback", self._build_playback_page())
        self._add_category("Recording", self._build_recording_page())
        self._add_category("Runtime", self._build_runtime_page())
        self._add_category("Diagnostics", self._build_diagnostics_page())
        self._add_category("Debug", self._build_debug_page())

    def _add_category(self, title: str, page: QWidget) -> None:
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, title)
        self.category_list.addItem(item)
        scroll_area = self._wrap_scrollable_page(page)
        self._page_scroll_areas[title] = scroll_area
        self.stack.addWidget(scroll_area)

    def _wrap_scrollable_page(self, page: QWidget) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        scroll_area.setWidget(page)
        return scroll_area

    def _make_page_shell(
        self,
        heading: str,
        description: str,
        *,
        actions: list[tuple[str, Callable[[], None]]] | None = None,
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 20, 24, 20)
        page_layout.setSpacing(12)

        header_frame = QFrame()
        header_frame.setObjectName("preferencesPageHeader")
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_frame.setFrameShadow(QFrame.Shadow.Plain)
        header_frame.setStyleSheet(
            "#preferencesPageHeader { border: 1px solid transparent; border-radius: 10px; }"
        )
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(8)

        header_top_row = QHBoxLayout()
        header_top_row.setContentsMargins(0, 0, 0, 0)
        header_top_row.setSpacing(12)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(4)
        title_label = QLabel(heading)
        title_label.setObjectName("preferencesHeading")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        subtitle_label = QLabel(description)
        subtitle_label.setWordWrap(True)
        title_stack.addWidget(title_label)
        title_stack.addWidget(subtitle_label)

        header_top_row.addLayout(title_stack, 1)

        if actions:
            action_column = QVBoxLayout()
            action_column.setSpacing(6)
            action_column.setAlignment(Qt.AlignmentFlag.AlignRight)
            for label, callback in actions:
                button = QPushButton(label)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setFlat(True)
                button.setStyleSheet(
                    "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
                )
                button.clicked.connect(callback)
                action_column.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)
            header_top_row.addLayout(action_column, 0)

        header_layout.addLayout(header_top_row)

        self._page_header_frames[heading] = header_frame
        page_layout.addWidget(header_frame)
        page_layout.addStretch(1)
        return page, page_layout

    def _build_appearance_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Workspace",
            "Adjust dirty-state styling and workspace tab visibility.",
            actions=[
                ("Restore Defaults", self.reset_appearance_settings_to_defaults),
            ],
        )

        self._appearance_item_titles = [
            "Dirty State",
            "Layout",
            "Search Results",
            "Search Spacing",
        ]
        self.appearance_item_list = QListWidget()
        self.appearance_item_list.setObjectName("appearanceItemList")
        self.appearance_item_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.appearance_item_list.setFixedWidth(180)
        self.appearance_item_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.appearance_item_list.currentRowChanged.connect(self._on_appearance_item_changed)
        for title in self._appearance_item_titles:
            self.appearance_item_list.addItem(title)

        self.appearance_item_stack = QStackedWidget()
        self.appearance_item_stack.setObjectName("appearanceItemStack")
        self.appearance_item_stack.addWidget(self._build_appearance_dirty_state_page())
        self.appearance_item_stack.addWidget(self._build_workspace_tabs_page())
        self.appearance_item_stack.addWidget(self._build_workspace_search_results_page())
        self.appearance_item_stack.addWidget(self._build_workspace_search_spacing_page())

        appearance_body = QWidget()
        appearance_body_layout = QHBoxLayout(appearance_body)
        appearance_body_layout.setContentsMargins(0, 0, 0, 0)
        appearance_body_layout.setSpacing(12)
        appearance_body_layout.addWidget(self.appearance_item_list, 0)
        appearance_body_layout.addWidget(self.appearance_item_stack, 1)
        layout.insertWidget(1, appearance_body)

        self.appearance_item_list.setCurrentRow(0)
        return page

    def _build_text_editor_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Editing",
            "Configure the editor, fonts, script language, and generated script formatting.",
            actions=[
                ("Restore Defaults", self.reset_text_editor_settings_to_defaults),
            ],
        )

        self._text_editor_item_list = QListWidget()
        self._text_editor_item_list.setObjectName("textEditorItemList")
        self._text_editor_item_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._text_editor_item_list.setFixedWidth(160)
        self._text_editor_item_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._text_editor_item_list.currentRowChanged.connect(self._on_text_editor_item_changed)
        for title in self._text_editor_item_titles:
            self._text_editor_item_list.addItem(title)

        self._text_editor_item_stack = QStackedWidget()
        self._text_editor_item_stack.setObjectName("textEditorItemStack")
        self._text_editor_item_stack.addWidget(self._build_appearance_editor_page())
        self._text_editor_item_stack.addWidget(self._build_appearance_typography_page())
        self._text_editor_item_stack.addWidget(self._build_appearance_script_language_page())
        self._text_editor_item_stack.addWidget(self._build_formatting_indentation_page())
        self._text_editor_item_stack.addWidget(self._build_formatting_typing_page())
        self._text_editor_item_stack.addWidget(self._build_formatting_save_time_page())
        self.text_editor_item_list = self._text_editor_item_list
        self.text_editor_item_stack = self._text_editor_item_stack

        text_editor_body = QWidget()
        text_editor_body_layout = QHBoxLayout(text_editor_body)
        text_editor_body_layout.setContentsMargins(0, 0, 0, 0)
        text_editor_body_layout.setSpacing(12)
        text_editor_body_layout.addWidget(self._text_editor_item_list, 0)
        text_editor_body_layout.addWidget(self._text_editor_item_stack, 1)
        layout.insertWidget(1, text_editor_body)

        self._text_editor_item_list.setCurrentRow(0)
        return page

    def _on_appearance_item_changed(self, index: int) -> None:
        if hasattr(self, "appearance_item_stack") and index >= 0:
            self.appearance_item_stack.setCurrentIndex(index)
        self._update_appearance_item_markers()

    def _on_text_editor_item_changed(self, index: int) -> None:
        if hasattr(self, "_text_editor_item_stack") and index >= 0:
            self._text_editor_item_stack.setCurrentIndex(index)
        self._update_appearance_item_markers()

    def _build_section_page(
        self,
        object_name: str,
        title: str,
        description: str,
    ) -> tuple[QWidget, QVBoxLayout, QVBoxLayout]:
        page = QWidget()
        page.setObjectName(object_name)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { padding: 8px; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(title_label, 1)
        frame_layout.addLayout(header)

        note = QLabel(description)
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)
        page_layout.addWidget(frame)
        page_layout.addStretch(1)
        return page, page_layout, frame_layout

    def _build_appearance_editor_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "editingEditorPage",
            "Editor",
            "Customize the editor color palette.",
        )
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addStretch(1)
        editor_reset_button = QPushButton("Restore Editor Defaults")
        editor_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        editor_reset_button.setFlat(True)
        editor_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        editor_reset_button.clicked.connect(self.reset_editor_settings_to_defaults)
        header.addWidget(editor_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addLayout(header, 0)
        self.appearance_style_table = self._build_table_api_style_table(
            "appearanceStyleTable",
            [],
            rows=self._editor_style_table_rows(self._default_editor_style_values()),
        )
        frame_layout.addWidget(self.appearance_style_table)
        return page

    def _build_appearance_typography_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "appearanceTypographyPage",
            "Typography",
            "Set the editor font family, size, weight, and line spacing.",
        )
        self.font_family_combo = QFontComboBox()
        default_font = QFont()
        default_font.setFamily("Consolas")
        default_font.setPointSize(11)
        self.font_family_combo.setCurrentFont(default_font)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 48)
        self.font_size_spin.setValue(11)
        self.font_weight_spin = QSpinBox()
        self.font_weight_spin.setRange(1, 1000)
        self.font_weight_spin.setValue(400)
        self.font_line_spacing_spin = QDoubleSpinBox()
        self.font_line_spacing_spin.setRange(0.5, 3.0)
        self.font_line_spacing_spin.setSingleStep(0.1)
        self.font_line_spacing_spin.setDecimals(2)
        self.font_line_spacing_spin.setValue(1.0)

        self.font_family_combo.currentFontChanged.connect(self._emit_preferences_changed)
        self.font_size_spin.valueChanged.connect(self._emit_preferences_changed)
        self.font_weight_spin.valueChanged.connect(self._emit_preferences_changed)
        self.font_line_spacing_spin.valueChanged.connect(self._emit_preferences_changed)

        self.typography_rows = []
        self.add_typography_row("Font family", self.font_family_combo)
        self.add_typography_row("Font size", self.font_size_spin)
        self.add_typography_row("Font weight", self.font_weight_spin)
        self.add_typography_row("Line spacing multiplier", self.font_line_spacing_spin)
        self.typography_table = self._build_typography_table(self.typography_rows)
        frame_layout.addWidget(self.typography_table)
        return page

    def _build_appearance_script_language_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "editingLanguagePage",
            "Language",
            "Choose the script language and adjust syntax colors.",
        )
        script_group = QFrame()
        script_group.setFrameShape(QFrame.Shape.StyledPanel)
        script_group.setStyleSheet("QFrame { padding: 8px; }")
        script_group_layout = QVBoxLayout(script_group)
        script_group_layout.setContentsMargins(0, 0, 0, 0)
        script_group_layout.setSpacing(8)

        script_header = QHBoxLayout()
        script_header.setContentsMargins(0, 0, 0, 0)
        script_header.setSpacing(8)
        script_header.addStretch(1)
        script_reset_button = QPushButton("Reset Language Defaults")
        script_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        script_reset_button.setFlat(True)
        script_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        script_reset_button.clicked.connect(self.reset_script_language_settings_to_defaults)
        script_header.addWidget(script_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        script_group_layout.addLayout(script_header, 0)
        script_group_layout.addWidget(self._build_script_settings_frame())
        frame_layout.addWidget(script_group)
        frame_layout.addWidget(self._build_syntax_colors_group())
        return page

    def _build_syntax_colors_group(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { padding: 8px; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        title_label = QLabel("Syntax Colors")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        frame_layout.addWidget(title_label)

        note = QLabel("Adjust the default token colors used for syntax highlighting.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addStretch(1)
        style_reset_button = QPushButton("Restore Syntax Colors Defaults")
        style_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        style_reset_button.setFlat(True)
        style_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        style_reset_button.clicked.connect(self.reset_style_settings_to_defaults)
        header.addWidget(style_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addLayout(header, 0)

        self.style_table_container = self._build_table_api_color_table(
            "styleTable",
            self._style_fields,
        )
        if not hasattr(self, "style_table"):
            raise RuntimeError("styleTable was not created")
        frame_layout.addWidget(self.style_table_container)
        return frame

    def _build_formatting_indentation_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "formattingIndentationPage",
            "Indentation",
            "Choose the indentation policy used by the editor and formatter.",
        )
        self.formatting_indent_spin = QSpinBox()
        self.formatting_indent_spin.setRange(1, 16)
        self.formatting_indent_spin.setValue(4)
        self.formatting_indent_spin.valueChanged.connect(self._emit_preferences_changed)
        self.formatting_use_spaces_checkbox = QCheckBox("Use spaces for indentation")
        self.formatting_use_spaces_checkbox.toggled.connect(self._emit_preferences_changed)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.addRow("Indent width", self.formatting_indent_spin)
        form.addRow(self.formatting_use_spaces_checkbox)
        frame_layout.addLayout(form)
        return page

    def _build_formatting_typing_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "formattingTypingPage",
            "Typing",
            "Control auto-indent and Enter/Tab behavior while editing.",
        )
        self.formatting_auto_indent_checkbox = QCheckBox("Auto-indent on Enter")
        self.formatting_auto_indent_checkbox.toggled.connect(self._emit_preferences_changed)
        frame_layout.addWidget(self.formatting_auto_indent_checkbox)
        note = QLabel(
            "Tab indents selection, Shift+Tab dedents selection, and Enter can wrap a selected block."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)
        return page

    def _build_formatting_save_time_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "formattingSaveTimePage",
            "Save",
            "Choose whether scripts are auto-formatted when saved.",
        )
        self.formatting_auto_format_checkbox = QCheckBox("Auto-format on save")
        self.formatting_auto_format_checkbox.toggled.connect(self._emit_preferences_changed)
        frame_layout.addWidget(self.formatting_auto_format_checkbox)
        return page

    def _build_appearance_dirty_state_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "appearanceDirtyStatePage",
            "Dirty State",
            "Adjust the colors used to mark unsaved changes and tab attention.",
        )
        self.dirty_state_table_container = self._build_dirty_state_table_api_table(
            "dirtyStateStyleTable",
            self._dirty_state_style_fields,
        )
        frame_layout.addWidget(self.dirty_state_table_container)

        attention_group = QGroupBox("Workspace tab attention")
        attention_group.setStyleSheet(
            "QGroupBox {"
            " background-color: #ffffff;"
            " border: 1px solid #c7cdd4;"
            " border-radius: 8px;"
            " margin-top: 10px;"
            " font-weight: 600;"
            " }"
            "QGroupBox::title {"
            " subcontrol-origin: margin;"
            " left: 10px;"
            " padding: 0 4px;"
            " color: #202020;"
            " }"
        )
        attention_layout = QFormLayout(attention_group)
        attention_layout.setContentsMargins(10, 12, 10, 10)
        attention_layout.setHorizontalSpacing(10)
        attention_layout.setVerticalSpacing(8)

        self.workspace_tab_attention_enabled_checkbox = QCheckBox(
            "Enable attention highlight for visible tabs"
        )
        self.workspace_tab_attention_enabled_checkbox.setToolTip(
            "When enabled, visible tabs that receive new output while unfocused get a highlight."
        )
        self.workspace_tab_attention_enabled_checkbox.setChecked(True)
        self.workspace_tab_attention_enabled_checkbox.toggled.connect(
            self._emit_preferences_changed
        )

        self.workspace_tab_attention_color_swatch = ColorSwatchButton(
            self._workspace_tab_attention_default_color
        )
        self.workspace_tab_attention_color_swatch.colorChanged.connect(
            self._emit_preferences_changed
        )

        attention_layout.addRow(self.workspace_tab_attention_enabled_checkbox)
        attention_layout.addRow("Attention color", self.workspace_tab_attention_color_swatch)
        attention_note = QLabel(
            "Only visible tabs that are not currently focused will get this highlight."
        )
        attention_note.setWordWrap(True)
        attention_note.setStyleSheet("color: #666666;")
        attention_layout.addRow(attention_note)
        frame_layout.addWidget(attention_group)
        return page

    def _build_workspace_tabs_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "workspaceTabsPage",
            "Layout",
            "Choose which workspace tabs are shown when the app opens.",
        )
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addStretch(1)
        tabs_reset_button = QPushButton("Restore Layout Defaults")
        tabs_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        tabs_reset_button.setFlat(True)
        tabs_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        tabs_reset_button.clicked.connect(self.reset_workspace_tabs_settings_to_defaults)
        header.addWidget(tabs_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addLayout(header, 0)

        self.show_summary_sidebar_checkbox = QCheckBox("Show summary sidebar on the left")
        self.show_summary_sidebar_checkbox.setToolTip(
            "Show or hide the summary sidebar on the left side of the workspace."
        )
        self.show_summary_sidebar_checkbox.setChecked(True)
        self.show_summary_sidebar_checkbox.toggled.connect(self._emit_preferences_changed)
        frame_layout.addWidget(self.show_summary_sidebar_checkbox)

        self.hidden_workspace_tabs_strip_collapsed_checkbox = QCheckBox(
            "Collapse hidden tab selections strip"
        )
        self.hidden_workspace_tabs_strip_collapsed_checkbox.setToolTip(
            "Enabled by default. Start with the hidden tab selections strip collapsed whenever hidden tabs exist."
        )
        self.hidden_workspace_tabs_strip_collapsed_checkbox.setChecked(True)
        self.hidden_workspace_tabs_strip_collapsed_checkbox.toggled.connect(
            self._emit_preferences_changed
        )
        frame_layout.addWidget(self.hidden_workspace_tabs_strip_collapsed_checkbox)

        self.show_analysis_tab_checkbox = QCheckBox("Show Analysis tab")
        self.show_analysis_tab_checkbox.setToolTip(
            "Show or hide the Analysis tab in the workspace."
        )
        self.show_analysis_tab_checkbox.setChecked(False)
        self.show_analysis_tab_checkbox.toggled.connect(
            self._sync_analysis_tab_visibility_toggled
        )
        frame_layout.addWidget(self.show_analysis_tab_checkbox)

        self.show_formatted_preview_checkbox = QCheckBox("Show formatted preview tab")
        self.show_formatted_preview_checkbox.setToolTip(
            "Show or hide the formatted preview tab in the workspace."
        )
        self.show_formatted_preview_checkbox.setChecked(True)
        self.show_formatted_preview_checkbox.toggled.connect(self._emit_preferences_changed)
        frame_layout.addWidget(self.show_formatted_preview_checkbox)

        self.show_raw_recordings_checkbox = QCheckBox("Show raw recordings tab")
        self.show_raw_recordings_checkbox.setToolTip(
            "Show or hide the Raw Recordings tab in the workspace."
        )
        self.show_raw_recordings_checkbox.setChecked(False)
        self.show_raw_recordings_checkbox.toggled.connect(self._emit_preferences_changed)
        frame_layout.addWidget(self.show_raw_recordings_checkbox)

        self.show_diagnostics_checkbox = QCheckBox("Show diagnostics tab")
        self.show_diagnostics_checkbox.setToolTip(
            "Show or hide the Diagnostics tab in the workspace."
        )
        self.show_diagnostics_checkbox.setChecked(False)
        self.show_diagnostics_checkbox.toggled.connect(
            self._sync_diagnostics_tab_visibility_toggled
        )
        frame_layout.addWidget(self.show_diagnostics_checkbox)

        note = QLabel("These options control whether matching workspace tabs are shown or hidden.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)
        return page

    def _build_search_results_controls(self) -> None:
        if hasattr(self, "search_results_header_active_color"):
            return
        self.search_results_header_active_color = ColorSwatchButton("#d7e9ff")
        self.search_results_header_hovered_color = ColorSwatchButton("#e0efff")
        self.search_results_header_active_hovered_color = ColorSwatchButton("#b9d9ff")
        self.search_results_header_text_color = ColorSwatchButton("#666666")
        self.search_results_line_text_color = ColorSwatchButton("#222222")
        self.search_results_hit_text_color = ColorSwatchButton("#666666")
        self.search_results_child_border_color = ColorSwatchButton("#8fb6e8")
        self.search_results_header_radius_edit = QLineEdit("4px")
        self.search_results_header_padding_edit = QLineEdit("1px 4px")
        self.search_results_child_border_width_edit = QLineEdit("2px")
        self.search_results_child_padding_left_spin = QSpinBox()
        self.search_results_child_padding_left_spin.setRange(0, 64)
        self.search_results_child_padding_left_spin.setValue(8)
        self.search_results_child_margin_left_spin = QSpinBox()
        self.search_results_child_margin_left_spin.setRange(0, 64)
        self.search_results_child_margin_left_spin.setValue(4)

        for widget in (
            self.search_results_header_active_color,
            self.search_results_header_hovered_color,
            self.search_results_header_active_hovered_color,
            self.search_results_header_text_color,
            self.search_results_line_text_color,
            self.search_results_hit_text_color,
            self.search_results_child_border_color,
        ):
            widget.colorChanged.connect(self._emit_preferences_changed)
        for widget in (
            self.search_results_header_radius_edit,
            self.search_results_header_padding_edit,
            self.search_results_child_border_width_edit,
        ):
            widget.textChanged.connect(self._emit_preferences_changed)
        self.search_results_child_padding_left_spin.valueChanged.connect(self._emit_preferences_changed)
        self.search_results_child_margin_left_spin.valueChanged.connect(self._emit_preferences_changed)

    def _build_workspace_search_results_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "workspaceSearchResultsPage",
            "Search Results",
            "Adjust the colors used in the search results tree.",
        )
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addStretch(1)
        search_results_reset_button = QPushButton("Reset Search Results")
        search_results_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        search_results_reset_button.setFlat(True)
        search_results_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        search_results_reset_button.clicked.connect(self.reset_search_results_settings_to_defaults)
        header.addWidget(search_results_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addLayout(header, 0)

        self._build_search_results_controls()

        def build_group_box(
            title: str,
            rows: list[tuple[str, QWidget]],
            *,
            columns: int = 1,
        ) -> QGroupBox:
            group_box = QGroupBox(title)
            group_box.setStyleSheet(
                "QGroupBox {"
                " background-color: #ffffff;"
                " border: 1px solid #c7cdd4;"
                " border-radius: 8px;"
                " margin-top: 10px;"
                " font-weight: 600;"
                " }"
                "QGroupBox::title {"
                " subcontrol-origin: margin;"
                " left: 10px;"
                " padding: 0 4px;"
                " color: #202020;"
                " }"
            )
            group_layout = QGridLayout(group_box)
            group_layout.setContentsMargins(10, 12, 10, 10)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(6)
            for index, (label_text, widget) in enumerate(rows):
                row_index = index if columns == 1 else index // columns
                column_offset = 0 if columns == 1 else (index % columns) * 2
                label = QLabel(label_text)
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                label.setStyleSheet("color: #444444;")
                group_layout.addWidget(label, row_index, column_offset)
                group_layout.addWidget(widget, row_index, column_offset + 1)
            for column in range(columns * 2):
                group_layout.setColumnStretch(column, 1 if column % 2 == 1 else 0)
            return group_box

        color_group = build_group_box(
            "Colors",
            [
                ("Active header", self.search_results_header_active_color),
                ("Hovered header", self.search_results_header_hovered_color),
                ("Active + hovered", self.search_results_header_active_hovered_color),
                ("Header text", self.search_results_header_text_color),
                ("Line text", self.search_results_line_text_color),
                ("Hit text", self.search_results_hit_text_color),
                ("Child border", self.search_results_child_border_color),
            ],
            columns=2,
        )

        frame_layout.addWidget(color_group)

        note = QLabel(
            "These settings control how search results are highlighted in the tree."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)
        return page

    def _build_workspace_search_spacing_page(self) -> QWidget:
        page, _page_layout, frame_layout = self._build_section_page(
            "workspaceSearchSpacingPage",
            "Search Spacing",
            "Adjust the spacing used in the search results tree.",
        )
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addStretch(1)
        search_spacing_reset_button = QPushButton("Reset Search Spacing")
        search_spacing_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        search_spacing_reset_button.setFlat(True)
        search_spacing_reset_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        search_spacing_reset_button.clicked.connect(self.reset_search_spacing_settings_to_defaults)
        header.addWidget(search_spacing_reset_button, 0, alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addLayout(header, 0)

        self._build_search_results_controls()

        def build_group_box(
            title: str,
            rows: list[tuple[str, QWidget]],
        ) -> QGroupBox:
            group_box = QGroupBox(title)
            group_box.setStyleSheet(
                "QGroupBox {"
                " background-color: #ffffff;"
                " border: 1px solid #c7cdd4;"
                " border-radius: 8px;"
                " margin-top: 10px;"
                " font-weight: 600;"
                " }"
                "QGroupBox::title {"
                " subcontrol-origin: margin;"
                " left: 10px;"
                " padding: 0 4px;"
                " color: #202020;"
                " }"
            )
            group_layout = QGridLayout(group_box)
            group_layout.setContentsMargins(10, 12, 10, 10)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(6)
            for row_index, (label_text, widget) in enumerate(rows):
                label = QLabel(label_text)
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                label.setStyleSheet("color: #444444;")
                group_layout.addWidget(label, row_index, 0)
                group_layout.addWidget(widget, row_index, 1)
            group_layout.setColumnStretch(0, 0)
            group_layout.setColumnStretch(1, 1)
            return group_box

        spacing_group = build_group_box(
            "Spacing",
            [
                ("Header radius", self.search_results_header_radius_edit),
                ("Header padding", self.search_results_header_padding_edit),
                ("Child border width", self.search_results_child_border_width_edit),
                ("Child padding left", self.search_results_child_padding_left_spin),
                ("Child margin left", self.search_results_child_margin_left_spin),
            ],
        )
        frame_layout.addWidget(spacing_group)

        note = QLabel(
            "These settings control indentation and padding in the search results tree."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        frame_layout.addWidget(note)
        return page

    def add_typography_row(self, label: str, widget: QWidget) -> None:
        # Keep typography registration centralized so new rows can be appended
        # from one place without changing the table construction logic.
        self.typography_rows.append((label, widget))

    def _build_typography_table(self, rows: list[tuple[str, QWidget]]) -> QTableWidget:
        model = PreferencesTableModel(
            table_name="typographyTable",
            columns=[
                TableColumnSpec("Typography Setting", "stretch"),
                TableColumnSpec("Value", "contents"),
            ],
            rows=[],
        )
        table = self._build_preferences_table_shell(model, row_count=len(rows))

        for row_index, (label, widget) in enumerate(rows):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_index, 0, item)
            table.setCellWidget(row_index, 1, widget)

        return table

    def _build_color_style_table(
        self,
        table_name: str,
        fields: list[tuple[str, str, str, str]],
        controls: dict[str, ColorSwatchButton],
        *,
        row_label: str,
    ) -> QTableWidget:
        model = PreferencesTableModel(
            table_name=table_name,
            columns=[
                TableColumnSpec(row_label, "stretch"),
                TableColumnSpec("Type", "contents"),
                TableColumnSpec("Value", "stretch"),
            ],
            rows=[],
        )
        table = self._build_preferences_table_shell(model, row_count=len(fields))

        for row, (label, field_name, column_name, default_color) in enumerate(fields):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, item)

            type_item = QTableWidgetItem(column_name.title())
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            type_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(row, 1, type_item)

            button = ColorSwatchButton(default_color)
            button.colorChanged.connect(self._emit_preferences_changed)
            controls[field_name] = button
            table.setCellWidget(row, 2, button)

        return table

    def _apply_color_swatches(
        self,
        controls: dict[str, ColorSwatchButton],
        values: dict[str, str],
    ) -> None:
        for field_name, color in values.items():
            control = controls.get(field_name)
            if control is not None:
                control.setColor(color)

    def _editor_style_values(self, editor: EditorAppearanceTheme) -> dict[str, str]:
        return {
            "editor_background": editor.background,
            "editor_text": editor.text,
            "gutter_background": editor.gutter_background,
            "gutter_text": editor.gutter_text,
            "current_line_foreground": editor.current_line_foreground,
            "current_line_highlight": editor.current_line_highlight,
        }

    def _editor_style_values_from_widgets(self) -> dict[str, str]:
        return {field_name: color.lower() for field_name, color in self._editor_style_data.items()}

    def _dirty_indicator_values(self, dirty: DirtyIndicatorTheme) -> dict[str, str]:
        return {
            "dirty_text": dirty.text,
            "dirty_accent": dirty.accent,
            "dirty_background": dirty.background,
            "dirty_selected_background": dirty.selected_background,
            "dirty_border": dirty.border,
        }

    def _dirty_indicator_values_from_model(self) -> dict[str, str]:
        if not hasattr(self, "dirty_state_model"):
            return {
                field_name: default_color
                for _label, field_name, _column_name, default_color in self._dirty_state_style_fields
            }
        return {
            "dirty_text": str(
                self.dirty_state_model.index(0, 1).data(Qt.ItemDataRole.DisplayRole) or "#7a4a00"
            ).lower(),
            "dirty_background": str(
                self.dirty_state_model.index(0, 2).data(Qt.ItemDataRole.DisplayRole) or "#fff5e3"
            ).lower(),
            "dirty_accent": str(
                self.dirty_state_model.index(1, 1).data(Qt.ItemDataRole.DisplayRole) or "#8b6a2f"
            ).lower(),
            "dirty_selected_background": str(
                self.dirty_state_model.index(2, 2).data(Qt.ItemDataRole.DisplayRole) or "#f0ddb4"
            ).lower(),
            "dirty_border": str(
                self.dirty_state_model.index(3, 2).data(Qt.ItemDataRole.DisplayRole) or "#ead8b6"
            ).lower(),
        }

    def _style_values(self, syntax: SyntaxHighlightTheme) -> dict[str, str]:
        return {
            "keyword": syntax.keyword,
            "string": syntax.string,
            "comment": syntax.comment,
            "number": syntax.number,
        }

    def _style_table_rows(self, values: dict[str, str]) -> list[dict[str, object]]:
        return [
            {
                "setting": label,
                "color": color_cell_value(values.get(field_name, default_color)),
            }
            for label, field_name, default_color in self._style_fields
        ]

    def _set_style_values(self, values: dict[str, str]) -> None:
        if hasattr(self, "style_model"):
            self.style_model.set_rows(self._style_table_rows(values))

    def _default_editor_style_values(self) -> dict[str, str]:
        return {
            field_name: default_color
            for _label, foreground_field, background_field, foreground_default, background_default in self._appearance_style_fields
            for field_name, default_color in (
                (foreground_field, foreground_default),
                (background_field, background_default),
            )
        }

    def _editor_style_table_rows(self, values: dict[str, str]) -> list[dict[str, object]]:
        return [
            {
                "setting": label,
                "foreground": color_cell_value(
                    values.get(foreground_field, foreground_default)
                ),
                "background": color_cell_value(values.get(background_field, background_default)),
            }
            for (
                label,
                foreground_field,
                background_field,
                foreground_default,
                background_default,
            ) in self._appearance_style_fields
        ]

    def _build_table_api_style_table(
        self,
        table_name: str,
        fields: list[tuple[str, str, str, str]],
        rows: list[dict[str, object]] | None = None,
    ) -> QTableView:
        headers = [
            ColumnSpec(
                name="setting",
                label="Setting",
                editable=False,
                width_mode="stretch",
            ),
            ColumnSpec(
                name="foreground",
                label="Foreground",
                editable=True,
                width_mode="fixed",
                fixed_width=120,
            ),
            ColumnSpec(
                name="background",
                label="Background",
                editable=True,
                width_mode="fixed",
                fixed_width=120,
            ),
        ]
        if rows is None:
            rows = [
                {
                    "setting": label,
                    "foreground": (
                        color_cell_value(default_color)
                        if column_name == "foreground"
                        else ""
                    ),
                    "background": (
                        color_cell_value(default_color)
                        if column_name == "background"
                        else ""
                    ),
                }
                for label, _field_name, column_name, default_color in fields
            ]
        model = self._table_api.create_model(headers, rows)
        self._wire_preferences_table_model(model)
        view = self._table_api.create_view(model)
        view.setObjectName(table_name)
        view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setAlternatingRowColors(True)
        view.setShowGrid(True)
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(34)
        view.verticalHeader().setMinimumSectionSize(34)
        view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        view.horizontalHeader().setVisible(False)
        color_delegate = ColorCellDelegate(self._on_appearance_style_color_changed, view)
        self._appearance_color_delegate = color_delegate
        view.setItemDelegateForColumn(1, color_delegate)
        view.setItemDelegateForColumn(2, color_delegate)
        view.setStyleSheet(
            "QTableView {"
            " background-color: #ffffff;"
            " border: 0;"
            " gridline-color: #d6dbe2;"
            " }"
            "QTableView::item {"
            " padding: 2px 8px;"
            " }"
        )
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame {"
            " background-color: #ffffff;"
            " border: 1px solid #c7cdd4;"
            " }"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(
            self._table_api.create_header_strip(
                headers,
                container,
                text_color="#202020",
                background_color="#e9edf2",
                border_color="#c7cdd4",
                padding="3px 8px",
                font_size=11,
                bold=True,
            )
        )
        container_layout.addWidget(view)
        self.appearance_style_model = model
        return container

    def _build_table_api_color_table(
        self,
        table_name: str,
        fields: list[tuple[str, str, str]],
    ) -> QWidget:
        headers = [
            ColumnSpec(
                name="setting",
                label="Setting",
                editable=False,
                width_mode="stretch",
            ),
            ColumnSpec(
                name="color",
                label="Foreground",
                editable=True,
                width_mode="fixed",
                fixed_width=132,
            ),
        ]
        rows: list[dict[str, object]] = [
            {
                "setting": label,
                "color": color_cell_value(default_color),
            }
            for label, _field_name, default_color in fields
        ]
        model = self._table_api.create_model(headers, rows)
        self._wire_preferences_table_model(model)
        view = self._table_api.create_view(model)
        view.setObjectName(table_name)
        view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setAlternatingRowColors(True)
        view.setShowGrid(True)
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(34)
        view.verticalHeader().setMinimumSectionSize(34)
        view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        view.horizontalHeader().setVisible(False)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setStyleSheet(
            "QTableView {"
            " background-color: #ffffff;"
            " border: 0;"
            " gridline-color: #d6dbe2;"
            " }"
            "QTableView::item {"
            " padding: 3px 8px;"
            " }"
        )
        color_delegate = ColorCellDelegate(self._on_style_color_changed, view)
        self._style_color_delegate = color_delegate
        view.setItemDelegateForColumn(1, color_delegate)

        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame {"
            " background-color: #ffffff;"
            " border: 1px solid #c7cdd4;"
            " }"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        header_strip = self._table_api.create_header_strip(
            headers,
            container,
            text_color="#202020",
            background_color="#e9edf2",
            border_color="#c7cdd4",
            padding="2px 8px",
            font_size=11,
            bold=True,
        )
        header_strip.setObjectName(f"{table_name}HeaderStrip")
        container_layout.addWidget(header_strip)
        container_layout.addWidget(view)
        self.style_model = model
        self.style_table = view
        return container

    def _set_editor_style_values(self, values: dict[str, str]) -> None:
        editor_style_data: dict[str, str] = {}
        for (
            _label,
            foreground_field,
            background_field,
            foreground_default,
            background_default,
        ) in self._appearance_style_fields:
            if foreground_field is not None:
                editor_style_data[foreground_field] = values.get(
                    foreground_field,
                    foreground_default,
                )
            if background_field is not None:
                editor_style_data[background_field] = values.get(
                    background_field,
                    background_default,
                )
        self._editor_style_data = editor_style_data
        if hasattr(self, "appearance_style_model"):
            self.appearance_style_model.set_rows(self._editor_style_table_rows(self._editor_style_data))

    def _on_appearance_style_color_changed(self, row: int, column: int, color: str) -> None:
        if self._loading_preferences:
            return
        if not (0 <= row < len(self._appearance_style_fields)):
            return
        (
            _label,
            foreground_field,
            background_field,
            _foreground_default,
            _background_default,
        ) = self._appearance_style_fields[row]
        field_name = foreground_field if column == 1 else background_field if column == 2 else None
        if field_name is not None:
            self._editor_style_data[field_name] = color.lower()
        self._emit_preferences_changed()

    def _build_dirty_state_table_api_table(
        self,
        table_name: str,
        fields: list[tuple[str, str, str, str]],
    ) -> QWidget:
        headers = [
            ColumnSpec(
                name="setting",
                label="Setting",
                editable=False,
                width_mode="stretch",
            ),
            ColumnSpec(
                name="foreground",
                label="Foreground",
                editable=True,
                width_mode="fixed",
                fixed_width=120,
            ),
            ColumnSpec(
                name="background",
                label="Background",
                editable=True,
                width_mode="fixed",
                fixed_width=120,
            ),
        ]
        rows = self._dirty_state_rows_from_values(self._dirty_indicator_values(DirtyIndicatorTheme()))
        model = self._table_api.create_model(headers, rows)
        self._wire_preferences_table_model(model)
        view = self._table_api.create_view(model)
        view.setObjectName(table_name)
        view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setAlternatingRowColors(True)
        view.setShowGrid(True)
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(34)
        view.verticalHeader().setMinimumSectionSize(34)
        view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        view.horizontalHeader().setVisible(False)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setStyleSheet(
            "QTableView {"
            " background-color: #ffffff;"
            " border: 0;"
            " gridline-color: #d6dbe2;"
            " }"
            "QTableView::item {"
            " padding: 3px 8px;"
            " }"
        )
        color_delegate = ColorCellDelegate(self._on_dirty_state_color_changed, view)
        self._dirty_state_color_delegate = color_delegate
        view.setItemDelegateForColumn(1, color_delegate)
        view.setItemDelegateForColumn(2, color_delegate)

        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame {"
            " background-color: #ffffff;"
            " border: 1px solid #c7cdd4;"
            " }"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        header_strip = self._table_api.create_header_strip(
            headers,
            container,
            text_color="#202020",
            background_color="#e9edf2",
            border_color="#c7cdd4",
            padding="3px 8px",
            font_size=11,
            bold=True,
        )
        header_strip.setObjectName(f"{table_name}HeaderStrip")
        container_layout.addWidget(header_strip)
        container_layout.addWidget(view)
        self.dirty_state_model = model
        self.dirty_state_table = view
        self.dirty_indicator_text_row = TableModelColorRow(
            model,
            0,
            1,
            self._emit_preferences_changed,
        )
        self.dirty_indicator_accent_row = TableModelColorRow(
            model,
            1,
            1,
            self._emit_preferences_changed,
        )
        self.dirty_indicator_text_background_row = TableModelColorRow(
            model,
            0,
            2,
            self._emit_preferences_changed,
        )
        self.dirty_indicator_selected_background_row = TableModelColorRow(
            model,
            2,
            2,
            self._emit_preferences_changed,
        )
        self.dirty_indicator_border_row = TableModelColorRow(
            model,
            3,
            2,
            self._emit_preferences_changed,
        )
        return container

    def _set_dirty_state_values(self, values: dict[str, str]) -> None:
        if not hasattr(self, "dirty_state_model"):
            return
        self.dirty_state_model.set_rows(self._dirty_state_rows_from_values(values))

    def _on_dirty_state_color_changed(self, row: int, column: int, color: str) -> None:
        if self._loading_preferences:
            return
        if not (0 <= row < len(self._dirty_state_style_fields)):
            return
        _label, field_name, _column_name, _default_color = self._dirty_state_style_fields[row]
        _ = field_name
        _ = column
        _ = color
        self._emit_preferences_changed()

    def _dirty_state_rows_from_values(self, values: dict[str, str]) -> list[dict[str, object]]:
        return [
            {
                "setting": "Text",
                "foreground": color_cell_value(values.get("dirty_text", "#7a4a00")),
                "background": color_cell_value(values.get("dirty_background", "#fff5e3")),
            },
            {
                "setting": "Accent",
                "foreground": color_cell_value(values.get("dirty_accent", "#8b6a2f")),
                "background": "",
            },
            {
                "setting": "Selected area",
                "foreground": "",
                "background": color_cell_value(values.get("dirty_selected_background", "#f0ddb4")),
            },
            {
                "setting": "Border",
                "foreground": "",
                "background": color_cell_value(values.get("dirty_border", "#ead8b6")),
            },
        ]

    def _build_placeholder_tab(self, title: str, note: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        label = QLabel(note)
        label.setWordWrap(True)
        label.setStyleSheet("color: #666666;")
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _build_preferences_table_shell(
        self,
        model: PreferencesTableModel,
        row_count: int | None = None,
    ) -> QTableWidget:
        table = QTableWidget(row_count if row_count is not None else len(model.rows), len(model.columns))
        table.setObjectName(model.table_name)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setVisible(True)
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        table.setHorizontalHeaderLabels([column.title for column in model.columns])
        for index, column in enumerate(model.columns):
            if column.width_mode == "stretch":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            elif column.width_mode == "fixed":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                if column.fixed_width is not None:
                    table.setColumnWidth(index, column.fixed_width)
            elif column.width_mode == "contents":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
            else:
                raise ValueError(f"Unsupported width mode: {column.width_mode}")
        return table

    def _build_general_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "General",
            "Startup preferences for restoring the last workspace.",
            actions=[("Restore All Defaults", self.reset_all_settings_to_defaults)],
        )

        general_frame = QFrame()
        general_frame.setFrameShape(QFrame.Shape.StyledPanel)
        general_frame.setStyleSheet("QFrame { padding: 8px; }")
        general_layout = QVBoxLayout(general_frame)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(12)

        startup_title = QLabel("Startup")
        startup_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        general_layout.addWidget(startup_title)

        startup_note = QLabel(
            "This section only controls whether the last workspace reopens when the app starts."
        )
        startup_note.setWordWrap(True)
        startup_note.setStyleSheet("color: #666666;")
        general_layout.addWidget(startup_note)

        self.restore_workspace_checkbox = QCheckBox("Restore the last opened workspace at startup")
        self.restore_workspace_checkbox.toggled.connect(self._emit_preferences_changed)
        general_layout.addWidget(self.restore_workspace_checkbox)
        general_layout.addStretch(1)

        layout.insertWidget(1, general_frame)
        return page

    def _build_hotkeys_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Hotkeys",
            "Assign keyboard shortcuts for app actions and editor commands.",
            actions=[("Restore Defaults", self.reset_hotkeys_settings_to_defaults)],
        )
        self.hotkeys_search = QLineEdit()
        self.hotkeys_search.setPlaceholderText("Search actions or shortcuts")
        self.hotkeys_search.setClearButtonEnabled(True)
        self.hotkeys_search.textChanged.connect(self._on_hotkeys_search_changed)
        hotkeys_columns = [
            ColumnSpec(name="action", label="Action", editable=False, width_mode="stretch"),
            ColumnSpec(
                name="shortcut",
                label="Shortcut",
                editor="keysequence",
                delegate_key="keysequence",
                editable=True,
                width_mode="fixed",
                fixed_width=180,
            ),
            ColumnSpec(
                name="note",
                label="Note",
                editable=False,
                width_mode="stretch",
                default_style=CellStyle(color="#8a5a00"),
            ),
            ColumnSpec(
                name="reset",
                label="Reset",
                delegate_key="action",
                editable=False,
                width_mode="fixed",
                fixed_width=72,
                default_style=CellStyle(color="#0b57d0", underline=True),
            ),
        ]
        self._hotkey_default_sequences = default_hotkey_bindings()
        self._table_api.register_delegate(
            "action",
            lambda parent, _column: ActionCellDelegate(
                self._on_hotkeys_reset_activated,
                parent,
            ),
        )
        self._hotkey_row_by_action_id: dict[str, int] = {}
        hotkey_rows: list[dict[str, object]] = []
        for row, definition in enumerate(HOTKEY_DEFINITIONS):
            self._hotkey_row_by_action_id[definition.action_id] = row
            hotkey_rows.append(
                {
                    "action": definition.label,
                    "shortcut": self._hotkey_default_sequences.get(definition.action_id, ""),
                    "note": definition.help_text,
                    "reset": "Reset",
                }
            )
        hotkeys_model = self._table_api.create_model(hotkeys_columns, hotkey_rows)
        self._hotkeys_model = hotkeys_model
        self.hotkeys_table = self._table_api.create_view(hotkeys_model, page)
        self.hotkeys_table.setObjectName("hotkeysTable")
        self._hotkey_shortcut_delegate = KeySequenceDelegate(
            parent=self.hotkeys_table,
            text_row_predicate=lambda index, stop_row=self._hotkey_row_by_action_id["stop"]: index.row()
            == stop_row,
        )
        self.hotkeys_table.setItemDelegateForColumn(1, self._hotkey_shortcut_delegate)
        self.hotkeys_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.hotkeys_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.hotkeys_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hotkeys_table.setAlternatingRowColors(True)
        self.hotkeys_table.setShowGrid(True)
        self.hotkeys_table.setWordWrap(False)
        self.hotkeys_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.hotkeys_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hotkeys_table.verticalHeader().setVisible(False)
        self.hotkeys_table.horizontalHeader().setVisible(False)
        hotkeys_model.dataChanged.connect(self._on_hotkeys_model_changed)
        layout.insertWidget(1, self.hotkeys_search)
        layout.insertWidget(
            2,
            self._table_api.create_header_strip(
                hotkeys_model.columns(),
                page,
                text_color="#202020",
                background_color="#e9edf2",
                border_color="#c7cdd4",
                padding="3px 8px",
                font_size=11,
                bold=True,
            ),
        )
        layout.insertWidget(3, self.hotkeys_table)
        self.hotkeys_warning_label = QLabel()
        self.hotkeys_warning_label.setWordWrap(True)
        self.hotkeys_warning_label.setStyleSheet("color: #a15c00; font-weight: 600;")
        self.hotkeys_warning_label.setVisible(False)
        layout.insertWidget(4, self.hotkeys_warning_label)
        self._apply_hotkeys_search_text()
        return page

    def _build_playback_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Playback",
            "Set playback repeat, stepping, delay, and mouse-settle defaults.",
            actions=[("Restore Defaults", self.reset_playback_settings_to_defaults)],
        )

        playback_frame = QFrame()
        playback_frame.setFrameShape(QFrame.Shape.StyledPanel)
        playback_frame.setStyleSheet("QFrame { padding: 8px; }")
        playback_layout = QFormLayout(playback_frame)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setHorizontalSpacing(12)
        playback_layout.setVerticalSpacing(10)

        self.playback_repeat_spin = QSpinBox()
        self.playback_repeat_spin.setRange(1, 1000)
        self.playback_repeat_spin.setValue(1)
        self.playback_repeat_spin.valueChanged.connect(self._emit_preferences_changed)

        self.playback_step_checkbox = QCheckBox("Pause before each playback event")
        self.playback_step_checkbox.toggled.connect(self._emit_preferences_changed)

        self.playback_send_key_taps_checkbox = QCheckBox(
            "Send key taps instead of text"
        )
        self.playback_send_key_taps_checkbox.toggled.connect(self._emit_preferences_changed)

        self.playback_delay_spin = QSpinBox()
        self.playback_delay_spin.setRange(0, 60000)
        self.playback_delay_spin.setSuffix(" ms")
        self.playback_delay_spin.setValue(0)
        self.playback_delay_spin.valueChanged.connect(self._emit_preferences_changed)

        self.playback_mouse_settle_spin = QSpinBox()
        self.playback_mouse_settle_spin.setRange(0, 10000)
        self.playback_mouse_settle_spin.setSuffix(" ms")
        self.playback_mouse_settle_spin.setValue(0)
        self.playback_mouse_settle_spin.valueChanged.connect(self._emit_preferences_changed)

        self.playback_interruptible_sleep_chunk_spin = QSpinBox()
        self.playback_interruptible_sleep_chunk_spin.setRange(1, 1000)
        self.playback_interruptible_sleep_chunk_spin.setSuffix(" ms")
        self.playback_interruptible_sleep_chunk_spin.setValue(50)
        self.playback_interruptible_sleep_chunk_spin.setToolTip(
            "Smaller values stop playback faster, but check for the stop key more often."
        )
        self.playback_interruptible_sleep_chunk_spin.valueChanged.connect(
            self._emit_preferences_changed
        )

        playback_layout.addRow("Repeat count", self.playback_repeat_spin)
        playback_layout.addRow("", self.playback_step_checkbox)
        playback_layout.addRow("", self.playback_send_key_taps_checkbox)
        playback_layout.addRow("Delay before each event", self.playback_delay_spin)
        playback_layout.addRow("Mouse settle before clicks", self.playback_mouse_settle_spin)
        playback_layout.addRow(
            "Interruptible sleep chunk",
            self.playback_interruptible_sleep_chunk_spin,
        )

        playback_hint = QLabel(
            "Repeat count sets how many times playback runs. Step mode pauses before each "
            "event, delay adds time before events, mouse settle gives the pointer time to "
            "stop before clicks, interruptible sleep chunk controls how often playback "
            "checks for the stop hotkey, and key taps can help emulators like DOSBox."
        )
        playback_hint.setWordWrap(True)
        playback_hint.setStyleSheet("color: #666666;")

        layout.insertWidget(1, playback_frame)
        layout.insertWidget(2, playback_hint)
        layout.addStretch(1)
        return page

    def _build_recording_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Recording",
            "Choose which raw input events are captured and how a recording becomes a script.",
            actions=[("Restore Defaults", self.reset_recording_settings_to_defaults)],
        )

        self.recording_capture_mouse_moves_checkbox = QCheckBox("Capture mouse moves")
        self.recording_capture_mouse_moves_checkbox.setChecked(True)
        self.recording_capture_mouse_moves_checkbox.toggled.connect(self._emit_preferences_changed)

        self.recording_capture_mouse_buttons_checkbox = QCheckBox("Capture mouse buttons")
        self.recording_capture_mouse_buttons_checkbox.setChecked(True)
        self.recording_capture_mouse_buttons_checkbox.toggled.connect(self._emit_preferences_changed)

        self.recording_capture_mouse_wheel_checkbox = QCheckBox("Capture mouse wheel")
        self.recording_capture_mouse_wheel_checkbox.setChecked(True)
        self.recording_capture_mouse_wheel_checkbox.toggled.connect(self._emit_preferences_changed)

        self.recording_capture_keyboard_checkbox = QCheckBox("Capture keyboard")
        self.recording_capture_keyboard_checkbox.setChecked(True)
        self.recording_capture_keyboard_checkbox.toggled.connect(self._emit_preferences_changed)

        self.recording_exclude_main_window_checkbox = QCheckBox(
            "Exclude main window during recording"
        )
        self.recording_exclude_main_window_checkbox.setChecked(True)
        self.recording_exclude_main_window_checkbox.setToolTip(
            "Keep the desktop workbench window out of the recording so you only capture the target app."
        )
        self.recording_exclude_main_window_checkbox.toggled.connect(
            self._emit_preferences_changed
        )

        self.recording_conversion_mode_combo = QComboBox()
        self.recording_conversion_mode_combo.addItem("Promote Generated Script", "promote_generated")
        self.recording_conversion_mode_combo.addItem("Direct Import", "direct_import")
        self.recording_conversion_mode_combo.currentIndexChanged.connect(
            self._emit_preferences_changed
        )

        self.recording_mouse_move_threshold_spin = QSpinBox()
        self.recording_mouse_move_threshold_spin.setRange(0, 10_000)
        self.recording_mouse_move_threshold_spin.setSuffix(" px")
        self.recording_mouse_move_threshold_spin.setValue(0)
        self.recording_mouse_move_threshold_spin.valueChanged.connect(self._emit_preferences_changed)

        recording_hint = QLabel(
            "These settings control which input types are recorded. Conversion mode chooses "
            "how a stopped recording becomes the active script."
        )
        recording_hint.setWordWrap(True)
        recording_hint.setStyleSheet("color: #666666;")

        capture_frame = QFrame()
        self.recording_capture_tab = capture_frame
        capture_frame.setFrameShape(QFrame.Shape.StyledPanel)
        capture_frame.setStyleSheet("QFrame { padding: 8px; }")
        capture_layout = QFormLayout(capture_frame)
        capture_layout.setContentsMargins(0, 0, 0, 0)
        capture_layout.setSpacing(8)
        capture_layout.addRow("Capture mouse moves", self.recording_capture_mouse_moves_checkbox)
        capture_layout.addRow("Capture mouse buttons", self.recording_capture_mouse_buttons_checkbox)
        capture_layout.addRow("Capture mouse wheel", self.recording_capture_mouse_wheel_checkbox)
        capture_layout.addRow("Capture keyboard", self.recording_capture_keyboard_checkbox)
        capture_layout.addRow(
            "Exclude main window during recording",
            self.recording_exclude_main_window_checkbox,
        )
        capture_layout.addRow("Mouse move threshold", self.recording_mouse_move_threshold_spin)
        capture_layout.addRow("Recording conversion mode", self.recording_conversion_mode_combo)

        layout.insertWidget(1, capture_frame)
        layout.insertWidget(2, recording_hint)
        layout.addStretch(1)
        return page

    def _build_files_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Files",
            "Choose where raw recordings, converted scripts, and diagnostics logs are saved.",
            actions=[("Restore Defaults", self.reset_files_settings_to_defaults)],
        )

        self.recording_autosave_checkbox = QCheckBox("Save converted script automatically")
        self.recording_autosave_checkbox.setChecked(True)
        self.recording_autosave_checkbox.toggled.connect(self._on_recording_autosave_toggled)

        self.recording_autosave_file_name_edit = QLineEdit()
        self.recording_autosave_file_name_edit.setPlaceholderText("Base file name")
        self.recording_autosave_file_name_edit.setToolTip(
            "Base file name used when automatic saving is enabled."
        )
        self.recording_autosave_file_name_edit.setText("recording")
        self.recording_autosave_file_name_edit.textChanged.connect(self._emit_preferences_changed)
        self.recording_autosave_file_name_edit.textChanged.connect(
            lambda _text: self._update_file_output_previews()
        )

        self.recording_autosave_timestamp_checkbox = QCheckBox("Append timestamp suffix")
        self.recording_autosave_timestamp_checkbox.setChecked(True)
        self.recording_autosave_timestamp_checkbox.toggled.connect(self._emit_preferences_changed)
        self.recording_autosave_timestamp_checkbox.toggled.connect(
            lambda _checked: self._update_file_output_previews()
        )

        self.recording_autosave_folder_edit = QLineEdit()
        self.recording_autosave_folder_edit.setPlaceholderText(
            "Choose where converted scripts are saved"
        )
        self.recording_autosave_folder_edit.setText("recordings")
        self.recording_autosave_folder_edit.textChanged.connect(self._emit_preferences_changed)
        self.recording_autosave_folder_edit.textChanged.connect(
            lambda _text: self._update_file_output_previews()
        )

        self.recording_autosave_browse_button = QPushButton("Browse...")
        self.recording_autosave_browse_button.clicked.connect(
            self._choose_recording_autosave_folder
        )

        self.recording_raw_autosave_checkbox = QCheckBox("Save raw recording automatically")
        self.recording_raw_autosave_checkbox.setChecked(True)
        self.recording_raw_autosave_checkbox.toggled.connect(
            self._on_recording_raw_autosave_toggled
        )

        self.recording_raw_autosave_file_name_edit = QLineEdit()
        self.recording_raw_autosave_file_name_edit.setPlaceholderText("Base file name")
        self.recording_raw_autosave_file_name_edit.setToolTip(
            "Base file name used when automatic saving is enabled."
        )
        self.recording_raw_autosave_file_name_edit.setText("recording")
        self.recording_raw_autosave_file_name_edit.textChanged.connect(
            self._emit_preferences_changed
        )
        self.recording_raw_autosave_file_name_edit.textChanged.connect(
            lambda _text: self._update_file_output_previews()
        )

        self.recording_raw_autosave_timestamp_checkbox = QCheckBox("Append timestamp suffix")
        self.recording_raw_autosave_timestamp_checkbox.setChecked(True)
        self.recording_raw_autosave_timestamp_checkbox.toggled.connect(
            self._emit_preferences_changed
        )
        self.recording_raw_autosave_timestamp_checkbox.toggled.connect(
            lambda _checked: self._update_file_output_previews()
        )

        self.recording_raw_autosave_folder_edit = QLineEdit()
        self.recording_raw_autosave_folder_edit.setPlaceholderText(
            "Choose where raw recordings are saved"
        )
        self.recording_raw_autosave_folder_edit.setText("recordings")
        self.recording_raw_autosave_folder_edit.textChanged.connect(self._emit_preferences_changed)
        self.recording_raw_autosave_folder_edit.textChanged.connect(
            lambda _text: self._update_file_output_previews()
        )

        self.recording_raw_autosave_browse_button = QPushButton("Browse...")
        self.recording_raw_autosave_browse_button.clicked.connect(
            self._choose_recording_raw_autosave_folder
        )

        self.scripting_extension_edit = QLineEdit()
        self.scripting_extension_edit.setPlaceholderText("Script extension, for example .ass")
        self.scripting_extension_edit.setToolTip(
            "File extension used when saving converted scripts."
        )
        self.scripting_extension_edit.textChanged.connect(self._emit_preferences_changed)
        self.scripting_extension_edit.textChanged.connect(
            lambda _text: self._update_file_output_previews()
        )

        self.diagnostic_log_path_edit = QLineEdit()
        self.diagnostic_log_path_edit.setPlaceholderText("Use the default diagnostics log path")
        self.diagnostic_log_path_edit.setToolTip(
            "Leave blank to use the default diagnostics log path."
        )
        self.diagnostic_log_path_edit.textChanged.connect(self._emit_preferences_changed)
        self.diagnostic_log_path_edit.textChanged.connect(
            lambda _text: self._update_diagnostics_log_path_label()
        )

        self.diagnostic_log_path_browse_button = QPushButton("Browse...")
        self.diagnostic_log_path_browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.diagnostic_log_path_browse_button.setFlat(True)
        self.diagnostic_log_path_browse_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        self.diagnostic_log_path_browse_button.clicked.connect(self._choose_diagnostic_log_path)

        self.files_tabs = QTabWidget()
        self.files_raw_tab = QWidget()
        self.files_converted_tab = QWidget()
        self.files_diagnostics_tab = QWidget()
        self.files_configuration_tab = QWidget()

        raw_autosave_layout = self._build_recording_tab_layout(
            self.files_raw_tab,
            "Raw recording",
            "Choose where raw recordings are written when autosave is on.",
        )
        raw_autosave_layout.addRow(self.recording_raw_autosave_checkbox)
        raw_autosave_layout.addRow("Recording file name", self.recording_raw_autosave_file_name_edit)
        raw_autosave_layout.addRow(self.recording_raw_autosave_timestamp_checkbox)
        raw_autosave_folder_row = QWidget()
        raw_autosave_folder_layout = QHBoxLayout(raw_autosave_folder_row)
        raw_autosave_folder_layout.setContentsMargins(0, 0, 0, 0)
        raw_autosave_folder_layout.setSpacing(8)
        raw_autosave_folder_layout.addWidget(self.recording_raw_autosave_folder_edit, 1)
        raw_autosave_folder_layout.addWidget(self.recording_raw_autosave_browse_button)
        raw_autosave_layout.addRow("Output folder", raw_autosave_folder_row)
        self.raw_autosave_preview_label = QLabel("")
        self.raw_autosave_preview_label.setWordWrap(True)
        self.raw_autosave_preview_label.setStyleSheet("color: #666666;")
        raw_autosave_layout.addRow("Preview", self.raw_autosave_preview_label)

        converted_autosave_layout = self._build_recording_tab_layout(
            self.files_converted_tab,
            "Converted script",
            "Choose where converted scripts are written when autosave is on.",
        )
        converted_autosave_layout.addRow(self.recording_autosave_checkbox)
        converted_autosave_layout.addRow("Script file name", self.recording_autosave_file_name_edit)
        converted_autosave_layout.addRow(self.recording_autosave_timestamp_checkbox)
        autosave_folder_row = QWidget()
        autosave_folder_layout = QHBoxLayout(autosave_folder_row)
        autosave_folder_layout.setContentsMargins(0, 0, 0, 0)
        autosave_folder_layout.setSpacing(8)
        autosave_folder_layout.addWidget(self.recording_autosave_folder_edit, 1)
        autosave_folder_layout.addWidget(self.recording_autosave_browse_button)
        converted_autosave_layout.addRow("Output folder", autosave_folder_row)
        script_extension_row = QWidget()
        script_extension_layout = QHBoxLayout(script_extension_row)
        script_extension_layout.setContentsMargins(0, 0, 0, 0)
        script_extension_layout.setSpacing(10)
        script_extension_layout.addWidget(self.scripting_extension_edit, 0)
        script_extension_hint = QLabel("Default script extension: .ass")
        script_extension_hint.setWordWrap(False)
        script_extension_hint.setStyleSheet("color: #777777; font-size: 11px;")
        script_extension_layout.addWidget(script_extension_hint, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        script_extension_layout.addStretch(1)
        converted_autosave_layout.addRow("Script extension", script_extension_row)
        self.converted_autosave_preview_label = QLabel("")
        self.converted_autosave_preview_label.setWordWrap(True)
        self.converted_autosave_preview_label.setStyleSheet("color: #666666;")
        converted_autosave_layout.addRow("Preview", self.converted_autosave_preview_label)

        diagnostics_layout = self._build_recording_tab_layout(
            self.files_diagnostics_tab,
            "Diagnostics",
            "Choose where the desktop diagnostics log is written.",
        )
        diagnostic_row = QWidget()
        diagnostic_row_layout = QHBoxLayout(diagnostic_row)
        diagnostic_row_layout.setContentsMargins(0, 0, 0, 0)
        diagnostic_row_layout.setSpacing(8)
        diagnostic_row_layout.addWidget(self.diagnostic_log_path_edit, 1)
        diagnostic_row_layout.addWidget(self.diagnostic_log_path_browse_button, 0)
        diagnostics_layout.addRow("Diagnostic log file", diagnostic_row)

        self.diagnostics_log_preview_label = QLabel("")
        self.diagnostics_log_preview_label.setWordWrap(True)
        self.diagnostics_log_preview_label.setStyleSheet("color: #666666;")
        diagnostics_layout.addRow("Preview", self.diagnostics_log_preview_label)

        configuration_layout = self._build_recording_tab_layout(
            self.files_configuration_tab,
            "Configuration",
            "See where the desktop settings file is stored.",
        )
        configuration_tab_layout = self.files_configuration_tab.layout()
        if configuration_tab_layout is not None:
            configuration_tab_layout.setContentsMargins(4, 8, 4, 8)
            configuration_tab_layout.setSpacing(10)
        self.configuration_directory_label = QLabel("")
        self.configuration_directory_label.setWordWrap(True)
        self.configuration_directory_label.setStyleSheet("color: #666666;")
        configuration_layout.addRow("Configuration directory", self.configuration_directory_label)

        self.configuration_settings_path_label = QLabel("")
        self.configuration_settings_path_label.setWordWrap(True)
        self.configuration_settings_path_label.setStyleSheet("color: #666666;")
        configuration_layout.addRow("Settings file", self.configuration_settings_path_label)

        configuration_folder_button = QPushButton("Open configuration folder")
        configuration_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        configuration_folder_button.setFlat(True)
        configuration_folder_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        configuration_folder_button.clicked.connect(self._open_configuration_folder)
        configuration_layout.addRow(
            self._build_inline_action_row(
                "Open folder",
                configuration_folder_button,
                label_width=self._configuration_action_label_width(),
            )
        )

        configuration_delete_button = QPushButton("Delete configuration file")
        configuration_delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        configuration_delete_button.setFlat(True)
        configuration_delete_button.setStyleSheet(
            "QPushButton { padding: 0 4px; font-size: 11px; text-decoration: underline; }"
        )
        configuration_delete_button.clicked.connect(self._delete_configuration_file)
        configuration_layout.addRow(
            self._build_inline_action_row(
                "Delete file",
                configuration_delete_button,
                label_width=self._configuration_action_label_width(),
            )
        )
        configuration_frame = self.files_configuration_tab.findChild(QFrame)
        if configuration_frame is not None:
            configuration_frame.setStyleSheet("QFrame { padding: 4px; }")

        self.files_tabs.addTab(self.files_raw_tab, "Raw recording")
        self.files_tabs.addTab(self.files_converted_tab, "Converted script")
        self.files_tabs.addTab(self.files_diagnostics_tab, "Diagnostics")
        self.files_tabs.addTab(self.files_configuration_tab, "Configuration")
        layout.insertWidget(1, self.files_tabs)
        self._update_configuration_file_labels()
        self._update_file_output_previews()
        self._update_recording_autosave_controls(self.recording_autosave_checkbox.isChecked())
        self._update_recording_raw_autosave_controls(
            self.recording_raw_autosave_checkbox.isChecked()
        )
        layout.addStretch(1)
        return page

    def _build_diagnostics_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Diagnostics",
            "Configure diagnostic logging levels and output destinations for the desktop app.",
            actions=[("Restore Defaults", self.reset_diagnostics_settings_to_defaults)],
        )

        self.diagnostics_enabled_checkbox = QCheckBox("Enable diagnostics")
        self.diagnostics_show_diagnostics_tab_checkbox = QCheckBox("Show diagnostics tab")
        self.diagnostics_show_diagnostics_tab_checkbox.setToolTip(
            "Show or hide the Diagnostics tab in the workspace."
        )
        self.diagnostics_show_diagnostics_tab_checkbox.setChecked(False)
        self.diagnostics_min_severity_combo = self._build_selection_combo(
            "Diagnostic minimum severity",
            [
                ("Debug", "debug"),
                ("Info", "info"),
                ("Warning", "warning"),
                ("Error", "error"),
            ],
        )
        self.diagnostics_max_detail_combo = self._build_selection_combo(
            "Maximum detail",
            [
                ("Essential", "essential"),
                ("Summary", "summary"),
                ("Decision", "decision"),
                ("Trace", "trace"),
            ],
        )
        self.diagnostics_file_checkbox = QCheckBox("Log to file")
        self.diagnostics_stdout_checkbox = QCheckBox("Log to standard output")
        self.diagnostics_stdout_checkbox.setToolTip(
            "Write diagnostics to the console as well as any file output."
        )
        self.diagnostics_show_diagnostics_tab_checkbox.toggled.connect(
            self._sync_diagnostics_tab_visibility_toggled
        )
        self.diagnostics_enabled_checkbox.toggled.connect(self._emit_preferences_changed)
        self.diagnostics_min_severity_combo.currentIndexChanged.connect(
            self._emit_preferences_changed
        )
        self.diagnostics_max_detail_combo.currentIndexChanged.connect(
            self._emit_preferences_changed
        )
        self.diagnostics_file_checkbox.toggled.connect(self._emit_preferences_changed)
        self.diagnostics_stdout_checkbox.toggled.connect(self._emit_preferences_changed)

        diagnostics_frame = QFrame()
        diagnostics_frame.setFrameShape(QFrame.Shape.StyledPanel)
        diagnostics_frame.setStyleSheet("QFrame { padding: 8px; }")
        diagnostics_layout = QFormLayout(diagnostics_frame)
        diagnostics_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_layout.setHorizontalSpacing(12)
        diagnostics_layout.setVerticalSpacing(10)
        diagnostics_layout.addRow(self.diagnostics_show_diagnostics_tab_checkbox)
        diagnostics_layout.addRow(self.diagnostics_enabled_checkbox)
        diagnostics_layout.addRow("Minimum severity", self.diagnostics_min_severity_combo)
        diagnostics_layout.addRow("Max detail", self.diagnostics_max_detail_combo)
        diagnostics_layout.addRow(self.diagnostics_stdout_checkbox)
        diagnostics_layout.addRow(self.diagnostics_file_checkbox)

        self.diagnostics_log_path_title_label = QLabel("Log file path")
        self.diagnostics_log_path_title_label.setStyleSheet("font-weight: 600;")
        self.diagnostics_log_path_label = QLabel("")
        self.diagnostics_log_path_label.setWordWrap(True)
        self.diagnostics_log_path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.diagnostics_log_path_label.setStyleSheet("color: #666666;")
        diagnostics_log_path_row = QWidget()
        diagnostics_log_path_layout = QVBoxLayout(diagnostics_log_path_row)
        diagnostics_log_path_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_log_path_layout.setSpacing(2)
        diagnostics_log_path_layout.addWidget(self.diagnostics_log_path_title_label)
        diagnostics_log_path_layout.addWidget(self.diagnostics_log_path_label)
        diagnostics_layout.addRow(diagnostics_log_path_row)

        diagnostics_note = QLabel(
            "Use the checkboxes to enable logging and choose output targets. The Files page "
            "owns the editable log path, and this page shows the resolved destination."
        )
        diagnostics_note.setWordWrap(True)
        diagnostics_note.setStyleSheet("color: #666666;")

        layout.insertWidget(1, diagnostics_frame)
        layout.insertWidget(2, diagnostics_note)
        self._update_diagnostics_log_path_label()
        layout.addStretch(1)
        return page

    def _build_debug_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Debug",
            "Choose whether the Run Sidebar is shown in the workspace.",
            actions=[("Restore Defaults", self.reset_debug_settings_to_defaults)],
        )

        debug_frame = QFrame()
        debug_frame.setFrameShape(QFrame.Shape.StyledPanel)
        debug_frame.setStyleSheet("QFrame { padding: 8px; }")
        debug_layout = QVBoxLayout(debug_frame)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_layout.setSpacing(12)

        self.open_debug_tab_on_pause_checkbox = QCheckBox("Open Run when paused")
        self.open_debug_tab_on_pause_checkbox.setToolTip(
            "Automatically switch to the Run Sidebar when execution pauses."
        )
        self.open_debug_tab_on_pause_checkbox.toggled.connect(self._emit_preferences_changed)
        debug_layout.addWidget(self.open_debug_tab_on_pause_checkbox)

        debug_note = QLabel(
            "Hide the Run Sidebar if you want a cleaner workspace while keeping the Run tab available."
        )
        debug_note.setWordWrap(True)
        debug_note.setStyleSheet("color: #666666;")
        debug_layout.addWidget(debug_note)

        layout.insertWidget(1, debug_frame)
        layout.addStretch(1)
        return page

    def _build_script_settings_frame(self) -> QFrame:
        script_frame = QFrame()
        script_frame.setFrameShape(QFrame.Shape.StyledPanel)
        script_frame.setStyleSheet("QFrame { padding: 8px; }")
        script_layout = QVBoxLayout(script_frame)
        script_layout.setContentsMargins(0, 0, 0, 0)
        script_layout.setSpacing(8)

        self.scripting_language_combo = QComboBox()
        self.scripting_language_combo.addItems(["ActionShellScript", "Custom"])
        self.scripting_language_combo.currentTextChanged.connect(self._emit_preferences_changed)
        script_subframe = QFrame()
        script_subframe.setFrameShape(QFrame.Shape.StyledPanel)
        script_subframe_layout = QFormLayout(script_subframe)
        script_subframe_layout.setContentsMargins(0, 0, 0, 0)
        script_subframe_layout.setSpacing(8)
        script_subframe_layout.addRow(
            "Language",
            self.scripting_language_combo,
        )
        script_layout.addWidget(script_subframe)
        return script_frame

    def _build_runtime_page(self) -> QWidget:
        page, layout = self._make_page_shell(
            "Runtime",
            "Set execution limits and mouse-movement defaults used during playback.",
            actions=[
                ("Restore Defaults", self.reset_runtime_settings_to_defaults),
            ],
        )

        runtime_tabs = QTabWidget()
        runtime_tabs.setObjectName("runtimeTabs")
        self.runtime_tabs = runtime_tabs
        runtime_tabs.setDocumentMode(True)
        runtime_tabs.addTab(self._build_execution_frame(), "Execution")
        runtime_tabs.addTab(self._build_mouse_movement_profile_frame(), "Mouse Movement Curve")
        runtime_tabs.addTab(self._build_mouse_movement_step_controls_tab(), "Step Controls")
        layout.insertWidget(1, runtime_tabs)
        layout.addStretch(1)
        return page

    def _build_execution_frame(self) -> QWidget:
        execution_frame = QFrame()
        execution_frame.setFrameShape(QFrame.Shape.StyledPanel)
        execution_frame.setStyleSheet("QFrame { padding: 8px; }")
        execution_layout = QVBoxLayout(execution_frame)
        execution_layout.setContentsMargins(0, 0, 0, 0)
        execution_layout.setSpacing(8)

        execution_header = QHBoxLayout()
        execution_header.setContentsMargins(0, 0, 0, 0)
        execution_header.setSpacing(8)

        execution_title = QLabel("Execution")
        execution_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        execution_header.addWidget(execution_title, 1)

        execution_layout.addLayout(execution_header)

        self.runtime_max_loop_iterations_spin = QSpinBox()
        self.runtime_max_loop_iterations_spin.setRange(1, 10_000_000)
        self.runtime_max_loop_iterations_spin.setValue(100_000)
        self.runtime_max_loop_iterations_spin.valueChanged.connect(self._emit_preferences_changed)

        self.runtime_max_call_depth_spin = QSpinBox()
        self.runtime_max_call_depth_spin.setRange(1, 10_000)
        self.runtime_max_call_depth_spin.setValue(250)
        self.runtime_max_call_depth_spin.valueChanged.connect(self._emit_preferences_changed)

        self.runtime_default_mouse_move_speed_spin = QSpinBox()
        self.runtime_default_mouse_move_speed_spin.setRange(0, 100)
        self.runtime_default_mouse_move_speed_spin.setValue(10)
        self.runtime_default_mouse_move_speed_spin.valueChanged.connect(self._emit_preferences_changed)

        execution_form = QFormLayout()
        execution_form.setContentsMargins(0, 0, 0, 0)
        execution_form.setHorizontalSpacing(12)
        execution_form.setVerticalSpacing(10)
        execution_form.addRow("Max loop iterations", self.runtime_max_loop_iterations_spin)
        execution_form.addRow("Max call depth", self.runtime_max_call_depth_spin)
        execution_form.addRow(
            "Default mouse move speed", self.runtime_default_mouse_move_speed_spin
        )
        execution_note = QLabel(
            "These settings control how much work playback can do at once and the default "
            "mouse movement speed."
        )
        execution_note.setWordWrap(True)
        execution_note.setStyleSheet("color: #666666;")
        execution_layout.addWidget(execution_note)
        execution_layout.addLayout(execution_form)

        execution_layout.addStretch(1)
        return execution_frame

    def _build_mouse_movement_profile_frame(self) -> QWidget:
        movement_frame = QFrame()
        movement_frame.setFrameShape(QFrame.Shape.StyledPanel)
        movement_frame.setStyleSheet("QFrame { padding: 8px; }")
        movement_layout = QVBoxLayout(movement_frame)
        movement_layout.setContentsMargins(0, 0, 0, 0)
        movement_layout.setSpacing(8)

        movement_header = QHBoxLayout()
        movement_header.setContentsMargins(0, 0, 0, 0)
        movement_header.setSpacing(8)

        movement_title = QLabel("Mouse Movement Curve")
        movement_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        movement_header.addWidget(movement_title, 1)
        movement_layout.addLayout(movement_header)

        editor_panel = QFrame()
        editor_panel.setObjectName("runtimeMouseMovementCurveEditorPanel")
        editor_panel.setFrameShape(QFrame.Shape.NoFrame)
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)

        fast_button = QPushButton("Fast")
        fast_button.setCursor(Qt.CursorShape.PointingHandCursor)
        fast_button.setMinimumHeight(28)
        fast_button.setStyleSheet(
            "QPushButton { padding: 2px 10px; font-size: 11px; }"
        )
        fast_button.clicked.connect(
            lambda: self._apply_mouse_movement_curve_preset(MouseMovementProfile.fast())
        )
        preset_row.addWidget(fast_button)

        slow_button = QPushButton("Slow")
        slow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        slow_button.setMinimumHeight(28)
        slow_button.setStyleSheet(
            "QPushButton { padding: 2px 10px; font-size: 11px; }"
        )
        slow_button.clicked.connect(
            lambda: self._apply_mouse_movement_curve_preset(MouseMovementProfile.slow())
        )
        preset_row.addWidget(slow_button)

        balanced_button = QPushButton("Balanced")
        balanced_button.setCursor(Qt.CursorShape.PointingHandCursor)
        balanced_button.setMinimumHeight(28)
        balanced_button.setStyleSheet(
            "QPushButton { padding: 2px 10px; font-size: 11px; }"
        )
        balanced_button.clicked.connect(
            lambda: self._apply_mouse_movement_curve_preset(MouseMovementProfile.balanced())
        )
        preset_row.addWidget(balanced_button)

        smooth_button = QPushButton("Smooth")
        smooth_button.setCursor(Qt.CursorShape.PointingHandCursor)
        smooth_button.setMinimumHeight(28)
        smooth_button.setStyleSheet(
            "QPushButton { padding: 2px 10px; font-size: 11px; }"
        )
        smooth_button.clicked.connect(
            lambda: self._apply_mouse_movement_curve_preset(MouseMovementProfile.smooth())
        )
        preset_row.addWidget(smooth_button)

        preset_row.addStretch(1)
        editor_layout.addLayout(preset_row)

        editor_widget = self._build_mouse_movement_curve_table()
        editor_layout.addWidget(editor_widget)

        movement_controls = QHBoxLayout()
        movement_controls.setContentsMargins(0, 0, 0, 0)
        movement_controls.setSpacing(8)

        add_point_button = QPushButton("Add Point")
        add_point_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_point_button.clicked.connect(self._add_mouse_movement_curve_point)
        movement_controls.addWidget(add_point_button)

        remove_point_button = QPushButton("Remove Selected")
        remove_point_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_point_button.clicked.connect(self._remove_selected_mouse_movement_curve_points)
        movement_controls.addWidget(remove_point_button)

        movement_controls.addStretch(1)
        editor_layout.addLayout(movement_controls)

        info_panel = self._build_mouse_movement_curve_info_panel()
        self.runtime_mouse_movement_curve_editor_scroll_area = None
        editor_scroll = QScrollArea()
        editor_scroll.setObjectName("runtimeMouseMovementCurveEditorScrollArea")
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor_scroll.setWidget(editor_panel)
        editor_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.runtime_mouse_movement_curve_editor_scroll_area = editor_scroll

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setObjectName("runtimeMouseMovementCurveContentSplitter")
        content_splitter.addWidget(editor_scroll)
        content_splitter.addWidget(info_panel)
        content_splitter.setHandleWidth(8)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_splitter.setSizes([860, 280])
        self.runtime_mouse_movement_curve_content_splitter = content_splitter
        self.runtime_mouse_movement_curve_info_frame = info_panel
        self.runtime_mouse_movement_curve_editor_panel = editor_panel
        self._update_mouse_movement_curve_layout()
        movement_layout.addWidget(content_splitter)
        movement_layout.addStretch(1)

        return movement_frame

    def _build_mouse_movement_curve_info_panel(self) -> QWidget:
        info_frame = QFrame()
        info_frame.setObjectName("runtimeMouseMovementCurveInfoFrame")
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setStyleSheet("QFrame { padding: 6px; }")
        info_frame.setMinimumWidth(240)
        info_frame.setMaximumWidth(300)
        info_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        info_title = QLabel("Curve Legend")
        info_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #202020;")
        info_layout.addWidget(info_title)

        self.runtime_mouse_movement_reference_checkbox = QCheckBox(
            "Show reference curve"
        )
        self.runtime_mouse_movement_reference_checkbox.setToolTip(
            "Show the default curve overlay in the preview."
        )
        self.runtime_mouse_movement_reference_checkbox.setChecked(True)
        self.runtime_mouse_movement_reference_checkbox.toggled.connect(
            self._emit_preferences_changed
        )
        info_layout.addWidget(self.runtime_mouse_movement_reference_checkbox)

        self.runtime_mouse_movement_curve_preview = MouseMovementCurvePreview()
        self.runtime_mouse_movement_reference_checkbox.toggled.connect(
            self.runtime_mouse_movement_curve_preview.set_reference_curve_visible
        )
        self.runtime_mouse_movement_curve_preview.set_reference_curve_visible(
            self.runtime_mouse_movement_reference_checkbox.isChecked()
        )
        info_layout.addWidget(self.runtime_mouse_movement_curve_preview)

        table_container = self._build_mouse_movement_curve_key_table()
        info_layout.addWidget(table_container)
        return info_frame

    def _update_mouse_movement_curve_layout(self) -> None:
        splitter = getattr(self, "runtime_mouse_movement_curve_content_splitter", None)
        info_frame = getattr(self, "runtime_mouse_movement_curve_info_frame", None)
        if splitter is None or info_frame is None:
            return
        if not self.isVisible():
            return

        runtime_tabs = getattr(self, "runtime_tabs", None)
        available_width = 0
        if runtime_tabs is not None:
            available_width = runtime_tabs.width()
        if available_width <= 1:
            available_width = self.width()
        if available_width <= 1:
            return
        should_stack = available_width < 1260
        target_orientation = (
            Qt.Orientation.Vertical if should_stack else Qt.Orientation.Horizontal
        )
        if splitter.orientation() != target_orientation:
            splitter.setOrientation(target_orientation)

        if should_stack:
            splitter.setHandleWidth(6)
            info_frame.setMinimumWidth(0)
            info_frame.setMaximumWidth(16777215)
            splitter.setSizes(
                [max(1, splitter.height() // 2), max(1, splitter.height() // 2)]
            )
        else:
            splitter.setHandleWidth(8)
            info_frame.setMinimumWidth(240)
            info_frame.setMaximumWidth(300)
            splitter.setSizes([860, 280])

    def _build_mouse_movement_step_controls_tab(self) -> QWidget:
        step_frame = QFrame()
        step_frame.setObjectName("runtimeMouseMovementStepControlsFrame")
        step_frame.setFrameShape(QFrame.Shape.StyledPanel)
        step_frame.setStyleSheet("QFrame { padding: 6px; }")
        step_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        step_layout = QVBoxLayout(step_frame)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(6)

        step_title = QLabel("Step Controls")
        step_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #202020;")
        step_layout.addWidget(step_title)

        self.runtime_mouse_movement_min_steps_spin = QSpinBox()
        self.runtime_mouse_movement_min_steps_spin.setRange(1, 1_000_000)
        self.runtime_mouse_movement_min_steps_spin.setValue(1)
        self.runtime_mouse_movement_min_steps_spin.valueChanged.connect(
            self._on_mouse_movement_step_settings_changed
        )

        self.runtime_mouse_movement_max_steps_spin = QSpinBox()
        self.runtime_mouse_movement_max_steps_spin.setRange(1, 1_000_000)
        self.runtime_mouse_movement_max_steps_spin.setValue(120)
        self.runtime_mouse_movement_max_steps_spin.valueChanged.connect(
            self._on_mouse_movement_step_settings_changed
        )

        self.runtime_mouse_movement_step_distance_px_spin = QSpinBox()
        self.runtime_mouse_movement_step_distance_px_spin.setRange(1, 1_000_000)
        self.runtime_mouse_movement_step_distance_px_spin.setValue(8)
        self.runtime_mouse_movement_step_distance_px_spin.valueChanged.connect(
            self._on_mouse_movement_step_settings_changed
        )

        step_form = QFormLayout()
        step_form.setContentsMargins(0, 0, 0, 0)
        step_form.setHorizontalSpacing(12)
        step_form.setVerticalSpacing(10)
        step_form.addRow("Minimum steps", self.runtime_mouse_movement_min_steps_spin)
        step_form.addRow("Maximum steps", self.runtime_mouse_movement_max_steps_spin)
        step_form.addRow(
            "Step distance (px)",
            self.runtime_mouse_movement_step_distance_px_spin,
        )
        step_layout.addLayout(step_form)

        step_note = QLabel(
            "These settings control how detailed the generated movement steps are for each move."
        )
        step_note.setWordWrap(True)
        step_note.setStyleSheet("color: #666666;")
        step_layout.addWidget(step_note)

        self._sync_mouse_movement_step_control_ranges()
        return step_frame

    def _build_mouse_movement_curve_key_table(self) -> QWidget:
        columns = [
            ColumnSpec(
                name="setting",
                label="Setting",
                editable=False,
                width_mode="fixed",
                fixed_width=120,
            ),
            ColumnSpec(
                name="value",
                label="Value",
                editable=False,
                width_mode="stretch",
            ),
        ]
        rows = [
            {
                "setting": "Speed range",
                "value": "0 to 100; 0 is reserved for MouseMove(..., 0) and curve points start at 1",
            },
            {
                "setting": "Speed meaning",
                "value": "0 = instant for MouseMove(..., 0); the curve editor starts at 1",
            },
            {"setting": "Duration range", "value": "0 to 60,000 ms"},
            {"setting": "Higher speed", "value": "Shorter travel"},
            {"setting": "Lower duration", "value": "Faster movement"},
            {"setting": "Editing", "value": "Use add / remove"},
        ]
        model = self._table_api.create_model(columns, rows)
        view = self._table_api.create_view(model)
        view.setObjectName("runtimeMouseMovementCurveKeyTable")
        view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setAlternatingRowColors(False)
        view.setShowGrid(True)
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(30)
        view.verticalHeader().setMinimumSectionSize(30)
        view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        view.horizontalHeader().setVisible(False)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setStyleSheet(
            "QTableView {"
            " background-color: #ffffff;"
            " border: 0;"
            " gridline-color: #e5e9f0;"
            " }"
            "QTableView::item {"
            " padding: 2px 6px;"
            " font-size: 11px;"
            " }"
        )

        container = QFrame()
        container.setObjectName("runtimeMouseMovementCurveKeyTableContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame {"
            " background-color: #ffffff;"
            " border: 1px solid #d9dee6;"
            " }"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        header_strip = self._table_api.create_header_strip(
            columns,
            container,
            text_color="#202020",
            background_color="#f3f5f8",
            border_color="#d9dee6",
            padding="3px 8px",
            font_size=10,
            bold=True,
        )
        header_strip.setObjectName("runtimeMouseMovementCurveKeyTableHeaderStrip")
        container_layout.addWidget(header_strip)
        container_layout.addWidget(view)
        return container

    def _build_mouse_movement_curve_table(self) -> QWidget:
        columns = [
            ColumnSpec(
                name="speed",
                label="Speed",
                editor="spinbox",
                delegate_key="spinbox",
                editable=True,
                width_mode="fixed",
                fixed_width=104,
                minimum=1,
                maximum=100,
                single_step=1,
            ),
            ColumnSpec(
                name="duration_ms",
                label="Duration",
                editor="spinbox",
                delegate_key="spinbox",
                editable=True,
                width_mode="fixed",
                fixed_width=148,
                minimum=0,
                maximum=60_000,
                single_step=5,
                suffix=" ms",
            ),
        ]
        rows = [
            {"speed": max(1, int(speed)), "duration_ms": duration_ms}
            for speed, duration_ms in MouseMovementProfile().duration_curve
        ]
        model = self._table_api.create_model(columns, rows)
        self._wire_preferences_table_model(
            model,
            on_change=self._update_mouse_movement_curve_preview,
        )
        self.runtime_mouse_movement_curve_model = model
        view = self._table_api.create_view(model)
        self.runtime_mouse_movement_curve_table = view
        view.setObjectName("runtimeMouseMovementCurveTable")
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        view.setAlternatingRowColors(True)
        view.setShowGrid(True)
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(34)
        view.verticalHeader().setMinimumSectionSize(34)
        view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        view.horizontalHeader().setVisible(True)
        view.horizontalHeader().setHighlightSections(False)
        view.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        view.horizontalHeader().setFixedHeight(56)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        view.setFixedWidth(292)
        view.setStyleSheet(
            "QTableView {"
            " background-color: #ffffff;"
            " border: 0;"
            " gridline-color: #d6dbe2;"
            " }"
            "QTableView QHeaderView::section {"
            " background-color: #e9edf2;"
            " color: #202020;"
            " border: 0;"
            " border-bottom: 1px solid #c7cdd4;"
            " padding: 12px 8px;"
            " font-size: 12px;"
            " font-weight: 600;"
            " }"
            "QTableView::item {"
            " padding: 3px 8px;"
            " }"
        )

        container = QFrame()
        container.setObjectName("runtimeMouseMovementCurveTableContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setStyleSheet(
            "QFrame {"
            " background-color: #ffffff;"
            " border: 1px solid #c7cdd4;"
            " }"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(view)
        self._update_mouse_movement_curve_preview()
        return container

    def _load_mouse_movement_curve_profile(self, profile: MouseMovementProfile) -> None:
        model = self.runtime_mouse_movement_curve_model
        model.set_rows(
            [
                {"speed": max(1, int(speed)), "duration_ms": max(0, int(duration_ms))}
                for speed, duration_ms in profile.duration_curve
            ]
        )
        blockers = []
        if hasattr(self, "runtime_mouse_movement_min_steps_spin"):
            blockers.append(QSignalBlocker(self.runtime_mouse_movement_min_steps_spin))
        if hasattr(self, "runtime_mouse_movement_max_steps_spin"):
            blockers.append(QSignalBlocker(self.runtime_mouse_movement_max_steps_spin))
        if hasattr(self, "runtime_mouse_movement_step_distance_px_spin"):
            blockers.append(QSignalBlocker(self.runtime_mouse_movement_step_distance_px_spin))
        _ = blockers
        if hasattr(self, "runtime_mouse_movement_min_steps_spin"):
            self.runtime_mouse_movement_min_steps_spin.setValue(profile.min_steps)
        if hasattr(self, "runtime_mouse_movement_max_steps_spin"):
            self.runtime_mouse_movement_max_steps_spin.setValue(profile.max_steps)
        if hasattr(self, "runtime_mouse_movement_step_distance_px_spin"):
            self.runtime_mouse_movement_step_distance_px_spin.setValue(profile.step_distance_px)
        self._sync_mouse_movement_step_control_ranges()
        self._update_mouse_movement_curve_preview()

    def reset_mouse_movement_curve_to_defaults(self) -> None:
        self._apply_mouse_movement_curve_preset(MouseMovementProfile())

    def _apply_mouse_movement_curve_preset(self, profile: MouseMovementProfile) -> None:
        self._load_mouse_movement_curve_profile(profile)
        self._emit_preferences_changed()

    def _sync_mouse_movement_step_control_ranges(self) -> None:
        if not hasattr(self, "runtime_mouse_movement_min_steps_spin"):
            return
        min_steps = self.runtime_mouse_movement_min_steps_spin.value()
        max_steps = self.runtime_mouse_movement_max_steps_spin.value()
        if max_steps < min_steps:
            max_steps = min_steps
            self.runtime_mouse_movement_max_steps_spin.setValue(max_steps)
        self.runtime_mouse_movement_min_steps_spin.setMaximum(max_steps)
        self.runtime_mouse_movement_max_steps_spin.setMinimum(min_steps)

    def _on_mouse_movement_step_settings_changed(self, *args) -> None:
        self._sync_mouse_movement_step_control_ranges()
        self._emit_preferences_changed()

    def _append_mouse_movement_curve_point(self, speed: int = 10, duration_ms: int = 100) -> None:
        self.runtime_mouse_movement_curve_model.add_row(
            {"speed": max(1, min(100, int(speed))), "duration_ms": max(0, int(duration_ms))}
        )

    def _add_mouse_movement_curve_point(self) -> None:
        self._append_mouse_movement_curve_point()
        self._emit_preferences_changed()

    def _remove_selected_mouse_movement_curve_points(self) -> None:
        table = self.runtime_mouse_movement_curve_table
        model = self.runtime_mouse_movement_curve_model
        selected_rows = sorted(
            {index.row() for index in table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            return
        if len(selected_rows) >= model.rowCount():
            model.set_rows(
                [
                    {
                        "speed": speed,
                        "duration_ms": duration_ms,
                    }
                    for speed, duration_ms in MouseMovementProfile().duration_curve
                ]
            )
            self._emit_preferences_changed()
            return
        for row in selected_rows:
            model.remove_row(row)
        self._emit_preferences_changed()

    def _wire_preferences_table_model(self, model, *, on_change: Callable[[], None] | None = None) -> None:
        model.dataChanged.connect(self._emit_preferences_changed)
        model.rowsInserted.connect(self._emit_preferences_changed)
        model.rowsRemoved.connect(self._emit_preferences_changed)
        model.modelReset.connect(self._emit_preferences_changed)
        if on_change is not None:
            model.dataChanged.connect(on_change)
            model.rowsInserted.connect(on_change)
            model.rowsRemoved.connect(on_change)
            model.modelReset.connect(on_change)

    def _update_mouse_movement_curve_preview(self, *args) -> None:
        _ = args
        if not hasattr(self, "runtime_mouse_movement_curve_preview"):
            return
        model = getattr(self, "runtime_mouse_movement_curve_model", None)
        if model is None:
            self.runtime_mouse_movement_curve_preview.set_curve_points(())
            return
        points: list[tuple[int, int]] = []
        for values in model.rows():
            try:
                speed = max(1, int(values.get("speed", 1)))
                duration_ms = max(0, int(values.get("duration_ms", 0)))
            except (TypeError, ValueError):
                continue
            points.append((speed, duration_ms))
        self.runtime_mouse_movement_curve_preview.set_curve_points(tuple(points))

    @contextmanager
    def _preferences_batch(self) -> Iterator[None]:
        self._preferences_batch_depth += 1
        try:
            yield
        finally:
            self._preferences_batch_depth -= 1

    def _capture_preferences_bundle(self) -> DesktopSettingsBundle:
        self._sync_font_family_selection()
        return self.settings_bundle()

    def _sync_font_family_selection(self) -> None:
        if not hasattr(self, "font_family_combo"):
            return
        if hasattr(self, "_text_editor_item_list") and self._text_editor_item_list.currentRow() == 1:
            return
        expected_family = self.draft_bundle.theme.font.family
        if self.font_family_combo.currentFont().family() == expected_family:
            return
        with QSignalBlocker(self.font_family_combo):
            self.font_family_combo.setCurrentFont(self.draft_bundle.theme.font.to_qfont())

    def _apply_preferences_bundle(self, bundle: DesktopSettingsBundle) -> None:
        self._load_preferences_into_widgets(bundle)

    def _refresh_preferences_ui_state(self) -> None:
        self._update_dirty_indicator()
        self._update_hotkey_conflicts()
        self._update_theme_readability_warning()
        self._update_appearance_item_markers()
        self._update_category_dirty_markers()

    def _section_snapshot_map(
        self,
        bundle: DesktopSettingsBundle | None = None,
    ) -> PreferenceSectionSnapshots:
        if bundle is None:
            bundle = self._capture_preferences_bundle()
        return PreferenceSectionSnapshots(
            general=(
                bundle.application.restore_last_workspace,
            ),
            appearance_editor=(
                bundle.theme.appearance.editor,
                bundle.theme.font,
            ),
            appearance_syntax=bundle.theme.appearance.syntax_highlighting,
            appearance_dirty_state=bundle.theme.appearance.dirty_indicators,
            appearance_tab_attention=bundle.theme.appearance.workspace_tab_attention,
            search_results_colors=(
                bundle.theme.search_results.header_active,
                bundle.theme.search_results.header_hovered,
                bundle.theme.search_results.header_active_hovered,
                bundle.theme.search_results.header_text,
                bundle.theme.search_results.line_text,
                bundle.theme.search_results.hit_text,
                bundle.theme.search_results.child_border_color,
            ),
            search_results_spacing=(
                bundle.theme.search_results.header_radius,
                bundle.theme.search_results.header_padding,
                bundle.theme.search_results.child_border_width,
                bundle.theme.search_results.child_padding_left,
                bundle.theme.search_results.child_margin_left,
            ),
            playback=bundle.playback,
            recording=bundle.recording,
            files=bundle.files,
            diagnostics=(bundle.diagnostics, bundle.application.show_diagnostics_tab),
            workspace_tabs=(
                bundle.application.show_summary_sidebar_on_left,
                bundle.application.hidden_workspace_tabs_strip_collapsed,
                bundle.application.show_analysis_tab,
                bundle.application.show_formatted_preview_tab,
                bundle.application.show_raw_recordings_tab,
                bundle.application.show_diagnostics_tab,
            ),
            debug=(
                bundle.application.open_debug_tab_on_pause,
            ),
            script=bundle.theme.scripting,
            runtime=bundle.runtime,
            hotkeys=self._hotkeys_snapshot(bundle),
        )

    def _hotkeys_snapshot(self, bundle: DesktopSettingsBundle | None = None) -> tuple[tuple[str, str], ...]:
        if bundle is None:
            bundle = self._capture_preferences_bundle()
        return tuple(
            (
                definition.action_id,
                bundle.application.hotkeys.bindings.get(definition.action_id, ""),
            )
            for definition in HOTKEY_DEFINITIONS
        )

    def _recompute_preferences_dirty(self) -> None:
        if self._preferences_batch_depth > 0:
            return
        previous_dirty = self._dirty
        self._draft_bundle = self._capture_preferences_bundle()
        section_diff = self._section_snapshot_map(self._draft_bundle).diff(
            self._section_snapshot_map(self._committed_bundle)
        )
        self._dirty = section_diff.any_dirty()
        self._refresh_preferences_ui_state()
        if previous_dirty != self._dirty:
            log.trace(
                "Preferences dirty state changed",
                event_id="desktop.preferences.dirty_state_changed",
                dirty=self._dirty,
            )
        self.preferencesChanged.emit(self._draft_bundle)

    def _section_default_bundle(self, section_name: str) -> DesktopSettingsBundle:
        for spec in self._SECTION_DEFAULT_SPECS:
            if spec.section_name == section_name:
                return spec.build_bundle(self)
        raise ValueError(f"Unsupported preference section: {section_name}")

    def _all_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle()

    def _playback_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=DesktopPlaybackSettings(),
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _hotkeys_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.draft_bundle.application.restore_last_workspace,
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                open_debug_tab_on_pause=self.draft_bundle.application.open_debug_tab_on_pause,
                show_summary_sidebar_on_left=self.draft_bundle.application.show_summary_sidebar_on_left,
                show_analysis_tab=self.draft_bundle.application.show_analysis_tab,
                show_formatted_preview_tab=self.draft_bundle.application.show_formatted_preview_tab,
                show_raw_recordings_tab=self.draft_bundle.application.show_raw_recordings_tab,
                show_diagnostics_tab=self.draft_bundle.application.show_diagnostics_tab,
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                hotkeys=DesktopHotkeySettings(bindings=default_hotkey_bindings()),
            ),
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _recording_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=DesktopRecordingSettings(),
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _appearance_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.draft_bundle.application.restore_last_workspace,
                open_debug_tab_on_pause=self.draft_bundle.application.open_debug_tab_on_pause,
                show_summary_sidebar_on_left=self.draft_bundle.application.show_summary_sidebar_on_left,
                show_analysis_tab=self.draft_bundle.application.show_analysis_tab,
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                show_formatted_preview_tab=True,
                show_raw_recordings_tab=False,
                show_diagnostics_tab=False,
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                hotkeys=self.draft_bundle.application.hotkeys,
            ),
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=AppearanceTheme(
                    editor=self.draft_bundle.theme.appearance.editor,
                    syntax_highlighting=self.draft_bundle.theme.appearance.syntax_highlighting,
                    dirty_indicators=DirtyIndicatorTheme(),
                    workspace_tab_attention=self.draft_bundle.theme.appearance.workspace_tab_attention,
                ),
                font=self.draft_bundle.theme.font,
                scripting=self.draft_bundle.theme.scripting,
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _workspace_tabs_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.draft_bundle.application.restore_last_workspace,
                open_debug_tab_on_pause=self.draft_bundle.application.open_debug_tab_on_pause,
                show_summary_sidebar_on_left=True,
                hidden_workspace_tabs_strip_collapsed=True,
                show_analysis_tab=False,
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                show_formatted_preview_tab=True,
                show_raw_recordings_tab=False,
                show_diagnostics_tab=False,
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                hotkeys=self.draft_bundle.application.hotkeys,
            ),
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _editor_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=AppearanceTheme(
                    editor=EditorAppearanceTheme(),
                    syntax_highlighting=self.draft_bundle.theme.appearance.syntax_highlighting,
                    dirty_indicators=self.draft_bundle.theme.appearance.dirty_indicators,
                    workspace_tab_attention=self.draft_bundle.theme.appearance.workspace_tab_attention,
                ),
                font=self.draft_bundle.theme.font,
                scripting=self.draft_bundle.theme.scripting,
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _text_editor_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=self.draft_bundle.theme.appearance,
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _formatting_defaults_bundle(self) -> DesktopSettingsBundle:
        current_scripting = cast(ScriptingSettings, self.draft_bundle.theme.scripting)
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=self.draft_bundle.theme.appearance,
                font=self.draft_bundle.theme.font,
                scripting=ScriptingSettings(
                    language=current_scripting.language,
                    indent_width=4,
                    use_spaces=True,
                    auto_indent=True,
                    auto_format_on_save=False,
                ),
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _style_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=AppearanceTheme(
                    editor=self.draft_bundle.theme.appearance.editor,
                    syntax_highlighting=SyntaxHighlightTheme(),
                    dirty_indicators=self.draft_bundle.theme.appearance.dirty_indicators,
                    workspace_tab_attention=self.draft_bundle.theme.appearance.workspace_tab_attention,
                ),
                font=self.draft_bundle.theme.font,
                scripting=self.draft_bundle.theme.scripting,
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _search_results_defaults_bundle(self) -> DesktopSettingsBundle:
        current = self.draft_bundle.theme.search_results
        defaults = SearchResultsTheme()
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=self.draft_bundle.theme.appearance,
                font=self.draft_bundle.theme.font,
                scripting=self.draft_bundle.theme.scripting,
                search_results=SearchResultsTheme(
                    header_active=defaults.header_active,
                    header_hovered=defaults.header_hovered,
                    header_active_hovered=defaults.header_active_hovered,
                    header_radius=current.header_radius,
                    header_padding=current.header_padding,
                    header_text=defaults.header_text,
                    line_text=defaults.line_text,
                    hit_text=defaults.hit_text,
                    child_border_color=defaults.child_border_color,
                    child_border_width=current.child_border_width,
                    child_padding_left=current.child_padding_left,
                    child_margin_left=current.child_margin_left,
                ),
            ),
        )

    def _search_spacing_defaults_bundle(self) -> DesktopSettingsBundle:
        current = self.draft_bundle.theme.search_results
        defaults = SearchResultsTheme()
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=self.draft_bundle.theme.appearance,
                font=self.draft_bundle.theme.font,
                scripting=self.draft_bundle.theme.scripting,
                search_results=SearchResultsTheme(
                    header_active=current.header_active,
                    header_hovered=current.header_hovered,
                    header_active_hovered=current.header_active_hovered,
                    header_radius=defaults.header_radius,
                    header_padding=defaults.header_padding,
                    header_text=current.header_text,
                    line_text=current.line_text,
                    hit_text=current.hit_text,
                    child_border_color=current.child_border_color,
                    child_border_width=defaults.child_border_width,
                    child_padding_left=defaults.child_padding_left,
                    child_margin_left=defaults.child_margin_left,
                ),
            ),
        )

    def _script_settings_defaults_bundle(self) -> DesktopSettingsBundle:
        current_scripting = cast(ScriptingSettings, self.draft_bundle.theme.scripting)
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=DesktopPreferences(
                appearance=self.draft_bundle.theme.appearance,
                font=self.draft_bundle.theme.font,
                scripting=ScriptingSettings(
                    language="ActionShellScript",
                    indent_width=current_scripting.indent_width,
                    use_spaces=current_scripting.use_spaces,
                    auto_indent=current_scripting.auto_indent,
                    auto_format_on_save=current_scripting.auto_format_on_save,
                ),
                search_results=self.draft_bundle.theme.search_results,
            ),
        )

    def _files_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=DesktopFilesSettings(),
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _diagnostics_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.draft_bundle.application.restore_last_workspace,
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                show_summary_sidebar_on_left=self.draft_bundle.application.show_summary_sidebar_on_left,
                show_formatted_preview_tab=self.draft_bundle.application.show_formatted_preview_tab,
                show_raw_recordings_tab=self.draft_bundle.application.show_raw_recordings_tab,
                show_diagnostics_tab=False,
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                hotkeys=self.draft_bundle.application.hotkeys,
            ),
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=DesktopDiagnosticsSettings(),
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _debug_tab_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.draft_bundle.application.restore_last_workspace,
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                open_debug_tab_on_pause=self.draft_bundle.application.open_debug_tab_on_pause,
                show_summary_sidebar_on_left=self.draft_bundle.application.show_summary_sidebar_on_left,
                show_formatted_preview_tab=self.draft_bundle.application.show_formatted_preview_tab,
                show_raw_recordings_tab=self.draft_bundle.application.show_raw_recordings_tab,
                show_diagnostics_tab=self.draft_bundle.application.show_diagnostics_tab,
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                hotkeys=self.draft_bundle.application.hotkeys,
            ),
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=self.draft_bundle.runtime,
            theme=self.draft_bundle.theme,
        )

    def _runtime_defaults_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=self.draft_bundle.application,
            playback=self.draft_bundle.playback,
            recording=self.draft_bundle.recording,
            files=self.draft_bundle.files,
            diagnostics=self.draft_bundle.diagnostics,
            runtime=DesktopRuntimeSettings(),
            theme=self.draft_bundle.theme,
        )

    _SECTION_DEFAULT_SPECS: ClassVar[tuple[PreferenceSectionDefaultSpec, ...]] = (
        PreferenceSectionDefaultSpec("all", _all_defaults_bundle),
        PreferenceSectionDefaultSpec("playback", _playback_defaults_bundle),
        PreferenceSectionDefaultSpec("hotkeys", _hotkeys_defaults_bundle),
        PreferenceSectionDefaultSpec("recording", _recording_defaults_bundle),
        PreferenceSectionDefaultSpec("files", _files_defaults_bundle),
        PreferenceSectionDefaultSpec("diagnostics", _diagnostics_defaults_bundle),
        PreferenceSectionDefaultSpec(DEBUG_PREFERENCES_SECTION, _debug_tab_defaults_bundle),
        PreferenceSectionDefaultSpec("editor", _editor_defaults_bundle),
        PreferenceSectionDefaultSpec("workspace_tabs", _workspace_tabs_defaults_bundle),
        PreferenceSectionDefaultSpec("search_results", _search_results_defaults_bundle),
        PreferenceSectionDefaultSpec("search_spacing", _search_spacing_defaults_bundle),
        PreferenceSectionDefaultSpec("text_editor", _text_editor_defaults_bundle),
        PreferenceSectionDefaultSpec("appearance", _appearance_defaults_bundle),
        PreferenceSectionDefaultSpec("formatting", _formatting_defaults_bundle),
        PreferenceSectionDefaultSpec("style", _style_defaults_bundle),
        PreferenceSectionDefaultSpec("scripting", _script_settings_defaults_bundle),
        PreferenceSectionDefaultSpec("runtime", _runtime_defaults_bundle),
    )

    def _restore_section_to_defaults(self, section_name: str) -> None:
        with self._preferences_batch():
            bundle = self._section_default_bundle(section_name)
            self._apply_preferences_bundle(bundle)
        self._recompute_preferences_dirty()

    def _build_placeholder_section(
        self,
        heading: str,
        description: str,
        *,
        action_label: str = "Restore Defaults",
        action_callback: Callable[[], None] | None = None,
    ) -> QWidget:
        if action_callback is None:
            action_callback = lambda: self._reset_placeholder_section(heading)
        page, layout = self._make_page_shell(
            heading,
            description,
            actions=[(action_label, action_callback)],
        )
        note = QLabel("This section is ready for future preferences.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        layout.insertWidget(1, note)
        return page

    def _build_on_off_combo(self, label: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(label.replace(" ", "").replace("-", "").lower() + "Combo")
        combo.addItem("OFF", False)
        combo.addItem("ON", True)
        return combo

    def _build_selection_combo(
        self,
        label: str,
        options: list[tuple[str, str]],
    ) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(label.replace(" ", "").replace("-", "").lower() + "Combo")
        for display, value in options:
            combo.addItem(display, value)
        return combo

    def _set_combo_data(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index < 0:
            index = 0
        combo.setCurrentIndex(index)

    def _build_recording_tab_layout(
        self,
        tab: QWidget,
        title: str,
        description: str,
    ) -> QFormLayout:
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(8, 8, 8, 8)
        tab_layout.setSpacing(12)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { padding: 8px; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        frame_layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #666666;")
        frame_layout.addWidget(description_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        frame_layout.addLayout(form)

        tab_layout.addWidget(frame)
        tab_layout.addStretch(1)
        return form

    def _build_inline_action_row(
        self,
        label_text: str,
        button: QPushButton,
        *,
        label_width: int | None = None,
    ) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 11px; color: #444444;")
        if label_width is not None:
            label.setFixedWidth(label_width)
        row_layout.addWidget(label)
        row_layout.addWidget(button)
        row_layout.addStretch(1)
        return row

    def _configuration_action_label_width(self) -> int:
        folder_width = QLabel("Open folder").sizeHint().width()
        file_width = QLabel("Delete file").sizeHint().width()
        return max(folder_width, file_width)

    def _on_hotkeys_model_changed(self, *args) -> None:  # noqa: ANN002
        _ = args
        if self._loading_preferences:
            return
        self._emit_preferences_changed()
        self._update_hotkey_conflicts()
        self._apply_hotkeys_search_text()

    def _on_hotkeys_search_changed(self, text: str) -> None:
        self._hotkeys_search_text = text
        self._filter_hotkeys_table(text)
        self.hotkeysSearchTextChanged.emit(text)

    def _apply_hotkeys_search_text(self) -> None:
        if not hasattr(self, "hotkeys_search"):
            return
        with QSignalBlocker(self.hotkeys_search):
            self.hotkeys_search.setText(self._hotkeys_search_text)
        self._filter_hotkeys_table(self._hotkeys_search_text)

    def hotkeys_search_text(self) -> str:
        return self._hotkeys_search_text

    def set_hotkeys_search_text(self, text: str) -> None:
        self._hotkeys_search_text = text
        self._apply_hotkeys_search_text()

    def _filter_hotkeys_table(self, query: str) -> None:
        if not hasattr(self, "_hotkeys_model"):
            return
        query_text = query.strip().casefold()
        for definition in HOTKEY_DEFINITIONS:
            row = self._hotkey_row_by_action_id.get(definition.action_id)
            if row is None:
                continue
            action_index = self._hotkeys_model.index(row, 0)
            shortcut_index = self._hotkeys_model.index(row, 1)
            note_index = self._hotkeys_model.index(row, 2)
            terms = " ".join(
                [
                    str(action_index.data() or "").casefold(),
                    str(shortcut_index.data() or "").casefold(),
                    str(note_index.data() or "").casefold(),
                ]
            )
            self.hotkeys_table.setRowHidden(row, query_text not in terms if query_text else False)

    def _on_hotkeys_reset_activated(self, index) -> None:  # noqa: ANN001
        if not index.isValid():
            return
        source_index = index
        model = index.model()
        if hasattr(model, "mapToSource"):
            source_index = model.mapToSource(index)
        row = source_index.row()
        if not (0 <= row < len(HOTKEY_DEFINITIONS)):
            return
        action_id = HOTKEY_DEFINITIONS[row].action_id
        self.reset_hotkey_to_default(action_id)

    def _on_category_changed(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        if index == 2:
            self._apply_hotkeys_search_text()
        self._update_mouse_movement_curve_layout()
        self._update_category_dirty_markers()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_widget = self.focusWidget()
            if not isinstance(
                focus_widget,
                (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit, QComboBox),
            ):
                event.ignore()
                return
        super().keyPressEvent(event)

    def preferences(self) -> DesktopPreferences:
        formatting = self._script_formatting_from_widgets()
        scripting = ScriptingSettings(
            language=self._script_language_from_widgets(),
            indent_width=formatting.indent_width,
            use_spaces=formatting.use_spaces,
            auto_indent=formatting.auto_indent,
            auto_format_on_save=formatting.auto_format_on_save,
        )
        editor_style = self._editor_style_values_from_widgets()
        dirty_style = self._dirty_indicator_values_from_model()
        return DesktopPreferences(
            appearance=AppearanceTheme(
                editor=EditorAppearanceTheme(
                    background=editor_style["editor_background"],
                    text=editor_style["editor_text"],
                    gutter_background=editor_style["gutter_background"],
                    gutter_text=editor_style["gutter_text"],
                    current_line_foreground=editor_style["current_line_foreground"],
                    current_line_highlight=editor_style["current_line_highlight"],
                ),
                dirty_indicators=DirtyIndicatorTheme(
                    text=dirty_style["dirty_text"],
                    accent=dirty_style["dirty_accent"],
                    background=dirty_style["dirty_background"],
                    selected_background=dirty_style["dirty_selected_background"],
                    border=dirty_style["dirty_border"],
                ),
                workspace_tab_attention=WorkspaceTabAttentionTheme(
                    enabled=self.workspace_tab_attention_enabled_checkbox.isChecked(),
                    accent=self.workspace_tab_attention_color_swatch.color(),
                ),
                syntax_highlighting=self._style_highlighting_from_widgets(),
            ),
            font=FontSettings(
                family=self.font_family_combo.currentFont().family(),
                size=self.font_size_spin.value(),
                weight=self.font_weight_spin.value(),
                line_spacing_multiplier=self.font_line_spacing_spin.value(),
            ),
            search_results=SearchResultsTheme(
                header_active=self.search_results_header_active_color.color(),
                header_hovered=self.search_results_header_hovered_color.color(),
                header_active_hovered=self.search_results_header_active_hovered_color.color(),
                header_radius=self.search_results_header_radius_edit.text().strip() or "4px",
                header_padding=self.search_results_header_padding_edit.text().strip() or "1px 4px",
                header_text=self.search_results_header_text_color.color(),
                line_text=self.search_results_line_text_color.color(),
                hit_text=self.search_results_hit_text_color.color(),
                child_border_color=self.search_results_child_border_color.color(),
                child_border_width=self.search_results_child_border_width_edit.text().strip() or "2px",
                child_padding_left=self.search_results_child_padding_left_spin.value(),
                child_margin_left=self.search_results_child_margin_left_spin.value(),
            ),
            scripting=scripting,
        )

    def playback_settings(self) -> DesktopPlaybackSettings:
        return DesktopPlaybackSettings(
            repeat_count=self.playback_repeat_spin.value(),
            step_mode=self.playback_step_checkbox.isChecked(),
            delay_ms=self.playback_delay_spin.value(),
            mouse_settle_ms=self.playback_mouse_settle_spin.value(),
            interruptible_sleep_chunk_ms=self.playback_interruptible_sleep_chunk_spin.value(),
            send_key_taps_instead_of_text=self.playback_send_key_taps_checkbox.isChecked(),
        )

    def recording_settings(self) -> DesktopRecordingSettings:
        return DesktopRecordingSettings(
            recording_conversion_mode=(
                self.recording_conversion_mode_combo.currentData() or "promote_generated"
            ),
            capture_mouse_moves=self.recording_capture_mouse_moves_checkbox.isChecked(),
            capture_mouse_buttons=self.recording_capture_mouse_buttons_checkbox.isChecked(),
            capture_mouse_wheel=self.recording_capture_mouse_wheel_checkbox.isChecked(),
            capture_keyboard=self.recording_capture_keyboard_checkbox.isChecked(),
            mouse_move_threshold_px=self.recording_mouse_move_threshold_spin.value(),
            exclude_main_window_during_recording=self.recording_exclude_main_window_checkbox.isChecked(),
        )

    def files_settings(self) -> DesktopFilesSettings:
        return self._files_settings_from_widgets()

    def diagnostics_settings(self) -> DesktopDiagnosticsSettings:
        return DesktopDiagnosticsSettings(
            enabled=self.diagnostics_enabled_checkbox.isChecked(),
            min_severity=str(self.diagnostics_min_severity_combo.currentData() or "info"),
            max_detail=str(self.diagnostics_max_detail_combo.currentData() or "summary"),
            log_to_file=self.diagnostics_file_checkbox.isChecked(),
            log_to_stdout=self.diagnostics_stdout_checkbox.isChecked(),
        )

    def runtime_settings(self) -> DesktopRuntimeSettings:
        return DesktopRuntimeSettings(
            max_loop_iterations=self.runtime_max_loop_iterations_spin.value(),
            max_call_depth=self.runtime_max_call_depth_spin.value(),
            default_mouse_move_speed=self.runtime_default_mouse_move_speed_spin.value(),
            show_mouse_movement_reference_curve=(
                self.runtime_mouse_movement_reference_checkbox.isChecked()
            ),
            mouse_movement_profile=self._mouse_movement_profile_from_widgets(),
        )

    def _mouse_movement_profile_from_widgets(self) -> MouseMovementProfile:
        model = self.runtime_mouse_movement_curve_model
        min_steps = self.runtime_mouse_movement_min_steps_spin.value()
        max_steps = self.runtime_mouse_movement_max_steps_spin.value()
        step_distance_px = self.runtime_mouse_movement_step_distance_px_spin.value()
        points: list[tuple[int, int, int]] = []
        for row, values in enumerate(model.rows()):
            try:
                speed = max(1, int(values.get("speed", 1)))
                duration_ms = int(values.get("duration_ms", 0))
            except (TypeError, ValueError):
                continue
            points.append((speed, duration_ms, row))

        if not points:
            return MouseMovementProfile()

        normalized_curve: list[tuple[int, int]] = []
        for speed, duration_ms, _row in sorted(points, key=lambda item: (item[0], item[2])):
            if normalized_curve and normalized_curve[-1][0] == speed:
                normalized_curve[-1] = (speed, duration_ms)
            else:
                normalized_curve.append((speed, duration_ms))

        try:
            return MouseMovementProfile(
                duration_curve=tuple(normalized_curve),
                min_steps=min_steps,
                max_steps=max_steps,
                step_distance_px=step_distance_px,
            )
        except ValueError:
            return MouseMovementProfile(
                min_steps=min_steps,
                max_steps=max_steps,
                step_distance_px=step_distance_px,
            )

    def settings_bundle(self) -> DesktopSettingsBundle:
        return DesktopSettingsBundle(
            application=DesktopApplicationSettings(
                restore_last_workspace=self.restore_workspace_checkbox.isChecked(),
                open_debug_tab_on_pause=self.open_debug_tab_on_pause_checkbox.isChecked(),
                show_summary_sidebar_on_left=self.show_summary_sidebar_checkbox.isChecked(),
                hidden_workspace_tabs_strip_collapsed=self.hidden_workspace_tabs_strip_collapsed_checkbox.isChecked(),
                show_analysis_tab=self.show_analysis_tab_checkbox.isChecked(),
                show_debug_tab=self.draft_bundle.application.show_debug_tab,
                show_formatted_preview_tab=self.show_formatted_preview_checkbox.isChecked(),
                show_raw_recordings_tab=self.show_raw_recordings_checkbox.isChecked(),
                show_diagnostics_tab=self.show_diagnostics_checkbox.isChecked(),
                last_workspace_path=self.draft_bundle.application.last_workspace_path,
                last_open_directory=self.draft_bundle.application.last_open_directory,
                go_to_last_mode=self.draft_bundle.application.go_to_last_mode,
                go_to_last_value=self.draft_bundle.application.go_to_last_value,
                go_to_last_geometry=self.draft_bundle.application.go_to_last_geometry,
                hotkeys=self.hotkeys(),
            ),
            playback=self.playback_settings(),
            recording=self.recording_settings(),
            files=self.files_settings(),
            diagnostics=self.diagnostics_settings(),
            runtime=self.runtime_settings(),
            theme=self.preferences(),
        )

    def _load_preferences_into_widgets(self, bundle: DesktopSettingsBundle) -> None:
        self.draft_bundle: DesktopSettingsBundle = bundle
        blockers = [
            QSignalBlocker(self.font_family_combo),
            QSignalBlocker(self.font_size_spin),
            QSignalBlocker(self.font_weight_spin),
            QSignalBlocker(self.font_line_spacing_spin),
            QSignalBlocker(self.scripting_language_combo),
            QSignalBlocker(self.scripting_extension_edit),
            QSignalBlocker(self.formatting_indent_spin),
            QSignalBlocker(self.formatting_use_spaces_checkbox),
            QSignalBlocker(self.formatting_auto_indent_checkbox),
            QSignalBlocker(self.formatting_auto_format_checkbox),
            QSignalBlocker(self.recording_autosave_checkbox),
            QSignalBlocker(self.recording_autosave_file_name_edit),
            QSignalBlocker(self.recording_autosave_timestamp_checkbox),
            QSignalBlocker(self.recording_autosave_folder_edit),
            QSignalBlocker(self.recording_raw_autosave_checkbox),
            QSignalBlocker(self.recording_raw_autosave_file_name_edit),
            QSignalBlocker(self.recording_raw_autosave_timestamp_checkbox),
            QSignalBlocker(self.recording_raw_autosave_folder_edit),
            QSignalBlocker(self.diagnostic_log_path_edit),
            QSignalBlocker(self.diagnostics_show_diagnostics_tab_checkbox),
            QSignalBlocker(self.diagnostics_enabled_checkbox),
            QSignalBlocker(self.diagnostics_min_severity_combo),
            QSignalBlocker(self.diagnostics_max_detail_combo),
            QSignalBlocker(self.diagnostics_file_checkbox),
            QSignalBlocker(self.diagnostics_stdout_checkbox),
            QSignalBlocker(self.restore_workspace_checkbox),
            QSignalBlocker(self.show_summary_sidebar_checkbox),
            QSignalBlocker(self.hidden_workspace_tabs_strip_collapsed_checkbox),
            QSignalBlocker(self.show_analysis_tab_checkbox),
            QSignalBlocker(self.open_debug_tab_on_pause_checkbox),
            QSignalBlocker(self.show_formatted_preview_checkbox),
            QSignalBlocker(self.show_raw_recordings_checkbox),
            QSignalBlocker(self.show_diagnostics_checkbox),
            QSignalBlocker(self.workspace_tab_attention_enabled_checkbox),
            QSignalBlocker(self.workspace_tab_attention_color_swatch),
            QSignalBlocker(self.playback_repeat_spin),
            QSignalBlocker(self.playback_step_checkbox),
            QSignalBlocker(self.playback_send_key_taps_checkbox),
            QSignalBlocker(self.playback_delay_spin),
            QSignalBlocker(self.playback_mouse_settle_spin),
            QSignalBlocker(self.playback_interruptible_sleep_chunk_spin),
            QSignalBlocker(self.recording_capture_mouse_moves_checkbox),
            QSignalBlocker(self.recording_capture_mouse_buttons_checkbox),
            QSignalBlocker(self.recording_capture_mouse_wheel_checkbox),
            QSignalBlocker(self.recording_capture_keyboard_checkbox),
            QSignalBlocker(self.recording_exclude_main_window_checkbox),
            QSignalBlocker(self.recording_conversion_mode_combo),
            QSignalBlocker(self.recording_mouse_move_threshold_spin),
            QSignalBlocker(self.runtime_max_loop_iterations_spin),
            QSignalBlocker(self.runtime_max_call_depth_spin),
            QSignalBlocker(self.runtime_default_mouse_move_speed_spin),
            QSignalBlocker(self.runtime_mouse_movement_reference_checkbox),
            QSignalBlocker(self.runtime_mouse_movement_min_steps_spin),
            QSignalBlocker(self.runtime_mouse_movement_max_steps_spin),
            QSignalBlocker(self.runtime_mouse_movement_step_distance_px_spin),
            QSignalBlocker(self.search_results_header_active_color),
            QSignalBlocker(self.search_results_header_hovered_color),
            QSignalBlocker(self.search_results_header_active_hovered_color),
            QSignalBlocker(self.search_results_header_text_color),
            QSignalBlocker(self.search_results_line_text_color),
            QSignalBlocker(self.search_results_hit_text_color),
            QSignalBlocker(self.search_results_child_border_color),
            QSignalBlocker(self.search_results_header_radius_edit),
            QSignalBlocker(self.search_results_header_padding_edit),
            QSignalBlocker(self.search_results_child_border_width_edit),
            QSignalBlocker(self.search_results_child_padding_left_spin),
            QSignalBlocker(self.search_results_child_margin_left_spin),
        ]
        _ = blockers
        self._load_application_preferences(bundle)
        self._load_playback_preferences(bundle)
        self._load_recording_preferences(bundle)
        self._load_files_preferences(bundle)
        self._load_diagnostics_preferences(bundle)
        self._load_runtime_preferences(bundle)
        self._load_appearance_preferences(bundle)
        self._load_script_language_preferences(bundle)
        self._load_hotkey_preferences(bundle)
        self._update_hotkey_conflicts()
        self._apply_hotkeys_search_text()
        self._emit_preferences_changed()

    def _load_application_preferences(self, bundle: DesktopSettingsBundle) -> None:
        self.restore_workspace_checkbox.setChecked(bundle.application.restore_last_workspace)
        self.show_summary_sidebar_checkbox.setChecked(
            bundle.application.show_summary_sidebar_on_left
        )
        self.hidden_workspace_tabs_strip_collapsed_checkbox.setChecked(
            bundle.application.hidden_workspace_tabs_strip_collapsed
        )
        self.show_analysis_tab_checkbox.setChecked(bundle.application.show_analysis_tab)
        self.open_debug_tab_on_pause_checkbox.setChecked(bundle.application.open_debug_tab_on_pause)
        self.show_formatted_preview_checkbox.setChecked(bundle.application.show_formatted_preview_tab)
        self.show_raw_recordings_checkbox.setChecked(bundle.application.show_raw_recordings_tab)
        self.show_diagnostics_checkbox.setChecked(bundle.application.show_diagnostics_tab)

    def _load_playback_preferences(self, bundle: DesktopSettingsBundle) -> None:
        playback = bundle.playback
        self.playback_repeat_spin.setValue(playback.repeat_count)
        self.playback_step_checkbox.setChecked(playback.step_mode)
        self.playback_send_key_taps_checkbox.setChecked(playback.send_key_taps_instead_of_text)
        self.playback_delay_spin.setValue(playback.delay_ms)
        self.playback_mouse_settle_spin.setValue(playback.mouse_settle_ms)
        self.playback_interruptible_sleep_chunk_spin.setValue(
            playback.interruptible_sleep_chunk_ms
        )

    def _load_recording_preferences(self, bundle: DesktopSettingsBundle) -> None:
        recording = bundle.recording
        self.recording_capture_mouse_moves_checkbox.setChecked(recording.capture_mouse_moves)
        self.recording_capture_mouse_buttons_checkbox.setChecked(recording.capture_mouse_buttons)
        self.recording_capture_mouse_wheel_checkbox.setChecked(recording.capture_mouse_wheel)
        self.recording_capture_keyboard_checkbox.setChecked(recording.capture_keyboard)
        self.recording_exclude_main_window_checkbox.setChecked(
            recording.exclude_main_window_during_recording
        )
        conversion_mode_index = self.recording_conversion_mode_combo.findData(
            recording.recording_conversion_mode
        )
        self.recording_conversion_mode_combo.setCurrentIndex(max(0, conversion_mode_index))
        self.recording_mouse_move_threshold_spin.setValue(recording.mouse_move_threshold_px)

    def _load_files_preferences(self, bundle: DesktopSettingsBundle) -> None:
        files = bundle.files
        with QSignalBlocker(self.scripting_extension_edit):
            self.scripting_extension_edit.setText(files.file_extension)
        self.recording_autosave_checkbox.setChecked(files.autosave_enabled)
        self.recording_autosave_file_name_edit.setText(files.autosave_file_name)
        self.recording_autosave_timestamp_checkbox.setChecked(files.autosave_timestamp_suffix)
        self.recording_autosave_folder_edit.setText(files.autosave_output_folder)
        self._update_recording_autosave_controls(files.autosave_enabled)
        self.recording_raw_autosave_checkbox.setChecked(files.raw_autosave_enabled)
        self.recording_raw_autosave_file_name_edit.setText(files.raw_autosave_file_name)
        self.recording_raw_autosave_timestamp_checkbox.setChecked(
            files.raw_autosave_timestamp_suffix
        )
        self.recording_raw_autosave_folder_edit.setText(files.raw_autosave_output_folder)
        self._update_recording_raw_autosave_controls(files.raw_autosave_enabled)
        self.diagnostic_log_path_edit.setText(files.diagnostic_log_path or "")
        self._update_file_output_previews()

    def _load_diagnostics_preferences(self, bundle: DesktopSettingsBundle) -> None:
        diagnostics = bundle.diagnostics
        self.set_diagnostics_tab_visible(bundle.application.show_diagnostics_tab)
        self.diagnostics_enabled_checkbox.setChecked(diagnostics.enabled)
        self._set_combo_data(self.diagnostics_min_severity_combo, diagnostics.min_severity)
        self._set_combo_data(self.diagnostics_max_detail_combo, diagnostics.max_detail)
        self.diagnostics_file_checkbox.setChecked(diagnostics.log_to_file)
        self.diagnostics_stdout_checkbox.setChecked(diagnostics.log_to_stdout)
        self._update_diagnostics_log_path_label()

    def _load_runtime_preferences(self, bundle: DesktopSettingsBundle) -> None:
        runtime = bundle.runtime
        self.runtime_max_loop_iterations_spin.setValue(runtime.max_loop_iterations)
        self.runtime_max_call_depth_spin.setValue(runtime.max_call_depth)
        self.runtime_default_mouse_move_speed_spin.setValue(runtime.default_mouse_move_speed)
        self.runtime_mouse_movement_reference_checkbox.setChecked(
            runtime.show_mouse_movement_reference_curve
        )
        self.runtime_mouse_movement_curve_preview.set_reference_curve_visible(
            runtime.show_mouse_movement_reference_curve
        )
        self._load_mouse_movement_curve_profile(runtime.mouse_movement_profile)

    def _load_appearance_preferences(self, bundle: DesktopSettingsBundle) -> None:
        editor = bundle.theme.appearance.editor
        self._set_editor_style_values(self._editor_style_values(editor))
        dirty = bundle.theme.appearance.dirty_indicators
        self._set_dirty_state_values(self._dirty_indicator_values(dirty))
        attention = bundle.theme.appearance.workspace_tab_attention
        self.workspace_tab_attention_enabled_checkbox.setChecked(attention.enabled)
        self.workspace_tab_attention_color_swatch.setColor(attention.accent)
        syntax = bundle.theme.appearance.syntax_highlighting
        self._set_style_values(self._style_values(syntax))
        search_results = bundle.theme.search_results
        self.search_results_header_active_color.setColor(search_results.header_active)
        self.search_results_header_hovered_color.setColor(search_results.header_hovered)
        self.search_results_header_active_hovered_color.setColor(search_results.header_active_hovered)
        self.search_results_header_text_color.setColor(search_results.header_text)
        self.search_results_line_text_color.setColor(search_results.line_text)
        self.search_results_hit_text_color.setColor(search_results.hit_text)
        self.search_results_child_border_color.setColor(search_results.child_border_color)
        self.search_results_header_radius_edit.setText(search_results.header_radius)
        self.search_results_header_padding_edit.setText(search_results.header_padding)
        self.search_results_child_border_width_edit.setText(search_results.child_border_width)
        self.search_results_child_padding_left_spin.setValue(search_results.child_padding_left)
        self.search_results_child_margin_left_spin.setValue(search_results.child_margin_left)
        self.font_family_combo.setCurrentFont(bundle.theme.font.to_qfont())
        self.font_size_spin.setValue(bundle.theme.font.size)
        self.font_weight_spin.setValue(bundle.theme.font.weight)
        self.font_line_spacing_spin.setValue(bundle.theme.font.line_spacing_multiplier)
        scripting = bundle.theme.scripting
        self.formatting_indent_spin.setValue(scripting.indent_width)
        self.formatting_use_spaces_checkbox.setChecked(scripting.use_spaces)
        self.formatting_auto_indent_checkbox.setChecked(scripting.auto_indent)
        self.formatting_auto_format_checkbox.setChecked(scripting.auto_format_on_save)

    def _load_script_language_preferences(self, bundle: DesktopSettingsBundle) -> None:
        scripting = bundle.theme.scripting
        with QSignalBlocker(self.scripting_language_combo):
            self.scripting_language_combo.setCurrentText(scripting.language)

    def _load_hotkey_preferences(self, bundle: DesktopSettingsBundle) -> None:
        hotkey_bindings = default_hotkey_bindings()
        bundle_bindings = bundle.application.hotkeys.bindings
        hotkey_bindings.update(bundle_bindings)
        if "search" in bundle_bindings and "find" not in bundle_bindings:
            hotkey_bindings["find"] = str(bundle_bindings["search"])
        if not hasattr(self, "_hotkeys_model"):
            return
        for definition in HOTKEY_DEFINITIONS:
            row = self._hotkey_row_by_action_id.get(definition.action_id)
            if row is None:
                continue
            index = self._hotkeys_model.index(row, 1)
            portable_text = self._hotkey_model_value(definition, hotkey_bindings.get(definition.action_id, ""))
            self._hotkeys_model.setData(index, portable_text, Qt.ItemDataRole.EditRole)

    def hotkeys(self) -> "DesktopHotkeySettings":
        bindings: dict[str, str] = {}
        for definition in HOTKEY_DEFINITIONS:
            row = self._hotkey_row_by_action_id.get(definition.action_id)
            if row is None or not hasattr(self, "_hotkeys_model"):
                continue
            index = self._hotkeys_model.index(row, 1)
            sequence_text = self._hotkey_model_value(definition, index.data())
            bindings[definition.action_id] = sequence_text
        return DesktopHotkeySettings(bindings=bindings)

    @property
    def draft_bundle(self) -> DesktopSettingsBundle:
        return self._draft_bundle

    @draft_bundle.setter
    def draft_bundle(self, value: DesktopSettingsBundle) -> None:
        self._draft_bundle = value

    @property
    def committed_bundle(self) -> DesktopSettingsBundle:
        return self._committed_bundle

    @committed_bundle.setter
    def committed_bundle(self, value: DesktopSettingsBundle) -> None:
        self._committed_bundle = value

    def set_preferences(self, bundle: DesktopSettingsBundle) -> None:
        self._loading_preferences = True
        with self._preferences_batch():
            try:
                incoming_bundle = copy.deepcopy(bundle)
                self._apply_preferences_bundle(incoming_bundle)
                self._committed_bundle = copy.deepcopy(self._capture_preferences_bundle())
                self._draft_bundle = copy.deepcopy(self._committed_bundle)
            finally:
                self._loading_preferences = False
        self._dirty = False
        self._refresh_preferences_ui_state()

    def set_open_debug_tab_on_pause(self, enabled: bool) -> None:
        if not hasattr(self, "open_debug_tab_on_pause_checkbox"):
            return
        with QSignalBlocker(self.open_debug_tab_on_pause_checkbox):
            self.open_debug_tab_on_pause_checkbox.setChecked(bool(enabled))
        if self._loading_preferences:
            return
        self._recompute_preferences_dirty()

    def set_debug_tab_visible(self, enabled: bool) -> None:
        _ = enabled

    def set_hidden_workspace_tabs_strip_collapsed(self, enabled: bool) -> None:
        if not hasattr(self, "hidden_workspace_tabs_strip_collapsed_checkbox"):
            return
        with QSignalBlocker(self.hidden_workspace_tabs_strip_collapsed_checkbox):
            self.hidden_workspace_tabs_strip_collapsed_checkbox.setChecked(bool(enabled))
        if hasattr(self, "draft_bundle"):
            self.draft_bundle.application.hidden_workspace_tabs_strip_collapsed = bool(enabled)
        if self._loading_preferences:
            return
        self._recompute_preferences_dirty()

    def set_analysis_tab_visible(self, enabled: bool) -> None:
        if not hasattr(self, "show_analysis_tab_checkbox"):
            return
        with QSignalBlocker(self.show_analysis_tab_checkbox):
            self.show_analysis_tab_checkbox.setChecked(bool(enabled))
        if self._loading_preferences:
            return
        self._recompute_preferences_dirty()

    def set_diagnostics_tab_visible(self, enabled: bool) -> None:
        if not hasattr(self, "show_diagnostics_checkbox") or not hasattr(
            self, "diagnostics_show_diagnostics_tab_checkbox"
        ):
            return
        with QSignalBlocker(self.show_diagnostics_checkbox), QSignalBlocker(
            self.diagnostics_show_diagnostics_tab_checkbox
        ):
            self.show_diagnostics_checkbox.setChecked(bool(enabled))
            self.diagnostics_show_diagnostics_tab_checkbox.setChecked(bool(enabled))
        if self._loading_preferences:
            return
        self._recompute_preferences_dirty()

    def _sync_analysis_tab_visibility_toggled(self, enabled: bool) -> None:
        self.set_analysis_tab_visible(bool(enabled))

    def _sync_diagnostics_tab_visibility_toggled(self, enabled: bool) -> None:
        self.set_diagnostics_tab_visible(bool(enabled))

    def _emit_preferences_changed(self, *args) -> None:
        if self._loading_preferences:
            return
        if self._preferences_batch_depth > 0:
            return
        self._recompute_preferences_dirty()

    def _update_theme_readability_warning(self) -> None:
        if not hasattr(self, "theme_readability_warning_label"):
            return
        issues = validate_desktop_preferences_readability(self.preferences())
        if issues:
            self.theme_readability_warning_label.setVisible(True)
            self.theme_readability_warning_label.setText(
                "Theme contrast is too low to save safely"
                if len(issues) == 1
                else f"Theme contrast is too low to save safely ({len(issues)} issues)"
            )
            self.theme_readability_warning_label.setToolTip("\n".join(issues))
        else:
            self.theme_readability_warning_label.clear()
            self.theme_readability_warning_label.setVisible(False)
            self.theme_readability_warning_label.setToolTip("")

    def _reset_placeholder_section(self, section_name: str) -> None:
        # Placeholder sections do not yet own editable values.
        _ = section_name
        return

    def _style_highlighting_from_widgets(self) -> SyntaxHighlightTheme:
        if not hasattr(self, "style_model"):
            return SyntaxHighlightTheme()
        values = self._style_values_from_model()
        return SyntaxHighlightTheme(
            keyword=values["keyword"],
            string=values["string"],
            comment=values["comment"],
            number=values["number"],
        )

    def _style_values_from_model(self) -> dict[str, str]:
        if not hasattr(self, "style_model"):
            return {
                field_name: default_color
                for _label, field_name, default_color in self._style_fields
            }
        return {
            "keyword": str(
                self.style_model.index(0, 1).data(Qt.ItemDataRole.DisplayRole) or "#005cc5"
            ).lower(),
            "string": str(
                self.style_model.index(1, 1).data(Qt.ItemDataRole.DisplayRole) or "#0b7a75"
            ).lower(),
            "comment": str(
                self.style_model.index(2, 1).data(Qt.ItemDataRole.DisplayRole) or "#6a737d"
            ).lower(),
            "number": str(
                self.style_model.index(3, 1).data(Qt.ItemDataRole.DisplayRole) or "#b31d28"
            ).lower(),
        }

    def _on_style_color_changed(self, row: int, column: int, color: str) -> None:
        _ = (row, column, color)
        if self._loading_preferences:
            return
        self._emit_preferences_changed()

    def _script_language_from_widgets(self) -> str:
        if not hasattr(self, "scripting_language_combo"):
            return "ActionShellScript"
        return self.scripting_language_combo.currentText()

    def _script_formatting_from_widgets(self) -> ScriptingSettings:
        if not hasattr(self, "formatting_indent_spin"):
            return ScriptingSettings()
        return ScriptingSettings(
            language="ActionShellScript",
            indent_width=self.formatting_indent_spin.value(),
            use_spaces=self.formatting_use_spaces_checkbox.isChecked(),
            auto_indent=self.formatting_auto_indent_checkbox.isChecked(),
            auto_format_on_save=self.formatting_auto_format_checkbox.isChecked(),
        )

    def _files_settings_from_widgets(self) -> DesktopFilesSettings:
        if not hasattr(self, "scripting_extension_edit"):
            return DesktopFilesSettings()
        return DesktopFilesSettings(
            file_extension=self.scripting_extension_edit.text().strip() or ".ass",
            autosave_enabled=self.recording_autosave_checkbox.isChecked(),
            autosave_file_name=self.recording_autosave_file_name_edit.text().strip() or "recording",
            autosave_timestamp_suffix=self.recording_autosave_timestamp_checkbox.isChecked(),
            autosave_output_folder=self.recording_autosave_folder_edit.text().strip(),
            raw_autosave_enabled=self.recording_raw_autosave_checkbox.isChecked(),
            raw_autosave_file_name=(
                self.recording_raw_autosave_file_name_edit.text().strip() or "recording"
            ),
            raw_autosave_timestamp_suffix=self.recording_raw_autosave_timestamp_checkbox.isChecked(),
            raw_autosave_output_folder=self.recording_raw_autosave_folder_edit.text().strip(),
            diagnostic_log_path=self.diagnostic_log_path_edit.text().strip() or None,
        )

    def reset_hotkey_to_default(self, action_id: str) -> None:
        if not hasattr(self, "_hotkeys_model"):
            return
        row = self._hotkey_row_by_action_id.get(action_id)
        if row is None:
            return
        default_value = self._hotkey_default_sequences.get(action_id, "")
        index = self._hotkeys_model.index(row, 1)
        self._hotkeys_model.setData(
            index,
            self._hotkey_model_value(action_id, default_value),
            Qt.ItemDataRole.EditRole,
        )

    def reset_hotkeys_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("hotkeys")

    def reset_playback_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("playback")

    def reset_recording_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("recording")

    def reset_files_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("files")

    def reset_diagnostics_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("diagnostics")

    def reset_debug_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("debug")

    def _resolve_files_preview_base_directory(self, parent: QWidget | None) -> Path:
        if parent is not None:
            settings_service = getattr(parent, "_settings_service", None)
            config_dir = getattr(settings_service, "config_dir", None)
            if config_dir is not None:
                return Path(config_dir)
        return DesktopSettingsService().config_dir

    def _recording_output_base_directory(self) -> Path:
        config_dir = self._files_preview_base_directory
        if config_dir.name == "config":
            return config_dir.parent
        return config_dir

    def _resolve_files_preview_folder(self, folder: str) -> Path:
        folder = str(folder).strip()
        if not folder:
            return self._recording_output_base_directory() / "recordings"

        candidate = Path(folder).expanduser()
        if candidate.is_absolute():
            return candidate
        return self._recording_output_base_directory() / candidate

    def _on_recording_autosave_toggled(self, enabled: bool) -> None:
        self._update_recording_autosave_controls(enabled)
        self._update_file_output_previews()
        self._emit_preferences_changed()

    def _update_recording_autosave_controls(self, enabled: bool) -> None:
        self.recording_autosave_file_name_edit.setEnabled(enabled)
        self.recording_autosave_timestamp_checkbox.setEnabled(enabled)
        self.recording_autosave_folder_edit.setEnabled(enabled)
        self.recording_autosave_browse_button.setEnabled(enabled)

    def _on_recording_raw_autosave_toggled(self, enabled: bool) -> None:
        self._update_recording_raw_autosave_controls(enabled)
        self._update_file_output_previews()
        self._emit_preferences_changed()

    def _update_recording_raw_autosave_controls(self, enabled: bool) -> None:
        self.recording_raw_autosave_file_name_edit.setEnabled(enabled)
        self.recording_raw_autosave_timestamp_checkbox.setEnabled(enabled)
        self.recording_raw_autosave_folder_edit.setEnabled(enabled)
        self.recording_raw_autosave_browse_button.setEnabled(enabled)

    def _update_file_output_previews(self) -> None:
        if hasattr(self, "raw_autosave_preview_label"):
            raw_name = self.recording_raw_autosave_file_name_edit.text().strip() or "recording"
            if self.recording_raw_autosave_timestamp_checkbox.isChecked():
                raw_name = f"{raw_name}[-timestamp]"
            if self.recording_raw_autosave_checkbox.isChecked():
                raw_resolved_folder = self._resolve_files_preview_folder(
                    self.recording_raw_autosave_folder_edit.text().strip()
                )
                self.raw_autosave_preview_label.setText(
                    f"Raw recording will be saved as: {raw_resolved_folder}/{raw_name}.json"
                )
            else:
                self.raw_autosave_preview_label.setText(
                    "Raw recording autosave is disabled. No file will be saved automatically."
                )
        if hasattr(self, "converted_autosave_preview_label"):
            name = self.recording_autosave_file_name_edit.text().strip() or "recording"
            extension = self.scripting_extension_edit.text().strip() or ".ass"
            if not extension.startswith("."):
                extension = f".{extension.lstrip('.')}"
            if self.recording_autosave_timestamp_checkbox.isChecked():
                name = f"{name}[-timestamp]"
            if self.recording_autosave_checkbox.isChecked():
                resolved_folder = self._resolve_files_preview_folder(
                    self.recording_autosave_folder_edit.text().strip()
                )
                self.converted_autosave_preview_label.setText(
                    f"Converted script will be saved as: {resolved_folder}/{name}{extension}"
                )
            else:
                self.converted_autosave_preview_label.setText(
                    "Converted script autosave is disabled. No file will be saved automatically."
                )
        self._update_diagnostics_log_path_label()

    def _update_diagnostics_log_path_label(self) -> None:
        if not hasattr(self, "diagnostics_log_path_label"):
            return
        raw_path = self.diagnostic_log_path_edit.text().strip() if hasattr(
            self, "diagnostic_log_path_edit"
        ) else ""
        if raw_path:
            candidate = Path(raw_path).expanduser()
            if candidate.is_absolute():
                resolved = candidate.resolve()
            else:
                resolved = self._files_preview_base_directory / candidate
        else:
            resolved = resolve_diagnostic_log_path()
        if hasattr(self, "diagnostics_log_preview_label"):
            self.diagnostics_log_preview_label.setText(
                f"Diagnostics log will be saved as: {resolved}"
            )
        self.diagnostics_log_path_label.setText(str(resolved))

    def _update_configuration_file_labels(self) -> None:
        if not hasattr(self, "configuration_directory_label"):
            return
        config_dir = self._resolve_files_preview_base_directory(self.parentWidget())
        self.configuration_directory_label.setText(self._soft_break_path_text(config_dir))
        self.configuration_directory_label.setToolTip(str(config_dir))
        settings_path = config_dir / "desktop_settings.json"
        self.configuration_settings_path_label.setText("desktop_settings.json")
        self.configuration_settings_path_label.setToolTip(str(settings_path))

    @staticmethod
    def _soft_break_path_text(path: Path) -> str:
        return str(path).replace("\\", "\\\u200b").replace("/", "/\u200b")

    def _choose_recording_autosave_folder(self) -> None:
        start_dir = str(
            self._resolve_files_preview_folder(self.recording_autosave_folder_edit.text().strip())
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Converted Script Folder",
            start_dir,
        )
        if not folder:
            return
        self.recording_autosave_folder_edit.setText(folder)
        self._update_file_output_previews()
        self._emit_preferences_changed()

    def _choose_recording_raw_autosave_folder(self) -> None:
        start_dir = str(
            self._resolve_files_preview_folder(
                self.recording_raw_autosave_folder_edit.text().strip()
            )
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Raw Recording Folder",
            start_dir,
        )
        if not folder:
            return
        self.recording_raw_autosave_folder_edit.setText(folder)
        self._update_file_output_previews()
        self._emit_preferences_changed()

    def reset_appearance_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("appearance")

    def reset_editor_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("editor")

    def reset_workspace_tabs_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("workspace_tabs")

    def reset_search_results_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("search_results")

    def reset_search_spacing_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("search_spacing")

    def reset_text_editor_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("text_editor")

    def reset_programming_language_settings_to_defaults(self) -> None:
        self.reset_script_language_settings_to_defaults()

    def reset_formatting_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("formatting")

    def reset_style_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("style")

    def reset_script_language_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("scripting")

    def reset_execution_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("runtime")

    def reset_runtime_settings_to_defaults(self) -> None:
        self.reset_execution_settings_to_defaults()

    def _resolve_diagnostic_log_start_path(self) -> Path:
        raw_path = self.diagnostic_log_path_edit.text().strip()
        if not raw_path:
            return resolve_diagnostic_log_path()

        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate
        return self._files_preview_base_directory / candidate

    def _choose_diagnostic_log_path(self) -> None:
        start_file = self._resolve_diagnostic_log_start_path()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Diagnostics Log File",
            str(start_file),
            "Log Files (*.log);;All Files (*.*)",
        )
        if not selected_path:
            return
        self.diagnostic_log_path_edit.setText(selected_path)

    def _open_configuration_folder(self) -> None:
        config_dir = self._resolve_files_preview_base_directory(self.parentWidget())
        resolved_dir = config_dir.resolve()
        if not resolved_dir.exists():
            choice = QMessageBox.question(
                self,
                "Configuration folder",
                f"The configuration folder does not exist yet:\n{resolved_dir}\n\n"
                "Create it now and open it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            resolved_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(resolved_dir))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved_dir)))

    def _delete_configuration_file(self) -> None:
        config_dir = self._resolve_files_preview_base_directory(self.parentWidget())
        settings_path = (config_dir / "desktop_settings.json").resolve()
        if not settings_path.exists():
            QMessageBox.information(
                self,
                "Configuration file",
                f"The configuration file does not exist yet:\n{settings_path}",
                QMessageBox.StandardButton.Ok,
            )
            return
        choice = QMessageBox.question(
            self,
            "Delete configuration file",
            f"Delete this configuration file?\n{settings_path}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        settings_path.unlink()

    def reset_all_settings_to_defaults(self) -> None:
        self._restore_section_to_defaults("all")

    def _update_hotkey_conflicts(self) -> None:
        if not hasattr(self, "_hotkeys_model"):
            return
        bindings: dict[str, list[tuple[str, str]]] = {}
        for definition in HOTKEY_DEFINITIONS:
            row = self._hotkey_row_by_action_id.get(definition.action_id)
            if row is None:
                continue
            sequence_text = str(self._hotkeys_model.index(row, 1).data() or "").strip()
            if not sequence_text:
                continue
            normalized = normalized_hotkey_binding(sequence_text)
            bindings.setdefault(normalized, []).append((definition.action_id, sequence_text))

        conflicts = self._hotkey_conflict_action_ids(bindings)

        if conflicts:
            self.hotkeys_warning_label.setVisible(True)
            self.hotkeys_warning_label.setText(
                "Shortcut conflict detected. More than one action uses the same key sequence."
            )
            self.hotkeys_save_warning_label.setVisible(True)
        else:
            self.hotkeys_warning_label.clear()
            self.hotkeys_warning_label.setVisible(False)
            self.hotkeys_save_warning_label.clear()
            self.hotkeys_save_warning_label.setText("Resolve hotkey conflicts before saving")
            self.hotkeys_save_warning_label.setVisible(False)

        self._apply_hotkey_conflict_styles(bindings, conflicts)
        self._apply_hotkeys_search_text()
        if hasattr(self, "hotkeys_table"):
            self.hotkeys_table.viewport().update()
            self.hotkeys_table.viewport().repaint()

    def _hotkey_conflict_action_ids(
        self,
        bindings: dict[str, list[tuple[str, str]]],
    ) -> set[str]:
        return {
            action_id
            for action_pairs in bindings.values()
            if len(action_pairs) > 1
            for action_id, _ in action_pairs
        }

    def _apply_hotkey_conflict_styles(
        self,
        bindings: dict[str, list[tuple[str, str]]],
        conflicts: set[str],
    ) -> None:
        with QSignalBlocker(self._hotkeys_model):
            for definition in HOTKEY_DEFINITIONS:
                row = self._hotkey_row_by_action_id.get(definition.action_id)
                if row is None:
                    continue
                self._apply_hotkey_conflict_style_for_row(
                    definition.action_id,
                    row,
                    definition.help_text or "",
                    bindings,
                    conflicts,
                )

    def _apply_hotkey_conflict_style_for_row(
        self,
        action_id: str,
        row: int,
        help_text: str,
        bindings: dict[str, list[tuple[str, str]]],
        conflicts: set[str],
    ) -> None:
        is_conflict = action_id in conflicts
        background_value = QColor("#fff2cc") if is_conflict else QColor()
        for column in range(4):
            self._hotkeys_model.setData(
                self._hotkeys_model.index(row, column),
                background_value,
                Qt.ItemDataRole.BackgroundRole,
            )
        note_index = self._hotkeys_model.index(row, 2)
        if is_conflict:
            row_sequence_portable = str(self._hotkeys_model.index(row, 1).data() or "").strip()
            row_sequence_display = display_hotkey_clauses(row_sequence_portable)
            row_sequence_native = QKeySequence(row_sequence_portable).toString(
                QKeySequence.SequenceFormat.NativeText
            ).strip()
            if not row_sequence_native:
                row_sequence_native = row_sequence_display or row_sequence_portable
            other_actions = [
                f"{item.label} ({row_sequence_native})"
                for item in HOTKEY_DEFINITIONS
                for conflict_action_id, sequence_text in bindings.get(
                    normalized_hotkey_binding(row_sequence_portable),
                    [],
                )
                if item.action_id == conflict_action_id and item.action_id != action_id
            ]
            conflict_text = (
                "Already used by " + ", ".join(other_actions)
                if other_actions
                else "Shortcut conflict"
            )
            self._hotkeys_model.setData(note_index, conflict_text, Qt.ItemDataRole.EditRole)
        else:
            self._hotkeys_model.setData(
                note_index,
                help_text,
                Qt.ItemDataRole.EditRole,
            )

    def _hotkey_model_value(self, definition_or_action_id: object, value: object) -> str:
        definition = definition_or_action_id
        if isinstance(definition_or_action_id, str):
            definition = next(
                (item for item in HOTKEY_DEFINITIONS if item.action_id == definition_or_action_id),
                None,
            )

        sequence_text = str(value or "").strip()
        if getattr(definition, "supports_alternates", False):
            return sequence_text
        return QKeySequence(sequence_text).toString(QKeySequence.SequenceFormat.PortableText)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._update_mouse_movement_curve_layout()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_mouse_movement_curve_layout()

    def mark_saved(self) -> None:
        self._dirty = False
        self._committed_bundle = copy.deepcopy(self._capture_preferences_bundle())
        self._draft_bundle = copy.deepcopy(self._committed_bundle)
        self._update_dirty_indicator()
        self._update_appearance_item_markers()
        self._update_category_dirty_markers()

    def is_dirty(self) -> bool:
        return self._dirty

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._dirty:
            event.accept()
            return

        choice = question_save_discard_cancel(
            self,
            "Preferences",
            "Save preferences before closing?",
        )
        if choice == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if choice == QMessageBox.StandardButton.Save:
            parent = self.parent()
            if parent is not None and hasattr(parent, "save_preferences"):
                if not cast(_PreferencesHost, parent).save_preferences():
                    event.ignore()
                    return
            else:
                self.saveRequested.emit()
        elif choice == QMessageBox.StandardButton.Discard:
            self.discardRequested.emit()
        event.accept()

    def _update_dirty_indicator(self) -> None:
        self.dirty_indicator_label.setVisible(self._dirty)
        self.setWindowTitle("Preferences *" if self._dirty else "Preferences")
        dirty_theme = self.draft_bundle.theme.appearance.dirty_indicators
        self.dirty_indicator_label.setStyleSheet(
            "QLabel {"
            " color: %s;"
            " font-size: 11px;"
            " font-weight: 700;"
            " padding: 2px 8px;"
            " border: 1px solid %s;"
            " border-radius: 9px;"
            " background-color: %s;"
            " }"
            % (dirty_theme.text, dirty_theme.border, dirty_theme.background)
        )

    def _update_category_dirty_markers(self) -> None:
        dirty_theme = self.draft_bundle.theme.appearance.dirty_indicators
        section_dirty = self._section_snapshot_map(self.draft_bundle).diff(
            self._section_snapshot_map(self.committed_bundle)
        )
        selected_row = self.category_list.currentRow()
        for index, title in enumerate(self._category_titles):
            item = self.category_list.item(index)
            if item is None:
                continue
            is_dirty = {
                "General": section_dirty.general,
                "Debug": section_dirty.debug,
                "Editing": (
                    section_dirty.appearance_editor
                    or section_dirty.appearance_syntax
                    or section_dirty.script
                ),
                "Workspace": (
                    section_dirty.workspace_tabs
                    or section_dirty.appearance_dirty_state
                    or section_dirty.appearance_tab_attention
                    or section_dirty.search_results_colors
                    or section_dirty.search_results_spacing
                ),
                "Playback": section_dirty.playback,
                "Recording": section_dirty.recording,
                "Files": section_dirty.files,
                "Diagnostics": section_dirty.diagnostics,
                "Hotkeys": section_dirty.hotkeys,
                "Runtime": section_dirty.runtime,
            }.get(title, False)
            item.setText(f"! {title}" if is_dirty else title)
            item.setIcon(
                self._dirty_marker_icon(dirty_theme) if is_dirty else QIcon()
            )
            item.setToolTip("Unsaved changes" if is_dirty else title)
            font = item.font()
            font.setBold(is_dirty)
            item.setFont(font)
            item.setForeground(QColor(dirty_theme.text) if is_dirty else QBrush())
            if is_dirty:
                item.setBackground(
                    QColor(dirty_theme.selected_background)
                    if index == selected_row
                    else QColor(dirty_theme.background)
                )
            else:
                item.setBackground(QBrush())
            header_frame = self._page_header_frames.get(title)
            if header_frame is not None:
                if is_dirty:
                    header_frame.setStyleSheet(
                        "#preferencesPageHeader {"
                        " background-color: %s;"
                        " border: 1px solid %s;"
                        " border-radius: 10px;"
                        " }"
                        % (
                            dirty_theme.selected_background
                            if index == selected_row
                            else dirty_theme.background,
                            dirty_theme.border,
                        )
                    )
                else:
                    header_frame.setStyleSheet(
                        "#preferencesPageHeader { border: 1px solid transparent; border-radius: 10px; }"
                    )

    def _update_appearance_item_markers(self) -> None:
        dirty_theme = self.draft_bundle.theme.appearance.dirty_indicators
        section_dirty = self._section_snapshot_map(self.draft_bundle).diff(
            self._section_snapshot_map(self.committed_bundle)
        )
        if hasattr(self, "_text_editor_item_list"):
            text_editor_item_dirty = [
                section_dirty.appearance_editor,
                section_dirty.appearance_editor,
                section_dirty.script,
                section_dirty.script,
                section_dirty.script,
                section_dirty.script,
            ]
            selected_text_editor_item = self._text_editor_item_list.currentRow()
            for index, title in enumerate(self._text_editor_item_titles):
                dirty = text_editor_item_dirty[index]
                item = self._text_editor_item_list.item(index)
                if item is None:
                    continue
                item.setText(f"! {title}" if dirty else title)
                item.setToolTip("Unsaved changes" if dirty else title)
                item.setIcon(self._dirty_marker_icon(dirty_theme) if dirty else QIcon())
                item.setForeground(QColor(dirty_theme.accent) if dirty else QBrush())
                item.setBackground(
                    QColor(dirty_theme.selected_background)
                    if dirty and index == selected_text_editor_item
                    else QColor(dirty_theme.background)
                    if dirty
                    else QBrush()
                )
        if hasattr(self, "appearance_item_list"):
            appearance_item_dirty = [
                section_dirty.appearance_dirty_state or section_dirty.appearance_tab_attention,
                section_dirty.workspace_tabs,
                section_dirty.search_results_colors,
                section_dirty.search_results_spacing,
            ]
            selected_item = self.appearance_item_list.currentRow()
            for index, title in enumerate(self._appearance_item_titles):
                dirty = appearance_item_dirty[index]
                item = self.appearance_item_list.item(index)
                if item is None:
                    continue
                item.setText(f"! {title}" if dirty else title)
                item.setToolTip("Unsaved changes" if dirty else title)
                item.setIcon(self._dirty_marker_icon(dirty_theme) if dirty else QIcon())
                item.setForeground(QColor(dirty_theme.accent) if dirty else QBrush())
                item.setBackground(
                    QColor(dirty_theme.selected_background)
                    if dirty and index == selected_item
                    else QColor(dirty_theme.background)
                    if dirty
                    else QBrush()
                )

    def _dirty_marker_icon(self, dirty_theme: DirtyIndicatorTheme) -> QIcon:
        cache_key = (dirty_theme.accent, dirty_theme.background, dirty_theme.border, dirty_theme.selected_background)
        cache = getattr(self, "_dirty_marker_icon_cache", None)
        if cache is None:
            cache = {}
            self._dirty_marker_icon_cache = cache
        icon = cache.get(cache_key)
        if icon is not None:
            return icon
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = None
        try:
            from PySide6.QtGui import QPainter

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QColor(dirty_theme.border))
            painter.setBrush(QColor(dirty_theme.selected_background))
            painter.drawRoundedRect(1, 1, 12, 12, 4, 4)
            painter.setPen(QColor(dirty_theme.accent))
            painter.setBrush(QColor(dirty_theme.accent))
            painter.drawEllipse(4, 4, 6, 6)
        finally:
            if painter is not None:
                painter.end()
        icon = QIcon(pixmap)
        cache[cache_key] = icon
        return icon
