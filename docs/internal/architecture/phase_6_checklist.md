# Phase-6 Completion Record

Phase 6 is complete. This document records the finished playback slice in ActionShellScript (ASS) and the boundary that the implementation now follows.

## Goal

The repo explicitly builds and executes a `PlaybackPlan` from either a `RecordingSession` or a `ScriptDocument`, keeps playback fully derived from the active authority source, and provides a real end-to-end playback workflow.

## Current Phase-6 Scope

Phase 6 is authority-first.

In scope:

- explicit playback source selection
- playback planning from recording and script authority
- playback execution through preview and live executors
- playback results and service orchestration
- one real playback CLI and one deterministic live demo path

Still deferred to later phases:

- debugger-specific stepping and live debug session behavior
- reconstructing script authority from playback artifacts
- UI playback controls and visual transport widgets
- using playback caches as truth

`PlaybackPlan` and `PlaybackResult` remain derived artifacts throughout phase 6.

For the document workflow, the `ScriptDocument` is the source of truth after conversion and the GUI must treat it as the authoritative editable artifact.

## Completed Playback Surface

- `ass-cli play recording path\to\session.json`
- `ass-cli play recording path\to\session.json --mode preview`
- `ass-cli play script path\to\document.ass`
- `ass-cli play script path\to\document.ass --mode live --demo-live --ass-play`

The CLI never guesses the active source. The caller chooses either `recording` or `script`, then the command derives a playback plan from that authority and executes it in `preview` or `live` mode.

For a deterministic live walkthrough during development or docs testing, `--demo-live` with `--mode live` routes through an in-memory live host and prints the captured host calls instead of touching real mouse or keyboard input. Add `--ass-play` when you want the script walkthrough to exercise SendKeys key taps instead of text events.

## Completed Contracts

- `RecordingSession` remains authoritative for recording-source playback.
- `ScriptDocument` remains authoritative for script-source playback.
- `PlaybackPlan` is always derived from one explicit source.
- `PlaybackResult` is always derived execution output.
- `PlaybackSummary` also carries derived console output for script playback consumers.
- Playback caches, previews, and executor state never become authority.
- `core/playback/builders/from_recording_builder.py` builds from `RecordingSession` through interpretation and shaping.
- `core/runtime/script_runtime.py` compiles real executable playback events from script text.
- `core/playback/builders/from_script_builder.py` builds a working plan from `ScriptDocument`.
- `core/playback/executors/input_executor.py` is implemented through `LiveInputExecutor`.
- `preview_input_executor.py` remains the non-destructive preview/test path.
- `PlaybackRequest` is part of the real service flow.
- `PlaybackMode` selects preview vs live execution.
- `repeat_count` is applied in engine execution.
- `--step` pauses before each playback event, `--delay-ms` slows playback down for inspection, and `--settle-ms` adds an explicit mouse-settle delay in live mode when needed.
- Playback plans preserve source kind and source id.
- Converted recording workflows end in a `ScriptDocument`, which is the authoritative document for editing and playback-from-document.
- Executor failures surface through `PlaybackResult`.
- Script-origin `Write` and `WriteLn` output is available through `PlaybackSummary.console_output` and `PlaybackResult.console_output`.
- `PlaybackPlan.events` uses a stricter playback event contract than plain dicts.
- Recording-source and script-source plans converge on the same executable playback vocabulary.

## Exit Criteria Met

- There is at least one real playback entry path.
- Recording-source playback planning is stable and intentional.
- Script-source playback is operational.
- A concrete live executor exists alongside preview execution.
- `PlaybackRequest` and `PlaybackMode` are part of the real playback flow.
- Playback planning and execution are tested.
- At least one end-to-end phase-6 proof path exists.
- The executable playback event contract is explicit.
- Playback pacing controls are documented and testable.
- The docs explain the playback boundary clearly.

## Related Docs

- [Docs Index](../index.md)
- [Phase 6 Playback Boundary](phase_6_document_boundary.md)
- [Phase 5 Checklist](phase_5_checklist.md)
