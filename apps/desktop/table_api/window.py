from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .api import TableAPI, TableOptions
from .dialogs import RowEditorDialog
from .model import EditableTableModel
from .proxy import TableFilterProxyModel
from .schema import ColumnSpec


class TableWindow(QMainWindow):
    """Full-featured table window with search and row actions."""

    def __init__(
        self,
        headers: list[str] | list[ColumnSpec],
        rows: list[dict[str, Any]] | list[list[Any]],
        *,
        editable: bool = True,
        title: str = "PySide6 Table App",
        parent=None,
        ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 600)

        self.table_api = TableAPI(
            TableOptions(editable=editable, sortable=True, filterable=True, alternating_row_colors=True)
        )
        self.model = self.table_api.create_model(headers, rows)
        self.view, proxy_model = self.table_api.create_view_with_proxy(self.model, self)
        if proxy_model is None:
            raise RuntimeError("TableWindow requires a filterable proxy model.")
        self.proxy = proxy_model
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setAlternatingRowColors(True)
        self.view.setSortingEnabled(True)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.view.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search all columns...")
        self.search.textChanged.connect(self.proxy.set_filter_text)

        self.count_label = QLabel(self)
        self._refresh_count()

        self.add_button = QPushButton("Add row", self)
        self.edit_button = QPushButton("Edit row", self)
        self.delete_button = QPushButton("Delete row", self)
        self.add_button.clicked.connect(self.add_row)
        self.edit_button.clicked.connect(self.edit_selected_row)
        self.delete_button.clicked.connect(self.delete_selected_rows)

        self._install_toolbar()
        self._build_central_widget()

        self.proxy.rowsInserted.connect(self._refresh_count)
        self.proxy.rowsRemoved.connect(self._refresh_count)
        self.proxy.modelReset.connect(self._refresh_count)
        self.proxy.layoutChanged.connect(self._refresh_count)

    def _install_toolbar(self) -> None:
        toolbar = QToolBar("Table Actions", self)
        toolbar.setMovable(False)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Filter:", self))
        toolbar.addWidget(self.search)
        self.addToolBar(toolbar)

    def _build_central_widget(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        header_row = QHBoxLayout()
        header_row.addWidget(self.count_label)
        header_row.addStretch(1)
        layout.addLayout(header_row)
        layout.addWidget(self.view)
        self.setCentralWidget(container)

    def _refresh_count(self, *args: Any) -> None:
        self.count_label.setText(
            f"Rows shown: {self.proxy.rowCount()} | total rows: {self.model.rowCount()}"
        )

    def _selected_proxy_row_indices(self) -> list[int]:
        indexes = self.view.selectionModel().selectedRows()
        rows = sorted({index.row() for index in indexes})
        return rows

    def _selected_source_row_indices(self) -> list[int]:
        source_rows: set[int] = set()
        for proxy_row in self._selected_proxy_row_indices():
            proxy_index = self.proxy.index(proxy_row, 0)
            source_index = self.proxy.mapToSource(proxy_index)
            if source_index.isValid():
                source_rows.add(source_index.row())
        return sorted(source_rows)

    def add_row(self) -> None:
        dialog = RowEditorDialog(self.model.columns(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.model.add_row(dialog.values())

    def edit_selected_row(self) -> None:
        selected_rows = self._selected_source_row_indices()
        if not selected_rows:
            QMessageBox.information(self, "Edit row", "Select one row to edit.")
            return
        if len(selected_rows) > 1:
            QMessageBox.information(self, "Edit row", "Please select only one row to edit.")
            return

        row_number = selected_rows[0]
        dialog = RowEditorDialog(self.model.columns(), initial=self.model.row_at(row_number), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.model.update_row(row_number, dialog.values())

    def delete_selected_rows(self) -> None:
        selected_rows = self._selected_source_row_indices()
        if not selected_rows:
            QMessageBox.information(self, "Delete rows", "Select one or more rows to delete.")
            return

        response = QMessageBox.question(
            self,
            "Delete rows",
            f"Delete {len(selected_rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        for row in reversed(selected_rows):
            self.model.remove_row(row)
