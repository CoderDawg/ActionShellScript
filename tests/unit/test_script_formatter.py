from __future__ import annotations

import pytest

from core.scripting.formatter import ScriptFormatter


def test_script_formatter_normalizes_and_reindents_text() -> None:
    formatter = ScriptFormatter()

    source = (
        "Func Test(a,b)\r\n"
        "Dim x=1, y=2\r\n"
        "\r\n"
        "\r\n"
        "If foo Then\r\n"
        "CallThing(1,2)\r\n"
        "Else\r\n"
        "CallOther(3,4)\r\n"
        "EndIf\r\n"
        "EndFunc\r\n"
    )

    formatted = formatter.format_script(source)

    assert formatted == (
        "Func Test( a, b )\n"
        "    Dim x = 1, y = 2\n"
        "\n"
        "    If foo Then\n"
        "        CallThing(1, 2)\n"
        "    Else\n"
        "        CallOther(3, 4)\n"
        "    EndIf\n"
        "EndFunc\n"
    )


def test_script_formatter_ast_formatting_is_explicitly_deferred() -> None:
    formatter = ScriptFormatter()

    with pytest.raises(NotImplementedError, match="intentionally deferred"):
        formatter.format_ast(object())


def test_script_formatter_normalizes_struct_blocks_and_typed_declarations() -> None:
    formatter = ScriptFormatter()

    source = (
        "Struct Point\r\n"
        "X as int32=1\r\n"
        "Y as string\r\n"
        "End Struct\r\n"
    )

    formatted = formatter.format_script(source)

    assert formatted == (
        "Struct Point\n"
        "    X As int32 = 1\n"
        "    Y As string\n"
        "End Struct\n"
    )


def test_script_formatter_normalizes_string_buffer_sizes() -> None:
    formatter = ScriptFormatter()

    source = (
        "Declare Func GetModuleFileNameW Lib \"kernel32.dll\" Default (hModule As Ptr, ByRef fileName As string ( 260 ), nSize As UInt32) As UInt32\n"
    )

    formatted = formatter.format_script(source)

    assert formatted == (
        "Declare Func GetModuleFileNameW Lib \"kernel32.dll\" Default (hModule As Ptr, ByRef fileName As String(260), nSize As UInt32) As UInt32\n"
    )


def test_script_formatter_normalizes_struct_layout_clauses() -> None:
    formatter = ScriptFormatter()

    source = (
        "Struct Point packed ( 1 )\r\n"
        "X As Int32\r\n"
        "Y As Int16\r\n"
        "End Struct\r\n"
    )

    formatted = formatter.format_script(source)

    assert formatted == (
        "Struct Point Packed(1)\n"
        "    X As Int32\n"
        "    Y As Int16\n"
        "End Struct\n"
    )


def test_script_formatter_preserves_semicolons_as_statement_separators() -> None:
    formatter = ScriptFormatter()

    source = "Hotkey(\"ctrl\", \"c\");Hotkey(\"alt\", \"v\")\n"

    formatted = formatter.format_script(source)

    assert formatted == "Hotkey(\"ctrl\", \"c\");Hotkey(\"alt\", \"v\")\n"


def test_script_formatter_reindents_select_case_blocks() -> None:
    formatter = ScriptFormatter()

    source = (
        "Select Case value\r\n"
        "Case 1\r\n"
        "WriteLn(\"one\")\r\n"
        "Case Else\r\n"
        "WriteLn(\"other\")\r\n"
        "End Select\r\n"
    )

    formatted = formatter.format_script(source)

    assert formatted == (
        "Select Case value\n"
        "    Case 1\n"
        "        WriteLn(\"one\")\n"
        "    Case Else\n"
        "        WriteLn(\"other\")\n"
        "End Select\n"
    )
