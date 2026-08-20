from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from .schema import ColumnSpec


class RowEditorDialog(QDialog):
    """Simple form dialog for creating or editing a table row."""

    def __init__(
        self,
        columns: list[ColumnSpec],
        initial: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Row" if initial else "Add Row")
        self._columns = columns
        self._fields: dict[str, QLineEdit | QComboBox | QCheckBox] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        values = initial or {}
        for column in columns:
            field = self._create_field(column, values.get(column.name, column.default))
            form.addRow(column.display_label(), field)
            self._fields[column.name] = field

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {column.name: self._read_field(column, self._fields[column.name]) for column in self._columns}

    def _create_field(self, column: ColumnSpec, value: Any):
        if column.editor == "checkbox":
            field = QCheckBox(self)
            field.setChecked(column.normalize_value(value))
            return field
        if column.editor == "combo":
            field = QComboBox(self)
            field.setEditable(True)
            for choice in column.choices:
                field.addItem(str(choice))
            current_text = "" if value is None else str(value)
            if current_text and field.findText(current_text) == -1:
                field.addItem(current_text)
            field.setCurrentText(current_text)
            return field
        field = QLineEdit(self)
        field.setText("" if value is None else str(value))
        return field

    def _read_field(self, column: ColumnSpec, field: QLineEdit | QComboBox | QCheckBox) -> Any:
        if column.editor == "checkbox" and isinstance(field, QCheckBox):
            return field.isChecked()
        if column.editor == "combo" and isinstance(field, QComboBox):
            return field.currentText()
        if isinstance(field, QLineEdit):
            return field.text()
        return ""
