# Phase 7 Debugger Boundary

Phase 7 is the debugger slice where script execution becomes inspectable through runtime hooks and a live `DebugSession`.

The debugger UI now lives in the desktop app's left sidebar as the Debugger panel. The editor remains the sole source surface, and all breakpoint editing and source navigation happen there.

Its job is intentionally narrow:

- start from an editable `ScriptDocument`
- run that document through `ScriptRuntime`
- bridge runtime callbacks through `RuntimeDebugHooks`
- record live debugger truth in `DebugSession`
- surface live debug state through the Debugger sidebar and the editor source view

Phase 7 does not derive debugger truth from playback artifacts.

- `ScriptDocument` remains authoritative for source text.
- `DebugSession` remains authoritative for live debug state.
- `RuntimeDebugHooks` are the bridge between runtime execution and debugger state.
- the Debugger sidebar is presentation and control only; it never becomes source truth.

## Live Debug Path

The debugger entry point is the desktop Debugger sidebar, which is driven by the live debug session:

```powershell
ass-debug script .\generated.ass --step --breakpoint 12
ass-debug script .\generated.ass --step --breakpoint 12 --ass-play
```

That path loads the script document, builds the debug controller and runtime hooks, runs `ScriptRuntime`, and updates the Debugger sidebar while keeping the editor as the source surface.

Use `--ass-play` when the script is SendKeys-heavy and needs printable characters to arrive as key taps instead of text events. For example, a debugger walkthrough that types into DOSBox or another emulator should use `--ass-play` so the target receives the same keystroke sequence it expects from manual typing.

## Debug Contract

The live debug contract is centered on document source mapping, editor source, and session state:

- `SourceMap` identifies debuggable source lines.
- `DebugController` owns breakpoints, stepping mode, pause/resume, and snapshots.
- `RuntimeDebugHooks` relay runtime callbacks into the controller.
- `DebugSession` stores the live debugger session state.
- the editor shows the source text that breakpoints and pause locations refer to.

## Related Docs

- [Docs Index](../index.md)
