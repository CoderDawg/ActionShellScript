param(
    [string]$Root = "."
)

$ErrorActionPreference = "Stop"

$directories = @(
    "apps/cli",
    "apps/desktop",
    "application",
    "core/recording",
    "core/interpretation",
    "core/shaping",
    "core/playback",
    "core/scripting",
    "core/runtime",
    "core/debugging",
    "core/artifacts",
    "editor",
    "infrastructure",
    "tests/unit",
    "tests/contract",
    "tests/integration",
    "docs/internal/architecture",
    "docs/user",
    "docs/project"
)

function New-DirectoryIfMissing {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
        Write-Host "Created directory: $Path"
    }
    else {
        Write-Host "Exists: $Path"
    }
}

$resolvedRoot = Resolve-Path -LiteralPath $Root
Push-Location $resolvedRoot

try {
    foreach ($directory in $directories) {
        New-DirectoryIfMissing -Path $directory
    }
}
finally {
    Pop-Location
}
