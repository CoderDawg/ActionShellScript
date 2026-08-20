# `ass-cli` Migration Plan

This plan describes how to add `ass-cli` as a thin front-end over the existing `ass-*` commands without replacing or destabilizing them.

## Objective

- Add one consistent user-facing entry point.
- Keep the existing command modules intact.
- Normalize file input and output handling at the front-end layer.
- Preserve direct use of the existing `ass-*` commands during migration.

## Migration Strategy

### Phase 1: Define the front-end contract

Lock the user-facing shape to:

```powershell
ass-cli <subcommand> [--input PATH] [--output PATH] [shared flags...]
```

Playback uses the source-first form:

```powershell
ass-cli play recording path\to\session.json
ass-cli play script path\to\document.ass
```

Decide the final front-end names and shared flag groups before wiring implementation:

- `record`
- `interpret`
- `record-interpret`
- `shape`
- `generate`
- `open-script`
- `play`
- `debug`
- `filter-recording`
- `filter-interpretation`
- `filter-shaping`
- `filter-document`

### Phase 2: Add a dispatcher layer

Implement a new front-end module that:

- parses the top-level subcommand
- normalizes `--input`, `--output`, and shared flags
- maps the request onto the existing command modules
- exits with the same style of status codes the backend commands already use

This layer should be the only new public CLI entry point needed for v1.

### Phase 3: Build command adapters

Add small adapter functions that translate the front-end contract into the current command arguments.

Suggested mapping:

| Front-end subcommand | Backend target |
|---|---|
| `record` | `apps.cli.record_command.run` |
| `interpret` | `apps.cli.interpret_command.run` |
| `record-interpret` | `apps.cli.record_interpret_command.run` |
| `shape` | `apps.cli.shape_command.run` |
| `generate` | `apps.cli.generate_command.run` |
| `open-script` | `apps.cli.document_command.run` |
| `play` | `apps.cli.play_command.run` |
| `debug` | `apps.cli.debug_command.run` |
| `filter-recording` | `apps.cli.filter_recording_command.run` |
| `filter-interpretation` | `apps.cli.filter_interpretation_command.run` |
| `filter-shaping` | `apps.cli.filter_shaping_command.run` |
| `filter-document` | `apps.cli.filter_document_command.run` |

The adapters should translate front-end flags into the current command-specific flag sets, including any positional arguments that remain in the backend for now. For playback, the source kind must be translated into the leading `recording` or `script` token and the source path must remain positional.

### Phase 4: Skip compatibility aliases

Do not add a dual-form alias layer for `ass-cli`.

- canonical user-facing form: `ass-cli <subcommand> ...`
- legacy direct commands: `ass-record`, `ass-interpret`, and so on

The legacy commands can remain as separate entry points, but the docs and examples should treat `ass-cli` as the canonical interface instead of presenting a compatibility alias path.

### Phase 5: Add tests

Add coverage at three levels:

1. Front-end parsing tests
2. Flag translation tests
3. End-to-end smoke tests against the existing backend modules

Useful test cases:

- `ass-cli record`
- `ass-cli record --no-save`
- `ass-cli record --save-raw session.json`
- `ass-cli interpret --input session.json`
- `ass-cli generate --input session.json --output generated.ass`
- `ass-cli play recording session.json --mode preview`
- `ass-cli debug --input generated.ass --step`
- filter commands with and without `--list-profiles`

### Phase 6: Update docs

Document the new front-end in the user docs and keep the old command pages as the underlying implementation reference.

Recommended docs updates:

- add an `ass-cli` quickstart page with common examples
- add `ass-cli` overview and examples
- add the front-end spec
- add a short migration note that the legacy commands remain available
- update quick-start examples to prefer `ass-cli`

### Phase 7: Roll out gradually

Use a staged rollout:

1. Add the front-end and leave existing commands untouched.
2. Update docs and examples to prefer `ass-cli`.
3. Collect feedback on the front-end contract.
4. Adjust the translation layer if any command feels awkward.
5. Only consider backend cleanup after the front-end has proven stable.

## Recommended Implementation Order

1. Add the top-level dispatcher.
2. Implement the adapter for one simple command, such as `interpret`.
3. Add a second simple command, such as `generate`.
4. Add `play` and `debug`, since they validate the source-selection pattern.
5. Add the filter commands.
6. Add the record pipeline commands.
7. Finish with docs and compatibility polish.

## Design Notes

- The front-end should be thin, not a rewrite.
- The backend commands can remain somewhat uneven internally as long as `ass-cli` presents one consistent contract.
- `play` is the only subcommand that truly needs explicit authority selection, so the source kind must appear before the source path.
- `record` should remain input-free because it captures live data rather than consuming a file.
