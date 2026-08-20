# Struct and DLL Quickstart

This guide shows the practical `Struct` and external-function syntax currently supported by ActionShellScript.

Use this page when you want a working example first and the ABI details second. For the exact layout contract, see [Struct Layout Contract](struct_layout_contract.md).

## What You Can Write

`Struct` gives you a fixed-layout value type with typed fields:

```ass
Struct Point
    X As Int32
    Y As Int32
End Struct

Dim p = Point(10, 20)
WriteLn(p.X)
WriteLn(p.Y)
```

Constructor calls use the struct name like a function call. The field order in the constructor matches the field order in the declaration.

If you want a script-only value object instead of a DLL-friendly ABI type, use `Record`:

```ass
Record WindowInfo
    Title As String
    ClassName As String
    IsVisible As Bool
End Record

Dim info = WindowInfo("My App", "MainWindow", True)
WriteLn(info.Title)
WriteLn(info.ClassName)
```

`Record` follows the same constructor and copy-by-value feel as `Struct`, but it is intended for script data, not native marshaling. That makes it a better fit for text-bearing objects or higher-level UI snapshots.

You can also declare external functions and subs for Windows DLL interop:

```ass
Declare Func GetDesktopWindow Lib "user32.dll" StdCall () As Ptr
Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default (text As String)
```

`Declare Func` returns a value. `Declare Sub` does not.

For writable string buffers, use `ByRef String(n)` with an explicit size:

```ass
Declare Func GetModuleFileNameW Lib "kernel32.dll" Default (hModule As Ptr, ByRef fileName As String(260), nSize As UInt32) As UInt32
```

## Recommended Pattern

The easiest way to use the feature is:

1. define one or more fixed-layout structs
2. declare the Win32 function signatures you need
3. call the constructor to build struct values
4. pass a writable `String(n)` buffer when the API needs an output string
5. use `Ptr` for opaque handles and window handles

## Runnable Sample

The repository includes a Windows sample script that exercises the full feature set:

- [Struct and DLL demo script](../../samples/struct_and_dll_demo.ass)
- [Record demo script](../../samples/record_demo.ass)
- [GetCursorPos smoke sample](../../samples/struct_and_dll_cursor_pos_demo.ass)
- [GetWindowRect wrapper demo](../../samples/window_rect_wrapper_demo.ass)
- [GetClientRect wrapper demo](../../samples/client_rect_wrapper_demo.ass)
- [GetWindowText wrapper demo](../../samples/window_text_wrapper_demo.ass)
- [GetWindowLongPtr wrapper demo](../../samples/window_long_ptr_wrapper_demo.ass)
- [Parent/enabled wrapper demo](../../samples/window_parent_enabled_wrapper_demo.ass)
- [GetClassName wrapper demo](../../samples/class_name_wrapper_demo.ass)
- [Window state wrapper demo](../../samples/window_state_wrapper_demo.ass) (`IsZoomed`, `IsIconic`, and `IsWindowVisible`)
- [GetWindowPlacement wrapper demo](../../samples/window_placement_wrapper_demo.ass)
- [Monitor Info wrapper demo flow](../../samples/README.md#monitor-info-wrapper-demo)
- [Monitor Info demo script](../../samples/monitor_info_demo.ass)

If you only want a tiny end-to-end check for `Struct POINT` plus `GetCursorPos`, start with the smoke sample above.

It demonstrates:

- typed struct fields
- struct constructor calls
- `Declare Func`
- `Declare Sub`
- `ByRef String(260)` output buffers
- a small Win32 call chain using `GetDesktopWindow`, `GetWindowRect`, and `GetModuleFileNameW`

Run it from the repository root with:

```powershell
ass-debug script .\samples\struct_and_dll_demo.ass
```

If you want to step through the calls, add `--step`.

## Notes

- `Struct` is intended to remain cross-platform.
- DLL interop is Windows-only in practice.
- `String` fields inside user-declared ABI structs are not layout-safe. For the built-in `GetMonitorInfoEx()` wrapper, `MonitorInfoEx.szDevice` is a normal script `String` field because the runtime owns the native buffer. See the [Monitor Info Wrapper Path](structs_and_dlls.md#monitor-info-wrapper-path) for the full flow.
- The runtime copies struct values on assignment and return.

## Related Docs

- [Struct Layout Contract](struct_layout_contract.md)
- [Structs and DLL Interop](structs_and_dlls.md)
- [Docs Index](../index.md)
