from __future__ import annotations

import pytest

from application.script_document_language_service import ScriptDocumentLanguageService
from core.runtime.builtins.builtin_registry import BUILTIN_FUNCTION_NAMES
from core.scripting.diagnostics import TextSpan
from editor.document.script_document import ScriptDocument
from editor.language_services.semantic_analysis_service import SemanticAnalysisService


def _analyze(text: str, *, document_id: str = "semantic-doc"):
    document = ScriptDocument(document_id=document_id, text=text)
    return ScriptDocumentLanguageService().analyze(document)


def test_analyze_reports_duplicate_labels_in_the_same_scope() -> None:
    analysis = _analyze("Start:\nStart:\n")

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM001"
    assert diagnostic.message == "Duplicate label in block: Start"
    assert diagnostic.span == TextSpan(7, 13)


def test_analyze_reports_missing_goto_target() -> None:
    analysis = _analyze("Goto Missing\n")

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM002"
    assert diagnostic.message == "Goto target label not defined: Missing"
    assert diagnostic.span == TextSpan(0, 12)


def test_analyze_reports_illegal_goto_target_into_a_branch() -> None:
    analysis = _analyze("Goto Inner\nIf x Then\nInner:\nEndIf\n")

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM003"
    assert diagnostic.message == "Goto target enters a structured block: Inner"
    assert diagnostic.span == TextSpan(0, 10)


def test_analyze_reports_return_outside_function() -> None:
    analysis = _analyze("Return 1\n")

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM004"
    assert diagnostic.message == "Return statement used outside of function"
    assert diagnostic.span == TextSpan(0, 8)


def test_analyze_reports_undefined_variable_usage_in_sleep_arguments() -> None:
    analysis = _analyze(
        "Sleep(1000)\n"
        "Sleep(X1000)\n"
        "Sleep(1000)\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM007"
    assert diagnostic.message == "Undefined variable: X1000"
    assert diagnostic.span == TextSpan(18, 23)


def test_analyze_treats_variable_names_case_insensitively_in_sleep_arguments() -> None:
    analysis = _analyze(
        "Dim newFile = 25\n"
        "Sleep(newfile)\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_reports_unsupported_function_calls_inside_ternary_branches() -> None:
    analysis = _analyze(
        "(True) ? SleepX(1) : 0\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM008"
    assert diagnostic.message == "Unsupported function: SleepX. Did you mean Sleep?"


def test_analyze_treats_host_values_case_insensitively() -> None:
    analysis = _analyze("WriteLn(@crlf)\n")

    assert analysis.diagnostics.items == []


@pytest.mark.parametrize(
    "text, expected_message, expected_span",
    [
        (
            "SleepX(1000)\n",
            "Unsupported function: SleepX. Did you mean Sleep?",
            TextSpan(0, 6),
        ),
        (
            "MsgBoxx(1, \"Title\", \"Body\")\n",
            "Unsupported function: MsgBoxx. Did you mean MsgBox?",
            TextSpan(0, 7),
        ),
        (
            "Func CallThing()\nEndFunc\nCallThng()\n",
            "Unsupported function: CallThng. Did you mean CallThing?",
            TextSpan(25, 33),
        ),
    ],
)
def test_analyze_reports_unsupported_function_calls_with_suggestions(
    text: str,
    expected_message: str,
    expected_span: TextSpan,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM008"
    assert diagnostic.message == expected_message
    assert diagnostic.span == expected_span


def test_analyze_allows_calls_to_declared_functions() -> None:
    analysis = _analyze(
        "Func Demo()\n"
        "Return 1\n"
        "EndFunc\n"
        "Demo()\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_allows_calls_to_declared_external_functions() -> None:
    analysis = _analyze(
        "Declare Func Ping Lib \"test.dll\" () As Int32\n"
        "Ping()\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_allows_string_external_function_signatures() -> None:
    analysis = _analyze(
        "Declare Func LstrlenW Lib \"kernel32.dll\" CDecl Alias \"lstrlenW\" (text As String) As Int32\n"
        "Declare Func GetCommandLineW Lib \"kernel32.dll\" Default () As String\n"
        "Declare Func GetModuleFileNameW Lib \"kernel32.dll\" Default (hModule As Ptr, ByRef fileName As String ( 260 ), nSize As UInt32) As UInt32\n"
        'Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default (text As String)\n'
    )

    assert analysis.diagnostics.items == []


@pytest.mark.parametrize(
    "text, expected_code, expected_message",
    [
        (
            "Declare Func Ping Lib \"test.dll\" (value As Widget) As Int32\n",
            "SEM015",
            "External function type is unknown: Widget",
        ),
        (
            "Declare Func Ping Lib \"\" () As Int32\n",
            "SEM011",
            "External function library name must not be empty",
        ),
        (
            "Declare Func Ping Lib \"test.dll\" (left As Int32, left As Int32) As Int32\n",
            "SEM013",
            "External function parameter name is duplicated: left",
        ),
        (
            "Declare Func Ping Lib \"test.dll\" (ByRef text As String) As Int32\n",
            "SEM020",
            "External function string buffer size must be specified for: text",
        ),
        (
            "Declare Func Ping Lib \"test.dll\" (ByRef text As String(0)) As Int32\n",
            "SEM021",
            "External function string buffer size is invalid: text",
        ),
        (
            "Struct BigRet\nA As Int64\nB As Int64\nC As Int64\nEnd Struct\nDeclare Func MakeBig Lib \"test.dll\" () As BigRet\n",
            "SEM028",
            "External function struct return is not supported by the current runtime: BigRet",
        ),
    ],
)
def test_analyze_rejects_unsafe_external_function_signatures(
    text: str,
    expected_code: str,
    expected_message: str,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == expected_code
    assert diagnostic.message == expected_message


def test_analyze_allows_struct_declarations_with_typed_fields() -> None:
    analysis = _analyze(
        "Struct Point\n"
        "X As Int32 = 1\n"
        "Y As String = \"a\"\n"
        "End Struct\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_allows_record_declarations_with_typed_fields() -> None:
    analysis = _analyze(
        "Record WindowInfo\n"
        "Title As String = \"App\"\n"
        "ClassName As String\n"
        "IsVisible As Bool\n"
        "End Record\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_allows_enum_declarations_and_member_usage() -> None:
    analysis = _analyze(
        "Enum WindowState\n"
        "Hidden = 0\n"
        "Visible\n"
        "End Enum\n"
        "Sleep(Visible)\n"
        "Sleep(WindowState.Hidden)\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_rejects_duplicate_enum_member_names() -> None:
    analysis = _analyze(
        "Enum WindowState\n"
        "Visible = 1\n"
        "Visible = 2\n"
        "End Enum\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM033"
    assert diagnostic.message == "Enum 'WindowState' member already declared: Visible"


def test_analyze_rejects_record_name_collisions_with_structs() -> None:
    analysis = _analyze(
        "Struct Point\n"
        "X As Int32\n"
        "End Struct\n"
        "Record Point\n"
        "Title As String\n"
        "End Record\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM029"
    assert diagnostic.message == "Record already declared: Point"


def test_analyze_allows_struct_layout_clauses() -> None:
    analysis = _analyze(
        "Struct Point Packed(1)\n"
        "X As Int32\n"
        "Y As Int16\n"
        "End Struct\n"
        "Struct Vec4 Align(4)\n"
        "X As Int32\n"
        "Y As Int32\n"
        "Z As Int32\n"
        "W As Int32\n"
        "End Struct\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_allows_record_constructor_calls() -> None:
    analysis = _analyze(
        "Record Point\n"
        "X As Int32\n"
        "Y As Int32\n"
        "End Record\n"
        "Dim p = Point(1, 2)\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_rejects_unknown_record_field_types() -> None:
    analysis = _analyze(
        "Record Point\n"
        "X As Widget\n"
        "End Record\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM030"
    assert diagnostic.message == "Record 'Point' field 'X' uses unknown type: Widget"


def test_analyze_rejects_recursive_record_layouts() -> None:
    analysis = _analyze(
        "Record A\n"
        "Child As B\n"
        "End Record\n"
        "Record B\n"
        "Child As A\n"
        "End Record\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM031"
    assert diagnostic.message == "Recursive record layout detected: A -> B -> A"


@pytest.mark.parametrize(
    "text, expected_code, expected_message",
    [
        (
            "Struct Point Packed(0)\nX As Int32\nEnd Struct\n",
            "SEM024",
            "External function struct layout value must be positive: Packed(0)",
        ),
        (
            "Struct Point Packed(3)\nX As Int32\nEnd Struct\n",
            "SEM025",
            "External function struct layout value must be a power of two: Packed(3)",
        ),
        (
            "Struct Point Align(16)\nX As Int32\nEnd Struct\n",
            "SEM027",
            "Struct alignment cannot be honored by the current runtime: Align(16)",
        ),
    ],
)
def test_analyze_rejects_invalid_struct_layout_clauses(
    text: str,
    expected_code: str,
    expected_message: str,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == expected_code
    assert diagnostic.message == expected_message


def test_analyze_allows_struct_constructor_calls() -> None:
    analysis = _analyze(
        "Struct Point\n"
        "X As Int32\n"
        "End Struct\n"
        "Dim p = Point(1)\n"
    )

    assert analysis.diagnostics.items == []


def test_analyze_rejects_recursive_layouts_in_external_signatures() -> None:
    analysis = _analyze(
        "Struct A\n"
        "Child As B\n"
        "End Struct\n"
        "Struct B\n"
        "Child As A\n"
        "End Struct\n"
        "Declare Func Ping Lib \"test.dll\" (value As A) As Int32\n"
    )

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM018"
    assert diagnostic.message == "External function signature contains a recursive struct layout: A -> B -> A"


@pytest.mark.parametrize(
    "candidate_name, expected_threshold",
    [
        ("abs", 0.88),
        ("sleep", 0.8),
        ("callthing", 0.76),
        ("mouseclickdrag", 0.72),
    ],
)
def test_function_replacement_threshold_varies_by_candidate_length(
    candidate_name: str,
    expected_threshold: float,
) -> None:
    service = SemanticAnalysisService()

    assert service._function_replacement_similarity_threshold(candidate_name) == expected_threshold


def test_builtin_argument_rules_only_reference_registered_builtins() -> None:
    service = SemanticAnalysisService()

    assert set(service._BUILTIN_ARGUMENT_INDEXES).issubset(BUILTIN_FUNCTION_NAMES)


@pytest.mark.parametrize(
    "text, marker",
    [
        ("SetCurrentEventDelay(X125)\n", "X125"),
        ("MouseMove(X10, 20)\n", "X10"),
        ("MouseClick(\"left\", 10, X20, 1)\n", "X20"),
        ("MouseClickDrag(\"left\", X1, 2, 3, 4)\n", "X1"),
        ("MouseDrag(\"left\", 1, 2, 3, 4, X30)\n", "X30"),
        ("MouseWheel(X5)\n", "X5"),
        ("MsgBox(X1, \"Title\", \"Body\", 2)\n", "X1"),
        ("KeyPress(\"a\", X3)\n", "X3"),
        ("BitRotate(X7, 2)\n", "X7"),
        ("BitShift(1, X8)\n", "X8"),
        ("BinaryMid([1, 2, 3], 1, X9)\n", "X9"),
        ("BinaryToString(\"abc\", X10)\n", "X10"),
        ("SetMouseMoveSpeed(X11)\n", "X11"),
        ("Ceiling(X12)\n", "X12"),
        ("Int(X34)\n", "X34"),
        ("Round(X35, 2)\n", "X35"),
        ("Round(1.23, X36)\n", "X36"),
        ("Mod(X13, 2)\n", "X13"),
        ("Abs(X14)\n", "X14"),
        ("Chr(X15)\n", "X15"),
        ("ChrW(X16)\n", "X16"),
        ("BitAnd(X17, 2)\n", "X17"),
        ("BitOr(1, X18)\n", "X18"),
        ("BitXor(X19, 2)\n", "X19"),
        ("BitNot(X21)\n", "X21"),
        ("BitNotUnsigned(X22)\n", "X22"),
        ("PixelGetColor(X23, 2)\n", "X23"),
        ("PixelSearch(X24, 2, 3, 4, 5)\n", "X24"),
        ("MsgBox(1, \"Title\", \"Body\", 2, X25)\n", "X25"),
        ("StringCompare(\"a\", \"b\", X26)\n", "X26"),
        ("StringLeft(\"abc\", X27)\n", "X27"),
        ("StringMid(\"abc\", X28, 2)\n", "X28"),
        ("StringMid(\"abc\", 1, X29)\n", "X29"),
        ("StringReplace(\"abc\", X30, \"z\")\n", "X30"),
        ("StringRight(\"abc\", X31)\n", "X31"),
        ("StringTrimLeft(\"abc\", X32)\n", "X32"),
        ("StringTrimRight(\"abc\", X33)\n", "X33"),
    ],
)
def test_analyze_reports_undefined_variable_usage_in_numeric_builtin_arguments(
    text: str,
    marker: str,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    start = text.index(marker)
    assert diagnostic.code == "SEM007"
    assert diagnostic.message == f"Undefined variable: {marker}"
    assert diagnostic.span == TextSpan(start, start + len(marker))


@pytest.mark.parametrize(
    "text, expected_code, expected_message, expected_span",
    [
        (
            "Exit\n",
            "SEM006",
            "Exit statement used outside of loop",
            TextSpan(0, 4),
        ),
        (
            "Continue\n",
            "SEM005",
            "Continue statement used outside of loop",
            TextSpan(0, 8),
        ),
    ],
)
def test_analyze_reports_loop_control_outside_a_loop(
    text: str,
    expected_code: str,
    expected_message: str,
    expected_span: TextSpan,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == expected_code
    assert diagnostic.message == expected_message
    assert diagnostic.span == expected_span


@pytest.mark.parametrize(
    "text, expected_code, expected_message, expected_span",
    [
        (
            "While x\nContinue For\nWEnd\n",
            "SEM005",
            "Continue statement for target 'for' used outside of matching loop",
            TextSpan(8, 20),
        ),
        (
            "For i = 1 To 3\nExit While\nNext\n",
            "SEM006",
            "Exit statement for target 'while' used outside of matching loop",
            TextSpan(15, 25),
        ),
    ],
)
def test_analyze_reports_loop_control_with_an_invalid_target(
    text: str,
    expected_code: str,
    expected_message: str,
    expected_span: TextSpan,
) -> None:
    analysis = _analyze(text)

    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == expected_code
    assert diagnostic.message == expected_message
    assert diagnostic.span == expected_span


def test_analyze_keeps_labels_isolated_between_top_level_and_function_scope() -> None:
    analysis = _analyze(
        "Start:\nFunc Demo()\nStart:\nReturn\nEndFunc\n",
    )

    assert analysis.diagnostics.items == []
    assert analysis.parse_succeeded is True
