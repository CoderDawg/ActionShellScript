from __future__ import annotations

import json
import uuid
from pathlib import Path

from core.interpretation.interpreted_recording import InterpretedRecording
from core.recording.recording_session import RecordingSession, RecordingState
from core.shaping.shaped_action_sequence import ShapedActionSequence
from editor.document.script_document import (
    ScriptDocument,
)
from infrastructure.persistence.recording_session_file_store import (
    RecordingSessionFileStore,
)
from infrastructure.persistence.script_document_file_store import (
    ScriptDocumentFileStore,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERPRETED_RECORDING_ARTIFACT = "interpreted_recording"
SHAPED_ACTION_SEQUENCE_ARTIFACT = "shaped_action_sequence"
_RECORDING_SESSION_STORE = RecordingSessionFileStore()
_SCRIPT_DOCUMENT_STORE = ScriptDocumentFileStore()


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() and not candidate.exists():
        candidate = REPO_ROOT / candidate
    return candidate


def resolve_recording_session_path(path: str) -> Path:
    return _resolve_path(path)


def _read_json(path: str) -> dict[str, object]:
    resolved = _resolve_path(path)
    return json.loads(resolved.read_text(encoding="utf-8"))


def load_recording_session(path: str) -> RecordingSession:
    return _RECORDING_SESSION_STORE.load(_resolve_path(path))


def load_interpreted_recording(path: str) -> InterpretedRecording:
    payload = _read_json(path)
    if payload.get("artifact_type") not in {None, INTERPRETED_RECORDING_ARTIFACT}:
        raise ValueError("Not an interpreted recording artifact.")

    return InterpretedRecording(
        source_session_id=str(payload["source_session_id"]),
        source_event_count=int(payload["source_event_count"]),
        events=[dict(event) for event in payload.get("events", [])],
    )


def load_shaped_action_sequence(path: str) -> ShapedActionSequence:
    payload = _read_json(path)
    if payload.get("artifact_type") not in {None, SHAPED_ACTION_SEQUENCE_ARTIFACT}:
        raise ValueError("Not a shaped action sequence artifact.")

    return ShapedActionSequence(
        source_session_id=str(payload["source_session_id"]),
        source_interpreted_event_count=int(payload["source_interpreted_event_count"]),
        actions=[dict(action) for action in payload.get("actions", [])],
    )


def load_interpretation_source(
    path: str,
) -> RecordingSession | InterpretedRecording:
    payload = _read_json(path)
    artifact_type = payload.get("artifact_type")
    if artifact_type == INTERPRETED_RECORDING_ARTIFACT:
        return load_interpreted_recording(path)
    if artifact_type is not None:
        raise ValueError(f"Unsupported artifact type: {artifact_type!r}.")
    return _RECORDING_SESSION_STORE.load(_resolve_path(path))


def load_shaping_source(
    path: str,
) -> RecordingSession | InterpretedRecording | ShapedActionSequence:
    payload = _read_json(path)
    artifact_type = payload.get("artifact_type")
    if artifact_type == SHAPED_ACTION_SEQUENCE_ARTIFACT:
        return load_shaped_action_sequence(path)
    if artifact_type == INTERPRETED_RECORDING_ARTIFACT:
        return load_interpreted_recording(path)
    if artifact_type is not None:
        raise ValueError(f"Unsupported artifact type: {artifact_type!r}.")
    return _RECORDING_SESSION_STORE.load(_resolve_path(path))


def load_script_document(path: str) -> ScriptDocument:
    script_path = _resolve_path(path)
    document = _SCRIPT_DOCUMENT_STORE.load(script_path)
    document.document_id = script_path.stem or document.document_id or str(uuid.uuid4())
    return document


def save_recording_session(session: RecordingSession, output_path: str) -> None:
    _RECORDING_SESSION_STORE.save(Path(output_path), session)


def save_interpreted_recording(
    interpreted: InterpretedRecording,
    output_path: str,
) -> None:
    path = Path(output_path)
    if path.parent != Path():
        path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "artifact_type": INTERPRETED_RECORDING_ARTIFACT,
        "schema_version": 1,
        "source_session_id": interpreted.source_session_id,
        "source_event_count": interpreted.source_event_count,
        "events": [dict(event) for event in interpreted.events],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_shaped_action_sequence(shaped: ShapedActionSequence, output_path: str) -> None:
    path = Path(output_path)
    if path.parent != Path():
        path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "artifact_type": SHAPED_ACTION_SEQUENCE_ARTIFACT,
        "schema_version": 1,
        "source_session_id": shaped.source_session_id,
        "source_interpreted_event_count": shaped.source_interpreted_event_count,
        "actions": [dict(action) for action in shaped.actions],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_script_document(document: ScriptDocument, output_path: str) -> None:
    _SCRIPT_DOCUMENT_STORE.save(Path(output_path), document)
