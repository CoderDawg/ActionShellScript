from __future__ import annotations

from editor.document.script_document import ScriptDocument
from editor.language_services.diagnostics_service import DiagnosticsService
from editor.language_services.parse_service import ParseService
from editor.language_services.semantic_analysis_service import SemanticAnalysisService
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis


class ScriptDocumentLanguageService:
    def __init__(
        self,
        parse_service: ParseService | None = None,
        diagnostics_service: DiagnosticsService | None = None,
        semantic_service: SemanticAnalysisService | None = None,
    ) -> None:
        self._parse_service = parse_service or ParseService()
        self._semantic_service = semantic_service or SemanticAnalysisService()
        self._diagnostics_service = diagnostics_service or DiagnosticsService(
            parse_service=self._parse_service,
            semantic_service=self._semantic_service,
        )

    def analyze(self, document: ScriptDocument) -> ScriptDocumentAnalysis:
        analysis = self._parse_service.parse_document(document)
        semantic_diagnostics = self._semantic_service.analyze(analysis)
        analysis.semantic_diagnostics.extend(semantic_diagnostics.items)
        analysis.diagnostics.extend(semantic_diagnostics.items)
        self._diagnostics_service.diagnostics_for_document(
            document,
            analysis=analysis,
        )
        return analysis
