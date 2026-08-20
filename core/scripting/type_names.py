"""Canonical type names for the scripting language.

This module establishes the early value-type vocabulary for future `Struct`
support and DLL-friendly marshaling. It is intentionally small and does not
introduce parsing or semantic rules yet.
"""

from __future__ import annotations

from typing import Final


CANONICAL_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "Int8",
        "UInt8",
        "Int16",
        "UInt16",
        "Int32",
        "UInt32",
        "Int64",
        "UInt64",
        "Float32",
        "Float64",
        "Bool",
        "Char",
        "String",
        "Ptr",
        "IntPtr",
    }
)

_CANONICAL_TYPE_NAME_LOOKUP: Final[dict[str, str]] = {
    name.lower(): name for name in CANONICAL_TYPE_NAMES
}


def is_canonical_type_name(name: str) -> bool:
    return normalize_type_name(name) in CANONICAL_TYPE_NAMES


def normalize_type_name(name: str) -> str:
    text = str(name).strip()
    if not text:
        return ""
    return _CANONICAL_TYPE_NAME_LOOKUP.get(text.lower(), text)


def canonical_type_names() -> tuple[str, ...]:
    return tuple(sorted(CANONICAL_TYPE_NAMES))
