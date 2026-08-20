from __future__ import annotations

from pathlib import Path


def test_recording_docs_show_pipe_separated_stop_hotkey_alternates() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    expectations = {
        repo_root / "docs" / "index.md": "Shift+Esc|Ctrl+C",
        repo_root / "docs" / "user" / "ass_cli_quickstart.md": (
            "--stop-hotkey Shift+Esc|Ctrl+C"
        ),
        repo_root / "docs" / "user" / "ass_cli_spec.md": (
            "--stop-hotkey <chord>|<chord>[|...]"
        ),
        repo_root / "docs" / "user" / "cli_cheat_sheet.md": "Shift+Esc|Ctrl+C",
    }

    for docs_file, snippet in expectations.items():
        text = docs_file.read_text(encoding="utf-8")
        assert snippet in text, docs_file

