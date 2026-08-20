# CLI Cheat Sheet

This is a compact reference for the public `ass-*` commands.

## Phase 1: Record

| Command | Key arguments | What it does |
|---|---|---|
| `ass-record` | `--session-id`, `--suppress`, `--no-mouse-moves`, `--no-mouse-buttons`, `--no-mouse-wheel`, `--no-keyboard`, `--mouse-move-threshold`, `--stop-hotkey`, `--debug-stop-hotkey`, `--save-raw <path>`, `--no-save`, `--force` | Records live input and prints a recording summary. Default stop chord is `Shift+Esc`; `--stop-hotkey` also accepts `|`-separated alternates like `Shift+Esc|Ctrl+C`. Use `--save-raw` to write raw session JSON, or pass `--no-save` for the older in-memory-only behavior. |
| `ass-record-interpret` | Same recording arguments as `ass-record`, plus `--show-events` and the interpretation tuning flags below | Records live input, writes raw session JSON with `--save-raw <path>`, and immediately interprets it. |

## Phase 2: Interpret

| Command | Key arguments | What it does |
|---|---|---|
| `ass-interpret` | `--input <path>` defaults to `.\session.json`, `--show-events`, `--click-max-move-distance-px`, `--double-click-max-interval-ms`, `--double-click-max-distance-px`, `--double-click-max-pause-ms`, `--double-click-max-inter-click-move-distance-px`, `--drag-min-distance-px`, `--drag-min-duration-ms` | Interprets a raw session JSON file into phase-2 meaning events. |

## Phase 3: Shape

| Command | Key arguments | What it does |
|---|---|---|
| `ass-shape` | `--input <path>` defaults to `.\session.json`, `--show-actions`, interpretation tuning flags, `--no-delays`, `--min-delay-ms`, `--max-delay-ms`, `--no-collapse-delays`, `--no-mouse-moves`, `--only-click-positions`, `--no-collapse-mouse-moves`, `--no-collapse-clicks`, `--click-collapse-distance-px`, `--click-collapse-max-duration-ms`, `--no-collapse-text-input`, `--keyboard-output-style` | Interprets a raw session JSON file and shapes it into phase-3 actions. |

## Phase 4: Generate

| Command | Key arguments | What it does |
|---|---|---|
| `ass-generate` | `--input <path>` defaults to `.\session.json`, `--output <path>`, `--force`, `--no-header-comments`, `--no-source-summary`, `--no-script-delays`, `--emit-unsupported-comments`, `--line-ending`, interpretation tuning flags, shaping flags | Generates phase-4 script output from a raw session JSON file. |

## Phase 5: Open Script

| Command | Key arguments | What it does |
|---|---|---|
| `ass-open-script` | `--input <path>` defaults to `.\session.json`, `--output <path>`, `--force`, `--recording-conversion-mode`, `--show-diagnostics`, `--show-formatted`, `--no-header-comments`, `--no-source-summary`, `--no-script-delays`, `--emit-unsupported-comments`, `--line-ending`, interpretation tuning flags, shaping flags | Converts a raw session JSON file into an authoritative `ScriptDocument` through the same Recording to Script Conversion flow used by the desktop preference. Default mode still uses the generated conversion path, and saved converted scripts can include a sibling `.ass.meta.json` provenance file. |

## Phase 6: Play

| Command | Key arguments | What it does |
|---|---|---|
| `ass-cli play` | Source subcommand: `recording` or `script`; shared options: `--mode`, `--repeat`, `--step`, `--delay-ms`, `--settle-ms`, `--show-events`, `--demo-live`, `--ass-play`; recording-only option: `--recording-conversion-mode`; `recording` defaults to `.\session.json` | Replays a raw recording session or executes a script document. `recording` can stay on the raw playback path or be converted into a `ScriptDocument` first; `script` runs the script runtime and may produce console output, diagnostics, and playback events. |

## Phase 7: Debug

| Command | Key arguments | What it does |
|---|---|---|
| `ass-debug` | Source subcommand: `script`; options: `--step`, `--breakpoint`, `--ass-play` | Runs a `ScriptDocument` under the debugger and prints debug state. `--ass-play` keeps printable `SendKeys` characters as key taps instead of text events when the script needs per-keystroke delivery. |

## Standalone Launchers

| Command | Key arguments | What it does |
|---|---|---|
| `ass-help` | `docs_path` | Opens the standalone help browser for bundled docs and can open a specific docs file on startup. |

## Filter Commands

| Command | Key arguments | What it does |
|---|---|---|
| `ass-filter-recording` | `--input <path>` defaults to `.\session.json` and is optional with `--list-profiles`; shared options: `--profile`, `--output`, `--list-profiles` | Applies a phase-1 recording filter profile. |
| `ass-filter-interpretation` | `--input <path>` defaults to `.\session.json` and is optional with `--list-profiles`; shared options: `--profile`, `--output`, `--list-profiles` | Applies a phase-2 interpretation filter profile. |
| `ass-filter-shaping` | `--input <path>` defaults to `.\session.json` and is optional with `--list-profiles`; shared options: `--profile`, `--output`, `--list-profiles` | Applies a phase-3 shaping filter profile. |
| `ass-filter-document` | `--input <path>` is optional with `--list-profiles`; shared options: `--profile`, `--output`, `--list-profiles` | Applies a phase-5 document filter profile. |

## Shared Option Groups

| Group | Options |
|---|---|
| Interpretation tuning | `--click-max-move-distance-px`, `--double-click-max-interval-ms`, `--double-click-max-distance-px`, `--double-click-max-pause-ms`, `--double-click-max-inter-click-move-distance-px`, `--drag-min-distance-px`, `--drag-min-duration-ms` |
| Shaping controls | `--no-delays`, `--min-delay-ms`, `--max-delay-ms`, `--no-collapse-delays`, `--no-mouse-moves`, `--only-click-positions`, `--no-collapse-mouse-moves`, `--no-collapse-clicks`, `--click-collapse-distance-px`, `--click-collapse-max-duration-ms`, `--no-collapse-text-input`, `--keyboard-output-style` |
| Generation controls | `--output`, `--no-header-comments`, `--no-source-summary`, `--no-script-delays`, `--emit-unsupported-comments`, `--line-ending` |

Converted `.ass` files that still have provenance should be kept together with their sibling `.ass.meta.json` files when you move, sync, or check in the generated scripts.
