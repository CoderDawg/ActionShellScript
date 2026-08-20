from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any, Sequence

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QStyledItemDelegate,
    QTableView,
    QWidget,
    QSizePolicy,
)

from .model import EditableTableModel
from .proxy import TableFilterProxyModel
from .schema import ColumnSpec
from .delegates import ComboBoxDelegate, KeySequenceDelegate
from .delegates import SpinBoxDelegate


@dataclass(slots=True)
class TableOptions:
    editable: bool = True
    sortable: bool = True
    filterable: bool = True
    alternating_row_colors: bool = True


class TableAPI:
    """Convenience facade for creating editable table models and views."""

    def __init__(self, options: TableOptions | None = None) -> None:
        self.options = options or TableOptions()
        self._delegate_factories: dict[
            str, Callable[[QWidget | None, ColumnSpec], QStyledItemDelegate]
        ] = {}
        self._register_default_delegates()

    def create_model(
        self,
        headers: Sequence[str] | Sequence[ColumnSpec],
        rows: Sequence[dict[str, Any]] | Sequence[Sequence[Any]],
    ) -> EditableTableModel:
        return EditableTableModel(headers, rows, editable=self.options.editable)

    def create_proxy_model(
        self,
        source_model: QAbstractTableModel,
        parent: QWidget | None = None,
    ) -> TableFilterProxyModel:
        return TableFilterProxyModel(source_model, parent)

    def create_view(
        self,
        model: QAbstractTableModel,
        parent: QWidget | None = None,
    ) -> QTableView:
        view, _proxy_model = self.create_view_with_proxy(model, parent)
        return view

    def create_view_with_proxy(
        self,
        model: QAbstractTableModel,
        parent: QWidget | None = None,
    ) -> tuple[QTableView, TableFilterProxyModel | None]:
        view = QTableView(parent)
        proxy_model: TableFilterProxyModel | None = None
        columns = self._resolve_columns(model)
        if self.options.filterable and not isinstance(model, TableFilterProxyModel):
            proxy_model = self.create_proxy_model(model, view)
            view.setModel(proxy_model)
            view._table_api_proxy_model = proxy_model  # Keep the proxy alive with the view.
        else:
            view.setModel(model)
            if isinstance(model, TableFilterProxyModel):
                proxy_model = model
        view.setAlternatingRowColors(self.options.alternating_row_colors)
        view.setSortingEnabled(self.options.sortable)
        if columns:
            self.apply_column_layout(view, columns)
            self.apply_column_delegates(view, columns)
        return view, proxy_model

    def apply_column_layout(
        self,
        view: QTableView,
        columns: Sequence[ColumnSpec],
    ) -> None:
        header = view.horizontalHeader()
        header.setStretchLastSection(False)
        for index, column in enumerate(columns):
            if column.width_mode == "stretch":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            elif column.width_mode == "fixed":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                if column.fixed_width is not None:
                    view.setColumnWidth(index, column.fixed_width)
            elif column.width_mode == "contents":
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
            else:
                raise ValueError(f"Unsupported width mode: {column.width_mode}")

    def apply_column_delegates(
        self,
        view: QTableView,
        columns: Sequence[ColumnSpec],
    ) -> None:
        delegates: list[object] = []
        for index, column in enumerate(columns):
            delegate = self._create_delegate_for_column(column, view)
            if delegate is None:
                continue
            view.setItemDelegateForColumn(index, delegate)
            delegates.append(delegate)
        if delegates:
            view._table_api_column_delegates = delegates

    def register_delegate(
        self,
        delegate_key: str,
        factory: Callable[[QWidget | None, ColumnSpec], QStyledItemDelegate],
    ) -> None:
        self._delegate_factories[delegate_key] = factory

    def create_header_strip(
        self,
        columns: Sequence[ColumnSpec],
        parent: QWidget | None = None,
        *,
        text_color: str = "#202020",
        background_color: str = "#e9edf2",
        border_color: str = "#c7cdd4",
        padding: str = "3px 8px",
        font_size: int = 11,
        bold: bool = True,
    ) -> QWidget:
        strip = QFrame(parent)
        strip.setStyleSheet(
            "QFrame {"
            f" background-color: {background_color};"
            " border: 0;"
            f" border-bottom: 1px solid {border_color};"
            " }"
        )
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for index, column in enumerate(columns):
            label = QLabel(column.display_label(), strip)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet(
                "QLabel {"
                f" color: {text_color};"
                f" font-size: {font_size}px;"
                f" font-weight: {'600' if bold else '400'};"
                f" padding: {padding};"
                " }"
            )
            if column.width_mode == "stretch":
                label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                layout.addWidget(label, 1)
            else:
                width = column.fixed_width
                if width is None and column.width_mode == "contents":
                    width = label.sizeHint().width()
                if width is not None:
                    label.setFixedWidth(width)
                layout.addWidget(label, 0)
        return strip

    @staticmethod
    def _resolve_columns(model: QAbstractTableModel) -> Sequence[ColumnSpec] | None:
        if isinstance(model, EditableTableModel):
            return model.columns()
        if isinstance(model, TableFilterProxyModel):
            source_model = model.sourceModel()
            if isinstance(source_model, EditableTableModel):
                return source_model.columns()
        return None

    def _register_default_delegates(self) -> None:
        self.register_delegate(
            "combo",
            lambda parent, column: ComboBoxDelegate(column.choices, parent),
        )
        self.register_delegate(
            "keysequence",
            lambda parent, _column: KeySequenceDelegate(parent=parent),
        )
        self.register_delegate(
            "spinbox",
            lambda parent, _column: SpinBoxDelegate(parent=parent),
        )

    def _create_delegate_for_column(
        self,
        column: ColumnSpec,
        parent: QWidget | None = None,
    ) -> QStyledItemDelegate | None:
        delegate_key = column.delegate_key or column.editor
        factory = self._delegate_factories.get(delegate_key)
        if factory is None:
            return None
        return factory(parent, column)
