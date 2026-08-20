from __future__ import annotations

from enum import Enum
from pathlib import Path

from apps.shared_assets import resolve_asset_path


_DESKTOP_ASSET_DIR = Path(__file__).resolve().parent / "assets"
_DESKTOP_ASSET_ROOT_ENV = "ASS_DESKTOP_ASSET_ROOT"


class DesktopAsset(str, Enum):
    FROG_ICON = "retro_pixelated_teal_smiling_frog.png"
    FROG_ICON_ICO = "retro_pixelated_teal_smiling_frog.ico"
    COMBO_BOX_ARROW = "combo_box_arrow.svg"
    CODERDAWG_LOGO = "CoderDawg_Logo.png"


def desktop_asset_path(asset: DesktopAsset | str) -> Path:
    name = asset.value if isinstance(asset, DesktopAsset) else asset
    return resolve_asset_path(
        name,
        source_dir=_DESKTOP_ASSET_DIR,
        env_var=_DESKTOP_ASSET_ROOT_ENV,
        frozen_relative_dirs=("apps/desktop/assets", "assets"),
    )
