$ErrorActionPreference = "Stop"

$root = "C:\Users\coder\OneDrive\Documents\dev\Scripts\Python\Macro_Recorders\ASS\ActionShellScript"
Set-Location $root

$work = Join-Path $root "tmp\e2e"
New-Item -ItemType Directory -Force -Path $work | Out-Null

$raw        = Join-Path $work "session.raw.json"
$recFilt    = Join-Path $work "session.filtered-recording.json"
$interpFilt  = Join-Path $work "session.interpreted.json"
$shapeFilt   = Join-Path $work "session.shaped.json"
$scriptRaw   = Join-Path $work "playback.ass"
$scriptFilt  = Join-Path $work "playback.filtered.ass"

Write-Host "Step 1: record raw input to $raw"
Write-Host "Press Shift+Esc or Ctrl+C to stop recording."
ass-record --save-raw $raw

Write-Host ""
Write-Host "Step 2: recording filter"
ass-filter-recording $raw --profile mouse_jitter_cleanup --output $recFilt

Write-Host ""
Write-Host "Step 3: interpretation filter"
ass-filter-interpretation $raw --profile text_run_refinement --output $interpFilt

Write-Host ""
Write-Host "Step 4: shaping filter"
ass-filter-shaping $raw --profile smooth_mouse --output $shapeFilt

Write-Host ""
Write-Host "Step 5: generate playback script"
ass-generate $raw --output $scriptRaw

Write-Host ""
Write-Host "Step 6: document filter"
ass-filter-document $scriptRaw --profile normalize_document --output $scriptFilt

Write-Host ""
Write-Host "Step 7: preview playback from the filtered script"
ass-cli play script $scriptFilt --mode preview --ass-play --show-events

Write-Host ""
Write-Host "Step 8: live demo playback from the filtered script"
Write-Host "This uses the in-memory demo live adapter, not real input."
ass-cli play script $scriptFilt --mode live --demo-live --ass-play --show-events
