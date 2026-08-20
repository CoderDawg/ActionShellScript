from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_pwsh() -> str | None:
    for candidate in ("pwsh", "powershell"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def test_release_stage_matches_desktop_hidden_tab_defaults(tmp_path: Path) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is required to stage the release tree.")

    stage_root = ROOT / "tmp_pytest_release_stage" / tmp_path.name
    try:
        result = subprocess.run(
            [
                pwsh,
                "-File",
                str(ROOT / "packaging" / "scripts" / "build_release.ps1"),
                "-Stage",
                "-Clean",
                "-StageRoot",
                str(stage_root),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0, result.stderr or result.stdout

        checks = [
            (
                ROOT / "apps" / "desktop" / "settings.py",
                stage_root / "apps" / "desktop" / "settings.py",
                "hidden_workspace_tabs_strip_collapsed: bool = True",
            ),
            (
                ROOT / "apps" / "desktop" / "preferences_dialog.py",
                stage_root / "apps" / "desktop" / "preferences_dialog.py",
                'Enabled by default. Start with the hidden tab selections strip collapsed whenever hidden tabs exist.',
            ),
            (
                ROOT / "apps" / "desktop" / "preferences_dialog.py",
                stage_root / "apps" / "desktop" / "preferences_dialog.py",
                "hidden_workspace_tabs_strip_collapsed_checkbox.setChecked(True)",
            ),
            (
                ROOT / "apps" / "desktop" / "preferences_dialog.py",
                stage_root / "apps" / "desktop" / "preferences_dialog.py",
                "hidden_workspace_tabs_strip_collapsed=True,",
            ),
            (
                ROOT / "application" / "persistence" / "desktop_settings_service.py",
                stage_root / "application" / "persistence" / "desktop_settings_service.py",
                'payload.get("hidden_workspace_tabs_strip_collapsed", True)',
            ),
        ]

        for source_path, staged_path, expected_snippet in checks:
            source_text = _read(source_path)
            staged_text = _read(staged_path)
            assert expected_snippet in source_text
            assert expected_snippet in staged_text
    finally:
        shutil.rmtree(stage_root.parent, ignore_errors=True)
