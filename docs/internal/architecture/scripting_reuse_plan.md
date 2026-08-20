# Scripting Reuse Plan

This document turns the scripting reuse guidance into a phase-by-phase migration plan for `ActionShellScript`.

It complements the north-star architecture by answering a narrower question:

- which scripting files should move over
- when each file becomes necessary
- whether each file should be kept, refactored, split, or deferred

## Reuse Summary

| Existing file | ASS target file | Reuse level | Action |
| --- | --- | --- | --- |
| `packages/app_core/scripting/ast_nodes.py` | `core/scripting/ast_nodes.py` | High | Refactor lightly |
| `packages/app_core/scripting/diagnostics.py` | `core/scripting/diagnostics.py` | High | Refactor lightly |
| `packages/app_core/scripting/tokens.py` | `core/scripting/tokens.py` | High | Keep mostly as-is |
| `packages/app_core/scripting/lexer.py` | `core/scripting/lexer.py` | High | Refactor lightly |
| `packages/app_core/scripting/parser.py` | `core/scripting/parser.py` | High | Refactor |
| `packages/app_core/scripting/formatter.py` | `core/scripting/formatter.py` | Medium | Refactor |
| `packages/app_core/scripting/script_generator.py` | `core/scripting/generation/action_to_script_renderer.py` and `core/scripting/generation/script_generation_pipeline.py` | Medium | Split |
| `packages/app_core/scripting/script_export_pipeline.py` | `core/scripting/generation/script_generation_pipeline.py` and shaping-side support | Low to Medium | Split heavily |
| Source-line helpers in `packages/app_core/runtime/script_runtime.py` | `core/debugging/source_map.py` | Medium | Move or extract |
| No clean existing single file | `core/scripting/language_definition.py` | N/A | New file needed later |
| No clean existing single file | `core/scripting/source_text.py` | N/A | New file needed later |
| No clean existing single file | `core/scripting/documents/script_document_factory.py` | N/A | New file needed |

## Phase 1: Recording Slice

### Goal
Get recording working without dragging in scripting complexity.

### Bring Over
None of the scripting files yet.

### Why
Phase 1 should stand on the recording slice only:

- `RecordingSession`
- `SessionRecorder`
- `InputCapture`
- `PynputCaptureBackend`
- `RecordingService`

### Do Not Bring Over Yet
- `tokens.py`
- `lexer.py`
- `parser.py`
- `ast_nodes.py`
- `diagnostics.py`
- `formatter.py`
- generation and export files

## Phase 2: Interpretation Slice

### Goal
Derive `InterpretedRecording` from `RecordingSession`.

### Bring Over
None of the scripting files yet.

### Why
Interpretation still belongs to the recording-side workflow. It should not depend on the scripting frontend.

### Do Not Bring Over Yet
- all scripting frontend files
- `formatter.py`
- generation and export files

## Phase 4: Script Generation Slice

### Goal
Generate executable `GeneratedScript` from `ShapedActionSequence`.

### Bring Over First
- `packages/app_core/scripting/tokens.py -> core/scripting/tokens.py`
- `packages/app_core/scripting/ast_nodes.py -> core/scripting/ast_nodes.py`
- `packages/app_core/scripting/diagnostics.py -> core/scripting/diagnostics.py`

### Bring Over Next
- `packages/app_core/scripting/formatter.py -> core/scripting/formatter.py`

Use this as a medium-reuse file. It is helpful, but it should eventually be less coupled to generation internals.

### Reuse Partially and Split
- `packages/app_core/scripting/script_generator.py`

Split its responsibilities into:

- `core/scripting/generation/action_to_script_renderer.py`
- `core/scripting/generation/script_generation_pipeline.py`

### Do Not Bring Over Directly
- `packages/app_core/scripting/script_export_pipeline.py`

Mine it for ideas only. Do not port it wholesale into ASS because it mixes concerns that the new architecture now separates.

### Why These Files Now
At phase 4, ASS needs:

- script text rendering
- diagnostics and span-friendly types
- optional formatting support for generated text
- generation pipeline structure that is downstream of shaping
- one real consumer path for preview/export, exposed through `ass-generate`

### Can Stay Deferred
- `lexer.py`
- `parser.py`
- `language_definition.py`
- `source_text.py`
- `core/debugging/source_map.py`

Phase 4 can still use direct action-to-text rendering. That is now an intentional contract, not provisional output, and it remains downstream of shaping rather than becoming editable script authority.

## Phase 5: Script Document and Editor Slice

### Goal
Promote `GeneratedScript` into an editable `ScriptDocument` and support parsing, diagnostics, and formatting workflows.

### Bring Over Now
- `packages/app_core/scripting/tokens.py -> core/scripting/tokens.py`
- `packages/app_core/scripting/lexer.py -> core/scripting/lexer.py`
- `packages/app_core/scripting/parser.py -> core/scripting/parser.py`
- `packages/app_core/scripting/ast_nodes.py -> core/scripting/ast_nodes.py`
- `packages/app_core/scripting/diagnostics.py -> core/scripting/diagnostics.py`

### Bring Over and Refactor Now
- `packages/app_core/scripting/formatter.py -> core/scripting/formatter.py`

By phase 5, formatting should align more cleanly with `ScriptDocument`, AST-based workflows, and editor services.

### Add New Supporting Files
- `core/scripting/documents/script_document_factory.py`
- `editor/document/script_document.py`
- `editor/language_services/parse_service.py`
- `editor/language_services/diagnostics_service.py`
- `editor/language_services/formatting_service.py`

### New File Needed Now
- `core/debugging/source_map.py`

This should become the home for source-location resolution instead of leaving those rules buried inside runtime glue.

### Optional New Support Files
- `core/scripting/language_definition.py`
- `core/scripting/source_text.py`

These are useful once language policy or source-identity concerns start scattering, but they are not day-one requirements for phase 5.

### Why These Files Now
Phase 5 is where script text becomes authoritative. That means:

- parsing matters
- diagnostics matter
- formatting matters
- source spans matter
- editor services need a stable scripting frontend

## Recommended Import Order

If the scripting files are brought into ASS incrementally, use this order:

1. `diagnostics.py`
2. `tokens.py`
3. `ast_nodes.py`
4. `lexer.py`
5. `parser.py`
6. `formatter.py`
7. split generation logic from `script_generator.py`

This order minimizes dependency pain and gets the scripting frontend core in place before higher-level helpers.

## What To Avoid

Do not bring these over too early:

- `script_export_pipeline.py` as a whole
- playback-bridging code mixed into scripting concerns
- debugger-coupled source lookup logic left inside runtime
- milestone-era scaffolding that does not have a clear migration path

## Practical Recommendation

For the early ASS migration:

- phase 1 and phase 2 should keep scripting out
- phase 4 should bring in only enough scripting to generate text cleanly
- phase 5 should bring in the full scripting frontend stack and make it the basis of editor authority
