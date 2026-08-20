from __future__ import annotations

from dataclasses import dataclass

from editor.document.document_version import DocumentVersion
from editor.document.script_document import ScriptDocument

from ..filter_profile import FilterProfile
from ..filter_registry import FilterRegistry, build_default_filter_registry
from ..filter_result import FilterResult
from ..filter_stage import FilterStage


@dataclass(slots=True)
class DocumentFilterPipeline:
    registry: FilterRegistry

    def __init__(self, registry: FilterRegistry | None = None) -> None:
        self.registry = registry or build_default_filter_registry()

    def apply(
        self,
        source: ScriptDocument,
        profile: FilterProfile,
    ) -> FilterResult[ScriptDocument]:
        if profile.target_stage is not FilterStage.DOCUMENT:
            raise ValueError(
                f"Profile {profile.profile_id!r} targets {profile.target_stage.value!r}, not document."
            )

        current = ScriptDocument(
            document_id=source.document_id,
            text=source.text,
            version=DocumentVersion(source.version.value),
            is_dirty=source.is_dirty,
            source_session_id=source.source_session_id,
            source_action_count=source.source_action_count,
            generated_from_recording=source.generated_from_recording,
            recording_conversion_route=source.recording_conversion_route,
            source_capture_excluded_main_window=source.source_capture_excluded_main_window,
        )
        applied_filters: list[str] = []
        notes: list[str] = []

        for filter_id in profile.enabled_filters:
            filter_impl = self.registry.get_filter(filter_id)
            current = filter_impl.apply(current, profile)
            applied_filters.append(filter_id)

        notes.append("Script document text was normalized through the document filter.")
        return FilterResult(value=current, applied_filters=applied_filters, notes=notes)
