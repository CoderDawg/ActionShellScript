from __future__ import annotations

from pathlib import Path


def test_enum_examples_docs_cover_basic_enum_usage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_file = repo_root / "docs" / "user" / "enum_examples.md"
    text = docs_file.read_text(encoding="utf-8")

    assert "## Window State Helper" in text
    assert "Enum WindowState" in text
    assert "WindowState.Visible" in text
    assert "direct_name: visible" in text
    assert "## Priority Routing" in text
    assert "Enum Priority" in text
    assert "Priority.High" in text
    assert "numeric: urgent" in text
    assert "## Struct Field With Enum" in text
    assert "State As WindowState" in text
    assert "WindowSnapshot(Visible)" in text
    assert "snapshot_state: visible" in text
    assert "## Record Field With Enum" in text
    assert "Record WindowSnapshot" in text
    assert "record_state: visible" in text
