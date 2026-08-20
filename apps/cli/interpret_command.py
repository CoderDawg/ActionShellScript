from __future__ import annotations

import argparse
import sys

from application.interpretation_service import InterpretationService
from apps.cli.filter_artifact_io import load_recording_session
from apps.cli.filter_artifact_io import resolve_recording_session_path
from apps.cli.io_announcements import print_input_output
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.interpretation_args import (
    add_interpretation_arguments,
    build_interpretation_config,
)
from apps.cli.interpretation_output import format_interpreted_event
from core.recording.recording_session import RecordingSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-interpret",
        description="Interpret a recorded session JSON file into phase-2 meaning events.",
    )
    parser.add_argument(
        "session_path",
        nargs="?",
        default=DEFAULT_RAW_SESSION_PATH,
        help=(
            "Path to a JSON object with session_id, timestamps, and raw events. "
            f"Default: {DEFAULT_RAW_SESSION_PATH}."
        ),
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print interpreted events in a readable one-line summary format.",
    )
    return add_interpretation_arguments(parser)


def load_session(path: str) -> RecordingSession:
    return load_recording_session(path)


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        print_input_output(
            input_label="Input source",
            input_value=str(resolve_recording_session_path(args.session_path)),
            output_label="Output destination",
            output_value="stdout",
        )
        session = load_session(args.session_path)
        service = InterpretationService(config=build_interpretation_config(args))
        interpreted = service.interpret_recording(session)
        summary = service.summarize(interpreted)
    except Exception as exc:
        print(f"Interpretation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Session ID             : {summary.source_session_id}", flush=True)
    print(f"Source event count     : {summary.source_event_count}", flush=True)
    print(f"Interpreted event count: {summary.interpreted_event_count}", flush=True)
    print("Interpreted event types:", flush=True)
    for event_type_name, count in summary.interpreted_event_types.items():
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
