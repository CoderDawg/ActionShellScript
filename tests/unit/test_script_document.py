from __future__ import annotations

from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument


def test_script_document_line_count_uses_document_text() -> None:
    document = ScriptDocument(document_id="doc-1", text="one\ntwo\nthree\n")

    assert document.line_count() == 3


def test_script_document_mark_saved_clears_dirty_without_changing_version() -> None:
    document = ScriptDocument(document_id="doc-1", text="one")

    document.replace_text("two")
    document.mark_saved()

    assert document.is_dirty is False
    assert document.version == DocumentVersion(value=2)
    assert document.last_saved_version == 2
