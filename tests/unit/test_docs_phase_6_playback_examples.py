from __future__ import annotations

import re
from pathlib import Path


def test_phase_6_walkthrough_docs_use_ass_cli_play_examples() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_files = [
        repo_root / "docs" / "index.md",
        repo_root / "docs" / "user" / "ass_cli_quickstart.md",
        repo_root / "docs" / "user" / "open_script_guide.md",
        repo_root / "docs" / "internal" / "architecture" / "phase_6_checklist.md",
        repo_root / "docs" / "internal" / "architecture" / "phase_6_document_boundary.md",
        repo_root / "docs" / "user" / "gui_preference_spec.md",
    ]

    for docs_file in docs_files:
        text = docs_file.read_text(encoding="utf-8")
        assert "ass-play script" not in text
        assert "ass-play recording" not in text

    index_text = (repo_root / "docs" / "index.md").read_text(encoding="utf-8")
    assert "The checked-in [SendKeys Key Tap Transport Demo](../samples/README.md#sendkeys-key-tap-transport-demo) is the canonical live-demo repro for this path:" in index_text
    assert "ass-cli play recording .\\samples\\click.json" in index_text
    assert "ass-cli play script .\\generated.ass --mode live --demo-live --ass-play --show-events" in index_text
    assert "ass-cli play script .\\samples\\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events" in index_text
    assert "When you want script playback to emit SendKeys printable characters as key taps, add `--ass-play`." in index_text

    quickstart_text = (repo_root / "docs" / "user" / "ass_cli_quickstart.md").read_text(
        encoding="utf-8"
    )
    assert "For a deterministic live walkthrough that exercises SendKeys key taps, use the checked-in [SendKeys Key Tap Transport Demo](../../samples/README.md#sendkeys-key-tap-transport-demo):" in quickstart_text
    assert "ass-cli play recording --mode preview" in quickstart_text
    assert "ass-cli play script .\\samples\\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events" in quickstart_text

    samples_readme_text = (repo_root / "samples" / "README.md").read_text(encoding="utf-8")
    assert "## SendKeys Key Tap Transport Demo" in samples_readme_text
    assert "canonical repro for the SendKeys transport work" in samples_readme_text
    assert "ass-cli play script .\\samples\\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events" in samples_readme_text

    open_script_text = (
        repo_root / "docs" / "user" / "open_script_guide.md"
    ).read_text(encoding="utf-8")
    assert (
        "ass-cli play script .\\document.ass --mode live --demo-live --ass-play"
        in open_script_text
    )


def test_ass_cli_play_user_docs_and_coverage_pages_use_the_new_command_name() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_files = [
        repo_root / "README.md",
        repo_root / "docs" / "user" / "ass_cli_spec.md",
        repo_root / "docs" / "user" / "builtin_coverage_map.md",
        repo_root / "docs" / "user" / "cli_cheat_sheet.md",
    ]

    for docs_file in docs_files:
        text = docs_file.read_text(encoding="utf-8")
        assert re.search(r"(?<!-)\bass-play\b", text) is None

    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "[SendKeys Key Tap Transport Demo](samples/README.md#sendkeys-key-tap-transport-demo)" in readme_text

    spec_text = (repo_root / "docs" / "user" / "ass_cli_spec.md").read_text(
        encoding="utf-8"
    )
    assert "ass-cli play script generated.ass --mode live --demo-live --ass-play" in spec_text
    assert "If the script only writes text, `ass-cli play` will show console output and diagnostics" in spec_text

    coverage_text = (
        repo_root / "docs" / "user" / "builtin_coverage_map.md"
    ).read_text(encoding="utf-8")
    assert "ass-cli play" in coverage_text
    assert "Write` | implemented | Writes into runtime console output" in coverage_text

    cheat_sheet_text = (repo_root / "docs" / "user" / "cli_cheat_sheet.md").read_text(
        encoding="utf-8"
    )
    assert "| `ass-cli play` |" in cheat_sheet_text
    assert "--ass-play" in cheat_sheet_text
