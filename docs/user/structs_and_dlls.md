# Structs and DLL Interop

This page covers the current scripting support for `Struct`, external declarations, and Win32 DLL interop.

If you want a hands-on walkthrough first, start with [Struct and DLL Quickstart](struct_and_dll_quickstart.md). That page now includes a short `Record` quickstart too.

Portability guarantee:

- `Struct` is a core language feature and is intended to remain available on non-Windows platforms.
- DLL interop is a separate Windows-only capability and should only affect scripts that use `Declare Func` or `Declare Sub`.
- Scripts that use `Struct` without external declarations should continue to run cross-platform.

## Structs

`Struct` declares an immutable value type with fixed fields:

```ass
Struct Point
    X As Int32
    Y As Int32
End Struct

Dim p = Point(10, 20)
WriteLn(p.X)
```

Current rules:

- `Struct Name` starts a struct declaration.
- `End Struct` and `EndStruct` both close the block.
- Fields use typed declarations with `As`.
- Default values are allowed on fields.
- Struct instances are immutable at runtime.
- Assignment and call boundaries copy struct values.
- Nested structs are supported when their layouts are safe.
- Recursive layout cycles are rejected.

The runtime currently computes fixed layouts for structs and uses those layouts for native marshaling.

## Records

`Record` declares an immutable script-only value type. Use it for text-bearing data and other shapes that should not be marshaled to native code:

```ass
Record WindowInfo
    Title As String
    ClassName As String
    IsVisible As Bool
End Record

Dim info = WindowInfo("My App", "MainWindow", True)
WriteLn(info.Title)
```

Current rules:

- `Record Name` starts a record declaration.
- `End Record` and `EndRecord` both close the block.
- Fields use typed declarations with `As`.
- Default values are allowed on fields.
- Record instances are immutable at runtime.
- Assignment and call boundaries copy record values.
- Nested records are supported.
- Records may contain `String` fields and other script-friendly types.
- Records are not ABI-safe and are not used for DLL marshaling.

For a shorter first-pass example that compares `Struct` and `Record` side by side, see [Struct and DLL Quickstart](struct_and_dll_quickstart.md).

## Layout Clauses

The current language supports optional ABI-oriented layout clauses:

```ass
Struct Point Packed(1)
    X As Int32
    Y As Int16
End Struct

Struct Vec4 Align(4)
    X As Float32
    Y As Float32
    Z As Float32
    W As Float32
End Struct
```

`Packed(n)` lowers field alignment to a pack ceiling. `Align(n)` requests a minimum final struct alignment and is accepted only when the runtime can truly honor it. See [Struct Layout Contract](struct_layout_contract.md) for the exact layout rules.

The narrow ABI matrix and rejection matrix in [Struct Layout Contract](struct_layout_contract.md) are the current source of truth for which struct layouts, struct returns, and unsupported ABI shapes are supported or rejected.

## External Declarations

External functions are declared with `Declare Func` or `Declare Sub`:

```ass
Declare Func GetDesktopWindow Lib "user32.dll" StdCall () As Ptr
Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default (text As String)
```

Current syntax notes:

- `Declare Func` requires a return type.
- `Declare Sub` is the void-returning form.
- `Lib "..."` names the DLL.
- `Alias "..."` names the exported native entry point.
- `Default`, `WinAPI`, `StdCall`, and `CDecl` are accepted calling conventions.
- `String` by value is marshaled as a wide string.
- `ByRef String(n)` uses an explicit fixed-capacity Unicode buffer.

Example with an explicit buffer:

```ass
Declare Func GetModuleFileNameW Lib "kernel32.dll" Default (hModule As Ptr, ByRef fileName As String(260), nSize As UInt32) As UInt32
```

For a tiny end-to-end smoke path using `Struct POINT` plus `GetCursorPos`, see [GetCursorPos smoke sample](../../samples/struct_and_dll_cursor_pos_demo.ass).

For the script-friendly wrapper form that returns a `Point` struct directly, see [GetCursorPos wrapper demo](../../samples/cursor_pos_wrapper_demo.ass).

For the script-friendly wrapper form that returns a `Rect` struct directly, see [GetWindowRect wrapper demo](../../samples/window_rect_wrapper_demo.ass).

For the script-friendly wrapper form that returns the client area of a window as `Rect`, see [GetClientRect wrapper demo](../../samples/client_rect_wrapper_demo.ass).

For the script-friendly wrapper form that returns the title text of a window as `String`, see [GetWindowText wrapper demo](../../samples/window_text_wrapper_demo.ass).

For the script-friendly wrapper form that returns a pointer-sized window field as `Ptr`, see [GetWindowLongPtr wrapper demo](../../samples/window_long_ptr_wrapper_demo.ass).

For the script-friendly wrapper forms that return a parent window handle and a window-enabled flag, see [parent/enabled wrapper demo](../../samples/window_parent_enabled_wrapper_demo.ass).

For the script-friendly wrapper form that returns the class name of a window as `String`, see [GetClassName wrapper demo](../../samples/class_name_wrapper_demo.ass).

For the script-friendly wrapper forms that return window state as `Bool`, see [window state wrapper demo](../../samples/window_state_wrapper_demo.ass). That demo now includes `IsZoomed(hWnd)`, `IsIconic(hWnd)`, and `IsWindowVisible(hWnd)`.

For the script-friendly wrapper form that returns a `WindowPlacement` struct, see [GetWindowPlacement wrapper demo](../../samples/window_placement_wrapper_demo.ass).

Current `ByRef String` behavior:

- the buffer size is explicit in source
- the runtime creates a writable Unicode buffer of that size
- the buffer is written back into the script variable after the call

User-declared ABI structs still reject `String` fields for native layout, but the built-in `GetMonitorInfoEx()` wrapper is a deliberate exception: it exposes `MONITORINFOEX.szDevice` as a normal script `String` field on `MonitorInfoEx` because the runtime fills the native monitor-name buffer internally.

## Monitor Info Wrapper Path

The monitor-info wrappers are the clearest example of the runtime-managed struct path.

For the runnable wrapper flow and the command sequence to try, see [Monitor Info Wrapper Demo](../../samples/README.md#monitor-info-wrapper-demo).

For the raw demo script, see [Monitor Info demo](../../samples/monitor_info_demo.ass).

Example wrapper usage:

```ass
Struct Rect
    Left As Int32
    Top As Int32
    Right As Int32
    Bottom As Int32
End Struct

Struct MonitorInfo
    cbSize As UInt32
    rcMonitor As Rect
    rcWork As Rect
    dwFlags As UInt32
End Struct

Struct MonitorInfoEx
    cbSize As UInt32
    rcMonitor As Rect
    rcWork As Rect
    dwFlags As UInt32
    szDevice As String
End Struct

Dim monitor = GetMonitorInfo(hMonitor)
Dim monitor_ex = GetMonitorInfoEx(hMonitor)
WriteLn(monitor.rcWork.Right)
WriteLn(monitor_ex.szDevice)
```

The two built-ins are Windows wrappers over `GetMonitorInfoW`:

- `GetMonitorInfo(hMonitor)` returns `MonitorInfo`
- `GetMonitorInfoEx(hMonitor)` returns `MonitorInfoEx` and includes the monitor device name in `szDevice`

For a runnable example, see [Monitor Info demo](../../samples/monitor_info_demo.ass).

For the window-rectangle wrapper, `GetWindowRect(hWnd)` returns a normal script `Rect` struct and hides the raw Win32 `RECT` payload behind the desktop host service. For a runnable example, see [GetWindowRect wrapper demo](../../samples/window_rect_wrapper_demo.ass).

For the client-rectangle wrapper, `GetClientRect(hWnd)` returns a normal script `Rect` struct and hides the raw Win32 `RECT` payload behind the desktop host service. For a runnable example, see [GetClientRect wrapper demo](../../samples/client_rect_wrapper_demo.ass).

For the window-text wrapper, `GetWindowText(hWnd)` returns a normal script `String` and hides the raw Win32 text buffer behind the desktop host service. For a runnable example, see [GetWindowText wrapper demo](../../samples/window_text_wrapper_demo.ass).

For the window-long-ptr wrapper, `GetWindowLongPtr(hWnd, index)` returns a normal script `Ptr` value and hides the raw Win32 `GetWindowLongPtrW` call behind the desktop host service. For a runnable example, see [GetWindowLongPtr wrapper demo](../../samples/window_long_ptr_wrapper_demo.ass).

For the parent/enabled wrappers, `GetParent(hWnd)` returns a normal script `Ptr` value and `IsWindowEnabled(hWnd)` returns a normal script `Bool` value, both hiding the raw Win32 state queries behind the desktop host service. For a runnable example, see [parent/enabled wrapper demo](../../samples/window_parent_enabled_wrapper_demo.ass).

For the class-name wrapper, `GetClassName(hWnd)` returns a normal script `String` and hides the raw Win32 class-name buffer behind the desktop host service. For a runnable example, see [GetClassName wrapper demo](../../samples/class_name_wrapper_demo.ass).

For the window-state wrappers, `IsZoomed(hWnd)`, `IsIconic(hWnd)`, and `IsWindowVisible(hWnd)` return normal script `Bool` values that hide the raw Win32 state queries behind the desktop host service. For a runnable example, see [window state wrapper demo](../../samples/window_state_wrapper_demo.ass).

For the window-placement wrapper, `GetWindowPlacement(hWnd)` returns a normal script `WindowPlacement` struct and exposes the nested `Point` and `Rect` data directly. For a runnable example, see [GetWindowPlacement wrapper demo](../../samples/window_placement_wrapper_demo.ass).

## Win32 and ABI Scope

The DLL interop path is currently Windows-oriented and tested against Win32-style APIs.

- The current runtime loads `user32.dll`, `kernel32.dll`, and similar Windows DLLs.
- `CDecl` uses `ctypes.CDLL`.
- `WinAPI`, `StdCall`, and `Default` use `ctypes.WinDLL` where available.
- Non-Windows platforms are not the target for the current DLL feature set.

## Ptr and Handle Notes

`Ptr` and `IntPtr` are the canonical native pointer-sized types today.

Use them for opaque native handles:

```ass
Declare Func GetDesktopWindow Lib "user32.dll" StdCall () As Ptr
```

If you want the smallest `Struct POINT` plus `GetCursorPos` check, use [GetCursorPos smoke sample](../../samples/struct_and_dll_cursor_pos_demo.ass).

Treat `Handle` as an ABI role, not a distinct runtime type. If a native API returns or accepts an opaque handle, model it with `Ptr` or `IntPtr` unless you deliberately choose a narrower integer type for the ABI.

## Current Limitations

- DLL interop is Windows-only in practice.
- `String` fields inside user-declared ABI structs are not layout-safe.
- Dynamic arrays, function pointers, and richer native ABI types are not yet supported.
- Struct return-by-value is currently limited to fixed-layout, ABI-safe structs that fit in a native pointer-sized return slot.
- Explicit packing/alignment is supported in the language and layout summaries, but `Align(n)` is rejected when the runtime cannot honor it exactly.

The portability guarantee and ABI matrix are documented in [Struct Layout Contract](struct_layout_contract.md) and pinned by the runtime and analyzer tests linked there.

## Related Docs

- [Struct Layout Contract](struct_layout_contract.md)
- [Docs Index](../index.md)
