from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.scripting.diagnostics import DiagnosticBag
from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument


@dataclass(frozen=True, slots=True)
class ScriptDocumentAnalysis:
    document_id: str
    document_version: DocumentVersion
    root: Any
    diagnostics: DiagnosticBag
    syntax_diagnostics: DiagnosticBag = field(default_factory=DiagnosticBag)
    semantic_diagnostics: DiagnosticBag = field(default_factory=DiagnosticBag)

    @property
    def parse_succeeded(self) -> bool:
        return not self.syntax_diagnostics.has_errors

    def is_stale_for(self, document: ScriptDocument) -> bool:
        return (
            self.document_id != document.document_id
            or self.document_version != document.version
        )
