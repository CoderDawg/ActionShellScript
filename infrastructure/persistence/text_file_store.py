from __future__ import annotations

from pathlib import Path

from infrastructure.persistence.atomic_file_writer import AtomicFileWriter


class TextFileStore:
    def __init__(
        self,
        writer: AtomicFileWriter | None = None,
    ) -> None:
        self._writer = writer or AtomicFileWriter()

    def load(self, path: Path, *, encoding: str = "utf-8") -> str:
        return path.read_text(encoding=encoding)

    def save(
        self,
        path: Path,
        text: str,
        *,
        encoding: str = "utf-8",
        newline: str = "",
    ) -> None:
        self._writer.write_text(path, text, encoding=encoding, newline=newline)
