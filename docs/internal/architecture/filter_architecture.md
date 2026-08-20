# Filter Architecture

This document defines the target filter architecture for ActionShellScript (ASS).

It describes where filters belong in the phase model, which artifacts they may transform, and how CLI-first filtering should work before a GUI becomes the primary interaction surface.

## Purpose

The filter system exists to support:

- optimization
- simplification
- mouse smoothing
- post-recording cleanup
- interpretation refinement
- explicit document-level transformations

The filter system must not:

- silently mutate authority artifacts
- hide workflow semantics inside the GUI
- collapse multiple workflow stages into one generic filter bucket
- let playback or editor state become an accidental source of truth

## Core principles

### 1. Filters are explicit derived transforms

A filter must always transform one artifact into another derived artifact.

Filters must never silently rewrite an authority source in place.

### 2. Filters are phase-scoped

ASS should not have one giant generic filter layer.

Instead, filters should belong to the workflow stage whose artifact they operate on:

- recording filters
- interpretation filters
- shaping filters
- document filters

### 3. GUI consumes filters; it does not define them

The GUI may:

- list filter profiles
- preview changes
- apply filters intentionally

The GUI must not become the place where filter logic or workflow rules are first implemented.

### 4. Profiles are explicit and stage-targeted

A filter profile must clearly state:

- which stage it targets
- which filters it enables
- what settings it provides

A profile must not ambiguously apply to "whatever is currently loaded."

### 5. Authority remains unchanged

The authority model does not change:

- `RecordingSession` remains authoritative raw recording truth
- `ScriptDocument` remains authoritative editable script truth after conversion

Filters operate on derived representations around those authority points.

## Phase alignment

### Recording phase

Raw recording remains authoritative.

Recording filters may derive a filtered recording result, but they must not silently replace the original `RecordingSession`.

### Interpretation phase

Interpretation filters may refine meaning-bearing events.

This is the correct place for transformations such as:

- detecting that adjacent keystrokes form text input
- refining keyboard meaning
- normalizing ambiguous interpreted actions

### Shaping phase

This is the strongest home for optimization and simplification filters.

Shaping filters are the best fit for:

- mouse smoothing
- action simplification
- delay optimization
- playback-oriented cleanup

### Script generation phase

Script generation should consume either:

- unfiltered shaped actions
- or explicitly filtered shaped actions

Generation must not silently apply hidden filters.

### Script document phase

Document filters operate explicitly on `ScriptDocument`.

These are document-authority transforms such as:

- formatting
- normalization
- script-level simplification

If a filter changes document text, that must be an intentional document workflow.

### Playback phase

Playback may consume filtered derived artifacts, but playback itself must never become the filter authority layer.

### Debugging phase

The debugger should still debug `ScriptDocument` as the authoritative script source.

Debugger behavior must not depend on filtered playback artifacts pretending to be source.

## Filter layers

ASS should use four separate filter layers.

### 1. Recording filters

Input:
- `RecordingSession`

Output:
- derived recording transform result

Good use cases:
- raw input noise cleanup
- trivial mouse jitter cleanup
- dead-time trimming
- duplicate raw-event cleanup

Bad use cases:
- semantic text detection
- script formatting
- playback-only optimization

### 2. Interpretation filters

Input:
- `InterpretedRecording`

Output:
- derived interpreted result

Good use cases:
- text-run detection from adjacent key input
- hotkey normalization
- semantic grouping of meaning-bearing events

This is the correct home for the idea that what looks like single keystrokes may really be text input.

### 3. Shaping filters

Input:
- `ShapedActionSequence`

Output:
- derived shaped-action result

Good use cases:
- optimization
- simplification
- mouse smoothing
- delay cleanup
- action collapse

This is likely the most important first filter layer for ASS.

### 4. Document filters

Input:
- `ScriptDocument`

Output:
- text transform result or a new document version

Good use cases:
- formatting
- normalization
- explicit document-level simplification

These are script-authority transforms and must remain explicit.

## Recommended CLI-first surface

For now, ASS should expose separate commands:

- `ass-filter-recording`
- `ass-filter-interpretation`
- `ass-filter-shaping`
- `ass-filter-document`

This is preferred over a unified `ass-filter` command at the current stage.

Reasons:

- each command makes the target stage explicit
- each command keeps authority boundaries visible
- CLI usage stays clear while the architecture is still stabilizing
- a future GUI can map directly onto stage-specific filtering workflows
- unification can happen later if it becomes genuinely helpful

## Filter profile model

Filter profiles should be stage-specific.

Recommended shape:

```python
@dataclass(frozen=True, slots=True)
class FilterProfile:
    profile_id: str
    target_stage: str
    enabled_filters: tuple[str, ...]
    settings: dict[str, object]
```

Examples:

- `recording_cleanup`
- `text_run_refinement`
- `smooth_mouse`
- `optimize_playback`
- `document_normalize`

Profiles must not cross stages implicitly.

## Filter result model

Each filter application should produce an explicit result object.

Recommended shape:

```python
@dataclass(slots=True)
class FilterResult[T]:
    value: T
    applied_filters: list[str]
    notes: list[str]
```

This helps both CLI and GUI:

- report what changed
- explain which profile ran
- provide user-facing auditability

## File formats

The current CLI filter commands round-trip four explicit artifact formats.
These are intentionally small and stage-specific.

### 1. Recording session JSON

Used by:

- `ass-filter-recording`

Shape:

```json
{
  "session_id": "string",
  "state": "idle|recording|stopped",
  "started_at_ms": 0,
  "stopped_at_ms": 0,
  "events": []
}
```

### 2. Interpreted recording JSON

Used by:

- `ass-filter-interpretation`

Shape:

```json
{
  "artifact_type": "interpreted_recording",
  "schema_version": 1,
  "source_session_id": "string",
  "source_event_count": 0,
  "events": []
}
```

### 3. Shaped action sequence JSON

Used by:

- `ass-filter-shaping`

Shape:

```json
{
  "artifact_type": "shaped_action_sequence",
  "schema_version": 1,
  "source_session_id": "string",
  "source_interpreted_event_count": 0,
  "actions": []
}
```

### 4. Script document text

Used by:

- `ass-filter-document`

Shape:

```text
plain ASS script text in UTF-8
```

Notes:

- recording session JSON stays compatible with the raw `--save-raw` shape
- derived JSON artifacts include `artifact_type` and `schema_version`
- the document filter writes normalized UTF-8 text directly to `.ass`

### Examples

Recording session JSON:

```json
{
  "session_id": "session-1",
  "state": "stopped",
  "started_at_ms": 100,
  "stopped_at_ms": 250,
  "events": [
    { "type": "mouse_move", "x": 10, "y": 10, "timestamp_ms": 120 }
  ]
}
```

Interpreted recording JSON:

```json
{
  "artifact_type": "interpreted_recording",
  "schema_version": 1,
  "source_session_id": "session-1",
  "source_event_count": 1,
  "events": [
    { "type": "text", "text": "hi", "timestamp_ms": 120 }
  ]
}
```

Shaped action sequence JSON:

```json
{
  "artifact_type": "shaped_action_sequence",
  "schema_version": 1,
  "source_session_id": "session-1",
  "source_interpreted_event_count": 1,
  "actions": [
    { "type": "text", "text": "hi", "timestamp_ms": 120 }
  ]
}
```

Script document text:

```text
Func Demo()
    CallThing(1, 2)
EndFunc
```

## Directory structure

Recommended structure:

```text
core/
  filtering/
    filter_profile.py
    filter_result.py
    filter_registry.py

    recording/
      recording_filter.py
      recording_filter_pipeline.py
      jitter_filter.py
      idle_trim_filter.py

    interpretation/
      interpretation_filter.py
      interpretation_filter_pipeline.py
      text_run_filter.py
      hotkey_normalization_filter.py

    shaping/
      shaped_action_filter.py
      shaped_action_filter_pipeline.py
      mouse_smoothing_filter.py
      delay_optimization_filter.py
      action_simplification_filter.py

    documents/
      document_filter.py
      document_filter_pipeline.py
      document_normalization_filter.py

application/
  recording_filter_service.py
  interpretation_filter_service.py
  shaping_filter_service.py
  document_filter_service.py
```

This keeps filtering:

- out of the GUI
- out of runtime execution semantics
- out of playback authority
- aligned with the existing phase model

## Recommended first implementation order

### 1. Shaping filters

Start here first.

This is the best place for:

- optimization
- simplification
- mouse smoothing

### 2. Interpretation filters

Add interpretation refinement second.

This is the right place for:

- text-run detection
- keyboard meaning refinement
- semantic grouping improvements

### 3. CLI commands

Add the four stage-specific filter commands after the first real filter services exist.

### 4. GUI integration

Once the filter services and CLI surfaces are stable, add GUI support for:

- listing profiles
- previewing changes
- applying filters intentionally

## Anti-goals

ASS should avoid:

- one giant generic `ass-filter` workflow too early
- GUI-owned filter semantics
- in-place mutation of `RecordingSession`
- hidden automatic filtering inside generation
- hidden automatic filtering inside playback
- debugger behavior based on filtered playback artifacts instead of `ScriptDocument`

## Initial success criteria

The filter architecture is on track when:

- filters are implemented in core/application, not in the GUI
- stage-specific CLI commands exist
- shaping filters support simplification and mouse smoothing
- interpretation filters support text-oriented refinement
- profiles are explicit and stage-targeted
- authority artifacts remain authoritative and unchanged unless explicitly replaced by a later workflow
