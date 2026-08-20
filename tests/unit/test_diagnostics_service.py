from __future__ import annotations

import pytest

from core.scripting.documents.script_document_factory import ScriptDocumentFactory
from core.scripting.generation.generated_script import GeneratedScript
from core.scripting.diagnostics import TextSpan
from editor.document.script_document import ScriptDocument
from editor.language_services.diagnostics_service import DiagnosticsService
from editor.language_services.parse_service import ParseService


def test_diagnostics_service_reuses_current_analysis_without_reparsing() -> None:
    generated = GeneratedScript(
        text='Hotkey("ctrl", "c")\n',
        source_session_id="session-12",
        source_action_count=1,
    )
    document = ScriptDocumentFactory().create_from_generated_script(generated)
    document.replace_text("Dim = 1\n")
    analysis = ParseService().parse_document(document)

    diagnostics = DiagnosticsService().diagnostics_for_document(
        document,
        analysis=analysis,
    )

    assert diagnostics is analysis.diagnostics
    assert diagnostics.has_errors is True
    assert len(diagnostics.items) == 1
    assert diagnostics.items[0].span == TextSpan(4, 5)
    assert document.text == "Dim = 1\n"


def test_diagnostics_service_rejects_stale_analysis_for_updated_document() -> None:
    document = ScriptDocumentFactory().create_from_generated_script(
        GeneratedScript(
            text='Hotkey("ctrl", "c")\n',
            source_session_id="session-13",
            source_action_count=1,
        )
    )
    analysis = ParseService().parse_document(document)
    document.replace_text('Hotkey("ctrl", "c")\nDim = 1\n')

    assert analysis.is_stale_for(document) is True

    with pytest.raises(ValueError, match="stale"):
        DiagnosticsService().diagnostics_for_document(document, analysis=analysis)


def test_diagnostics_service_runs_semantic_analysis_when_no_analysis_is_provided() -> None:
    document = ScriptDocument(
        document_id="session-14",
        text="Return 1\n",
    )

    diagnostics = DiagnosticsService().diagnostics_for_document(document)

    assert len(diagnostics.items) == 1
    assert diagnostics.items[0].code == "SEM004"
    assert diagnostics.items[0].message == "Return statement used outside of function"
    assert diagnostics.items[0].span == TextSpan(0, 8)
