from __future__ import annotations

import pytest

from core.runtime.script_runtime import ScriptRuntime
from core.runtime.struct_values import RecordInstance
from core.runtime.struct_values import StructInstance
from core.runtime.struct_values import format_debugger_value


def test_struct_constructor_supports_field_access_and_default_values() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Point\n"
            "X As Int32\n"
            "Y As Int32 = 4\n"
            "End Struct\n"
            "Dim p = Point(1)\n"
            "Dim q = p\n"
            "WriteLn(p.X)\n"
            "WriteLn(q.Y)\n"
        )
    )

    assert context.console_output == ["1\n", "4\n"]
    assert isinstance(context.variables["p"], StructInstance)
    assert isinstance(context.variables["q"], StructInstance)
    assert context.variables["p"] is not context.variables["q"]
    assert context.variables["p"].X == 1
    assert context.variables["q"].Y == 4


def test_struct_assignment_copies_nested_struct_instances() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Point\n"
            "X As Int32\n"
            "End Struct\n"
            "Struct Pair\n"
            "First As Point\n"
            "Second As Point\n"
            "End Struct\n"
            "Dim p = Point(7)\n"
            "Dim pair1 = Pair(p, p)\n"
            "Dim pair2 = pair1\n"
        )
    )

    pair1 = context.variables["pair1"]
    pair2 = context.variables["pair2"]

    assert isinstance(pair1, StructInstance)
    assert isinstance(pair2, StructInstance)
    assert pair1 is not pair2
    assert pair1._values[0] is not pair2._values[0]


def test_record_constructor_supports_strings_and_nested_copy_semantics() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Record Point\n"
            "X As Int32\n"
            "Y As Int32\n"
            "End Record\n"
            "Record WindowInfo\n"
            "Title As String\n"
            "Origin As Point\n"
            "End Record\n"
            "Dim first = WindowInfo(\"ActionShellScript\", Point(3, 4))\n"
            "Dim second = first\n"
            "WriteLn(first.Title)\n"
            "WriteLn(second.Origin.X)\n"
        )
    )

    first = context.variables["first"]
    second = context.variables["second"]

    assert context.console_output == ["ActionShellScript\n", "3\n"]
    assert isinstance(first, RecordInstance)
    assert isinstance(second, RecordInstance)
    assert first is not second
    assert first.record_name == "WindowInfo"
    assert first.Title == "ActionShellScript"
    assert first.Origin.record_name == "Point"
    assert first.Origin.X == 3
    assert first.Origin.Y == 4
    assert first._values[1] is not second._values[1]


def test_record_nesting_round_trips_through_runtime() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Rect\n"
            "Left As Int32\n"
            "Top As Int32\n"
            "Right As Int32\n"
            "Bottom As Int32\n"
            "End Struct\n"
            "Record WindowInfo\n"
            "Title As String\n"
            "Bounds As Rect\n"
            "End Record\n"
            "Record WindowSnapshot\n"
            "Info As WindowInfo\n"
            "IsVisible As Bool\n"
            "End Record\n"
            "Dim info = WindowInfo(\"Mixed nesting\", Rect(10, 20, 640, 480))\n"
            "Dim snapshot = WindowSnapshot(info, True)\n"
            "Dim copy = snapshot\n"
        )
    )

    info = context.variables["info"]
    snapshot = context.variables["snapshot"]
    copy = context.variables["copy"]

    assert isinstance(info, RecordInstance)
    assert isinstance(snapshot, RecordInstance)
    assert isinstance(copy, RecordInstance)
    assert info.Title == "Mixed nesting"
    assert info.Bounds.Right == 640
    assert snapshot.Info.record_name == "WindowInfo"
    assert snapshot.Info.Bounds.Bottom == 480
    assert snapshot.IsVisible is True
    assert snapshot is not copy
    assert snapshot._values[0] is not copy._values[0]


def test_enum_declarations_publish_constants_and_namespace_access() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Enum WindowState\n"
            "Hidden = 0\n"
            "Visible\n"
            "Maximized = Visible + 1\n"
            "End Enum\n"
            "Dim current = WindowState.Visible\n"
            "WriteLn(current)\n"
        )
    )

    assert context.console_output == ["1\n"]
    assert context.get_variable("Hidden") == 0
    assert context.get_variable("Visible") == 1
    assert context.get_variable("Maximized") == 2
    assert context.get_variable("WindowState")["Visible"] == 1
    assert context.get_variable("WindowState")["Maximized"] == 2


def test_enum_types_are_accepted_in_struct_fields() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Enum WindowState\n"
            "Hidden = 0\n"
            "Visible\n"
            "End Enum\n"
            "Struct WindowSnapshot\n"
            "State As WindowState\n"
            "End Struct\n"
            "Dim snapshot = WindowSnapshot(Visible)\n"
        )
    )

    snapshot = context.variables["snapshot"]

    assert isinstance(snapshot, StructInstance)
    assert snapshot.State == 1


def test_struct_field_assignment_is_rejected_for_immutable_values() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="field 'X' is immutable"):
        runtime.compile(
            (
                "Struct Point\n"
                "X As Int32\n"
                "End Struct\n"
                "Dim p = Point(1)\n"
                "p.X = 2\n"
            )
        )


def test_record_field_assignment_is_rejected_for_immutable_values() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Record 'Point' field 'X' is immutable"):
        runtime.compile(
            (
                "Record Point\n"
                "X As Int32\n"
                "End Record\n"
                "Dim p = Point(1)\n"
                "p.X = 2\n"
            )
        )


@pytest.mark.parametrize(
    "script, expected_message",
    [
        (
            (
                "Struct Point\n"
                "X As Int32\n"
                "End Struct\n"
                "Dim p = Point(True)\n"
            ),
            "Struct 'Point' field 'X' expects Int32 but got Bool",
        ),
        (
            (
                "Struct Point\n"
                "X As Bool\n"
                "End Struct\n"
                "Dim p = Point(1)\n"
            ),
            "Struct 'Point' field 'X' expects Bool but got Int",
        ),
        (
            (
                "Struct Point\n"
                "X As Char\n"
                "End Struct\n"
                "Dim p = Point(\"ab\")\n"
            ),
            "Struct 'Point' field 'X' expects Char but got String",
        ),
        (
            (
                "Struct Point\n"
                "X As UInt8\n"
                "End Struct\n"
                "Dim p = Point(-1)\n"
            ),
            "Struct 'Point' field 'X' expects UInt8 but got Int",
        ),
        (
            (
                "Struct Point\n"
                "X As Int8\n"
                "End Struct\n"
                "Dim p = Point(128)\n"
            ),
            "Struct 'Point' field 'X' expects Int8 but got Int",
        ),
        (
            (
                "Struct Point\n"
                "X As Float64\n"
                "End Struct\n"
                "Dim p = Point(1)\n"
            ),
            "Struct 'Point' field 'X' expects Float64 but got Int",
        ),
    ],
)
def test_struct_constructor_rejects_values_with_incompatible_types(
    script: str,
    expected_message: str,
) -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match=expected_message):
        runtime.compile(script)


def test_struct_constructor_rejects_nested_struct_values_with_wrong_type() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Struct 'Pair' field 'First' expects Point but got Int"):
        runtime.compile(
            (
                "Struct Point\n"
                "X As Int32\n"
                "End Struct\n"
                "Struct Pair\n"
                "First As Point\n"
                "End Struct\n"
                "Dim pair = Pair(1)\n"
            )
        )


def test_record_constructor_rejects_nested_record_values_with_wrong_type() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Record 'Pair' field 'First' expects Point but got Int"):
        runtime.compile(
            (
                "Record Point\n"
                "X As Int32\n"
                "End Record\n"
                "Record Pair\n"
                "First As Point\n"
                "End Record\n"
                "Dim pair = Pair(1)\n"
            )
        )


def test_struct_registration_rejects_unknown_field_types() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Struct 'Point' field 'X' uses unknown type: Widget"):
        runtime.compile(
            (
                "Struct Point\n"
                "X As Widget\n"
                "End Struct\n"
            )
        )


def test_record_registration_rejects_unknown_field_types() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Record 'Point' field 'X' uses unknown type: Widget"):
        runtime.compile(
            (
                "Record Point\n"
                "X As Widget\n"
                "End Record\n"
            )
        )


def test_record_registration_rejects_name_collisions_with_structs() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Record already declared: point"):
        runtime.compile(
            (
                "Struct Point\n"
                "X As Int32\n"
                "End Struct\n"
                "Record point\n"
                "Title As String\n"
                "End Record\n"
            )
        )


def test_struct_constructor_rejects_default_values_with_incompatible_types() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Struct 'Point' field 'X' expects Bool but got Int"):
        runtime.compile(
            (
                "Struct Point\n"
                "X As Bool = 1\n"
                "End Struct\n"
                "Dim p = Point()\n"
            )
        )


def test_record_constructor_rejects_default_values_with_incompatible_types() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match="Record 'Point' field 'X' expects Bool but got Int"):
        runtime.compile(
            (
                "Record Point\n"
                "X As Bool = 1\n"
                "End Record\n"
                "Dim p = Point()\n"
            )
        )


@pytest.mark.parametrize(
    "script, expected_cycle",
    [
        (
            (
                "Struct Node\n"
                "Child As Node\n"
                "End Struct\n"
            ),
            "Recursive struct layout detected: Node -> Node",
        ),
        (
            (
                "Struct A\n"
                "Child As B\n"
                "End Struct\n"
                "Struct B\n"
                "Child As A\n"
                "End Struct\n"
            ),
            "Recursive struct layout detected: A -> B -> A",
        ),
    ],
)
def test_struct_registration_rejects_recursive_layout_cycles(
    script: str,
    expected_cycle: str,
) -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match=expected_cycle):
        runtime.compile(script)


def test_struct_layout_metadata_reflects_packed_and_aligned_clauses() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct PackedPoint Packed(1)\n"
            "X As Int32\n"
            "Y As Int16\n"
            "End Struct\n"
            "Struct WideVec Align(4)\n"
            "X As Int32\n"
            "Y As Int32\n"
            "Z As Int32\n"
            "W As Int32\n"
            "End Struct\n"
        )
    )

    packed_summary = runtime._build_struct_layout_summary("PackedPoint", context)
    wide_summary = runtime._build_struct_layout_summary("WideVec", context)

    assert packed_summary.packing == 1
    assert packed_summary.alignment_override is None
    assert packed_summary.field_offsets == (0, 4)
    assert packed_summary.size == 6
    assert packed_summary.alignment == 1

    assert wide_summary.packing is None
    assert wide_summary.alignment_override == 4
    assert wide_summary.field_offsets == (0, 4, 8, 12)
    assert wide_summary.size == 16
    assert wide_summary.alignment == 4


def test_record_constructor_returns_are_copied_and_preserve_nested_values() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Record Point\n"
            "X As Int32\n"
            "Y As Int32\n"
            "End Record\n"
            "Record Pair\n"
            "First As Point\n"
            "Second As Point\n"
            "End Record\n"
            "Func MakePair()\n"
            "Dim result = Pair(Point(1, 2), Point(3, 4))\n"
            "Return result\n"
            "EndFunc\n"
            "Dim pair1 = MakePair()\n"
            "Dim pair2 = pair1\n"
        )
    )

    pair1 = context.variables["pair1"]
    pair2 = context.variables["pair2"]

    assert isinstance(pair1, RecordInstance)
    assert isinstance(pair2, RecordInstance)
    assert pair1 is not pair2
    assert pair1.record_name == "Pair"
    assert pair1.First.record_name == "Point"
    assert pair1.Second.record_name == "Point"
    assert pair1.First.X == 1
    assert pair1.First.Y == 2
    assert pair1.Second.X == 3
    assert pair1.Second.Y == 4
    assert pair1._values[0] is not pair2._values[0]


def test_struct_alignment_overrides_that_cannot_be_honored_are_rejected() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct TooWide Align(16)\n"
            "X As Int32\n"
            "Y As Int32\n"
            "End Struct\n"
        )
    )

    summary = runtime._build_struct_layout_summary("TooWide", context)

    assert summary.is_layout_safe is False
    assert summary.alignment is None
    assert summary.rejection_reason == (
        "Struct alignment cannot be honored by the current runtime: Align(16)"
    )


def test_nested_packed_and_aligned_struct_layouts_remain_independent() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Inner Align(4)\n"
            "Value As Int32\n"
            "End Struct\n"
            "Struct Outer Packed(1)\n"
            "Prefix As Int8\n"
            "Child As Inner\n"
            "Suffix As Int8\n"
            "End Struct\n"
        )
    )

    inner_summary = runtime._build_struct_layout_summary("Inner", context)
    outer_summary = runtime._build_struct_layout_summary("Outer", context)

    assert inner_summary.is_layout_safe is True
    assert inner_summary.packing is None
    assert inner_summary.alignment_override == 4
    assert inner_summary.field_offsets == (0,)
    assert inner_summary.size == 4
    assert inner_summary.alignment == 4

    assert outer_summary.is_layout_safe is True
    assert outer_summary.packing == 1
    assert outer_summary.alignment_override is None
    assert outer_summary.field_offsets == (0, 1, 5)
    assert outer_summary.field_alignments == (1, 1, 1)
    assert outer_summary.size == 6
    assert outer_summary.alignment == 1


def test_struct_function_returns_are_copied_and_preserve_nested_values() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Point\n"
            "X As Int32\n"
            "Y As Int32\n"
            "End Struct\n"
            "Struct Pair\n"
            "First As Point\n"
            "Second As Point\n"
            "End Struct\n"
            "Func MakePair()\n"
            "Dim result = Pair(Point(1, 2), Point(3, 4))\n"
            "Return result\n"
            "EndFunc\n"
            "Dim pair1 = MakePair()\n"
            "Dim pair2 = pair1\n"
        )
    )

    pair1 = context.variables["pair1"]
    pair2 = context.variables["pair2"]

    assert isinstance(pair1, StructInstance)
    assert isinstance(pair2, StructInstance)
    assert pair1 is not pair2
    assert pair1.struct_name == "Pair"
    assert pair1.First.struct_name == "Point"
    assert pair1.Second.struct_name == "Point"
    assert pair1.First.X == 1
    assert pair1.First.Y == 2
    assert pair1.Second.X == 3
    assert pair1.Second.Y == 4
    assert pair1._values[0] is not pair2._values[0]


def test_struct_instance_repr_survives_container_formatting() -> None:
    point = StructInstance("Point", ("X", "Y"), (1, 2))

    assert format_debugger_value([point]) == "[Point(X=1, Y=2)]"
