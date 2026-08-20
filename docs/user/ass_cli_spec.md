# `ass-cli` Front-End Spec

`ass-cli` is a thin, uniform front-end over the existing `ass-*` commands. The goal is to give users one consistent command shape while keeping the underlying commands intact.

## Goals

- Provide one entry point for common workflows.
- Use one consistent invocation form for every subcommand.
- Hide backend command quirks behind a stable user-facing contract.
- Keep the existing `ass-*` commands available for direct use.

## Top-Level Shape

```powershell
ass-cli <subcommand> [--input PATH] [--output PATH] [shared flags...]
```

Rules:

- `--input` is the standard file input flag, and raw-session consumers default to `.\session.json` when it is omitted.
- `--output` is the standard file output flag for derived artifacts.
- `--force` is the standard overwrite flag.
- Shared flags are inherited by subcommands that need them.
- Subcommands define behavior; the front-end only normalizes usage.

## Shared Flag Groups

### Recording Capture

Used by `record` and `record-interpret`.

- `--session-id <id>`
- `--suppress`
- `--no-mouse-moves`
- `--no-mouse-buttons`
- `--no-mouse-wheel`
- `--no-keyboard`
- `--mouse-move-threshold <px>`
- `--stop-hotkey <chord>|<chord>[|...]`
- `--debug-stop-hotkey`
- `--save-raw <path>`
- `--no-save`
- `--force`

The default recording stop chord remains `Shift+Esc`. `--stop-hotkey` accepts `|`-separated alternate chords, so `Shift+Esc|Ctrl+C` lets either chord stop recording in a single workflow.

### Interpretation Tuning

Used by `interpret`, `record-interpret`, `shape`, `generate`, and `open-script`.

- `--click-max-move-distance-px <n>`
- `--double-click-max-interval-ms <n>`
- `--double-click-max-distance-px <n>`
- `--double-click-max-pause-ms <n>`
- `--double-click-max-inter-click-move-distance-px <n>`
- `--drag-min-distance-px <n>`
- `--drag-min-duration-ms <n>`

### Shaping Controls

Used by `shape`, `generate`, and `open-script`.

- `--no-delays`
- `--min-delay-ms <n>`
- `--max-delay-ms <n>`
- `--no-collapse-delays`
- `--no-mouse-moves`
- `--only-click-positions`
- `--no-collapse-mouse-moves`
- `--no-collapse-clicks`
- `--click-collapse-distance-px <n>`
- `--click-collapse-max-duration-ms <n>`
- `--no-collapse-text-input`
- `--keyboard-output-style <structured|text>`

### Generation Controls

Used by `generate` and `open-script`.

- `--output <path>`
- `--no-header-comments`
- `--no-source-summary`
- `--no-script-delays`
- `--emit-unsupported-comments`
- `--line-ending <lf|crlf>`
- `--force`

### Playback Controls

Used by `play`.

- `recording <path>` or `script <path>`
- `--mode <preview|live>`
- `--repeat <n>`
- `--step`
- `--delay-ms <n>`
- `--settle-ms <n>`
- `--show-events`
- `--demo-live`

### Debugger

Used by `debug`.

- `--input <path>`
- `--step`
- `--breakpoint <line>` repeated as needed

### Filter Controls

Used by `filter-recording`, `filter-interpretation`, `filter-shaping`, and `filter-document`.

- `--input <path>`
- `--profile <name>`
- `--output <path>`
- `--list-profiles`

## Subcommands

| Subcommand | Required flags | Optional flags | Purpose |
|---|---|---|---|
| `record` | None | Recording capture | Record live input and write raw session JSON with `--save-raw .\session.json`. Use `--no-save` to restore the old in-memory-only behavior. |
| `interpret` | `--input <path>` optional, default `.\session.json` | Interpretation tuning | Interpret a raw session into phase-2 events. |
| `record-interpret` | None | Recording capture, `--show-events`, interpretation tuning | Record live input, write raw session JSON with `--save-raw .\session.json`, and immediately interpret it. |
| `shape` | `--input <path>` optional, default `.\session.json` | `--show-actions`, interpretation tuning, shaping controls | Interpret a source artifact and shape it into phase-3 actions. |
| `generate` | `--input <path>` optional, default `.\session.json` | `--output <path>`, generation controls, interpretation tuning, shaping controls | Generate phase-4 script output from a source artifact. |
| `open-script` | `--input <path>` optional, default `.\session.json` | `--output <path>`, `--recording-conversion-mode <promote_generated|direct_import>`, `--show-diagnostics`, `--show-formatted`, generation controls, interpretation tuning, shaping controls | Convert a source recording into an authoritative `ScriptDocument` using the desktop Recording to Script Conversion flow and run document services. The default path still uses the generated conversion path. When the converted script still has provenance, writing it also writes a sibling `.ass.meta.json` file. |
| `play` | `recording <path>` or `script <path>`; `recording` defaults to `.\session.json` | Playback controls, `--recording-conversion-mode <promote_generated|direct_import>` on `recording` | Build and execute playback from a raw recording session or a script authority. For `recording`, the default path uses the raw recording playback pipeline, and the optional conversion mode can first turn the recording into a `ScriptDocument` before playback. For `script`, the runtime executes the script and may emit console output, diagnostics, and playback events. Only playback events drive mouse or keyboard input in `--mode live`. |
| `debug` | `--input <path>` | `--step`, `--breakpoint <line>` | Run an authoritative `ScriptDocument` under the debugger and print debug state. |
| `filter-recording` | `--profile <name>` unless `--list-profiles`; `--input <path>` defaults to `.\session.json` | `--output <path>`, `--list-profiles` | Apply a recording filter profile. |
| `filter-interpretation` | `--profile <name>` unless `--list-profiles`; `--input <path>` defaults to `.\session.json` | `--output <path>`, `--list-profiles` | Apply an interpretation filter profile. |
| `filter-shaping` | `--profile <name>` unless `--list-profiles`; `--input <path>` defaults to `.\session.json` | `--output <path>`, `--list-profiles` | Apply a shaping filter profile. |
| `filter-document` | `--profile <name>` unless `--list-profiles` | `--input <path>`, `--output <path>`, `--list-profiles` | Apply a document filter profile. |

## Related Launchers

| Launcher | Purpose |
|---|---|
| `ass-help` | Launch the standalone help browser for bundled docs. The legacy `ass-record` dispatcher also exposes this as the `help` command. |

## Examples

```powershell
ass-cli record --save-raw .\session.json
ass-cli record --no-save
ass-cli record-interpret --save-raw .\session.json
ass-cli interpret
ass-cli shape --show-actions
ass-cli generate --output generated.ass
ass-cli open-script --output authoritative.ass
ass-cli open-script --recording-conversion-mode direct_import
ass-cli play recording --mode preview
ass-cli play script generated.ass --mode live --demo-live --ass-play
ass-cli debug --input generated.ass --step
ass-cli filter-recording --profile clean
```

For shorter onboarding examples, see the [ass-cli Quickstart](ass_cli_quickstart.md).

## Script Document Sidecar Contract

Converted `.ass` files can be paired with a sibling `.ass.meta.json` provenance file when the saved `ScriptDocument` still has provenance fields.

- The `.ass` body keeps the short human-readable provenance header:
  - `recording_conversion_route`
  - `source_capture_excluded_main_window`
- The `.ass.meta.json` sidecar keeps the full provenance payload:
  - `source_session_id`
  - `source_action_count`
  - `generated_from_recording`
  - `recording_conversion_route`
  - `source_capture_excluded_main_window`
- Keep the `.ass` file and `.ass.meta.json` file together when moving, syncing, or checking in converted scripts.
- If a document has no provenance fields left, no sidecar file is written.

## Notes

- The front-end should translate into the existing command modules rather than replacing them.
- `play` is the one command that needs an explicit authority choice because it can execute from either a recording or a script, so the source kind comes before the source path.
- `script` playback is script execution, not automatically desktop automation. If the script only writes text, `ass-cli play` will show console output and diagnostics but there will be no mouse or keyboard actions to dispatch.
- The backend commands can stay as-is initially; this spec is about the user-facing entry point.

For the current `Struct` and DLL interop surface, see [Structs and DLL Interop](structs_and_dlls.md).
