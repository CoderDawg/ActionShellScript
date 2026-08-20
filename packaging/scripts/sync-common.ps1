[CmdletBinding()]
param()

Set-StrictMode -Version Latest

function Get-FullPath {
    param([Parameter(Mandatory)][string]$Path)
    [System.IO.Path]::GetFullPath($Path)
}

function Get-CurrentCheckoutRoot {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Resolve-OneDriveRepoRoot {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        return Get-FullPath $ExplicitPath
    }

    if (-not [string]::IsNullOrWhiteSpace($env:ASS_ONE_DRIVE_REPO_ROOT)) {
        return Get-FullPath $env:ASS_ONE_DRIVE_REPO_ROOT
    }

    throw "OneDriveRepoRoot is not configured. Pass -OneDriveRepoRoot or set ASS_ONE_DRIVE_REPO_ROOT."
}

function Invoke-SyncScript {
    param(
        [Parameter(Mandatory)][string]$ScriptPath,
        [string]$OneDriveRepoRoot
    )

    $resolvedScriptPath = Get-FullPath $ScriptPath
    $resolvedOneDriveRepoRoot = $null
    $scriptArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($OneDriveRepoRoot)) {
        $resolvedOneDriveRepoRoot = Resolve-OneDriveRepoRoot -ExplicitPath $OneDriveRepoRoot
        $scriptArgs += @("-OneDriveRepoRoot", $resolvedOneDriveRepoRoot)
    }

    $startedAtUtc = [DateTime]::UtcNow
    $capturedOutput = New-Object 'System.Collections.Generic.List[object]'
    try {
        & $resolvedScriptPath @scriptArgs 6>&1 2>&1 | ForEach-Object {
            $capturedOutput.Add($_) | Out-Null
        }
        $completedAtUtc = [DateTime]::UtcNow
        $stdoutLines = New-Object 'System.Collections.Generic.List[string]'
        $stderrLines = New-Object 'System.Collections.Generic.List[string]'
        $informationLines = New-Object 'System.Collections.Generic.List[string]'

        foreach ($item in $capturedOutput) {
            if ($item -is [System.Management.Automation.ErrorRecord]) {
                $stderrLines.Add($item.ToString()) | Out-Null
            }
            elseif ($item -is [System.Management.Automation.InformationRecord]) {
                $informationLines.Add($item.MessageData.ToString()) | Out-Null
            }
            else {
                $stdoutLines.Add($item.ToString()) | Out-Null
            }
        }

        [pscustomobject]@{
            ScriptPath = $resolvedScriptPath
            OneDriveRepoRoot = $resolvedOneDriveRepoRoot
            Succeeded = $true
            Status = "ok"
            StartedAtUtc = $startedAtUtc
            CompletedAtUtc = $completedAtUtc
            DurationMs = [math]::Round(($completedAtUtc - $startedAtUtc).TotalMilliseconds, 2)
            StdOutLines = @($stdoutLines)
            StdErrLines = @($stderrLines)
            InformationLines = @($informationLines)
            StdOutText = ($stdoutLines -join [Environment]::NewLine)
            StdErrText = ($stderrLines -join [Environment]::NewLine)
            InformationText = ($informationLines -join [Environment]::NewLine)
            ErrorMessage = $null
        }
    }
    catch {
        $completedAtUtc = [DateTime]::UtcNow
        $stdoutLines = New-Object 'System.Collections.Generic.List[string]'
        $stderrLines = New-Object 'System.Collections.Generic.List[string]'
        $informationLines = New-Object 'System.Collections.Generic.List[string]'

        foreach ($item in $capturedOutput) {
            if ($item -is [System.Management.Automation.ErrorRecord]) {
                $stderrLines.Add($item.ToString()) | Out-Null
            }
            elseif ($item -is [System.Management.Automation.InformationRecord]) {
                $informationLines.Add($item.MessageData.ToString()) | Out-Null
            }
            else {
                $stdoutLines.Add($item.ToString()) | Out-Null
            }
        }

        $errorRecordText = $_.ToString()
        if (-not [string]::IsNullOrWhiteSpace($errorRecordText)) {
            $stderrLines.Add($errorRecordText) | Out-Null
        }

        [pscustomobject]@{
            ScriptPath = $resolvedScriptPath
            OneDriveRepoRoot = $resolvedOneDriveRepoRoot
            Succeeded = $false
            Status = "failed"
            StartedAtUtc = $startedAtUtc
            CompletedAtUtc = $completedAtUtc
            DurationMs = [math]::Round(($completedAtUtc - $startedAtUtc).TotalMilliseconds, 2)
            StdOutLines = @($stdoutLines)
            StdErrLines = @($stderrLines)
            InformationLines = @($informationLines)
            StdOutText = ($stdoutLines -join [Environment]::NewLine)
            StdErrText = ($stderrLines -join [Environment]::NewLine)
            InformationText = ($informationLines -join [Environment]::NewLine)
            ErrorMessage = $_.Exception.Message
        }
    }
}
