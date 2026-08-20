from __future__ import annotations

from collections.abc import Callable, Sequence

import qtawesome as qta
from PySide6.QtCore import QEvent, QModelIndex, Qt, Signal, QSize, QRect
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QComboBox,
    QColorDialog,
    QApplication,
    QHBoxLayout,
    QKeySequenceEdit,
    QLineEdit,
    QStyle,
    QStyleOptionViewItem,
    QToolButton,
    QStyledItemDelegate,
    QSpinBox,
    QWidget,
)

from .schema import CellStyle, CellValue, ColumnSpec


def contrast_color(color: str) -> str:
    hex_color = color.lstrip("#")
    if len(hex_color) != 6:
        return "#000000"
    try:
        red = int(hex_color[0:2], 16)
        green = int(hex_color[2:4], 16)
        blue = int(hex_color[4:6], 16)
    except ValueError:
        return "#000000"
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#000000" if luminance > 160 else "#ffffff"


def color_cell_value(color: str, *, font_family: str = "Consolas") -> CellValue:
    normalized = color.upper()
    return CellValue(
        normalized,
        CellStyle(
            background=color,
            foreground=contrast_color(color),
            font_family=font_family,
        ),
    )


class ColorCellDelegate(QStyledItemDelegate):
    """Open a color chooser when the user clicks a color cell."""

    def __init__(
        self,
        on_color_changed: Callable[[int, int, str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_color_changed = on_color_changed

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        current_text = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        if not current_text:
            return False
        current_color = QColor(current_text)
        if not current_color.isValid():
            current_color = QColor("#000000")
        chosen = QColorDialog.getColor(current_color, option.widget, "Choose Color")
        if not chosen.isValid():
            return True
        hex_color = chosen.name().upper()
        model.setData(index, hex_color, Qt.ItemDataRole.EditRole)
        model.setData(index, chosen, Qt.ItemDataRole.BackgroundRole)
        model.setData(index, QColor(contrast_color(hex_color)), Qt.ItemDataRole.ForegroundRole)
        self._on_color_changed(index.row(), index.column(), hex_color)
        return True

    def initStyleOption(self, option, index) -> None:  # noqa: ANN001
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter


class _HotkeyCaptureEdit(QKeySequenceEdit):
    """Capture one shortcut at a time with clear and ignore rules."""

    _blocked_standard_keys = (
        QKeySequence.StandardKey.Copy,
        QKeySequence.StandardKey.Cut,
        QKeySequence.StandardKey.Paste,
        QKeySequence.StandardKey.Undo,
        QKeySequence.StandardKey.Redo,
        QKeySequence.StandardKey.SelectAll,
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def clear(self) -> None:  # noqa: A003
        super().clear()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) and event.modifiers() in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            self.clear()
            self.editingFinished.emit()
            return
        if any(event.matches(key) for key in self._blocked_standard_keys):
            return
        if event.key() in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return
        super().keyPressEvent(event)
        self.editingFinished.emit()


class HotkeySequenceEdit(QWidget):
    """Capture one shortcut at a time with a visible clear affordance."""

    editingFinished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._line_edit = _HotkeyCaptureEdit(self)
        self._line_edit.editingFinished.connect(self.editingFinished.emit)

        self._clear_button = QToolButton(self)
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_button.setToolTip("Clear shortcut")
        self._clear_button.setAccessibleName("Clear shortcut")
        self._clear_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._clear_button.setAutoRaise(True)
        self._clear_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton)
        )
        self._clear_button.setIconSize(QSize(12, 12))
        self._clear_button.setFixedWidth(20)
        self._clear_button.setStyleSheet(
            "QToolButton { padding: 0; margin: 0; border: 0; }"
        )
        self._clear_button.clicked.connect(self._clear_and_finish)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._line_edit, 1)
        layout.addWidget(self._clear_button, 0)
        self.setFocusProxy(self._line_edit)

    def _clear_and_finish(self) -> None:
        self._line_edit.clear()
        self.editingFinished.emit()

    def keySequence(self) -> QKeySequence:
        return self._line_edit.keySequence()

    def setKeySequence(self, sequence) -> None:  # noqa: ANN001
        self._line_edit.setKeySequence(sequence)

    def clear(self) -> None:  # noqa: A003
        self._line_edit.clear()


class HotkeyTextEdit(QWidget):
    """Capture alternate hotkey text with a visible clear affordance."""

    editingFinished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._line_edit = QLineEdit(self)
        self._line_edit.editingFinished.connect(self.editingFinished.emit)

        self._clear_button = QToolButton(self)
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_button.setToolTip("Clear shortcut")
        self._clear_button.setAccessibleName("Clear shortcut")
        self._clear_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._clear_button.setAutoRaise(True)
        self._clear_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton)
        )
        self._clear_button.setIconSize(QSize(12, 12))
        self._clear_button.setFixedWidth(20)
        self._clear_button.setStyleSheet(
            "QToolButton { padding: 0; margin: 0; border: 0; }"
        )
        self._clear_button.clicked.connect(self._clear_and_finish)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._line_edit, 1)
        layout.addWidget(self._clear_button, 0)
        self.setFocusProxy(self._line_edit)

    def _clear_and_finish(self) -> None:
        self._line_edit.clear()
        self.editingFinished.emit()

    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, text: str) -> None:  # noqa: N802
        self._line_edit.setText(text)

    def clear(self) -> None:  # noqa: A003
        self._line_edit.clear()


class KeySequenceDelegate(QStyledItemDelegate):
    """Edit hotkey cells with ``QKeySequenceEdit`` or alternate text input."""

    def __init__(
        self,
        parent=None,
        *,
        text_row_predicate: Callable[[QModelIndex], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._text_row_predicate = text_row_predicate

    def _use_text_editor(self, index: QModelIndex) -> bool:
        if self._text_row_predicate is None:
            return False
        return self._text_row_predicate(index)

    def createEditor(self, parent, option, index):  # noqa: ANN001
        editor = HotkeyTextEdit(parent) if self._use_text_editor(index) else HotkeySequenceEdit(parent)
        finished = False

        def commit_and_close() -> None:
            nonlocal finished
            if finished:
                return
            finished = True
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)

        editor.editingFinished.connect(commit_and_close)
        return editor

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if option.widget is None:
            return False
        if index.flags() & Qt.ItemFlag.ItemIsEditable:
            option.widget.edit(index)
            return True
        return False

    def setEditorData(self, editor, index) -> None:  # noqa: ANN001
        sequence_text = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        if self._use_text_editor(index):
            editor.setText(sequence_text)
            return
        editor.setKeySequence(QKeySequence(sequence_text))

    def setModelData(self, editor, model, index) -> None:  # noqa: ANN001
        if self._use_text_editor(index):
            sequence_text = editor.text().strip()
        else:
            sequence_text = editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        model.setData(index, sequence_text, Qt.ItemDataRole.EditRole)


class ComboBoxDelegate(QStyledItemDelegate):
    """Edit a table cell with a combo box populated from column choices."""

    def __init__(
        self,
        choices: Sequence[str] | Callable[[], Sequence[str]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._choices = choices

    def _resolve_choices(self) -> list[str]:
        if callable(self._choices):
            return [str(choice) for choice in self._choices()]
        return [str(choice) for choice in self._choices]

    def createEditor(self, parent, option, index):  # noqa: ANN001
        editor = QComboBox(parent)
        editor.setEditable(True)
        for choice in self._resolve_choices():
            editor.addItem(choice)
        return editor

    def setEditorData(self, editor, index) -> None:  # noqa: ANN001
        current_text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if current_text and editor.findText(current_text) == -1:
            editor.addItem(current_text)
        editor.setCurrentText(current_text)

    def setModelData(self, editor, model, index) -> None:  # noqa: ANN001
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class SpinBoxDelegate(QStyledItemDelegate):
    """Edit a table cell with a ``QSpinBox``."""

    def createEditor(self, parent, option, index):  # noqa: ANN001
        editor = QSpinBox(parent)
        column = self._column_spec(index)
        if column is not None and column.minimum is not None:
            editor.setMinimum(int(column.minimum))
        if column is not None and column.maximum is not None:
            editor.setMaximum(int(column.maximum))
        if column is not None and column.single_step is not None:
            editor.setSingleStep(max(1, int(column.single_step)))
        if column is not None and column.suffix:
            editor.setSuffix(column.suffix)
        editor.setAccelerated(True)
        return editor

    def setEditorData(self, editor, index) -> None:  # noqa: ANN001
        try:
            editor.setValue(int(index.data(Qt.ItemDataRole.EditRole) or 0))
        except (TypeError, ValueError):
            editor.setValue(0)

    def setModelData(self, editor, model, index) -> None:  # noqa: ANN001
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)

    @staticmethod
    def _column_spec(index) -> ColumnSpec | None:  # noqa: ANN001
        model = index.model()
        columns = getattr(model, "columns", None)
        if callable(columns):
            resolved_columns = columns()
            if 0 <= index.column() < len(resolved_columns):
                return resolved_columns[index.column()]
        return None


class ActionCellDelegate(QStyledItemDelegate):
    """Activate a table cell like a button."""

    def __init__(self, on_activated: Callable[[QModelIndex], None], parent=None) -> None:
        super().__init__(parent)
        self._on_activated = on_activated

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._on_activated(index)
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self._on_activated(index)
            return True
        return False

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        if self._is_reset_cell(index):
            reset_option = self._reset_option(option, index)
            style = reset_option.widget.style() if reset_option.widget is not None else QApplication.instance().style() if QApplication.instance() is not None else None
            if style is not None:
                style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, reset_option, painter, reset_option.widget)
            self._paint_reset_contents(painter, reset_option, index)
            return
        super().paint(painter, option, index)

    def initStyleOption(self, option, index) -> None:  # noqa: ANN001
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        if self._is_reset_cell(index):
            try:
                option.icon = qta.icon("msc.clear-all")
            except Exception:
                app = QApplication.instance()
                style = option.widget.style() if option.widget is not None else app.style() if app is not None else None
                if style is not None:
                    option.icon = style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
            option.decorationSize = QSize(10, 10)
            option.decorationPosition = QStyleOptionViewItem.Position.Left
            option.decorationAlignment = Qt.AlignmentFlag.AlignVCenter

    def _is_reset_cell(self, index) -> bool:  # noqa: ANN001
        return str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip() == "Reset"

    def _reset_option(self, option, index) -> QStyleOptionViewItem:  # noqa: ANN001
        reset_option = QStyleOptionViewItem(option)
        self.initStyleOption(reset_option, index)
        return reset_option

    def _reset_layout(self, option, index) -> tuple[QRect, QRect, str]:  # noqa: ANN001
        reset_option = self._reset_option(option, index)
        text = str(reset_option.text or index.data(Qt.ItemDataRole.DisplayRole) or "Reset").strip()
        icon_size = reset_option.decorationSize if reset_option.decorationSize.isValid() else QSize(10, 10)
        font_metrics = reset_option.fontMetrics
        gap = 4
        group_width = icon_size.width() + gap + font_metrics.horizontalAdvance(text)
        group_height = max(icon_size.height(), font_metrics.height())
        group_rect = QRect(reset_option.rect)
        group_rect.setWidth(group_width)
        group_rect.setHeight(group_height)
        group_rect.moveCenter(reset_option.rect.center())

        icon_rect = QRect(
            group_rect.left(),
            group_rect.center().y() - icon_size.height() // 2,
            icon_size.width(),
            icon_size.height(),
        )
        text_rect = QRect(
            icon_rect.right() + 1 + gap,
            group_rect.top(),
            max(0, font_metrics.horizontalAdvance(text)),
            group_rect.height(),
        )
        return icon_rect, text_rect, text

    def _paint_reset_contents(self, painter, option, index) -> None:  # noqa: ANN001
        icon_rect, text_rect, text = self._reset_layout(option, index)
        painter.save()
        try:
            if not option.icon.isNull():
                option.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            painter.setFont(option.font)
            painter.setPen(option.palette.color(QPalette.ColorRole.Link))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
        finally:
            painter.restore()
