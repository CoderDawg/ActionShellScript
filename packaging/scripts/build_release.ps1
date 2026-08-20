# Release pipeline:
# - No step flags: run the full release pipeline (stage, bundle with PyInstaller, then compile the installer with Inno Setup).
# - -Stage: run only the staging step that copies files into release_stage.
# - -PyInstaller: run only the bundling step that creates the app executables from the staged tree.
# - -Inno: run only the installer step that compiles the Inno Setup script from the staged dist tree.
# - -PackagingNotesOnly: print just the packaging notes for the current installer artifact and exit.
[CmdletBinding()]
param(
    [string]$StageRoot,
    [switch]$Clean,
    # Use these switches to run only the named release phases instead of the full pipeline.
    [switch]$Stage,
    [switch]$PyInstaller,
    [switch]$Inno,
    [switch]$PackagingNotesOnly,
    [string]$InnoCompilerPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($StageRoot)) {
    $StageRoot = Join-Path $RepoRoot "release_stage"
}

function Get-NormalizedFullPath {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-PathUnderRoot {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Root
    )

    $fullPath = Get-NormalizedFullPath -Path $Path
    $fullRoot = Get-NormalizedFullPath -Path $Root
    if (-not $fullRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $fullRoot += [System.IO.Path]::DirectorySeparatorChar
    }

    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside the repository root. Path: $fullPath Root: $fullRoot"
    }

    return $fullPath
}

function Get-ProjectVersion {
    param(
        [Parameter(Mandatory)]
        [string]$PyProjectPath
    )

    $pyproject = Get-Content -LiteralPath $PyProjectPath -Raw
    $match = [regex]::Match(
        $pyproject,
        '^\s*version\s*=\s*"([^"]+)"\s*$',
        [System.Text.RegularExpressions.RegexOptions]::Multiline
    )

    if (-not $match.Success) {
        throw "Unable to read project version from $PyProjectPath"
    }

    return $match.Groups[1].Value
}

function ConvertTo-WindowsFileVersion {
    param(
        [Parameter(Mandatory)]
        [string]$Version
    )

    $match = [regex]::Match(
        $Version.Trim(),
        '^(?<major>\d+)(?:\.(?<minor>\d+))?(?:\.(?<patch>\d+))?(?:(?<tag>a|b|rc)(?<serial>\d+))?$',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if (-not $match.Success) {
        throw "Unable to convert version '$Version' into a Windows file version."
    }

    $components = @(
        [int]$match.Groups["major"].Value
        if ($match.Groups["minor"].Success) { [int]$match.Groups["minor"].Value } else { 0 }
        if ($match.Groups["patch"].Success) { [int]$match.Groups["patch"].Value } else { 0 }
        if ($match.Groups["serial"].Success) {
            [int]$match.Groups["serial"].Value
        }
        else {
            0
        }
    )

    return ($components -join ".")
}

function Get-PackageAssetManifest {
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot,
        [Parameter(Mandatory)]
        [string]$PythonPath
    )

    $helperPath = Join-Path $RepoRoot "packaging\asset_manifest.py"

    if (-not (Test-Path -LiteralPath $helperPath)) {
        throw "Missing asset manifest helper: $helperPath"
    }

    $runtimeAssets = @(
        & $PythonPath $helperPath --runtime-assets |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { ConvertTo-ManifestAssetPath -Path $_.Trim() }
    )
    $installerSetupIcon = (
        & $PythonPath $helperPath --installer-setup-icon
    ).Trim()

    return [pscustomobject]@{
        runtime_assets = $runtimeAssets
        installer_setup_icon = $installerSetupIcon
    }
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function ConvertTo-ManifestAssetPath {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    return $Path.Replace("/", "\")
}

function Format-ElapsedTime {
    param(
        [Parameter(Mandatory)]
        [TimeSpan]$Duration
    )

    return ("{0:hh\:mm\:ss\.fff}" -f $Duration)
}

function Get-FileSha256 {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
    return $hash.Hash.ToUpperInvariant()
}

function Get-StepTimingText {
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$Timing
    )

    if ($Timing.Status -eq "skipped") {
        return "skipped"
    }

    if ($null -eq $Timing.Elapsed) {
        return $Timing.Status
    }

    return "$(Format-ElapsedTime -Duration $Timing.Elapsed) ($($Timing.Status))"
}

function Write-ReleaseSummary {
    param(
        [Parameter(Mandatory)]
        [TimeSpan]$TotalElapsed,
        [Parameter(Mandatory)]
        [string]$PythonPath,
        [Parameter(Mandatory)]
        [string]$PyInstallerPath
    )

    $manifestPath = Join-Path $StageRoot "stage-manifest.txt"
    Write-Host "Release pipeline summary:"
    Write-Host "  stage root: $StageRoot"
    Write-Host "  status: $stagingStatus"
    Write-Host "  bundle status: $pyInstallerStatus"
    Write-Host "  installer status: $installerStatus"
    Write-Host "  packaging versioning:"
    Write-Host "    project version: $projectVersion"
    Write-Host "    installer version: $projectVersion"
    Write-Host "    windows file version: $projectFileVersion"
    Write-Host "  copied package roots: $(if ($runStage) { "$copiedPackageRoots/$packageRootCount" } else { 'skipped' })"
    Write-Host "  copied top-level files: $(if ($runStage) { "$copiedTopLevelFiles/$topLevelFileCount" } else { 'skipped' })"
    Write-Host "  copied runtime assets: $(if ($runStage) { "$copiedRuntimeAssets/$runtimeAssetCount" } else { 'skipped' })"
    Write-Host "  manifest: $(if ($manifestWritten) { $manifestPath } else { 'not-written' })"
    Write-Host "  build output: $(if (Test-Path -LiteralPath $buildOutputRoot) { $buildOutputRoot } else { 'not-written' })"
    Write-Host "  installer output: $(if (Test-Path -LiteralPath $installerOutputRoot) { $installerOutputRoot } else { 'not-written' })"
    Write-Host "  python interpreter: $PythonPath"
    Write-Host "  pyinstaller executable: $PyInstallerPath"
    Write-Host "Release timing summary:"
    Write-Host "  total elapsed: $(Format-ElapsedTime -Duration $TotalElapsed)"
    Write-Host "  stage: $(Get-StepTimingText -Timing $stepTimings.stage)"
    Write-Host "  pyinstaller: $(Get-StepTimingText -Timing $stepTimings.pyinstaller)"
    Write-Host "  inno: $(Get-StepTimingText -Timing $stepTimings.inno)"
}

function Write-PackagingNotes {
    param(
        [Parameter(Mandatory)]
        [string]$ProjectVersion,
        [Parameter(Mandatory)]
        [string]$ProjectFileVersion,
        [Parameter(Mandatory)]
        [string]$InstallerExePath
    )

    if (-not (Test-Path -LiteralPath $InstallerExePath)) {
        return
    }

    $gitTagVersion = "v$ProjectVersion"
    $installerSha256 = Get-FileSha256 -Path $InstallerExePath
    $literalTick = [char]96

    Write-Host "## Packaging Notes"
    Write-Host ""
    Write-Host "- Project version: $literalTick$ProjectVersion$literalTick"
    Write-Host "- Git tag: $literalTick$gitTagVersion$literalTick"
    Write-Host "- Installer/file version: $literalTick$ProjectFileVersion$literalTick"
    Write-Host "- SHA256: $literalTick$installerSha256$literalTick"
}

function Resolve-PackagingNotesInstallerPath {
    param(
        [Parameter(Mandatory)]
        [string]$StageRoot,
        [Parameter(Mandatory)]
        [string]$InstallerOutputRoot
    )

    $candidatePaths = @(
        (Join-Path $InstallerOutputRoot "ActionShellScript-Setup.exe"),
        (Join-Path $StageRoot "installer\ActionShellScript-Setup.exe")
    )

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path -LiteralPath $candidatePath) {
            return $candidatePath
        }
    }

    throw "Unable to find ActionShellScript-Setup.exe for packaging notes. Build the installer first or place it under '$InstallerOutputRoot'."
}

function Write-SelectedToolPaths {
    param(
        [Parameter(Mandatory)]
        [string]$PythonPath,
        [Parameter(Mandatory)]
        [pscustomobject]$PyInstallerInvocation
    )

    Write-Host "Selected tool paths:"
    Write-Host "  python interpreter: $PythonPath"
    Write-Host "  pyinstaller executable: $($PyInstallerInvocation.DisplayText)"
}

function Resolve-PreferredExecutablePath {
    param(
        [Parameter(Mandatory)]
        [string]$CommandName,
        [Parameter(Mandatory)]
        [string[]]$PreferredPaths
    )

    foreach ($preferredPath in $PreferredPaths) {
        if (-not [string]::IsNullOrWhiteSpace($preferredPath) -and (Test-Path -LiteralPath $preferredPath)) {
            return Get-NormalizedFullPath -Path $preferredPath
        }
    }

    $command = Get-Command $CommandName -ErrorAction Stop
    return $command.Source
}

function Resolve-PyInstallerInvocation {
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot,
        [Parameter(Mandatory)]
        [string]$PythonPath
    )

    $preferredPath = Join-Path $RepoRoot ".venv\Scripts\pyinstaller.exe"
    if (Test-Path -LiteralPath $preferredPath) {
        $resolvedPath = Get-NormalizedFullPath -Path $preferredPath
        return [pscustomobject]@{
            UsePythonModuleFallback = $false
            DisplayText = $resolvedPath
            Command = $resolvedPath
        }
    }

    $command = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return [pscustomobject]@{
            UsePythonModuleFallback = $false
            DisplayText = $command.Source
            Command = $command.Source
        }
    }

    return [pscustomobject]@{
        UsePythonModuleFallback = $true
        DisplayText = "$PythonPath -m PyInstaller"
        Command = $PythonPath
    }
}

function Copy-DirectoryTreeFiltered {
    param(
        [Parameter(Mandatory)]
        [string]$Source,
        [Parameter(Mandatory)]
        [string]$Destination,
        [string[]]$ExcludeDirectories = @("__pycache__", ".pytest_cache", ".venv", "build", "dist", "tmp", "logs"),
        [string[]]$ExcludeFiles = @()
    )

    Ensure-Directory -Path $Destination

    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        if ($item.PSIsContainer) {
            if ($ExcludeDirectories -contains $item.Name) {
                continue
            }

            Copy-DirectoryTreeFiltered `
                -Source $item.FullName `
                -Destination (Join-Path $Destination $item.Name) `
                -ExcludeDirectories $ExcludeDirectories `
                -ExcludeFiles $ExcludeFiles
            continue
        }

        if ($ExcludeFiles -contains $item.Name) {
            continue
        }

        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Force
    }
}

function Remove-FilesFromTreeFiltered {
    param(
        [Parameter(Mandatory)]
        [string]$Root,
        [string[]]$FileNames = @()
    )

    if (-not (Test-Path -LiteralPath $Root)) {
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
        if ($FileNames -contains $item.Name) {
            Remove-Item -LiteralPath $item.FullName -Force
        }
    }
}

function Invoke-PyInstallerBuild {
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$PyInstallerInvocation,
        [Parameter(Mandatory)]
        [string]$SpecPath,
        [Parameter(Mandatory)]
        [string]$DistRoot,
        [Parameter(Mandatory)]
        [string]$WorkRoot,
        [Parameter(Mandatory)]
        [string]$SourceRoot
    )

    $previousSourceRoot = $env:ASS_RELEASE_SOURCE_ROOT
    try {
        $env:ASS_RELEASE_SOURCE_ROOT = $SourceRoot
        if ($PyInstallerInvocation.UsePythonModuleFallback) {
            & $PyInstallerInvocation.Command `
                -m `
                PyInstaller `
                --noconfirm `
                --clean `
                --distpath $DistRoot `
                --workpath $WorkRoot `
                $SpecPath
        }
        else {
            & $PyInstallerInvocation.Command `
                --noconfirm `
                --clean `
                --distpath $DistRoot `
                --workpath $WorkRoot `
                $SpecPath
        }
    }
    finally {
        if ($null -ne $previousSourceRoot) {
            $env:ASS_RELEASE_SOURCE_ROOT = $previousSourceRoot
        }
        else {
            Remove-Item Env:\ASS_RELEASE_SOURCE_ROOT -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-InnoCompiler {
    param(
        [string]$ExplicitPath
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $resolved = Get-NormalizedFullPath -Path $ExplicitPath
        if (-not (Test-Path -LiteralPath $resolved)) {
            throw "Inno compiler not found at $resolved"
        }
        return $resolved
    }

    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    foreach ($candidate in @(
        (Join-Path $env:LocalAppData "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Unable to find the Inno Setup compiler. Pass -InnoCompilerPath or install Inno Setup 6."
}

function New-InnoWorkingRoot {
    param(
        [Parameter(Mandatory)]
        [string]$Prefix
    )

    $suffix = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
    $workingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ass-$Prefix-$suffix")
    Ensure-Directory -Path $workingRoot
    return $workingRoot
}

function Invoke-InnoSetupBuild {
    param(
        [Parameter(Mandatory)]
        [string]$CompilerPath,
        [Parameter(Mandatory)]
        [string]$ScriptPath,
        [Parameter(Mandatory)]
        [string]$SourceRoot,
        [Parameter(Mandatory)]
        [string]$InstallerOutputRoot,
        [Parameter(Mandatory)]
        [string]$MyAppVersion,
        [Parameter(Mandatory)]
        [string]$MyAppFileVersion,
        [Parameter(Mandatory)]
        [string]$InstallerSetupIcon
    )

    $previousLocation = Get-Location
    try {
        Set-Location ([System.IO.Path]::GetTempPath())
        & $CompilerPath "/DReleaseSourceRoot=$SourceRoot" "/DInstallerOutputRoot=$InstallerOutputRoot" "/DMyAppVersion=$MyAppVersion" "/DMyAppFileVersion=$MyAppFileVersion" "/DInstallerSetupIcon=$InstallerSetupIcon" $ScriptPath
    }
    finally {
        Set-Location $previousLocation
    }
}

$runStage = $Stage.IsPresent
$runPyInstaller = $PyInstaller.IsPresent
$runInno = $Inno.IsPresent
if ($PackagingNotesOnly) {
    $runStage = $false
    $runPyInstaller = $false
    $runInno = $false
}
elseif (-not ($runStage -or $runPyInstaller -or $runInno)) {
    $runStage = $true
    $runPyInstaller = $true
    $runInno = $true
}

$StageRoot = Assert-PathUnderRoot -Path $StageRoot -Root $RepoRoot

if (Test-Path -LiteralPath $StageRoot) {
    if ($Clean) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force
    }
}

$installerOutputRoot = Join-Path $StageRoot "installer"
# Keep the shipping installer free of QtWebEngine debug payloads.
# These files are large, are not used by the runtime apps, and only bloat
# the final setup executable.
$installerExcludedFiles = @(
    "qtwebengine_devtools_resources.debug.pak",
    "qtwebengine_resources.debug.pak",
    "qtwebengine_resources_200p.debug.pak",
    "qtwebengine_resources_100p.debug.pak",
    "v8_context_snapshot.debug.bin"
)
$projectVersion = Get-ProjectVersion -PyProjectPath (Join-Path $RepoRoot "pyproject.toml")
$projectFileVersion = ConvertTo-WindowsFileVersion -Version $projectVersion

if ($PackagingNotesOnly) {
    $notesOnlyInstallerPath = Resolve-PackagingNotesInstallerPath -StageRoot $StageRoot -InstallerOutputRoot $installerOutputRoot
    Write-PackagingNotes `
        -ProjectVersion $projectVersion `
        -ProjectFileVersion $projectFileVersion `
        -InstallerExePath $notesOnlyInstallerPath
    return
}

Ensure-Directory -Path $StageRoot

$stagingStatus = "not-run"
$pyInstallerStatus = "not-run"
$installerStatus = "not-run"
$copiedPackageRoots = 0
$copiedTopLevelFiles = 0
$copiedRuntimeAssets = 0
$manifestWritten = $false
$packageRootCount = 8
$topLevelFileCount = 6
$buildOutputRoot = Join-Path $StageRoot "dist"
$buildWorkRoot = Join-Path $StageRoot "build"
$installerSpecPath = Join-Path $RepoRoot "packaging\installer\ActionShellScript.iss"
$specPath = Join-Path $RepoRoot "packaging\pyinstaller\ActionShellScript.spec"
$pythonInterpreterPath = Resolve-PreferredExecutablePath `
    -CommandName "python" `
    -PreferredPaths @(
        (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    )
$pyInstallerInvocation = Resolve-PyInstallerInvocation `
    -RepoRoot $RepoRoot `
    -PythonPath $pythonInterpreterPath
$assetManifest = Get-PackageAssetManifest -RepoRoot $RepoRoot -PythonPath $pythonInterpreterPath
$runtimeAssets = @($assetManifest.runtime_assets)
$runtimeAssetCount = $runtimeAssets.Count
$installerSetupIcon = Get-NormalizedFullPath -Path (Join-Path $RepoRoot $assetManifest.installer_setup_icon)
$null = Write-SelectedToolPaths -PythonPath $pythonInterpreterPath -PyInstallerInvocation $pyInstallerInvocation
$stagingError = $null
$pyInstallerError = $null
$installerError = $null
$installerSourceRoot = $null
$pipelineStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$stepTimings = [ordered]@{
    stage = [pscustomobject]@{
        Status = "skipped"
        Elapsed = $null
    }
    pyinstaller = [pscustomobject]@{
        Status = "skipped"
        Elapsed = $null
    }
    inno = [pscustomobject]@{
        Status = "skipped"
        Elapsed = $null
    }
}

try {
    if ($runStage) {
        $stageStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $stageSucceeded = $false
        $packageRoots = @(
            "apps\cli",
            "apps\desktop",
            "application",
            "core",
            "editor",
            "infrastructure",
            "docs",
            "samples"
        )

        $topLevelFiles = @(
            "ATTRIBUTION.txt",
            "LICENSE",
            "NOTICE",
            "README.md",
            "pyproject.toml",
            "table_api.py"
        )

        foreach ($relativePath in $packageRoots) {
            Write-Host "Copying $relativePath..."
            $sourcePath = Join-Path $RepoRoot $relativePath
            $destinationPath = Join-Path $StageRoot $relativePath
            if (-not (Test-Path -LiteralPath $sourcePath)) {
                throw "Missing required source folder: $sourcePath"
            }

            $excludeDirectories = @("__pycache__", ".pytest_cache", ".venv", "build", "dist", "tmp", "logs")
            if ($relativePath -eq "docs") {
                $excludeDirectories += "internal"
            }

            Copy-DirectoryTreeFiltered -Source $sourcePath -Destination $destinationPath -ExcludeDirectories $excludeDirectories
            $copiedPackageRoots++
        }

        foreach ($relativeFile in $topLevelFiles) {
            Write-Host "Copying $relativeFile..."
            $sourceFile = Join-Path $RepoRoot $relativeFile
            if (Test-Path -LiteralPath $sourceFile) {
                Copy-Item -LiteralPath $sourceFile -Destination $StageRoot -Force
                $copiedTopLevelFiles++
            }
        }

        foreach ($relativeFile in $runtimeAssets) {
            Write-Host "Copying $relativeFile..."
            $sourceFile = Join-Path $RepoRoot $relativeFile
            if (-not (Test-Path -LiteralPath $sourceFile)) {
                throw "Missing required runtime asset: $sourceFile"
            }

            $targetDirectory = Join-Path $StageRoot (Split-Path $relativeFile -Parent)
            Ensure-Directory -Path $targetDirectory
            Copy-Item -LiteralPath $sourceFile -Destination $targetDirectory -Force
            $copiedRuntimeAssets++
        }

        $manifestPath = Join-Path $StageRoot "stage-manifest.txt"
        $manifestLines = @(
            "ActionShellScript staging manifest",
            "Repo root: $RepoRoot",
            "Stage root: $StageRoot",
            "",
            "Copied package roots:",
            "  - apps\cli",
            "  - apps\desktop",
            "  - application",
            "  - core",
            "  - editor",
            "  - infrastructure",
            "  - docs",
            "  - samples",
            "",
            "Copied top-level files:",
            "  - ATTRIBUTION.txt",
            "  - LICENSE",
            "  - NOTICE",
            "  - README.md",
            "  - pyproject.toml",
            "  - table_api.py",
            "",
            "Copied runtime assets:"
        )
        $manifestLines += $runtimeAssets | ForEach-Object { "  - $_" }

        $manifestLines | Set-Content -LiteralPath $manifestPath -Encoding UTF8
        $manifestWritten = $true
        $stagingStatus = "ok"
        $stageSucceeded = $true
    }

    if ($runStage) {
        $stageStopwatch.Stop()
        $stagingStatus = if ($stageSucceeded) { "ok" } else { "failed" }
        $stepTimings.stage = [pscustomobject]@{
            Status = $stagingStatus
            Elapsed = $stageStopwatch.Elapsed
        }
        Write-Host "Stage step $(if ($stageSucceeded) { 'completed' } else { 'finished with errors' }) in $(Format-ElapsedTime -Duration $stageStopwatch.Elapsed)."
    }

    if ($runPyInstaller) {
        $pyInstallerStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $pyInstallerSucceeded = $false
        Write-Host "Running PyInstaller spec..."
        try {
            Invoke-PyInstallerBuild `
                -PyInstallerInvocation $pyInstallerInvocation `
                -SpecPath $specPath `
                -DistRoot $buildOutputRoot `
                -WorkRoot $buildWorkRoot `
                -SourceRoot $StageRoot
            # PyInstaller bundles QtWebEngine's debug payloads by default; remove
            # them from the staged dist so the installer and shipped bundles stay lean.
            Remove-FilesFromTreeFiltered -Root $buildOutputRoot -FileNames $installerExcludedFiles
            $pyInstallerStatus = "ok"
            $pyInstallerSucceeded = $true
        }
        finally {
            $pyInstallerStopwatch.Stop()
            $stepTimings.pyinstaller = [pscustomobject]@{
                Status = if ($pyInstallerSucceeded) { "ok" } else { "failed" }
                Elapsed = $pyInstallerStopwatch.Elapsed
            }
            Write-Host "PyInstaller step $(if ($pyInstallerSucceeded) { 'completed' } else { 'finished with errors' }) in $(Format-ElapsedTime -Duration $pyInstallerStopwatch.Elapsed)."
        }
    }

    if ($runInno) {
        $innoStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $innoSucceeded = $false
        Write-Host "Running Inno Setup compiler..."
        try {
            $innoCompiler = Resolve-InnoCompiler -ExplicitPath $InnoCompilerPath
            $stagedDistRoot = Join-Path $StageRoot "dist"
            if (-not (Test-Path -LiteralPath $stagedDistRoot)) {
                throw "Missing staged dist tree: $stagedDistRoot"
            }

            $installerSourceRoot = New-InnoWorkingRoot -Prefix "source"
            Copy-DirectoryTreeFiltered `
                -Source $stagedDistRoot `
                -Destination (Join-Path $installerSourceRoot "dist") `
                -ExcludeDirectories @("__pycache__", ".pytest_cache", ".venv", "build", "dist", "tmp", "logs", "objects-Debug", "objects-RelWithDebInfo", "internal") `
                -ExcludeFiles $installerExcludedFiles
            Copy-Item -LiteralPath (Join-Path $StageRoot "ATTRIBUTION.txt") -Destination $installerSourceRoot -Force
            Ensure-Directory -Path $installerOutputRoot
            Invoke-InnoSetupBuild `
                -CompilerPath $innoCompiler `
                -ScriptPath $installerSpecPath `
                -SourceRoot $installerSourceRoot `
                -InstallerOutputRoot $installerOutputRoot `
                -MyAppVersion $projectVersion `
                -MyAppFileVersion $projectFileVersion `
                -InstallerSetupIcon $installerSetupIcon
            $compiledInstallerExePath = Join-Path $installerOutputRoot "ActionShellScript-Setup.exe"
            if (-not (Test-Path -LiteralPath $compiledInstallerExePath)) {
                $installerContents = if (Test-Path -LiteralPath $installerOutputRoot) {
                    @(Get-ChildItem -LiteralPath $installerOutputRoot -Force | Select-Object -ExpandProperty Name) -join ", "
                }
                else {
                    "not-written"
                }

                throw "Inno Setup did not create the expected installer at '$compiledInstallerExePath'. Installer output contents: $installerContents"
            }
            $installerStatus = "ok"
            $innoSucceeded = $true
        }
        finally {
            $innoStopwatch.Stop()
            $stepTimings.inno = [pscustomobject]@{
                Status = if ($innoSucceeded) { "ok" } else { "failed" }
                Elapsed = $innoStopwatch.Elapsed
            }
            Write-Host "Inno step $(if ($innoSucceeded) { 'completed' } else { 'finished with errors' }) in $(Format-ElapsedTime -Duration $innoStopwatch.Elapsed)."
        }
    }
}
catch {
    if ($stagingStatus -ne "failed") {
        if ($pyInstallerStatus -eq "not-run" -and $runPyInstaller) {
            $pyInstallerStatus = "failed"
            $pyInstallerError = $_
        }
        elseif ($installerStatus -eq "not-run" -and $runInno) {
            $installerStatus = "failed"
            $installerError = $_
        }
        else {
            $pyInstallerStatus = "failed"
            $pyInstallerError = $_
        }
    }
    else {
        $stagingError = $_
    }
}
finally {
    if ($null -ne $installerSourceRoot -and (Test-Path -LiteralPath $installerSourceRoot)) {
        Remove-Item -LiteralPath $installerSourceRoot -Recurse -Force
    }
}

if ($null -ne $stagingError) {
    $pipelineStopwatch.Stop()
    Write-ReleaseSummary -TotalElapsed $pipelineStopwatch.Elapsed -PythonPath $pythonInterpreterPath -PyInstallerPath $pyInstallerInvocation.DisplayText
    throw $stagingError
}

if ($null -ne $pyInstallerError) {
    $pipelineStopwatch.Stop()
    Write-ReleaseSummary -TotalElapsed $pipelineStopwatch.Elapsed -PythonPath $pythonInterpreterPath -PyInstallerPath $pyInstallerInvocation.DisplayText
    throw $pyInstallerError
}

function Assert-RequiredPathExists {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Expected $Label at '$Path' was not found."
    }
}

if ($null -ne $installerError) {
    $pipelineStopwatch.Stop()
    Write-ReleaseSummary -TotalElapsed $pipelineStopwatch.Elapsed -PythonPath $pythonInterpreterPath -PyInstallerPath $pyInstallerInvocation.DisplayText
    throw $installerError
}

Write-Host "Final artifacts:"
Write-Host "  dist root: $buildOutputRoot"
Write-Host "  installer root: $installerOutputRoot"

if ($runPyInstaller) {
    $desktopExePath = Join-Path $buildOutputRoot "ass-gui\ass-gui.exe"
    Write-Host "  dist executable: $desktopExePath"
    Assert-RequiredPathExists -Path $desktopExePath -Label "PyInstaller output executable"
}

if ($runInno) {
    $installerExePath = Join-Path $installerOutputRoot "ActionShellScript-Setup.exe"
    Write-Host "  installer executable: $installerExePath"
    Assert-RequiredPathExists -Path $installerExePath -Label "installer output executable"

    Write-PackagingNotes `
        -ProjectVersion $projectVersion `
        -ProjectFileVersion $projectFileVersion `
        -InstallerExePath $installerExePath
}

$pipelineStopwatch.Stop()
Write-ReleaseSummary -TotalElapsed $pipelineStopwatch.Elapsed -PythonPath $pythonInterpreterPath -PyInstallerPath $pyInstallerInvocation.DisplayText
Write-Host "Release pipeline complete."
