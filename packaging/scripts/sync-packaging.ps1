[CmdletBinding()]
param(
    [string]$WorktreePackagingRoot,
    [string]$OneDriveRepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "sync-common.ps1")

$CurrentCheckoutRoot = Get-CurrentCheckoutRoot
if ([string]::IsNullOrWhiteSpace($WorktreePackagingRoot)) {
    $WorktreePackagingRoot = Join-Path $CurrentCheckoutRoot "packaging"
}

function Assert-PackagingRootLike {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Role
    )

    $fullPath = Get-FullPath $Path
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "$Role does not exist: $fullPath"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $fullPath "scripts"))) {
        throw "$Role does not look like a packaging root: $fullPath (missing scripts)"
    }

    $fullPath
}

$WorktreePackagingRoot = Assert-PackagingRootLike -Path $WorktreePackagingRoot -Role "WorktreePackagingRoot"
$OneDriveRepoRoot = Resolve-OneDriveRepoRoot -ExplicitPath $OneDriveRepoRoot
$SourcePackagingRoot = $WorktreePackagingRoot
$DestinationRepoRoot = $OneDriveRepoRoot

$SourcePackagingPath = $SourcePackagingRoot
$DestinationPackagingPath = Join-Path $DestinationRepoRoot "packaging"

if (-not (Test-Path -LiteralPath $SourcePackagingPath)) {
    throw "Missing source packaging folder: $SourcePackagingPath"
}

if ((Get-FullPath $SourcePackagingPath) -eq (Get-FullPath $DestinationPackagingPath)) {
    throw "Source and destination packaging folders are the same. Pass a different -SourcePackagingRoot to mirror from another checkout."
}

New-Item -ItemType Directory -Force -Path $DestinationPackagingPath | Out-Null

Copy-Item -Path (Join-Path $SourcePackagingPath "*") -Destination $DestinationPackagingPath -Recurse -Force

Write-Host "Synced packaging from:"
Write-Host "  $SourcePackagingPath"
Write-Host "to:"
Write-Host "  $DestinationPackagingPath"
