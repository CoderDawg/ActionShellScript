from __future__ import annotations

import argparse
import threading
import sys
from pathlib import Path

from application.debugging_service import DebuggingService
from core.debugging.debug_event import DebugEvent
from core.debugging.debug_request import DebugRequest
from core.debugging.source_map import SourceMap
from core.runtime.script_runtime import ScriptRuntimeCancelled
from core.runtime.struct_values import format_debugger_value
from apps.desktop.settings import DesktopPlaybackSettings
from apps.cli.io_announcements import print_input_output
from apps.cli.io_announcements import resolve_display_path
from editor.document.script_document import ScriptDocument
from infrastructure.persistence.script_document_file_store import (
    ScriptDocumentFileStore,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-debug",
        description="Run a ScriptDocument under the debugger and print debug events.",
    )
    subparsers = parser.add_subparsers(dest="source_kind", required=True)

    script_parser = subparsers.add_parser(
        "script",
        help="Debug a script document file.",
    )
    script_parser.add_argument(
        "source_path",
        help="Path to a script document text file.",
    )
    script_parser.add_argument(
        "--step",
        action="store_true",
        help="Stop at every debuggable statement boundary.",
    )
    script_parser.add_argument(
        "--breakpoint",
        action="append",
        type=int,
        default=[],
        help="Add a line breakpoint. Repeat for multiple breakpoints.",
    )
    script_parser.add_argument(
        "--ass-play",
        action="store_true",
        help=(
            "Emit SendKeys printable characters as key taps instead of text "
            "events."
        ),
    )
    return parser


def _load_script_document(path_text: str) -> ScriptDocument:
    path = Path(path_text).resolve()
    document = ScriptDocumentFileStore().load(path)
    document.document_id = str(path)
    document.source_path = str(path)
    return document


def _validate_breakpoints(document: ScriptDocument, lines: list[int]) -> tuple[int, ...]:
    source_map = SourceMap(document.text)
    debuggable_lines = set(source_map.collect_debuggable_source_lines())
    line_count = len(document.text.splitlines())
    validated_lines: list[int] = []
    seen_lines: set[int] = set()

    for line in lines:
        if line in seen_lines:
            raise ValueError(f"Breakpoint line {line} is duplicated.")
        if line < 1 or line > line_count:
            if line_count == 0:
                raise ValueError(f"Breakpoint line {line} is out of range for this empty script.")
            raise ValueError(f"Breakpoint line {line} is out of range for this script (1-{line_count}).")
        if line not in debuggable_lines:
            raise ValueError(f"Breakpoint line {line} is not debuggable.")

        seen_lines.add(line)
        validated_lines.append(line)

    return tuple(validated_lines)


def _format_debug_value(value) -> str:
    return format_debugger_value(value, max_length=80)


def _format_variables(snapshot) -> list[str]:
    if not snapshot.variables:
        return ["<none>"]

    lines: list[str] = []
    for variable in snapshot.variables:
        lines.append(
            f"- {variable.name}: {_format_debug_value(variable.value)} ({variable.type_name})"
        )
    return lines


def _format_call_stack(snapshot) -> list[str]:
    if not snapshot.call_stack:
        return ["<empty>"]

    lines: list[str] = []
    for depth, frame in enumerate(snapshot.call_stack, start=1):
        location = f"line {frame.source_line}" if frame.source_line is not None else "line ?"
        lines.append(f"{depth}. {frame.function_name} @ {location}")
        if frame.locals:
            for local in frame.locals:
                lines.append(
                    f"   - {local.name}: {_format_debug_value(local.value)} ({local.type_name})"
                )
    return lines


def _format_pause_summary(snapshot) -> list[str]:
    lines: list[str] = []
    current_line = snapshot.current_line if snapshot.current_line is not None else "?"
    lines.append(f"Paused at line {current_line}")

    if snapshot.call_stack:
        top_frame = snapshot.call_stack[-1]
        location = f"line {top_frame.source_line}" if top_frame.source_line is not None else "line ?"
        lines.append(f"Current frame: {top_frame.function_name} @ {location}")
    else:
        lines.append("Current frame: <global>")

    return lines


def _format_stack_details(snapshot) -> list[str]:
    if not snapshot.call_stack:
        return ["Call stack:", "  <empty>"]

    lines: list[str] = ["Call stack:"]
    top_index = len(snapshot.call_stack) - 1
    for depth, frame in enumerate(snapshot.call_stack, start=1):
        location = f"line {frame.source_line}" if frame.source_line is not None else "line ?"
        marker = "->" if depth - 1 == top_index else "  "
        lines.append(f"{marker} {depth}. {frame.function_name} @ {location}")
        if frame.locals:
            for local in frame.locals:
                lines.append(
                    f"     - {local.name}: {_format_debug_value(local.value)} ({local.type_name})"
                )
    return lines


def _format_variable_details(snapshot) -> list[str]:
    if not snapshot.variables:
        return ["Variables:", "  <none>"]

    lines: list[str] = ["Variables:"]
    for variable in snapshot.variables:
        lines.append(
            f"  - {variable.name}: {_format_debug_value(variable.value)} ({variable.type_name})"
        )
    return lines


def _format_local_details(snapshot) -> list[str]:
    if not snapshot.call_stack:
        return ["Locals:", "  <global>"]

    top_frame = snapshot.call_stack[-1]
    if not top_frame.locals:
        return ["Locals:", "  <none>"]

    lines: list[str] = ["Locals:"]
    for local in top_frame.locals:
        lines.append(
            f"  - {local.name}: {_format_debug_value(local.value)} ({local.type_name})"
        )
    return lines


def _format_frame_details(snapshot, frame_number: int) -> list[str]:
    if frame_number == 0:
        raise ValueError("Frame command number must be >= 1.")
    if frame_number < 1:
        raise ValueError("Frame command number must be >= 1.")
    if not snapshot.call_stack:
        raise ValueError("No call stack is available.")
    if frame_number > len(snapshot.call_stack):
        raise ValueError(f"Frame number must be between 1 and {len(snapshot.call_stack)}.")

    frame = snapshot.call_stack[frame_number - 1]
    location = f"line {frame.source_line}" if frame.source_line is not None else "line ?"
    lines: list[str] = [f"Frame {frame_number}: {frame.function_name} @ {location}"]
    if frame.locals:
        for local in frame.locals:
            lines.append(
                f"  - {local.name}: {_format_debug_value(local.value)} ({local.type_name})"
            )
    else:
        lines.append("  <none>")
    return lines


def _parse_print_command(command: str, current_line: int | None, line_count: int) -> tuple[int, int]:
    default_radius = 2
    normalized = command.strip().lower()

    if normalized in {"p *", "p all"}:
        return 1, line_count

    if normalized == "p":
        center_line = current_line if isinstance(current_line, int) and current_line > 0 else 1
        start_line = max(1, center_line - default_radius)
        end_line = min(line_count, center_line + default_radius)
        return start_line, end_line

    if normalized.startswith("p "):
        target = normalized[2:].strip()
        if target == "*":
            center_line = current_line if isinstance(current_line, int) and current_line > 0 else 1
        elif target == "all":
            return 1, line_count
        else:
            try:
                center_line = int(target)
            except ValueError as exc:
                raise ValueError("Print command expects '*' , 'all', or a line number.") from exc
            if center_line < 1:
                raise ValueError("Print command line number must be >= 1.")

        start_line = max(1, center_line - default_radius)
        end_line = min(line_count, center_line + default_radius)
        return start_line, end_line

    raise ValueError("Print command expects 'p', 'p *', 'p all', or 'p <line>'.")


def _render_script_slice(
    document: ScriptDocument,
    *,
    current_line: int | None,
    breakpoints: set[int],
    start_line: int,
    end_line: int,
) -> list[str]:
    lines = document.text.splitlines()
    if not lines:
        return ["<empty script>"]

    width = max(1, len(str(len(lines))))
    output: list[str] = []
    for line_number in range(start_line, end_line + 1):
        if line_number < 1 or line_number > len(lines):
            continue
        current_marker = "->" if line_number == current_line else "  "
        breakpoint_marker = "*" if line_number in breakpoints else " "
        output.append(
            f"{current_marker}{breakpoint_marker} {line_number:>{width}} | {lines[line_number - 1]}"
        )
    return output


def _print_script_slice(
    document: ScriptDocument,
    *,
    current_line: int | None,
    breakpoints: set[int],
    start_line: int,
    end_line: int,
    label: str,
) -> None:
    print(label, flush=True)
    for line in _render_script_slice(
        document,
        current_line=current_line,
        breakpoints=breakpoints,
        start_line=start_line,
        end_line=end_line,
    ):
        print(line, flush=True)


def _emit_event(event: DebugEvent, snapshot_getter) -> None:
    line_text = f" line={event.line}" if event.line is not None else ""
    message_text = f" message={event.message}" if event.message else ""
    reason_text = f" reason={event.pause_reason}" if event.pause_reason else ""
    function_text = f" function={event.function_name}" if event.function_name else ""
    print(f"[{event.kind}]{line_text}{function_text}{reason_text}{message_text}", flush=True)

    if event.kind in {"stopped", "exception"}:
        snapshot = snapshot_getter()
        if snapshot is not None:
            print(f"  state: {snapshot.state}", flush=True)
            print("  use 'stack' or 'vars' for details", flush=True)


def _print_pause_help() -> None:
    print("Debugger commands:", flush=True)
    print("  Navigation: Enter/i=step into, o=step over, u=step out, c=continue, g=go, r=restart, q=quit", flush=True)
    print("  g=go to completion, ignore breakpoints", flush=True)
    print("  Inspect   : stack, vars, locals, frame N, frame top", flush=True)
    print("  Source    : p, p *, p all, p N", flush=True)
    print("  Help      : h", flush=True)


def _handle_pause_command(
    command: str,
    *,
    document: ScriptDocument,
    snapshot,
) -> str | None:
    normalized = command.strip().lower()
    if normalized in {"", "step", "i", "into", "step into"}:
        return "step_into"
    if normalized in {"o", "over", "step over"}:
        return "step_over"
    if normalized in {"u", "out", "step out"}:
        return "step_out"
    if normalized in {"c", "continue"}:
        return "continue"
    if normalized in {"g", "go"}:
        return "go"
    if normalized in {"r", "restart"}:
        return "restart"
    if normalized in {"q", "quit"}:
        return "quit"
    if normalized in {"h", "help"}:
        return "help"
    if normalized in {"stack", "s"}:
        return "stack"
    if normalized in {"vars", "v"}:
        return "vars"
    if normalized in {"locals", "l"}:
        return "locals"
    if normalized == "frame top":
        return "frame top"
    if normalized.startswith("frame "):
        target = normalized[6:].strip()
        if target == "top":
            return "frame top"
        if not target:
            raise ValueError("Frame command expects a frame number.")
        try:
            frame_number = int(target)
        except ValueError as exc:
            raise ValueError("Frame command expects a frame number.") from exc
        if frame_number < 1:
            raise ValueError("Frame command number must be >= 1.")
        return f"frame {frame_number}"
    if normalized.startswith("p"):
        start_line, end_line = _parse_print_command(
            normalized,
            snapshot.current_line,
            len(document.text.splitlines()),
        )
        _print_script_slice(
            document,
            current_line=snapshot.current_line,
            breakpoints=set(snapshot.breakpoints),
            start_line=start_line,
            end_line=end_line,
            label=f"Script lines {start_line}-{end_line}:",
        )
        return None
    raise ValueError("Unknown debugger command.")


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.source_kind != "script":
        print("Only the script debugger slice is implemented.", file=sys.stderr)
        return 1

    try:
        document = _load_script_document(args.source_path)
        breakpoint_lines = _validate_breakpoints(document, [int(line) for line in args.breakpoint])
    except ValueError as exc:
        print(f"Invalid breakpoint request: {exc}", file=sys.stderr)
        return 1

    print_input_output(
        input_label="Input source",
        input_value=f"script file {resolve_display_path(args.source_path)}",
        output_label="Output destination",
        output_value="stdout",
    )

    try:
        service = DebuggingService(
            playback_settings=DesktopPlaybackSettings(
                send_key_taps_instead_of_text=bool(args.ass_play),
            )
        )
        request = DebugRequest(
            document_id=document.document_id,
            stop_mode="step" if args.step else "continue",
            breakpoints=breakpoint_lines,
        )

        handle_box: dict[str, object] = {}

        def emit_event(event: DebugEvent) -> None:
            handle = handle_box.get("handle")
            snapshot_getter = (
                (lambda: handle.controller.snapshot()) if handle is not None else (lambda: None)
            )
            _emit_event(event, snapshot_getter)

        while True:
            stop_event = threading.Event()
            handle = service.start_debug_session(
                document,
                request,
                emit_event=emit_event,
                stop_event=stop_event,
            )
            handle_box["handle"] = handle
            runtime_result: dict[str, object] = {}
            runtime_error: dict[str, BaseException] = {}
            restart_requested = False
            quit_requested = False

            def run_runtime() -> None:
                try:
                    runtime_result["context"] = handle.runtime.compile(
                        document.text,
                        source_path=document.source_path,
                    )
                except Exception as exc:  # pragma: no cover - surfaced through runtime_error
                    runtime_error["exc"] = exc

            worker = threading.Thread(target=run_runtime, daemon=True)
            worker.start()

            while worker.is_alive():
                if not handle.controller.wait_for_pause(timeout=0.1):
                    continue

                snapshot = handle.controller.snapshot()
                if snapshot.state != "paused":
                    continue

                if sys.stdin.isatty():
                    for line in _format_pause_summary(snapshot):
                        print(line, flush=True)
                    while True:
                        command = input(
                            "Debugger paused. [Enter]=step into, o=step over, u=step out, c=continue, g=go, q=quit, h=help (type h for more): "
                        )
                        try:
                            action = _handle_pause_command(
                                command,
                                document=document,
                                snapshot=snapshot,
                            )
                        except ValueError as exc:
                            print(f"{exc}", flush=True)
                            continue

                        if action is None:
                            continue
                        if action == "help":
                            _print_pause_help()
                            continue
                        if action == "stack":
                            for line in _format_stack_details(snapshot):
                                print(line, flush=True)
                            continue
                        if action == "vars":
                            for line in _format_variable_details(snapshot):
                                print(line, flush=True)
                            continue
                        if action == "locals":
                            for line in _format_local_details(snapshot):
                                print(line, flush=True)
                            continue
                        if action == "frame top":
                            for line in _format_local_details(snapshot):
                                print(line, flush=True)
                            continue
                        if isinstance(action, str) and action.startswith("frame "):
                            frame_number = int(action[6:].strip())
                            for line in _format_frame_details(snapshot, frame_number):
                                print(line, flush=True)
                            continue
                        if action == "restart":
                            print("Restarting debugger...", flush=True)
                            restart_requested = True
                            stop_event.set()
                            handle.controller.resume_continue()
                            break
                        if action == "quit":
                            quit_requested = True
                            stop_event.set()
                            handle.controller.resume_continue()
                            break
                        if action == "go":
                            handle.controller.resume_go()
                            break
                        if action == "step_out":
                            handle.controller.resume_step_out()
                            break
                        if action == "continue":
                            handle.controller.resume_continue()
                            break
                        if action == "step_over":
                            handle.controller.resume_step_over()
                            break
                        handle.controller.resume_step()
                        break
                    if restart_requested:
                        break
                    if quit_requested:
                        break
                else:
                    if request.stop_mode == "step":
                        handle.controller.resume_step()
                    else:
                        handle.controller.resume_continue()

            worker.join()

            if restart_requested:
                if "exc" in runtime_error and not isinstance(
                    runtime_error["exc"],
                    ScriptRuntimeCancelled,
                ):
                    raise runtime_error["exc"]
                continue

            if quit_requested:
                if "exc" in runtime_error and not isinstance(
                    runtime_error["exc"],
                    ScriptRuntimeCancelled,
                ):
                    raise runtime_error["exc"]
                print("Debugger terminated by user.", flush=True)
                return 1

            if "exc" in runtime_error:
                raise runtime_error["exc"]

            if "context" in runtime_result:
                handle.controller.sync_from_context(runtime_result["context"])
            if handle.session.state not in {"completed", "failed"}:
                handle.controller.complete()
            break
    except Exception as exc:
        print(f"Debug session failed: {exc}", file=sys.stderr)
        return 1

    handle = handle_box.get("handle")
    if handle is None:
        return 1
    snapshot = handle.controller.snapshot()
    print(flush=True)
    print(f"Session ID   : {snapshot.session_id}", flush=True)
    print(f"Document ID  : {snapshot.document_id}", flush=True)
    print(f"State        : {snapshot.state}", flush=True)
    print(f"Current line : {snapshot.current_line}", flush=True)
    print(f"Breakpoints  : {snapshot.breakpoints}", flush=True)
    print(f"Last error   : {snapshot.last_exception}", flush=True)
    print("Call stack   :", flush=True)
    for line in _format_call_stack(snapshot):
        print(f"  {line}", flush=True)
    print("Variables    :", flush=True)
    for line in _format_variables(snapshot):
        print(f"  {line}", flush=True)
    return 0 if snapshot.state == "completed" else 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(run())
