# PySide6 Table API

A small PySide6 table framework for building editable tables with:

- `QAbstractTableModel`-based data handling
- sorting and filtering
- add, edit, and delete row actions
- richer row editors with text fields, combo boxes, and checkboxes
- cell styling for foreground, background, fonts, and text emphasis
- reusable color-cell editors and swatch values
- column layout metadata that keeps view widths and custom header strips in sync

## Project Layout

- `apps/desktop/table_api/schema.py`
  - `ColumnSpec` describes a column
  - `CellStyle` stores styling metadata
  - `CellValue` wraps a value plus optional style
- `apps/desktop/table_api/model.py`
  - `EditableTableModel` is the source model
  - supports edits, insertions, removals, sorting, and Qt style roles
- `apps/desktop/table_api/proxy.py`
  - `TableFilterProxyModel` provides case-insensitive search across all columns
- `apps/desktop/table_api/dialogs.py`
  - `RowEditorDialog` builds the add/edit form from column metadata
- `apps/desktop/table_api/window.py`
  - `TableWindow` is the main UI with toolbar actions and search
- `apps/desktop/table_api/api.py`
  - `TableAPI` is a small convenience facade for application code
  - `create_view_with_proxy(...)` returns both the view and the filter proxy
  - `create_header_strip(...)` builds a matching header row from column metadata
- `table_api.py`
  - repo-root compatibility wrapper that re-exports `apps.desktop.table_api`
  - launch the demo with `python table_api.py`

## Basic Usage

```python
from table_api import ColumnSpec, TableWindow

window = TableWindow(
    headers=[
        ColumnSpec(name="name", label="Name", width_mode="stretch"),
        ColumnSpec(
            name="role",
            label="Role",
            editor="combo",
            choices=["Engineer", "Manager"],
            width_mode="fixed",
            fixed_width=160,
        ),
        ColumnSpec(
            name="active",
            label="Active",
            editor="checkbox",
            default=True,
            width_mode="fixed",
            fixed_width=90,
        ),
    ],
    rows=[
        {"name": "Ada", "role": "Engineer", "active": True},
        {"name": "Grace", "role": "Manager", "active": False},
    ],
    editable=True,
)
```

If you want to build the pieces yourself, `TableAPI` provides the same model/view wiring:

```python
from table_api import TableAPI, TableOptions

api = TableAPI(TableOptions(editable=True, sortable=False, filterable=True))
model = api.create_model(headers, rows)
view, proxy = api.create_view_with_proxy(model)
header = api.create_header_strip(model.columns(), parent=view)
```

You can also register a custom delegate for a column hint before creating the view:

```python
from table_api import ColumnSpec, TableAPI, TableOptions
from my_delegates import MyRatingDelegate

api = TableAPI(TableOptions(editable=True, sortable=False, filterable=False))
api.register_delegate(
    "rating",
    lambda parent, column: MyRatingDelegate(parent, choices=column.choices),
)

model = api.create_model(
    [ColumnSpec(name="rating", label="Rating", delegate_key="rating")],
    [{"rating": "good"}],
)
view = api.create_view(model)
```

## Hotkey Editors

The table API includes a reusable hotkey editor for single-cell shortcut capture:

- `delegate_key="keysequence"` wires in the native shortcut editor
- the editor captures normal shortcut chords
- `Backspace` and `Delete` clear the current shortcut
- common clipboard/edit shortcuts such as copy, cut, paste, undo, redo, and select-all are ignored while capturing
- the editor includes a small clear button so unassigning is visible in the UI
- the desktop Preferences dialog uses the same editor, and duplicate shortcuts are allowed temporarily while editing but rejected at save time

This is the same editor used by the desktop Preferences Hotkeys table.

## Column Types

Each column is defined with `ColumnSpec`.

```python
ColumnSpec(
    name="role",
    label="Role",
    editor="combo",
    choices=["Engineer", "Architect", "Manager"],
    width_mode="fixed",
    fixed_width=160,
)
```

Supported editors:

- `text`
- `combo`
- `checkbox`

## Reusable Color Cells

The API includes helpers for tables that edit color values in-place:

```python
from table_api import ColorCellDelegate, color_cell_value, contrast_color

row = {
    "foreground": color_cell_value("#000000"),
    "background": color_cell_value("#fff4c2"),
}
```

- `ColorCellDelegate` opens the color picker on a single click
- `color_cell_value(...)` wraps a hex value in a styled table cell
- `contrast_color(...)` chooses a readable text color for the swatch

## Styling Cells

Cell data can be provided as plain values or as `CellValue(value, style)`.

```python
from table_api import CellStyle, CellValue

row = {
    "name": CellValue(
        "Ada",
        CellStyle(color="#0f172a", bold=True, font_family="Segoe UI"),
    ),
    "role": CellValue(
        "Engineer",
        CellStyle(background="#dbeafe"),
    ),
    "active": True,
}
```

Supported style fields:

- `color`
- `foreground`
- `background`
- `font_family`
- `point_size`
- `bold`
- `italic`
- `underline`
- `strikeout`

## Model Features

`EditableTableModel` supports:

- `set_rows(...)`
- `add_row(...)`
- `update_row(...)`
- `remove_row(...)`
- `row_at(...)`
- `rows()`
- `columns()`

Checkbox columns are stored as booleans and rendered with Qt check state support.

## Search And Sorting

`TableFilterProxyModel` filters across all visible columns using a single search box.

The table view is sortable, and the model/proxy both use numeric-aware ordering when possible.

## Extending The App

Common next steps are:

1. add CSV or JSON import/export
2. add validation rules per column
3. add a dedicated style editor in the row dialog
4. add conditional formatting rules

## Notes

- The canonical package code lives under `apps.desktop.table_api`.
- The repo-root `table_api.py` file is a compatibility launcher and re-export layer.
- If you are importing from another module in this repository, `from table_api import ...` works because of that wrapper.
