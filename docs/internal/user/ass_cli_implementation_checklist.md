# `ass-cli` Shipped Checklist

This page records the implementation that shipped for the `ass-cli` front-end. It is historical by design and is kept as a completion record, not an open task list.

## 1. Front-end contract

- [x] The public form is `ass-cli <subcommand> [--input PATH] [--output PATH] [shared flags...]`.
- [x] The canonical subcommands are `record`, `interpret`, `record-interpret`, `shape`, `generate`, `open-script`, `play`, `debug`, `filter-recording`, `filter-interpretation`, `filter-shaping`, and `filter-document`.
- [x] `--input` is the standard file input flag for the front-end.
- [x] `--output` is the standard file output flag for the front-end.
- [x] `play` uses `recording <path>` or `script <path>` so the source kind is selected before the path.

What shipped:

- The contract was documented in one place before rollout.
- The front-end keeps file-bearing commands and file-free commands visually distinct.

## 2. Dispatcher entry point

- [x] A dedicated `ass-cli` entry point and module target exists.
- [x] The top-level subcommand is parsed before backend-specific parsing occurs.
- [x] Each subcommand routes through a dedicated adapter function.
- [x] Exit-code behavior remains delegated to the underlying command runners.

What shipped:

- `ass-cli --help` shows the front-end and its subcommands.
- Unknown subcommands fail cleanly through argparse validation.
- Backend logic is not executed before the subcommand is validated.

## 3. Argument translation

- [x] Adapter functions exist for each front-end subcommand.
- [x] `--input` is translated into the backend positional file argument where needed.
- [x] `--output` is translated into the backend output flag or file write path.
- [x] Shared flags are translated into backend command flags without changing behavior.
- [x] `record` stays input-free.
- [x] `play` stays authority-based with an explicit source selector.

What shipped:

- Every front-end subcommand reaches the existing backend module with the expected arguments.
- The translation layer preserves command semantics.
- File-based commands can be invoked through `ass-cli` without exposing backend positional quirks.

## 4. Shared flag groups

- [x] The recording capture flag group is wired for `record` and `record-interpret`.
- [x] The interpretation tuning flag group is wired for `interpret`, `record-interpret`, `shape`, `generate`, and `open-script`.
- [x] The shaping controls are wired for `shape`, `generate`, and `open-script`.
- [x] The generation controls are wired for `generate` and `open-script`.
- [x] The playback controls are wired for `play`.
- [x] The debug controls are wired for `debug`.
- [x] The filter controls are wired for all `filter-*` commands.

What shipped:

- Each flag group behaves through `ass-cli` the same way the backend already does.
- No front-end subcommand requires a special-case file or shared-flag style.

## 5. Compatibility

- [x] The existing `ass-*` commands remain available.
- [x] Legacy commands are still exposed directly during and after migration.
- [x] Existing scripts and documentation can continue using the legacy commands.

What shipped:

- Existing direct command usage continues to work.
- `ass-cli` can be adopted incrementally.
- No backend command had to be renamed as part of the front-end rollout.

## 6. Tests

- [x] Parser tests cover the `ass-cli` subcommand surface.
- [x] Translation tests verify that front-end flags become the expected backend arguments.
- [x] Smoke tests cover the main workflows.
- [x] Negative tests cover invalid subcommands, missing required flags, and invalid `play` authority choices.
- [x] Profile-listing tests cover the filter commands.

Smoke coverage that shipped:

- [x] `ass-cli record`
- [x] `ass-cli record --no-save`
- [x] `ass-cli record --save-raw session.json`
- [x] `ass-cli interpret --input session.json`
- [x] `ass-cli shape --input session.json --show-actions`
- [x] `ass-cli generate --input session.json --output generated.ass`
- [x] `ass-cli open-script --input session.json --output authoritative.ass`
- [x] `ass-cli play recording session.json --mode preview`
- [x] `ass-cli debug --input generated.ass --step`
- [x] `ass-cli filter-recording --input session.json --profile clean`

What shipped:

- The major subcommands are covered by passing tests.
- Translation tests lock in the front-end contract.
- Invalid invocations fail with predictable errors.

## 7. Documentation

- [x] The docs include a short `ass-cli` overview.
- [x] The docs index links the spec and implementation checklist.
- [x] Quick-start examples prefer `ass-cli`.
- [x] Legacy command docs remain available as implementation references.
- [x] The docs note that the backend commands remain available.

What shipped:

- Users can find `ass-cli` documentation from the docs landing page.
- The canonical `ass-cli` form is shown first.
- The docs do not imply the old commands were removed.

## 8. Rollout

- [x] `ass-cli` shipped with the existing commands still intact.
- [x] The front-end was validated on the main workflows.
- [x] Feedback was collected on awkward subcommand or flag names during rollout.
- [x] The front-end contract was left open to later refinement if usage revealed a real problem.

What shipped:

- The front-end is usable without backend refactors.
- Any follow-up cleanup could happen after the new entry point had proven stable.

## Implementation Order

The order below reflects the path that was taken to deliver the shipped front-end:

1. Add the dispatcher.
2. Implement `interpret` and `generate`.
3. Implement `play` and `debug`.
4. Implement the filter commands.
5. Implement the record pipeline commands.
6. Add tests.
7. Update docs.
