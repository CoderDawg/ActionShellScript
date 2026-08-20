from __future__ import annotations

import shutil
import subprocess
import sysconfig
from pathlib import Path

import pytest


def _resolve_ass_cli_executable() -> str | None:
    executable = shutil.which("ass-cli")
    if executable:
        return executable

    scripts_dir = Path(sysconfig.get_path("scripts") or "")
    for candidate_name in ("ass-cli.exe", "ass-cli.cmd", "ass-cli.bat", "ass-cli"):
        candidate = scripts_dir / candidate_name
        if candidate.exists():
            return str(candidate)

    return None


def test_installed_ass_cli_executable_runs_filter_recording_list_profiles() -> None:
    executable = _resolve_ass_cli_executable()
    if executable is None:
        pytest.skip("ass-cli executable is not installed in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [executable, "filter-recording", "--list-profiles"],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    assert "Available recording filter profiles:" in result.stdout
    assert "mouse_jitter_cleanup" in result.stdout
    assert result.stderr == ""


def test_installed_ass_cli_executable_runs_sendkeys_live_demo_script_playback() -> None:
    executable = _resolve_ass_cli_executable()
    if executable is None:
        pytest.skip("ass-cli executable is not installed in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    sample_path = repo_root / "samples" / "sendkeys_key_taps_demo.ass"
    result = subprocess.run(
        [
            executable,
            "play",
            "script",
            str(sample_path),
            "--mode",
            "live",
            "--demo-live",
            "--ass-play",
            "--show-events",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    assert "Playback mode          : live" in result.stdout
    assert "Playback success       : True" in result.stdout
    assert "SendKeys transport     : key taps" in result.stdout
    assert "Dispatched host calls (SendKeys key taps mode):" in result.stdout
    assert '"action": "key_down"' in result.stdout
    assert '"action": "key_up"' in result.stdout
    assert '"action": "send_text"' not in result.stdout
    assert '"type": "text"' not in result.stdout
    assert result.stderr == ""
