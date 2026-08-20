# `ass-cli` Quickstart

`ass-cli` is the recommended front-end for common ActionShellScript workflows. It keeps the command shape uniform:

```powershell
ass-cli <subcommand> [--input PATH] [--output PATH] [shared flags...]
```

Playback is the one deliberate exception: select `recording` or `script` first, then pass the source path as the positional input so the source authority stays explicit.

## Quick Examples

Record live input and write raw session JSON to `.\session.json`:

```powershell
ass-cli record --save-raw .\session.json
```

`ass-cli record --save-raw .\session.json` stops with `Shift+Esc` by default and writes raw session JSON to the path that the later `session.json` examples use. `--stop-hotkey` accepts `|`-separated alternates, so `--stop-hotkey Shift+Esc|Ctrl+C` makes either chord stop recording.

Use `ass-cli record --no-save` if you want the older in-memory-only behavior.

`ass-cli record-interpret --save-raw .\session.json` uses the same raw-session save path and also prints the destination before it begins recording.

Interpret a saved session. If you omit the input path, `ass-cli` reads `.\session.json` by default:

```powershell
ass-cli interpret
```

Shape a recording and show the derived actions. The default input is also `.\session.json`:

```powershell
ass-cli shape --show-actions
```

Generate script output from the default raw session file:

```powershell
ass-cli generate --output .\generated.ass
```

Convert generated output into a `ScriptDocument` using the same Recording to Script Conversion flow exposed in the desktop preferences. This also defaults to `.\session.json` when you omit the input:

```powershell
ass-cli open-script --output .\authoritative.ass
```

Play back a recording in preview mode. When you choose `recording`, the default source path is `.\session.json`:

```powershell
ass-cli play recording --mode preview
```

If you use `script` instead of `recording`, `ass-cli play` runs the script runtime first. That can produce console output and diagnostics even when it does not emit any mouse or keyboard playback events.

For a deterministic live walkthrough that exercises SendKeys key taps, use the checked-in [SendKeys Key Tap Transport Demo](../../samples/README.md#sendkeys-key-tap-transport-demo):

```powershell
ass-cli play script .\samples\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events
```

Run a script under the debugger:

```powershell
ass-cli debug --input .\generated.ass --step
```

If you prefer a one-command record -> generate -> play wrapper, see [record_and_play_live.ps1 Wrapper](record_and_play_live_wrapper.md). It supports `-ValidateOnly` for a JSON dry run and exposes the same playback knobs used by `ass-cli play`.

## When To Use It

- Use `ass-cli` when you want one stable front-end for day-to-day workflows.
- Use the legacy `ass-*` commands directly if you are scripting against the existing backend entry points.

## Related Docs

- [ass-cli Spec](ass_cli_spec.md)
