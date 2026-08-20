from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import tomllib

from apps.cli import main as cli_main


def _load_pyproject() -> dict[str, object]:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def test_dispatch_commands_match_public_console_scripts() -> None:
    pyproject = _load_pyproject()
    expected_scripts = tuple(
        script
        for script in pyproject["project"]["scripts"]
        if script not in {"ass-cli", "ass-gui"}
    )
    expected_commands = tuple(script.removeprefix("ass-") for script in expected_scripts)

    assert tuple(cli_main.COMMAND_TARGETS) == expected_commands
    assert {f"ass-{command}" for command in cli_main.COMMAND_TARGETS} == set(
        expected_scripts
    )


def test_dispatcher_defaults_to_record_and_routes_explicit_commands(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_loader(module_name: str, attribute_name: str):
        def runner(argv: list[str] | None) -> int:
            calls.append((f"{module_name}:{attribute_name}", list(argv or [])))
            return 7 if module_name.endswith("record_command") else 13

        return runner

    monkeypatch.setattr(cli_main, "_load_runner", fake_loader)

    assert cli_main.run(["--session-id", "session-1"]) == 7
    assert cli_main.run(["--no-save"]) == 7
    assert cli_main.run(["debug", "--trace"]) == 13
    assert cli_main.run(["filter-shaping", "session.json", "--profile", "smooth_mouse"]) == 13
    assert calls == [
        ("apps.cli.record_command:run", ["--session-id", "session-1"]),
        ("apps.cli.record_command:run", ["--no-save"]),
        ("apps.cli.debug_command:run", ["--trace"]),
        (
            "apps.cli.filter_shaping_command:run",
            ["session.json", "--profile", "smooth_mouse"],
        ),
    ]


def test_dispatcher_uses_standalone_help_launcher_when_frozen(monkeypatch, tmp_path) -> None:
    bundle_root = tmp_path / "bundle"
    help_launcher_dir = bundle_root / "ass-help"
    help_launcher_dir.mkdir(parents=True)
    (help_launcher_dir / "ass-help.exe").write_bytes(b"")

    monkeypatch.setattr(cli_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        cli_main.sys,
        "executable",
        str(bundle_root / "ass-cli" / "ass-cli.exe"),
        raising=False,
    )

    run_calls: list[list[str]] = []
    monkeypatch.setattr(
        cli_main.subprocess,
        "run",
        lambda args, check=False: run_calls.append(list(args)) or SimpleNamespace(returncode=0),
    )

    load_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cli_main,
        "_load_runner",
        lambda module_name, attribute_name: load_calls.append((module_name, attribute_name))
        or (lambda argv: 99),
    )

    assert cli_main.run(["help", "docs/user/cli_cheat_sheet.md"]) == 0
    assert run_calls == [
        [str(help_launcher_dir / "ass-help.exe"), "docs/user/cli_cheat_sheet.md"]
    ]
    assert load_calls == []


def test_module_invocation_prints_dispatcher_help() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.main", "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    assert "Dispatch to the ActionShellScript phase commands." in result.stdout
    assert "help" in result.stdout
    assert "ass-help" in result.stdout
    assert "record" in result.stdout
    assert "ass-record" in result.stdout
    assert "filter-recording" in result.stdout
