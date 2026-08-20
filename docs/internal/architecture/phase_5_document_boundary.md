# Phase 5 Script-Document Boundary

Phase 5 is the point where script text can become editable authority.

That transfer is explicit.

- Before conversion, `GeneratedScript` is derived output from shaping.
- After conversion, `ScriptDocument` is the only editable script authority for the document workflow.
- Parse, diagnostics, and formatting services run against `ScriptDocument.text`.
- Regeneration must not silently replace document text after conversion.

## Authority Transfer

The transfer happens only through an explicit conversion step such as `ass-open-script`.

That step can use one of two explicit modes:

- `promote_generated` interprets, shapes, generates, and then converts the generated script text into a `ScriptDocument`
- `direct_import` performs a minimal translation from `RecordingSession` into `ScriptDocument`

In either mode, the step:

1. creates a `ScriptDocument`
2. copies in the chosen converted text
3. preserves source provenance from the recording flow
4. starts document lifecycle state at a clean saved revision

After that point, the document owns:

- current editable text
- version state
- dirty state

The generated script remains useful provenance in the generated-conversion path, but it is no longer the live source of truth.

## Lifecycle Contract

Phase 5 keeps the document lifecycle intentionally small:

- `replace_text()` updates text, advances version, and marks the document dirty
- replacing identical text is a no-op
- `mark_saved()` clears dirty state without rewriting text

`DocumentVersion` is intentionally part of the current phase-5 contract. It stays because the repo is already modeling revision state explicitly, and summaries flatten it to an integer for CLI-facing output.

## Language-Service Contract

Phase-5 language services are document consumers, not document owners.

- `ParseService` reads `ScriptDocument.text` and returns a parsed root plus syntax diagnostics
- `DiagnosticsService` derives parse-plus-semantic diagnostics from document text, including unsupported function calls like `SleepX(1000)`
- `FormattingService` returns formatted text without mutating the document unless a caller explicitly writes that text back

This keeps the authority boundary clean: services analyze or transform document text, but the caller decides whether to apply results.

## Deferred Work

Phase 5 is still CLI-first.

Still deferred:

- caret state
- selection ranges
- interactive editor behavior
- UI-only document state

`editor/document/document_selection.py` remains a deferred note on purpose and does not represent incomplete phase-5 implementation.

## Desktop Editing Contract

The desktop editor is the user-facing place where converted script text becomes customizable automation.

The intended workflow is:

- convert a recording into `ScriptDocument`
- edit the script text
- keep the edited text as the authoritative source for script workflow
- hand that script text to playback without replacing it behind the user's back

The document workflow must not be reduced to "has replay events" or "has visible output." A `ScriptDocument` may be valid even when it currently compiles to no playback events.

## Promotion and Editing Expectations

After conversion:

- `ScriptDocument` is the editable authority
- the editor may freely modify the document text
- the document lifecycle remains separate from playback execution
- parse, diagnostics, and formatting continue to operate on `ScriptDocument.text`

The UI must not silently reintroduce generated text or other derived content as if it were new source authority.
