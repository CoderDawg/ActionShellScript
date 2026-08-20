from __future__ import annotations

from pathlib import Path

from packaging.asset_manifest import load_asset_manifest


def test_release_pipeline_reads_version_from_pyproject_and_forwards_it_to_inno() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    build_release_path = repo_root / "packaging" / "scripts" / "build_release.ps1"

    script_text = build_release_path.read_text(encoding="utf-8")

    assert "function Get-ProjectVersion" in script_text
    assert "function ConvertTo-WindowsFileVersion" in script_text
    assert 'Get-Content -LiteralPath $PyProjectPath -Raw' in script_text
    assert 'Join-Path $RepoRoot "pyproject.toml"' in script_text
    assert '$projectVersion = Get-ProjectVersion -PyProjectPath (Join-Path $RepoRoot "pyproject.toml")' in script_text
    assert '$projectFileVersion = ConvertTo-WindowsFileVersion -Version $projectVersion' in script_text
    assert '"/DMyAppVersion=$MyAppVersion"' in script_text
    assert '"/DMyAppFileVersion=$MyAppFileVersion"' in script_text
    assert '"/DInstallerOutputRoot=$InstallerOutputRoot"' in script_text
    assert '"/DInstallerSetupIcon=$InstallerSetupIcon"' in script_text
    assert '$installerSetupIcon = Get-NormalizedFullPath -Path (Join-Path $RepoRoot $assetManifest.installer_setup_icon)' in script_text
    assert '[switch]$PackagingNotesOnly' in script_text
    assert "function Resolve-PackagingNotesInstallerPath" in script_text
    assert 'if ($PackagingNotesOnly) {' in script_text
    assert 'Write-PackagingNotes `' in script_text
    assert '-MyAppVersion $projectVersion' in script_text
    assert '-MyAppFileVersion $projectFileVersion' in script_text
    assert '-InstallerOutputRoot $installerOutputRoot' in script_text
    assert '-InstallerSetupIcon $installerSetupIcon' in script_text
    assert 'Write-Host "  packaging versioning:"' in script_text
    assert 'Write-Host "    project version: $projectVersion"' in script_text
    assert 'Write-Host "    installer version: $projectVersion"' in script_text
    assert 'Write-Host "    windows file version: $projectFileVersion"' in script_text
    assert "function Get-FileSha256" in script_text
    assert "function Write-PackagingNotes" in script_text
    assert 'Write-Host "## Packaging Notes"' in script_text
    assert 'Get-FileHash -LiteralPath $Path -Algorithm SHA256' in script_text
    assert 'Write-Host "- Project version: $literalTick$ProjectVersion$literalTick"' in script_text
    assert 'Write-Host "- Git tag: $literalTick$gitTagVersion$literalTick"' in script_text
    assert 'Write-Host "- Installer/file version: $literalTick$ProjectFileVersion$literalTick"' in script_text
    assert 'Write-Host "- SHA256: $literalTick$installerSha256$literalTick"' in script_text
    assert 'return' in script_text
    assert 'if ($relativePath -eq "docs") {' in script_text
    assert 'internal' in script_text
    assert '-ExcludeDirectories @("__pycache__", ".pytest_cache", ".venv", "build", "dist", "tmp", "logs", "objects-Debug", "objects-RelWithDebInfo", "internal")' in script_text
    assert "function Resolve-PreferredExecutablePath" in script_text
    assert "function Write-SelectedToolPaths" in script_text
    assert 'Join-Path $RepoRoot ".venv\\Scripts\\python.exe"' in script_text
    assert 'Join-Path $RepoRoot ".venv\\Scripts\\pyinstaller.exe"' in script_text
    assert 'Write-Host "Selected tool paths:"' in script_text
    assert 'Write-Host "  python interpreter: $PythonPath"' in script_text
    assert 'Write-Host "  pyinstaller executable: $PyInstallerPath"' in script_text
    assert 'Write-Host "Final artifacts:"' in script_text
    assert 'Write-Host "  dist root: $buildOutputRoot"' in script_text
    assert 'Write-Host "  installer root: $installerOutputRoot"' in script_text
    assert 'Assert-RequiredPathExists -Path $desktopExePath -Label "PyInstaller output executable"' in script_text
    assert 'Assert-RequiredPathExists -Path $installerExePath -Label "installer output executable"' in script_text


def test_release_pipeline_falls_back_to_python_module_when_pyinstaller_exe_is_missing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    build_release_path = repo_root / "packaging" / "scripts" / "build_release.ps1"

    script_text = build_release_path.read_text(encoding="utf-8")

    assert "function Resolve-PyInstallerInvocation" in script_text
    assert 'Join-Path $RepoRoot ".venv\\Scripts\\pyinstaller.exe"' in script_text
    assert "UsePythonModuleFallback = $true" in script_text
    assert 'DisplayText = "$PythonPath -m PyInstaller"' in script_text
    assert '& $PyInstallerInvocation.Command `' in script_text
    assert '-m `' in script_text
    assert 'PyInstaller `' in script_text
    assert '$pyInstallerInvocation = Resolve-PyInstallerInvocation' in script_text
    assert '-PyInstallerInvocation $pyInstallerInvocation' in script_text


def test_release_pipeline_summary_uses_manifest_runtime_asset_count() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    build_release_path = repo_root / "packaging" / "scripts" / "build_release.ps1"
    manifest_path = repo_root / "packaging" / "asset_manifest.json"

    script_text = build_release_path.read_text(encoding="utf-8")
    manifest = load_asset_manifest(manifest_path)

    assert '$runtimeAssetCount = $runtimeAssets.Count' in script_text
    assert '$runtimeAssetCount = 3' not in script_text
    assert len(manifest.runtime_assets) == 4


def test_desktop_bundle_includes_qtpy_packaging_dependency() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec"

    spec_text = spec_path.read_text(encoding="utf-8")

    assert '"packaging.version"' in spec_text


def test_desktop_bundle_includes_attribution_notice() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec"

    spec_text = spec_path.read_text(encoding="utf-8")

    assert 'source_root / "ATTRIBUTION.txt"' in spec_text


def test_desktop_bundle_excludes_internal_docs_tree() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec"

    spec_text = spec_path.read_text(encoding="utf-8")

    assert 'exclude_directory_names={"internal"}' in spec_text


def test_desktop_bundle_keeps_qt_print_support_available() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec"

    spec_text = spec_path.read_text(encoding="utf-8")

    assert '"QtPrintSupport"' not in spec_text


def test_inno_script_keeps_a_standalone_version_fallback() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    installer_path = repo_root / "packaging" / "installer" / "ActionShellScript.iss"

    installer_text = installer_path.read_text(encoding="utf-8")

    assert '#ifndef MyAppVersion' in installer_text
    assert '#define MyAppVersion "0.2.0a2"' in installer_text
    assert '#ifndef MyAppFileVersion' in installer_text
    assert '#define MyAppFileVersion "0.2.0.1"' in installer_text
    assert 'VersionInfoVersion={#MyAppFileVersion}' in installer_text
    assert 'OutputDir="{#InstallerOutputRoot}"' in installer_text
    assert '#endif' in installer_text


def test_inno_script_sources_setup_icon_from_a_define() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    installer_path = repo_root / "packaging" / "installer" / "ActionShellScript.iss"

    installer_text = installer_path.read_text(encoding="utf-8")

    assert 'SetupIconFile={#InstallerSetupIcon}' in installer_text
    assert "retro_pixelated_teal_smiling_frog.ico" not in installer_text


def test_inno_script_removes_app_and_user_data_on_uninstall() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    installer_path = repo_root / "packaging" / "installer" / "ActionShellScript.iss"

    installer_text = installer_path.read_text(encoding="utf-8")

    assert "[UninstallDelete]" in installer_text
    assert 'Type: filesandordirs; Name: "{app}"' in installer_text
    assert 'Type: filesandordirs; Name: "{userappdata}\\ActionShellScript"' in installer_text
