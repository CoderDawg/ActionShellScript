# Phase-7 Completion Record

Phase 7 is complete. This document records the finished debugger slice in ActionShellScript (ASS) and the boundary that the implementation now follows. The debugger UI lives in the desktop sidebar Debugger, while the editor remains the sole source surface.

## Goal

The repo can run a `ScriptDocument` through `ScriptRuntime` with `RuntimeDebugHooks`, produce a live `DebugSession`, and surface debug events and state through `ass-debug`.

## Current Phase-7 Scope

Phase 7 is authority-first and runtime-backed.

In scope:

- debug a `ScriptDocument` through `ass-debug`
- initialize runtime execution with debugger hooks
- map runtime callbacks into `DebugSession`
- breakpoint, step, continue, and resume behavior
- debug events and state snapshots surfaced to the CLI
- source-accurate line mapping from the document text
- live inspection through the sidebar Debugger without duplicating source in a second debug tab

Still deferred to later work:

- desktop debugger controls and visual state panels beyond the sidebar Debugger
- debugger truth reconstructed from playback artifacts
- treating playback metadata as debugger authority

`DebugSession` and the runtime debugger hooks remain the live debug authority throughout phase 7.

## Completed Debugger Surface

- `ass-debug script path\to\document.ass`
- `ass-debug script path\to\document.ass --step`
- `ass-debug script path\to\document.ass --ass-play`
- `ass-debug script path\to\document.ass --breakpoint 12`
- `ass-debug script path\to\document.ass --step --breakpoint 12`

For SendKeys-heavy scripts, `--ass-play` keeps printable characters flowing as key taps instead of text events. That matters when the target expects individual keystrokes, such as a script that types into DOSBox or another emulator that reacts differently to pasted text.

The CLI starts from script authority, attaches runtime debugger hooks, and prints the resulting debug events instead of rebuilding debug truth from playback or UI state.

## Completed Contracts

- `ScriptDocument` remains the authoritative source text for debugging and editing.
- `ScriptRuntime` executes with debugger hooks attached.
- `RuntimeDebugHooks` translate runtime callbacks into debug-session notifications.
- `DebugSession` is authoritative for live debug runtime state.
- `DebugController` owns breakpoints, stepping, pause/resume state, and snapshots.
- `DebugEvent` is the CLI-facing event vocabulary for the live run.
- `DebugState` snapshots reflect the current live debugger view.
- CLI output is derived from the live debug session, not from playback caches.
- The debug path is explicit: `ScriptDocument -> ScriptRuntime -> RuntimeDebugHooks -> DebugSession -> CLI`.
- The desktop Debugger sidebar reads from the same live debug session and editor source without owning a separate source surface.

## Exit Criteria Met

- `ass-debug` exists as a public entry point.
- The debugger path starts from `ScriptDocument`.
- Runtime callbacks flow through debugger hooks into `DebugSession`.
- Breakpoints and stepping are exercised by the live debugger path.
- Debug output is surfaced from the live run.
- The docs explain the debugger boundary clearly.
- The editor remains the only place where source text is edited and displayed as the source of truth.

## Related Docs

- [Docs Index](../index.md)
- [Phase 7 Debugger Boundary](phase_7_debugger_boundary.md)
- [Phase 6 Checklist](phase_6_checklist.md)
