from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Callable


if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


CommandRunner = Callable[[list[str] | None], int]


COMMAND_TARGETS: dict[str, tuple[str, str]] = {
    "record": ("apps.cli.record_command", "run"),
    "help": ("apps.desktop.help_main", "main"),
    "debug": ("apps.cli.debug_command", "run"),
    "interpret": ("apps.cli.interpret_command", "run"),
    "record-interpret": ("apps.cli.record_interpret_command", "run"),
    "shape": ("apps.cli.shape_command", "run"),
    "generate": ("apps.cli.generate_command", "run"),
    "open-script": ("apps.cli.document_command", "run"),
    "play": ("apps.cli.play_command", "run"),
    "filter-recording": ("apps.cli.filter_recording_command", "run"),
    "filter-interpretation": ("apps.cli.filter_interpretation_command", "run"),
    "filter-shaping": ("apps.cli.filter_shaping_command", "run"),
    "filter-document": ("apps.cli.filter_document_command", "run"),
}
DEFAULT_COMMAND = "record"


def _load_runner(module_name: str, attribute_name: str) -> CommandRunner:
    module = importlib.import_module(module_name)
    runner = getattr(module, attribute_name)
    if not callable(runner):  # pragma: no cover - defensive guard
        raise TypeError(f"{module_name}.{attribute_name} is not callable.")
    return runner


def _standalone_help_launcher_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    executable_root = Path(sys.executable).resolve().parent
    launcher_path = executable_root.parent / "ass-help" / "ass-help.exe"
    if launcher_path.exists():
        return launcher_path
    return None


def _run_help_command(argv: list[str]) -> int:
    launcher_path = _standalone_help_launcher_path()
    if launcher_path is not None:
        completed = subprocess.run([str(launcher_path), *argv], check=False)
        return int(completed.returncode)

    runner = _load_runner("apps.desktop.help_main", "main")
    return runner(argv)


def _build_help_parser() -> argparse.ArgumentParser:
    command_lines = "\n".join(
        f"  {command:<16} ass-{command}" for command in COMMAND_TARGETS
    )
    parser = argparse.ArgumentParser(
        prog="python -m apps.cli.main",
        description="Dispatch to the ActionShellScript phase commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Available commands:\n"
            f"{command_lines}\n\n"
            f"Omit the command to run {DEFAULT_COMMAND!r} for backward compatibility."
        ),
    )
    return parser


def _print_help() -> None:
    _build_help_parser().print_help()


def _dispatch(command: str, argv: list[str]) -> int:
    if command == "help":
        return _run_help_command(argv)

    module_name, attribute_name = COMMAND_TARGETS[command]
    runner = _load_runner(module_name, attribute_name)
    return runner(argv)


def run(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)

    if not tokens:
        return _dispatch(DEFAULT_COMMAND, [])

    first_token = tokens[0]
    if first_token in {"-h", "--help"}:
        _print_help()
        return 0

    if first_token in COMMAND_TARGETS:
        command = tokens.pop(0)
        return _dispatch(command, tokens)

    if first_token.startswith("-"):
        return _dispatch(DEFAULT_COMMAND, tokens)

    print(f"Unknown command: {first_token}", file=sys.stderr)
    _print_help()
    return 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
