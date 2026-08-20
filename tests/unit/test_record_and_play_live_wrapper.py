from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

import pytest


def _resolve_pwsh() -> str | None:
    for candidate in ("pwsh", "powershell"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def _preview_command(arguments: list[str]) -> str:
    parts: list[str] = []
    for argument in arguments:
        if re.fullmatch(r"[A-Za-z0-9._:/\\+-]+", argument) or re.fullmatch(
            r"-?\d+(\.\d+)?",
            argument,
        ):
            parts.append(argument)
        else:
            parts.append("'" + argument.replace("'", "''") + "'")
    return " ".join(parts)


def _write_ass_cli_smoke_shim(
    shim_dir: Path,
    *,
    log_path: Path,
    python_exe: str,
) -> Path:
    shim_path = shim_dir / "ass-cli.ps1"
    shim_text = """
$ErrorActionPreference = 'Stop'
$logPath = '{log_path}'

function Write-SmokeLog {{
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    [pscustomobject]@{{
        command = $Command
        args = @($Args)
    }} | ConvertTo-Json -Compress -Depth 8 | Add-Content -LiteralPath $logPath -Encoding utf8
}}

$command = $args[0]
Write-SmokeLog -Command $command -Args $args

if ($command -eq 'record') {{
    $saveRawIndex = [Array]::IndexOf($args, '--save-raw')
    if ($saveRawIndex -lt 0 -or ($saveRawIndex + 1) -ge $args.Count) {{
        throw 'Missing --save-raw.'
    }}
    if ($args.Count -lt 6 -or $args[4] -ne '--stop-hotkey' -or $args[5] -ne 'Shift+Esc|Ctrl+C') {{
        throw 'Unexpected stop hotkey.'
    }}

    $rawPath = $args[$saveRawIndex + 1]
    $session = [ordered]@{{
        session_id = 'wrapper-smoke-session'
        state = 'stopped'
        started_at_ms = 100
        stopped_at_ms = 180
        events = @(
            [ordered]@{{ type = 'key_down'; key = 'ctrl'; timestamp_ms = 100 }},
            [ordered]@{{ type = 'key_down'; key = 'c'; timestamp_ms = 120 }},
            [ordered]@{{ type = 'key_up'; key = 'c'; timestamp_ms = 150 }},
            [ordered]@{{ type = 'key_up'; key = 'ctrl'; timestamp_ms = 180 }}
        )
    }}
    $session | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $rawPath -Encoding utf8

    Write-Host 'Recording started. Press Shift+Esc or Ctrl+C to stop.'
    Write-Host 'Stop hotkey detected: Shift+Esc|Ctrl+C'
    Write-Host ''
    Write-Host 'Recording stopped.'
    Write-Host 'Session ID   : wrapper-smoke-session'
    Write-Host 'State        : stopped'
    Write-Host 'Event count  : 4'
    Write-Host 'Started at   : 100'
    Write-Host 'Stopped at   : 180'
    Write-Host 'Duration (ms): 80'
    exit 0
}}

& '{python_exe}' -m apps.cli.ass_cli @args
exit $LASTEXITCODE
""".format(
        log_path=str(log_path).replace("'", "''"),
        python_exe=python_exe.replace("'", "''"),
    )
    shim_path.write_text(shim_text, encoding="utf-8")
    return shim_path


def test_record_and_play_live_wrapper_emits_a_stable_plan() -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is not available in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "record_and_play_live.ps1"
    artifacts_dir = repo_root / "tmp" / "wrapper-smoke"
    raw_path = artifacts_dir / "recording.json"
    generated_path = artifacts_dir / "generated.ass"

    result = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-Root",
            str(repo_root),
            "-ArtifactsDirectory",
            str(artifacts_dir),
            "-RawPath",
            str(raw_path),
            "-ScriptPath",
            str(generated_path),
            "-PlaybackMode",
            "live",
            "-PlaybackDelayMs",
            "150",
            "-PlaybackRepeat",
            "2",
            "-PlaybackSettleMs",
            "25",
            "-PlaybackShowEvents:$false",
            "-PlaybackDemoLive",
            "-PlaybackAssPlay",
            "-ValidateOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)

    assert plan["root_path"] == str(repo_root)
    assert plan["artifacts_directory"] == str(artifacts_dir)
    assert plan["raw_path"] == str(raw_path)
    assert plan["script_path"] == str(generated_path)
    assert plan["playback_mode"] == "live"
    assert plan["playback_delay_ms"] == 150
    assert plan["playback_repeat"] == 2
    assert plan["playback_settle_ms"] == 25
    assert plan["playback_show_events"] is False
    assert plan["playback_demo_live"] is True
    assert plan["playback_ass_play"] is True
    assert plan["pause_after_generate"] is True

    assert plan["record_arguments"] == [
        "record",
        "--save-raw",
        str(raw_path),
        "--force",
        "--stop-hotkey",
        "Shift+Esc|Ctrl+C",
    ]
    assert plan["generate_arguments"] == [
        "generate",
        "--input",
        str(raw_path),
        "--output",
        str(generated_path),
        "--force",
    ]
    assert plan["play_arguments"] == [
        "play",
        "script",
        str(generated_path),
        "--mode",
        "live",
        "--repeat",
        "2",
        "--delay-ms",
        "150",
        "--settle-ms",
        "25",
        "--demo-live",
        "--ass-play",
    ]

    assert plan["record_message"] == f"ass-cli record --save-raw {raw_path}"
    assert (
        plan["generate_message"]
        == f"ass-cli generate --input {raw_path} --output {generated_path}"
    )
    assert (
        plan["play_message"]
        == f"ass-cli {_preview_command(plan['play_arguments'])}"
    )


def test_record_and_play_live_wrapper_runs_end_to_end_with_demo_live_smoke(
    tmp_path,
) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is not available in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "record_and_play_live.ps1"
    artifacts_dir = tmp_path / "wrapper-smoke"
    raw_path = artifacts_dir / "recording.json"
    generated_path = artifacts_dir / "generated.ass"
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    log_path = tmp_path / "ass-cli-invocations.jsonl"
    _write_ass_cli_smoke_shim(
        shim_dir,
        log_path=log_path,
        python_exe=sys.executable,
    )

    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    pathext = env.get("PATHEXT", "")
    env["PATHEXT"] = (
        pathext + ";.PS1" if ".PS1" not in pathext.upper() else pathext
    )
    env["ASS_WRAPPER_SMOKE_LOG"] = str(log_path)
    env["PYTHON_EXE"] = sys.executable

    result = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-Root",
            str(repo_root),
            "-ArtifactsDirectory",
            str(artifacts_dir),
            "-RawPath",
            str(raw_path),
            "-ScriptPath",
            str(generated_path),
            "-PlaybackMode",
            "live",
            "-PlaybackDelayMs",
            "0",
            "-PlaybackRepeat",
            "1",
            "-PlaybackSettleMs",
            "0",
            "-PlaybackShowEvents:$true",
            "-PlaybackDemoLive",
            "-PlaybackAssPlay",
            "-PauseAfterGenerate:$false",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Press Shift+Esc or Ctrl+C to stop recording." in result.stdout
    assert "This uses the in-memory demo live adapter, not real input." in result.stdout
    assert "Playback mode          : live" in result.stdout
    assert "SendKeys transport     : key taps" in result.stdout
    assert "Dispatched host calls (SendKeys key taps mode):" in result.stdout
    assert "Playback success       : True" in result.stdout
    assert raw_path.exists()
    assert generated_path.exists()
    assert 'Hotkey("ctrl", "c")' in generated_path.read_text(encoding="utf-8")

    log_entries = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [entry["command"] for entry in log_entries] == ["record", "generate", "play"]
    assert log_entries[0]["args"] == [
        "record",
        "--save-raw",
        str(raw_path),
        "--force",
        "--stop-hotkey",
        "Shift+Esc|Ctrl+C",
    ]
    assert log_entries[1]["args"] == [
        "generate",
        "--input",
        str(raw_path),
        "--output",
        str(generated_path),
        "--force",
    ]
    assert log_entries[2]["args"] == [
        "play",
        "script",
        str(generated_path),
        "--mode",
        "live",
        "--repeat",
        "1",
        "--delay-ms",
        "0",
        "--settle-ms",
        "0",
        "--show-events",
        "--demo-live",
        "--ass-play",
    ]


@pytest.mark.parametrize(
    ("diagnostic_path", "expected_path"),
    [
        (None, "default"),
        ("custom-diagnostics.log", "override"),
    ],
)
def test_record_and_play_live_wrapper_resolves_diagnostic_log_path(
    diagnostic_path: str | None,
    expected_path: str,
) -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is not available in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "record_and_play_live.ps1"
    artifacts_dir = repo_root / "tmp" / "wrapper-smoke"
    raw_path = artifacts_dir / "recording.json"
    generated_path = artifacts_dir / "generated.ass"

    env = os.environ.copy()
    env.pop("ASS_DIAGNOSTIC_PATH", None)
    expected_override = None
    if diagnostic_path is not None:
        expected_override = (artifacts_dir / diagnostic_path).resolve()
        env["ASS_DIAGNOSTIC_PATH"] = str(expected_override)

    result = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-Root",
            str(repo_root),
            "-ArtifactsDirectory",
            str(artifacts_dir),
            "-RawPath",
            str(raw_path),
            "-ScriptPath",
            str(generated_path),
            "-PlaybackMode",
            "live",
            "-PlaybackDemoLive",
            "-Diagnostics",
            "-ValidateOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)

    diagnostic_log_path = Path(plan["diagnostic_log_path"])
    if expected_path == "default":
        assert diagnostic_log_path.parent == Path(tempfile.gettempdir())
        assert diagnostic_log_path.name.startswith("actionshellscript_diagnostics_")
        assert diagnostic_log_path.suffix == ".log"
    else:
        assert diagnostic_log_path == expected_override


def test_record_and_play_live_wrapper_assembles_ass_play_command() -> None:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is not available in this test environment.")

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "record_and_play_live.ps1"
    artifacts_dir = repo_root / "tmp" / "wrapper-smoke"
    raw_path = artifacts_dir / "recording.json"
    generated_path = artifacts_dir / "generated.ass"

    result = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-Root",
            str(repo_root),
            "-ArtifactsDirectory",
            str(artifacts_dir),
            "-RawPath",
            str(raw_path),
            "-ScriptPath",
            str(generated_path),
            "-PlaybackMode",
            "live",
            "-PlaybackDelayMs",
            "150",
            "-PlaybackRepeat",
            "2",
            "-PlaybackSettleMs",
            "25",
            "-PlaybackStep",
            "-PlaybackShowEvents:$true",
            "-PlaybackDemoLive",
            "-PlaybackAssPlay",
            "-ValidateOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)

    assert plan["play_arguments"] == [
        "play",
        "script",
        str(generated_path),
        "--mode",
        "live",
        "--repeat",
        "2",
        "--delay-ms",
        "150",
        "--settle-ms",
        "25",
        "--step",
        "--show-events",
        "--demo-live",
        "--ass-play",
    ]
    assert (
        plan["play_message"]
        == f"ass-cli {_preview_command(plan['play_arguments'])}"
    )
