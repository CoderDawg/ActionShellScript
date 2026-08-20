from __future__ import annotations

from core.scripting.diagnostics import DiagnosticBag
from editor.document.script_document import ScriptDocument
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis
from editor.language_services.semantic_analysis_service import SemanticAnalysisService

from .parse_service import ParseService


class DiagnosticsService:
    def __init__(
        self,
        parse_service: ParseService | None = None,
        semantic_service: SemanticAnalysisService | None = None,
    ) -> None:
        self._parse_service = parse_service or ParseService()
        self._semantic_service = semantic_service or SemanticAnalysisService()

    def diagnostics_for_document(
        self,
        document: ScriptDocument,
        *,
        analysis: ScriptDocumentAnalysis | None = None,
    ) -> DiagnosticBag:
        if analysis is not None:
            if analysis.is_stale_for(document):
                raise ValueError("analysis result is stale for the current document version")
            return analysis.diagnostics

        analysis = self._parse_service.parse_document(document)
        semantic_diagnostics = self._semantic_service.analyze(analysis)
        analysis.semantic_diagnostics.extend(semantic_diagnostics.items)
        analysis.diagnostics.extend(semantic_diagnostics.items)
        return analysis.diagnostics
