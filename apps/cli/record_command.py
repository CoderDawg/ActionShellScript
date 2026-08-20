"""Phase 1 recording CLI command."""
from __future__ import annotations

import argparse
import threading
import uuid
import sys
from pathlib import Path

from application.recording_service import RecordingService
from application.persistence.unsaved_changes_service import UnsavedChangesService
from apps.cli.session_json import save_raw_session
from apps.cli.io_announcements import print_input_output
from apps.cli.save_resolution import add_force_argument, refuse_unless_forced
from core.persistence.persistence_models import PendingAction
from core.recording.input_capture import InputCapture
from core.recording.recorder_config import RecorderConfig
from core.recording.session_recorder import SessionRecorder
from infrastructure.input.pynput_backend import PynputCaptureBackend

DEFAULT_RAW_SESSION_PATH = r".\session.json"


def add_recording_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_save_raw: str | None = None,
    include_no_save: bool = False,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional explicit session id.",
    )
    parser.add_argument(
        "--suppress",
        action="store_true",
        help="Ask pynput to suppress input events while recording.",
    )
    parser.add_argument(
        "--no-mouse-moves",
        action="store_true",
        help="Do not store mouse move events.",
    )
    parser.add_argument(
        "--no-mouse-buttons",
        action="store_true",
        help="Do not store mouse button up/down events.",
    )
    parser.add_argument(
        "--no-mouse-wheel",
        action="store_true",
        help="Do not store mouse wheel events.",
    )
    parser.add_argument(
        "--no-keyboard",
        action="store_true",
        help="Do not store keyboard events.",
    )
    parser.add_argument(
        "--mouse-move-threshold",
        type=int,
        default=0,
        help="Minimum pixel delta before storing a mouse move.",
    )
    parser.add_argument(
        "--stop-hotkey",
        default="Shift+Esc",
        help=(
            "Chord that stops recording without Ctrl+C. Use | to add alternate "
            "chords, such as Shift+Esc|Ctrl+C. Default: Shift+Esc."
        ),
    )
    parser.add_argument(
        "--debug-stop-hotkey",
        action="store_true",
        help="Print normalized stop-hotkey press/release debug info to stderr.",
    )
    save_group = (
        parser.add_mutually_exclusive_group()
        if include_no_save
        else parser
    )
    save_group.add_argument(
        "--save-raw",
        default=default_save_raw,
        help=(
            "Optional path to save the captured raw RecordingSession as JSON."
            + (
                f" Default: {default_save_raw}."
                if default_save_raw is not None
                else ""
            )
        ),
    )
    if include_no_save:
        save_group.add_argument(
            "--no-save",
            action="store_true",
            help="Do not write the captured raw RecordingSession to disk.",
        )
    parser = add_force_argument(
        parser,
        "Allow overwriting an existing raw session file without save resolution.",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="record",
        description="Record mouse and keyboard input until interrupted.",
    )
    return add_recording_arguments(
        parser,
        default_save_raw=DEFAULT_RAW_SESSION_PATH,
        include_no_save=True,
    )


def build_config(args: argparse.Namespace) -> RecorderConfig:
    return RecorderConfig(
        capture_mouse_moves=not args.no_mouse_moves,
        capture_mouse_buttons=not args.no_mouse_buttons,
        capture_mouse_wheel=not args.no_mouse_wheel,
        capture_keyboard=not args.no_keyboard,
        mouse_move_threshold_px=args.mouse_move_threshold,
    )


def _recording_output_message(save_raw_path: str | None) -> str | None:
    if save_raw_path is None:
        return None
    return f"Recording output will be saved to {save_raw_path}."


def _effective_save_raw_path(args: argparse.Namespace) -> str | None:
    if getattr(args, "no_save", False):
        return None
    return args.save_raw


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    stop_requested = threading.Event()
    unsaved_changes_service = UnsavedChangesService()

    try:
        config = build_config(args)
        backend = PynputCaptureBackend(
            config=config,
            suppress=args.suppress,
            stop_hotkey=args.stop_hotkey,
            on_stop_requested=stop_requested.set,
            debug_stop_hotkey=args.debug_stop_hotkey,
        )
        capture = InputCapture(backend=backend)
        recorder = SessionRecorder(
            config=config,
            capture=capture,
        )
        service = RecordingService(recorder)

        session_id = args.session_id or str(uuid.uuid4())
        save_raw_path = _effective_save_raw_path(args)
        print_input_output(
            input_label="Input source",
            input_value="live input capture",
            output_label="Output destination",
            output_value=save_raw_path or "<not saved>",
        )

        output_message = _recording_output_message(save_raw_path)
        if output_message is not None:
            print(output_message, flush=True)
        service.start_recording(session_id=session_id)
        print(f"Recording started. Press {args.stop_hotkey} or Ctrl+C to stop.", flush=True)

        while service.is_recording():
            if stop_requested.wait(0.05):
                break

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Recording failed to start: {exc}", file=sys.stderr)
        return 1

    try:
        if stop_requested.is_set():
            print(f"Stop hotkey detected: {args.stop_hotkey}", flush=True)
        session = service.stop_recording()
        if save_raw_path:
            output_path = Path(save_raw_path)
            requirement = unsaved_changes_service.requires_resolution_for_existing_target(
                target=output_path,
                action=PendingAction.REPLACE_EXISTING_OUTPUT,
                target_description="Raw session file",
            )
            if refuse_unless_forced(
                target=output_path,
                requirement=requirement,
                force=args.force,
                target_description="Raw session file",
            ):
                return 1
            save_raw_session(session, save_raw_path)
        summary = service.summarize(session)
    except Exception as exc:
        print(f"Recording failed to stop cleanly: {exc}", file=sys.stderr)
        return 1

    print(flush=True)
    print("Recording stopped.", flush=True)
    print(f"Session ID   : {summary.session_id}", flush=True)
    print(f"State        : {summary.state}", flush=True)
    print(f"Event count  : {summary.event_count}", flush=True)
    print(f"Started at   : {summary.started_at_ms}", flush=True)
    print(f"Stopped at   : {summary.stopped_at_ms}", flush=True)
    print(f"Duration (ms): {summary.duration_ms}", flush=True)
    if save_raw_path:
        print(f"Saved raw session   : {save_raw_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
