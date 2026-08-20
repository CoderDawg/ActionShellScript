from __future__ import annotations

from dataclasses import asdict

from application.script_document_language_service import ScriptDocumentLanguageService
from core.scripting.documents.script_document_factory import ScriptDocumentFactory
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.script_document import ScriptDocument
from editor.language_services.diagnostics_service import DiagnosticsService
from editor.language_services.parse_service import ParseService


class CountingParseService(ParseService):
    def __init__(self) -> None:
        self.calls = 0

    def parse_document(self, document: ScriptDocument):
        self.calls += 1
        return super().parse_document(document)


def test_language_service_reports_parse_success_for_promoted_script_document() -> None:
    document = ScriptDocumentFactory().create_from_generated_script(
        GeneratedScript(
            text='Hotkey("ctrl", "c")\n',
            source_session_id="session-17",
            source_action_count=1,
        )
    )

    analysis = ScriptDocumentLanguageService().analyze(document)

    assert analysis.parse_succeeded is True
    assert len(analysis.root.statements) == 1
    assert analysis.diagnostics.has_errors is False
    assert len(analysis.diagnostics.items) == 0


def test_language_service_preserves_promoted_document_metadata_during_analysis() -> None:
    document = ScriptDocumentFactory().create_from_generated_script(
        GeneratedScript(
            text='Hotkey("ctrl", "c")\n',
            source_session_id="session-18",
            source_action_count=1,
        )
    )
    metadata_before_analysis = asdict(document)

    analysis = ScriptDocumentLanguageService().analyze(document)

    assert analysis.parse_succeeded is True
    assert asdict(document) == metadata_before_analysis


def test_language_service_uses_a_single_parse_pass_for_one_document_snapshot() -> None:
    document = ScriptDocumentFactory().create_from_generated_script(
        GeneratedScript(
            text='Hotkey("ctrl", "c")\n',
            source_session_id="session-19",
            source_action_count=1,
        )
    )
    parse_service = CountingParseService()
    diagnostics_service = DiagnosticsService(parse_service=parse_service)
    language_service = ScriptDocumentLanguageService(
        parse_service=parse_service,
        diagnostics_service=diagnostics_service,
    )

    analysis = language_service.analyze(document)

    assert parse_service.calls == 1
    assert analysis.parse_succeeded is True
    assert analysis.document_version == document.version
