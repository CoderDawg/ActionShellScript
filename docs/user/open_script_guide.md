# Open Script Guide

This guide shows how to use `ass-open-script` to convert a raw session JSON file into a phase-5 `ScriptDocument` using the desktop Recording to Script Conversion flow.

If you want to exercise phase-6 playback from the converted document, use `ass-cli play script .\document.ass --mode live --demo-live --ass-play` to run the deterministic live demo path without controlling the real desktop. If the script only writes output, `ass-cli play` will show console output and diagnostics but will not move the mouse or press keys.

## What `ass-open-script` Does

`ass-open-script` converts a raw session JSON file into a `ScriptDocument`:

1. load raw session JSON
2. choose a conversion mode
3. create a `ScriptDocument`
4. run parse, diagnostics, and formatting services against `ScriptDocument.text`, including semantic checks that flag unsupported function calls like `SleepX(1000)`

`ass-open-script` supports the same two explicit conversion modes exposed by the desktop preference:

- `promote_generated` keeps the current interpret -> shape -> generate -> convert path.
- `direct_import` performs a minimal translation from `RecordingSession` into `ScriptDocument`.

In both modes, the resulting `ScriptDocument` becomes the editable authority.

## Basic Usage

Convert a saved session into a `ScriptDocument` and print the authoritative text:

```powershell
ass-open-script .\session.json
```

Import a recording directly into a `ScriptDocument`:

```powershell
ass-open-script .\session.json --recording-conversion-mode direct_import
```

Use one of the sample fixtures:

```powershell
ass-open-script .\samples\hotkey_copy.json
ass-open-script .\samples\drag.json
```

Write the authoritative document text to disk:

```powershell
ass-open-script .\samples\drag.json --output .\authoritative.ass
```

## Useful Options

Show diagnostics for the converted document:

```powershell
ass-open-script .\session.json --show-diagnostics
```

Show a formatted preview without mutating the document:

```powershell
ass-open-script .\session.json --show-formatted
```

Show both services together:

```powershell
ass-open-script .\session.json --show-diagnostics --show-formatted
```

Pass through the same generation controls used by `ass-generate` when using the default generated conversion path:

```powershell
ass-open-script .\session.json --no-header-comments --no-script-delays
```

## What The Output Means

The command prints summary lines for:

- source session id
- shaped action count or recording event count, depending on conversion mode
- document id
- document version
- document line count
- document dirty state
- parsed statement count
- diagnostics count

The `Authoritative document text` section is the resulting `ScriptDocument.text`.

If you also request `--show-formatted`, the `Formatted preview` section is only a derived formatting result. It does not overwrite the document automatically.

## Saving Converted Scripts

When `ass-open-script --output` or the desktop save flow writes a converted `.ass` file, it also writes a sibling `.ass.meta.json` file if the `ScriptDocument` still has provenance fields.

- The `.ass` file keeps the short provenance header for the conversion route and the main-window exclusion setting.
- The `.ass.meta.json` sidecar keeps the full provenance payload:
  - `source_session_id`
  - `source_action_count`
  - `generated_from_recording`
  - `recording_conversion_route`
  - `source_capture_excluded_main_window`
- Keep the `.ass` file and `.ass.meta.json` file together when moving, syncing, or checking in converted scripts.
- If a document has no provenance fields left, no sidecar file is written.

## Authority Model Reminder

Before conversion:

- `RecordingSession` is capture provenance, not script authority
- `GeneratedScript` is rebuildable output in the generated conversion path
- generation text is not editable authority

After conversion:

- `ScriptDocument` is the editable authority and source of truth for this workflow
- parse reads document text
- diagnostics read document text and now include semantic checks for unsupported function calls
- formatting reads document text

## Related Docs

- [Docs Index](../index.md)
