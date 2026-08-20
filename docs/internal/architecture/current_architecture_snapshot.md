# Current Architecture Snapshot

Snapshot date: 2026-05-12

This document captures the repository architecture as it exists right now. It is intentionally a point-in-time map, not a promise that every layer is finished or frozen.

## System Shape

`ActionShellScript` is organized as a staged pipeline with a few supporting subsystems:

1. Raw input capture records a `RecordingSession`.
2. Interpretation derives higher-level meaning from raw events.
3. Shaping rewrites interpreted events for downstream consumers.
4. Script generation renders shaped actions into script text.
5. Script documents become authoritative editable artifacts.
6. Playback derives executable plans from either a recording or a script document.
7. Runtime and debugging support script execution, stepping, and inspection.

The key architectural rule in the current codebase is source-of-truth separation:

- recording owns raw event truth
- interpretation owns derived meaning truth
- shaping owns downstream representation truth
- generated script text is derived until converted into a `ScriptDocument`
- playback always derives from one explicit authority source

## File-By-File Map

### Packaging and Project Entry

- [pyproject.toml](../../../pyproject.toml) defines the package metadata, runtime dependency on `pynput`, dev dependency on `pytest`, and the console entry points for every CLI command.
- [build_backend.py](../../../build_backend.py) is a custom PEP 517 backend that builds wheels and editable wheels and writes the metadata/entry-point payload.
- [ActionShellScript.code-workspace](../../../ActionShellScript.code-workspace) is the editor workspace definition.
- [requirements.txt](../../../requirements.txt) is the single editable-install wrapper for the current checkout. It delegates to the dependency metadata in [pyproject.toml](../../../pyproject.toml), which is the authoritative source for runtime and dev dependencies.
- [session.json](../../../session.json) is a captured raw session artifact, useful as data but not part of the code path.

### CLI Layer

- [apps/cli/main.py](../../../apps/cli/main.py) is the default `ass-record` entry point and delegates directly to the record command.
- [apps/cli/record_command.py](../../../apps/cli/record_command.py) implements phase 1 recording, stop-hotkey handling, and optional raw-session export.
- [apps/cli/interpret_command.py](../../../apps/cli/interpret_command.py) loads a saved raw session and prints interpreted-event summaries.
- [apps/cli/record_interpret_command.py](../../../apps/cli/record_interpret_command.py) combines live capture and interpretation in one command.
- [apps/cli/shape_command.py](../../../apps/cli/shape_command.py) performs interpretation plus shaping and prints shaped-action summaries.
- [apps/cli/generate_command.py](../../../apps/cli/generate_command.py) runs interpretation, shaping, and script generation, then prints or writes the resulting script text.
- [apps/cli/document_command.py](../../../apps/cli/document_command.py) converts generated script text into an authoritative `ScriptDocument` and runs document language services.
- [apps/cli/play_command.py](../../../apps/cli/play_command.py) builds and executes playback plans from either a recording session or a script document.
- [apps/cli/debug_command.py](../../../apps/cli/debug_command.py) runs a `ScriptDocument` through the debugger and prints live debug events.
- [apps/cli/interpretation_args.py](../../../apps/cli/interpretation_args.py) defines CLI flags for interpretation thresholds.
- [apps/cli/shaping_args.py](../../../apps/cli/shaping_args.py) defines CLI flags for shaping behavior.
- [apps/cli/generation_args.py](../../../apps/cli/generation_args.py) defines CLI flags for generation output and formatting.
- [apps/cli/session_json.py](../../../apps/cli/session_json.py) serializes `RecordingSession` objects into the raw JSON shape accepted by the interpretation commands.
- [apps/cli/interpretation_output.py](../../../apps/cli/interpretation_output.py) formats interpreted events for readable terminal output.
- [apps/cli/shaping_output.py](../../../apps/cli/shaping_output.py) formats shaped actions for readable terminal output.
- [apps/cli/__init__.py](../../../apps/cli/__init__.py) is the package marker for the CLI namespace.

### Application Services

- [application/recording_service.py](../../../application/recording_service.py) is the use-case wrapper around the recorder and exposes a stable summary DTO.
- [application/interpretation_service.py](../../../application/interpretation_service.py) wraps the interpretation pipeline and returns counts by interpreted event type.
- [application/shaping_service.py](../../../application/shaping_service.py) wraps the shaping pipeline and summarizes shaped output.
- [application/script_generation_service.py](../../../application/script_generation_service.py) wraps script generation and summarizes the generated result.
- [application/script_document_service.py](../../../application/script_document_service.py) converts generated text into a `ScriptDocument`, updates text, and marks documents saved.
- [application/script_document_language_service.py](../../../application/script_document_language_service.py) runs parse plus semantic diagnostics analysis over a `ScriptDocument`, including unsupported-call checks such as `SleepX(1000)`.
- [application/playback_service.py](../../../application/playback_service.py) orchestrates plan building and execution for preview/live playback.
- [application/debugging_service.py](../../../application/debugging_service.py) bootstraps a debug session around a document and runtime hooks.

### Phase 1 Recording

- [core/recording/recorder_config.py](../../../core/recording/recorder_config.py) stores capture toggles and the mouse-move threshold.
- [core/recording/input_capture.py](../../../core/recording/input_capture.py) defines the backend protocol for OS input capture and the thin adapter around it.
- [core/recording/recording_session.py](../../../core/recording/recording_session.py) is the authoritative raw-event session model with start/stop state.
- [core/recording/session_recorder.py](../../../core/recording/session_recorder.py) owns session lifecycle, timestamps raw events, and stores only raw recording data.
- [core/recording/event_normalizer.py](../../../core/recording/event_normalizer.py) defines a normalized event model, but it is currently separate from the authoritative raw-session path and appears reserved for later derived workflows.

### Phase 2 Interpretation

- [core/interpretation/interpretation_config.py](../../../core/interpretation/interpretation_config.py) contains thresholds for clicks, double-clicks, and drags.
- [core/interpretation/event_vocabulary.py](../../../core/interpretation/event_vocabulary.py) defines the interpreted-event dict contract and shared helper functions.
- [core/interpretation/interpreted_recording.py](../../../core/interpretation/interpreted_recording.py) is the phase 2 output container.
- [core/interpretation/click_interpreter.py](../../../core/interpretation/click_interpreter.py) collapses raw mouse button sequences into click or double-click events.
- [core/interpretation/drag_interpreter.py](../../../core/interpretation/drag_interpreter.py) annotates drag sequences after click collapse.
- [core/interpretation/keyboard_interpreter.py](../../../core/interpretation/keyboard_interpreter.py) annotates key holds and hotkey sequences.
- [core/interpretation/recording_interpreter.py](../../../core/interpretation/recording_interpreter.py) coordinates the interpretation passes in the current order.

### Phase 3 Shaping

- [core/shaping/shaping_config.py](../../../core/shaping/shaping_config.py) controls delay emission, mouse move cleanup, click simplification, and keyboard output style.
- [core/shaping/shaped_action_sequence.py](../../../core/shaping/shaped_action_sequence.py) defines the shaped-action container and common metadata helpers.
- [core/shaping/mouse_shaper.py](../../../core/shaping/mouse_shaper.py) removes or collapses mouse move actions.
- [core/shaping/click_shaper.py](../../../core/shaping/click_shaper.py) simplifies click actions when they stay within configured tolerances.
- [core/shaping/keyboard_shaper.py](../../../core/shaping/keyboard_shaper.py) normalizes keyboard actions and can collapse printable key holds into `text`.
- [core/shaping/delay_shaper.py](../../../core/shaping/delay_shaper.py) filters, clamps, and optionally collapses delay actions.
- [core/shaping/shaping_pipeline.py](../../../core/shaping/shaping_pipeline.py) runs the shaping passes in a fixed order.

### Phase 4 Script Generation

- [core/scripting/generation/script_generation_config.py](../../../core/scripting/generation/script_generation_config.py) controls generation headers, line endings, and delay emission.
- [core/scripting/generation/generated_script.py](../../../core/scripting/generation/generated_script.py) is the generated-script DTO.
- [core/scripting/generation/header_comment_renderer.py](../../../core/scripting/generation/header_comment_renderer.py) emits generated-script header comments.
- [core/scripting/generation/action_to_script_renderer.py](../../../core/scripting/generation/action_to_script_renderer.py) maps shaped actions to script lines.
- [core/scripting/generation/script_generation_pipeline.py](../../../core/scripting/generation/script_generation_pipeline.py) combines headers and body lines into final script text.
- [core/scripting/documents/script_document_factory.py](../../../core/scripting/documents/script_document_factory.py) converts generated text into an authoritative `ScriptDocument`.

### Core Scripting Frontend

- [core/scripting/tokens.py](../../../core/scripting/tokens.py) is the canonical token vocabulary and keyword/operator source of truth.
- [core/scripting/lexer.py](../../../core/scripting/lexer.py) tokenizes source text, handles strings/comments/numbers, and records lexical diagnostics.
- [core/scripting/ast_nodes.py](../../../core/scripting/ast_nodes.py) defines the AST node hierarchy and traversal helper.
- [core/scripting/parser.py](../../../core/scripting/parser.py) is the recursive-descent parser for statements, expressions, interpolation, spans, and recovery.
- [core/scripting/formatter.py](../../../core/scripting/formatter.py) is a text formatter for script documents, not a full AST renderer.
- [core/scripting/diagnostics.py](../../../core/scripting/diagnostics.py) centralizes diagnostics, spans, and source excerpt rendering.
- [core/scripting/__init__.py](../../../core/scripting/__init__.py) is currently empty.

### Editor and Document Authority

- [editor/document/document_version.py](../../../editor/document/document_version.py) provides monotonic document versioning.
- [editor/document/script_document.py](../../../editor/document/script_document.py) is the authoritative editable document model with dirty tracking and provenance metadata.
- [editor/document/document_selection.py](../../../editor/document/document_selection.py) is a deferred placeholder for future caret/selection state.
- [editor/language_services/parse_service.py](../../../editor/language_services/parse_service.py) parses a document into AST plus syntax diagnostics.
- [editor/language_services/diagnostics_service.py](../../../editor/language_services/diagnostics_service.py) returns parse-plus-semantic diagnostics for a document, reusing the current document snapshot.
- [editor/language_services/formatting_service.py](../../../editor/language_services/formatting_service.py) formats document text using the scripting formatter.

### Phase 6 Playback

- [core/playback/playback_mode.py](../../../core/playback/playback_mode.py) distinguishes preview and live playback.
- [core/playback/playback_request.py](../../../core/playback/playback_request.py) validates playback requests.
- [core/playback/playback_plan.py](../../../core/playback/playback_plan.py) stores the derived playback plan and its events.
- [core/playback/playback_result.py](../../../core/playback/playback_result.py) records execution success/failure, event counts, and derived console output.
- [core/playback/playback_events.py](../../../core/playback/playback_events.py) defines playback event dataclasses and converts shaped actions into executable events.
- [core/playback/playback_builder.py](../../../core/playback/playback_builder.py) is the facade for building plans from recording or script authority.
- [core/playback/playback_engine.py](../../../core/playback/playback_engine.py) runs a plan through an executor and returns a `PlaybackResult`.
- [core/playback/executors/input_executor.py](../../../core/playback/executors/input_executor.py) defines the executor protocol.
- [core/playback/executors/preview_input_executor.py](../../../core/playback/executors/preview_input_executor.py) captures executed events in memory for preview mode.
- [core/playback/executors/live_input_executor.py](../../../core/playback/executors/live_input_executor.py) turns playback events into host input operations.
- [core/playback/builders/from_recording_builder.py](../../../core/playback/builders/from_recording_builder.py) derives playback events from a recording by running interpretation, shaping, and event normalization.
- [core/playback/builders/from_script_builder.py](../../../core/playback/builders/from_script_builder.py) derives playback events and captured console output from script text through the runtime compiler.

### Runtime

- [core/runtime/execution_context.py](../../../core/runtime/execution_context.py) is the mutable runtime state container for variables, call stack, diagnostics, breakpoints, emitted playback events, and console output capture.
- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py) is the runtime/compiler shell used by playback and debugger execution, and it now cooperates with debugger hooks and stop events.
- [core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py) centralizes runtime error messages and helper text.
- [core/runtime/builtins/builtin_registry.py](../../../core/runtime/builtins/builtin_registry.py) defines the built-in function names recognized by the runtime.

### Debugging

- [core/debugging/debug_request.py](../../../core/debugging/debug_request.py) is the debug-session request DTO.
- [core/debugging/debug_event.py](../../../core/debugging/debug_event.py) defines debugger event kinds and payload shape.
- [core/debugging/debug_state.py](../../../core/debugging/debug_state.py) is the snapshot model for debugger UI/state consumers.
- [core/debugging/debug_session.py](../../../core/debugging/debug_session.py) tracks running and paused state plus breakpoint ownership.
- [core/debugging/debug_controller.py](../../../core/debugging/debug_controller.py) bridges document source, source maps, runtime callbacks, and debug-event emission.
- [core/debugging/runtime_debug_hooks.py](../../../core/debugging/runtime_debug_hooks.py) adapts runtime callbacks into controller notifications.
- [core/debugging/breakpoints.py](../../../core/debugging/breakpoints.py) stores line breakpoints for a document.
- [core/debugging/call_stack.py](../../../core/debugging/call_stack.py) stores and snapshots runtime call frames.
- [core/debugging/call_stack_snapshot.py](../../../core/debugging/call_stack_snapshot.py) defines immutable frame snapshots.
- [core/debugging/variable_snapshot.py](../../../core/debugging/variable_snapshot.py) defines immutable variable snapshots.
- [core/debugging/source_map.py](../../../core/debugging/source_map.py) maps AST nodes back to source lines and determines debuggable statement boundaries.

### Desktop Frontend Persistence

- [apps/desktop/main.py](../../../apps/desktop/main.py) is the Qt desktop entry point and now prepares platform-specific font and message-handler settings before the window launches.
- [apps/desktop/bootstrap.py](../../../apps/desktop/bootstrap.py) contains the desktop startup helpers for repo-path setup, Qt font-directory selection, and message filtering.
- [apps/desktop/settings.py](../../../apps/desktop/settings.py) defines the persisted `DesktopSettingsBundle`, which groups `application`, `playback`, `recording`, `files`, `diagnostics`, `runtime`, and `theme` settings into one configuration object.
- [apps/desktop/hotkeys.py](../../../apps/desktop/hotkeys.py) defines the desktop hotkey registry, including the debugger step, continue, and stop shortcuts surfaced in the preferences dialog.
- [apps/desktop/theme.py](../../../apps/desktop/theme.py) defines the nested `DesktopPreferences` model used by the `theme` section for appearance, scripting, and font settings.
- [apps/desktop/preferences_dialog.py](../../../apps/desktop/preferences_dialog.py) exposes the General, Appearance, Hotkeys, Playback, Recording, Files, Runtime, Diagnostics, and Debug preference pages, with General owning startup/workspace settings, Appearance splitting into `Editor`, `Style`, `Formatting`, and `Dirty State` tabs, Workspace owning the hidden-tab strip collapse default, formatted preview tab, summary sidebar placement, raw recordings tab, Analysis tab, and Diagnostics tab visibility controls, Hotkeys editing the full shortcut registry, Runtime owning the mouse-movement curve editor, preview toggle, and step controls, and Debug owning the `Open Run when paused` behavior for the Run Sidebar; the dialog also keeps the Diagnostics tab toggle synchronized across pages and edits a snapshot of the bundle rather than writing files directly.
- [apps/desktop/script_action_controller.py](../../../apps/desktop/script_action_controller.py) applies the current desktop playback, recording, and runtime settings to play and record actions.
- [apps/desktop/help_browser.py](../../../apps/desktop/help_browser.py) owns the built-in desktop help engine. It renders bundled markdown and HTML docs inside the app, provides a searchable table of contents, supports section-aware opening for built-in guides, and reuses the desktop theme palette for the browser chrome, topic highlights, and empty states.
- [apps/desktop/window.py](../../../apps/desktop/window.py) owns the desktop workbench window, loads and saves the desktop settings bundle, applies the active `theme` settings immediately, keeps the summary sidebar and workspace tabs aligned with the bundle, and propagates updated settings to the controller and debugger service.
- [apps/desktop/pixel_inspector_window.py](../../../apps/desktop/pixel_inspector_window.py) owns the Pixel Inspector tool. It uses Qt screen capture for the magnifier and pixel sampling, but the window handle/title readout depends on Win32 APIs (`WindowFromPoint` and `GetWindowTextW`) when the app is running on Windows.
- [application/persistence/desktop_settings_service.py](../../../application/persistence/desktop_settings_service.py) persists the desktop bundle to `desktop_settings.json` and automatically migrates legacy split preference files on first load.

### Infrastructure

- [infrastructure/debug_logger.py](../../../infrastructure/debug_logger.py) is the env-configured debug logging helper used across the repo.
- [infrastructure/input/pynput_backend.py](../../../infrastructure/input/pynput_backend.py) is the live input-capture backend for recording mouse/keyboard events and the stop-hotkey path.
- [infrastructure/input/pynput_playback_adapter.py](../../../infrastructure/input/pynput_playback_adapter.py) is the live playback adapter that drives OS input through `pynput`.

### Samples

- [samples/README.md](../../../samples/README.md) explains how the fixture recordings are used.
- [samples/click.json](../../../samples/click.json) is a simple click fixture.
- [samples/borderline_click_drag.json](../../../samples/borderline_click_drag.json) is the threshold-tuning fixture for click-vs-drag behavior.
- [samples/double_click.json](../../../samples/double_click.json) is a double-click fixture.
- [samples/drag.json](../../../samples/drag.json) is a drag fixture.
- [samples/hotkey_copy.json](../../../samples/hotkey_copy.json) is a hotkey fixture.

### Tests

- [tests/conftest.py](../../../tests/conftest.py) adds the repo root to test imports.
- [tests/test_build_backend.py](../../../tests/test_build_backend.py) covers packaging and backend behavior.
- [tests/recording/test_session_recorder.py](../../../tests/recording/test_session_recorder.py) covers recording lifecycle and raw-event storage.
- [tests/recording/test_pynput_backend.py](../../../tests/recording/test_pynput_backend.py) covers the recording backend behavior.
- [tests/recording/test_record_command.py](../../../tests/recording/test_record_command.py) covers the record CLI.
- [tests/recording/test_input_capture.py](../../../tests/recording/test_input_capture.py) covers the capture adapter contract.
- [tests/recording/test_recording_session.py](../../../tests/recording/test_recording_session.py) covers the raw session model.
- [tests/recording/test_recorder_config.py](../../../tests/recording/test_recorder_config.py) covers recorder config validation.
- [tests/recording/fakes.py](../../../tests/recording/fakes.py) provides recording test doubles.
- [tests/interpretation/test_click_interpreter.py](../../../tests/interpretation/test_click_interpreter.py) covers click and double-click recognition.
- [tests/interpretation/test_drag_interpreter.py](../../../tests/interpretation/test_drag_interpreter.py) covers drag annotation.
- [tests/interpretation/test_keyboard_interpreter.py](../../../tests/interpretation/test_keyboard_interpreter.py) covers key hold and hotkey annotation.
- [tests/interpretation/test_recording_interpreter.py](../../../tests/interpretation/test_recording_interpreter.py) covers interpretation pipeline ordering.
- [tests/interpretation/test_interpretation_service_cli.py](../../../tests/interpretation/test_interpretation_service_cli.py) covers the interpretation service/CLI interaction.
- [tests/interpretation/test_record_interpret_command.py](../../../tests/interpretation/test_record_interpret_command.py) covers the combined live record plus interpret command.
- [tests/interpretation/test_sample_fixtures.py](../../../tests/interpretation/test_sample_fixtures.py) validates fixture behavior.
- [tests/shaping/test_mouse_shaper.py](../../../tests/shaping/test_mouse_shaper.py) covers mouse shaping rules.
- [tests/shaping/test_click_shaper.py](../../../tests/shaping/test_click_shaper.py) covers click simplification.
- [tests/shaping/test_keyboard_shaper.py](../../../tests/shaping/test_keyboard_shaper.py) covers keyboard collapse and text shaping.
- [tests/shaping/test_delay_shaper.py](../../../tests/shaping/test_delay_shaper.py) covers delay filtering and collapse.
- [tests/shaping/test_shape_command.py](../../../tests/shaping/test_shape_command.py) covers the shaping CLI.
- [tests/shaping/test_shaping_pipeline.py](../../../tests/shaping/test_shaping_pipeline.py) covers the shaping orchestration.
- [tests/generation/test_header_comment_renderer.py](../../../tests/generation/test_header_comment_renderer.py) covers generation header comments.
- [tests/generation/test_action_to_script_renderer.py](../../../tests/generation/test_action_to_script_renderer.py) covers action-to-script mapping.
- [tests/generation/test_script_generation_pipeline.py](../../../tests/generation/test_script_generation_pipeline.py) covers generation orchestration.
- [tests/generation/test_script_generation_service.py](../../../tests/generation/test_script_generation_service.py) covers the generation service wrapper.
- [tests/generation/test_generate_command.py](../../../tests/generation/test_generate_command.py) covers the generation CLI.
- [tests/generation/test_document_command.py](../../../tests/generation/test_document_command.py) covers the document-conversion CLI.
- [tests/unit/test_script_document.py](../../../tests/unit/test_script_document.py) covers the document model.
- [tests/unit/test_script_document_versioning.py](../../../tests/unit/test_script_document_versioning.py) covers version increments.
- [tests/unit/test_script_document_service.py](../../../tests/unit/test_script_document_service.py) covers document-service behavior.
- [tests/unit/test_script_document_language_service.py](../../../tests/unit/test_script_document_language_service.py) covers parse and diagnostics integration.
- [tests/unit/test_script_document_factory.py](../../../tests/unit/test_script_document_factory.py) covers generated-script conversion.
- [tests/unit/test_phase_5_document_flow.py](../../../tests/unit/test_phase_5_document_flow.py) covers the phase 5 authority flow.
- [tests/unit/test_parse_service.py](../../../tests/unit/test_parse_service.py) covers document parsing.
- [tests/unit/test_formatting_service.py](../../../tests/unit/test_formatting_service.py) covers document formatting.
- [tests/unit/test_diagnostics_service.py](../../../tests/unit/test_diagnostics_service.py) covers diagnostics lookup.
- [tests/unit/test_script_formatter.py](../../../tests/unit/test_script_formatter.py) covers the formatter directly.
- [tests/unit/test_scripting_spans.py](../../../tests/unit/test_scripting_spans.py) covers span handling.
- [tests/playback/test_playback_events.py](../../../tests/playback/test_playback_events.py) covers playback event modeling and normalization.
- [tests/playback/test_playback_builders.py](../../../tests/playback/test_playback_builders.py) covers building plans from recordings and scripts.
- [tests/playback/test_playback_execution.py](../../../tests/playback/test_playback_execution.py) covers the playback engine.
- [tests/playback/test_play_command.py](../../../tests/playback/test_play_command.py) covers the playback CLI.

## Current Architectural Boundaries

- Recording is the only source of raw event truth.
- Interpretation is a pure derivation layer over raw recording.
- Shaping is another pure derivation layer and does not mutate interpretation.
- Generated script text is derived output until it is converted into `ScriptDocument`.
- Playback is source-specific and never guesses whether the authority is recording or script.
- The scripting frontend is canonical for lexing, parsing, diagnostics, and formatting of document text, and semantic analysis now rejects unsupported function calls while still allowing builtins and declared user functions.
- The runtime compiler path now participates in live debugging through debugger hooks and a live `DebugSession`.
- The debugger subsystem is wired end-to-end for the `ScriptDocument -> ScriptRuntime -> RuntimeDebugHooks -> DebugSession -> CLI` path.

## Notes For Future Updates

- This snapshot should be revised when the runtime execution methods are filled in, when document/editor interaction grows, or when the playback source-of-truth rules change.
- `core/recording/event_normalizer.py` and `editor/document/document_selection.py` are good markers for future architectural change.
- The docs under `docs/internal/architecture/` are the best place to keep the phase-boundary truth aligned with implementation.

