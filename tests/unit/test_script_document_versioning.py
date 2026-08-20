from __future__ import annotations

from application.script_document_service import ScriptDocumentService
from core.scripting.documents.script_document_factory import ScriptDocumentFactory
from core.scripting.generation.generated_script import GeneratedScript
from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument


def test_script_document_starts_with_document_version() -> None:
    document = ScriptDocument(document_id="doc-1", text="line one")

    assert document.version == DocumentVersion(value=1)


def test_replace_text_advances_document_version() -> None:
    document = ScriptDocument(document_id="doc-1", text="line one")

    document.replace_text("line two")

    assert document.version == DocumentVersion(value=2)
    assert document.is_dirty is True


def test_replace_text_with_identical_text_does_not_advance_document_version() -> None:
    document = ScriptDocument(document_id="doc-1", text="line one")

    document.replace_text("line one")

    assert document.version == DocumentVersion(value=1)
    assert document.is_dirty is False


def test_script_document_service_summary_flattens_document_version() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="line one\nline two",
        version=DocumentVersion(value=3),
        is_dirty=True,
        source_session_id="session-1",
    )

    summary = ScriptDocumentService().summarize(document)

    assert summary.version == 3
    assert isinstance(summary.version, int)
    assert summary.last_saved_version is None


def test_script_document_factory_creates_documents_with_document_version() -> None:
    generated = GeneratedScript(
        text="SendText(\"hello\")\n",
        source_session_id="session-1",
        source_action_count=4,
    )

    document = ScriptDocumentFactory().create_from_generated_script(generated)

    assert document.version == DocumentVersion()
    assert document.is_dirty is False
    assert document.last_saved_version is None
