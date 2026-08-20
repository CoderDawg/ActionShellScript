# `record_and_play_live.ps1` Wrapper

`tools/record_and_play_live.ps1` is a convenience wrapper for the full record -> generate -> play round trip. It builds a stable plan first, then either prints that plan with `-ValidateOnly` or runs the underlying `ass-cli` commands in order.

The wrapper is useful when you want one command to:

1. capture live input
2. generate a script from the raw recording
3. play the generated script back immediately

## Dry-Run Mode

Use `-ValidateOnly` to inspect the planned work without touching the desktop:

```powershell
.\tools\record_and_play_live.ps1 -Root . -ValidateOnly
```

Dry-run mode prints a JSON plan to standard output. The plan includes:

- resolved paths such as `root_path`, `artifacts_directory`, `raw_path`, and `script_path`
- the generated argument arrays for `record_arguments`, `generate_arguments`, and `play_arguments`
- the selected playback settings, including `playback_mode`, `playback_repeat`, `playback_delay_ms`, `playback_settle_ms`, `playback_step`, `playback_show_events`, `playback_demo_live`, and `playback_ass_play`
- the preview strings in `record_message`, `generate_message`, and `play_message`

`play_message` is only a human-readable preview. `play_arguments` is the authoritative list that gets passed to `ass-cli`.

## Playback Knobs

The wrapper exposes the newer playback knobs directly so the dry-run plan and the real execution stay aligned:

- `-PlaybackRepeat` maps to `--repeat`
- `-PlaybackDelayMs` maps to `--delay-ms`
- `-PlaybackSettleMs` maps to `--settle-ms`
- `-PlaybackStep` adds `--step`
- `-PlaybackShowEvents` controls whether `--show-events` is included
- `-PlaybackDemoLive` adds `--demo-live`
- `-PlaybackAssPlay` adds `--ass-play`

The default `-PlaybackShowEvents` value is `True`, so a normal plan includes `--show-events` unless you explicitly disable it with `-PlaybackShowEvents:$false`.

## Examples

Inspect the full plan before running anything:

```powershell
.\tools\record_and_play_live.ps1 `
  -Root . `
  -ArtifactsDirectory .\tmp\e2e\live_round_trip `
  -PlaybackMode live `
  -PlaybackRepeat 2 `
  -PlaybackDelayMs 150 `
  -PlaybackSettleMs 25 `
  -PlaybackStep `
  -PlaybackShowEvents:$false `
  -PlaybackDemoLive `
  -PlaybackAssPlay `
  -ValidateOnly
```

That dry run prints a JSON payload with the resolved paths plus the exact `ass-cli` arguments that would be used for recording, generation, and playback.

Run the wrapper for a real live round trip with the deterministic demo adapter and per-keystroke playback:

```powershell
.\tools\record_and_play_live.ps1 `
  -Root . `
  -PlaybackMode live `
  -PlaybackDemoLive `
  -PlaybackAssPlay `
  -PlaybackRepeat 2 `
  -PlaybackDelayMs 150 `
  -PlaybackSettleMs 25 `
  -PlaybackStep
```

This records input, generates the script, pauses after generation by default, and then plays the generated script with the selected playback flags.

## Related Docs

- [ass-cli Quickstart](ass_cli_quickstart.md)
- [CLI Cheat Sheet](cli_cheat_sheet.md#phase-6-play)
- [Docs Index](../index.md)
