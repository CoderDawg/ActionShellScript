from __future__ import annotations

import os
import sys
from pathlib import Path


def _shared_asset_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    bundle_root = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    candidate = bundle_root / "assets"
    if candidate.exists():
        return candidate
    return None


asset_root = _shared_asset_root()
if asset_root is not None:
    os.environ.setdefault("ASS_SHARED_ASSET_ROOT", str(asset_root))
