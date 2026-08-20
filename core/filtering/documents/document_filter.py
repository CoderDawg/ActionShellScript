from __future__ import annotations

from typing import Protocol

from editor.document.script_document import ScriptDocument

from ..filter_profile import FilterProfile


class DocumentFilter(Protocol):
    filter_id: str

    def apply(
        self,
        source: ScriptDocument,
        profile: FilterProfile,
    ) -> ScriptDocument: ...
