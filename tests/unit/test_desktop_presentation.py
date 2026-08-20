from __future__ import annotations

from pathlib import Path

from core.playback.playback_result import PlaybackResult
from core.scripting.diagnostics import TextSpan
from core.scripting.diagnostics import DiagnosticSeverity
from core.scripting.diagnostics import DiagnosticBag
from apps.desktop.presentation import (
    build_analysis_summary_lines,
    build_debug_summary_lines,
    build_diagnostics_html,
    build_diagnostics_text,
    build_document_summary_lines,
    build_formatted_preview_text,
    build_playback_output_text,
    build_playback_summary_lines,
    build_raw_recording_text,
)
from editor.document.script_document import ScriptDocument
from application.script_document_language_service import ScriptDocumentLanguageService
from editor.language_services.parse_service import ParseService
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis
from core.recording.recording_session import RecordingSession, RecordingState
from editor.document.document_version import DocumentVersion


def test_build_document_summary_lines_reflects_path_and_edit_state() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="line one\nline two\n",
        is_dirty=True,
        last_saved_version=3,
        source_session_id="session-1",
        source_action_count=7,
        generated_from_recording=True,
        recording_conversion_route="direct_import",
        source_capture_excluded_main_window=True,
    )

    lines = build_document_summary_lines(
        document,
        path=Path("sample.ass"),
        analysis_stale=True,
        editor_dirty=True,
    )

    assert "Document ID: doc-1" in lines
    assert "Path: sample.ass" in lines
    assert "Document dirty: True" in lines
    assert "Editor dirty: True" in lines
    assert "Analysis stale after edits: True" in lines
    assert "Recording conversion route: Direct import" in lines
    assert "Recording exclusion: enabled (main window excluded during recording)" in lines
    assert "Generated from recording: True" in lines


def test_build_document_summary_lines_describes_recording_exclusion_state() -> None:
    document = ScriptDocument(
        document_id="doc-1",
        text="",
        recording_conversion_route="promote_generated",
        source_capture_excluded_main_window=False,
    )

    lines = build_document_summary_lines(document)

    assert "Recording exclusion: disabled (main window included during recording)" in lines
    assert "Recording conversion route: Promote generated script" in lines


def test_build_analysis_summary_lines_and_diagnostics_text() -> None:
    document = ScriptDocument(document_id="doc-2", text="Func Demo()\nEndFunc\n")
    analysis = ParseService().parse_document(document)

    summary_lines = build_analysis_summary_lines(
        analysis,
        analysis_stale=False,
        source_text=document.text,
    )
    diagnostics_text = build_diagnostics_text(analysis, source_text=document.text)

    assert "Parse success: True" in summary_lines
    assert "Syntax phase: passed" in summary_lines
    assert "Semantic phase: passed" in summary_lines
    assert "Syntax diagnostics: 0" in summary_lines
    assert "Semantic diagnostics: 0" in summary_lines
    assert "Diagnostics count: 0" in summary_lines
    assert diagnostics_text == "<none>"


def test_build_analysis_summary_lines_describes_refresh_scope_and_stale_state() -> None:
    document = ScriptDocument(document_id="doc-2a", text="Func Demo()\nEndFunc\n")
    analysis = ParseService().parse_document(document)

    fresh_lines = build_analysis_summary_lines(
        analysis,
        analysis_stale=False,
        source_text=document.text,
    )
    stale_lines = build_analysis_summary_lines(
        analysis,
        analysis_stale=True,
        source_text=document.text,
    )

    assert "Analysis status: current" in fresh_lines
    assert "Analysis phase: syntax passed" in fresh_lines
    assert "Analysis reflects the current editor text." in fresh_lines
    assert "Refresh scope: current editor text only" in fresh_lines
    assert "Not refreshed: saved file state or preview output" in fresh_lines
    assert "Analysis status: stale after edits" in stale_lines
    assert "Analysis phase: stale" in stale_lines
    assert "Analysis is stale after edits. Click Analyze to refresh the current editor text." in stale_lines


def test_build_analysis_summary_lines_includes_first_diagnostic_preview() -> None:
    document = ScriptDocument(document_id="doc-2b", text="Fir x = 1 to 10\n")
    analysis = ParseService().parse_document(document)

    summary_lines = build_analysis_summary_lines(
        analysis,
        analysis_stale=False,
        source_text=document.text,
    )

    assert "First diagnostic: ERROR PAR004 at line 1, column 5" in summary_lines
    assert "Preview: Expected 'newline'." in summary_lines


def test_build_analysis_summary_lines_marks_semantic_phase_failure_separately() -> None:
    document = ScriptDocument(
        document_id="doc-2c",
        text="Func CallThing()\nEndFunc\nCallThng()\n",
    )
    analysis = ScriptDocumentLanguageService().analyze(document)
    diagnostics_text = build_diagnostics_text(analysis, source_text=document.text)

    summary_lines = build_analysis_summary_lines(
        analysis,
        analysis_stale=False,
        source_text=document.text,
    )

    assert "Parse success: True" in summary_lines
    assert "Syntax phase: passed" in summary_lines
    assert "Semantic phase: failed" in summary_lines
    assert "Syntax diagnostics: 0" in summary_lines
    assert "Semantic diagnostics: 1" in summary_lines
    assert "Diagnostics count: 1" in summary_lines
    assert "First diagnostic: ERROR SEM008 at line 3, column 1" in summary_lines
    assert "Preview: Unsupported function: CallThng. Did you mean CallThing?" in summary_lines
    assert "Unsupported function: CallThng. Did you mean CallThing?" in diagnostics_text


def test_build_diagnostics_html_uses_severity_specific_colors() -> None:
    diagnostics = DiagnosticBag()
    diagnostics.warning("SEM100", "Soft issue", TextSpan(0, 4), source_name="doc-3")
    analysis = ScriptDocumentAnalysis(
        document_id="doc-3",
        document_version=DocumentVersion(),
        root=type("Root", (), {"statements": []})(),
        diagnostics=diagnostics,
    )

    html = build_diagnostics_html(analysis, source_text="warn")

    assert html is not None
    assert "#f9a825" in html
    assert "#fff8e1" in html
    assert "#f0d27a" in html
    assert "SEM100" in html
    assert "doc-3" not in html


def test_build_debug_summary_lines_include_pause_details_and_final_outcome() -> None:
    snapshot = type(
        "DebugSnapshot",
        (),
        {
            "state": "paused",
            "pause_reason": "breakpoint",
            "current_line": 17,
        },
    )()

    lines = build_debug_summary_lines(
        snapshot,
        pause_summary="paused on Breakpoint in Helper (depth 2) at line 17",
        paused_line=17,
        paused_reason="Breakpoint",
        paused_function="Helper",
        stack_depth=2,
        final_run_outcome="failed: boom",
    )

    assert lines == [
        "Debug session status: paused",
        "Pause summary: paused on Breakpoint in Helper (depth 2) at line 17",
        "Paused line: 17",
        "Paused reason: Breakpoint",
        "Paused function: Helper",
        "Stack depth: 2",
        "Final run outcome: failed: boom",
    ]


def test_build_formatted_preview_text_uses_placeholder_for_empty_documents() -> None:
    assert build_formatted_preview_text("") == "# <empty script document>"


def test_build_raw_recording_text_renders_session_json() -> None:
    session = RecordingSession(
        session_id="session-1",
        state=RecordingState.STOPPED,
        started_at_ms=10,
        stopped_at_ms=20,
        events=[{"type": "mouse_move", "x": 1, "y": 2}],
    )

    text = build_raw_recording_text(session)

    assert '"session_id": "session-1"' in text
    assert '"state": "stopped"' in text
    assert '"started_at_ms": 10' in text
    assert '"events": [' in text


def test_build_raw_recording_text_uses_placeholder_for_missing_session() -> None:
    assert build_raw_recording_text(None) == "<none>"


def test_build_playback_output_text_includes_diagnostics_source_label() -> None:
    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=2,
        success=True,
        delay_ms=125,
        playback_mode="preview",
        sendkeys_transport="key taps",
        console_output=["alpha\n"],
        diagnostics_output=["trace one\n", "trace two"],
    )

    text = build_playback_output_text(result)

    assert "Console output:\nalpha" in text
    assert "Delay per event (ms): 125" in text
    assert "Playback mode: preview" in text
    assert "SendKeys transport: key taps" in text
    assert "Diagnostics output (DiagWrite/DiagWriteLn):" in text
    assert "trace one" in text
    assert "trace two" in text


def test_build_playback_summary_lines_include_effective_delay() -> None:
    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=2,
        success=True,
        delay_ms=125,
        playback_mode="live",
        sendkeys_transport="text events",
    )

    lines = build_playback_summary_lines(result)

    assert lines == [
        "Playback result:",
        "Source kind: script_document",
        "Source ID: script-1",
        "Executed event count: 2",
        "Success: True",
        "Delay per event (ms): 125",
        "Playback mode: live",
        "SendKeys transport: text events",
    ]
