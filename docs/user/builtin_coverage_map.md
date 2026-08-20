# Builtin Coverage Map

This document maps the names listed in `core/runtime/builtins/builtin_registry.py` to the current runtime implementation status.

Status meanings:

- `implemented`: the runtime has a concrete dispatch branch and observable behavior.
- `partially implemented`: the name exists and does something, but the behavior is limited or not visible through `ass-cli play` in the way you might expect.
- `not wired yet`: reserved for future registry names that are not yet dispatched.

| name | status | why |
|---|---|---|
| `Abs` | implemented | Returns the numeric absolute value. |
| `AppendBytes` | implemented | Appends binary data to a file with runtime validation and filesystem error handling. |
| `AppendFile` | implemented | Appends text to a file with runtime validation and encoding support. |
| `Asc` | implemented | Returns the code point of the first character. |
| `AscW` | implemented | Same as `Asc` in the current runtime. |
| `Ceiling` | implemented | Returns a numeric value rounded up to the next integer. |
| `Base64` | implemented | Returns Base64 text for binary input. |
| `Binary` | implemented | Coerces a value to binary data. |
| `BinaryLength` | implemented | Returns the number of bytes in a binary value. |
| `BinaryMid` | implemented | Returns a slice of binary data from a 1-based start index. |
| `BinaryToString` | implemented | Decodes binary data using the selected encoding mode. |
| `BitAnd` | implemented | Returns bitwise AND of its arguments. |
| `BitNot` | implemented | Returns bitwise NOT of its argument. |
| `BitNotUnsigned` | implemented | Returns the unsigned 32-bit bitwise NOT result. |
| `BitOr` | implemented | Returns bitwise OR of its arguments. |
| `BitRotate` | implemented | Rotates a 32-bit value with width selection and sets `Error` on invalid width. |
| `BitShift` | implemented | Returns left or right shift depending on the sign of the shift value. |
| `BitXor` | implemented | Returns bitwise XOR of its arguments. |
| `Chr` | implemented | Returns the character for an integer code point. |
| `ChrW` | implemented | Same as `Chr` in the current runtime. |
| `CreateDir` | implemented | Creates directories with runtime validation. |
| `CopyDir` | implemented | Copies a directory tree to a target directory path with optional overwrite support. |
| `CopyFile` | implemented | Copies a file to a target file path with optional overwrite support. |
| `DeleteFile` | implemented | Deletes files with runtime validation and filesystem error handling. |
| `DirectoryDelete` | implemented | Removes a directory path and can optionally recurse through its contents. |
| `DiagWrite` | implemented | Writes into the runtime diagnostics stream, honoring diagnostics preferences and surfacing through the Diagnostics tab, log file, and standard I/O when enabled. |
| `DiagWriteLn` | implemented | Same as `DiagWrite`, but appends `\n` to the emitted diagnostics message. |
| `Exp` | implemented | Returns `e` raised to a numeric power. |
| `DirectoryName` | implemented | Returns the parent directory portion of a path. |
| `DirectoryList` | implemented | Returns the immediate child directories for a directory path, optionally filtered by pattern. |
| `DirExists` | implemented | Returns whether a path exists as a directory. |
| `EnumerateFiles` | implemented | Returns recursive child files for a directory path, optionally filtered by pattern. |
| `ExtensionName` | implemented | Returns the file extension portion of a path. |
| `Floor` | implemented | Returns a numeric value rounded down to the previous integer. |
| `Int` | implemented | Returns the integer part of a numeric value by dropping the fractional portion. |
| `Round` | implemented | Returns a rounded numeric value with optional decimal-place control. |
| `ArrayLength` | implemented | Returns the number of items in an array. |
| `ArrayInsert` | implemented | Inserts one or more values into an array in place at a zero-based index and returns the new length. |
| `ArrayPush` | implemented | Appends one or more values to an array in place and returns the new length. |
| `ArrayPop` | implemented | Removes and returns the last array item, returning `Null` and setting `Error` when the array is empty. |
| `ArrayRemove` | implemented | Removes one or more values from an array in place and returns the removed value or values. |
| `ArrayContains` | implemented | Returns `1` when an array contains a value and `0` otherwise. |
| `ArrayContainsAll` | implemented | Returns `1` when an array contains every requested value and `0` otherwise. |
| `ArrayCount` | implemented | Returns how many times a value appears in an array. |
| `ArrayInitialize` | implemented | Sets every element in an array to a single value and returns the array length after initialization. |
| `ArrayClear` | implemented | Sets every element in an array to an empty string and returns the array length after clearing. |
| `ArrayClone` | implemented | Returns a deep copy of an array that can be mutated independently of the original. |
| `ArrayRemoveAll` | implemented | Removes every matching value from an array in place and returns the number of items removed. |
| `ArrayIndexOf` | implemented | Returns the zero-based index of the first matching array item, or `-1` when there is no match. |
| `ArrayLastIndexOf` | implemented | Returns the zero-based index of the last matching array item, or `-1` when there is no match. |
| `ArrayReverse` | implemented | Returns a reversed copy of an array without mutating the source array. |
| `ArraySort` | implemented | Returns a sorted copy of an array, with optional descending and case-sensitivity control. |
| `ArrayUnique` | implemented | Returns a copy of an array with duplicates removed while preserving first-seen order. |
| `ArrayToString` | implemented | Flattens an array into a string using commas by default or a custom separator. |
| `ArrayJoin` | implemented | Alias for `ArrayToString`, using commas by default or a custom separator. |
| `ArraySlice` | implemented | Returns a new zero-based slice of an array without mutating the source array. |
| `FileExists` | implemented | Returns whether a path exists as a file. |
| `FileChecksum` | implemented | Returns a lowercase hex checksum for file contents with optional algorithm selection. |
| `FileInfo` | implemented | Returns path metadata as a record including size, name, parent path, and timestamps. |
| `FileCompare` | implemented | Compares the binary contents of two files and returns -1, 0, or 1. |
| `FileList` | implemented | Returns the immediate child files for a directory path, optionally filtered by pattern. |
| `FileName` | implemented | Returns the final path component. |
| `FileHash` | implemented | Returns a lowercase hex digest for file contents with optional algorithm selection. |
| `FileSize` | implemented | Returns the size in bytes for a file or the recursive size of a directory tree. |
| `FileTime` | implemented | Returns a selected timestamp for a file or directory. |
| `GetClientRect` | implemented | Returns the client rectangle for a window handle. |
| `GetCurrentEventDelay` | implemented | Returns the current runtime event delay. |
| `GetCursorPos` | implemented | Returns the current cursor position. |
| `GetClassName` | implemented | Returns the window class name. |
| `GetMonitorInfo` | implemented | Returns monitor information for a handle. |
| `GetMonitorInfoEx` | implemented | Returns extended monitor information for a handle. |
| `GetParent` | implemented | Returns the parent window handle. |
| `GetWindowLongPtr` | implemented | Returns the long pointer value for a window attribute. |
| `GetWindowPlacement` | implemented | Returns the placement structure for a window. |
| `GetWindowRect` | implemented | Returns the outer rectangle for a window handle. |
| `GetWindowText` | implemented | Returns the window title text. |
| `FromBase64` | implemented | Decodes Base64 text to binary data. |
| `FromHex` | implemented | Decodes hexadecimal text to binary data. |
| `Hex` | implemented | Returns hexadecimal text for binary input. |
| `HotKey` | implemented | Emits a `hotkey` playback event. |
| `IsIconic` | implemented | Returns whether a window is minimized. |
| `IsPathValid` | implemented | Validates whether a path string is acceptable for the host platform. |
| `IsWindowEnabled` | implemented | Returns whether a window is enabled. |
| `IsWindowVisible` | implemented | Returns whether a window is visible. |
| `IsZoomed` | implemented | Returns whether a window is maximized. |
| `KeyDown` | implemented | Emits a `key_down` playback event. |
| `KeyPress` | implemented | Emits repeated key playback events. |
| `KeyToggle` | implemented | Routes through the host-service seam. |
| `KeyUp` | implemented | Emits a `key_up` playback event. |
| `MouseDown` | implemented | Emits a `mouse_down` playback event. |
| `MouseClick` | implemented | Emits a `mouse_click` playback event. |
| `MouseClickDrag` | implemented | Emits drag playback events with optional speed override. |
| `MouseDrag` | implemented | Emits drag playback events with duration and path normalization. |
| `MouseMove` | implemented | Emits a `mouse_move` playback event. |
| `GetMouseMoveSpeed` | implemented | Returns the current effective mouse move speed. |
| `SetMouseMoveSpeed` | implemented | Updates the mouse move speed override and returns the effective speed. |
| `MouseUp` | implemented | Emits a `mouse_up` playback event. |
| `MouseWheel` | implemented | Emits a `mouse_wheel` playback event. |
| `MsgBox` | implemented | Routes through the host-service seam with validation. |
| `Mod` | implemented | Returns the modulus of two numeric values. |
| `PathCombine` | implemented | Joins multiple path segments. |
| `PathNormalize` | implemented | Normalizes a path string. |
| `PathExists` | implemented | Returns whether any path exists. |
| `MoveDir` | implemented | Moves a directory tree to a target directory path with optional overwrite support. |
| `MoveFile` | implemented | Moves a file to a target file path with optional overwrite support. |
| `RemoveDir` | implemented | Removes a directory path and can optionally recurse through its contents. |
| `WalkDir` | implemented | Returns recursive child directories for a directory path, optionally filtered by pattern. |
| `SetCurrentEventDelay` | implemented | Updates the runtime event delay and returns the effective delay. |
| `PixelGetColor` | implemented | Routes through the host-service seam with validation. |
| `PixelSearch` | implemented | Routes through the host-service seam with validation and result-shape checks. |
| `ReadBytes` | implemented | Reads raw bytes from a file. |
| `ReadFile` | implemented | Reads text from a file with optional encoding. |
| `SendKeys` | implemented | Parses and emits key/text playback sequences, with optional inter-key delays. |
| `SendText` | implemented | Emits a `text` playback event. |
| `Sleep` | implemented | Emits a `delay` playback event. |
| `NowDateTime` | implemented | Returns a localized date and time string using the computer's regional settings. |
| `DateToString` | implemented | Returns a localized date and time string using the computer's regional settings. |
| `DateToLocalString` | implemented | Returns a localized date and time string using the computer's regional settings. |
| `DateToUTCString` | implemented | Returns a UTC date and time string. |
| `UTCDateTime` | implemented | Returns a UTC date and time string. |
| `ParseDateTime` | implemented | Parses common local, ISO, and UTC date and time strings into Unix epoch seconds, with an optional strict format parameter and configurable separator tolerance by token group. |
| `FormatDateTime` | implemented | Formats an epoch timestamp or `tm` struct using a strftime-style format string. |
| `DateAdd` | implemented | Adds a time interval to an epoch timestamp using local calendar arithmetic. |
| `DateDiff` | implemented | Returns the elapsed difference between two epoch timestamps in a requested unit. |
| `ConvertTimeZone` | implemented | Shifts an epoch timestamp between fixed UTC offsets. |
| `UTCOffset` | implemented | Returns the local offset from UTC for a supplied epoch timestamp in minutes. |
| `TimeZoneOffset` | implemented | Returns the local offset from UTC for a supplied epoch timestamp in minutes. |
| `FormatDateTimeInOffset` | implemented | Formats an epoch timestamp or `tm` struct using a strftime-style format string in a fixed UTC offset. |
| `ParseDateTimeInOffset` | implemented | Parses a date and time string into Unix epoch seconds using a fixed UTC offset. |
| `UTCTime` | implemented | Returns a `tm` struct for the current UTC calendar time. |
| `StartOfDay` | implemented | Returns the local epoch timestamp for the start of the day containing the supplied time. |
| `EndOfDay` | implemented | Returns the local epoch timestamp for the end of the day containing the supplied time. |
| `StartOfMonth` | implemented | Returns the local epoch timestamp for the start of the month containing the supplied time. |
| `EndOfMonth` | implemented | Returns the local epoch timestamp for the end of the month containing the supplied time. |
| `StartOfWeek` | implemented | Returns the local epoch timestamp for the start of the week containing the supplied time. |
| `DayOfWeek` | implemented | Returns the local weekday number for an epoch value. |
| `DayOfYear` | implemented | Returns the local day-of-year number for an epoch value. |
| `DatePart` | implemented | Returns a selected calendar field from an epoch value or `tm` struct. |
| `DateSerial` | implemented | Returns the local epoch timestamp for a supplied year, month, and day. |
| `TimeSerial` | implemented | Returns seconds since midnight for a supplied hour, minute, and second. |
| `DaysInMonth` | implemented | Returns the number of days in the month containing the supplied time. |
| `IsLeapYear` | implemented | Returns whether a calendar year is a leap year. |
| `IsDate` | implemented | Returns whether a string can be interpreted as a valid date or time using the runtime's regional parsing rules. |
| `IsTime` | implemented | Returns whether a string can be interpreted as a valid time using the runtime's regional parsing rules. |
| `LocalTime` | implemented | Returns a `tm` struct for the current or supplied epoch time, expressed in local calendar time. |
| `NowDate` | implemented | Returns the current local date using the computer's regional date format. |
| `NowTime` | implemented | Returns the current local time using the computer's regional time format. |
| `Time` | implemented | Returns the current Unix timestamp in seconds. |
| `String` | implemented | Returns a stringified value. |
| `StringCompare` | implemented | Compares two strings and optionally performs case-insensitive comparison when `compare_type` is `0`. |
| `StringIsAlpha` | implemented | Returns `1` when the string contains only alphabetic characters, otherwise `0`. |
| `StringIsAlphaNumeric` | implemented | Returns `1` when the string contains only letters and digits, otherwise `0`. |
| `StringIsASCII` | implemented | Returns `1` when the string contains only ASCII characters in the 0x00-0x7f range, otherwise `0`. |
| `StringIsDigit` | implemented | Returns `1` when the string contains only digit characters, otherwise `0`. |
| `StringIsFloat` | implemented | Returns `1` when the value converts to a decimal string with exactly one period and optional leading sign, otherwise `0`. |
| `StringIsInt` | implemented | Returns `1` when the string contains only an optional leading sign and digits, or when the input is already an integer expression. |
| `StringIsLower` | implemented | Returns `1` when the string contains only lowercase characters, otherwise `0`. |
| `StringIsSpace` | implemented | Returns `1` when the string contains only whitespace characters, including `Chr(0)`, otherwise `0`. |
| `StringIsUpper` | implemented | Returns `1` when the string contains only uppercase characters, otherwise `0`. |
| `StringInStr` | implemented | Returns the 1-based position of a substring, with optional case sensitivity, occurrence direction, and search-window limits. |
| `StringLength` | implemented | Returns the character length of a string. |
| `StringLeft` | implemented | Returns the leftmost characters from a string. |
| `StringStartsWith` | implemented | Returns `1` when a string begins with the given prefix, otherwise `0`. |
| `StringEndsWith` | implemented | Returns `1` when a string ends with the given suffix, otherwise `0`. |
| `StringContains` | implemented | Returns `1` when a string contains the given needle, otherwise `0`. |
| `StringSplit` | implemented | Returns an array of substrings split on a delimiter, with optional limit and case-sensitivity control. |
| `StringJoin` | implemented | Joins array elements into a string using an optional delimiter. |
| `StringReplace` | implemented | Replaces matching substrings or a start-position slice and stores the replacement count in `@Extended`. |
| `StringReverse` | implemented | Returns the characters from a string in reverse order. |
| `StringRight` | implemented | Returns the rightmost characters from a string. |
| `StringMid` | implemented | Returns a substring starting at a 1-based position with an optional length. |
| `StringTrimLeft` | implemented | Returns the string with a number of characters removed from the left. |
| `StringTrimRight` | implemented | Returns the string with a number of characters removed from the right. |
| `StringToLower` | implemented | Returns the lowercase form of a string argument. |
| `StringToUpper` | implemented | Returns the uppercase form of a string argument. |
| `RegexEscape` | implemented | Escapes literal text so it can be embedded safely in a regular expression. |
| `RegexIsMatch` | implemented | Returns `1` when the pattern matches anywhere in the text, otherwise `0`. |
| `RegexInStr` | implemented | Returns the 1-based position of the first regex match, with optional start and option flags. |
| `RegexMatch` | implemented | Returns `Null` when there is no match, otherwise returns an array containing the full match and capture groups. |
| `RegexReplace` | implemented | Replaces regex matches and supports `$0`/`$1` style replacement backreferences. |
| `Write` | implemented | Writes into runtime console output, which is surfaced through playback summary and `ass-cli play`. |
| `WriteBytes` | implemented | Writes raw bytes to a file. |
| `WriteFile` | implemented | Writes text to a file with optional encoding. |
| `WriteLn` | implemented | Writes into runtime console output and appends `\n`. |

## Notes

- The registry and dispatcher now align for the recovered builtin surface.
- `Write` and `WriteLn` now write into runtime console output and are surfaced through playback summary and `ass-cli play`.
- `DiagWrite` and `DiagWriteLn` record messages in the runtime diagnostics stream, so they follow the same diagnostics preferences as the rest of the structured logger output.
- `SetMouseMoveSpeed`, `MouseClickDrag`, and related mouse builtins now preserve and consume the effective speed override.
- `Ceiling`, `Exp`, `Floor`, `Int`, `Mod`, and `Round` are documented with a runnable `.ass` example in [Math Builtin Examples](math_builtin_examples.md).
- `AppendBytes`, `AppendFile`, `ReadBytes`, `ReadFile`, `WriteBytes`, and `WriteFile` cover the file IO surface, while `CopyDir`, `CopyFile`, `CreateDir`, `DirectoryDelete`, `DirectoryList`, `DirectoryName`, `DirExists`, `EnumerateFiles`, `FileChecksum`, `FileCompare`, `FileExists`, `FileHash`, `FileInfo`, `FileList`, `FileName`, `FileSize`, `FileTime`, `IsPathValid`, `MoveDir`, `MoveFile`, `PathCombine`, `PathExists`, `PathNormalize`, `RemoveDir`, and `WalkDir` cover the path helpers.
- `DirectoryList` and `FileList` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `RemoveDir` and `DirectoryDelete` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `CopyFile` and `CopyDir` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `MoveFile` and `MoveDir` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `FileSize`, `FileTime`, and `FileInfo` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `FileHash` and `FileChecksum` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `FileCompare` is documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `WalkDir` and `EnumerateFiles` are documented with a runnable example in [Path Helper Examples](path_helpers_examples.md).
- `Base64`, `Binary`, `BinaryLength`, `BinaryMid`, `BinaryToString`, `FromBase64`, `FromHex`, and `Hex` cover the binary conversion helpers.
- `StringCompare`, `StringInStr`, `StringReplace`, `StringStartsWith`, `StringEndsWith`, `StringContains`, `StringSplit`, `StringJoin`, `RegexEscape`, `RegexIsMatch`, `RegexInStr`, `RegexMatch`, and `RegexReplace` are documented with runnable `.ass` examples in [String Helper Examples](string_helpers_examples.md).
- `StringIsAlpha`, `StringIsAlphaNumeric`, `StringIsASCII`, `StringIsDigit`, `StringIsFloat`, `StringIsInt`, `StringIsLower`, `StringIsSpace`, `StringIsUpper`, `StringLength`, `StringLeft`, `StringRight`, `StringMid`, `StringTrimLeft`, and `StringTrimRight` cover the basic string slicing and trimming helpers.
- `ReadFile` is documented with a runnable `.ass` example in [ReadFile Demo](../../samples/README.md#readfile-demo).
- `StringReverse` adds the `StringReverse()` helper for reversing characters in a string.
- `StringToLower` and `StringToUpper` round out the runtime string case-conversion helpers with `StringToLower()` and `StringToUpper()`.
- `SendKeys(keyText[, msDelay])` can insert a delay between emitted keypresses and text characters when `msDelay` is provided, and it can switch printable output to key taps when `PlaybackSendKeyTapsInsteadOfText` is enabled.
- `StringInStr` follows the same string-search conventions as the recovered AutoIt-style builtins and is covered by runtime tests for left-to-right, right-to-left, and bounded searches.
- `StringReplace` follows the recovered AutoIt-style search-and-replace conventions, including occurrence direction, case sensitivity, and start-position replacement.
- `StringStartsWith`, `StringEndsWith`, `StringContains`, `StringSplit`, and `StringJoin` cover the most common string-prefix, suffix, containment, splitting, and joining helpers that are still missing from the runtime surface.
- `ArrayLength`, `ArrayInsert`, `ArrayPush`, `ArrayPop`, `ArrayRemove`, `ArrayContains`, `ArrayContainsAll`, `ArrayCount`, `ArrayInitialize`, `ArrayClear`, `ArrayClone`, `ArrayRemoveAll`, `ArrayIndexOf`, `ArrayLastIndexOf`, `ArrayReverse`, `ArraySort`, `ArrayUnique`, `ArrayToString`, `ArrayJoin`, and `ArraySlice` cover the common array list operations that the runtime surface was still missing, and they are documented with a runnable example in [Array Helper Examples](array_helpers_examples.md).
- `IsDate()` and `IsTime()` follow the same regional parsing rules as `ParseDateTime()` and distinguish between date-capable and time-only strings.
- `ConvertTimeZone()`, `FormatDateTimeInOffset()`, and `ParseDateTimeInOffset()` work together as a fixed-offset round-trip path.
- `DatePart()` extracts one calendar field from an epoch value or `tm` struct.
- `DateSerial()` builds a local midnight epoch timestamp from calendar components.
- `TimeSerial()` builds a time-only value as seconds since midnight.
- `DaysInMonth()` returns the number of days in the month containing the supplied time.
- `StartOfWeek()` returns the local epoch timestamp for the start of the week containing the supplied time.
- `UTCOffset()` returns the local offset from UTC for a supplied epoch timestamp in minutes.
- `TimeZoneOffset()` is a compatibility alias for `UTCOffset()`.
- These helpers are exercised together in [Date and Time Demo](../../samples/README.md#date-and-time-demo).

```ass
Dim lower_text = StringToLower("MiXeD Case")
Dim upper_text = StringToUpper("MiXeD Case")
Dim reversed_text = StringReverse("ActionShellScript")
Dim alpha_only = StringIsAlpha("Café")
Dim alpha_numeric_only = StringIsAlphaNumeric("Café42")
Dim ascii_only = StringIsASCII("ASCII text")
Dim digit_only = StringIsDigit("012345")
Dim float_only = StringIsFloat(1.25)
Dim int_only = StringIsInt(42)
Dim lower_only = StringIsLower("lowercase")
Dim space_only = StringIsSpace(" \t\r\n")
Dim upper_only = StringIsUpper("UPPERCASE")
WriteLn(lower_text)
WriteLn(upper_text)
WriteLn(reversed_text)
WriteLn(alpha_only)
WriteLn(alpha_numeric_only)
WriteLn(ascii_only)
WriteLn(digit_only)
WriteLn(float_only)
WriteLn(int_only)
WriteLn(lower_only)
WriteLn(space_only)
WriteLn(upper_only)
```

```ass
Dim local_date_text = "05/26/2026"
Dim local_time_text = "3:04:05 PM"
WriteLn(IsDate(local_date_text))
WriteLn(IsDate(local_time_text))
Dim time_text = "3:04:05 PM"
WriteLn(IsTime(time_text))
```

```ass
Dim utc_midday = ConvertTimeZone(0, "+0000", "+0200")
WriteLn(FormatDateTimeInOffset(utc_midday, "%Y-%m-%d %H:%M:%S %z", "+0200"))
WriteLn(ParseDateTimeInOffset("1970-01-01 02:00:00", "%Y-%m-%d %H:%M:%S", "+0200"))
```

```ass
Dim offset_minutes = UTCOffset(Time())
WriteLn(offset_minutes)
WriteLn(TimeZoneOffset(Time()))
```

```ass
WriteLn(ParseDateTimeInOffset("1970-01-01 02:00:00", "%Y-%m-%d %H:%M:%S", "+0200"))
```

- The scripting parser and runtime now also make loop control explicit: `Continue`, `Continue For`, `Continue While`, and `Continue Loop` are accepted, targeted continues propagate through nested loops, and top-level misuse reports a clear outside-of-loop error.
