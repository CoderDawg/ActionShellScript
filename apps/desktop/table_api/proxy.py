from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt


class TableFilterProxyModel(QSortFilterProxyModel):
    """Searchable and sortable proxy that matches text across all columns."""

    def __init__(self, source_model=None, parent=None) -> None:
        super().__init__(parent)
        if source_model is not None:
            self.setSourceModel(source_model)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

    def filter_text(self) -> str:
        return self._filter_text

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # noqa: N802
        if not self._filter_text:
            return True

        model = self.sourceModel()
        if model is None:
            return True

        for column in range(model.columnCount()):
            index = model.index(source_row, column, source_parent)
            value = model.data(index, Qt.ItemDataRole.DisplayRole)
            if self._filter_text in str(value).lower():
                return True
        return False

    def lessThan(self, left, right) -> bool:  # noqa: N802
        left_value = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole)
        right_value = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole)
        return self._sort_value(left_value) < self._sort_value(right_value)

    @staticmethod
    def _sort_value(value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        try:
            return float(text)
        except ValueError:
            return text.lower()
