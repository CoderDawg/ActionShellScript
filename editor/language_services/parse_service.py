from __future__ import annotations

from core.scripting.diagnostics import DiagnosticBag
from core.scripting.lexer import lex
from core.scripting.parser import Parser
from editor.document.script_document import ScriptDocument
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis


class ParseService:
    def parse_document(self, document: ScriptDocument) -> ScriptDocumentAnalysis:
        syntax_diagnostics = DiagnosticBag()
        tokens = lex(
            document.text,
            diagnostics=syntax_diagnostics,
            source_name=document.document_id,
        )
        parser = Parser(
            tokens,
            diagnostics=syntax_diagnostics,
            source_name=document.document_id,
        )
        root = parser.parse()
        diagnostics = DiagnosticBag()
        diagnostics.extend(syntax_diagnostics.items)
        return ScriptDocumentAnalysis(
            document_id=document.document_id,
            document_version=document.version,
            root=root,
            diagnostics=diagnostics,
            syntax_diagnostics=syntax_diagnostics,
        )
