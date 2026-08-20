from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


_MANIFEST_PATH = Path(__file__).resolve().with_name("asset_manifest.json")


@dataclass(frozen=True, slots=True)
class PackagingAssetManifest:
    runtime_assets: tuple[str, ...]
    installer_setup_icon: str


def asset_manifest_path() -> Path:
    return _MANIFEST_PATH


def load_asset_manifest(manifest_path: Path | str | None = None) -> PackagingAssetManifest:
    path = Path(manifest_path) if manifest_path is not None else _MANIFEST_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    runtime_assets = tuple(str(asset) for asset in payload["runtime_assets"])
    installer_setup_icon = str(payload["installer_setup_icon"])
    return PackagingAssetManifest(
        runtime_assets=runtime_assets,
        installer_setup_icon=installer_setup_icon,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m packaging.asset_manifest")
    parser.add_argument(
        "--manifest-path",
        default=str(_MANIFEST_PATH),
        help="Path to the manifest JSON file.",
    )
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument(
        "--runtime-assets",
        action="store_true",
        help="Print the runtime asset paths, one per line.",
    )
    output.add_argument(
        "--installer-setup-icon",
        action="store_true",
        help="Print the installer setup icon path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manifest = load_asset_manifest(args.manifest_path)

    if args.runtime_assets:
        print("\n".join(manifest.runtime_assets))
        return 0

    print(manifest.installer_setup_icon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
