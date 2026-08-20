from __future__ import annotations

from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument
from core.scripting.formatter import FormatOptions
from editor.language_services.formatting_service import FormattingService


def test_formatting_service_formats_script_document_text_without_mutating_document() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="Func Demo(a,b)\r\nCallThing(1,2)\r\nEndFunc\r\n",
    )

    service = FormattingService()

    formatted = service.format_document(document)

    assert formatted == (
        "Func Demo( a, b )\n"
        "    CallThing(1, 2)\n"
        "EndFunc\n"
    )
    assert document.text == "Func Demo(a,b)\r\nCallThing(1,2)\r\nEndFunc\r\n"
    assert document.version == DocumentVersion()
    assert document.is_dirty is False


def test_formatting_service_uses_configured_indent_policy() -> None:
    document = ScriptDocument(
        document_id="doc-2",
        text="Func Demo()\r\nCallThing()\r\nEndFunc\r\n",
    )

    service = FormattingService(options=FormatOptions(indent="\t"))

    assert service.format_document(document) == "Func Demo()\n\tCallThing()\nEndFunc\n"

    service.set_options(FormatOptions(indent="  "))

    assert service.format_document(document) == "Func Demo()\n  CallThing()\nEndFunc\n"


def test_formatting_service_exposes_live_options_for_preference_sync() -> None:
    service = FormattingService()

    assert service.options.indent == "    "

    service.set_options(FormatOptions(indent="\t"))

    assert service.options.indent == "\t"


def test_formatting_service_preserves_semicolon_separated_statements() -> None:
    document = ScriptDocument(
        document_id="doc-3",
        text='Hotkey("ctrl", "c");Hotkey("alt", "v")\n',
    )

    service = FormattingService()

    assert service.format_document(document) == 'Hotkey("ctrl", "c");Hotkey("alt", "v")\n'
