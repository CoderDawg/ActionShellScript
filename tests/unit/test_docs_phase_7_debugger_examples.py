from __future__ import annotations

from pathlib import Path


def test_phase_7_debugger_docs_cover_ass_play_flag() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    index_text = (repo_root / "docs" / "index.md").read_text(encoding="utf-8")
    checklist_text = (
        repo_root / "docs" / "internal" / "architecture" / "phase_7_checklist.md"
    ).read_text(encoding="utf-8")
    boundary_text = (
        repo_root / "docs" / "internal" / "architecture" / "phase_7_debugger_boundary.md"
    ).read_text(encoding="utf-8")
    cheat_sheet_text = (
        repo_root / "docs" / "user" / "cli_cheat_sheet.md"
    ).read_text(encoding="utf-8")

    assert "ass-debug script .\\generated.ass --step --ass-play" in index_text
    assert (
        "Add `--ass-play` when the script is SendKeys-heavy and you want printable characters to reach the target as key taps instead of text events"
        in index_text
    )

    assert "ass-debug script path\\to\\document.ass --ass-play" in checklist_text
    assert "DOSBox" in checklist_text

    assert "ass-debug script .\\generated.ass --step --breakpoint 12 --ass-play" in boundary_text
    assert (
        "Use `--ass-play` when the script is SendKeys-heavy and needs printable characters to arrive as key taps instead of text events"
        in boundary_text
    )

    assert (
        "| `ass-debug` | Source subcommand: `script`; options: `--step`, `--breakpoint`, `--ass-play` |"
        in cheat_sheet_text
    )
    assert "per-keystroke delivery" in cheat_sheet_text
