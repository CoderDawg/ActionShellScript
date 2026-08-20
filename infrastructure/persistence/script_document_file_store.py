from __future__ import annotations

import json
import uuid
from pathlib import Path

from application.persistence.persistence_errors import (
    PersistenceLoadError,
    PersistenceSaveError,
)
from application.persistence.script_document_store import ScriptDocumentStore
from editor.document.script_document import (
    ScriptDocument,
    build_recording_provenance_header,
    parse_recording_provenance_header,
    strip_recording_provenance_header,
)
from infrastructure.persistence.text_file_store import TextFileStore


class ScriptDocumentFileStore(ScriptDocumentStore):
    def __init__(
        self,
        text_store: TextFileStore | None = None,
    ) -> None:
        self._text_store = text_store or TextFileStore()

    def load(self, path: Path) -> ScriptDocument:
        try:
            raw_text = self._text_store.load(path)
        except OSError as exc:
            raise PersistenceLoadError(
                f"Could not load script document from {path}."
            ) from exc

        text = strip_recording_provenance_header(raw_text)
        provenance = self._load_provenance(path, raw_text)
        document = ScriptDocument(
            document_id=str(uuid.uuid4()),
            text=text,
            source_session_id=provenance["source_session_id"],
            source_action_count=provenance["source_action_count"],
            generated_from_recording=provenance["generated_from_recording"],
            recording_conversion_route=provenance["recording_conversion_route"],
            source_capture_excluded_main_window=(
                provenance["source_capture_excluded_main_window"]
            ),
            source_path=str(path),
        )
        document.mark_saved()
        return document

    def save(self, path: Path, document: ScriptDocument) -> None:
        try:
            self._text_store.save(path, self._serialized_text(document))
            self._save_provenance(path, document)
        except OSError as exc:
            raise PersistenceSaveError(
                f"Could not save script document to {path}."
            ) from exc

    def _load_provenance(self, path: Path, text: str) -> dict[str, object | None]:
        metadata_path = self._metadata_path(path)
        if metadata_path.exists():
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as exc:
                raise PersistenceLoadError(
                    f"Could not load script document metadata from {metadata_path}."
                ) from exc
            return self._normalize_provenance_payload(payload)

        recording_conversion_route, source_capture_excluded_main_window = (
            parse_recording_provenance_header(text)
        )
        return {
            "source_session_id": None,
            "source_action_count": None,
            "generated_from_recording": bool(
                recording_conversion_route is not None
                or source_capture_excluded_main_window is not None
            ),
            "recording_conversion_route": recording_conversion_route,
            "source_capture_excluded_main_window": source_capture_excluded_main_window,
        }

    def _save_provenance(self, path: Path, document: ScriptDocument) -> None:
        payload = self._provenance_payload(document)
        metadata_path = self._metadata_path(path)
        has_provenance = (
            document.source_session_id is not None
            or document.source_action_count is not None
            or document.generated_from_recording
            or document.recording_conversion_route is not None
            or document.source_capture_excluded_main_window is not None
        )
        if not has_provenance:
            if metadata_path.exists():
                metadata_path.unlink()
            return
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _serialized_text(document: ScriptDocument) -> str:
        header = build_recording_provenance_header(
            recording_conversion_route=document.recording_conversion_route,
            source_capture_excluded_main_window=(
                document.source_capture_excluded_main_window
            ),
        )
        if not header:
            return document.text
        return f"{header}{strip_recording_provenance_header(document.text)}"

    @staticmethod
    def _metadata_path(path: Path) -> Path:
        return path.with_name(f"{path.name}.meta.json")

    @staticmethod
    def _provenance_payload(document: ScriptDocument) -> dict[str, object | None]:
        return {
            "source_session_id": document.source_session_id,
            "source_action_count": document.source_action_count,
            "generated_from_recording": document.generated_from_recording,
            "recording_conversion_route": document.recording_conversion_route,
            "source_capture_excluded_main_window": (
                document.source_capture_excluded_main_window
            ),
        }

    @staticmethod
    def _normalize_provenance_payload(
        payload: object,
    ) -> dict[str, object | None]:
        if not isinstance(payload, dict):
            raise PersistenceLoadError("Script document metadata payload is invalid.")
        source_session_id = payload.get("source_session_id")
        source_action_count = payload.get("source_action_count")
        generated_from_recording = _normalize_optional_bool(
            payload.get("generated_from_recording", False)
        )
        recording_conversion_route = payload.get("recording_conversion_route")
        source_capture_excluded_main_window = payload.get(
            "source_capture_excluded_main_window"
        )
        if source_action_count is not None:
            source_action_count = int(source_action_count)
        source_capture_excluded_main_window = _normalize_optional_bool(
            source_capture_excluded_main_window
        )
        return {
            "source_session_id": (
                None if source_session_id is None else str(source_session_id)
            ),
            "source_action_count": source_action_count,
            "generated_from_recording": bool(generated_from_recording),
            "recording_conversion_route": (
                None if recording_conversion_route is None else str(recording_conversion_route)
            ),
            "source_capture_excluded_main_window": source_capture_excluded_main_window,
        }


def _normalize_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return bool(value)
