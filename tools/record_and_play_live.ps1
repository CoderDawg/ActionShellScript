[CmdletBinding()]
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$ArtifactsDirectory,
    [string]$RawPath,
    [string]$ScriptPath,
    [ValidateSet("preview", "live")]
    [string]$PlaybackMode = "live",
    [int]$PlaybackDelayMs = 200,
    [int]$PlaybackRepeat = 1,
    [int]$PlaybackSettleMs = 0,
    [switch]$PlaybackStep,
    [bool]$PlaybackShowEvents = $true,
    [switch]$PlaybackDemoLive,
    [switch]$PlaybackAssPlay,
    [switch]$Diagnostics,
    [bool]$PauseAfterGenerate = $true,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$previousTreatControlCAsInput = $null
$treatControlCAsInputApplied = $false

function Join-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$ChildPath
    )

    if ([System.IO.Path]::IsPathRooted($ChildPath)) {
        return [System.IO.Path]::GetFullPath($ChildPath)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $ChildPath))
}

function Format-CommandPreview {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $formattedArguments = foreach ($argument in $Arguments) {
        if ($argument -match '^[A-Za-z0-9._:/\\+-]+$' -or $argument -match '^-?\d+(\.\d+)?$') {
            $argument
        }
        else {
            "'" + $argument.Replace("'", "''") + "'"
        }
    }

    return ($formattedArguments -join " ")
}

function Get-DiagnosticLogPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,
        [string]$ConfiguredPath
    )

    if ($ConfiguredPath) {
        return Join-AbsolutePath -BasePath $RootPath -ChildPath $ConfiguredPath
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = "actionshellscript_diagnostics_$stamp.log"
    return Join-Path ([System.IO.Path]::GetTempPath()) $filename
}

function Get-LiveRoundTripPlan {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,
        [string]$ArtifactsPath,
        [string]$RawArtifactPath,
        [string]$ScriptArtifactPath,
        [Parameter(Mandatory = $true)]
        [string]$Mode,
        [Parameter(Mandatory = $true)]
        [int]$DelayMs,
        [Parameter(Mandatory = $true)]
        [int]$RepeatCount,
        [Parameter(Mandatory = $true)]
        [int]$SettleMs,
        [Parameter(Mandatory = $true)]
        [bool]$StepMode,
        [Parameter(Mandatory = $true)]
        [bool]$ShowEvents,
        [Parameter(Mandatory = $true)]
        [bool]$DemoLive,
        [Parameter(Mandatory = $true)]
        [bool]$AssPlay,
        [Parameter(Mandatory = $true)]
        [bool]$PauseAfterGenerate,
        [string]$DiagnosticLogPath
    )

    $artifactsDirectory = if ($ArtifactsPath) {
        Join-AbsolutePath -BasePath $RootPath -ChildPath $ArtifactsPath
    }
    else {
        Join-Path $RootPath "tmp\e2e\live_round_trip"
    }

    $rawPath = if ($RawArtifactPath) {
        Join-AbsolutePath -BasePath $RootPath -ChildPath $RawArtifactPath
    }
    else {
        Join-Path $artifactsDirectory "live_session.json"
    }

    $scriptPath = if ($ScriptArtifactPath) {
        Join-AbsolutePath -BasePath $RootPath -ChildPath $ScriptArtifactPath
    }
    else {
        Join-Path $artifactsDirectory "live_session.ass"
    }

    $recordArgs = @(
        "record"
        "--save-raw"
        $rawPath
        "--force"
        "--stop-hotkey"
        "Shift+Esc|Ctrl+C"
    )

    $generateArgs = @(
        "generate"
        "--input"
        $rawPath
        "--output"
        $scriptPath
        "--force"
    )

    $playArgs = @(
        "play"
        "script"
        $scriptPath
        "--mode"
        $Mode
        "--repeat"
        [string]$RepeatCount
        "--delay-ms"
        [string]$DelayMs
        "--settle-ms"
        [string]$SettleMs
    )

    if ($StepMode) {
        $playArgs += "--step"
    }

    if ($ShowEvents) {
        $playArgs += "--show-events"
    }

    if ($DemoLive) {
        $playArgs += "--demo-live"
    }

    if ($AssPlay) {
        $playArgs += "--ass-play"
    }

    $playMessage = "ass-cli $(Format-CommandPreview -Arguments $playArgs)"

    [pscustomobject]@{
        root_path = $RootPath
        artifacts_directory = $artifactsDirectory
        raw_path = $rawPath
        script_path = $scriptPath
        playback_mode = $Mode
        playback_delay_ms = $DelayMs
        playback_repeat = $RepeatCount
        playback_settle_ms = $SettleMs
        playback_step = $StepMode
        playback_show_events = $ShowEvents
        playback_demo_live = $DemoLive
        playback_ass_play = $AssPlay
        pause_after_generate = $PauseAfterGenerate
        diagnostic_log_path = $DiagnosticLogPath
        record_arguments = $recordArgs
        generate_arguments = $generateArgs
        play_arguments = $playArgs
        record_message = "ass-cli record --save-raw $rawPath"
        generate_message = "ass-cli generate --input $rawPath --output $scriptPath"
        play_message = $playMessage
    }
}

function Invoke-AssCli {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host "ass-cli $Step" -ForegroundColor Cyan
    & ass-cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ass-cli $Step failed with exit code $LASTEXITCODE."
    }
}

function Write-PlanJson {
    param(
        [Parameter(Mandatory = $true)]
        $Plan
    )

    $Plan | ConvertTo-Json -Depth 6
}

if ($Diagnostics) {
    $env:ASS_DIAGNOSTICS = "1"
    $env:ASS_DIAGNOSTIC_MIN_SEVERITY = "debug"
    $env:ASS_DIAGNOSTIC_MAX_DETAIL = "3"
    $env:ASS_DIAGNOSTIC_FILE = "1"
}
else {
    Remove-Item Env:ASS_DIAGNOSTICS -ErrorAction SilentlyContinue
    Remove-Item Env:ASS_DIAGNOSTIC_MIN_SEVERITY -ErrorAction SilentlyContinue
    Remove-Item Env:ASS_DIAGNOSTIC_MAX_DETAIL -ErrorAction SilentlyContinue
    Remove-Item Env:ASS_DIAGNOSTIC_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:ASS_DIAGNOSTIC_PATH -ErrorAction SilentlyContinue
}

try {
    $diagnosticLogPath = $null
    if ($Diagnostics) {
        $diagnosticLogPath = Get-DiagnosticLogPath `
            -RootPath $Root `
            -ConfiguredPath $env:ASS_DIAGNOSTIC_PATH
        $env:ASS_DIAGNOSTIC_PATH = $diagnosticLogPath
    }

    $plan = Get-LiveRoundTripPlan `
        -RootPath $Root `
        -ArtifactsPath $ArtifactsDirectory `
        -RawArtifactPath $RawPath `
        -ScriptArtifactPath $ScriptPath `
        -Mode $PlaybackMode `
        -DelayMs $PlaybackDelayMs `
        -RepeatCount $PlaybackRepeat `
        -SettleMs $PlaybackSettleMs `
        -StepMode ([bool]$PlaybackStep) `
        -ShowEvents $PlaybackShowEvents `
        -DemoLive ([bool]$PlaybackDemoLive) `
        -AssPlay ([bool]$PlaybackAssPlay) `
        -PauseAfterGenerate $PauseAfterGenerate `
        -DiagnosticLogPath $diagnosticLogPath

    if ($ValidateOnly) {
        Write-PlanJson -Plan $plan
        return
    }

    $work = $plan.artifacts_directory
    New-Item -ItemType Directory -Force -Path $work | Out-Null

    if ($Diagnostics) {
        Write-Host "Diagnostics log file   : $diagnosticLogPath"
        Write-Host ""
    }
    Write-Host $plan.record_message
    Write-Host "Perform the interaction you want to replay."
    Write-Host "Press Shift+Esc or Ctrl+C to stop recording."
    try {
        try {
            $previousTreatControlCAsInput = [Console]::TreatControlCAsInput
            [Console]::TreatControlCAsInput = $true
            $treatControlCAsInputApplied = $true
        }
        catch {
            $previousTreatControlCAsInput = $null
            $treatControlCAsInputApplied = $false
        }
        Invoke-AssCli -Step "record live actions" -Arguments $plan.record_arguments
    }
    finally {
        if ($treatControlCAsInputApplied -and $null -ne $previousTreatControlCAsInput) {
            [Console]::TreatControlCAsInput = $previousTreatControlCAsInput
        }
    }

    Write-Host ""
    Write-Host $plan.generate_message
    Invoke-AssCli -Step "generate the script" -Arguments $plan.generate_arguments

    if ($PauseAfterGenerate) {
        Write-Host ""
        Write-Host "Press any key to continue"
        $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }

    Write-Host ""
    Write-Host $plan.play_message
    if ($PlaybackMode -eq "live") {
        if ($PlaybackDemoLive) {
            Write-Host "This uses the in-memory demo live adapter, not real input."
        }
        else {
            Write-Host "This uses the real live playback adapter, not demo mode."
        }
    }
    Invoke-AssCli -Step "play the generated script" -Arguments $plan.play_arguments
}
finally {
    if ($treatControlCAsInputApplied -and $null -ne $previousTreatControlCAsInput) {
        [Console]::TreatControlCAsInput = $previousTreatControlCAsInput
    }
}
