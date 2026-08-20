# Sample Capture Fixtures

These sample files use the same raw `RecordingSession` JSON format written by:

- `ass-record --save-raw path.json`
- `ass-record-interpret --save-raw path.json`

They are intended as small, repeatable interpretation fixtures you can run from the repo root.

## Try Them

```powershell
ass-interpret .\samples\click.json --show-events
ass-interpret .\samples\borderline_click_drag.json --show-events
ass-interpret .\samples\double_click.json --show-events
ass-interpret .\samples\drag.json --show-events
ass-interpret .\samples\hotkey_copy.json --show-events
```

For debugger smoke testing, try the tiny script sample:

```powershell
ass-debug script .\samples\debugger_smoke.ass --step
ass-debug script .\samples\debugger_smoke.ass --breakpoint 2
```

That sample now includes `++` and `--` examples, so it is a quick place to see prefix and postfix increment behavior in action.

For the struct and Win32 interop surface, try the runnable demo:

```powershell
ass-debug script .\samples\struct_and_dll_demo.ass
ass-debug script .\samples\struct_and_dll_demo.ass --step
```

For the script-only `Record` demo, try:

```powershell
ass-debug script .\samples\record_demo.ass
ass-debug script .\samples\record_demo.ass --step
```

That sample also includes `++` and `--` snippets, which makes it a second quick place to see the increment and decrement operators in a more structured demo.

For a date and time smoke test, try:

```powershell
ass-debug script .\samples\date_time_demo.ass
ass-debug script .\samples\date_time_demo.ass --step
```

## SendKeys Key Tap Transport Demo

This checked-in `.ass` sample is the canonical repro for the SendKeys transport work. It exercises printable `SendKeys()` output in key-tap mode without touching real input when run with the deterministic live demo host.

Try:

```powershell
ass-cli play script .\samples\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events
```

## ReadFile Demo

This runnable sample reads `samples/read_file_demo.txt` with `ReadFile()` and prints each line with `WriteLn()`.

```powershell
ass-debug script .\samples\read_file_demo.ass
ass-debug script .\samples\read_file_demo.ass --step
```

## Date and Time Demo

This runnable sample exercises the date and time helpers with `Time()`, `LocalTime()`, `UTCTime()`, `ParseDateTime()`, `ParseDateTimeInOffset()`, `FormatDateTime()`, `FormatDateTimeInOffset()`, `ConvertTimeZone()`, `UTCOffset()`, `DateAdd()`, `DateDiff()`, `DateSerial()`, `TimeSerial()`, `DaysInMonth()`, and `IsLeapYear()`.

```powershell
ass-debug script .\samples\date_time_demo.ass
ass-debug script .\samples\date_time_demo.ass --step
```

## String Helpers Demo

This runnable sample exercises the string helper surface with `StringCompare()`, `StringInStr()`, `StringReplace()`, `RegexEscape()`, `RegexIsMatch()`, `RegexInStr()`, `RegexMatch()`, `RegexReplace()`, `StringToLower()`, `StringToUpper()`, `StringLength()`, `StringLeft()`, `StringRight()`, `StringMid()`, `StringTrimLeft()`, `StringTrimRight()`, `StringReverse()`, `StringSplit()`, and `StringJoin()`.

```powershell
ass-debug script .\samples\string_helpers_demo.ass
ass-debug script .\samples\string_helpers_demo.ass --step
```

## Regex Smoke Test

Run the string helpers demo and compare the regex helper output against this transcript:

```text
regex_escape: a\.b
regex_is_match: 1
regex_in_str: 9
regex_match_full: Ada Lovelace
regex_match_first: Ada
regex_match_last: Lovelace
regex_replace: a[1]b[2]c[3]
regex_replace_extended: 3
```

To step through it interactively, run:

```powershell
ass-debug script .\samples\string_helpers_demo.ass --step
```

## Enum Examples Demo

This runnable sample exercises `Enum` declarations with namespace-qualified members, direct member names, and a helper that turns enum values into readable labels.

```powershell
ass-debug script .\samples\enum_examples_demo.ass
ass-debug script .\samples\enum_examples_demo.ass --step
```

## Path Helpers Demo

This runnable sample uses `DirectoryList()` and `FileList()` to enumerate the checked-in `samples` folder and prints stable file and directory names.

```powershell
ass-debug script .\samples\path_helpers_demo.ass
ass-debug script .\samples\path_helpers_demo.ass --step
```

## Directory Removal Demo

This runnable sample creates a scratch directory under the current working directory and removes it with `RemoveDir()`.

```powershell
ass-debug script .\samples\remove_dir_demo.ass
ass-debug script .\samples\remove_dir_demo.ass --step
```

## Copy Helpers Demo

This runnable sample copies a file and a directory tree inside a temporary scratch directory, then removes the scratch directory with `RemoveDir()`.

```powershell
ass-debug script .\samples\copy_helpers_demo.ass
ass-debug script .\samples\copy_helpers_demo.ass --step
```

## Move Helpers Demo

This runnable sample moves a file and a directory tree inside a temporary scratch directory, then removes the scratch directory with `RemoveDir()`.

```powershell
ass-debug script .\samples\move_helpers_demo.ass
ass-debug script .\samples\move_helpers_demo.ass --step
```

## Metadata Helpers Demo

This runnable sample creates a file in a scratch directory, reads its metadata with `FileInfo()`, `FileSize()`, and `FileTime()`, verifies its contents with `FileHash()` and `FileChecksum()`, and then removes the scratch directory with `RemoveDir()`.

```powershell
ass-debug script .\samples\metadata_helpers_demo.ass
ass-debug script .\samples\metadata_helpers_demo.ass --step
```

## Traversal Helpers Demo

This runnable sample creates a small nested directory tree and scans it recursively with `WalkDir()` and `EnumerateFiles()`.

```powershell
ass-debug script .\samples\traversal_helpers_demo.ass
ass-debug script .\samples\traversal_helpers_demo.ass --step
```

## File Compare Demo

This runnable sample compares two identical files and two different files with `FileCompare()`.

```powershell
ass-debug script .\samples\file_compare_demo.ass
ass-debug script .\samples\file_compare_demo.ass --step
```

For the cursor-position wrapper demo, try:

```powershell
ass-debug script .\samples\cursor_pos_wrapper_demo.ass
ass-debug script .\samples\cursor_pos_wrapper_demo.ass --step
```

For the window-rectangle wrapper demo, try:

```powershell
ass-debug script .\samples\window_rect_wrapper_demo.ass
ass-debug script .\samples\window_rect_wrapper_demo.ass --step
```

For the client-rectangle wrapper demo, try:

```powershell
ass-debug script .\samples\client_rect_wrapper_demo.ass
ass-debug script .\samples\client_rect_wrapper_demo.ass --step
```

For the window-text wrapper demo, try:

```powershell
ass-debug script .\samples\window_text_wrapper_demo.ass
ass-debug script .\samples\window_text_wrapper_demo.ass --step
```

For the window-long-ptr wrapper demo, try:

```powershell
ass-debug script .\samples\window_long_ptr_wrapper_demo.ass
ass-debug script .\samples\window_long_ptr_wrapper_demo.ass --step
```

For the parent/enabled wrapper demo, try:

```powershell
ass-debug script .\samples\window_parent_enabled_wrapper_demo.ass
ass-debug script .\samples\window_parent_enabled_wrapper_demo.ass --step
```

For the class-name wrapper demo, try:

```powershell
ass-debug script .\samples\class_name_wrapper_demo.ass
ass-debug script .\samples\class_name_wrapper_demo.ass --step
```

For the window-state wrapper demo (`IsZoomed`, `IsIconic`, and `IsWindowVisible`), try:

```powershell
ass-debug script .\samples\window_state_wrapper_demo.ass
ass-debug script .\samples\window_state_wrapper_demo.ass --step
```

For the window-placement wrapper demo, try:

```powershell
ass-debug script .\samples\window_placement_wrapper_demo.ass
ass-debug script .\samples\window_placement_wrapper_demo.ass --step
```

## Monitor Info Wrapper Demo

This flow shows the Windows-only `GetMonitorInfo` and `GetMonitorInfoEx` wrappers and the struct guidance they rely on.

Try:

```powershell
ass-debug script .\samples\monitor_info_demo.ass
ass-debug script .\samples\monitor_info_demo.ass --step
```

Debugger pause commands:

- `[Enter]` or `i`: step into
- `o`: step over
- `u`: step out
- `c`: continue to the next breakpoint
- `g`: go to completion and ignore breakpoints
- `r`: restart the script from the top
- `q`: quit the debugger
- `h`: show the command help
- `p`: print a small source window around the current line
- `p *` or `p all`: print the whole script
- `p N`: print a window centered on line `N`
- `stack`: print the whole call stack
- `vars`: print all variables
- `locals`: print the top frame locals
- `frame N`: print a specific stack frame
- `frame top`: print the current frame

For threshold tuning, compare the borderline sample under different configs:

```powershell
ass-interpret .\samples\borderline_click_drag.json --show-events
ass-interpret .\samples\borderline_click_drag.json --show-events --click-max-move-distance-px 6
ass-interpret .\samples\borderline_click_drag.json --show-events --drag-min-distance-px 6
```

## Notes

- The files are hand-curated to reflect realistic saved capture shapes and timings.
- They are stable regression fixtures, not authoritative truth about every desktop or device.
- If you capture a real problematic interaction, prefer saving it with `--save-raw` and adding it here as a new fixture.
