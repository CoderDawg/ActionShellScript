# ActionShellScript

ActionShellScript is a Python app for recording input, interpreting it into higher-level actions, shaping that output, generating script text, promoting scripts into editable `ScriptDocument` authority, playing scripts back, and debugging runtime execution.

The project is organized as a phase-based pipeline:

1. Raw recording capture
2. Interpretation
3. Shaping
4. Script generation
5. Document authority
6. Playback
7. Debugging

## Install

From the repository root:

```powershell
python -m pip install -r requirements.txt
```

That `requirements.txt` shim is the simplest install path. It is the same as running `python -m pip install -e .[dev]`, so it installs the current checkout in editable mode and includes the declared test dependency. Working tree changes are picked up immediately.

## Packaging

To print the current packaging notes without running the release pipeline, use:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -PackagingNotesOnly
```

This shows the project version, Git tag, installer/file version, and SHA256 for `ActionShellScript-Setup.exe`.

## Licensing

ActionShellScript is intended to be released under the [MIT License](LICENSE). Third-party dependencies and bundled assets remain under their own licenses; see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for the current summary.

Packaged releases also include a shorter [NOTICE](NOTICE) file for redistribution bundles.

The main runtime licensing considerations are `PySide6` and `pynput`, which are LGPL-based. `PyInstaller` is used only as a bundling tool, and `qtawesome` is MIT licensed but may include icon/font assets with separate upstream notices.

## Run

### CLI

Use the unified front-end for common workflows:

```powershell
ass-cli record --save-raw .\session.json
ass-cli record --no-save
ass-cli interpret
ass-cli shape --show-actions
ass-cli generate --output .\generated.ass
ass-cli open-script --output .\authoritative.ass
ass-cli play recording --mode preview
ass-cli debug --input .\generated.ass --step
```

`ass-cli record --save-raw .\session.json` starts the common record-then-process workflow by writing raw session JSON. The downstream raw-session commands now default to `.\session.json`, so `ass-cli interpret`, `ass-cli shape`, `ass-cli generate`, `ass-cli open-script`, and `ass-cli play recording` all work without an explicit input path when you want the default session file. `ass-cli record --no-save` still restores the older in-memory-only behavior.

The legacy `ass-*` commands are still available directly, including:

- `ass-record`
- `ass-interpret`
- `ass-record-interpret`
- `ass-shape`
- `ass-generate`
- `ass-open-script`
- `ass-cli play`
- `ass-debug`

### GUI

Launch the desktop workbench with:

```powershell
ass-gui
```

The GUI opens the Qt-based document workbench for editing, analyzing, formatting, saving, playing, and debugging `ScriptDocument` files. It also exposes the summary sidebar, workspace tab visibility controls, preview-play actions, and breakpoint-aware debugger controls.

Launch the standalone help browser with:

```powershell
ass-help
```

The help browser can stay open while the main workbench is minimized or closed, and it can also be launched on its own without starting the full desktop workbench.

The search sidebar includes `Next` and `Previous` buttons for one-step navigation. The `Previous direction` checkbox switches button-driven search and replace operations to the previous match, so the replace button and menu action read `Replace Next` or `Replace Previous` to match the active direction. `Replace All` still applies to every match in the current search range.

Search menu icons are used as direction hints: `Next` uses a redo-style glyph, `Find Previous` uses an undo-style glyph, the selection-scoped search items use search/navigation glyphs, and replace actions use replace glyphs.

## Project Layout

- `apps/cli/` contains the command entry points and the `ass-cli` dispatcher.
- `apps/desktop/` contains the Qt desktop workbench.
- `application/` contains use-case services.
- `core/` contains recording, interpretation, shaping, scripting, playback, runtime, and debugging logic.
- `editor/` contains document models and language services.
- `infrastructure/` contains persistence and input adapters.
- `docs/` contains the detailed documentation set.
- `samples/` contains fixture recordings and example inputs.
- `tests/` contains the automated test suite.

## Documentation

- [Docs landing page](docs/index.md)
- [ass-cli spec](docs/user/ass_cli_spec.md)
- [ass-cli quickstart](docs/user/ass_cli_quickstart.md)
- [Language Reference](docs/user/language_reference.md)
- [Struct and DLL quickstart](docs/user/struct_and_dll_quickstart.md)
- [Monitor Info demo](samples/monitor_info_demo.ass)
- [ReadFile demo](samples/read_file_demo.ass)
- [GUI preference spec](docs/user/gui_preference_spec.md)
- [SendKeys Key Tap Transport Demo](samples/README.md#sendkeys-key-tap-transport-demo)

## Useful Notes

- `ass-cli` is the recommended front-end for day-to-day use.
- A recording remains raw session JSON until it is explicitly converted into a `ScriptDocument`.
- When a converted `.ass` file still carries provenance, writing it also writes a same-name `.ass.meta.json` sidecar. The `.ass` body keeps the short human-readable provenance header for `recording_conversion_route` and `source_capture_excluded_main_window`, while the sidecar keeps the full provenance payload, including `source_session_id`, `source_action_count`, and `generated_from_recording`. Keep the `.ass` and `.ass.meta.json` files together when moving or checking in converted scripts.
- Playback always derives from one explicit authority source at a time.
- The Workspace preferences now default to collapsing the hidden tab selections strip, and `Restore Layout Defaults` restores that collapsed state.
- The desktop preferences bundle is persisted in `desktop_settings.json` under the app's per-user data tree, which defaults to `%APPDATA%\ActionShellScript\config\desktop_settings.json` on Windows. The matching uninstall path removes the app install tree and the app-owned `%APPDATA%\ActionShellScript` directory so the standard desktop install leaves no ActionShellScript leftovers behind.

## Development

Run the test suite with:

```powershell
pytest -q
```
