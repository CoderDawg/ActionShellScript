from __future__ import annotations

from dataclasses import asdict

from core.scripting.diagnostics import TextSpan
from application.script_document_language_service import ScriptDocumentLanguageService
from application.script_document_service import ScriptDocumentService
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.document_version import DocumentVersion
from editor.language_services.formatting_service import FormattingService


def test_phase_5_flow_promotes_generated_script_and_runs_language_services() -> None:
    generated = GeneratedScript(
        text="Func CallThing()\nEndFunc\nCallThng()\n",
        source_session_id="session-14",
        source_action_count=2,
    )

    document_service = ScriptDocumentService()
    language_service = ScriptDocumentLanguageService()
    formatting_service = FormattingService()

    document = document_service.promote_generated_script(generated)
    metadata_before_analysis = asdict(document)
    analysis = language_service.analyze(document)
    formatted = formatting_service.format_document(document)
    summary = document_service.summarize(document)

    assert document.text == generated.text
    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False
    assert len(analysis.root.statements) == 2
    assert analysis.parse_succeeded is True
    assert analysis.syntax_diagnostics.has_errors is False
    assert len(analysis.semantic_diagnostics.items) == 1
    assert analysis.semantic_diagnostics.items[0].code == "SEM008"
    assert (
        analysis.semantic_diagnostics.items[0].message
        == "Unsupported function: CallThng. Did you mean CallThing?"
    )
    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "SEM008"
    assert diagnostic.message == "Unsupported function: CallThng. Did you mean CallThing?"
    assert formatted == (
        "Func CallThing()\n"
        "EndFunc\n"
        "CallThng()\n"
    )
    assert document.text == generated.text
    assert asdict(document) == metadata_before_analysis
    assert summary.version == 1
    assert summary.line_count == 3


def test_phase_5_language_services_do_not_mutate_promoted_document_authority() -> None:
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-16",
        source_action_count=1,
    )
    document = ScriptDocumentService().promote_generated_script(generated)
    metadata_before_analysis = asdict(document)

    analysis = ScriptDocumentLanguageService().analyze(document)

    assert analysis.parse_succeeded is True
    assert analysis.diagnostics.items == []
    assert asdict(document) == metadata_before_analysis
    assert document.document_id == metadata_before_analysis["document_id"]
    assert document.source_session_id == "session-16"
    assert document.source_action_count == 1
    assert document.generated_from_recording is True


def test_phase_5_parse_and_diagnostics_share_absolute_token_spans() -> None:
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-17",
        source_action_count=1,
    )
    document = ScriptDocumentService().promote_generated_script(generated)
    document.replace_text('Hotkey("ctrl", "c")\nDim = 1\n')

    analysis = ScriptDocumentLanguageService().analyze(document)

    assert analysis.parse_succeeded is False
    assert len(analysis.diagnostics.items) == 1
    assert analysis.diagnostics.items[0].span == TextSpan(24, 25)
    assert analysis.diagnostics.items[0].format_header(document.text).startswith(
        f"{document.document_id}:2:5: ERROR PAR001:"
    )


def test_phase_5_document_diagnostics_keep_absolute_spans_at_eof_recovery() -> None:
    generated = GeneratedScript(
        text="Func Demo()\nReturn 1\n",
        source_session_id="session-18",
        source_action_count=1,
    )
    document = ScriptDocumentService().promote_generated_script(generated)

    analysis = ScriptDocumentLanguageService().analyze(document)

    assert analysis.parse_succeeded is False
    assert len(analysis.diagnostics.items) == 2
    assert {diagnostic.code for diagnostic in analysis.diagnostics.items} == {"PAR001"}
    assert {diagnostic.span for diagnostic in analysis.diagnostics.items} == {
        TextSpan(len(document.text), len(document.text) + 1),
    }
    assert all(
        diagnostic.format_header(document.text).startswith(
            f"{document.document_id}:3:1: ERROR PAR001:"
        )
        for diagnostic in analysis.diagnostics.items
    )
