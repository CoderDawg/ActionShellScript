from __future__ import annotations

from pathlib import Path

from apps.shared_assets import shared_asset_path


def test_shared_asset_path_points_into_repo_asset_tree() -> None:
    asset_dir = Path(__file__).resolve().parents[2] / "assets"
    assert shared_asset_path("icons/msc_debug-breakpoint.png") == asset_dir / "icons/msc_debug-breakpoint.png"


def test_shared_asset_path_prefers_explicit_bundle_root_env_var(monkeypatch, tmp_path) -> None:
    source_asset_dir = Path(__file__).resolve().parents[2] / "assets"
    asset_root = tmp_path / "bundle-assets"
    icon_dir = asset_root / "icons"
    icon_dir.mkdir(parents=True)

    icon_name = "msc_debug-breakpoint.png"
    bundle_asset_path = icon_dir / icon_name
    bundle_asset_path.write_bytes((source_asset_dir / "icons" / icon_name).read_bytes())

    monkeypatch.setenv("ASS_SHARED_ASSET_ROOT", str(asset_root))

    assert shared_asset_path("icons/msc_debug-breakpoint.png") == bundle_asset_path
