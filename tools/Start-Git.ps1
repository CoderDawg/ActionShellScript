$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$safeDirectory = $repoRoot.Path

git config --global --get-all safe.directory
git config --global --add safe.directory $safeDirectory
#git config --global --unset-all safe.directory $safeDirectory

