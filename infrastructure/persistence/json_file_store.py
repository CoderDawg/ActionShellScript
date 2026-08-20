from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infrastructure.persistence.atomic_file_writer import AtomicFileWriter


class JsonFileStore:
    def __init__(
        self,
        writer: AtomicFileWriter | None = None,
    ) -> None:
        self._writer = writer or AtomicFileWriter()

    def load(self, path: Path, *, encoding: str = "utf-8") -> dict[str, Any]:
        return json.loads(path.read_text(encoding=encoding))

    def save(
        self,
        path: Path,
        payload: dict[str, Any],
        *,
        encoding: str = "utf-8",
        indent: int = 2,
    ) -> None:
        text = json.dumps(payload, indent=indent)
        self._writer.write_text(path, text, encoding=encoding, newline="")
