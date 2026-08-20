from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from core.scripting import ast_nodes as ast


@dataclass(frozen=True, slots=True)
class StructFieldDefinition:
    name: str
    type_name: str
    initializer: ast.Expression | None = None


@dataclass(frozen=True, slots=True)
class StructDefinition:
    name: str
    fields: tuple[StructFieldDefinition, ...]
    packing: int | None = None
    alignment: int | None = None

    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def has_field(self, field_name: str) -> bool:
        return self.field_index(field_name) is not None

    def field_index(self, field_name: str) -> int | None:
        normalized = str(field_name).strip()
        if not normalized:
            return None
        for index, field in enumerate(self.fields):
            if field.name == normalized:
                return index
        return None


@dataclass(frozen=True, slots=True)
class RecordDefinition:
    name: str
    fields: tuple[StructFieldDefinition, ...]

    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def has_field(self, field_name: str) -> bool:
        return self.field_index(field_name) is not None

    def field_index(self, field_name: str) -> int | None:
        normalized = str(field_name).strip()
        if not normalized:
            return None
        for index, field in enumerate(self.fields):
            if field.name == normalized:
                return index
        return None


@dataclass(frozen=True, slots=True)
class StructInstance:
    struct_name: str
    _field_names: tuple[str, ...]
    _values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if len(self._field_names) != len(self._values):
            raise ValueError("StructInstance field names and values must have the same length")

    def __getattr__(self, name: str) -> Any:
        return self.get_field(name)

    def get_field(self, name: str) -> Any:
        field_name = str(name).strip()
        if not field_name:
            raise AttributeError("Struct field name must not be empty")

        for index, candidate in enumerate(self._field_names):
            if candidate == field_name:
                return clone_runtime_value(self._values[index])

        raise AttributeError(f"{self.struct_name} has no field named {field_name!r}")

    def copy(self) -> "StructInstance":
        return StructInstance(
            struct_name=self.struct_name,
            _field_names=self._field_names,
            _values=tuple(clone_runtime_value(value) for value in self._values),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            field_name: clone_runtime_value(value)
            for field_name, value in zip(self._field_names, self._values, strict=False)
        }

    def field_names(self) -> tuple[str, ...]:
        return self._field_names

    def __repr__(self) -> str:
        fields = ", ".join(
            f"{field_name}={repr(value)}"
            for field_name, value in zip(self._field_names, self._values, strict=False)
        )
        return f"{self.struct_name}({fields})"

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class RecordInstance:
    record_name: str
    _field_names: tuple[str, ...]
    _values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if len(self._field_names) != len(self._values):
            raise ValueError("RecordInstance field names and values must have the same length")

    def __getattr__(self, name: str) -> Any:
        return self.get_field(name)

    def get_field(self, name: str) -> Any:
        field_name = str(name).strip()
        if not field_name:
            raise AttributeError("Record field name must not be empty")

        for index, candidate in enumerate(self._field_names):
            if candidate == field_name:
                return clone_runtime_value(self._values[index])

        raise AttributeError(f"{self.record_name} has no field named {field_name!r}")

    def copy(self) -> "RecordInstance":
        return RecordInstance(
            record_name=self.record_name,
            _field_names=self._field_names,
            _values=tuple(clone_runtime_value(value) for value in self._values),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            field_name: clone_runtime_value(value)
            for field_name, value in zip(self._field_names, self._values, strict=False)
        }

    def field_names(self) -> tuple[str, ...]:
        return self._field_names

    def __repr__(self) -> str:
        fields = ", ".join(
            f"{field_name}={repr(value)}"
            for field_name, value in zip(self._field_names, self._values, strict=False)
        )
        return f"{self.record_name}({fields})"

    __str__ = __repr__


def describe_debugger_value_type(value: Any) -> str:
    if isinstance(value, StructInstance):
        return value.struct_name
    if isinstance(value, RecordInstance):
        return value.record_name
    return type(value).__name__


def format_debugger_value(value: Any, *, max_length: int = 120) -> str:
    text = repr(value)
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return "." * max_length
    return f"{text[: max_length - 3]}..."


def clone_runtime_value(value: Any) -> Any:
    if isinstance(value, StructInstance):
        return value.copy()
    if isinstance(value, RecordInstance):
        return value.copy()
    if isinstance(value, list):
        return [clone_runtime_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(clone_runtime_value(item) for item in value)
    if isinstance(value, dict):
        return {key: clone_runtime_value(item) for key, item in value.items()}
    return value


def build_struct_instance(
    definition: StructDefinition,
    values: Sequence[Any],
) -> StructInstance:
    return StructInstance(
        struct_name=definition.name,
        _field_names=definition.field_names(),
        _values=tuple(clone_runtime_value(value) for value in values),
    )


def build_record_instance(
    definition: RecordDefinition,
    values: Sequence[Any],
) -> RecordInstance:
    return RecordInstance(
        record_name=definition.name,
        _field_names=definition.field_names(),
        _values=tuple(clone_runtime_value(value) for value in values),
    )
