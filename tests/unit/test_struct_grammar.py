from __future__ import annotations

from core.scripting import ast_nodes as ast
from core.scripting.diagnostics import DiagnosticBag
from core.scripting.lexer import lex
from core.scripting.parser import Parser


def test_struct_grammar_parses_typed_fields_and_end_struct() -> None:
    script = (
        "Struct Point\n"
        "X As Int32\n"
        "Y As string = 0\n"
        "End Struct\n"
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.StructDecl)
    assert statement.name == "Point"
    assert [field.name for field in statement.fields] == ["X", "Y"]
    assert [field.type_name for field in statement.fields] == ["Int32", "String"]
    assert statement.fields[1].initializer is not None


def test_struct_grammar_parses_packed_struct_layout() -> None:
    script = (
        "Struct Point Packed(1)\n"
        "X As Int32\n"
        "Y As Int16\n"
        "End Struct\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.StructDecl)
    assert statement.packing == 1
    assert statement.alignment is None


def test_struct_grammar_parses_aligned_struct_layout() -> None:
    script = (
        "Struct Vec4 Align(16)\n"
        "X As Int32\n"
        "Y As Int32\n"
        "Z As Int32\n"
        "W As Int32\n"
        "End Struct\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.StructDecl)
    assert statement.packing is None
    assert statement.alignment == 16


def test_record_grammar_parses_script_only_records() -> None:
    script = (
        "Record WindowInfo\n"
        "Title As String\n"
        "ClassName As String\n"
        "IsVisible As Bool\n"
        "End Record\n"
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.RecordDecl)
    assert statement.name == "WindowInfo"
    assert [field.name for field in statement.fields] == ["Title", "ClassName", "IsVisible"]
    assert [field.type_name for field in statement.fields] == ["String", "String", "Bool"]


def test_enum_grammar_parses_members_and_end_enum() -> None:
    script = (
        "Enum WindowState\n"
        "Hidden = 0\n"
        "Visible\n"
        "Minimized = Hidden + 2\n"
        "End Enum\n"
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.EnumDecl)
    assert statement.name == "WindowState"
    assert [member.name for member in statement.members] == ["Hidden", "Visible", "Minimized"]
    assert statement.members[0].initializer is not None
    assert statement.members[2].initializer is not None


def test_enum_grammar_parses_compact_end_enum() -> None:
    script = (
        "Enum HotKeyState\n"
        "Idle\n"
        "Pressed\n"
        "EndEnum\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.EnumDecl)
    assert [member.name for member in statement.members] == ["Idle", "Pressed"]


def test_struct_grammar_reports_duplicate_layout_clauses() -> None:
    diagnostics = DiagnosticBag()
    script = (
        "Struct Point Packed(1) Align(16)\n"
        "X As Int32\n"
        "End Struct\n"
    )

    program = Parser(lex(script), diagnostics=diagnostics).parse()

    assert len(program.statements) == 1
    assert len(diagnostics.items) == 1
    diagnostic = diagnostics.items[0]
    assert diagnostic.code == "SEM023"


def test_typed_locals_and_parameters_share_the_canonical_type_vocabulary() -> None:
    script = (
        "Dim value As int32 = 1\n"
        "Func Demo(ByRef count As uint64 = 2, amount As string)\n"
        "Return value\n"
        "EndFunc\n"
    )

    program = Parser(lex(script)).parse()

    var_decl = program.statements[0]
    assert isinstance(var_decl, ast.VarDecl)
    assert var_decl.declarators[0].type_name == "Int32"

    func_decl = program.statements[1]
    assert isinstance(func_decl, ast.FunctionDecl)
    assert [param.type_name for param in func_decl.params] == ["UInt64", "String"]
    assert func_decl.params[0].is_byref is True


def test_declare_func_parses_external_function_signatures() -> None:
    script = (
        "Declare Func MessageBoxW Lib \"user32.dll\" Alias \"MessageBoxW\" "
        "(hWnd As Ptr, text As String) As Int32\n"
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.ExternalFunctionDecl)
    assert statement.name == "MessageBoxW"
    assert statement.library_name == "user32.dll"
    assert statement.export_name == "MessageBoxW"
    assert statement.return_type_name == "Int32"
    assert [param.name for param in statement.params] == ["hWnd", "text"]
    assert [param.type_name for param in statement.params] == ["Ptr", "String"]
    assert [param.string_buffer_size for param in statement.params] == [None, None]


def test_declare_sub_parses_void_external_signatures() -> None:
    script = (
        'Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default '
        '(text As String)\n'
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.ExternalFunctionDecl)
    assert statement.name == "OutputDebugStringW"
    assert statement.is_sub is True
    assert statement.return_type_name == ""
    assert statement.library_name == "kernel32.dll"
    assert statement.export_name == "OutputDebugStringW"
    assert statement.calling_convention == "default"
    assert [param.type_name for param in statement.params] == ["String"]
    assert [param.string_buffer_size for param in statement.params] == [None]


def test_declare_func_parses_explicit_string_buffer_sizes() -> None:
    script = (
        "Declare Func GetModuleFileNameW Lib \"kernel32.dll\" Default "
        "(hModule As Ptr, ByRef fileName As String(260), nSize As UInt32) As UInt32\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.ExternalFunctionDecl)
    assert [param.type_name for param in statement.params] == ["Ptr", "String", "UInt32"]
    assert [param.string_buffer_size for param in statement.params] == [None, 260, None]
