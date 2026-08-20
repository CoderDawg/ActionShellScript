from __future__ import annotations

import os
from typing import TypeVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeySequence, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (
    QApplication,
    QKeySequenceEdit,
    QStyledItemDelegate,
    QToolButton,
    QWidget,
)  # noqa: E402

from apps.desktop.table_api import ColumnSpec, TableAPI, TableOptions  # noqa: E402
from apps.desktop.table_api.delegates import HotkeySequenceEdit  # noqa: E402
from apps.desktop.table_api.model import EditableTableModel  # noqa: E402
from apps.desktop.table_api.schema import CellStyle  # noqa: E402

TWidget = TypeVar("TWidget", bound=QWidget)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _required_child(parent: QWidget, child_type: type[TWidget], name: str | None = None) -> TWidget:
    child = parent.findChild(child_type, name) if name is not None else parent.findChild(child_type)
    assert child is not None
    return cast(TWidget, child)


def test_table_api_registers_builtin_delegates_from_column_spec() -> None:
    _app()

    api = TableAPI(TableOptions(editable=True, sortable=False, filterable=False))
    model = api.create_model(
        [
            ColumnSpec(name="shortcut", delegate_key="keysequence"),
            ColumnSpec(name="choice", editor="combo", choices=["one", "two"]),
        ],
        [{"shortcut": "Ctrl+N", "choice": "one"}],
    )

    view = api.create_view(model)

    assert view.itemDelegateForColumn(0).__class__.__name__ == "KeySequenceDelegate"
    assert view.itemDelegateForColumn(1).__class__.__name__ == "ComboBoxDelegate"


def test_table_api_uses_registered_delegate_factories() -> None:
    _app()

    class MarkerDelegate(QStyledItemDelegate):
        pass

    api = TableAPI(TableOptions(editable=True, sortable=False, filterable=False))
    api.register_delegate(
        "marker",
        lambda parent, column: MarkerDelegate(parent),
    )
    model = api.create_model(
        [ColumnSpec(name="custom", delegate_key="marker")],
        [{"custom": "value"}],
    )

    view = api.create_view(model)

    assert isinstance(view.itemDelegateForColumn(0), MarkerDelegate)


def test_table_api_registers_custom_rating_delegate_from_column_spec() -> None:
    _app()

    captured_choices: list[str] = []

    class RatingDelegate(QStyledItemDelegate):
        def __init__(self, choices: list[str], parent=None) -> None:
            super().__init__(parent)
            captured_choices.extend(choices)

    api = TableAPI(TableOptions(editable=True, sortable=False, filterable=False))
    api.register_delegate(
        "rating",
        lambda parent, column: RatingDelegate(list(column.choices), parent),
    )
    model = api.create_model(
        [
            ColumnSpec(
                name="rating",
                label="Rating",
                delegate_key="rating",
                choices=["good", "ok", "bad"],
            )
        ],
        [{"rating": "good"}],
    )

    view = api.create_view(model)

    assert isinstance(view.itemDelegateForColumn(0), RatingDelegate)
    assert captured_choices == ["good", "ok", "bad"]


def test_hotkey_sequence_edit_clears_with_backspace_and_ignores_copy_shortcut() -> None:
    _app()

    parent = QWidget()
    editor = HotkeySequenceEdit(parent)
    editor.show()
    capture_field = _required_child(editor, QKeySequenceEdit)
    capture_field.setFocus()
    editor.setKeySequence(QKeySequence("Ctrl+N"))
    QTest.keyClick(capture_field, Qt.Key.Key_Backspace)
    assert editor.keySequence().toString() == ""

    editor.setKeySequence(QKeySequence("Ctrl+N"))
    QTest.keyClick(capture_field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert editor.keySequence().toString() == "Ctrl+N"


def test_hotkey_sequence_edit_shows_a_clear_button() -> None:
    _app()

    parent = QWidget()
    editor = HotkeySequenceEdit(parent)
    editor.show()
    editor.setKeySequence(QKeySequence("Ctrl+N"))

    clear_button = _required_child(editor, QToolButton)
    assert clear_button.text() == ""
    assert not clear_button.icon().isNull()

    QTest.mouseClick(clear_button, Qt.MouseButton.LeftButton)

    assert editor.keySequence().toString() == ""


def test_hotkey_sequence_edit_captures_modifier_shortcuts() -> None:
    _app()

    parent = QWidget()
    editor = HotkeySequenceEdit(parent)
    editor.show()
    capture_field = _required_child(editor, QKeySequenceEdit)
    capture_field.setFocus()

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_N),
        Qt.KeyboardModifier.ControlModifier,
    )
    QApplication.sendEvent(capture_field, event)

    assert editor.keySequence().toString() == "Ctrl+N"


def test_editable_table_model_ignores_non_positive_point_sizes() -> None:
    assert EditableTableModel._positive_point_size(None) is None
    assert EditableTableModel._positive_point_size(0) is None
    assert EditableTableModel._positive_point_size(-1) is None
    assert EditableTableModel._positive_point_size(11) == 11

    font = EditableTableModel._style_font(CellStyle(font_family="Consolas", point_size=11))

    assert font.family() == "Consolas"
    assert font.pointSize() == 11
