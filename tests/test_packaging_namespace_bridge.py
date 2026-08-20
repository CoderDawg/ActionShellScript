from __future__ import annotations


def test_packaging_namespace_exposes_both_local_assets_and_third_party_modules() -> None:
    import packaging
    from packaging.asset_manifest import load_asset_manifest
    from packaging.version import Version, parse

    assert callable(load_asset_manifest)
    assert Version("1.2.3") == parse("1.2.3")
    assert any("site-packages" in path for path in packaging.__path__)
