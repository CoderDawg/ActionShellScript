from __future__ import annotations

import argparse
import sys
from pathlib import Path

from application.interpretation_service import InterpretationService
from application.persistence.unsaved_changes_service import UnsavedChangesService
from application.script_generation_service import ScriptGenerationService
from application.shaping_service import ShapingService
from apps.cli.generation_args import add_generation_arguments, build_generation_config
from apps.cli.filter_artifact_io import resolve_recording_session_path
from apps.cli.interpret_command import load_session
from apps.cli.io_announcements import print_input_output
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.interpretation_args import (
    add_interpretation_arguments,
    build_interpretation_config,
)
from apps.cli.save_resolution import add_force_argument, refuse_unless_forced
from apps.cli.shaping_args import add_shaping_arguments, build_shaping_config
from core.persistence.persistence_models import PendingAction


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-generate",
        description=(
            "Load a raw session JSON file, interpret it, shape it, and generate "
            "phase-4 script text."
        ),
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
    parser = add_force_argument(
        parser,
        "Allow overwriting an existing output script without save resolution.",
    )
    parser = add_interpretation_arguments(parser)
    parser = add_shaping_arguments(parser)
    return add_generation_arguments(parser)


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    unsaved_changes_service = UnsavedChangesService()

    try:
        print_input_output(
            input_label="Input source",
            input_value=str(resolve_recording_session_path(args.session_path)),
            output_label="Output destination",
            output_value=str(Path(args.output).resolve()) if args.output else "stdout",
        )
        session = load_session(args.session_path)
        interpretation_service = InterpretationService(
            config=build_interpretation_config(args)
        )
        shaping_service = ShapingService(config=build_shaping_config(args))
        generation_service = ScriptGenerationService(
            config=build_generation_config(args)
        )

        interpreted = interpretation_service.interpret_recording(session)
        shaped = shaping_service.shape_recording(interpreted)
        generated = generation_service.generate_script(shaped)
        summary = generation_service.summarize(generated)
    except Exception as exc:
        print(f"Script generation failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output)
        requirement = unsaved_changes_service.requires_resolution_for_existing_target(
            target=output_path,
            action=PendingAction.REPLACE_EXISTING_OUTPUT,
            target_description="Output script",
        )
        if refuse_unless_forced(
            target=output_path,
            requirement=requirement,
            force=args.force,
            target_description="Output script",
        ):
            return 1
        _write_script(Path(args.output), generated.text)

    print(f"Session ID             : {summary.source_session_id}", flush=True)
    print(
        f"Interpreted event count: {shaped.source_interpreted_event_count}",
        flush=True,
    )
    print(f"Shaped action count    : {summary.source_action_count}", flush=True)
    print(f"Generated line count   : {summary.line_count}", flush=True)
    if args.output:
        print(f"Output path            : {Path(args.output)}", flush=True)

    print(flush=True)
    print("Generated script:", flush=True)
    if generated.text:
        print(generated.text, end="", flush=True)
    else:
        print("# <empty generated script>", flush=True)

    return 0


def _write_script(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
