[CmdletBinding()]
param(
    [string]$WorktreeReleaseRoot,
    [string]$OneDriveRepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "sync-common.ps1")

$CurrentCheckoutRoot = Get-CurrentCheckoutRoot
if ([string]::IsNullOrWhiteSpace($WorktreeReleaseRoot)) {
    $WorktreeReleaseRoot = Join-Path $CurrentCheckoutRoot "release_stage"
}

if (-not (Test-Path -LiteralPath $WorktreeReleaseRoot)) {
    Write-Host "Release output not found, skipping sync:"
    Write-Host "  $WorktreeReleaseRoot"
    exit 0
}

$SourceReleaseRoot = Get-FullPath $WorktreeReleaseRoot
$DestinationRepoRoot = Resolve-OneDriveRepoRoot -ExplicitPath $OneDriveRepoRoot
$DestinationReleaseRoot = Join-Path $DestinationRepoRoot "release_stage"

if ($SourceReleaseRoot -eq $DestinationReleaseRoot) {
    throw "Source and destination release folders are the same. The sync script needs two different checkouts."
}

New-Item -ItemType Directory -Force -Path $DestinationReleaseRoot | Out-Null

Copy-Item -Path (Join-Path $SourceReleaseRoot "*") -Destination $DestinationReleaseRoot -Recurse -Force

Write-Host "Synced release output from:"
Write-Host "  $SourceReleaseRoot"
Write-Host "to:"
Write-Host "  $DestinationReleaseRoot"
