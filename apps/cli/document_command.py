from __future__ import annotations

import argparse
import sys
from pathlib import Path

from application.interpretation_service import InterpretationService
from application.persistence.unsaved_changes_service import UnsavedChangesService
from application.persistence.save_coordinator import SaveCoordinator
from application.script_document_service import ScriptDocumentService
from application.script_document_language_service import ScriptDocumentLanguageService
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
from editor.document.script_document import ScriptDocument
from editor.language_services.diagnostics_service import DiagnosticsService
from editor.language_services.formatting_service import FormattingService
from editor.language_services.parse_service import ParseService
from infrastructure.persistence.script_document_file_store import ScriptDocumentFileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-open-script",
        description=(
            "Load a raw session JSON file, convert it into a ScriptDocument, and "
            "run document language services."
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
    parser.add_argument(
        "--show-formatted",
        action="store_true",
        help="Print the formatted document preview after the authoritative text.",
    )
    parser.add_argument(
        "--show-diagnostics",
        action="store_true",
        help="Print parser and diagnostics output for the converted document.",
    )
    parser.add_argument(
        "--recording-conversion-mode",
        choices=["promote_generated", "direct_import"],
        default="promote_generated",
        help=(
            "Choose how the RecordingSession becomes a ScriptDocument. "
            "Default: promote_generated."
        ),
    )
    parser = add_force_argument(
        parser,
        "Allow overwriting an existing output document without save resolution.",
    )
    parser = add_interpretation_arguments(parser)
    parser = add_shaping_arguments(parser)
    return add_generation_arguments(parser)


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        print_input_output(
            input_label="Input source",
            input_value=str(resolve_recording_session_path(args.session_path)),
            output_label="Output destination",
            output_value=str(Path(args.output).resolve()) if args.output else "stdout",
        )
        session = load_session(args.session_path)
        document_service = ScriptDocumentService()
        parse_service = ParseService()
        diagnostics_service = DiagnosticsService(parse_service=parse_service)
        language_service = ScriptDocumentLanguageService(
            parse_service=parse_service,
            diagnostics_service=diagnostics_service,
        )
        formatting_service = FormattingService()
        save_coordinator = SaveCoordinator()
        script_document_store = ScriptDocumentFileStore()
        unsaved_changes_service = UnsavedChangesService()

        if args.recording_conversion_mode == "direct_import":
            document = document_service.import_recording_session(
                session,
                recording_conversion_route="direct_import",
            )
            source_action_count = len(session.events)
            source_count_label = "Recording event count"
        else:
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
            document = document_service.promote_generated_script(
                generated,
                recording_conversion_route="promote_generated",
            )
            source_action_count = generated.source_action_count
            source_count_label = "Shaped action count"

        if args.output:
            output_path = Path(args.output)
            if output_path.exists():
                existing_document = script_document_store.load(output_path)
                if existing_document.text != document.text:
                    save_candidate = ScriptDocument(
                        document_id=document.document_id,
                        text=document.text,
                        version=document.version,
                        is_dirty=True,
                        last_saved_version=document.last_saved_version,
                        source_session_id=document.source_session_id,
                        source_action_count=document.source_action_count,
                        generated_from_recording=document.generated_from_recording,
                        recording_conversion_route=document.recording_conversion_route,
                        source_capture_excluded_main_window=(
                            document.source_capture_excluded_main_window
                        ),
                    )
                    requirement = unsaved_changes_service.requires_resolution(
                        save_candidate,
                        action=PendingAction.OPEN_OTHER_DOCUMENT,
                    )
                    if refuse_unless_forced(
                        target=output_path,
                        requirement=requirement,
                        force=args.force,
                        target_description="Output document",
                    ):
                        return 1

            save_coordinator.save_script_document(
                document,
                path=output_path,
                store=script_document_store,
            )
        summary = document_service.summarize(document)
        analysis = language_service.analyze(document)
        formatted = formatting_service.format_document(document)
    except Exception as exc:
        print(f"Document conversion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Session ID             : {summary.source_session_id}", flush=True)
    print(f"{source_count_label:<23}: {source_action_count}", flush=True)
    print(f"Document ID            : {summary.document_id}", flush=True)
    print(f"Document version       : {summary.version}", flush=True)
    print(f"Document line count    : {summary.line_count}", flush=True)
    print(f"Document dirty         : {summary.is_dirty}", flush=True)
    print(f"Parse success          : {analysis.parse_succeeded}", flush=True)
    print(f"Parsed statement count : {len(analysis.root.statements)}", flush=True)
    print(f"Diagnostics count      : {len(analysis.diagnostics)}", flush=True)
    if args.output:
        print(f"Output path            : {Path(args.output)}", flush=True)

    print(flush=True)
    print("Authoritative document text:", flush=True)
    if document.text:
        print(document.text, end="", flush=True)
    else:
        print("# <empty script document>", flush=True)

    if args.show_diagnostics:
        print(flush=True)
        print("Diagnostics:", flush=True)
        if analysis.diagnostics.items:
            for diagnostic in analysis.diagnostics.items:
                print(diagnostic.format(document.text), flush=True)
                print(flush=True)
        else:
            print("<none>", flush=True)

    if args.show_formatted:
        print(flush=True)
        print("Formatted preview:", flush=True)
        if formatted:
            print(formatted, end="", flush=True)
        else:
            print("# <empty formatted script>", flush=True)

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
