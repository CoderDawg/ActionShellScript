# Phase-5 Completion Checklist

Use this checklist to finish the phase-5 script-document and editor-services slice in ActionShellScript (ASS).

## Goal

Phase 5 is complete when the repo can explicitly convert a `GeneratedScript` into a `ScriptDocument`, treat that document as the new editable authority, and run parse, diagnostics, and formatting services against document text without requiring a GUI editor.

## Current phase-5 scope

Phase 5 is still CLI-first.

In scope:

- conversion from `GeneratedScript` to `ScriptDocument`
- document lifecycle behavior
- parse, diagnostics, and formatting services over document text
- end-to-end proof that script authority has transferred

Explicitly deferred:

- editor caret state
- selection ranges
- visual editor interactions
- UI-only document state

`editor/document/document_selection.py` is intentionally deferred and must not count as incomplete work for CLI-first phase-5 progress.

## 1. Add a real conversion path from `GeneratedScript` to `ScriptDocument`

- Add at least one workflow that explicitly converts generated script into a document.
- Confirm the converted result is a `ScriptDocument`.
- Confirm that after conversion, document text is the active script authority.
- Confirm later language services operate on `ScriptDocument.text`, not on generated script text.

Done when:
- Authority transfer is real and observable, not just a factory method on disk.
- The repo has one practical phase-5 entry path.

## 2. Lock the phase-5 boundary

- Confirm `GeneratedScript` stays derived and non-authoritative until conversion.
- Confirm `ScriptDocument` becomes authoritative only after explicit conversion.
- Confirm parse, diagnostics, and formatting services consume `ScriptDocument`.
- Confirm UI-only editor state is still out of scope for this phase.

Done when:
- The repo has one clear editable authority after conversion.
- CLI-first phase-5 work is separated cleanly from later UI/editor interaction work.

## 3. Test the document model and conversion flow

- Add dedicated tests for `editor/document/script_document.py`.
- Add dedicated tests for `core/scripting/documents/script_document_factory.py`.
- Add dedicated tests for `application/script_document_service.py`.
- Verify in tests that:
  - conversion preserves provenance fields
  - `replace_text()` increments version and marks dirty
  - replacing identical text does not advance version
  - `mark_saved()` clears dirty
  - summaries flatten document version correctly

Done when:
- Document lifecycle behavior is covered and stable.
- Promotion into document authority is proven by tests.

## 4. Test parse and diagnostics services against `ScriptDocument`

- Add tests for `editor/language_services/parse_service.py`.
- Add tests for `editor/language_services/diagnostics_service.py`.
- Verify parsing runs from `ScriptDocument.text`.
- Verify diagnostics are produced from document text, not generated-script text.
- Verify these services do not mutate the document.

Done when:
- Phase-5 language services are proven to run against the new authority source.

## 5. Verify formatting service in the document-authority path

- Add or extend tests for `editor/language_services/formatting_service.py`.
- Confirm formatting consumes `ScriptDocument.text`.
- Confirm formatting does not silently mutate the document unless a caller explicitly writes the result back.
- Decide whether formatting returns text only or whether a later service will apply the formatted text to a document.

Done when:
- Formatting fits the phase-5 document-authority model cleanly.

## 6. Wire `DocumentVersion` in cleanly or remove it

- Decide whether `DocumentVersion` is part of the real phase-5 contract.
- If yes, wire it into `ScriptDocument` and related summaries cleanly.
- If no, remove it until it is genuinely needed.

Done when:
- Document revision state is either intentionally typed or intentionally simple.
- There is no dead versioning scaffolding in the phase-5 contract.

## 7. Keep `document_selection.py` explicitly deferred

- Leave only a deferred note in `editor/document/document_selection.py`.
- Do not treat selection state as part of phase-5 completion.
- Do not add selection or caret state just to make the phase look fuller.

Done when:
- The repo makes it explicit that selection is a later UI/editor concern.
- Selection state no longer appears as open CLI-first work.

## 8. Add one end-to-end phase-5 proof path

- Add a CLI or test-harness path like:
  - `GeneratedScript -> ScriptDocument -> parse -> diagnostics -> format`
- Confirm this path proves document authority has transferred.
- Confirm the flow is usable without a GUI editor.

Done when:
- Phase 5 is a real vertical slice, not just a set of document-related classes.

## 9. Add phase-5 docs

- Add a short phase-5 boundary note if needed.
- Link the phase-5 checklist from the architecture docs.
- Update docs-root messaging once phase 5 is truly in place.
- State clearly that selection/editor UI state is deferred.

Done when:
- The docs explain document-authority transfer clearly.
- CLI-first phase-5 scope is visible and honest.

## Recommended implementation order

1. Add a real conversion path from `GeneratedScript` to `ScriptDocument`.
2. Lock the phase-5 boundary.
3. Add tests for document model, factory, and service.
4. Add tests for parse and diagnostics services.
5. Verify formatting service in the document-authority path.
6. Wire `DocumentVersion` in cleanly or remove it.
7. Keep `document_selection.py` explicitly deferred.
8. Add one end-to-end phase-5 proof path.
9. Add phase-5 docs and links.

## Exit criteria for Phase 5

- `GeneratedScript` can be explicitly converted into a `ScriptDocument`.
- `ScriptDocument` is the clear editable authority after conversion.
- Document lifecycle behavior is tested.
- Parse, diagnostics, and formatting services operate on `ScriptDocument`.
- `DocumentVersion` is either wired in cleanly or intentionally removed.
- `document_selection.py` is explicitly deferred and does not count as incomplete CLI-first work.
- At least one end-to-end phase-5 proof path exists.
- The docs explain the authority transfer clearly.
