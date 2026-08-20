from __future__ import annotations

from pathlib import Path


def test_cli_docs_list_the_help_launcher_explicitly() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    cheat_sheet_text = (repo_root / "docs" / "user" / "cli_cheat_sheet.md").read_text(
        encoding="utf-8"
    )
    assert "## Standalone Launchers" in cheat_sheet_text
    assert "| `ass-help` | `docs_path` |" in cheat_sheet_text

    spec_text = (repo_root / "docs" / "user" / "ass_cli_spec.md").read_text(
        encoding="utf-8"
    )
    assert "## Related Launchers" in spec_text
    assert "| `ass-help` | Launch the standalone help browser for bundled docs." in spec_text
    assert "the `help` command" in spec_text
