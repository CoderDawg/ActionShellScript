# Builtin Migration Map

This document maps the old builtin implementation files in `Macro_Recorder` to their natural target locations in `ActionShellScript`.

Its goal is to make builtin migration work more concrete by answering:

- where the old builtin behavior currently lives
- which ASS files should receive that behavior
- which builtin families belong together
- which pieces should move directly and which should stay deferred

Status note:

- the playback, host-interaction, file/path, binary/encoding, and remaining utility slices described here have now been recovered in ASS
- the map remains useful as a provenance and architecture reference for where the recovered code came from

## Main Source Of Truth In Macro_Recorder

Most of the old builtin behavior lives in one file:

- `packages/app_core/runtime/builtin_macro_calls.py`

That file contains the `BuiltinMacroCallDispatcher` plus the concrete per-builtin implementation methods for most of the old runtime surface.

Supporting builtin-related runtime behavior also lives in:

- `packages/app_core/runtime/runtime_errors.py`
- `packages/app_core/runtime/execution_context.py`
- `packages/app_core/runtime/script_runtime.py`
- `packages/app_core/runtime/builtin_constants.py`

## Main ASS Target Files

The natural target files in ASS are:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- [core/runtime/builtins/builtin_registry.py](../../../core/runtime/builtins/builtin_registry.py)

If ASS recovers more of the old builtin surface later, additional helper files may become worthwhile, such as:

- `core/runtime/builtins/builtin_dispatcher.py`
- `core/runtime/builtins/builtin_constants.py`
- `core/runtime/builtins/filesystem_helpers.py`
- `core/runtime/builtins/binary_helpers.py`

## File-By-File Migration Map

| Macro_Recorder source | What lives there | ASS target | Migration note |
| --- | --- | --- | --- |
| `packages/app_core/runtime/builtin_macro_calls.py` | Most builtin dispatcher branches and helper logic | [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py) | Short term: port selected branches into ASS runtime. Long term: extract a dedicated ASS builtin dispatcher if needed. |
| `packages/app_core/runtime/runtime_errors.py` | Runtime validation and builtin error text | [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py) | ASS already has this file and should continue extending it as builtin support grows. |
| `packages/app_core/runtime/execution_context.py` | Runtime state, emitted events, host values, host services | [core/runtime/execution_context.py](../../../core/runtime/execution_context.py) | This is the right target for shared runtime-state support used by recovered builtins. |
| `packages/app_core/runtime/builtin_constants.py` | Builtin constants such as `MB_*` and `ID*` | `core/runtime/builtins/builtin_constants.py` | Add only if ASS intentionally recovers `MsgBox`-style support or similar constant-driven host APIs. |
| `packages/app_core/runtime/script_runtime.py` | Runtime shell and builtin wiring patterns | [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py) | Use as integration reference rather than as a wholesale copy source. |

## Migration By Builtin Family

### Playback-First Action Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- [core/playback/playback_events.py](../../../core/playback/playback_events.py)

Includes:

- `Sleep`
- `SendText`
- `KeyPress`
- `SendKeys`
- `HotKey`
- `KeyDown`
- `KeyUp`
- `MouseMove`
- `MouseClick`
- `MouseClickDrag`
- `MouseDrag`
- `MouseDown`
- `MouseUp`
- `MouseWheel`
- `GetMouseMoveSpeed`
- `SetMouseMoveSpeed`

Migration guidance:

- move selected builtin logic into ASS runtime dispatch
- keep emitted events aligned with ASS playback event vocabulary
- avoid reintroducing old runtime event shapes that no longer match ASS

### Diagnostic And Output Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)

Includes:

- `Write`
- `WriteLn`
- `DiagWrite`
- `DiagWriteLn`

Migration guidance:

- these should remain runtime-local behavior
- diagnostic output should keep using the runtime diagnostics logger stream rather than playback output, so it honors diagnostics preferences and appears in the Diagnostics tab, stdout, and log file sinks

### Host-Interaction Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)
- `core/runtime/builtins/builtin_constants.py`

Includes:

- `KeyToggle`
- `MsgBox`
- `PixelGetColor`
- `PixelSearch`

Migration guidance:

- implement through ASS host-service seams where possible
- keep platform-specific behavior out of the core runtime when practical
- only add builtin constants when the related host features are intentionally recovered

### File And Path Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- possible future helper: `core/runtime/builtins/filesystem_helpers.py`

Includes:

- `ReadFile`
- `WriteFile`
- `AppendFile`
- `FileExists`
- `DeleteFile`
- `CreateDir`
- `DirExists`
- `PathExists`
- `PathCombine`
- `PathNormalize`
- `IsPathValid`
- `FileName`
- `DirectoryName`
- `ExtensionName`

Migration guidance:

- defer unless ASS intentionally broadens into utility scripting
- if recovered, consider extracting helper code instead of crowding the runtime dispatcher

### Binary And Encoding Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- possible future helper: `core/runtime/builtins/binary_helpers.py`

Includes:

- `ReadBytes`
- `WriteBytes`
- `AppendBytes`
- `BinaryLength`
- `Hex`
- `FromHex`
- `Base64`
- `FromBase64`
- `Binary`
- `BinaryMid`
- `BinaryToString`

Migration guidance:

- defer unless ASS intentionally expands beyond automation-first scripting
- if recovered, extract helper-heavy logic instead of embedding everything in the main runtime file

### Bitwise And Small Utility Builtins

Primary old source:

- `packages/app_core/runtime/builtin_macro_calls.py`

Primary ASS targets:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)

Includes:

- `Abs`
- `Asc`
- `AscW`
- `Chr`
- `ChrW`
- `BitAnd`
- `BitNot`
- `BitNotUnsigned`
- `BitRotate`
- `BitShift`
- `BitOr`
- `BitXor`

Migration guidance:

- keep the simple active ones inline
- recover deferred ones only if there is real script demand

## Recommended ASS Target Structure

### If builtin scope stays relatively small

These files are enough:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- [core/runtime/builtins/builtin_registry.py](../../../core/runtime/builtins/builtin_registry.py)

### If ASS recovers a broader builtin surface

These additional files should be considered:

- `core/runtime/builtins/builtin_dispatcher.py`
- `core/runtime/builtins/builtin_constants.py`
- `core/runtime/builtins/filesystem_helpers.py`
- `core/runtime/builtins/binary_helpers.py`

This keeps ASS from recreating one oversized builtin file too early.

## Recommended Migration Order

### 1. Recover the strongest playback-first conveniences

Start with:

- `KeyPress`
- `SendKeys`
- `MouseClickDrag`

These are the most natural next builtin recoveries for ASS.

### 2. Pull over the related validation and error text

As each builtin returns, move only the needed validation and error support into:

- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)

### 3. Expand execution-context support only when the builtin family truly needs it

Use:

- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)

for:

- host service support
- host value support
- additional emitted event needs

### 4. Add constants only when recovering host-dialog style features

Only introduce:

- `core/runtime/builtins/builtin_constants.py`

when ASS intentionally recovers things like `MsgBox`.

### 5. Leave file/path/binary families deferred until ASS explicitly wants that broader scripting scope

These should not be revived accidentally just because the old code exists.

## Practical Summary

Most of the old builtin behavior lives in:

- `packages/app_core/runtime/builtin_macro_calls.py`

And most of the ASS migration target belongs in or beside:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)

That is the main builtin migration spine.

## Short Version

If you want the shortest useful mapping:

- old builtin behavior mostly lives in `builtin_macro_calls.py`
- ASS should recover selected builtin logic into [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- shared runtime-state support belongs in [core/runtime/execution_context.py](../../../core/runtime/execution_context.py)
- validation and message support belongs in [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py)
- constants and helper-heavy families should become separate files only when ASS intentionally broadens builtin scope
