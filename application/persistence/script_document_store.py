from __future__ import annotations

from pathlib import Path
from typing import Protocol

from editor.document.script_document import ScriptDocument


class ScriptDocumentStore(Protocol):
    def load(self, path: Path) -> ScriptDocument: ...

    def save(self, path: Path, document: ScriptDocument) -> None: ...
