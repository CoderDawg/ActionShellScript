[CmdletBinding()]
param(
    [string]$OneDriveRepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
. (Join-Path $ScriptDir "sync-common.ps1")

$RepoRoot = Get-CurrentCheckoutRoot
$WorktreeReleaseRoot = Join-Path $RepoRoot "release_stage"
$syncFailure = $null
$packagingStatus = "not-run"
$releaseStatus = "not-run"

try {
    Write-Host "Syncing packaging..."
    $packagingResult = Invoke-SyncScript -ScriptPath (Join-Path $ScriptDir "sync-packaging.ps1") -OneDriveRepoRoot $OneDriveRepoRoot
    if ($packagingResult.Succeeded) {
        $packagingStatus = $packagingResult.Status
    }
    else {
        Write-Host "Packaging sync failed."
        $packagingStatus = $packagingResult.Status
        $syncFailure = $packagingResult
    }

    Write-Host "Syncing release output..."
    if ($null -eq $syncFailure) {
        if (Test-Path -LiteralPath $WorktreeReleaseRoot) {
            $releaseResult = Invoke-SyncScript -ScriptPath (Join-Path $ScriptDir "sync-release.ps1") -OneDriveRepoRoot $OneDriveRepoRoot
            if ($releaseResult.Succeeded) {
                $releaseStatus = $releaseResult.Status
            }
            else {
                Write-Host "Release sync failed."
                $releaseStatus = $releaseResult.Status
                $syncFailure = $releaseResult
            }
        }
        else {
            Write-Host "Release output missing, skipping release sync."
            $releaseStatus = "skipped"
        }
    }
    else {
        $releaseStatus = "skipped"
    }
}
catch {
    $syncFailure = $_
    if ($releaseStatus -eq "not-run") {
        $releaseStatus = "failed"
    }
}
finally {
    Write-Host "Sync summary: packaging=$packagingStatus, release=$releaseStatus"
}

if ($null -ne $syncFailure) {
    if ($syncFailure.PSObject.Properties.Name -contains "ScriptPath") {
        $failureMessage = "Sync failed for $($syncFailure.ScriptPath): $($syncFailure.ErrorMessage)"
        if ($syncFailure.PSObject.Properties.Name -contains "StdErrText" -and -not [string]::IsNullOrWhiteSpace($syncFailure.StdErrText)) {
            $failureMessage += [Environment]::NewLine
            $failureMessage += "Captured stderr:"
            $failureMessage += [Environment]::NewLine
            $failureMessage += $syncFailure.StdErrText
        }

        throw $failureMessage
    }

    throw $syncFailure
}

Write-Host "Synced packaging and release output."
