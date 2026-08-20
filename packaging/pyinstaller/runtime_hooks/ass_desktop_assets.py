from __future__ import annotations

import os
import sys
from pathlib import Path


def _desktop_asset_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    bundle_root = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    candidate = bundle_root / "apps" / "desktop" / "assets"
    if candidate.exists():
        return candidate
    return None


asset_root = _desktop_asset_root()
if asset_root is not None:
    os.environ.setdefault("ASS_DESKTOP_ASSET_ROOT", str(asset_root))
