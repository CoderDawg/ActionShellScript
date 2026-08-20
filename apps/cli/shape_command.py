from __future__ import annotations

import argparse
import sys

from application.interpretation_service import InterpretationService
from application.shaping_service import ShapingService
from apps.cli.interpret_command import load_session
from apps.cli.filter_artifact_io import resolve_recording_session_path
from apps.cli.io_announcements import print_input_output
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.interpretation_args import (
    add_interpretation_arguments,
    build_interpretation_config,
)
from apps.cli.shaping_args import add_shaping_arguments, build_shaping_config
from apps.cli.shaping_output import format_shaped_action


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-shape",
        description="Interpret a recorded session JSON file and shape it into phase-3 actions.",
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
        "--show-actions",
        action="store_true",
        help="Print shaped actions in a readable one-line summary format.",
    )
    parser = add_interpretation_arguments(parser)
    return add_shaping_arguments(parser)


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
        interpretation_service = InterpretationService(
            config=build_interpretation_config(args)
        )
        shaping_service = ShapingService(config=build_shaping_config(args))
        interpreted = interpretation_service.interpret_recording(session)
        shaped = shaping_service.shape_recording(interpreted)
        summary = shaping_service.summarize(shaped)
    except Exception as exc:
        print(f"Shaping failed: {exc}", file=sys.stderr)
        return 1

    print(f"Session ID               : {summary.source_session_id}", flush=True)
    print(
        f"Interpreted event count  : {summary.source_interpreted_event_count}",
        flush=True,
    )
    print(f"Shaped action count      : {summary.shaped_action_count}", flush=True)
    print("Shaped action types      :", flush=True)
    action_types: dict[str, int] = {}
    for action in shaped.actions:
        action_type = str(action.get("type", "")).strip().lower()
        action_types[action_type] = action_types.get(action_type, 0) + 1
    for action_type, count in action_types.items():
        print(f"  {action_type}: {count}", flush=True)

    if args.show_actions:
        print(flush=True)
        print("Shaped actions:", flush=True)
        for index, action in enumerate(shaped.actions, start=1):
            print(format_shaped_action(action, index=index), flush=True)

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
