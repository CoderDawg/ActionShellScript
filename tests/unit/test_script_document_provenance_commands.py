from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.filtering import FilterResult
from editor.document.script_document import ScriptDocument
from infrastructure.persistence.script_document_file_store import (
    ScriptDocumentFileStore,
)

from apps.cli import debug_command
from apps.cli import filter_document_command
from apps.cli import play_command
from apps.cli.filter_artifact_io import load_script_document


def _save_recording_provenance_script(tmp_path: Path, filename: str = "source.ass") -> Path:
    path = tmp_path / filename
    ScriptDocumentFileStore().save(
        path,
        ScriptDocument(
            document_id="source-document",
            text='Hotkey("ctrl", "c")\n',
            source_session_id="session-42",
            source_action_count=7,
            generated_from_recording=True,
            recording_conversion_route="promote_generated",
            source_capture_excluded_main_window=True,
        ),
    )
    return path


def test_ass_cli_play_script_loads_recording_provenance_from_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = _save_recording_provenance_script(tmp_path)
    captured: dict[str, ScriptDocument] = {}

    class FakePlaybackService:
        def build_plan_from_script(self, document: ScriptDocument):
            captured["document"] = document
            return SimpleNamespace(
                source_kind="script_document",
                source_id=document.document_id,
                event_count=document.line_count(),
                console_output=[],
                diagnostics_output=[],
                delay_ms_override=None,
                events=[],
            )

        def play_plan(self, plan, request):
            return SimpleNamespace(
                playback_mode=request.mode.value,
                sendkeys_transport=request.sendkeys_transport,
                executed_event_count=plan.event_count,
                success=True,
                error_line=None,
                error_message=None,
            )

        def summarize_plan(self, plan):
            return SimpleNamespace(
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                event_count=plan.event_count,
                console_output=[],
                diagnostics_output=[],
            )

    monkeypatch.setattr(
        play_command,
        "PlaybackService",
        lambda **kwargs: FakePlaybackService(),
    )

    exit_code = play_command.run(["script", str(source_path)])

    assert exit_code == 0
    loaded = captured["document"]
    assert loaded.source_path == str(source_path.resolve())
    assert loaded.source_session_id == "session-42"
    assert loaded.source_action_count == 7
    assert loaded.generated_from_recording is True
    assert loaded.recording_conversion_route == "promote_generated"
    assert loaded.source_capture_excluded_main_window is True


def test_ass_debug_script_loads_recording_provenance_from_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = _save_recording_provenance_script(tmp_path)
    captured: dict[str, ScriptDocument] = {}

    class FakeRuntime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        def compile(self, text: str, source_path: str | None = None):
            self.calls.append((text, source_path))
            return {"compiled": True}

    class FakeController:
        def __init__(self, document: ScriptDocument) -> None:
            self._document = document

        def wait_for_pause(self, timeout: float) -> bool:
            return False

        def snapshot(self):
            return SimpleNamespace(
                session_id="session-99",
                document_id=self._document.document_id,
                state="completed",
                current_line=None,
                breakpoints=(),
                last_exception=None,
                call_stack=[],
                variables=[],
            )

        def sync_from_context(self, context) -> None:
            self.context = context

        def complete(self) -> None:
            self.completed = True

        def resume_continue(self) -> None:
            return None

        def resume_step(self) -> None:
            return None

        def resume_step_over(self) -> None:
            return None

        def resume_step_out(self) -> None:
            return None

    class FakeHandle:
        def __init__(self, document: ScriptDocument) -> None:
            self.session = SimpleNamespace(state="completed")
            self.runtime = FakeRuntime()
            self.controller = FakeController(document)

    class FakeDebuggingService:
        def start_debug_session(
            self,
            document: ScriptDocument,
            request,
            *,
            emit_event=None,
            stop_event=None,
        ):
            captured["document"] = document
            captured["request"] = request
            return FakeHandle(document)

    monkeypatch.setattr(
        debug_command,
        "DebuggingService",
        lambda *args, **kwargs: FakeDebuggingService(),
    )

    exit_code = debug_command.run(["script", str(source_path)])

    assert exit_code == 0
    loaded = captured["document"]
    assert loaded.source_path == str(source_path.resolve())
    assert loaded.source_session_id == "session-42"
    assert loaded.source_action_count == 7
    assert loaded.generated_from_recording is True
    assert loaded.recording_conversion_route == "promote_generated"
    assert loaded.source_capture_excluded_main_window is True


def test_ass_filter_document_output_preserves_recording_provenance_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = _save_recording_provenance_script(tmp_path)
    output_path = tmp_path / "filtered.ass"
    captured: dict[str, ScriptDocument] = {}

    class FakeDocumentFilterService:
        def apply_filter(self, document: ScriptDocument, profile_id: str):
            captured["document"] = document
            captured["profile_id"] = profile_id
            return FilterResult(
                value=document,
                applied_filters=["normalize_document"],
            )

        def summarize(self, result, *, profile_id: str):
            return SimpleNamespace(
                profile_id=profile_id,
                document_id=result.value.document_id,
                line_count=result.value.line_count(),
                applied_filters=tuple(result.applied_filters),
            )

    monkeypatch.setattr(
        filter_document_command,
        "DocumentFilterService",
        lambda: FakeDocumentFilterService(),
    )

    exit_code = filter_document_command.run(
        [
            str(source_path),
            "--profile",
            "normalize_document",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    loaded_source = captured["document"]
    assert loaded_source.source_path == str(source_path.resolve())
    assert loaded_source.source_session_id == "session-42"
    assert loaded_source.source_action_count == 7
    assert loaded_source.generated_from_recording is True
    assert loaded_source.recording_conversion_route == "promote_generated"
    assert loaded_source.source_capture_excluded_main_window is True

    loaded_output = load_script_document(str(output_path))
    assert loaded_output.text == 'Hotkey("ctrl", "c")\n'
    assert loaded_output.source_path == str(output_path.resolve())
    assert loaded_output.source_session_id == "session-42"
    assert loaded_output.source_action_count == 7
    assert loaded_output.generated_from_recording is True
    assert loaded_output.recording_conversion_route == "promote_generated"
    assert loaded_output.source_capture_excluded_main_window is True
