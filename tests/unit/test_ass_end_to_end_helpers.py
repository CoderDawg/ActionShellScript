from __future__ import annotations

from pathlib import Path


def test_ass_end_to_end_1_describes_real_live_playback_and_uses_ass_cli() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_text = (repo_root / "tools" / "ass_end_to_end_1.ps1").read_text(
        encoding="utf-8"
    )

    assert "This uses the real live playback adapter, not demo mode." in script_text
    assert "ass-cli play recording $raw --mode preview --show-events" in script_text
    assert "ass-cli play recording $raw --mode live --show-events --delay-ms 200" in script_text
    assert "ass-play recording $raw" not in script_text
    assert "in-memory demo live adapter, not real input" not in script_text


def test_ass_end_to_end_2_uses_key_tap_transport_for_script_playback() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_text = (repo_root / "tools" / "ass_end_to_end_2.ps1").read_text(
        encoding="utf-8"
    )
    samples_text = (repo_root / "samples" / "README.md").read_text(encoding="utf-8")

    assert "ass-cli play script $scriptFilt --mode preview --ass-play --show-events" in script_text
    assert (
        "ass-cli play script $scriptFilt --mode live --demo-live --ass-play --show-events"
        in script_text
    )
    assert "This uses the in-memory demo live adapter, not real input." in script_text
    assert "ass-play script $scriptFilt" not in script_text
    assert (
        "ass-cli play script .\\samples\\sendkeys_key_taps_demo.ass --mode live --demo-live --ass-play --show-events"
        in samples_text
    )
