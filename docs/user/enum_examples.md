# Enum Examples

This page collects runnable examples for `Enum` declarations. The examples show how enum members are published as both qualified names like `WindowState.Visible` and simple names like `Visible`.

## Window State Helper

This example models a small window-state helper. The enum stores the state codes, and the helper function turns those codes into readable text for logs or diagnostics.

```ass
Enum WindowState
    Hidden = 0
    Visible
    Maximized = Visible + 1
End Enum

Func DescribeWindowState(state)
    If state == WindowState.Hidden Then
        Return "hidden"
    ElseIf state == WindowState.Visible Then
        Return "visible"
    ElseIf state == WindowState.Maximized Then
        Return "maximized"
    End If

    Return "unknown"
End Func

Dim states = [WindowState.Hidden, WindowState.Visible, WindowState.Maximized]

WriteLn("state_0: " + DescribeWindowState(states[0]))
WriteLn("state_1: " + DescribeWindowState(states[1]))
WriteLn("state_2: " + DescribeWindowState(states[2]))
WriteLn("direct_name: " + DescribeWindowState(Visible))
```

Expected output:

```text
state_0: hidden
state_1: visible
state_2: maximized
direct_name: visible
```

## Priority Routing

This example shows how a second enum can be used for simple decision-making. The enum members behave like integer constants, so they can be stored, compared, and passed around just like other numeric values.

```ass
Enum Priority
    Low = 1
    Normal
    High = 10
End Enum

Func PriorityLabel(level)
    If level >= Priority.High Then
        Return "urgent"
    ElseIf level >= Priority.Normal Then
        Return "standard"
    End If

    Return "background"
End Func

Dim levels = [Priority.Low, Priority.Normal, Priority.High]

WriteLn("low: " + PriorityLabel(levels[0]))
WriteLn("normal: " + PriorityLabel(levels[1]))
WriteLn("high: " + PriorityLabel(levels[2]))
WriteLn("numeric: " + PriorityLabel(12))
```

Expected output:

```text
low: background
normal: standard
high: urgent
numeric: urgent
```

## Struct Field With Enum

This example shows an enum flowing through a typed `Struct` field. The `State As WindowState` declaration keeps the enum value attached to the snapshot object, and the helper function reads that field back to decide what text to print.

```ass
Enum WindowState
    Hidden = 0
    Visible
End Enum

Struct WindowSnapshot
    State As WindowState
End Struct

Func DescribeSnapshot(snapshot)
    If snapshot.State == WindowState.Visible Then
        Return "visible"
    End If

    Return "hidden"
End Func

Dim snapshot = WindowSnapshot(Visible)

WriteLn("snapshot_state: " + DescribeSnapshot(snapshot))
```

Expected output:

```text
snapshot_state: visible
```

## Record Field With Enum

This example uses the same pattern with a `Record`, which keeps the enum-backed value inside a script-only structured type. It is useful when you want a lightweight data shape without the ABI concerns of `Struct`.

```ass
Enum WindowState
    Hidden = 0
    Visible
End Enum

Record WindowSnapshot
    State As WindowState
End Record

Func DescribeSnapshot(snapshot)
    If snapshot.State == WindowState.Visible Then
        Return "visible"
    End If

    Return "hidden"
End Func

Dim snapshot = WindowSnapshot(Visible)

WriteLn("record_state: " + DescribeSnapshot(snapshot))
```

Expected output:

```text
record_state: visible
```

## Related Docs

- [Language Reference](language_reference.md)
- [Enum Examples Demo](../../samples/README.md#enum-examples-demo)
- [Docs Index](../index.md)
