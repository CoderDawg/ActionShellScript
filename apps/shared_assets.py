from __future__ import annotations

import os
import sys
from pathlib import Path


_SHARED_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
_SHARED_ASSET_ROOT_ENV = "ASS_SHARED_ASSET_ROOT"


def _asset_dirs(
    *,
    source_dir: Path,
    env_var: str,
    frozen_relative_dirs: tuple[str, ...],
) -> tuple[Path, ...]:
    dirs: list[Path] = []

    asset_root = os.environ.get(env_var, "").strip()
    if asset_root:
        dirs.append(Path(asset_root).expanduser())

    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
        executable_root = Path(sys.executable).resolve().parent
        for relative_dir in frozen_relative_dirs:
            dirs.extend(
                [
                    bundle_root / relative_dir,
                    bundle_root.parent / relative_dir,
                    executable_root / relative_dir,
                ]
            )

    dirs.append(source_dir)

    unique_dirs: list[Path] = []
    for directory in dirs:
        if directory not in unique_dirs:
            unique_dirs.append(directory)
    return tuple(unique_dirs)


def resolve_asset_path(
    relative_path: str | Path,
    *,
    source_dir: Path,
    env_var: str,
    frozen_relative_dirs: tuple[str, ...] = ("assets",),
) -> Path:
    asset_path = Path(relative_path)
    for directory in _asset_dirs(
        source_dir=source_dir,
        env_var=env_var,
        frozen_relative_dirs=frozen_relative_dirs,
    ):
        candidate = directory / asset_path
        if candidate.is_file():
            return candidate

        # Some frozen bundles have historically embedded data files under a
        # directory named after the file itself. Keep supporting that layout so
        # older builds still resolve assets correctly.
        nested_candidate = candidate / asset_path.name
        if nested_candidate.is_file():
            return nested_candidate
    return source_dir / asset_path


def shared_asset_path(relative_path: str | Path) -> Path:
    return resolve_asset_path(
        relative_path,
        source_dir=_SHARED_ASSET_DIR,
        env_var=_SHARED_ASSET_ROOT_ENV,
    )
