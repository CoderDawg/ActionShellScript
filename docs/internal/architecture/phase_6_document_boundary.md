# Phase 6 Playback Boundary

Phase 6 is the point where playback becomes an explicit derived execution slice.

Its job is intentionally narrow:

- consume either a `RecordingSession` or a `ScriptDocument`
- derive a `PlaybackPlan` from one explicit authority source
- execute the derived plan in preview or live mode
- keep playback state, previews, and executor output non-authoritative
- preserve script-origin `console_output` as derived playback output, not authority

Phase 6 does not create new source authority.

- `RecordingSession` remains authoritative for recording-source playback.
- `ScriptDocument` remains authoritative for script-source playback.
- When a recording is converted into a script document in the GUI or CLI, the resulting `ScriptDocument` becomes the authoritative script artifact for that workflow.
- `PlaybackPlan` stays derived.
- `PlaybackResult` stays derived.
- `PlaybackSummary` can expose derived console output for callers that only need summary data.

## Playback and Derived Output

Playback plans are derived execution artifacts, not source authority.

A valid `PlaybackPlan` may contain:

- executable playback events
- `console_output`
- zero executable playback events

The absence of executable events does not by itself make the plan invalid. If a script produces only console output, that output still belongs to the playback result and may be surfaced by consumers.

`DiagWrite` and `DiagWriteLn` are not part of the playback transcript. They emit structured diagnostic events that follow the diagnostics logger configuration, so they appear in the Diagnostics tab, log file, and standard output only when diagnostics are enabled.

## UI Contract for Playback

Consumers of playback plans must not infer workflow failure solely from `event_count == 0`.

The desktop application must treat playback as a derived execution step from the current authority source, not as a validation rule that rejects plans with no OS-level replay actions.

For document-based workflows, the `ScriptDocument` is the source of truth that the GUI edits, saves, analyzes, formats, and sends to script playback.

## Supported Results

Playback execution may legitimately produce:

- a non-empty event stream
- console output with no replay events
- a fully empty result only when the source truly produces no derived playback or output

## Live Demo Path

The deterministic live demo path is part of the completed phase-6 surface:

```powershell
ass-cli play script .\generated.ass --mode live --demo-live --ass-play
```

That path uses an in-memory live host so the docs and tests can show the live execution flow without touching the real desktop.

## Playback Contract

Playback executors consume the typed playback event contract from `core/playback/playback_events.py`.

The event vocabulary is shared by both recording-source and script-source planning so the executor layer sees one intentional shape instead of loose dicts.

## Related Docs

- [Docs Index](../index.md)
- [Architecture Index](index.md)
