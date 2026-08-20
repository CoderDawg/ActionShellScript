from __future__ import annotations

from pathlib import Path


def test_string_helpers_demo_is_linked_from_the_samples_readme() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    samples_readme = repo_root / "samples" / "README.md"
    sample_script = repo_root / "samples" / "string_helpers_demo.ass"

    readme_text = samples_readme.read_text(encoding="utf-8")
    script_text = sample_script.read_text(encoding="utf-8")

    assert "## String Helpers Demo" in readme_text
    assert "ass-debug script .\\samples\\string_helpers_demo.ass" in readme_text
    assert "StringCompare(\"Alpha\", \"alpha\")" in script_text
    assert "RegexEscape(\"a.b\")" in script_text
    assert "RegexIsMatch(\"Ada Lovelace\", \"(\\w+)\\s+(\\w+)\")" in script_text
    assert "RegexInStr(\"one two one two one\", \"one\", 5)" in script_text
    assert "RegexMatch(\"Ada Lovelace\", \"(\\w+)\\s+(\\w+)\")" in script_text
    assert "RegexReplace(\"a1b2c3\", \"(\\d)\", \"[$1]\")" in script_text
    assert "StringReplace(\"abcdef\", 3, \"XYZ\")" in script_text
    assert "RegexEscape()" in readme_text
    assert "RegexIsMatch()" in readme_text
    assert "RegexInStr()" in readme_text
    assert "RegexMatch()" in readme_text
    assert "RegexReplace()" in readme_text
