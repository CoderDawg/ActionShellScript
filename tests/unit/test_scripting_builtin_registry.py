from __future__ import annotations

import ast
from pathlib import Path

from core.runtime.builtins.builtin_registry import BUILTIN_FUNCTION_NAMES as RUNTIME_BUILTIN_FUNCTION_NAMES
from core.runtime.builtins.builtin_registry import format_builtin_function_name
from core.runtime.runtime_errors import RuntimeErrorMessages
from core.scripting import BUILTIN_FUNCTION_NAMES as SCRIPTING_BUILTIN_FUNCTION_NAMES


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = REPO_ROOT / "core" / "runtime" / "script_runtime.py"


def test_shared_builtin_registry_matches_runtime_builtin_registry() -> None:
    assert SCRIPTING_BUILTIN_FUNCTION_NAMES == RUNTIME_BUILTIN_FUNCTION_NAMES


def test_builtin_registry_matches_runtime_dispatch_surface() -> None:
    # Keep the registry and runtime dispatch in lockstep so adding a builtin
    # requires touching both places intentionally.
    runtime_names = _load_runtime_builtin_names()

    assert runtime_names == set(RUNTIME_BUILTIN_FUNCTION_NAMES)


def test_builtin_display_name_helper_uses_pretty_casing() -> None:
    assert format_builtin_function_name("sleep") == "Sleep"
    assert format_builtin_function_name("time") == "Time"
    assert format_builtin_function_name("hotkey") == "HotKey"
    assert format_builtin_function_name("diagwrite") == "DiagWrite"
    assert format_builtin_function_name("diagwriteln") == "DiagWriteLn"
    assert format_builtin_function_name("localtime") == "LocalTime"
    assert format_builtin_function_name("utctime") == "UTCTime"
    assert format_builtin_function_name("nowdatetime") == "NowDateTime"
    assert format_builtin_function_name("datetostring") == "DateToString"
    assert format_builtin_function_name("datetolocalstring") == "DateToLocalString"
    assert format_builtin_function_name("datetoutcstring") == "DateToUTCString"
    assert format_builtin_function_name("parsedatetime") == "ParseDateTime"
    assert format_builtin_function_name("formatdatetime") == "FormatDateTime"
    assert format_builtin_function_name("dateadd") == "DateAdd"
    assert format_builtin_function_name("datediff") == "DateDiff"
    assert format_builtin_function_name("converttimezone") == "ConvertTimeZone"
    assert format_builtin_function_name("utcoffset") == "UTCOffset"
    assert format_builtin_function_name("timezoneoffset") == "TimeZoneOffset"
    assert format_builtin_function_name("formatdatetimeinoffset") == "FormatDateTimeInOffset"
    assert format_builtin_function_name("utcdatetime") == "UTCDateTime"
    assert format_builtin_function_name("parsedatetimeinoffset") == "ParseDateTimeInOffset"
    assert format_builtin_function_name("startofday") == "StartOfDay"
    assert format_builtin_function_name("endofday") == "EndOfDay"
    assert format_builtin_function_name("startofmonth") == "StartOfMonth"
    assert format_builtin_function_name("endofmonth") == "EndOfMonth"
    assert format_builtin_function_name("startofweek") == "StartOfWeek"
    assert format_builtin_function_name("dayofweek") == "DayOfWeek"
    assert format_builtin_function_name("dayofyear") == "DayOfYear"
    assert format_builtin_function_name("datepart") == "DatePart"
    assert format_builtin_function_name("dateserial") == "DateSerial"
    assert format_builtin_function_name("timeserial") == "TimeSerial"
    assert format_builtin_function_name("daysinmonth") == "DaysInMonth"
    assert format_builtin_function_name("isleapyear") == "IsLeapYear"
    assert format_builtin_function_name("isdate") == "IsDate"
    assert format_builtin_function_name("istime") == "IsTime"
    assert format_builtin_function_name("nowdate") == "NowDate"
    assert format_builtin_function_name("nowtime") == "NowTime"
    assert format_builtin_function_name("msgbox") == "MsgBox"
    assert format_builtin_function_name("mouseclickdrag") == "MouseClickDrag"
    assert format_builtin_function_name("getmousemovespeed") == "GetMouseMoveSpeed"
    assert format_builtin_function_name("setmousemovespeed") == "SetMouseMoveSpeed"
    assert format_builtin_function_name("arraylength") == "ArrayLength"
    assert format_builtin_function_name("arrayinsert") == "ArrayInsert"
    assert format_builtin_function_name("arraycontains") == "ArrayContains"
    assert format_builtin_function_name("arraycontainsall") == "ArrayContainsAll"
    assert format_builtin_function_name("arraycount") == "ArrayCount"
    assert format_builtin_function_name("arrayinitialize") == "ArrayInitialize"
    assert format_builtin_function_name("arrayclear") == "ArrayClear"
    assert format_builtin_function_name("arrayclone") == "ArrayClone"
    assert format_builtin_function_name("arrayindexof") == "ArrayIndexOf"
    assert format_builtin_function_name("arraylastindexof") == "ArrayLastIndexOf"
    assert format_builtin_function_name("arrayjoin") == "ArrayJoin"
    assert format_builtin_function_name("arrayreverse") == "ArrayReverse"
    assert format_builtin_function_name("arraysort") == "ArraySort"
    assert format_builtin_function_name("arrayunique") == "ArrayUnique"
    assert format_builtin_function_name("arraypush") == "ArrayPush"
    assert format_builtin_function_name("arraypop") == "ArrayPop"
    assert format_builtin_function_name("arrayremove") == "ArrayRemove"
    assert format_builtin_function_name("arrayremoveall") == "ArrayRemoveAll"
    assert format_builtin_function_name("arraytostring") == "ArrayToString"
    assert format_builtin_function_name("arrayslice") == "ArraySlice"
    assert format_builtin_function_name("stringcompare") == "StringCompare"
    assert format_builtin_function_name("stringisalpha") == "StringIsAlpha"
    assert format_builtin_function_name("stringisalphanumeric") == "StringIsAlphaNumeric"
    assert format_builtin_function_name("stringisascii") == "StringIsASCII"
    assert format_builtin_function_name("stringisdigit") == "StringIsDigit"
    assert format_builtin_function_name("stringisfloat") == "StringIsFloat"
    assert format_builtin_function_name("stringisint") == "StringIsInt"
    assert format_builtin_function_name("stringislower") == "StringIsLower"
    assert format_builtin_function_name("stringisspace") == "StringIsSpace"
    assert format_builtin_function_name("stringisupper") == "StringIsUpper"
    assert format_builtin_function_name("stringinstr") == "StringInStr"
    assert format_builtin_function_name("stringlength") == "StringLength"
    assert format_builtin_function_name("stringleft") == "StringLeft"
    assert format_builtin_function_name("stringreplace") == "StringReplace"
    assert format_builtin_function_name("stringreverse") == "StringReverse"
    assert format_builtin_function_name("stringright") == "StringRight"
    assert format_builtin_function_name("stringcontains") == "StringContains"
    assert format_builtin_function_name("stringendswith") == "StringEndsWith"
    assert format_builtin_function_name("stringjoin") == "StringJoin"
    assert format_builtin_function_name("stringmid") == "StringMid"
    assert format_builtin_function_name("stringsplit") == "StringSplit"
    assert format_builtin_function_name("stringstartswith") == "StringStartsWith"
    assert format_builtin_function_name("stringtrimleft") == "StringTrimLeft"
    assert format_builtin_function_name("stringtrimright") == "StringTrimRight"
    assert format_builtin_function_name("stringtolower") == "StringToLower"
    assert format_builtin_function_name("stringtoupper") == "StringToUpper"
    assert format_builtin_function_name("copyfile") == "CopyFile"
    assert format_builtin_function_name("copydir") == "CopyDir"
    assert format_builtin_function_name("filechecksum") == "FileChecksum"
    assert format_builtin_function_name("fileinfo") == "FileInfo"
    assert format_builtin_function_name("filecompare") == "FileCompare"
    assert format_builtin_function_name("filehash") == "FileHash"
    assert format_builtin_function_name("filesize") == "FileSize"
    assert format_builtin_function_name("filetime") == "FileTime"
    assert format_builtin_function_name("enumeratefiles") == "EnumerateFiles"
    assert format_builtin_function_name("movefile") == "MoveFile"
    assert format_builtin_function_name("movedir") == "MoveDir"
    assert format_builtin_function_name("walkdir") == "WalkDir"
    assert format_builtin_function_name("directorylist") == "DirectoryList"
    assert format_builtin_function_name("directorydelete") == "DirectoryDelete"
    assert format_builtin_function_name("filelist") == "FileList"
    assert format_builtin_function_name("removedir") == "RemoveDir"
    assert format_builtin_function_name("regexmatch") == "RegexMatch"
    assert format_builtin_function_name("regexreplace") == "RegexReplace"


def test_runtime_error_messages_pretty_case_builtin_names() -> None:
    assert RuntimeErrorMessages.unsupported_function("sleep") == "Unsupported function: Sleep"
    assert RuntimeErrorMessages.expects_argument_count("msgbox", 3) == "MsgBox expects 3 argument(s)"
    assert RuntimeErrorMessages.argument_must_be_string("mouseclick", 1) == "MouseClick argument 1 must be a string"
    assert RuntimeErrorMessages.invalid_date_time_text("parsedatetime", "bad") == "ParseDateTime text is not a valid date/time: bad"
    assert RuntimeErrorMessages.argument_must_be_datetime_value("formatdatetime", 1) == "FormatDateTime argument 1 must be a number or tm struct"


def _load_runtime_builtin_names() -> set[str]:
    module = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"), filename=str(RUNTIME_PATH))
    builtin_names: set[str] = set()

    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ScriptRuntime":
            continue

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "_HOST_INTERACTION_BUILTIN_NAMES":
                        builtin_names.update(_string_set_from_ast(item.value))
            elif isinstance(item, ast.FunctionDef) and item.name == "_execute_builtin_call":
                builtin_names.update(_builtin_names_from_execute_builtin_call(item))

    return builtin_names


def _string_set_from_ast(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Set):
        return {
            element.value.lower()
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }

    if isinstance(node, ast.Call):
        values: set[str] = set()
        for arg in node.args:
            values.update(_string_set_from_ast(arg))
        return values

    return set()


def _builtin_names_from_execute_builtin_call(function_node: ast.FunctionDef) -> set[str]:
    builtin_names: set[str] = set()
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "normalized_name":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            builtin_names.add(comparator.value.lower())
    return builtin_names
