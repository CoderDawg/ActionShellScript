from __future__ import annotations

from core.scripting.formatter import FormatOptions, ScriptFormatter
from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument

from ..filter_profile import FilterProfile


class DocumentNormalizationFilter:
    filter_id = "normalize_document"

    def apply(
        self,
        source: ScriptDocument,
        profile: FilterProfile,
    ) -> ScriptDocument:
        options = _format_options_from_profile(profile)
        formatter = ScriptFormatter(options=options)
        normalized_text = formatter.format_script(source.text)

        return ScriptDocument(
            document_id=source.document_id,
            text=normalized_text,
            version=DocumentVersion(source.version.value),
            is_dirty=False,
            source_session_id=source.source_session_id,
            source_action_count=source.source_action_count,
            generated_from_recording=source.generated_from_recording,
            recording_conversion_route=source.recording_conversion_route,
            source_capture_excluded_main_window=source.source_capture_excluded_main_window,
        )



def _format_options_from_profile(profile: FilterProfile) -> FormatOptions:
    settings = profile.settings
    return FormatOptions(
        indent=str(settings.get("indent", "    ")),
        newline=str(settings.get("newline", "\n")),
        max_blank_lines=int(settings.get("max_blank_lines", 1)),
        keyword_case=str(settings.get("keyword_case", "canonical")),
        final_newline=bool(settings.get("final_newline", True)),
    )
