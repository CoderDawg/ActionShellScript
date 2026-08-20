from __future__ import annotations

import argparse

from core.scripting.generation.script_generation_config import ScriptGenerationConfig


DEFAULT_SCRIPT_GENERATION_CONFIG = ScriptGenerationConfig()


def add_generation_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--output",
        help="Write the generated script text to this path.",
    )
    parser.add_argument(
        "--no-header-comments",
        action="store_true",
        help="Omit the generated-script header comments.",
    )
    parser.add_argument(
        "--no-source-summary",
        action="store_true",
        help="Omit source session metadata from the generated header.",
    )
    parser.add_argument(
        "--no-script-delays",
        action="store_true",
        help="Drop standalone delay actions from generated script output.",
    )
    parser.add_argument(
        "--emit-unsupported-comments",
        action="store_true",
        help="Emit comment lines when generation encounters unsupported actions.",
    )
    parser.add_argument(
        "--line-ending",
        choices=["lf", "crlf"],
        default="lf" if DEFAULT_SCRIPT_GENERATION_CONFIG.line_ending == "\n" else "crlf",
        help="Choose the generated script line ending style.",
    )
    return parser


def build_generation_config(args: argparse.Namespace) -> ScriptGenerationConfig:
    line_ending = "\r\n" if args.line_ending == "crlf" else "\n"
    return ScriptGenerationConfig(
        include_header_comments=not args.no_header_comments,
        include_source_summary=not args.no_source_summary,
        line_ending=line_ending,
        emit_delays=not args.no_script_delays,
        emit_metadata_comments=args.emit_unsupported_comments,
    )
