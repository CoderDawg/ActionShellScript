from __future__ import annotations

import sys
from pathlib import Path

from application.document_filter_service import DocumentFilterService
from apps.cli.filter_artifact_io import load_script_document, save_script_document
from apps.cli.filter_command_support import (
    build_filter_parser,
    require_profile,
    require_source_path,
)
from apps.cli.io_announcements import print_input_output


def build_parser() -> object:
    return build_filter_parser(
        prog="ass-filter-document",
        description="Apply a phase-5 document filter profile to a script document.",
        source_help="Path to a script document (.ass) file.",
    )


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = DocumentFilterService()

    try:
        if args.list_profiles:
            print("Available document filter profiles:", flush=True)
            for profile_id in service.list_profile_ids():
                print(f"  {profile_id}", flush=True)
            return 0

        profile_id = require_profile(args, parser)
        source_path = require_source_path(args, parser)
        print_input_output(
            input_label="Input source",
            input_value=str(Path(source_path).resolve()),
            output_label="Output destination",
            output_value=str(Path(args.output).resolve()) if args.output else "stdout",
        )
        document = load_script_document(source_path)
        result = service.apply_filter(document, profile_id)
        summary = service.summarize(result, profile_id=profile_id)
    except Exception as exc:
        print(f"Document filtering failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        save_script_document(result.value, args.output)

    print(f"Profile                : {summary.profile_id}", flush=True)
    print(f"Document ID            : {summary.document_id}", flush=True)
    print(f"Filtered line count    : {summary.line_count}", flush=True)
    print("Applied filters        :", flush=True)
    for filter_id in summary.applied_filters:
        print(f"  {filter_id}", flush=True)
    for note in result.notes:
        print(f"Note                   : {note}", flush=True)
    print(flush=True)
    print("Filtered document text:", flush=True)
    if result.value.text:
        print(result.value.text, end="", flush=True)
    else:
        print("# <empty script document>", flush=True)
    if args.output:
        print(f"Output path            : {Path(args.output)}", flush=True)

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
