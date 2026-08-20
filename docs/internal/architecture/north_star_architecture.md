# ActionShellScript North-Star Architecture

## Purpose
This document defines the target architecture for the fresh `ActionShellScript` repository.

It exists to keep the project grounded around clear boundaries, explicit authority, and predictable workflow transitions. The primary goal is to avoid the architectural drift that happens when recording data, transformed data, script text, playback caches, and UI state all compete to be the system's truth.

## Architectural Principles
### One Authority Per Workflow Stage
At any point in the workflow, exactly one artifact is authoritative. Every other artifact is derived, cached, or disposable.

### Derived Artifacts Are Rebuildable
Interpretation results, shaped actions, generated script text, playback plans, and diagnostics must all be reproducible from their authoritative source.

### Caches Are Never Truth
Preview data, cached playback events, editor-side transforms, and debug traces are convenience structures. They must never silently become the active source of truth.

### The UI Is A Consumer
The desktop application consumes application services and domain artifacts. It does not decide workflow semantics or own orchestration rules.

### Playback Is Always Derived
Playback plans are built from the currently selected authority. Playback itself never becomes authoritative.

### Debugging Starts From Script Authority
Debugging starts from `ScriptDocument` and runtime source mapping, never from a playback cache or reconstructed UI state.

## Desktop Workflow Contract
The desktop application is the editing and playback surface for user-authored automation.

The intended user workflow is:

- Record a session
- Convert the recording into editable script form
- Modify the script as needed
- Play the edited script back
- Or skip editing and play the recording directly

The editor is not a secondary view. It is the place where recorded playback becomes user-customized automation.

### Workflow Expectations

- A recorded session may be played back without being edited.
- A recording may be converted into a `ScriptDocument` for customization.
- A `ScriptDocument` may be edited freely before playback.
- Playback must always use the current authoritative source.
- The UI must not treat the absence of executable playback events as a workflow failure if the derived plan still contains valid derived output.

### Playback and Output

`PlaybackPlan` is derived and disposable.

A playback plan may legitimately contain:

- executable playback events
- `console_output`
- zero executable playback events

The desktop UI must not infer invalidity solely from `event_count == 0`. If a plan contains only derived output, that output must still be allowed to flow through the playback path.

Script diagnostics are a separate structured logger stream. `DiagWrite` and `DiagWriteLn` should flow through diagnostics logging surfaces rather than the playback transcript.

### Desktop Responsibility

The desktop application consumes application services and domain artifacts.

It must not redefine workflow semantics based on UI convenience. In particular, the desktop UI must preserve the distinction between:

- authoritative source artifacts
- derived playback plans
- derived output
- unsupported host features

If a feature is not yet surfaced in the desktop UI, that limitation must be explicit. It must not be represented as a failure of the source artifact or the playback plan itself.

## Authority Model
### Authoritative Objects
#### `RecordingSession`
Authoritative for:

- captured input history
- recording session start and stop boundaries
- raw recording truth

#### `ScriptDocument`
Authoritative for:

- editable script text
- document version and dirty state
- script editing workflow after conversion

#### `DebugSession`
Authoritative for:

- live runtime control state during debugging
- pause and resume state
- current line, stack, variables, and exception state for the active run

### Derived Objects
#### `InterpretedRecording`
Derived from `RecordingSession`.

Represents recognized user actions such as clicks, drags, hotkeys, and key holds.

#### `ShapedActionSequence`
Derived from `InterpretedRecording`.

Represents representation-oriented cleanup and simplification for script generation or playback planning.

#### `GeneratedScript`
Derived from `ShapedActionSequence`.

Represents initial script text produced from recording-derived actions.

#### `PlaybackPlan`
Derived from either:

- `RecordingSession`, or
- `ScriptDocument`

Represents executable playback instructions for a single chosen source.

#### `DiagnosticsReport`
Derived from any authoritative or derived artifact for analysis and display.

## Authority Transfer Rules
### Recording Mode
Authority is the live in-memory `RecordingSession`.

### Recording Review Mode
Authority remains the finalized `RecordingSession`.

Derived views may include:

- interpreted recording
- shaped action sequence
- generated script preview
- playback preview

These remain views of the recording and do not replace it.

### Script Conversion
Authority transfers only when the user explicitly converts generated script into an editable document, such as by choosing `Edit Script` or `Open as Script`.

At that moment:

- a `ScriptDocument` is created
- it is initialized from `GeneratedScript.text`
- the `ScriptDocument` becomes authoritative for the script editing workflow

The original recording-derived artifacts remain provenance, not live truth.

### Playback
Authority remains external to playback:

- `RecordingSession` when playing from recording review
- `ScriptDocument` when playing from the editor or debugger path

`PlaybackPlan` is always derived and disposable, even when it contains zero executable events.

### Debugging
Authority is split cleanly:

- `ScriptDocument` is authoritative for source text
- `DebugSession` is authoritative for live debug runtime state

## Phase Model
## Phase 1: Recording Slice
### Goal
Capture input and produce a valid `RecordingSession`.

### Authoritative Object
- `RecordingSession`

### Main Components
- `RecorderConfig`
- `InputCapture`
- `PynputCaptureBackend`
- `SessionRecorder`
- `RecordingService`
- `apps/cli/record_command.py`

### Responsibilities
- start and stop recording
- capture raw input
- store raw events only
- maintain recording session truth

### Non-Responsibilities
- no interpretation
- no script shaping
- no playback planning
- no editor involvement

## Phase 2: Interpretation Slice
### Goal
Recognize user actions from `RecordingSession` without mutating it.

### Authoritative Object
- `RecordingSession`

### Derived Object
- `InterpretedRecording`

### Main Components
- `InterpretationConfig`
- `RecordingInterpreter`
- click interpreter
- drag interpreter
- keyboard interpreter
- `InterpretationService`

### Responsibilities
- click recognition
- drag recognition
- key hold recognition
- hotkey recognition

### Non-Responsibilities
- no shaping
- no script generation
- no playback planning

## Phase 3: Shaping Slice
### Goal
Reshape interpreted actions for representation purposes without changing meaning.

### Authoritative Objects
- `RecordingSession`
- `InterpretedRecording`

### Derived Object
- `ShapedActionSequence`

### Main Components
- `ShapingConfig`
- `ShapingPipeline`
- delay shaper
- mouse shaper
- click shaper
- keyboard shaper
- `ShapingService`

### Responsibilities
- simplification
- representation cleanup
- downstream-friendly action shaping

### Non-Responsibilities
- must not redefine user action meaning
- must not mutate recording truth or interpretation truth

## Phase 4: Script Generation Slice
### Goal
Generate initial executable script text from shaped actions for preview and export.

### Authoritative Object
- `ShapedActionSequence`

### Derived Object
- `GeneratedScript`

### Main Components
- `GeneratedScript`
- `ScriptGenerationConfig`
- `ScriptGenerationPipeline`
- action-to-script renderer
- header comment renderer
- `ScriptGenerationService`
- `apps/cli/generate_command.py`

### Responsibilities
- generate initial script text
- support preview and export
- preserve provenance back to the source session
- provide a real end-to-end generation path from saved raw session input
- keep generated text rebuildable from shaping truth

### Non-Responsibilities
- generated script is not editable authority
- generation must not mutate `ShapedActionSequence`

## Phase 5: Script Document / Editor Slice
### Goal
Promote `GeneratedScript` into an editable `ScriptDocument`.

### New Authoritative Object
- `ScriptDocument`

### Main Components
- `ScriptDocument`
- `ScriptDocumentFactory`
- `ScriptDocumentService`
- parse service
- diagnostics service
- formatting service

### Responsibilities
- explicit authority transfer
- editable document lifecycle
- document versioning and dirty tracking

### Non-Responsibilities
- regenerated script must not silently overwrite `ScriptDocument`

## Phase 6: Playback Slice
### Goal
Execute playback from explicit source authorities.

### Authoritative Objects
- `RecordingSession`
- `ScriptDocument`

### Derived Objects
- `PlaybackRequest`
- `PlaybackPlan`
- `PlaybackResult`

### Main Components
- `PlaybackPlanFromRecordingBuilder`
- `PlaybackPlanFromScriptBuilder`
- `PlaybackBuilder`
- `PlaybackEngine`
- executors
- `PlaybackService`

### Responsibilities
- explicit source selection
- playback plan generation
- playback execution

### Non-Responsibilities
- playback plans are never authoritative
- cached playback must never replace the active source authority

## Phase 7: Debugger Slice
### Goal
Debug script execution from `ScriptDocument` using runtime hooks and source spans.

### Authoritative Objects
- `ScriptDocument`
- `DebugSession`

### Derived Objects
- parsed AST
- debug events
- debug state snapshots
- variable snapshots
- call stack snapshots
- execution traces

### Main Components
- `DebugRequest`
- `DebugEvent`
- `DebugState`
- `BreakpointSet`
- `SourceMap`
- `DebugController`
- `RuntimeDebugHooks`
- `DebuggingService`

### Responsibilities
- breakpoints
- stepping
- pause and resume behavior
- runtime-backed debug state snapshots
- source-accurate debugging

### Non-Responsibilities
- debugger must not start from playback caches
- playback metadata is not debugger truth

## Target Directory Structure
```text
apps/
  cli/
  desktop/

application/
  recording_service.py
  interpretation_service.py
  shaping_service.py
  script_generation_service.py
  script_document_service.py
  playback_service.py
  debugging_service.py

core/
  recording/
  interpretation/
  shaping/
  playback/
  debugging/
  scripting/

editor/
  document/
  language_services/

infrastructure/
  input/
  logging/
  persistence/
```

## Layer Responsibilities
### `core/`
Contains domain and workflow logic. No UI-specific behavior. No direct desktop dependency.

### `application/`
Contains use-case orchestration for CLI and desktop consumers.

### `editor/`
Contains editable document concerns and language services. This is its own product surface, not a side effect of the desktop shell.

### `infrastructure/`
Contains external integrations such as input libraries, persistence, filesystem access, logging, and platform adapters.

### `apps/`
Contains entrypoints and presentation shells:

- CLI commands
- desktop UI

## Dependency Rules
### Allowed Direction
- `apps -> application -> core`
- `apps -> application -> editor`
- composition roots wire `infrastructure` into `application` and `core`

### Not Allowed
- `core` importing desktop UI
- `core` depending directly on editor widgets
- UI reconstructing workflow truth from caches
- playback caches used as script or debug authority

## Source-of-Truth Guardrails
### Must Never Be Edited In Place
- finalized `RecordingSession`
- `InterpretedRecording`
- `ShapedActionSequence`
- `GeneratedScript`
- `PlaybackPlan`
- preview caches
- playback caches
- debug traces

### Can Be Edited
- live `RecordingSession` while capture is active
- `ScriptDocument`
- user-facing settings and profiles

## Filtering and Transformation Model
The system should stop treating all transformation concerns as one generic filtering subsystem.

### Recording-Stage Cleanup
Purpose:
- capture correctness
- signal cleanup necessary to preserve truth

### Interpretation
Purpose:
- decide what the user did

### Shaping
Purpose:
- decide how interpreted behavior should be represented

### Playback Adaptation
Purpose:
- apply execution-specific adjustments only when necessary for reliable playback

## Debugging Model
### Source of Truth
- `ScriptDocument.text`

### Source Mapping
- parser spans
- no synthetic-line fallback as the normal contract

### Runtime Hooks
- before statement
- function enter and return
- exception
- breakpoint and stepping checks

### UI Role
- consume debug snapshots and events
- never compute debugger truth itself

## Playback Model
### Explicit Entry Paths
- playback from `RecordingSession`
- playback from `ScriptDocument`

### Playback Plan Requirements
- always derived
- always disposable
- always tagged with source kind and source id

## Builtin Behavior Model
The builtin set is grouped by how each builtin behaves from the desktop application's point of view.

### Visible Desktop Output
These builtins produce runtime output that the desktop UI surfaces in the playback output view:

- `Write`
- `WriteLn`
- `DiagWrite`
- `DiagWriteLn`

### Desktop Host Services
These builtins depend on desktop host behavior and are wired through the desktop runtime seam:

- `MsgBox`
- `KeyToggle`
- `PixelGetColor`
- `PixelSearch`

### Playback / OS Input Actions
These builtins replay input or timing actions on the host:

- `SendKeys`
- `KeyDown`
- `KeyPress`
- `KeyUp`
- `Hotkey`
- `MouseClick`
- `MouseClickDrag`
- `MouseDrag`
- `MouseDown`
- `MouseMove`
- `SetMouseMoveSpeed`
- `MouseWheel`
- `Sleep`

### Runtime Helpers
These builtins are language and runtime helpers. They are supported by the runtime and do not require special desktop UI wiring:

- `GetMouseMoveSpeed`
- `String`
- `Asc`
- `AscW`
- `Chr`
- `ChrW`
- `Abs`
- `Ceiling`
- `ReadFile`
- `WriteFile`
- `AppendFile`
- `FileExists`
- `DeleteFile`
- `CreateDir`
- `DirExists`
- `PathExists`
- `PathCombine`
- `PathNormalize`
- `IsPathValid`
- `FileName`
- `DirectoryName`
- `ExtensionName`
- `ReadBytes`
- `WriteBytes`
- `AppendBytes`
- `BinaryLength`
- `Hex`
- `FromHex`
- `Base64`
- `FromBase64`
- `Binary`
- `BinaryMid`
- `BinaryToString`
- `BitAnd`
- `BitNot`
- `BitNotUnsigned`
- `Exp`
- `Floor`
- `Mod`
- `BitRotate`
- `BitShift`
- `BitOr`
- `BitXor`

### Builtin Contract
- Desktop output builtins must be visible in the UI.
- Desktop host services must be wired through the desktop runtime seam.
- Playback actions are replayed as OS input events.
- Runtime helpers are supported by the language runtime and may not have direct UI-visible effects.

## Migration Strategy
### First Focus
Build the phase-1 recording CLI slice cleanly.

### Then Progress Through
1. interpretation
2. shaping
3. script generation
4. script document conversion
5. playback
6. debugger

### Migration Principle
Port behavior in thin vertical slices. Do not copy unclear orchestration layers into the new repo unchanged.

## Anti-Goals
The new repo should avoid:

- giant bridge modules
- UI-owned workflow semantics
- multiple co-authoritative representations
- playback cache as source of truth
- debugger behavior reconstructed from playback metadata
- temporary compatibility scaffolding becoming permanent architecture

## Initial Success Criteria
The architecture is on track when:

- recording CLI works without desktop UI
- `RecordingSession` is the only recording truth
- interpretation is derived and repeatable
- shaping is distinct from meaning
- generated script is not mistaken for editable authority
- `ScriptDocument` becomes authoritative only after conversion
- playback source is always explicit
- debugger always starts from `ScriptDocument`
