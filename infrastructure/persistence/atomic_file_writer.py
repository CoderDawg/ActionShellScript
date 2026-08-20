from __future__ import annotations

import os
import tempfile
from pathlib import Path


class AtomicFileWriter:
    def write_text(
        self,
        path: Path,
        text: str,
        *,
        encoding: str = "utf-8",
        newline: str = "",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding=encoding,
            newline=newline,
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)

        try:
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
