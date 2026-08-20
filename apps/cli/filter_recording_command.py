from __future__ import annotations

import sys
from pathlib import Path

from application.recording_filter_service import RecordingFilterService
from apps.cli.filter_artifact_io import (
    load_recording_session,
    resolve_recording_session_path,
    save_recording_session,
)
from apps.cli.io_announcements import print_input_output
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.filter_command_support import (
    build_filter_parser,
    require_profile,
    require_source_path,
)


def build_parser() -> object:
    return build_filter_parser(
        prog="ass-filter-recording",
        description="Apply a phase-1 recording filter profile to a raw session JSON file.",
        source_help="Path to a recording session JSON file.",
        default_source_path=DEFAULT_RAW_SESSION_PATH,
    )


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = RecordingFilterService()

    try:
        if args.list_profiles:
            print("Available recording filter profiles:", flush=True)
            for profile_id in service.list_profile_ids():
                print(f"  {profile_id}", flush=True)
            return 0

        profile_id = require_profile(args, parser)
        source_path = require_source_path(args, parser)
        print_input_output(
            input_label="Input source",
            input_value=str(resolve_recording_session_path(source_path)),
            output_label="Output destination",
            output_value=str(Path(args.output).resolve()) if args.output else "stdout",
        )
        session = load_recording_session(source_path)
        result = service.apply_filter(session, profile_id)
        summary = service.summarize(
            result,
            profile_id=profile_id,
            source_session_id=session.session_id,
            source_event_count=len(session.events),
        )
    except Exception as exc:
        print(f"Recording filtering failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        save_recording_session(result.value, args.output)

    print(f"Profile                : {summary.profile_id}", flush=True)
    print(f"Session ID             : {summary.source_session_id}", flush=True)
    print(f"Source event count     : {summary.source_event_count}", flush=True)
    print(f"Filtered event count   : {summary.filtered_event_count}", flush=True)
    print("Applied filters        :", flush=True)
    for filter_id in summary.applied_filters:
        print(f"  {filter_id}", flush=True)
    for note in result.notes:
        print(f"Note                   : {note}", flush=True)
    if args.output:
        print(f"Output path            : {Path(args.output)}", flush=True)

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
