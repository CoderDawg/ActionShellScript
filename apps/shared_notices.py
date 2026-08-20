from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from apps.shared_assets import resolve_asset_path


_NOTICE_ROOT = Path(__file__).resolve().parents[1]
_NOTICE_ROOT_ENV = "ASS_SHARED_NOTICE_ROOT"


def shared_notice_path(relative_path: str | Path) -> Path:
    return resolve_asset_path(
        relative_path,
        source_dir=_NOTICE_ROOT,
        env_var=_NOTICE_ROOT_ENV,
        frozen_relative_dirs=(".",),
    )


@lru_cache(maxsize=1)
def load_attribution_notice_text() -> str:
    return shared_notice_path("ATTRIBUTION.txt").read_text(encoding="utf-8")
