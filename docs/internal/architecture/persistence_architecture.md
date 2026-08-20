# Persistence Architecture

This document defines the target persistence architecture for ActionShellScript (ASS).

It covers:

- shared save/load responsibilities
- dirty-state tracking
- unsaved-changes workflow boundaries
- separation between shared persistence and GUI-only state

## Purpose

ASS needs a persistence model that works for both CLI and GUI workflows without letting the GUI become the owner of project and document save logic.

The persistence system should support:

- script save/load
- saved recording/session files
- filter profile/config persistence
- future project/workspace files
- shared dirty-state tracking

The persistence system should avoid:

- UI-owned project save logic
- duplicated CLI and GUI file handling rules
- silent mutation of authority without save-state tracking
- mixing project/workflow persistence with GUI-only preferences

## Core principles

### 1. Project and workflow persistence are shared

If a persisted artifact would still make sense without a GUI, it should belong to a shared persistence layer.

Examples:

- `ScriptDocument`
- `RecordingSession`
- filter profiles
- project files
- shared configuration bundles

### 2. GUI-only preferences stay separate

GUI-specific state should not live in the shared persistence layer.

Examples:

- window size
- layout
- theme
- desktop preferences that combine workspace behavior and editor appearance
- splitter positions
- recent panel state

## Desktop preferences

ASS now treats desktop preferences as one persisted desktop settings bundle with a clear split between storage, application policy, and live UI state.

### Persisted bundle shape

The persisted unit is `DesktopSettingsBundle`, stored in `desktop_settings.json`. It contains seven submodels:

- `application`
  - workspace restoration behavior
  - whether the formatted preview tab is shown
  - whether the summary sidebar is shown on the left
  - whether the Raw Recordings, Analysis, Diagnostics, and Debugger sidebar are shown in the workspace
  - whether the Debugger sidebar opens automatically when execution pauses
  - the last workspace path, when restore-last-workspace is enabled
  - desktop hotkey bindings, including the workspace, debug-tab, and debugger step/continue/stop shortcuts
- `playback`
  - repeat count
  - step mode
  - pre-event delay
  - live mouse settle timing
- `recording`
  - capture toggles for mouse, wheel, and keyboard input
  - mouse-move threshold
  - recording conversion mode
  - autosave and raw-autosave defaults
- `files`
  - raw recording autosave defaults
  - converted script autosave defaults
  - diagnostic log path
- `diagnostics`
  - diagnostics enablement
  - severity and detail filters
  - stdout and file logging toggles
- `runtime`
  - loop and call-depth guards
  - default mouse-move speed for runtime-backed execution
  - mouse-movement curve profile, reference-curve toggle, and step controls used by the runtime preferences page
- `theme`
  - the nested `DesktopPreferences` model
  - appearance colors for the editor, syntax highlighting, and dirty indicators
  - scripting defaults such as language, extension, indent width, spaces-vs-tabs, and auto-format
  - font family, size, weight, and line spacing

### Persistence flow

`DesktopSettingsService` owns load and save of the full bundle. The GUI does not write individual preference files directly.

On startup, the service:

1. Loads `desktop_settings.json` when present.
2. Falls back to the legacy `application_settings.json` and `theme_settings.json` files when the unified file is missing.
3. Migrates any legacy files into `desktop_settings.json` after the first successful load.

The diagnostic log path now lives in the `files` section. Older runtime-stored values are migrated forward on load so existing users keep their setting.

At runtime, the desktop window may update the `last_workspace_path` field on a best-effort basis when restore-last-workspace is enabled.

The preferences dialog edits a snapshot of the bundle, not the persisted file in place. Dirty state is derived by comparing the current in-memory snapshot against the saved snapshot, which keeps restore-defaults, section badges, and the save prompt aligned with the actual bundle contents.

When the user saves, the service persists the whole `DesktopSettingsBundle` back to `desktop_settings.json` in one write.

### 3. Dirty-state tracking is shared

Whether a document or project has unsaved changes is not a GUI concept.

Dirty-state tracking belongs in the shared layer.

### 4. User prompting is interface-specific

The shared layer should determine whether save resolution is needed.

The GUI or CLI should decide how to ask the user.

Examples:

- GUI modal dialog with `Save`, `Discard`, `Cancel`
- CLI prompt or `--force` behavior

### 5. Authority boundaries remain explicit

Persistence should reinforce the existing authority model.

Examples:

- saving a `ScriptDocument` persists script authority
- saving a `RecordingSession` persists raw recording authority
- saving a generated artifact must not silently convert it to authority unless the workflow explicitly does so

## Shared versus GUI-only persistence

## Shared persistence

Shared persistence should handle:

- `ScriptDocument`
- `RecordingSession`
- filter profiles and profile bundles
- future project/workspace files
- dirty-state tracking
- save coordination

## GUI-only persistence

GUI-only persistence should handle:

- window geometry
- theme preferences
- panel state
- recent visual state
- other interface personalization

The GUI should consume shared persistence for project/workflow data rather than reimplementing it.

## Dirty-state model

Dirty-state should be part of shared document/project behavior.

## Shared responsibilities

The shared layer should own:

- whether an artifact is dirty
- whether a change increments version
- whether a successful save clears dirty state
- whether an action requires unsaved-changes resolution

## Recommended shared types

### Unsaved-changes choice

```python
from enum import StrEnum


class UnsavedChangesChoice(StrEnum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"
```

### Dirty-state summary

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DirtyState:
    is_dirty: bool
    version: int
    last_saved_version: int | None
```

### Save requirement

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SaveRequirement:
    requires_save: bool
    reason: str | None = None
```

## Script document dirty-state

`ScriptDocument` should remain the main early persistence example.

Recommended state:

- current version
- dirty flag
- optional `last_saved_version`

Example shape:

```python
@dataclass(slots=True)
class ScriptDocument:
    document_id: str
    text: str
    version: DocumentVersion = field(default_factory=DocumentVersion)
    is_dirty: bool = False
    last_saved_version: int | None = None

    def replace_text(self, new_text: str) -> None:
        if new_text == self.text:
            return
        self.text = new_text
        self.version = self.version.next()
        self.is_dirty = True

    def mark_saved(self) -> None:
        self.is_dirty = False
        self.last_saved_version = self.version.value
```

## Unsaved-changes interaction model

The shared layer should answer:

- is this artifact dirty?
- does this action require save resolution?

The interface layer should ask:

- `Save`
- `Discard`
- `Cancel`

## Recommended shared service

```python
class DirtyStateService:
    def requires_save_before_close(self, document: ScriptDocument) -> SaveRequirement: ...
    def requires_save_before_replace(self, document: ScriptDocument) -> SaveRequirement: ...
```

This keeps save-resolution policy shared while allowing different interfaces to present different prompts.

## Interface-specific behavior

### GUI

The GUI may show:

- modal dialogs
- destructive-action warnings
- save/discard/cancel buttons

### CLI

The CLI may use:

- interactive prompts
- `--force`
- `--discard-unsaved`
- fail-fast behavior in non-interactive mode

These interaction mechanisms should not live in the shared persistence layer.

## Persistence architecture layers

ASS should use three persistence layers.

## 1. Application persistence layer

This layer owns save/load orchestration in application terms.

Recommended responsibilities:

- saving and loading script documents
- saving and loading sessions
- saving and loading filter profiles
- coordinating dirty-state and save workflows

Recommended structure:

```text
application/
  persistence/
    script_document_store.py
    recording_session_store.py
    filter_profile_store.py
    project_store.py
    save_coordinator.py
    dirty_state_service.py
    persistence_errors.py
```

## 2. Core persistence types

This layer owns shared persistence-oriented value types and contracts.

Recommended structure:

```text
core/
  persistence/
    save_result.py
    load_result.py
    file_reference.py
    persistence_models.py
```

This layer should stay thin.

## 3. Infrastructure persistence layer

This layer owns actual file I/O behavior.

Recommended structure:

```text
infrastructure/
  persistence/
    json_file_store.py
    text_file_store.py
    atomic_file_writer.py
```

This is where actual path handling, encoding, and atomic writes should live.

## Store model

Each persisted artifact should have:

- a shared store contract
- a file-backed infrastructure implementation

## Script document store

```python
class ScriptDocumentStore(Protocol):
    def load(self, path: Path) -> ScriptDocument: ...
    def save(self, path: Path, document: ScriptDocument) -> None: ...
```

## Recording session store

```python
class RecordingSessionStore(Protocol):
    def load(self, path: Path) -> RecordingSession: ...
    def save(self, path: Path, session: RecordingSession) -> None: ...
```

## Filter profile store

```python
class FilterProfileStore(Protocol):
    def load(self, path: Path) -> FilterProfile: ...
    def save(self, path: Path, profile: FilterProfile) -> None: ...
```

## Project store

If ASS introduces a project/workspace file, it should use a dedicated store:

```python
class ProjectStore(Protocol):
    def load(self, path: Path) -> AssProject: ...
    def save(self, path: Path, project: AssProject) -> None: ...
```

## Save coordinator

ASS should have a shared save coordinator that ties dirty-state and persistence together.

Recommended role:

- save current document
- save as
- clear dirty state only after successful persistence
- centralize save workflow policy

Example:

```python
class SaveCoordinator:
    def save_script_document(
        self,
        document: ScriptDocument,
        *,
        path: Path,
        store: ScriptDocumentStore,
    ) -> None: ...
```

On successful save:

- the store writes the file
- the document is marked saved

## Atomic writes

ASS should prefer atomic writes for persisted files.

This is especially important once GUI save flows exist.

Recommended infrastructure support:

- temporary-file write
- replace-on-success
- parent directory creation
- consistent encoding rules

This belongs in:

- `infrastructure/persistence/atomic_file_writer.py`

## Recommended GUI-only persistence structure

GUI-only persistence should be separate.

Recommended structure:

```text
gui/
  preferences/
    preferences_store.py
    ui_state_store.py
    recent_files_store.py
```

This layer should not own:

- script authority
- recording/session save logic
- filter profile format
- project file structure

## Save/discard/cancel workflow model

The shared layer should define the abstract workflow concepts.

The interface layer should present them.

## Recommended shared action enum

```python
class PendingAction(StrEnum):
    CLOSE_DOCUMENT = "close_document"
    OPEN_OTHER_DOCUMENT = "open_other_document"
    EXIT_APPLICATION = "exit_application"
```

## Recommended shared service

```python
class UnsavedChangesService:
    def requires_resolution(
        self,
        document: ScriptDocument,
        *,
        action: PendingAction,
    ) -> SaveRequirement: ...
```

Then:

- the GUI can show a save/discard/cancel dialog
- the CLI can prompt or honor `--force`
- tests can inject a choice directly

## Recommended implementation order

### 1. Shared script persistence

Start with:

- `ScriptDocument`
- `ScriptDocumentStore`
- `SaveCoordinator`

### 2. Shared session persistence

Then add:

- `RecordingSessionStore`

### 3. Shared dirty-state helpers

Then add:

- `DirtyStateService`
- `UnsavedChangesService`

### 4. Shared filter profile persistence

Then add:

- `FilterProfileStore`

### 5. GUI-only preferences later

Only after the shared model is stable, add GUI-only persistence for:

- preferences
- layout
- visual state

## Anti-goals

ASS should avoid:

- GUI-owned project file logic
- duplicated save/load logic across CLI and GUI
- modal-dialog code in shared persistence
- terminal prompt code in shared persistence
- mixing workflow persistence with UI personalization

## Initial success criteria

The persistence architecture is on track when:

- script save/load is shared between CLI and GUI
- recording/session save/load is shared between CLI and GUI
- dirty-state tracking is part of shared document logic
- save/discard/cancel interaction remains interface-specific
- GUI-only preferences are separated from project/workflow persistence
- successful saves clear dirty state through shared save coordination
