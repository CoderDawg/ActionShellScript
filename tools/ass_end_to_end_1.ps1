$ErrorActionPreference = "Stop"

$root = "C:\Users\coder\OneDrive\Documents\dev\Scripts\Python\Macro_Recorders\ASS\ActionShellScript"
Set-Location $root

$work = Join-Path $root "tmp\e2e"
New-Item -ItemType Directory -Force -Path $work | Out-Null

$raw = Join-Path $work "session.json"

Write-Host "Step 1: recording to $raw"
Write-Host "Press Shift+Esc or Ctrl+C to stop recording."
ass-record --save-raw $raw --force

#Write-Host ""
#Write-Host "Step 2: preview playback"
#ass-cli play recording $raw --mode preview --show-events

Write-Host ""
Write-Host "Step 3: live playback"
Write-Host "This uses the real live playback adapter, not demo mode."
#ass-cli play recording $raw --mode live --demo-live --show-events
ass-cli play recording $raw --mode live --show-events --delay-ms 200
