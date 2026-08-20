from __future__ import annotations

from pathlib import Path


def test_monitor_info_demo_is_linked_from_key_docs() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    root_readme = repo_root / "README.md"
    docs_index = repo_root / "docs" / "index.md"
    quickstart_doc = repo_root / "docs" / "user" / "struct_and_dll_quickstart.md"
    interop_doc = repo_root / "docs" / "user" / "structs_and_dlls.md"
    layout_doc = repo_root / "docs" / "user" / "struct_layout_contract.md"
    samples_readme = repo_root / "samples" / "README.md"
    expected_link = "samples/monitor_info_demo.ass"
    wrapper_flow_link = "samples/README.md#monitor-info-wrapper-demo"
    assert expected_link in root_readme.read_text(encoding="utf-8")
    assert expected_link in quickstart_doc.read_text(encoding="utf-8")
    assert expected_link in interop_doc.read_text(encoding="utf-8")
    assert wrapper_flow_link in docs_index.read_text(encoding="utf-8")
    assert "## Monitor Info Wrapper Demo" in samples_readme.read_text(encoding="utf-8")
    assert "GetMonitorInfoEx" in samples_readme.read_text(encoding="utf-8")
    assert "Monitor Info Wrapper Path" in layout_doc.read_text(encoding="utf-8")


def test_monitor_info_demo_sample_matches_the_wrapper_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sample_text = (repo_root / "samples" / "monitor_info_demo.ass").read_text(encoding="utf-8")

    assert "Struct MonitorInfoEx" in sample_text
    assert "szDevice As String" in sample_text
    assert "Dim monitor_info_ex = GetMonitorInfoEx(monitor_handle)" in sample_text
    assert "Dim monitor_info = GetMonitorInfo(monitor_handle)" in sample_text
