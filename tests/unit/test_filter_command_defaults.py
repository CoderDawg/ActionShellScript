from __future__ import annotations

from apps.cli.filter_interpretation_command import build_parser as build_interpretation_parser
from apps.cli.filter_recording_command import build_parser as build_recording_parser
from apps.cli.filter_shaping_command import build_parser as build_shaping_parser


def test_filter_recording_parser_defaults_to_session_json() -> None:
    args = build_recording_parser().parse_args([])

    assert args.source_path == r".\session.json"


def test_filter_interpretation_parser_defaults_to_session_json() -> None:
    args = build_interpretation_parser().parse_args([])

    assert args.source_path == r".\session.json"


def test_filter_shaping_parser_defaults_to_session_json() -> None:
    args = build_shaping_parser().parse_args([])

    assert args.source_path == r".\session.json"
