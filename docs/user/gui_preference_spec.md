# GUI Preference Spec: Recording to Script Conversion

This spec defines the desktop preference that mirrors the CLI recording conversion mode.
It is about how a stopped recording becomes a `ScriptDocument` in the GUI.

## Goal

The GUI must not leave `RecordingSession` and `ScriptDocument` feeling like competing sources of truth.
The capture session is raw input provenance, and the resulting `ScriptDocument` is the only editable authority for the script workflow.

## Preference Name

- Setting key: `recording_conversion_mode`
- Display label: `Recording to Script Conversion`
- Placement: `Recording` preferences page

## Values

- `promote_generated`
- `direct_import`

## Default

- Default value: `promote_generated`

This preserves the current behavior:

1. record input
2. interpret it
3. shape it
4. generate script text
5. promote that generated text into a `ScriptDocument`

## Behavior

When a recording stops in the desktop app, the preference determines how the app creates the new `ScriptDocument`.

### `promote_generated`

- Keep the existing recording pipeline.
- Convert the `RecordingSession` through interpretation, shaping, and generation.
- Promote the generated script into a `ScriptDocument`.
- Make that `ScriptDocument` the active editable document in the workspace.

### `direct_import`

- Skip the interpretation, shaping, and generation pipeline for the conversion step.
- Create a new `ScriptDocument` directly from the `RecordingSession` with minimal translation.
- Preserve recording provenance on the document.
- Make the imported `ScriptDocument` the active editable document in the workspace.

## Authority Rule

Both values must end in the same authority model:

- `RecordingSession` remains capture provenance only.
- `ScriptDocument` becomes the single source of truth after conversion.
- The editor, save flow, analysis flow, formatting flow, and playback-from-document flow all read and write the `ScriptDocument`.

The desktop preferences UI uses the same snapshot-based dirty-state model for restore and save behavior:

- restore-defaults applies the section's canonical defaults and then recomputes dirty state from the resulting settings snapshot
- section badges and the footer dirty indicator are derived from the same canonical snapshot comparison
- hotkey changes can be temporarily conflicted while editing, but save-time validation still rejects duplicate shortcuts
- the Hotkeys page includes the debugger step, continue, and stop shortcuts alongside the existing workspace bindings
- the diagnostics-tab visibility toggle stays synchronized between the Workspace page and the Diagnostics page so both views edit the same setting
- the Workspace page also owns the summary sidebar placement, hidden-tab strip collapse default, Analysis tab visibility, formatted preview tab visibility, raw recordings tab visibility, and Diagnostics tab visibility
- the Debug page owns the `Open Run when paused` behavior so execution switches to the Run Sidebar automatically after a pause

## Recording Exclusion

The `Exclude main window during recording` checkbox is for the common "record while the app is open" workflow.
When it is enabled, the recorder ignores the ActionShellScript workbench window itself, so clicks, focus changes, and other interactions with the recorder UI do not get captured as part of the target session.

That setting is not preferences-only metadata. It is surfaced again in the document status summary so the active `ScriptDocument` can show whether it came from a recording that excluded the main window.
The landing page in the built-in help browser also calls out the setting, so users can find the behavior from the documentation entry point instead of having to infer it from the checkbox label alone.

The desktop preferences pages are split by ownership:

- `General` owns workspace startup behavior, including restoring the last opened workspace and showing the preview tab
- `Appearance` owns the `Editor`, `Style`, `Formatting`, and `Dirty State` tabs for editor styling, script formatting, dirty-indicator styling, and fonts
- `Runtime` owns the mouse-movement curve editor, preview toggle, and step controls for runtime-backed execution, and the editor switches between a side-by-side and stacked layout as the window narrows
- `Files` owns the raw-recording, converted-script, and diagnostic-log paths

## Suggested UI Copy

Checkbox label:

- `Exclude main window during recording`

Preference label:

- `Recording to Script Conversion`

Option labels:

- `Promote Generated Script`
- `Direct Import`

Helper text:

- `Choose how the desktop app turns a finished recording into the active script document.`
- `When enabled, the recorder ignores the workbench window itself so you only capture the target app.`

## Persistence

The value should live in the desktop settings bundle so it survives app restarts.

If the GUI later exposes a single shared settings model for CLI and desktop defaults, this preference can also act as the desktop default for `ass-open-script` and `ass-cli play recording`, but that is optional and not required by this spec.

## Acceptance Criteria

- The preferences dialog exposes the conversion mode in the `Recording` section.
- The saved setting defaults to `promote_generated`.
- Switching to `direct_import` makes the next recorded result load as a directly imported `ScriptDocument`.
- Switching back to `promote_generated` restores the current generated conversion path.
- The active document after conversion is always a `ScriptDocument`.
- No GUI flow treats `RecordingSession` as editable script authority after conversion.

## Desktop Table API

The preferences dialog now uses the reusable desktop table API for some table-based UI, including the Hotkeys table and its shortcut editor. Implementation notes for that work live in [apps/desktop/table_api/README.md](../../apps/desktop/table_api/README.md).
