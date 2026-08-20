from __future__ import annotations

from pathlib import Path


def test_enum_examples_demo_is_linked_from_samples_readme_and_docs_index() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    samples_readme = repo_root / "samples" / "README.md"
    docs_index = repo_root / "docs" / "index.md"
    sample_script = repo_root / "samples" / "enum_examples_demo.ass"

    readme_text = samples_readme.read_text(encoding="utf-8")
    index_text = docs_index.read_text(encoding="utf-8")
    script_text = sample_script.read_text(encoding="utf-8")

    assert "## Enum Examples Demo" in readme_text
    assert "ass-debug script .\\samples\\enum_examples_demo.ass" in readme_text
    assert "[Enum Examples Demo](../samples/README.md#enum-examples-demo)" in index_text
    assert "Enum WindowState" in script_text
    assert "DescribeWindowState(Visible)" in script_text
