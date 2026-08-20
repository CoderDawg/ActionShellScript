from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(slots=True)
class CellStyle:
    color: str | None = None
    foreground: str | None = None
    background: str | None = None
    font_family: str | None = None
    point_size: int | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikeout: bool | None = None

    def merge(self, fallback: CellStyle | None) -> CellStyle:
        if fallback is None:
            return CellStyle(
                color=self.color,
                foreground=self.foreground,
                background=self.background,
                font_family=self.font_family,
                point_size=self.point_size,
                bold=self.bold,
                italic=self.italic,
                underline=self.underline,
                strikeout=self.strikeout,
            )
        return CellStyle(
            color=self.color if self.color is not None else fallback.color,
            foreground=self.foreground if self.foreground is not None else fallback.foreground,
            background=self.background if self.background is not None else fallback.background,
            font_family=self.font_family if self.font_family is not None else fallback.font_family,
            point_size=self.point_size if self.point_size is not None else fallback.point_size,
            bold=self.bold if self.bold is not None else fallback.bold,
            italic=self.italic if self.italic is not None else fallback.italic,
            underline=self.underline if self.underline is not None else fallback.underline,
            strikeout=self.strikeout if self.strikeout is not None else fallback.strikeout,
        )


@dataclass(slots=True)
class CellValue:
    value: Any
    style: CellStyle | None = None


@dataclass(slots=True)
class ColumnSpec:
    name: str
    label: str | None = None
    editor: str = "text"
    delegate_key: str | None = None
    choices: Sequence[str] = field(default_factory=tuple)
    default: Any = ""
    default_style: CellStyle | None = None
    editable: bool = True
    width_mode: str = "stretch"
    fixed_width: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    single_step: int | None = None
    suffix: str = ""

    def display_label(self) -> str:
        return self.label or self.name

    def normalize_value(self, value: Any) -> Any:
        if isinstance(value, CellValue):
            value = value.value
        if self.editor == "checkbox":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "checked"}
            return bool(value)
        if self.editor == "spinbox":
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(self.default)
                except (TypeError, ValueError):
                    return 0
        if value is None:
            return self.default
        return value
