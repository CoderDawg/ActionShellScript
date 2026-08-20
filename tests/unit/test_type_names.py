from __future__ import annotations

from core.scripting import CANONICAL_TYPE_NAMES
from core.scripting import canonical_type_names
from core.scripting import is_canonical_type_name
from core.scripting import normalize_type_name


def test_canonical_type_names_cover_the_early_struct_value_types() -> None:
    assert CANONICAL_TYPE_NAMES == frozenset(
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


def test_canonical_type_name_helpers_are_case_insensitive() -> None:
    assert normalize_type_name(" int32 ") == "Int32"
    assert normalize_type_name("string") == "String"
    assert normalize_type_name("custom_type") == "custom_type"
    assert is_canonical_type_name("bool") is True
    assert is_canonical_type_name("custom_type") is False


def test_canonical_type_names_are_stable_and_sorted_for_display() -> None:
    assert canonical_type_names() == (
        "Bool",
        "Char",
        "Float32",
        "Float64",
        "Int16",
        "Int32",
        "Int64",
        "Int8",
        "IntPtr",
        "Ptr",
        "String",
        "UInt16",
        "UInt32",
        "UInt64",
        "UInt8",
    )
