# Recommended Diagnostic Logging Map

This document identifies the files in ActionShellScript (ASS) where targeted diagnostic logging would provide the most value when things are not working properly.

It is intended as a practical logging map, not as a mandate to add verbose tracing everywhere.

## Purpose

ASS should use diagnostic logging to make failures and unexpected behavior easier to understand in areas where:

- phase boundaries are crossed
- derived artifacts are built
- external side effects are executed
- runtime state is difficult to inspect from tests alone

ASS should avoid:

- permanent always-on hot-path tracing
- logging that turns production behavior into migration scaffolding
- scattered ad hoc prints
- low-value noise that hides actual failures

## Logging principles

### 1. Prefer phase-boundary summaries

The highest-value logs are usually emitted where one artifact becomes another.

Examples:

- recording started and stopped
- interpretation transformed N raw events into M interpreted events
- shaping transformed N interpreted events into M shaped actions
- playback plan built from one explicit source

### 2. Prefer decision summaries over event spam

Good logging:

- why a click candidate was rejected
- how many mouse moves were collapsed
- why playback failed on a specific action

Bad logging:

- logging every mouse move in normal operation
- tracing every internal helper call by default

### 3. Keep hot-path tracing opt-in

Runtime, playback, and debugging paths may need detailed tracing during development, but those traces should be behind explicit debug controls.

### 4. Never use `print(...)` for internal diagnostics

Internal diagnostics should go through the shared logger infrastructure, not directly to stdout.

### 5. Preserve authority boundaries

Logs should make it easier to see:

- what the authority source was
- what derived artifact was created
- what downstream step consumed it

## Existing logger infrastructure

ASS already has:

- [debug_logger.py](../../infrastructure/debug_logger.py)

This should remain the shared diagnostic logging entry point.

## Current diagnostic logger model

ASS now uses a structured diagnostic logger rather than the older integer `level` / `verbosity` helper style.

The core model is:

- `DiagnosticLogger`
- `DiagnosticSeverity`
- `DiagnosticDetail`
- `DiagnosticEvent`
- `DiagnosticConfig`
- `DiagnosticTimestampFormat`

### Severity

Severity answers:

- how serious is this event?

Current values:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`

### Detail

Detail answers:

- how verbose is this event?

Current values:

- `ESSENTIAL`
- `SUMMARY`
- `DECISION`
- `TRACE`

### Recommended method usage

Prefer the class-style logger methods:

- `.info(...)` for lifecycle and phase-boundary summaries
- `.decision(...)` for meaningful branch/filter/interpreter decisions
- `.trace(...)` for opt-in hot-path detail
- `.warning(...)` for unexpected but non-fatal conditions
- `.error(...)` for explicit failures
- `.exception(...)` when logging a caught exception boundary

### Structured fields

Call sites should prefer structured fields over message-only strings.

When a call site includes an `event_id`, it should use a stable normalized dot-delimited name so related diagnostics stay easy to search and correlate.

Good:

```python
log.info(
    "Playback plan executed successfully",
    event_id="playback.execute.success",
    source_kind=result.source_kind,
    source_id=result.source_id,
    executed_event_count=result.executed_event_count,
)
```

Less useful:

```python
log.info("playback worked")
```

### Environment variables

The current logger reads configuration from environment variables:

- `ASS_DIAGNOSTICS`
- `ASS_DIAGNOSTIC_MIN_SEVERITY`
- `ASS_DIAGNOSTIC_MAX_DETAIL`
- `ASS_DIAGNOSTIC_TIMESTAMP_FORMAT`
- `ASS_DIAGNOSTIC_FILE`
- `ASS_DIAGNOSTIC_STDOUT`
- `ASS_DIAGNOSTIC_PATH`
- `ASS_DIAGNOSTIC_SUBSYSTEMS`

This allows diagnostics to stay opt-in while still making deep tracing available when needed.

`ASS_DIAGNOSTIC_MIN_SEVERITY` accepts `debug`, `info`, `warning`, `error`, or the matching numeric enum values.
`ASS_DIAGNOSTIC_MAX_DETAIL` accepts `0` through `3`, the matching names `essential`, `summary`, `decision`, `trace`, and shorthand ranges such as `0..3` or `0..1`, which are treated as the upper bound.
`ASS_DIAGNOSTIC_TIMESTAMP_FORMAT` accepts `epoch_ms` by default and `iso8601` for an ISO-8601 timestamp with milliseconds, while still preserving the human-readable local clock timestamp in the log prefix.

## File-by-file logging map

## Recording

### [recording_service.py](../../application/recording_service.py)

Recommended diagnostics:

- recording start request
- recording stop request
- selected config summary
- capture backend selection
- returned session summary
- lifecycle failures

Why it matters:

- this is the application boundary for phase 1
- it is the best place to understand high-level recording lifecycle behavior

### [session_recorder.py](../../core/recording/session_recorder.py)

Recommended diagnostics:

- recorder state transitions
- accepted vs suppressed raw events
- stop-hotkey suppression behavior
- event counts by type
- reset behavior

Why it matters:

- this is where raw-event authority is assembled
- it is often the first place to inspect when capture looks incomplete or noisy

### [input_capture.py](../../core/recording/input_capture.py)

Recommended diagnostics:

- listener start/stop
- callback registration failures
- backend invocation boundaries

Why it matters:

- this is where backend failures can otherwise disappear into infrastructure edges

### [pynput_backend.py](../../infrastructure/input/pynput_backend.py)

Implemented diagnostics now include:

- backend start/stop lifecycle
- listener startup and shutdown
- hotkey normalization and stop-hotkey state transitions
- threshold-based mouse-move suppression decisions
- capture-disabled and raw-event emission tracing

Recommended diagnostics:

- OS-hook startup failures
- listener-thread exceptions
- normalized raw event creation failures

Why it matters:

- this is the lowest-level live input capture boundary

## Interpretation

### [interpretation_service.py](../../application/interpretation_service.py)

Recommended diagnostics:

- interpretation config summary
- input event count
- output interpreted-event count
- top-level interpretation failures

Why it matters:

- this is the application boundary for phase 2

### [recording_interpreter.py](../../core/interpretation/recording_interpreter.py)

Recommended diagnostics:

- pass ordering
- event-count deltas after each pass
- whether pass-through output remained unchanged

Why it matters:

- this is the central interpretation orchestration point

### [click_interpreter.py](../../core/interpretation/click_interpreter.py)
### [drag_interpreter.py](../../core/interpretation/drag_interpreter.py)
### [keyboard_interpreter.py](../../core/interpretation/keyboard_interpreter.py)

Recommended diagnostics:

- why a candidate was accepted
- why a candidate was rejected
- threshold values used in the decision
- interleaving-policy rejections

Why they matter:

- these are the files most likely to explain "why didn’t this action get recognized?"

## Shaping

### [shaping_service.py](../../application/shaping_service.py)

Recommended diagnostics:

- shaping config summary
- input interpreted-event count
- output shaped-action count

Why it matters:

- this is the application boundary for phase 3

### [shaping_pipeline.py](../../core/shaping/shaping_pipeline.py)

Recommended diagnostics:

- action-count deltas after each shaping pass
- pass ordering

Why it matters:

- this is where "what changed?" is easiest to summarize

### [mouse_shaper.py](../../core/shaping/mouse_shaper.py)
### [keyboard_shaper.py](../../core/shaping/keyboard_shaper.py)
### [click_shaper.py](../../core/shaping/click_shaper.py)
### [delay_shaper.py](../../core/shaping/delay_shaper.py)

Recommended diagnostics:

- collapse decisions
- smoothing decisions
- dropped/merged action summaries
- threshold values involved in simplification

Why they matter:

- these files explain why output became simpler or more optimized

## Filter system

### Application services

- [recording_filter_service.py](../../application/recording_filter_service.py)
- [interpretation_filter_service.py](../../application/interpretation_filter_service.py)
- [shaping_filter_service.py](../../application/shaping_filter_service.py)
- [document_filter_service.py](../../application/document_filter_service.py)

Recommended diagnostics:

- selected profile
- enabled filters
- input summary
- output summary
- applied filter list
- filter-service failures

Why they matter:

- these are the best places to explain what a profile actually did

### Core filter pipelines and implementations

Recommended diagnostics:

- filter-specific accept/reject decisions
- changed vs unchanged counts
- threshold/config values
- notes explaining why a filter skipped an item

Highest-value files:

- recording filter pipelines
- interpretation filter pipelines
- shaping filter pipelines
- document filter pipelines
- mouse smoothing filter
- text-run refinement filter
- document normalization filter

Why they matter:

- filters are often hard to debug because they are intentionally derived and multi-stage

## Script generation and document conversion

### [script_generation_service.py](../../application/script_generation_service.py)

Recommended diagnostics:

- generation config summary
- shaped action count
- generated line count
- unsupported-action handling summary

### [script_generation_pipeline.py](../../core/scripting/generation/script_generation_pipeline.py)
### [action_to_script_renderer.py](../../core/scripting/generation/action_to_script_renderer.py)

Implemented diagnostics now include:

- generation start and completion summaries
- header-comment emission or skip decisions
- separator insertion between header and body
- body-render summary counts

Recommended diagnostics:

- per-action rendering decisions
- unsupported action comments
- header/comment emission behavior

Why they matter:

- these explain why generated script text looks the way it does

### [script_document_service.py](../../application/script_document_service.py)
### [script_document_factory.py](../../core/scripting/documents/script_document_factory.py)

Recommended diagnostics:

- conversion from `GeneratedScript` to `ScriptDocument`
- document id/version summary
- source provenance fields
- authority transfer confirmation

Why they matter:

- this is where script authority becomes explicit

## Playback

### [playback_service.py](../../application/playback_service.py)

Recommended diagnostics:

- selected source kind
- request summary
- mode and repeat behavior
- request validation failures

Why it matters:

- this is the application boundary for phase 6

### [playback_engine.py](../../core/playback/playback_engine.py)

Recommended diagnostics:

- execution start and finish
- repeat loop summary
- executed event count
- first failure point

Why it matters:

- this is where playback side effects are actually consumed

### [from_recording_builder.py](../../core/playback/builders/from_recording_builder.py)
### [from_script_builder.py](../../core/playback/builders/from_script_builder.py)

Recommended diagnostics:

- source-to-plan derivation summary
- output event count
- unsupported source constructs

Why they matter:

- these explain how playback plans were derived from explicit authority

### [live_input_executor.py](../../core/playback/executors/live_input_executor.py)
### [pynput_playback_adapter.py](../../infrastructure/input/pynput_playback_adapter.py)

Implemented diagnostics now include:

- per-event live dispatch tracing
- hotkey press/release sequencing
- delay dispatch summaries
- malformed hotkey rejection
- hotkey cleanup after partial failure

Recommended diagnostics:

- actual host calls
- host-call failures
- unsupported action type failures

Why they matter:

- these are the playback equivalents of the old input executor logging hotspots

## Runtime

### [script_runtime.py](../../core/runtime/script_runtime.py)

Recommended diagnostics:

- compile start/finish
- parse/diagnostic failures
- function call and return summaries
- unsupported builtin or statement failures
- script-to-playback compilation summary
- runtime exception boundaries

Why it matters:

- this is one of the highest-value debugging files in the repo

Caution:

- keep detailed tracing opt-in
- do not leave always-on runtime trace scaffolding in the hot path

### [execution_context.py](../../core/runtime/execution_context.py)

Recommended diagnostics:

- call-frame push/pop
- emitted runtime/playback events
- exception recording
- scope/variable state summaries around failure points

## Debugging

### [debugging_service.py](../../application/debugging_service.py)

Recommended diagnostics:

- debug-session startup
- request summary
- runtime/controller wiring summary

Why it matters:

- this is the application boundary for phase 7

### [debug_controller.py](../../core/debugging/debug_controller.py)

Recommended diagnostics:

- breakpoint hits
- pause and resume transitions
- step-over and step-out depth logic
- session completion/failure transitions
- exception handling

Why it matters:

- this is the most valuable debugger-state diagnostic file

### [runtime_debug_hooks.py](../../core/debugging/runtime_debug_hooks.py)
### [source_map.py](../../core/debugging/source_map.py)

Recommended diagnostics:

- statement-to-line mapping
- breakpointability lookups
- missing or invalid source-location cases

Why they matter:

- these explain why the debugger stopped where it did, or why it did not

## Highest-value starting points

If logging is being added incrementally, start here:

1. [recording_service.py](../../application/recording_service.py)
2. [session_recorder.py](../../core/recording/session_recorder.py)
3. [interpretation_service.py](../../application/interpretation_service.py)
4. [recording_interpreter.py](../../core/interpretation/recording_interpreter.py)
5. [shaping_filter_service.py](../../application/shaping_filter_service.py)
6. [playback_service.py](../../application/playback_service.py)
7. [playback_engine.py](../../core/playback/playback_engine.py)
8. [script_runtime.py](../../core/runtime/script_runtime.py)
9. [debug_controller.py](../../core/debugging/debug_controller.py)

## Recommended logging policy

ASS should prefer:

- service-level lifecycle logs
- builder and pipeline summaries
- filter profile and threshold summaries
- executor failure diagnostics
- runtime and debugger diagnostics behind explicit debug controls

ASS should avoid:

- permanent always-on hot-path tracing
- direct `print(...)` debugging
- logging every tiny event in normal operation
- reviving raw integer `level` logging at new call sites

## Initial success criteria

The diagnostic logging strategy is on track when:

- phase boundaries emit useful summaries
- failures are attributable to a specific stage or file
- playback and runtime failures are easier to localize
- filter behavior can be understood from applied-profile logs
- debugger pause/resume behavior can be explained from controller logs
- verbose tracing remains opt-in rather than permanent
