from __future__ import annotations

from typing import Any, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from .schema import CellStyle, CellValue, ColumnSpec


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)

class EditableTableModel(QAbstractTableModel):
    """An editable table model backed by dictionaries or sequences."""

    def __init__(
        self,
        headers: Sequence[str] | Sequence[ColumnSpec],
        rows: Sequence[dict[str, Any]] | Sequence[Sequence[Any]] | None = None,
        *,
        editable: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._columns = self._normalize_columns(headers)
        self._editable = editable
        self._rows: list[dict[str, CellValue]] = []
        if rows:
            self.set_rows(rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self._columns[index.column()]
        cell = row.get(column.name, self._default_cell(column))
        value = cell.value
        style = self._effective_style(column, cell.style)
        if column.editor == "checkbox":
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if bool(value) else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.EditRole:
                return bool(value)
            if role == Qt.ItemDataRole.DisplayRole:
                return ""
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return _stringify(value)
        if role == Qt.ItemDataRole.ForegroundRole:
            color = self._style_color(style.color or style.foreground)
            if color is not None:
                return QBrush(color)
        if role == Qt.ItemDataRole.BackgroundRole:
            color = self._style_color(style.background)
            if color is not None:
                return QBrush(color)
        if role == Qt.ItemDataRole.FontRole:
            return self._style_font(style)
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        column = self._columns[index.column()]
        if not index.isValid() or not self._editable:
            return False
        if role == Qt.ItemDataRole.CheckStateRole and column.editor == "checkbox":
            cell = self._rows[index.row()].get(column.name, self._default_cell(column))
            cell.value = value == Qt.CheckState.Checked
            self._rows[index.row()][column.name] = cell
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.DisplayRole])
            return True
        if role == Qt.ItemDataRole.ForegroundRole:
            cell = self._rows[index.row()].get(column.name, self._default_cell(column))
            cell.style = self._update_style(cell.style, foreground=self._extract_color(value))
            self._rows[index.row()][column.name] = cell
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.ForegroundRole])
            return True
        if role == Qt.ItemDataRole.BackgroundRole:
            cell = self._rows[index.row()].get(column.name, self._default_cell(column))
            cell.style = self._update_style(cell.style, background=self._extract_color(value))
            self._rows[index.row()][column.name] = cell
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.BackgroundRole])
            return True
        if role == Qt.ItemDataRole.FontRole and isinstance(value, QFont):
            cell = self._rows[index.row()].get(column.name, self._default_cell(column))
            cell.style = self._update_style(
                cell.style,
                font_family=value.family(),
                point_size=value.pointSize() if value.pointSize() > 0 else None,
                bold=value.bold(),
                italic=value.italic(),
                underline=value.underline(),
                strikeout=value.strikeOut(),
            )
            self._rows[index.row()][column.name] = cell
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.FontRole])
            return True
        if role != Qt.ItemDataRole.EditRole:
            return False
        cell = self._rows[index.row()].get(column.name, self._default_cell(column))
        cell.value = self._coerce_value(column, value)
        self._rows[index.row()][column.name] = cell
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        column = self._columns[index.column()]
        if column.editor == "checkbox":
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        if self._editable and column.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section].display_label()
            return None
        return section + 1

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:  # noqa: N802
        if not (0 <= column < len(self._columns)):
            return
        header = self._columns[column].name
        reverse = order == Qt.SortOrder.DescendingOrder
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=lambda row: self._sort_value(row.get(header, "")), reverse=reverse)
        self.layoutChanged.emit()

    def headers(self) -> list[str]:
        return [column.name for column in self._columns]

    def columns(self) -> list[ColumnSpec]:
        return list(self._columns)

    def rows(self) -> list[dict[str, Any]]:
        return [{name: cell.value for name, cell in row.items()} for row in self._rows]

    def row_at(self, row: int) -> dict[str, Any]:
        return {name: cell.value for name, cell in self._rows[row].items()}

    def styled_row_at(self, row: int) -> dict[str, CellValue]:
        return {
            name: CellValue(value=cell.value, style=cell.style)
            for name, cell in self._rows[row].items()
        }

    def set_rows(self, rows: Sequence[dict[str, Any]] | Sequence[Sequence[Any]]) -> None:
        self.beginResetModel()
        self._rows = [self._normalize_row(row) for row in rows]
        self.endResetModel()

    def add_row(self, row: dict[str, Any] | Sequence[Any] | None = None) -> int:
        payload = self._normalize_row(row or {})
        position = len(self._rows)
        self.beginInsertRows(QModelIndex(), position, position)
        self._rows.append(payload)
        self.endInsertRows()
        return position

    def update_row(self, row: int, values: dict[str, Any] | Sequence[Any]) -> None:
        self._rows[row] = self._normalize_row(values, existing_row=self._rows[row])
        top_left = self.index(row, 0)
        bottom_right = self.index(row, max(0, len(self._columns) - 1))
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    def remove_row(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._rows[row]
        self.endRemoveRows()

    def is_editable(self) -> bool:
        return self._editable

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        if self.rowCount() and self.columnCount():
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.EditRole])

    def _normalize_row(
        self,
        row: dict[str, Any] | Sequence[Any],
        *,
        existing_row: dict[str, CellValue] | None = None,
    ) -> dict[str, CellValue]:
        if isinstance(row, dict):
            return {
                column.name: self._make_cell(column, row.get(column.name, column.default), existing_row=existing_row)
                for column in self._columns
            }
        values = list(row)
        return {
            column.name: self._make_cell(
                column,
                values[index] if index < len(values) else column.default,
                existing_row=existing_row,
            )
            for index, column in enumerate(self._columns)
        }

    def _normalize_columns(self, headers: Sequence[str] | Sequence[ColumnSpec]) -> list[ColumnSpec]:
        columns: list[ColumnSpec] = []
        for header in headers:
            if isinstance(header, ColumnSpec):
                columns.append(header)
            else:
                columns.append(ColumnSpec(name=str(header), label=str(header)))
        return columns

    @staticmethod
    def _coerce_value(column: ColumnSpec, value: Any) -> Any:
        if column.editor == "checkbox":
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return value == 2
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "checked"}
            return bool(value)
        if column.editor == "spinbox":
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(column.default)
                except (TypeError, ValueError):
                    return 0
        return value

    def _make_cell(
        self,
        column: ColumnSpec,
        value: Any,
        *,
        existing_row: dict[str, CellValue] | None = None,
    ) -> CellValue:
        if isinstance(value, CellValue):
            normalized_value = column.normalize_value(value.value)
            style = self._merge_styles(column.default_style, value.style)
            return CellValue(normalized_value, style)

        existing_style = None
        if existing_row is not None and column.name in existing_row:
            existing_style = existing_row[column.name].style
        normalized_value = column.normalize_value(value)
        style = self._merge_styles(column.default_style, existing_style)
        return CellValue(normalized_value, style)

    @staticmethod
    def _default_cell(column: ColumnSpec) -> CellValue:
        return CellValue(column.normalize_value(column.default), column.default_style)

    @staticmethod
    def _merge_styles(base: CellStyle | None, override: CellStyle | None) -> CellStyle | None:
        if base is None:
            return override
        if override is None:
            return base
        return override.merge(base)

    @staticmethod
    def _update_style(style: CellStyle | None, **updates: Any) -> CellStyle:
        current = style or CellStyle()
        return CellStyle(
            color=updates.get("color", current.color),
            foreground=updates.get("foreground", current.foreground),
            background=updates.get("background", current.background),
            font_family=updates.get("font_family", current.font_family),
            point_size=updates.get("point_size", current.point_size),
            bold=updates.get("bold", current.bold),
            italic=updates.get("italic", current.italic),
            underline=updates.get("underline", current.underline),
            strikeout=updates.get("strikeout", current.strikeout),
        )

    @staticmethod
    def _effective_style(column: ColumnSpec, cell_style: CellStyle | None) -> CellStyle:
        if column.default_style is None and cell_style is None:
            return CellStyle()
        if column.default_style is None:
            return cell_style or CellStyle()
        if cell_style is None:
            return column.default_style
        return cell_style.merge(column.default_style)

    @staticmethod
    def _extract_color(value: Any) -> str | None:
        if isinstance(value, QBrush):
            color = value.color()
            return color.name() if color.isValid() else None
        if isinstance(value, QColor):
            return value.name() if value.isValid() else None
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _style_color(value: str | None) -> QColor | None:
        if not value:
            return None
        color = QColor(value)
        return color if color.isValid() else None

    @staticmethod
    def _style_font(style: CellStyle) -> QFont:
        font = QFont()
        if style.font_family:
            font.setFamily(style.font_family)
        point_size = EditableTableModel._positive_point_size(style.point_size)
        if point_size is not None:
            font.setPointSize(point_size)
        if style.bold is not None:
            font.setBold(style.bold)
        if style.italic is not None:
            font.setItalic(style.italic)
        if style.underline is not None:
            font.setUnderline(style.underline)
        if style.strikeout is not None:
            font.setStrikeOut(style.strikeout)
        return font

    @staticmethod
    def _positive_point_size(value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        return value

    @staticmethod
    def _sort_value(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        try:
            return float(text)
        except ValueError:
            return text.lower()
