from __future__ import annotations

from pathlib import Path


def test_converted_script_docs_explain_the_sidecar_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    expectations = {
        repo_root / "README.md": [
            "same-name `.ass.meta.json` sidecar",
            "Keep the `.ass` and `.ass.meta.json` files together",
            "`source_session_id`, `source_action_count`, and `generated_from_recording`",
        ],
        repo_root / "docs" / "index.md": [
            "sibling `.ass.meta.json` sidecar",
            "Keep the `.ass` and `.ass.meta.json` files together",
        ],
        repo_root / "docs" / "user" / "ass_cli_spec.md": [
            "## Script Document Sidecar Contract",
            "full provenance payload",
            "`source_session_id`",
            "`generated_from_recording`",
        ],
        repo_root / "docs" / "user" / "open_script_guide.md": [
            "writes a sibling `.ass.meta.json` file",
            "Keep the `.ass` file and `.ass.meta.json` file together",
        ],
        repo_root / "docs" / "user" / "cli_cheat_sheet.md": [
            "saved converted scripts can include a sibling `.ass.meta.json` provenance file",
            "kept together with their sibling `.ass.meta.json` files",
        ],
    }

    for docs_file, snippets in expectations.items():
        text = docs_file.read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"missing {snippet!r} in {docs_file}"
