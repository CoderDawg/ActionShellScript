from __future__ import annotations

from pathlib import Path

from application.persistence.dirty_state_service import DirtyStateService
from application.persistence.save_coordinator import SaveCoordinator
from application.persistence.unsaved_changes_service import UnsavedChangesService
from core.persistence.persistence_models import PendingAction
from editor.document.document_version import DocumentVersion
from editor.document.script_document import (
    ScriptDocument,
    build_recording_provenance_header,
)
from infrastructure.persistence.script_document_file_store import ScriptDocumentFileStore


def test_script_document_file_store_round_trips_with_sidecar_present(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.ass"
    store = ScriptDocumentFileStore()
    document = ScriptDocument(
        document_id="doc-1",
        text='Hotkey("ctrl", "c")\n',
        version=DocumentVersion(value=3),
        is_dirty=True,
        source_session_id="session-1",
        source_action_count=4,
        generated_from_recording=True,
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=True,
    )

    store.save(path, document)
    loaded = store.load(path)

    assert path.read_text(encoding="utf-8") == (
        build_recording_provenance_header(
            recording_conversion_route="promote_generated",
            source_capture_excluded_main_window=True,
        )
        + document.text
    )
    assert (path.parent / f"{path.name}.meta.json").exists()
    assert loaded.text == document.text
    assert loaded.version == DocumentVersion(value=1)
    assert loaded.is_dirty is False
    assert loaded.last_saved_version == 1
    assert loaded.source_path == str(path)
    assert loaded.source_session_id == "session-1"
    assert loaded.source_action_count == 4
    assert loaded.generated_from_recording is True
    assert loaded.recording_conversion_route == "promote_generated"
    assert loaded.source_capture_excluded_main_window is True


def test_script_document_file_store_round_trips_with_sidecar_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.ass"
    store = ScriptDocumentFileStore()
    body_text = 'SendText("hello")\n'
    path.write_text(
        build_recording_provenance_header(
            recording_conversion_route="direct_import",
            source_capture_excluded_main_window=False,
        )
        + body_text,
        encoding="utf-8",
    )

    loaded = store.load(path)

    assert loaded.text == body_text
    assert loaded.generated_from_recording is True
    assert loaded.recording_conversion_route == "direct_import"
    assert loaded.source_capture_excluded_main_window is False

    round_trip_path = tmp_path / "round_trip.ass"
    store.save(round_trip_path, loaded)

    assert round_trip_path.read_text(encoding="utf-8") == (
        build_recording_provenance_header(
            recording_conversion_route="direct_import",
            source_capture_excluded_main_window=False,
        )
        + body_text
    )
    assert (round_trip_path.parent / f"{round_trip_path.name}.meta.json").exists()


def test_save_coordinator_marks_document_saved_after_persist(tmp_path: Path) -> None:
    path = tmp_path / "saved.ass"
    store = ScriptDocumentFileStore()
    coordinator = SaveCoordinator()
    document = ScriptDocument(
        document_id="doc-2",
        text='SendText("hello")\n',
        source_session_id="session-2",
        source_action_count=1,
        generated_from_recording=True,
        recording_conversion_route="direct_import",
        source_capture_excluded_main_window=False,
    )
    document.replace_text('SendText("goodbye")\n')

    result = coordinator.save_script_document(document, path=path, store=store)

    assert path.read_text(encoding="utf-8") == (
        build_recording_provenance_header(
            recording_conversion_route="direct_import",
            source_capture_excluded_main_window=False,
        )
        + 'SendText("goodbye")\n'
    )
    assert (path.parent / f"{path.name}.meta.json").exists()
    assert document.is_dirty is False
    assert document.last_saved_version == document.version.value
    assert document.source_path == str(path)
    assert result.target.path == path
    assert result.version == document.version.value


def test_dirty_state_service_reports_unsaved_changes() -> None:
    document = ScriptDocument(document_id="doc-3", text="line one\n")
    service = DirtyStateService()

    clean_state = service.summarize(document)
    clean_requirement = service.requires_save_before_close(document)
    document.replace_text("line two\n")
    dirty_state = service.summarize(document)
    dirty_requirement = service.requires_save_before_replace(document)

    assert clean_state.is_dirty is False
    assert clean_state.last_saved_version is None
    assert clean_requirement.requires_save is False
    assert dirty_state.is_dirty is True
    assert dirty_state.version == 2
    assert dirty_requirement.requires_save is True
    assert dirty_requirement.reason is not None


def test_unsaved_changes_service_requires_resolution_for_pending_actions() -> None:
    document = ScriptDocument(document_id="doc-4", text="line one\n")
    service = UnsavedChangesService()

    clean_close = service.requires_resolution(
        document,
        action=PendingAction.CLOSE_DOCUMENT,
    )

    document.replace_text("line two\n")

    close_requirement = service.requires_resolution(
        document,
        action=PendingAction.CLOSE_DOCUMENT,
    )
    replace_requirement = service.requires_resolution(
        document,
        action=PendingAction.OPEN_OTHER_DOCUMENT,
    )
    exit_requirement = service.requires_resolution(
        document,
        action=PendingAction.EXIT_APPLICATION,
    )

    assert clean_close.requires_save is False
    assert close_requirement.requires_save is True
    assert close_requirement.reason == "Document has unsaved changes before close."
    assert replace_requirement.requires_save is True
    assert (
        replace_requirement.reason
        == "Document has unsaved changes before replace."
    )
    assert exit_requirement.requires_save is True
    assert (
        exit_requirement.reason
        == "Document has unsaved changes before application exit."
    )
