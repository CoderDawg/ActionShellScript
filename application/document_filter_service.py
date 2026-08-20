from __future__ import annotations

from dataclasses import dataclass

from core.filtering import FilterResult, FilterStage, build_default_filter_registry
from core.filtering.documents.document_filter_pipeline import DocumentFilterPipeline
from editor.document.script_document import ScriptDocument
from infrastructure.debug_logger import get_diagnostic_logger


log = get_diagnostic_logger("document_filter_service")


@dataclass(frozen=True, slots=True)
class DocumentFilterSummary:
    profile_id: str
    document_id: str
    line_count: int
    applied_filters: tuple[str, ...]


class DocumentFilterService:
    def __init__(self, pipeline: DocumentFilterPipeline | None = None) -> None:
        self._pipeline = pipeline or DocumentFilterPipeline(
            registry=build_default_filter_registry()
        )

    def list_profile_ids(self) -> tuple[str, ...]:
        return self._pipeline.registry.list_profile_ids(FilterStage.DOCUMENT)

    def apply_filter(
        self,
        document: ScriptDocument,
        profile_id: str,
    ) -> FilterResult[ScriptDocument]:
        log.info(
            "Document filter service started",
            event_id="filter.document.started",
            profile_id=profile_id,
            document_id=document.document_id,
            line_count=document.line_count(),
            is_dirty=document.is_dirty,
        )
        profile = self._pipeline.registry.get_profile(FilterStage.DOCUMENT, profile_id)
        result = self._pipeline.apply(document, profile)
        log.info(
            "Document filter service completed",
            event_id="filter.document.completed",
            profile_id=profile_id,
            document_id=result.value.document_id,
            line_count=result.value.line_count(),
            applied_filters=result.applied_filters,
        )
        return result

    def summarize(
        self,
        result: FilterResult[ScriptDocument],
        *,
        profile_id: str,
    ) -> DocumentFilterSummary:
        summary = DocumentFilterSummary(
            profile_id=profile_id,
            document_id=result.value.document_id,
            line_count=result.value.line_count(),
            applied_filters=tuple(result.applied_filters),
        )
        log.trace(
            "Document filter summary created",
            event_id="filter.document.summary",
            profile_id=summary.profile_id,
            document_id=summary.document_id,
            line_count=summary.line_count,
            applied_filters=summary.applied_filters,
        )
        return summary
