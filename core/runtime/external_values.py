from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any

from core.scripting import ast_nodes as ast


@dataclass(frozen=True, slots=True)
class StructLayoutSummary:
    name: str
    is_layout_safe: bool
    is_blittable: bool
    size: int | None
    alignment: int | None
    packing: int | None = None
    alignment_override: int | None = None
    field_offsets: tuple[int, ...] = ()
    field_sizes: tuple[int, ...] = ()
    field_alignments: tuple[int, ...] = ()
    field_blittable: tuple[bool, ...] = ()
    field_type_names: tuple[str, ...] = ()
    ctypes_type: type[ctypes.Structure] | None = None
    cycle_path: tuple[str, ...] | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalTypeInfo:
    name: str
    kind: str
    native_type: Any | None
    is_layout_safe: bool
    is_blittable: bool
    is_byref_eligible: bool
    is_return_eligible: bool
    size: int | None = None
    alignment: int | None = None
    struct_summary: StructLayoutSummary | None = None


@dataclass(frozen=True, slots=True)
class ExternalParameterInfo:
    name: str
    type_info: ExternalTypeInfo
    is_byref: bool
    is_byval: bool
    string_buffer_size: int | None = None


@dataclass(slots=True)
class ExternalFunctionBinding:
    declaration: ast.ExternalFunctionDecl
    library_name: str
    export_name: str
    calling_convention: str
    params: tuple[ExternalParameterInfo, ...]
    return_type: ExternalTypeInfo | None
    is_void: bool = False
    library_handle: Any | None = None
    function_handle: Any | None = None
    resolved: bool = False

    def signature_key(self) -> str:
        return self.declaration.name.lower().strip()


__all__ = [
    "ExternalFunctionBinding",
    "ExternalParameterInfo",
    "ExternalTypeInfo",
    "StructLayoutSummary",
]
