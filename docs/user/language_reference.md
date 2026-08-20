# Language Reference

This page is a compact reference for the `ActionShellScript` scripting language as parsed by the current frontend and executed by the runtime.

The language is intentionally small and regular:

- statements are line-oriented
- keywords are case-insensitive
- function names are case-insensitive
- type names are normalized to the canonical runtime vocabulary
- `End If`, `End Func`, `End Struct`, and `End Record` are accepted as spaced terminators, in addition to the compact forms

## Syntax Overview

Most scripts are a sequence of statements:

```ass
Dim name = "Ada"
Dim count = 2

If count > 1 Then
    WriteLn($"Hello {name}, count={count}")
End If
```

The parser supports:

- variable declarations with `Dim`, `Local`, `Global`, and `Redim`
- constants with `Const`
- functions with `Func` / `Function`
- external declarations with `Declare Func` and `Declare Sub`
- `Struct` declarations for runtime-backed value types
- `Record` declarations for script-only structured values
- assignments, function calls, indexing, and member access
- `If`, `While`, `Do ... Until`, and `For` control flow
- labels and `Goto`
- `Return`, `ExitScript`, `Exit`, and `Continue`

The parser supports `Select Case ... Case ... End Select` as structured multi-branch control flow, including `Case Is < ...`, `Case Is Not ...`, `Case Is Not Like ...`, `Case Is >= ...`, `Case Like ...`, `Case Not Like ...`, and `Case Else`.

Example:

```ass
Select Case status
Case Is 0
    WriteLn("idle")
Case Is Not Like "ERR*"
    WriteLn("ok")
Case Else
    WriteLn("unknown")
End Select
```

## Comments

The lexer accepts these comment forms:

- `//` line comments
- `#` line comments
- `/* ... */` block comments
- `#comments-start ... #comments-end` block comments

Semicolons are statement separators and can be used in place of newlines when you want multiple statements on one line.

Example:

```ass
// this is also a comment
# so is this
/* this is a
multi-line comment */
Hotkey("ctrl", "c"); Hotkey("ctrl", "v")

#comments-start
This whole block is ignored.
#comments-end
```

## Identifiers And Literals

Identifiers are case-insensitive for user-defined names, while keywords are not.

The lexer recognizes:

- identifiers such as `name`, `Count`, or `$value`
- host identifiers prefixed with `@`, such as `@windowTitle`
- built-in runtime values prefixed with `@`, such as `@Error`, `@CR`, `@LF`, `@CRLF`, `@TAB`, `@ScriptName`, `@ScriptDirectory`, and `@WorkingDir`
- both user-defined names and `@` runtime values are matched case-insensitively
- numeric literals, including integers, decimals, scientific notation, and hexadecimal values like `0xFF`
- string literals using double quotes
- raw string literals using single quotes
- interpolated strings using `$"..."`
- array literals using `[ ... ]`
- the boolean and null literals `True`, `False`, and `Null`

Examples:

```ass
Dim hexValue = 0xFF
Dim temperature = 21.5
Dim title = "ActionShellScript"
Dim raw = 'no escapes here'
Dim message = $"Hello {title}"
Dim items = [1, 2, 3]
Dim enabled = True
Dim missing = Null
```

Interpolated strings support escaped braces by doubling them:

```ass
Dim total = 12
WriteLn($"{{total}} = {total}")
```

## Built-in Runtime Values

The runtime injects a small set of read-only `@` values that are available in normal expressions. Scripts can read them, but only the host/runtime can set them:

- `@Error` stores the last runtime error code.
- `@CR`, `@LF`, and `@CRLF` provide carriage-return and line-feed separators.
- `@TAB` provides a tab character.
- `@ScriptName` resolves to the current script file name.
- `@ScriptDirectory` resolves to the current script directory.
- `@WorkingDir` resolves to the current working directory.
- `@PlaybackRepeatCount` exposes the Playback repeat count preference.
- `@PlaybackEventPause` exposes whether "Pause before each playback event" is enabled.
- `@PlaybackEventDelay` exposes the "Delay before each event" preference in milliseconds.
- `@PlaybackMouseSettle` exposes the "Mouse settle before clicks" preference in milliseconds.

Example:

```ass
WriteLn(@ScriptName)
WriteLn(@ScriptDirectory)
WriteLn(@WorkingDir)
WriteLn("A" & @TAB & "B")
WriteLn("Line 1" & @CRLF & "Line 2")
```

The path-valued entries depend on where the script lives and runs, so the exact output will vary by machine.

## Statements

Statements normally end at a newline, but `;` is also accepted as an end-of-line separator.

The parser also accepts structured blocks with the following terminators:

- `If ... Then` / `End If`
- `While ...` / `Wend`
- `Do` / `Until`
- `For ... To ... Step ...` / `Next`
- `Func` / `End Func`
- `Struct` / `End Struct`
- `Record` / `End Record`

Supported statement forms include:

- assignment: `name = expression`
- expression statement: `FuncName(arg1, arg2)`
- return: `Return expression`
- script exit: `ExitScript expression`
- loop control: `Exit`, `Exit For`, `Exit While`, `Exit Loop`, `Continue`, `Continue For`, `Continue While`, `Continue Loop`
- label: `StartLoop:`
- goto: `Goto StartLoop`

Example:

```ass
Dim index = 0

While index < 3
    WriteLn($"index={index}")
    index = index + 1
Wend
```

`Select Case` / `Case` / `End Select` are supported for structured multi-branch control flow, and `Case Is`, `Case Is Not`, `Case Is Not Like`, `Case Like`, and `Case Not Like` forms are available for comparisons and wildcard matching.

## Declarations

### Variables And Constants

Variable declarations use a storage keyword followed by one or more declarators:

```ass
Dim value = 10
Local temp As Int32 = 42
Global name As String
Redim buffer As String
Const answer = 42
```

Declarators may include:

- a type annotation with `As`
- an initializer with `=`
- multiple declarators separated by commas

Type names are normalized to the canonical runtime set:

- `Int8`, `UInt8`, `Int16`, `UInt16`, `Int32`, `UInt32`, `Int64`, `UInt64`
- `Float32`, `Float64`
- `Bool`, `Char`, `String`
- `Ptr`, `IntPtr`

### Functions

Function declarations use `Func` or `Function`:

```ass
Func Add(ByVal left As Int32, ByVal right As Int32) As Int32
    Return left + right
End Func
```

Parameter rules:

- `ByVal` and `ByRef` are accepted
- default values are allowed
- parameter types are optional in the current parser, but the runtime and document services work best when you include them

### External Functions

External declarations describe DLL or host interop:

```ass
Declare Func MessageBoxW Lib "user32.dll" Alias "MessageBoxW" Default (hWnd As Ptr, text As String) As Int32
Declare Sub OutputDebugStringW Lib "kernel32.dll" Alias "OutputDebugStringW" Default (text As String)
```

Supported calling conventions:

- `Default`
- `WinApi`
- `StdCall`
- `CDecl`

Parameters can also use explicit string buffer sizes:

```ass
Declare Func GetModuleFileNameW Lib "kernel32.dll" Default (hModule As Ptr, ByRef fileName As String(260), nSize As UInt32) As UInt32
```

### Structs And Records

`Struct` declarations define runtime value types:

```ass
Struct Point Packed(1)
    X As Int32
    Y As Int32
End Struct
```

`Record` declarations define script-only structured values:

```ass
Record WindowInfo
    Title As String
    ClassName As String
    IsVisible As Bool
End Record
```

For runnable examples that show `Enum` values inside `Struct` and `Record` fields, see [Enum Examples](enum_examples.md).

`Enum` declarations define integer constants that are published both as individual names and through the enum namespace:

```ass
Enum WindowState
    Hidden = 0
    Visible
    Maximized = Visible + 1
End Enum

Dim current = WindowState.Visible
WriteLn(Visible)
```

For a couple of more complete examples, see [Enum Examples](enum_examples.md).

Field declarations require a type annotation and may include an initializer.

Supported layout clauses for `Struct`:

- `Packed(n)`
- `Align(n)`

Only one layout clause may appear on a given `Struct` header.

## Expressions

The expression grammar supports:

- function calls: `Name(arg1, arg2)`
- indexing: `items[0]`
- member access: `point.X`
- parentheses: `(a + b)`
- arrays: `[1, 2, 3]`
- conditional expressions: `condition ? when_true : when_false`
- unary operators: `+`, `-`, `Not`, `++`, `--`
- binary operators:
  - logical: `And`, `Or`
  - comparison: `==`, `!=`, `<>`, `<`, `<=`, `>`, `>=`
  - concatenation: `&`
  - arithmetic: `+`, `-`, `*`, `/`, `%`

Precedence from low to high:

1. conditional `? :`
2. `Or`
3. `And`
4. comparison operators
5. `&`
6. `+` and `-`
7. `*`, `/`, and `%`

Example:

```ass
Dim result = (2 + 3) * 4
Dim label = "Count: " & result
Dim ok = Not False And result > 5
Dim verdict = (result >= 20) ? "Pass" : "Fail"
Dim tier = score >= 90 ? "A" : score >= 80 ? "B" : "C"
Dim message = ready And count > 0 ? "Go" : "Wait"
```

The `tier` example nests ternaries in the false branch, so it reads as:

```ass
Dim tier = score >= 90 ? "A" : (score >= 80 ? "B" : "C")
```

The `message` example shows that the condition is evaluated before the ternary branch selection:

```ass
Dim message = (ready And count > 0) ? "Go" : "Wait"
```

The increment examples show both prefix and postfix forms:

```ass
Dim counter = 0
Dim prefix = ++counter   ; prefix returns 1 and leaves counter as 1
Dim postfix = counter++  ; postfix returns 1 and leaves counter as 2
```

## Builtins And Runtime Hooks

Builtin function names are case-insensitive. The runtime recognizes the builtin registry in `core/runtime/builtins/builtin_registry.py`, which includes helpers for:

- math, including `Abs()`, `Int()`, `Round()`, `Ceiling()`, `Exp()`, `Floor()`, and `Mod()`
- arrays, including `ArrayLength()`, `ArrayInsert()`, `ArrayPush()`, `ArrayPop()`, `ArrayRemove()`, `ArrayContains()`, `ArrayContainsAll()`, `ArrayCount()`, `ArrayInitialize()`, `ArrayClear()`, `ArrayClone()`, `ArrayRemoveAll()`, `ArrayIndexOf()`, `ArrayLastIndexOf()`, `ArrayReverse()`, `ArraySort()`, `ArrayUnique()`, `ArrayToString()`, `ArrayJoin()`, and `ArraySlice()`
- strings, including `StringCompare()`, `StringIsAlpha()`, `StringIsAlphaNumeric()`, `StringIsASCII()`, `StringIsDigit()`, `StringIsFloat()`, `StringIsInt()`, `StringIsLower()`, `StringIsSpace()`, `StringIsUpper()`, `StringInStr()`, `StringReplace()`, `StringStartsWith()`, `StringEndsWith()`, `StringContains()`, `StringSplit()`, `StringJoin()`, `StringLength()`, `StringLeft()`, `StringReverse()`, `StringRight()`, `StringMid()`, `StringTrimLeft()`, and `StringTrimRight()`
- regex, including `RegexEscape()`, `RegexIsMatch()`, `RegexInStr()`, `RegexMatch()`, and `RegexReplace()`
- dates and times, including `Time()`, `UTCTime()`, `LocalTime()`, `NowDate()`, `NowTime()`, `NowDateTime()`, `DateToString()`, `DateToLocalString()`, `DateToUTCString()`, `UTCDateTime()`, `ParseDateTime()`, `ParseDateTimeInOffset()`, `FormatDateTime()`, `FormatDateTimeInOffset()`, `DateAdd()`, `DateDiff()`, `ConvertTimeZone()`, `UTCOffset()`, `TimeZoneOffset()`, `StartOfDay()`, `EndOfDay()`, `StartOfMonth()`, `EndOfMonth()`, `StartOfWeek()`, `DayOfWeek()`, `DayOfYear()`, `DatePart()`, `DateSerial()`, `TimeSerial()`, `DaysInMonth()`, `IsLeapYear()`, `IsDate()`, and `IsTime()`
- files and paths, including `AppendBytes()`, `AppendFile()`, `CopyDir()`, `CopyFile()`, `CreateDir()`, `DeleteFile()`, `DirectoryDelete()`, `DirectoryList()`, `DirectoryName()`, `DirExists()`, `EnumerateFiles()`, `FileChecksum()`, `FileCompare()`, `FileExists()`, `FileHash()`, `FileInfo()`, `FileList()`, `FileName()`, `FileSize()`, `FileTime()`, `IsPathValid()`, `MoveDir()`, `MoveFile()`, `PathCombine()`, `PathExists()`, `PathNormalize()`, `ReadBytes()`, `ReadFile()`, `RemoveDir()`, `WalkDir()`, `WriteBytes()`, and `WriteFile()`
- binary data, including `Base64()`, `Binary()`, `BinaryLength()`, `BinaryMid()`, `BinaryToString()`, `FromBase64()`, `FromHex()`, and `Hex()`
- mouse and keyboard actions, including `KeyDown()`, `KeyPress()`, `KeyToggle()`, `KeyUp()`, `MouseClick()`, `MouseClickDrag()`, `MouseDown()`, `MouseDrag()`, `MouseMove()`, `MouseUp()`, `MouseWheel()`, `SendKeys()`, and `SendText()`
- pixel and window inspection, including `GetClientRect()`, `GetClassName()`, `GetCursorPos()`, `GetMonitorInfo()`, `GetMonitorInfoEx()`, `GetParent()`, `GetWindowLongPtr()`, `GetWindowPlacement()`, `GetWindowRect()`, `GetWindowText()`, `IsIconic()`, `IsWindowEnabled()`, `IsWindowVisible()`, `IsZoomed()`, `PixelGetColor()`, and `PixelSearch()`
- diagnostics and output, including `DiagWrite()`, `DiagWriteLn()`, `MsgBox()`, `Write()`, and `WriteLn()`

### Array Helpers

The array helper surface covers the common list operations that sit on top of the language's array literals and 0-based indexing:

- `ArrayLength(values)` returns the number of items in `values`
- `ArrayInsert(values, index, value[, ...])` inserts one or more values into `values` in place at the zero-based `index` and returns the new length
- `ArrayPush(values, value[, ...])` appends one or more values to `values` in place and returns the new length
- `ArrayPop(values)` removes and returns the last item from `values`; when the array is empty, it returns `Null` and sets `@Error = 1`
- `ArrayRemove(values, index[, count])` removes one or more values from `values` in place and returns the removed value or values
- `ArrayContains(values, value)` returns `1` when `value` is present in `values` and `0` otherwise
- `ArrayContainsAll(values, value[, ...])` returns `1` when every requested value is present in `values` and `0` otherwise
- `ArrayCount(values, value)` returns how many times `value` appears in `values`
- `ArrayInitialize(values, value)` sets every element in `values` to `value` and returns the array length after initialization
- `ArrayClear(values)` sets every element in `values` to an empty string and returns the array length after clearing
- `ArrayClone(values)` returns a deep copy of `values` that can be mutated independently of the original
- `ArrayRemoveAll(values, value)` removes every matching value from `values` in place and returns how many items were removed
- `ArrayIndexOf(values, value)` returns the zero-based index of the first matching element, or `-1` if there is no match
- `ArrayLastIndexOf(values, value)` returns the zero-based index of the last matching element, or `-1` if there is no match
- `ArrayReverse(values)` returns a reversed copy of `values` without mutating the source array
- `ArraySort(values[, descending[, casesense]])` returns a sorted copy of `values` without mutating the source array
- `ArrayUnique(values[, casesense])` returns a copy of `values` with duplicates removed while preserving first-seen order; `casesense = 0` compares strings case-insensitively and `casesense = 1` compares them case-sensitively
- `ArrayToString(values[, separator])` flattens an array into a string, using commas by default or a custom separator when provided
- `ArrayJoin(values[, separator])` is an alias for `ArrayToString(values[, separator])`
- `ArraySlice(values, start[, count])` returns a new array containing a zero-based slice of `values`
- `start` is 0-based and `count` is optional
- when `count` is omitted, `ArraySlice()` returns the remainder of the array from `start`
- when `count` is negative, `ArraySlice()` returns an empty array
- when `start` is out of range, `ArraySlice()` returns an empty array
- `ArrayInsert()`, `ArrayPush()`, `ArrayPop()`, `ArrayRemove()`, `ArrayInitialize()`, and `ArrayClear()` mutate the array argument you pass in, so use a variable or other writable list reference
- `ArrayContains()`, `ArrayContainsAll()`, `ArrayCount()`, `ArrayRemoveAll()`, `ArrayIndexOf()`, and `ArrayLastIndexOf()` compare values using the runtime's normal equality rules
- `ArrayReverse()` returns a new array and leaves the source array unchanged
- `ArrayClone()` returns a deep copy of the array and leaves the source array unchanged
- `ArraySort()` sorts numbers numerically, strings with optional case sensitivity, and falls back to a deterministic string-based ordering for other values
- `ArrayUnique()` preserves the first occurrence of each value and, when `casesense` is omitted or `0`, treats strings case-insensitively
- `ArrayToString()` uses `","` by default and stringifies each element with the runtime's normal string conversion rules
- `ArrayJoin()` behaves the same as `ArrayToString()`
- `ArraySlice()` returns a new array and leaves the source array unchanged

```ass
Dim values = [1, 2, 3]
Dim search_values = [1, 2, 3, 2, 1]
Dim after_insert = ArrayInsert(values, 1, 9)
Dim after_first_push = ArrayPush(values, 4)
Dim after_second_push = ArrayPush(values, 5, 6)
Dim popped = ArrayPop(values)
Dim removed = ArrayRemove(values, 1)
Dim has_three = ArrayContains(search_values, 3)
Dim has_all = ArrayContainsAll(search_values, 1, 2, 3)
Dim count_two = ArrayCount(search_values, 2)
Dim initialized = ArrayInitialize(search_values, 0)
Dim cleared = ArrayClear(search_values)
Dim cloned = ArrayClone(search_values)
Dim removed_twos = ArrayRemoveAll(search_values, 2)
Dim first_two = ArrayIndexOf(search_values, 2)
Dim last_two = ArrayLastIndexOf(search_values, 2)
Dim reversed_numbers = ArrayReverse([1, 2, 3])
Dim sorted_numbers = ArraySort([3, 1, 2])
Dim sorted_text = ArraySort(["Bravo", "alpha", "charlie"])
Dim unique_text = ArrayUnique(["Bravo", "alpha", "BRAVO", "alpha"])
Dim csv = ArrayToString(values)
Dim semicolon = ArrayToString(values, ";")
Dim joined = ArrayJoin(values, "|")
Dim slice = ArraySlice(values, 1, 2)

WriteLn("length_initial: " + ArrayLength([1, 2, 3]))
WriteLn("after_insert: " + after_insert)
WriteLn("after_first_push: " + after_first_push)
WriteLn("after_second_push: " + after_second_push)
WriteLn("popped: " + popped)
WriteLn("removed: " + removed)
WriteLn("has_three: " + has_three)
WriteLn("has_all: " + has_all)
WriteLn("count_two: " + count_two)
WriteLn("initialized: " + initialized)
WriteLn("cleared: " + cleared)
WriteLn("cloned: " + ArrayLength(cloned))
WriteLn("removed_twos: " + removed_twos)
WriteLn("first_two: " + first_two)
WriteLn("last_two: " + last_two)
WriteLn("reversed_numbers: " + reversed_numbers[0] + "," + reversed_numbers[1] + "," + reversed_numbers[2])
WriteLn("sorted_numbers: " + sorted_numbers[0] + "," + sorted_numbers[1] + "," + sorted_numbers[2])
WriteLn("sorted_text: " + sorted_text[0] + "," + sorted_text[1] + "," + sorted_text[2])
WriteLn("unique_text: " + unique_text[0] + "," + unique_text[1])
WriteLn("csv: " + csv)
WriteLn("semicolon: " + semicolon)
WriteLn("joined: " + joined)
WriteLn("length_after_pop: " + ArrayLength(values))
WriteLn("slice_0: " + slice[0])
WriteLn("slice_1: " + slice[1])
```

Expected output:

```text
length_initial: 3
after_insert: 4
after_first_push: 4
after_second_push: 6
popped: 6
removed: 9
has_three: 1
has_all: 1
count_two: 2
initialized: 5
cleared: 5
cloned: 5
removed_twos: 2
first_two: 1
last_two: 3
reversed_numbers: 3,2,1
sorted_numbers: 1,2,3
sorted_text: alpha,Bravo,charlie
unique_text: Bravo,alpha
csv: 1,2,3,4,5
semicolon: 1;2;3;4;5
joined: 1|2|3|4|5
length_after_pop: 5
slice_0: 2
slice_1: 3
```

For a runnable array-helper example, see [Array Helper Examples](array_helpers_examples.md).

### File And Path Enumeration

The file and path helper surface includes `DirectoryList()` and `FileList()` for enumerating the immediate children of a directory.

- `DirectoryList(path[, pattern])` returns an array of full path strings for the child directories inside `path`
- `FileList(path[, pattern])` returns an array of full path strings for the child files inside `path`
- `pattern` is optional and uses shell-style wildcard matching against each child name, so `*`, `?`, and character classes work the same way they do in the runtime's glob-style matcher
- both helpers return their results sorted by child name
- both helpers raise a runtime error when `path` does not exist or when `path` exists but is not a directory

```ass
Dim sample_dir = @ScriptDirectory
Dim repo_root = PathCombine(sample_dir, "..")
Dim files = FileList(sample_dir, "read_file_demo.*")
Dim directories = DirectoryList(repo_root, "samples")

WriteLn("file_0: " + FileName(files[0]))
WriteLn("file_1: " + FileName(files[1]))
WriteLn("directory_0: " + FileName(directories[0]))
```

Expected output:

```text
file_0: read_file_demo.ass
file_1: read_file_demo.txt
directory_0: samples
```

For a runnable path-enumeration example, see [Path Helper Examples](path_helpers_examples.md).

### Directory Removal

`RemoveDir(path[, recursive])` removes a directory path. `DirectoryDelete(path[, recursive])` is an alias with the same behavior.

- when `recursive` is omitted or `0`, the helper removes only empty directories
- when `recursive` is nonzero, the helper removes the directory and all of its contents
- both helpers raise a runtime error when the target directory does not exist
- both helpers raise a runtime error when the target path exists but is not a directory
- non-recursive removal of a non-empty directory raises a runtime error instead of silently deleting contents

```ass
Dim scratch = PathCombine(@WorkingDir, "__remove_dir_demo__")
CreateDir(PathCombine(scratch, "nested"))
WriteLn(DirExists(scratch))
RemoveDir(scratch, 1)
WriteLn(DirExists(scratch))
```

Expected output:

```text
1
0
```

For a runnable directory-removal example, see [Path Helper Examples](path_helpers_examples.md).

### File And Directory Copy

`CopyFile(source, destination[, overwrite])` copies a single file to a target file path.

- `source` must exist and be a file
- `destination` is treated as the full target file path
- when `overwrite` is omitted or `0`, the helper fails if the target path already exists
- when `overwrite` is nonzero, the helper replaces the target file if it already exists

`CopyDir(source, destination[, overwrite])` copies a directory tree to a new target directory path.

- `source` must exist and be a directory
- `destination` is treated as the full target directory path
- when `overwrite` is omitted or `0`, the helper fails if the target path already exists
- when `overwrite` is nonzero, the helper replaces the target directory tree if it already exists

```ass
Dim scratch = PathCombine(@WorkingDir, "__copy_demo__")
Dim source_dir = PathCombine(scratch, "source")
Dim copied_dir = PathCombine(scratch, "copied")
Dim source_file = PathCombine(source_dir, "message.txt")
Dim copied_file = PathCombine(scratch, "message_copy.txt")

CreateDir(source_dir)
WriteFile(source_file, "hello")
CopyFile(source_file, copied_file)
CopyDir(source_dir, copied_dir)
WriteLn("file_exists: " + FileExists(copied_file))
WriteLn("dir_exists: " + DirExists(copied_dir))
WriteLn("copied_text: " + ReadFile(copied_file))
RemoveDir(scratch, 1)
```

Expected output:

```text
file_exists: 1
dir_exists: 1
copied_text: hello
```

For a runnable copy example, see [Path Helper Examples](path_helpers_examples.md).

### File And Directory Move

`MoveFile(source, destination[, overwrite])` moves a single file to a target file path. `MoveDir(source, destination[, overwrite])` moves a directory tree to a target directory path.

- `source` must exist and have the expected file or directory type
- `destination` is treated as the full target path
- when `overwrite` is omitted or `0`, the helper fails if the target already exists
- when `overwrite` is nonzero, the helper replaces the existing target before moving the source

```ass
Dim scratch = PathCombine(@WorkingDir, "__move_demo__")
Dim source_dir = PathCombine(scratch, "source")
Dim moved_dir = PathCombine(scratch, "moved")
Dim source_file = PathCombine(source_dir, "message.txt")
Dim moved_file = PathCombine(scratch, "message_moved.txt")

CreateDir(source_dir)
WriteFile(source_file, "hello")
MoveFile(source_file, moved_file)
MoveDir(source_dir, moved_dir)
WriteLn("file_exists_after_move: " + FileExists(moved_file))
WriteLn("dir_exists_after_move: " + DirExists(moved_dir))
WriteLn("moved_text: " + ReadFile(moved_file))
RemoveDir(scratch, 1)
```

Expected output:

```text
file_exists_after_move: 1
dir_exists_after_move: 1
moved_text: hello
```

For a runnable move example, see [Path Helper Examples](path_helpers_examples.md).

### File And Directory Metadata

`FileSize(path)` returns the size in bytes of a file, or the recursive size of all files beneath a directory.

`FileTime(path[, kind])` returns a Unix timestamp as a number. `kind` defaults to `modified`, and can also be `created` or `accessed`.

`FileInfo(path)` returns a `Record<FileInfo>` with these fields:

- `Path`
- `Name`
- `ParentPath`
- `Extension`
- `IsDirectory`
- `Size`
- `CreatedTime`
- `ModifiedTime`
- `AccessedTime`

```ass
Dim scratch = PathCombine(@WorkingDir, "__metadata_demo__")
Dim data_file = PathCombine(scratch, "payload.txt")

CreateDir(scratch)
WriteFile(data_file, "hello world")

Dim info = FileInfo(data_file)
WriteLn("size: " + FileSize(data_file))
WriteLn("dir_size: " + FileSize(scratch))
WriteLn("file_name: " + info.Name)
WriteLn("is_dir: " + info.IsDirectory)
WriteLn("time_is_float: " + StringIsFloat(FileTime(data_file)))
RemoveDir(scratch, 1)
```

Expected output:

```text
size: 11
dir_size: 11
file_name: payload.txt
is_dir: 0
time_is_float: 1
```

For a runnable metadata example, see [Path Helper Examples](path_helpers_examples.md).

### File Hash And Checksum

`FileHash(path[, algorithm])` returns a lowercase hex digest for the file contents.

- `algorithm` defaults to `sha256`
- supported algorithms: `md5`, `sha1`, `sha256`, and `sha512`

`FileChecksum(path[, algorithm])` returns a lowercase hex checksum for the file contents.

- `algorithm` defaults to `crc32`
- supported algorithms: `crc32` and `adler32`

```ass
Dim scratch = PathCombine(@WorkingDir, "__metadata_demo__")
Dim data_file = PathCombine(scratch, "payload.txt")

CreateDir(scratch)
WriteFile(data_file, "hello world")

WriteLn("sha256: " + FileHash(data_file))
WriteLn("md5: " + FileHash(data_file, "md5"))
WriteLn("crc32: " + FileChecksum(data_file))
WriteLn("adler32: " + FileChecksum(data_file, "adler32"))
RemoveDir(scratch, 1)
```

Expected output:

```text
sha256: b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
md5: 5eb63bbbe01eeed093cb22bb8f5acdc3
crc32: 0d4a1185
adler32: 1a0b045d
```

For a runnable hash/checksum example, see [Path Helper Examples](path_helpers_examples.md).

### File Comparison

`FileCompare(left, right)` compares the binary contents of two files and returns:

- `0` when the files are identical
- `-1` when `left` sorts before `right`
- `1` when `left` sorts after `right`

This is a byte-wise comparison, so it is useful for exact file verification and deterministic ordering.

```ass
Dim scratch = PathCombine(@WorkingDir, "__compare_demo__")
Dim same_a = PathCombine(scratch, "same_a.txt")
Dim same_b = PathCombine(scratch, "same_b.txt")
Dim less = PathCombine(scratch, "less.txt")
Dim greater = PathCombine(scratch, "greater.txt")

CreateDir(scratch)
WriteFile(same_a, "same")
WriteFile(same_b, "same")
WriteFile(less, "abc")
WriteFile(greater, "abd")

WriteLn("same: " + FileCompare(same_a, same_b))
WriteLn("less: " + FileCompare(less, greater))
WriteLn("greater: " + FileCompare(greater, less))
RemoveDir(scratch, 1)
```

Expected output:

```text
same: 0
less: -1
greater: 1
```

For a runnable file comparison example, see [Path Helper Examples](path_helpers_examples.md).

### Directory Traversal

`WalkDir(path[, pattern])` returns the recursive child directories beneath `path`, sorted by relative path.

`EnumerateFiles(path[, pattern])` returns the recursive child files beneath `path`, sorted by relative path.

- `pattern` is optional and uses shell-style wildcard matching against each child name
- both helpers return full path strings
- both helpers raise a runtime error if the root path does not exist or is not a directory

```ass
Dim scratch = PathCombine(@WorkingDir, "__traverse_demo__")
Dim root = PathCombine(scratch, "root")
Dim nested = PathCombine(root, "nested")
Dim deep = PathCombine(nested, "deep")
Dim root_file = PathCombine(root, "alpha.txt")
Dim nested_file = PathCombine(nested, "beta.txt")
Dim deep_file = PathCombine(deep, "omega.log")

CreateDir(deep)
WriteFile(root_file, "root")
WriteFile(nested_file, "nested")
WriteFile(deep_file, "deep")

Dim dirs = WalkDir(root)
Dim files = EnumerateFiles(root, "*.txt")

WriteLn("dir_0: " + FileName(dirs[0]))
WriteLn("dir_1: " + FileName(dirs[1]))
WriteLn("files_0: " + FileName(files[0]))
WriteLn("files_1: " + FileName(files[1]))
RemoveDir(scratch, 1)
```

Expected output:

```text
dir_0: nested
dir_1: deep
files_0: alpha.txt
files_1: beta.txt
```

For a runnable traversal example, see [Path Helper Examples](path_helpers_examples.md).

### String Helpers

The basic string helper family covers `StringCompare()`, common case conversion, search, replacement, slicing, trimming, and reversal tasks:

- `StringCompare("left", "right"[, casesense])` returns `0` when the strings are equal, `1` when `left` sorts after `right`, and `-1` when `left` sorts before `right`; `casesense = 0` performs a case-insensitive comparison, while `casesense = 1` performs a case-sensitive comparison
- `StringLength("text")` returns the number of characters in `text`
- `StringIsAlpha("text")` returns `1` when `text` contains only alphabetic characters and `0` otherwise
- any whitespace in `StringIsAlpha()` input causes it to return `0`
- `StringIsAlphaNumeric("text")` returns `1` when `text` contains only alphabetic characters and digits and `0` otherwise
- any whitespace in `StringIsAlphaNumeric()` input causes it to return `0`
- `StringIsASCII("text")` returns `1` when `text` contains only ASCII characters in the `0x00-0x7f` range and `0` otherwise
- `StringIsDigit("text")` returns `1` when `text` contains only digits and `0` otherwise
- `StringIsFloat("text")` returns `1` when `text` is a decimal string with exactly one period and an optional leading `+` or `-`, and `0` otherwise
- `StringIsFloat()` converts non-string values to strings before checking them
- `StringIsInt("text")` returns `1` when `text` contains only an optional leading sign and digits, or when the input is already an integer expression
- `StringIsLower("text")` returns `1` when `text` contains only lowercase characters and `0` otherwise
- digits, punctuation, and whitespace make `StringIsLower()` return `0`
- `StringIsSpace("text")` returns `1` when `text` contains only whitespace characters, including `Chr(0)`, and `0` otherwise
- `StringIsUpper("text")` returns `1` when `text` contains only uppercase characters and `0` otherwise
- digits, punctuation, and whitespace make `StringIsUpper()` return `0`
- `StringLeft("text", count)` returns the leftmost `count` characters
- `StringReplace("text", "search", "replace" [, occurrence [, casesense]])` replaces matching substrings and stores the replacement count in `@Extended`
- `StringReplace("text", start, "replace")` replaces characters starting at the 1-based `start` position with `replace`
- `StringStartsWith("text", "prefix" [, casesense])` returns `1` when the text begins with the prefix and `0` otherwise
- `StringEndsWith("text", "suffix" [, casesense])` returns `1` when the text ends with the suffix and `0` otherwise
- `StringContains("text", "needle" [, casesense])` returns `1` when the text contains the needle and `0` otherwise
- `StringSplit("text", "delimiter" [, limit [, casesense]])` returns an array of substrings split on the delimiter
- `StringJoin(values [, delimiter])` joins array elements into a single string
- `StringReverse("text")` returns `text` with the characters reversed
- `StringRight("text", count)` returns the rightmost `count` characters
- `StringMid("text", start [, count])` returns a substring starting at the 1-based `start` position
- `StringTrimLeft("text", count)` returns `text` with `count` characters removed from the left
- `StringTrimRight("text", count)` returns `text` with `count` characters removed from the right

Edge cases follow the runtime behavior:

- if `count` exceeds the string length in `StringLeft()` or `StringRight()`, the full string is returned
- if `count` is negative in `StringLeft()` or `StringRight()`, an empty string is returned
- if `count` is out of bounds in `StringTrimLeft()` or `StringTrimRight()`, an empty string is returned
- if `start` is out of bounds in `StringMid()`, an empty string is returned
- if `count` is omitted in `StringMid()`, the remainder of the string is returned
- if `StringReplace()` uses start-position mode and the replacement would extend past the end of the string, the runtime returns an empty string and sets `@Error` to `1`
- `StringStartsWith()`, `StringEndsWith()`, `StringContains()`, and `StringSplit()` default to case-insensitive matching when `casesense` is omitted
- `StringJoin()` stringifies each array element with the runtime's normal string conversion rules and returns `""` for an empty array

Example:

```ass
Dim text = "Hello World"
WriteLn(StringIsAlpha("Café"))
WriteLn(StringIsAlphaNumeric("Café42"))
WriteLn(StringIsASCII("ASCII text"))
WriteLn(StringIsDigit("012345"))
WriteLn(StringIsFloat(1.25))
WriteLn(StringIsInt(42))
WriteLn(StringIsLower("lowercase"))
WriteLn(StringIsSpace(" \t\r\n"))
WriteLn(StringIsUpper("UPPERCASE"))
WriteLn(StringLength(text))
WriteLn(StringLeft(text, 5))
WriteLn(StringReplace(text, "l", "L"))
WriteLn(StringReplace(text, 4, "XYZ"))
WriteLn(StringStartsWith(text, "he"))
WriteLn(StringEndsWith(text, "LD"))
WriteLn(StringContains(text, "wor"))
Dim parts = StringSplit("a,b,c", ",")
WriteLn(parts[0])
WriteLn(StringJoin(["a", "b", "c"], ", "))
WriteLn(StringReverse(text))
WriteLn(StringRight(text, 5))
WriteLn(StringMid(text, 7, 5))
WriteLn(StringTrimLeft(text, 6))
WriteLn(StringTrimRight(text, 6))
```

### Regex Helpers

The regex helpers reuse the same builtin-call syntax as the string helpers, but they operate on Python-style regular expressions and support capture groups and replacement backreferences:

- `RegexEscape("text")` returns an escaped pattern literal that can be embedded safely into a regular expression
- `RegexIsMatch("text", "pattern"[, options])` returns `1` when the pattern matches anywhere in the text and `0` otherwise
- `RegexInStr("text", "pattern"[, start[, options]])` returns the 1-based position of the first match or `0` when there is no match
- `RegexMatch("text", "pattern"[, options])` returns `Null` when there is no match, otherwise it returns an array whose first element is the full match and whose remaining elements are the capture groups in order
- `RegexReplace("text", "pattern", "replacement"[, count[, options]])` replaces matches and returns the updated string

Regex patterns support normal character classes such as `[abc]`, `[a-z]`, `[^abc]`, `\d`, `\w`, and `\s`.

Supported option characters are:

- `i` for case-insensitive matching
- `m` for multiline matching
- `s` for dot-matches-newline
- `x` for verbose matching

By default, regex matching is case-sensitive. Add `i` to `options` when you want case-insensitive matching.

Replacement strings in `RegexReplace()` use `$0`, `$1`, `$2`, and so on for backreferences, and `$$` emits a literal dollar sign.

Examples:

```ass
Dim text = "Ada Lovelace"
Dim match = RegexMatch(text, "(\w+)\s+(\w+)")
Dim first_name = match[1]
Dim last_name = match[2]
Dim swapped = RegexReplace(text, "(\w+)\s+(\w+)", "$2, $1")
Dim literal = RegexEscape("a.b")
```

### Time Functions

The built-in date and time helpers cover `Time()`, `UTCTime()`, `LocalTime()`, `NowDate()`, `NowTime()`, `NowDateTime()`, `DateToString()`, `DateToLocalString()`, `DateToUTCString()`, `UTCDateTime()`, `ParseDateTime()`, `ParseDateTimeInOffset()`, `FormatDateTime()`, `FormatDateTimeInOffset()`, `DateAdd()`, `DateDiff()`, `ConvertTimeZone()`, `UTCOffset()`, `TimeZoneOffset()`, `StartOfDay()`, `EndOfDay()`, `StartOfMonth()`, `EndOfMonth()`, `StartOfWeek()`, `DayOfWeek()`, `DayOfYear()`, `DatePart()`, `DateSerial()`, `TimeSerial()`, `DaysInMonth()`, `IsLeapYear()`, `IsDate()`, and `IsTime()`, and are split into a few small groups:

- `Time()` returns the current Unix timestamp in seconds
- `LocalTime()` and `UTCTime()` return `tm` structs for local time and UTC
- `NowDate()`, `NowTime()`, `NowDateTime()`, `DateToString()`, `DateToLocalString()`, and `DateToUTCString()` return human-readable local or UTC strings
- `ParseDateTime()` and `ParseDateTimeInOffset()` turn text into Unix epoch seconds
- `FormatDateTime()` and `FormatDateTimeInOffset()` turn epoch values or `tm` structs into formatted strings
- `DateAdd()`, `DateDiff()`, `ConvertTimeZone()`, `UTCOffset()`, and `TimeZoneOffset()` handle time math and fixed-offset conversion
- `StartOfDay()`, `EndOfDay()`, `StartOfMonth()`, `EndOfMonth()`, `StartOfWeek()`, `DayOfWeek()`, `DayOfYear()`, `DatePart()`, `DateSerial()`, `TimeSerial()`, `DaysInMonth()`, `IsLeapYear()`, `IsDate()`, and `IsTime()` provide calendar and validation helpers

Example:

```ass
Dim current_time = Time()
Dim current_local = LocalTime(current_time)
Dim current_utc_text = UTCDateTime()
Dim parsed_offset = ParseDateTimeInOffset("2026-05-26 15:04:05", "%Y-%m-%d %H:%M:%S", "+0200")
Dim utc_round_trip = ConvertTimeZone(parsed_offset, "+0200", "+0000")
Dim offset_minutes = UTCOffset(current_time)
Dim week_start = StartOfWeek(current_time)
WriteLn(current_utc_text)
WriteLn(FormatDateTimeInOffset(parsed_offset, "%Y-%m-%d %H:%M:%S %z", "+0200"))
WriteLn(FormatDateTimeInOffset(utc_round_trip, "%Y-%m-%d %H:%M:%S %z", "+0000"))
WriteLn(offset_minutes)
WriteLn(week_start)
WriteLn(IsDate(NowDate()))
WriteLn(IsTime(NowTime()))
WriteLn(DatePart(current_time, "month"))
WriteLn(DateSerial(2026, 5, 26))
WriteLn(TimeSerial(15, 4, 5))
WriteLn(DaysInMonth(current_time))
WriteLn(IsLeapYear(2024))
WriteLn(IsLeapYear(2026))
```

For the broader runnable smoke test that exercises these helpers together, see [samples/date_time_demo.ass](../../samples/date_time_demo.ass).

Examples:

```ass
WriteLn("Hello from the runtime")
Sleep(250)
MouseClick("left", 100, 200, 1)
Hotkey("ctrl", "c")
```

`SendKeys()` can also pause between emitted keypresses:

```ass
SendKeys("Test", 250)
```

Brace tokens still work in delayed mode:

```ass
SendKeys("A,{enter}B", 100)
```

If the `PlaybackSendKeyTapsInsteadOfText` preference path is enabled, the runtime uses key taps for printable characters instead of text events, while still preserving the same delay behavior.

For the full builtin inventory and implementation status, see [Builtin Coverage Map](builtin_coverage_map.md).

For a runnable file-reading example that prints each line from a sibling fixture, see [ReadFile Demo](../../samples/README.md#readfile-demo).

## Practical Notes

- The parser is newline-sensitive for statement separation.
- Comments may appear anywhere whitespace is allowed.
- `True`, `False`, and `Null` are recognized as literals.
- `@name` host identifiers are used when runtime host values are injected.
- `@name` runtime values are read-only in scripts, even though the host/runtime can set them internally.
- `Select Case` is supported for structured multi-branch control flow.
- The language is designed to round-trip through `ScriptDocument` formatting and runtime execution without needing extra syntax sugar.

## Related Docs

- [Docs Index](../index.md)
- [Generate Script Guide](generate_script_guide.md)
- [Open Script Guide](open_script_guide.md)
- [String Helper Examples](string_helpers_examples.md)
- [Builtin Coverage Map](builtin_coverage_map.md)
