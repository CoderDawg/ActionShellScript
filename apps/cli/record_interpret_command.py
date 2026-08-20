from __future__ import annotations

import argparse
import sys
import threading
import uuid
from pathlib import Path

from application.interpretation_service import InterpretationService
from application.persistence.unsaved_changes_service import UnsavedChangesService
from apps.cli.interpretation_args import (
    add_interpretation_arguments,
    build_interpretation_config,
)
from application.recording_service import RecordingService
from apps.cli.interpretation_output import format_interpreted_event
from apps.cli.io_announcements import print_input_output
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.record_command import add_recording_arguments, build_config
from apps.cli.save_resolution import refuse_unless_forced
from core.persistence.persistence_models import PendingAction
from apps.cli.session_json import save_raw_session
from core.recording.input_capture import InputCapture
from core.recording.session_recorder import SessionRecorder
from infrastructure.input.pynput_backend import PynputCaptureBackend


def _effective_save_raw_path(args: argparse.Namespace) -> str | None:
    if getattr(args, "no_save", False):
        return None
    return args.save_raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-record-interpret",
        description="Record live input and immediately interpret it as phase-2 events.",
    )
    add_recording_arguments(
        parser,
        default_save_raw=DEFAULT_RAW_SESSION_PATH,
        include_no_save=True,
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print interpreted events in a readable one-line summary format.",
    )
    return add_interpretation_arguments(parser)


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
        recording_service = RecordingService(recorder)
        interpretation_service = InterpretationService(
            config=build_interpretation_config(args)
        )

        session_id = args.session_id or str(uuid.uuid4())
        save_raw_path = _effective_save_raw_path(args)

        print_input_output(
            input_label="Input source",
            input_value="live input capture",
            output_label="Output destination",
            output_value=save_raw_path or "<not saved>",
        )
        if save_raw_path:
            print(
                f"Recording output will be saved to {save_raw_path} and interpreted afterward.",
                flush=True,
            )
        recording_service.start_recording(session_id=session_id)
        print(
            f"Recording started. Press {args.stop_hotkey} or Ctrl+C to stop and interpret.",
            flush=True,
        )

        while recording_service.is_recording():
            if stop_requested.wait(0.05):
                break

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Record+interpret failed to start: {exc}", file=sys.stderr)
        return 1

    try:
        if stop_requested.is_set():
            print(f"Stop hotkey detected: {args.stop_hotkey}", flush=True)
        session = recording_service.stop_recording()
        save_raw_path = _effective_save_raw_path(args)
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
        recording_summary = recording_service.summarize(session)
        interpreted = interpretation_service.interpret_recording(session)
        interpretation_summary = interpretation_service.summarize(interpreted)
    except Exception as exc:
        print(f"Record+interpret failed to stop cleanly: {exc}", file=sys.stderr)
        return 1

    print(flush=True)
    print("Recording stopped.", flush=True)
    print(f"Session ID                : {recording_summary.session_id}", flush=True)
    print(f"Recording state           : {recording_summary.state}", flush=True)
    print(f"Recorded raw event count  : {recording_summary.event_count}", flush=True)
    print(f"Started at                : {recording_summary.started_at_ms}", flush=True)
    print(f"Stopped at                : {recording_summary.stopped_at_ms}", flush=True)
    print(f"Recording duration (ms)   : {recording_summary.duration_ms}", flush=True)
    if save_raw_path:
        print(f"Saved raw session   : {save_raw_path}", flush=True)
    print(f"Interpreted event count   : {interpretation_summary.interpreted_event_count}", flush=True)
    print("Interpreted event types   :", flush=True)
    for event_type_name, count in interpretation_summary.interpreted_event_types.items():
        print(f"  {event_type_name}: {count}", flush=True)

    if args.show_events:
        print(flush=True)
        print("Interpreted events:", flush=True)
        for index, event in enumerate(interpreted.events, start=1):
            print(format_interpreted_event(event, index=index), flush=True)

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
