from __future__ import annotations

from pathlib import Path


def test_docs_reference_the_live_wrapper_from_tools_not_build() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_root = repo_root / "docs"

    docs_files = [
        docs_root / "index.md",
        docs_root / "user" / "ass_cli_quickstart.md",
    ]

    for docs_file in docs_files:
        text = docs_file.read_text(encoding="utf-8")
        assert "build/record_and_play_live.ps1" not in text

    wrapper_docs_path = docs_root / "user" / "record_and_play_live_wrapper.md"
    wrapper_docs = wrapper_docs_path.read_text(encoding="utf-8")
    assert "build/record_and_play_live.ps1" not in wrapper_docs
    assert "tools/record_and_play_live.ps1" in wrapper_docs

    assert "-ValidateOnly" in wrapper_docs
    assert "playback_repeat" in wrapper_docs
    assert "playback_demo_live" in wrapper_docs
    assert "playback_ass_play" in wrapper_docs
