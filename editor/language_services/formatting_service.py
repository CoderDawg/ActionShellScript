from __future__ import annotations

from core.scripting.formatter import FormatOptions, ScriptFormatter
from editor.document.script_document import ScriptDocument


class FormattingService:
    def __init__(
        self,
        formatter: ScriptFormatter | None = None,
        *,
        options: FormatOptions | None = None,
    ) -> None:
        self._formatter = formatter or ScriptFormatter(options=options)

    def format_document(self, document: ScriptDocument) -> str:
        return self._formatter.format_script(document.text)

    def set_options(self, options: FormatOptions) -> None:
        self._formatter.options = options

    @property
    def options(self) -> FormatOptions:
        return self._formatter.options
