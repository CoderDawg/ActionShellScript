from __future__ import annotations

import pytest

from editor.document.document_version import DocumentVersion
from core.scripting.diagnostics import TextSpan
from editor.document.script_document import ScriptDocument
from editor.language_services.parse_service import ParseService


def test_parse_service_parses_script_document_text_without_mutation() -> None:
    document = ScriptDocument(
        document_id="doc-parse-1",
        text='Hotkey("ctrl", "c")\n',
    )

    analysis = ParseService().parse_document(document)

    assert len(analysis.root.statements) == 1
    assert analysis.document_version == DocumentVersion()
    assert analysis.diagnostics.has_errors is False
    assert document.text == 'Hotkey("ctrl", "c")\n'
    assert document.is_dirty is False


def test_parse_service_uses_current_document_text_after_promotion() -> None:
    document = ScriptDocument(
        document_id="doc-parse-2",
        text='Hotkey("ctrl", "c")\n',
    )
    document.replace_text('Hotkey("ctrl", "c")\nDim = 1\n')

    analysis = ParseService().parse_document(document)

    assert analysis.diagnostics.has_errors is True
    assert len(analysis.diagnostics.items) == 1
    assert analysis.diagnostics.items[0].span == TextSpan(24, 25)
    assert analysis.diagnostics.items[0].format_header(document.text).startswith(
        "doc-parse-2:2:5: ERROR PAR001:"
    )


@pytest.mark.parametrize(
    "text, expected_line, expected_column",
    [
        ('Hotkey("ctrl", "c") Hotkey("alt", "v")\n', 1, 21),
        ("Dim x = 1 Dim y = 2\n", 1, 11),
        ("Return 1 Return 2\n", 1, 10),
        ("Goto Label Label:\n", 1, 12),
    ],
)
def test_parse_service_reports_missing_statement_separator_between_statements(
    text: str,
    expected_line: int,
    expected_column: int,
) -> None:
    document = ScriptDocument(
        document_id="doc-parse-4",
        text=text,
    )

    analysis = ParseService().parse_document(document)

    assert analysis.parse_succeeded is False
    assert len(analysis.diagnostics.items) == 1
    diagnostic = analysis.diagnostics.items[0]
    assert diagnostic.code == "PAR004"
    assert diagnostic.message == "Expected 'newline'."
    assert diagnostic.format_header(text).startswith(
        f"doc-parse-4:{expected_line}:{expected_column}: ERROR PAR004:"
    )


@pytest.mark.parametrize(
    "text, expected_count",
    [
        ('Hotkey("ctrl", "c"); Hotkey("alt", "v")\n', 2),
        ("Dim x = 1; Dim y = 2\n", 2),
        ("Return 1;\nReturn 2\n", 2),
    ],
)
def test_parse_service_accepts_semicolon_separated_statements(
    text: str,
    expected_count: int,
) -> None:
    document = ScriptDocument(
        document_id="doc-parse-5",
        text=text,
    )

    analysis = ParseService().parse_document(document)

    assert analysis.parse_succeeded is True
    assert analysis.diagnostics.has_errors is False
    assert len(analysis.root.statements) == expected_count


def test_parse_service_accepts_ternary_expressions_in_assignments() -> None:
    document = ScriptDocument(
        document_id="doc-parse-ternary",
        text='result = (score >= 50) ? "Pass" : "Fail"\n',
    )

    analysis = ParseService().parse_document(document)

    assert analysis.parse_succeeded is True
    assert analysis.diagnostics.has_errors is False
    assert len(analysis.root.statements) == 1


def test_parse_service_accepts_multiline_block_comments_between_statements() -> None:
    document = ScriptDocument(
        document_id="doc-parse-6",
        text='Hotkey("ctrl", "c")\n/* comment\nspanning lines */\nHotkey("alt", "v")\n',
    )

    analysis = ParseService().parse_document(document)

    assert analysis.parse_succeeded is True
    assert analysis.diagnostics.has_errors is False
    assert len(analysis.root.statements) == 2


def test_parse_service_analysis_detects_stale_document_version() -> None:
    document = ScriptDocument(
        document_id="doc-parse-3",
        text='Hotkey("ctrl", "c")\n',
    )

    analysis = ParseService().parse_document(document)
    document.replace_text('Hotkey("ctrl", "c")\nDim = 1\n')

    assert analysis.document_version == DocumentVersion()
    assert analysis.is_stale_for(document) is True
