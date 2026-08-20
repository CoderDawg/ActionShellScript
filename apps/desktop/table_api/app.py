from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .schema import CellStyle, CellValue
from .schema import ColumnSpec
from .window import TableWindow


def main() -> int:
    app = QApplication([])
    window = TableWindow(
        headers=[
            ColumnSpec(name="name", label="Name", width_mode="stretch"),
            ColumnSpec(
                name="role",
                label="Role",
                editor="combo",
                choices=["Engineer", "Architect", "Manager"],
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
            ColumnSpec(name="office", label="Office", width_mode="stretch"),
        ],
        rows=[
            {
                "name": CellValue("Ada", CellStyle(color="#0f172a", bold=True, font_family="Segoe UI")),
                "role": CellValue("Engineer", CellStyle(background="#dbeafe")),
                "active": True,
                "office": CellValue("Seattle", CellStyle(foreground="#b91c1c", italic=True)),
            },
            {"name": "Linus", "role": "Architect", "active": False, "office": "Helsinki"},
            {"name": "Grace", "role": "Manager", "active": True, "office": "New York"},
        ],
        editable=True,
        title="PySide6 Table Manager",
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
