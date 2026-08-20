from __future__ import annotations

import shutil
import subprocess
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _resolve_pwsh() -> str | None:
    for candidate in ("pwsh", "powershell"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def _prepare_sync_all_checkout(
    tmp_path: Path,
    packaging_script_body: str,
    release_script_body: str | None = None,
    create_release_stage: bool = False,
) -> tuple[Path, Path]:
    checkout_root = tmp_path / "checkout"
    mirror_root = tmp_path / "mirror"
    scripts_root = checkout_root / "packaging" / "scripts"
    scripts_root.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging" / "scripts" / "sync-all.ps1", scripts_root / "sync-all.ps1")
    shutil.copy2(ROOT / "packaging" / "scripts" / "sync-common.ps1", scripts_root / "sync-common.ps1")
    (scripts_root / "sync-packaging.ps1").write_text(
        packaging_script_body.strip() + "\n",
        encoding="utf-8",
    )
    if release_script_body is not None:
        (scripts_root / "sync-release.ps1").write_text(
            release_script_body.strip() + "\n",
            encoding="utf-8",
        )
    if create_release_stage:
        (checkout_root / "release_stage").mkdir()
    return checkout_root, mirror_root


def test_sync_all_skips_release_when_release_stage_is_missing(tmp_path: Path) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is required to run the packaging sync script.")

    checkout_root, mirror_root = _prepare_sync_all_checkout(
        tmp_path,
        """
[CmdletBinding()]
param(
    [string]$WorktreePackagingRoot,
    [string]$OneDriveRepoRoot
)

Write-Host "Stub packaging sync completed."
""",
    )

    result = subprocess.run(
        [
            pwsh,
            "-File",
            str(checkout_root / "packaging" / "scripts" / "sync-all.ps1"),
            "-OneDriveRepoRoot",
            str(mirror_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=checkout_root,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    stdout = result.stdout
    assert "Syncing packaging..." in stdout
    assert "Syncing release output..." in stdout
    assert "Release output missing, skipping release sync." in stdout
    assert "Sync summary: packaging=ok, release=skipped" in stdout
    assert "Synced packaging and release output." in stdout


def test_sync_all_marks_release_skipped_when_packaging_sync_fails(tmp_path: Path) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is required to run the packaging sync script.")

    checkout_root, mirror_root = _prepare_sync_all_checkout(
        tmp_path,
        """
[CmdletBinding()]
param(
    [string]$WorktreePackagingRoot,
    [string]$OneDriveRepoRoot
)

throw "Stub packaging sync failed."
""",
    )

    result = subprocess.run(
        [
            pwsh,
            "-File",
            str(checkout_root / "packaging" / "scripts" / "sync-all.ps1"),
            "-OneDriveRepoRoot",
            str(mirror_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=checkout_root,
    )

    assert result.returncode != 0

    stdout = result.stdout
    stderr = result.stderr
    assert "Syncing packaging..." in stdout
    assert "Packaging sync failed." in stdout
    assert "Syncing release output..." in stdout
    assert "Sync summary: packaging=failed, release=skipped" in stdout
    assert "Stub packaging sync failed." in stderr or "Stub packaging sync failed." in stdout


def test_sync_all_reports_ok_when_packaging_and_release_sync_succeed(tmp_path: Path) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is required to run the packaging sync script.")

    checkout_root, mirror_root = _prepare_sync_all_checkout(
        tmp_path,
        """
$checkoutRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
@($args) | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $checkoutRoot "packaging-invocation.json") -Encoding utf8
""",
        """
$checkoutRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
@($args) | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $checkoutRoot "release-invocation.json") -Encoding utf8
""",
        create_release_stage=True,
    )
    assert (checkout_root / "release_stage").is_dir()

    result = subprocess.run(
        [
            pwsh,
            "-File",
            str(checkout_root / "packaging" / "scripts" / "sync-all.ps1"),
            "-OneDriveRepoRoot",
            str(mirror_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=checkout_root,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    stdout = result.stdout
    assert "Syncing packaging..." in stdout
    assert "Syncing release output..." in stdout
    assert "Sync summary: packaging=ok, release=ok" in stdout
    assert "Synced packaging and release output." in stdout

    packaging_invocation = json.loads((checkout_root / "packaging-invocation.json").read_text(encoding="utf-8"))
    release_invocation = json.loads((checkout_root / "release-invocation.json").read_text(encoding="utf-8"))
    assert packaging_invocation == ["-OneDriveRepoRoot", str(mirror_root)]
    assert release_invocation == ["-OneDriveRepoRoot", str(mirror_root)]
