from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.runtime.script_runtime import ScriptRuntime
from core.runtime.runtime_errors import RuntimeErrorMessages
from core.runtime.struct_values import StructInstance


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows DLL interop only")


def test_runtime_calls_external_function_returning_a_pointer() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            'Declare Func GetDesktopWindow Lib "user32.dll" StdCall () As Ptr\n'
            'Dim desktop = GetDesktopWindow()\n'
        )
    )

    assert isinstance(context.variables["desktop"], int)
    assert context.variables["desktop"] > 0


def test_runtime_rejects_oversized_struct_return_values() -> None:
    runtime = ScriptRuntime()

    with pytest.raises(RuntimeError, match=RuntimeErrorMessages.external_function_struct_return_not_supported("BigRet")):
        runtime.compile(
            (
                "Struct BigRet\n"
                "A As Int64\n"
                "B As Int64\n"
                "C As Int64\n"
                "End Struct\n"
                'Declare Func MakeBig Lib "test.dll" () As BigRet\n'
            )
        )


def test_runtime_marshals_string_arguments_and_return_values() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
            (
                'Declare Func WcsLen Lib "msvcrt.dll" CDecl Alias "wcslen" (text As String) As UInt64\n'
                'Declare Func GetCommandLineW Lib "kernel32.dll" Default () As String\n'
                'Declare Func GetModuleFileNameW Lib "kernel32.dll" Default (hModule As Ptr, ByRef fileName As String ( 260 ), nSize As UInt32) As UInt32\n'
                'Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default (text As String)\n'
                'Dim length = WcsLen("hello from ActionShellScript")\n'
                'Dim command_line = GetCommandLineW()\n'
                'Dim file_name = ""\n'
                'Dim file_name_length = GetModuleFileNameW(0, file_name, 260)\n'
                'OutputDebugStringW(command_line)\n'
        )
    )

    assert context.variables["length"] == len("hello from ActionShellScript")
    assert isinstance(context.variables["command_line"], str)
    assert context.variables["command_line"]
    assert isinstance(context.variables["file_name_length"], int)
    assert context.variables["file_name_length"] > 0
    assert isinstance(context.variables["file_name"], str)
    assert context.variables["file_name"]


def test_runtime_marshals_byref_primitive_external_arguments() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            'Declare Func QueryPerformanceCounter Lib "kernel32.dll" '
            '(ByRef counter As Int64) As Bool\n'
            'Dim counter = 0\n'
            'Dim ok = QueryPerformanceCounter(counter)\n'
        )
    )

    assert context.variables["ok"] is True
    assert isinstance(context.variables["counter"], int)
    assert context.variables["counter"] != 0


def test_runtime_marshals_byref_struct_external_arguments() -> None:
    runtime = ScriptRuntime()

    context = runtime.compile(
        (
            "Struct Rect\n"
            "Left As Int32\n"
            "Top As Int32\n"
            "Right As Int32\n"
            "Bottom As Int32\n"
            "End Struct\n"
            'Declare Func GetDesktopWindow Lib "user32.dll" () As Ptr\n'
            'Declare Func GetWindowRect Lib "user32.dll" (hWnd As Ptr, ByRef rect As Rect) As Bool\n'
            "Dim desktop = GetDesktopWindow()\n"
            "Dim rect = Rect(0, 0, 0, 0)\n"
            "Dim ok = GetWindowRect(desktop, rect)\n"
        )
    )

    assert context.variables["ok"] is True
    rect = context.variables["rect"]
    assert isinstance(rect, StructInstance)
    assert rect.struct_name == "Rect"
    assert rect.field_names() == ("Left", "Top", "Right", "Bottom")
    assert isinstance(rect.Left, int)
    assert isinstance(rect.Top, int)
    assert isinstance(rect.Right, int)
    assert isinstance(rect.Bottom, int)


def test_struct_and_dll_demo_sample_compiles_and_runs() -> None:
    runtime = ScriptRuntime()

    script = Path("samples/struct_and_dll_demo.ass").read_text(encoding="utf-8")
    context = runtime.compile(script)

    assert context.variables["origin"].X == 0
    assert context.variables["origin"].Y == 0
    assert context.variables["size"].X == 640
    assert context.variables["size"].Y == 480
    assert context.variables["rect_ok"] is True
    assert isinstance(context.variables["module_path_length"], int)
    assert context.variables["module_path_length"] > 0
    assert isinstance(context.variables["module_path"], str)
    assert context.variables["module_path"]
