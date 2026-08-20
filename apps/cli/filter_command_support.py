from __future__ import annotations

import argparse


def build_filter_parser(
    *,
    prog: str,
    description: str,
    source_help: str,
    default_source_path: str | None = None,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "source_path",
        nargs="?",
        default=default_source_path,
        help=(
            source_help
            + (f" Default: {default_source_path}." if default_source_path else "")
        ),
    )
    parser.add_argument(
        "--profile",
        help="Filter profile name to apply at this stage.",
    )
    parser.add_argument(
        "--output",
        help="Optional path for the derived output artifact.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles for this stage and exit.",
    )
    return parser


def require_profile(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.list_profiles:
        return ""
    if not args.profile:
        parser.error("--profile is required unless --list-profiles is set.")
    return str(args.profile)


def require_source_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> str:
    if args.list_profiles:
        return ""
    if not args.source_path:
        parser.error("source_path is required unless --list-profiles is set.")
    return str(args.source_path)
