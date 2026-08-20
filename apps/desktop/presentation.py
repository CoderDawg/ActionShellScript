from __future__ import annotations

import html
import json
from pathlib import Path

from core.debugging.debug_state import DebugState
from core.scripting.diagnostics import SourcePosition
from core.playback.playback_result import PlaybackResult
from core.recording.recording_session import RecordingSession
from editor.document.script_document import ScriptDocument
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis


def build_document_summary_lines(
    document: ScriptDocument,
    *,
    path: Path | None = None,
    analysis_stale: bool = False,
    editor_dirty: bool = False,
) -> list[str]:
    if document.recording_conversion_route == "direct_import":
        conversion_route = "Direct import"
    elif document.recording_conversion_route == "promote_generated":
        conversion_route = "Promote generated script"
    elif document.recording_conversion_route is None:
        conversion_route = "<unknown>"
    else:
        conversion_route = document.recording_conversion_route

    lines = [
        f"Document ID: {document.document_id}",
        f"Path: {path if path is not None else '<unsaved>'}",
        f"Version: {document.version.value}",
        f"Line count: {document.line_count()}",
        f"Document dirty: {document.is_dirty}",
        f"Editor dirty: {editor_dirty}",
        f"Analysis stale after edits: {analysis_stale}",
        f"Last saved version: {document.last_saved_version}",
        f"Source session ID: {document.source_session_id}",
        f"Source action count: {document.source_action_count}",
        f"Recording conversion route: {conversion_route}",
        "Recording exclusion: enabled (main window excluded during recording)"
        if document.source_capture_excluded_main_window is True
        else "Recording exclusion: disabled (main window included during recording)"
        if document.source_capture_excluded_main_window is False
        else "Recording exclusion: <unknown>",
        f"Generated from recording: {document.generated_from_recording}",
    ]
    return [line for line in lines if line is not None]


def build_analysis_summary_lines(
    analysis: ScriptDocumentAnalysis | None,
    *,
    analysis_stale: bool = False,
    source_text: str = "",
) -> list[str]:
    if analysis is None:
        return [
            "Analysis status: not run",
            "Analysis phase: not run",
            "Refresh scope: current editor text only",
            "Not refreshed: saved file state or preview output",
            "Click Analyze to populate diagnostics and the analysis summary.",
            "Parse success: <unknown>",
            "Syntax phase: <unknown>",
            "Semantic phase: <unknown>",
            "Syntax diagnostics: 0",
            "Semantic diagnostics: 0",
            "Diagnostics count: 0",
            "Error count: 0",
            "Warning count: 0",
            "Statement count: 0",
        ]

    diagnostics = analysis.diagnostics.items
    syntax_diagnostics = analysis.syntax_diagnostics.items
    semantic_diagnostics = analysis.semantic_diagnostics.items
    errors = sum(1 for diagnostic in diagnostics if diagnostic.severity.value == "error")
    warnings = sum(1 for diagnostic in diagnostics if diagnostic.severity.value == "warning")
    root = analysis.root
    statements = getattr(root, "statements", None)
    statement_count = len(statements) if statements is not None else 0
    stale_note = (
        "Analysis is stale after edits. Click Analyze to refresh the current editor text."
        if analysis_stale
        else "Analysis reflects the current editor text."
    )
    if analysis_stale:
        phase_text = "stale"
    elif analysis.syntax_diagnostics.has_errors:
        phase_text = "syntax failed"
    elif analysis.semantic_diagnostics.has_errors:
        phase_text = "semantic failed"
    else:
        phase_text = "syntax passed"

    return [
        f"Analysis status: {'stale after edits' if analysis_stale else 'current'}",
        f"Analysis phase: {phase_text}",
        stale_note,
        "Refresh scope: current editor text only",
        "Not refreshed: saved file state or preview output",
        f"Parse success: {analysis.parse_succeeded}",
        f"Syntax phase: {'failed' if analysis.syntax_diagnostics.has_errors else 'passed'}",
        f"Semantic phase: {'failed' if analysis.semantic_diagnostics.has_errors else 'passed'}",
        f"Syntax diagnostics: {len(syntax_diagnostics)}",
        f"Semantic diagnostics: {len(semantic_diagnostics)}",
        f"Diagnostics count: {len(diagnostics)}",
        f"Error count: {errors}",
        f"Warning count: {warnings}",
        f"Statement count: {statement_count}",
        *_build_first_diagnostic_preview_lines(diagnostics, source_text=source_text),
    ]


def build_debug_summary_lines(
    snapshot: DebugState | None,
    *,
    pause_summary: str | None = None,
    paused_line: int | None = None,
    paused_reason: str | None = None,
    paused_function: str | None = None,
    stack_depth: int | None = None,
    final_run_outcome: str | None = None,
) -> list[str]:
    lines: list[str] = []
    if snapshot is not None:
        lines.append(f"Debug session status: {snapshot.state}")
        if pause_summary is not None:
            lines.append(f"Pause summary: {pause_summary}")
        if paused_line is not None:
            lines.append(f"Paused line: {paused_line}")
        if paused_reason is not None:
            lines.append(f"Paused reason: {paused_reason}")
        if paused_function is not None:
            lines.append(f"Paused function: {paused_function}")
        if stack_depth is not None:
            lines.append(f"Stack depth: {stack_depth}")
    if final_run_outcome is not None:
        lines.append(f"Final run outcome: {final_run_outcome}")
    return lines


def build_diagnostics_text(
    analysis: ScriptDocumentAnalysis | None,
    *,
    source_text: str = "",
) -> str:
    if analysis is None or not analysis.diagnostics.items:
        return "<none>"
    return analysis.diagnostics.format_all(source_text)


def build_diagnostics_html(
    analysis: ScriptDocumentAnalysis | None,
    *,
    source_text: str = "",
    live_lines: list[str] | None = None,
) -> str | None:
    analysis_items = analysis.diagnostics.items if analysis is not None else []
    live_lines = list(live_lines or [])
    if not analysis_items and not live_lines:
        return None

    parts: list[str] = [
        '<div style="font-family: monospace; white-space: normal;">',
    ]

    if analysis_items:
        parts.append(
            f'<div style="font-weight: 600; margin: 0 0 6px 0;">Analysis diagnostics: ({len(analysis_items)})</div>'
        )
        for index, diagnostic in enumerate(analysis_items):
            palette = _diagnostic_palette(diagnostic.severity.value)
            severity = html.escape(diagnostic.severity.value.upper())
            code = html.escape(diagnostic.code)
            message = html.escape(diagnostic.message)
            location = _diagnostic_location_text(diagnostic, source_text)
            parts.append(
                "\n".join(
                    [
                        f'<a href="analysis-diagnostic-{index}" style="color: inherit; text-decoration: none;">',
                        f'<div style="margin: 0 0 10px 0; padding: 10px 12px; border: 1px solid {palette["border"]}; border-radius: 6px; background: {palette["background"]};">',
                        '<div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 8px 0;">',
                        f'<span style="padding: 2px 8px; border-radius: 999px; background: {palette["pill"]}; color: {palette["pill_text"]}; font-size: 11px; font-weight: 700;">{severity}</span>',
                        f'<span style="padding: 2px 8px; border-radius: 999px; background: #e8eef9; color: #1f3a66; font-size: 11px; font-weight: 700;">{code}</span>',
                        f'<span style="color: #666666; font-size: 11px;">{location}</span>',
                        "</div>",
                        f'<div style="font-size: 13px; font-weight: 600; color: {palette["text"]}; margin: 0 0 2px 0;">{message}</div>',
                        "</div>",
                        "</a>",
                    ]
                )
            )

    if live_lines:
        if analysis_items:
            parts.append('<div style="height: 8px;"></div>')
        parts.append(
            f'<div style="font-weight: 600; margin: 0 0 6px 0;">Live diagnostics: ({len(live_lines)})</div>'
        )
        live_text = html.escape("\n".join(live_lines))
        parts.append(
            f'<pre style="margin: 0; padding: 8px 10px; border: 1px solid #d8d8d8; border-radius: 4px; background: #fafafa; white-space: pre-wrap; font-family: monospace;">{live_text}</pre>'
        )

    parts.append("</div>")
    return "\n".join(parts)


def _diagnostic_location_text(diagnostic, source_text: str) -> str:
    if diagnostic.span is None or not source_text:
        return "at <unknown>"
    position = SourcePosition.from_index(source_text, diagnostic.span.start)
    return f"at line {position.line}, column {position.column}"


def _build_first_diagnostic_preview_lines(diagnostics, *, source_text: str) -> list[str]:
    if not diagnostics:
        return []

    first = diagnostics[0]
    severity = first.severity.value.upper()
    code = first.code
    location = _diagnostic_location_text(first, source_text)
    message = first.message
    return [
        f"First diagnostic: {severity} {code} {location}",
        f"Preview: {message}",
    ]


def _diagnostic_palette(severity: str) -> dict[str, str]:
    normalized = severity.strip().lower()
    if normalized == "warning":
        return {
            "background": "#fff8e1",
            "border": "#f0d27a",
            "pill": "#f9a825",
            "pill_text": "#3e2723",
            "text": "#4e342e",
        }
    if normalized == "info":
        return {
            "background": "#eef6ff",
            "border": "#b7d3f2",
            "pill": "#1976d2",
            "pill_text": "#ffffff",
            "text": "#183b66",
        }
    return {
        "background": "#fff5f5",
        "border": "#efb8b8",
        "pill": "#d32f2f",
        "pill_text": "#ffffff",
        "text": "#5f2120",
    }


def build_formatted_preview_text(text: str) -> str:
    return text if text else "# <empty script document>"


def build_raw_recording_text(session: RecordingSession | None) -> str:
    if session is None:
        return "<none>"

    payload = {
        "session_id": session.session_id,
        "state": session.state.value,
        "started_at_ms": session.started_at_ms,
        "stopped_at_ms": session.stopped_at_ms,
        "events": [dict(event) for event in session.events],
    }
    return json.dumps(payload, indent=2)


def build_playback_output_text(result: PlaybackResult | None) -> str:
    if result is None:
        return "<none>"

    lines = [
        "Playback result:",
        f"Source kind: {result.source_kind}",
        f"Source ID: {result.source_id}",
        f"Executed event count: {result.executed_event_count}",
        f"Success: {result.success}",
        f"Delay per event (ms): {result.delay_ms}",
        f"Playback mode: {result.playback_mode or '<unknown>'}",
        f"SendKeys transport: {result.sendkeys_transport or '<unknown>'}",
    ]
    if result.error_line is not None:
        lines.append(f"Error line: {result.error_line}")
    if result.error_message:
        lines.append(f"Error message: {result.error_message}")
    lines.extend(["", "Console output:"])
    if result.console_output:
        lines.extend(normalize_output_chunks(result.console_output))
    else:
        lines.append("<none>")
    if result.diagnostics_output:
        lines.extend(["", "Diagnostics output (DiagWrite/DiagWriteLn):"])
        lines.extend(normalize_output_chunks(result.diagnostics_output))
    return "\n".join(lines)


def build_playback_summary_lines(result: PlaybackResult | None) -> list[str]:
    if result is None:
        return []

    lines = [
        "Playback result:",
        f"Source kind: {result.source_kind}",
        f"Source ID: {result.source_id}",
        f"Executed event count: {result.executed_event_count}",
        f"Success: {result.success}",
        f"Delay per event (ms): {result.delay_ms}",
        f"Playback mode: {result.playback_mode or '<unknown>'}",
        f"SendKeys transport: {result.sendkeys_transport or '<unknown>'}",
    ]
    if result.error_line is not None:
        lines.append(f"Error line: {result.error_line}")
    if result.error_message:
        lines.append(f"Error message: {result.error_message}")
    return lines


def normalize_output_chunks(chunks: list[str]) -> list[str]:
    return [chunk[:-1] if chunk.endswith("\n") else chunk for chunk in chunks]
