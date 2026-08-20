from __future__ import annotations

from pathlib import Path


def test_phase_1_record_docs_use_explicit_save_raw_before_session_json_examples() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    expectations = {
        repo_root / "README.md": [
            "ass-cli record --save-raw .\\session.json",
            "ass-cli interpret",
            "ass-cli generate --output .\\generated.ass",
        ],
        repo_root / "docs" / "index.md": [
            "ass-cli record --save-raw .\\session.json",
            "ass-record-interpret --save-raw .\\session.json",
            "The downstream raw-session commands now default to `.\\session.json`",
        ],
        repo_root / "docs" / "user" / "ass_cli_quickstart.md": [
            "ass-cli record --save-raw .\\session.json",
            "ass-cli record-interpret --save-raw .\\session.json",
            "ass-cli interpret",
            "ass-cli play recording --mode preview",
        ],
        repo_root / "docs" / "user" / "ass_cli_spec.md": [
            "ass-cli record --save-raw .\\session.json",
            "ass-cli record-interpret --save-raw .\\session.json",
            "ass-cli open-script --output authoritative.ass",
        ],
        repo_root / "docs" / "user" / "cli_cheat_sheet.md": [
            "`--input <path>` defaults to `.\\session.json`",
            "Records live input, writes raw session JSON with `--save-raw <path>`, and immediately interprets it.",
        ],
    }

    for docs_file, snippets in expectations.items():
        text = docs_file.read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"missing {snippet!r} in {docs_file}"
