# ActionShellScript Docs

This directory contains project documentation for `ActionShellScript`.

Portability note: `Struct` remains a core cross-platform language feature, `Record` is script-only, and Win32 DLL interop is a Windows-only backend capability.

`ActionShellScript` now covers the recording-to-document-authority pipeline through phase 7:

- phase 1: raw recording capture
- phase 2: interpretation
- phase 3: shaping
- phase 4: generated script preview/export
- phase 5: converted recording output into authoritative `ScriptDocument` plus CLI-first parse, diagnostics, and formatting services
- phase 6: derived playback planning and execution from explicit recording authority or authoritative `ScriptDocument` playback
- phase 7: debugger execution from `ScriptDocument` through runtime hooks and a live `DebugSession` (see the internal architecture docs)

## Release Notes

- [v0.2.0a2 - Alpha 2](releases/v0.2.0a2-alpha-2.md)

Phase 6 playback is complete as an explicit derived execution slice:

- `ass-cli play recording path\to\session.json`
- `ass-cli play script path\to\document.ass`
- `ass-cli play script path\to\document.ass --mode live --demo-live --ass-play`
- playback plans, results, previews, and executor state remain derived from the chosen authority source
- when a recording is converted into a document in the GUI or CLI, the resulting `ScriptDocument` is the authoritative source of truth for editing, saving, analysis, formatting, and script playback

### Install
From the repo root:

```powershell
python -m pip install -r requirements.txt
```

Use `requirements.txt` for the shortest path, or run `python -m pip install -e .[dev]` directly. Both install the current checkout in editable mode and pull in the declared dev dependency used by the documented test command.

### Run
Use either the installed console entry point or module invocation:

```powershell
ass-cli record --save-raw .\session.json
python -m apps.cli.main
```

`ass-cli` is the recommended front-end for the common workflows.
The first desktop frontend is now available as `ass-gui`, which opens the Qt-based document workbench for opening, editing, analyzing, formatting, and breakpoint-marking `ScriptDocument` files. When a recording is converted in the GUI, the resulting `ScriptDocument` is the authoritative source of truth for that workflow. The workbench now also exposes the summary sidebar, workspace tab visibility controls, a dedicated `Preview Play` action for preview-mode playback, and a `Documentation` toolbar button that opens the built-in help browser with a searchable table of contents and docs landing page. The help browser also has its own standalone launcher, `ass-help`, so you can keep docs open independently of the main workbench.
The `Pixel Inspector` tool under `Tools > Pixel Inspector...` is Windows-aware by design. It relies on Win32 APIs to identify the window handle and title under the cursor, so those fields are available on Windows and fall back to unavailable on other platforms. The live magnifier and pixel sampling still use Qt capture APIs, but the window metadata path is intentionally platform-specific and should be treated as a Windows feature. The toolbar now includes quick actions for `Copy`, `Capture`, `Pointer Coordinates`, `Coordinate Capture`, and `Refresh Output`, and the dedicated [Pixel Inspector User Guide](user/pixel_inspector_guide.md#main-controls) covers the full control set and workflows in more detail.
The desktop preferences are intentionally split into one persisted bundle plus a live editing layer. `desktop_settings.json` stores a `DesktopSettingsBundle` with separate `application`, `playback`, `recording`, `files`, `diagnostics`, `runtime`, and `theme` sections, while the `theme` section itself wraps the nested `DesktopPreferences` model for appearance, scripting, and font settings. The preferences dialog edits a snapshot of that bundle, and the window applies changes immediately to play, record, debug, and diagnostics-tab behavior. Dirty state is derived from the canonical bundle snapshot, so restore-defaults and section badges stay in sync with the saved settings instead of relying on page-local flags. The General page owns startup behavior such as restoring the last opened workspace and showing the preview tab, while Appearance now splits into `Editor`, `Style`, `Formatting`, and `Dirty State` tabs and covers editor styling, script formatting, dirty-indicator styling, and fonts. The Workspace page now also includes the hidden-tab selection strip collapse control, which defaults to collapsed, alongside the summary sidebar placement, Analysis tab visibility, formatted preview tab visibility, raw recordings tab visibility, and Diagnostics tab visibility controls. The Runtime page owns the mouse-movement curve editor, the preview toggle, and the step controls, and it now reflows between a side-by-side layout and a stacked layout when the window narrows. The Recording page now includes `Exclude main window during recording`, which keeps the workbench itself out of captured input when you are driving the recorder in front of the app. The Files page owns the raw-recording, converted-script, and diagnostic-log paths. The Hotkeys page now uses a dedicated key-capture editor with a visible clear affordance, ignores common clipboard/edit shortcuts while capturing, and includes the debugger step, continue, and stop shortcuts alongside the rest of the workspace bindings. The Workspace and Diagnostics pages keep the diagnostics-tab visibility toggle synchronized so the tab state stays aligned wherever the setting is edited. The Document Status dialog reports the recording exclusion state alongside the conversion route so you can tell whether the active document came from a self-excluding capture. On Windows, the standard uninstall path removes both the installed app tree and the app-owned `%APPDATA%\ActionShellScript` data tree, so the default `desktop_settings.json` and recordings folders do not linger after removal.
Desktop preferences now persist together in one unified settings file:

- `desktop_settings.json` stores the workspace-level application, playback, recording, files, diagnostics, runtime, and theme bundle
- first load automatically migrates legacy split files into `desktop_settings.json` when either old file is still present
- the General section includes workspace startup controls, including restore-last-workspace and preview-tab visibility
- the Appearance section includes the `Editor`, `Style`, `Formatting`, and `Dirty State` tabs for editor styling, script formatting, and dirty-indicator controls for the editor, main window, and Preferences UI
- the Runtime section includes the mouse-movement curve editor, preview toggle, step controls, and default mouse-move speed for runtime-backed execution
- the Files section includes the raw-recording, converted-script, and diagnostic-log output paths
- restore-last-workspace tracking is best-effort and is only persisted when that option is enabled

The public CLI surface now also includes the legacy `ass-*` commands plus `ass-debug` for runtime-backed debugger sessions.

Useful flags:

- `--session-id demo-session`
- `--save-raw .\session.json`
- `--no-save`
- `--mouse-move-threshold 4`
- `--stop-hotkey Shift+Esc`
- `--debug-stop-hotkey`
- `--no-mouse-moves`
- `--no-mouse-buttons`
- `--no-mouse-wheel`
- `--no-keyboard`
- `--suppress`

Start recording, perform a short interaction, then press `Shift+Esc` by default to stop and print the session summary. You can still use `Ctrl+C`, or override the stop chord with `--stop-hotkey`. `--stop-hotkey` accepts `|`-separated alternates, so `--stop-hotkey Shift+Esc|Ctrl+C` lets either chord stop recording in one run. The configured stop chord is intentionally suppressed from the recorded raw keyboard events. Use `--debug-stop-hotkey` when you want to inspect the normalized hotkey matching output on stderr. Use `ass-cli record --save-raw .\session.json` when you want the raw session JSON to flow into the later `session.json` examples. The downstream raw-session commands now default to `.\session.json`, so `ass-cli interpret`, `ass-cli shape --show-actions`, `ass-cli generate --output .\generated.ass`, `ass-cli open-script --output .\authoritative.ass`, and `ass-cli play recording --mode preview` work without an explicit input path when you want the default session file. Pass `--no-save` to `ass-cli record` if you want the old in-memory-only behavior back.

## Phase 2 Interpretation CLI
Phase 2 derives meaning from a raw recording without mutating the original `RecordingSession`.

```powershell
ass-interpret path\to\session.json
ass-interpret path\to\session.json --show-events
ass-interpret path\to\session.json --click-max-move-distance-px 2 --drag-min-distance-px 12
```

The JSON input is a single object with `session_id` plus an `events` array using the raw recording vocabulary (`mouse_down`, `mouse_up`, `mouse_move`, `mouse_wheel`, `key_down`, `key_up`). The command prints a summary of the derived `InterpretedRecording` and can optionally print each interpreted event as a readable one-line summary.

Interpretation tuning flags are available on both `ass-interpret` and `ass-record-interpret`:

- `--click-max-move-distance-px`
- `--double-click-max-interval-ms`
- `--double-click-max-distance-px`
- `--double-click-max-pause-ms`
- `--double-click-max-inter-click-move-distance-px`
- `--drag-min-distance-px`
- `--drag-min-duration-ms`

## One-Shot Live Phase 2
To test phase 2 interactively in one step, use:

```powershell
ass-record-interpret
ass-record-interpret --show-events
ass-record-interpret --save-raw .\session.json
ass-record-interpret --show-events --click-max-move-distance-px 2 --drag-min-distance-px 12
```

This command records live input with the same capture flags as `ass-record`, stops with the same `--stop-hotkey` behavior, and immediately prints the derived interpretation summary. With `--show-events`, it prints readable one-line interpreted event summaries instead of raw JSON blobs.

Use `--save-raw path.json` when you want to keep the raw `RecordingSession` on disk for later inspection or for a separate `ass-interpret path.json` run.

## Phase 3 Shaping CLI
Phase 3 consumes `InterpretedRecording` truth and reshapes it for downstream consumers without mutating interpretation.

```powershell
ass-shape .\samples\click.json
ass-shape .\samples\hotkey_copy.json --show-actions
ass-shape .\samples\hotkey_copy.json --keyboard-output-style text --show-actions
```

The command loads a saved raw session JSON file, interprets it, then shapes the interpreted events into a `ShapedActionSequence`. Use `--show-actions` to print one-line shaped action summaries. Shaping flags let you control delay emission, mouse move cleanup, click simplification, and whether printable keyboard input stays structured or collapses into `text`.

## Phase 4 Generation CLI
Phase 4 consumes `ShapedActionSequence` truth and renders a derived `GeneratedScript` without turning that generated text into editable authority.

```powershell
ass-generate .\samples\hotkey_copy.json
ass-generate .\samples\drag.json --output .\generated.ass
ass-generate .\samples\click.json --no-header-comments --no-script-delays
```

The command loads a raw session JSON file, interprets it, shapes it, and generates phase-4 script output. By default it prints a summary plus the generated script preview. Use `--output path.ass` to write the generated script output to disk.

Generation flags let you control:

- header comments with `--no-header-comments`
- source summary comments with `--no-source-summary`
- standalone delay rendering with `--no-script-delays`
- unknown-action comments with `--emit-unsupported-comments`
- line endings with `--line-ending lf|crlf`

## Phase 5 Document Conversion CLI
Phase 5 converts a raw session JSON file into an authoritative `ScriptDocument`, then runs parse, diagnostics, and formatting services against document text. The diagnostics pass now includes semantic checks for unsupported function calls, so typos like `SleepX(1000)` are reported instead of being ignored. The default path still uses the generated-script conversion path, and an explicit direct-import mode is also available for minimal translation.

```powershell
ass-open-script .\samples\hotkey_copy.json
ass-open-script .\samples\drag.json --output .\authoritative.ass
ass-open-script .\samples\click.json --show-diagnostics --show-formatted
```

The command loads a raw session JSON file, interprets it, shapes it, generates script output, converts that output into a `ScriptDocument`, and then runs the language-service slice against `ScriptDocument.text`. The printed "Authoritative document text" section is the resulting `ScriptDocument.text`, not pre-conversion preview state. When that converted document is written to disk, ActionShellScript writes any available provenance into a sibling `.ass.meta.json` sidecar. The `.ass` file keeps the short provenance header for the conversion route and capture-exclusion setting, while the sidecar stores the full provenance payload. Keep the `.ass` and `.ass.meta.json` files together if you move or check in converted scripts.

## Phase 6 Playback CLI
Phase 6 builds and executes a derived `PlaybackPlan` from one explicit authority source at a time.

The checked-in [SendKeys Key Tap Transport Demo](../samples/README.md#sendkeys-key-tap-transport-demo) is the canonical live-demo repro for this path:

```powershell
ass-cli play script .\samples\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events
```

```powershell
ass-cli play recording .\samples\click.json
ass-cli play recording .\samples\drag.json --mode preview --show-events
ass-cli play script .\generated.ass --mode live --ass-play
ass-cli play script .\generated.ass --mode live --demo-live --ass-play --show-events
ass-cli play script .\samples\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events
ass-cli play script .\generated.ass --mode live --step --ass-play --show-events
ass-cli play script .\generated.ass --mode live --delay-ms 250 --ass-play
ass-cli play script .\generated.ass --mode live --delay-ms 250 --settle-ms 500 --ass-play
```

`ass-cli play` never guesses the active source. You choose either `recording` or `script`, then the command derives a playback plan from that authority and executes it in `preview` or `live` mode. The CLI defaults to `preview` so the first execution path is safe and inspectable.
For a deterministic live walkthrough during development or docs testing, use `--demo-live` with `--mode live`; that path routes through an in-memory live host and, with `--show-events`, prints the dispatched host calls instead of touching real mouse or keyboard input. When you want script playback to emit SendKeys printable characters as key taps, add `--ass-play`. The checked-in [SendKeys Key Tap Transport Demo](../samples/README.md#sendkeys-key-tap-transport-demo) is the canonical repro for that path.
Use `--step` to pause before each playback event, `--delay-ms N` to slow down each event with a fixed pre-dispatch delay, and `--settle-ms N` to add a pause after mouse moves before mouse button actions during live playback.
When the source is a script, `Write` and `WriteLn` output is also surfaced through the playback summary and printed by `ass-cli play`.

## Phase 7 Debugger CLI
Phase 7 is complete as an explicit runtime-backed debugger slice.

Phase 7 runs a `ScriptDocument` through `ScriptRuntime` with `RuntimeDebugHooks`, produces a live `DebugSession`, and prints debug events through `ass-debug`.

```powershell
ass-debug script .\generated.ass
ass-debug script .\generated.ass --step
ass-debug script .\generated.ass --step --ass-play
ass-debug script .\generated.ass --breakpoint 12
ass-debug script .\generated.ass --step --breakpoint 12
```

The debugger starts from editable script authority and runtime source mapping, not from playback caches or reconstructed UI state. Add `--ass-play` when the script is SendKeys-heavy and you want printable characters to reach the target as key taps instead of text events, which is often necessary for emulators and other keystroke-sensitive apps.

## Sample Fixtures
The repo includes a small fixture set under `samples/` using the same raw session JSON shape produced by `--save-raw`.

```powershell
ass-interpret .\samples\click.json --show-events
ass-interpret .\samples\borderline_click_drag.json --show-events
ass-interpret .\samples\double_click.json --show-events
ass-interpret .\samples\drag.json --show-events
ass-interpret .\samples\hotkey_copy.json --show-events
```

These are useful for quick sanity checks before or after changing interpretation thresholds.

The dedicated borderline fixture is especially useful for threshold tuning:

```powershell
ass-interpret .\samples\borderline_click_drag.json --show-events
ass-interpret .\samples\borderline_click_drag.json --show-events --click-max-move-distance-px 6
ass-interpret .\samples\borderline_click_drag.json --show-events --drag-min-distance-px 6
```

## Sections
- [User Guides](user/generate_script_guide.md)
- [Structs and DLL Interop](user/structs_and_dlls.md)
- [Struct Layout Contract](user/struct_layout_contract.md)

## User Guides
- [ass-cli Quickstart](user/ass_cli_quickstart.md)
- [record_and_play_live.ps1 Wrapper](user/record_and_play_live_wrapper.md)
- [Language Reference](user/language_reference.md)
- [Generate Script Guide](user/generate_script_guide.md#what-ass-generate-does)
- [Open Script Guide](user/open_script_guide.md#what-ass-open-script-does)
- [GUI Preference Spec](user/gui_preference_spec.md#goal)
- [Pixel Inspector User Guide: controls and toolbar actions](user/pixel_inspector_guide.md#main-controls)
- [Desktop Table API](../apps/desktop/table_api/README.md)
- [CLI Cheat Sheet](user/cli_cheat_sheet.md#phase-1-record)
- [ass-cli Spec](user/ass_cli_spec.md)
- [Math Builtin Examples](user/math_builtin_examples.md)
- [String Helper Examples](user/string_helpers_examples.md)
- [Enum Examples](user/enum_examples.md)
- [ReadFile Demo](../samples/README.md#readfile-demo)
- [Date and Time Demo](../samples/README.md#date-and-time-demo)
- [Enum Examples Demo](../samples/README.md#enum-examples-demo)
- [SendKeys Key Tap Transport Demo](../samples/README.md#sendkeys-key-tap-transport-demo): canonical live-demo repro for the SendKeys transport path.
- String helper examples cover compare/search/replace, slicing, trimming, case conversion, and runtime values in [String Helper Examples](user/string_helpers_examples.md).
- Enum examples show namespace access, comparisons, and helper functions in [Enum Examples](user/enum_examples.md).
- [Builtin Coverage Map](user/builtin_coverage_map.md)

## Windows Interop
- [Struct and DLL Quickstart](user/struct_and_dll_quickstart.md): practical example-first guide for `Struct`, `Declare Func`, and `Declare Sub`.
- [Structs and DLL Interop](user/structs_and_dlls.md): full walkthrough of the current Windows interop surface and wrapper behavior.
- [Struct Layout Contract](user/struct_layout_contract.md): exact ABI rules, rejection cases, and the `GetMonitorInfoEx()` exception.
- [Monitor Info Wrapper Demo](../samples/README.md#monitor-info-wrapper-demo): runnable `GetMonitorInfo` / `GetMonitorInfoEx` flow with the wrapper guidance.

