from __future__ import annotations

from pkgutil import extend_path
from pathlib import Path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_package_dir = Path(__file__).resolve().parent
for _candidate_root in map(Path, __import__("sys").path):
    _candidate_dir = _candidate_root / __name__
    if _candidate_dir == _package_dir:
        continue
    if (_candidate_dir / "version.py").exists():
        _path_entry = str(_candidate_dir)
        if _path_entry not in __path__:
            __path__.append(_path_entry)
        break
