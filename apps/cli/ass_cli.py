from __future__ import annotations

import argparse

from apps.cli import main as legacy_dispatch
from apps.cli.generation_args import DEFAULT_SCRIPT_GENERATION_CONFIG
from apps.cli.generation_args import add_generation_arguments
from apps.cli.interpretation_args import DEFAULT_INTERPRETATION_CONFIG
from apps.cli.interpretation_args import (
    add_interpretation_arguments,
)
from apps.cli.play_command import _add_playback_arguments
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from apps.cli.record_command import add_recording_arguments
from apps.cli.save_resolution import add_force_argument
from apps.cli.shaping_args import DEFAULT_SHAPING_CONFIG
from apps.cli.shaping_args import add_shaping_arguments


def _build_recording_parser(
    parser: argparse.ArgumentParser,
    *,
    default_save_raw: str | None = None,
    include_no_save: bool = False,
) -> argparse.ArgumentParser:
    return add_recording_arguments(
        parser,
        default_save_raw=default_save_raw,
        include_no_save=include_no_save,
    )


def _build_interpretation_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        default=DEFAULT_RAW_SESSION_PATH,
        help=(
            "Path to the source session or artifact file. "
            f"Default: {DEFAULT_RAW_SESSION_PATH}."
        ),
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print interpreted events in a readable one-line summary format.",
    )
    return add_interpretation_arguments(parser)


def _build_shaping_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        default=DEFAULT_RAW_SESSION_PATH,
        help=(
            "Path to the source session or artifact file. "
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


def _build_generation_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        default=DEFAULT_RAW_SESSION_PATH,
        help=(
            "Path to the source session or artifact file. "
            f"Default: {DEFAULT_RAW_SESSION_PATH}."
        ),
    )
    parser = add_interpretation_arguments(parser)
    parser = add_shaping_arguments(parser)
    parser = add_generation_arguments(parser)
    return add_force_argument(
        parser,
        "Allow overwriting an existing output script without save resolution.",
    )


def _build_open_script_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    _build_generation_parser(parser)
    parser.add_argument(
        "--show-diagnostics",
        action="store_true",
        help="Print parser and diagnostics output for the promoted document.",
    )
    parser.add_argument(
        "--show-formatted",
        action="store_true",
        help="Print the formatted document preview after the authoritative text.",
    )
    return parser


def _build_playback_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    phase_6_parser = argparse.ArgumentParser(add_help=False)
    phase_6_parser = _add_playback_arguments(phase_6_parser)
    parser = subparsers.add_parser(
        "play",
        help="Build and execute derived playback from a selected source kind.",
        parents=[phase_6_parser],
    )

    source_parser = parser.add_subparsers(dest="source_kind", required=True)

    recording_parser = source_parser.add_parser(
        "recording",
        help="Build playback from a saved RecordingSession JSON file.",
        parents=[phase_6_parser],
    )
    recording_parser.add_argument(
        "input",
        nargs="?",
        default=DEFAULT_RAW_SESSION_PATH,
        help="Path to the raw recording session JSON file.",
    )

    script_parser = source_parser.add_parser(
        "script",
        help="Build playback from a script document file.",
        parents=[phase_6_parser],
    )
    script_parser.add_argument(
        "input",
        help="Path to the script document text file.",
    )

    return parser


def _build_debug_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the script document text file.",
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Stop at every debuggable statement boundary.",
    )
    parser.add_argument(
        "--breakpoint",
        action="append",
        type=int,
        default=[],
        help="Add a line breakpoint. Repeat for multiple breakpoints.",
    )
    parser.add_argument(
        "--ass-play",
        action="store_true",
        help=(
            "Emit SendKeys printable characters as key taps instead of text "
            "events."
        ),
    )
    return parser


def _build_filter_parser(
    parser: argparse.ArgumentParser,
    *,
    default_source_path: str | None = None,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        default=default_source_path,
        help=(
            "Path to the source file."
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-cli",
        description="Uniform front-end over the ActionShellScript command set.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    record_parser = subparsers.add_parser(
        "record",
        help="Record live input.",
    )
    _build_recording_parser(
        record_parser,
        default_save_raw=DEFAULT_RAW_SESSION_PATH,
        include_no_save=True,
    )
    record_parser.set_defaults(_runner=_run_record)

    interpret_parser = subparsers.add_parser(
        "interpret",
        help="Interpret a saved recording.",
    )
    _build_interpretation_parser(interpret_parser)
    interpret_parser.set_defaults(_runner=_run_interpret)

    record_interpret_parser = subparsers.add_parser(
        "record-interpret",
        help="Record live input and immediately interpret it.",
    )
    _build_recording_parser(
        record_interpret_parser,
        default_save_raw=DEFAULT_RAW_SESSION_PATH,
        include_no_save=True,
    )
    record_interpret_parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print interpreted events in a readable one-line summary format.",
    )
    add_interpretation_arguments(record_interpret_parser)
    record_interpret_parser.set_defaults(_runner=_run_record_interpret)

    shape_parser = subparsers.add_parser(
        "shape",
        help="Interpret and shape a saved recording.",
    )
    _build_shaping_parser(shape_parser)
    shape_parser.set_defaults(_runner=_run_shape)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate script text from a source artifact.",
    )
    _build_generation_parser(generate_parser)
    generate_parser.set_defaults(_runner=_run_generate)

    open_script_parser = subparsers.add_parser(
        "open-script",
        help="Promote generated script into a ScriptDocument.",
    )
    _build_open_script_parser(open_script_parser)
    open_script_parser.set_defaults(_runner=_run_open_script)

    play_parser = _build_playback_parser(subparsers)
    play_parser.set_defaults(_runner=_run_play)

    debug_parser = subparsers.add_parser(
        "debug",
        help="Run a script document under the debugger.",
    )
    _build_debug_parser(debug_parser)
    debug_parser.set_defaults(_runner=_run_debug)

    for name, help_text, runner, default_source_path in (
        (
            "filter-recording",
            "Apply a recording filter profile.",
            _run_filter_recording,
            DEFAULT_RAW_SESSION_PATH,
        ),
        (
            "filter-interpretation",
            "Apply an interpretation filter profile.",
            _run_filter_interpretation,
            DEFAULT_RAW_SESSION_PATH,
        ),
        (
            "filter-shaping",
            "Apply a shaping filter profile.",
            _run_filter_shaping,
            DEFAULT_RAW_SESSION_PATH,
        ),
        (
            "filter-document",
            "Apply a document filter profile.",
            _run_filter_document,
            None,
        ),
    ):
        parser_for_filter = subparsers.add_parser(name, help=help_text)
        _build_filter_parser(parser_for_filter, default_source_path=default_source_path)
        parser_for_filter.set_defaults(_runner=runner)

    return parser


def _load_runner(module_name: str, attribute_name: str):
    return legacy_dispatch._load_runner(module_name, attribute_name)


def _dispatch_backend(command: str, argv: list[str]) -> int:
    module_name, attribute_name = legacy_dispatch.COMMAND_TARGETS[command]
    runner = _load_runner(module_name, attribute_name)
    return runner(argv)


def _append_option(
    argv: list[str],
    flag: str,
    value: object | None,
    *,
    default: object | None,
) -> None:
    if value is None or value == default:
        return
    argv.extend([flag, str(value)])


def _append_flag(
    argv: list[str],
    flag: str,
    enabled: bool,
    *,
    default: bool = False,
) -> None:
    if enabled != default:
        argv.append(flag)


def _recording_argv(args: argparse.Namespace) -> list[str]:
    argv: list[str] = []
    _append_option(argv, "--session-id", args.session_id, default=None)
    _append_flag(argv, "--suppress", args.suppress)
    _append_flag(argv, "--no-mouse-moves", args.no_mouse_moves)
    _append_flag(argv, "--no-mouse-buttons", args.no_mouse_buttons)
    _append_flag(argv, "--no-mouse-wheel", args.no_mouse_wheel)
    _append_flag(argv, "--no-keyboard", args.no_keyboard)
    _append_option(argv, "--mouse-move-threshold", args.mouse_move_threshold, default=0)
    _append_option(argv, "--stop-hotkey", args.stop_hotkey, default="Shift+Esc")
    _append_flag(argv, "--debug-stop-hotkey", args.debug_stop_hotkey)
    if getattr(args, "no_save", False):
        argv.append("--no-save")
    else:
        _append_option(
            argv,
            "--save-raw",
            args.save_raw,
            default=DEFAULT_RAW_SESSION_PATH,
        )
    _append_flag(argv, "--force", args.force)
    return argv


def _interpretation_argv(
    args: argparse.Namespace,
    *,
    include_input: bool = True,
) -> list[str]:
    argv = [args.input] if include_input else []
    _append_option(
        argv,
        "--click-max-move-distance-px",
        args.click_max_move_distance_px,
        default=DEFAULT_INTERPRETATION_CONFIG.click_max_move_distance_px,
    )
    _append_option(
        argv,
        "--double-click-max-interval-ms",
        args.double_click_max_interval_ms,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_interval_ms,
    )
    _append_option(
        argv,
        "--double-click-max-distance-px",
        args.double_click_max_distance_px,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_distance_px,
    )
    _append_option(
        argv,
        "--double-click-max-pause-ms",
        args.double_click_max_pause_ms,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_pause_ms,
    )
    _append_option(
        argv,
        "--double-click-max-inter-click-move-distance-px",
        args.double_click_max_inter_click_move_distance_px,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_inter_click_move_distance_px,
    )
    _append_option(
        argv,
        "--drag-min-distance-px",
        args.drag_min_distance_px,
        default=DEFAULT_INTERPRETATION_CONFIG.drag_min_distance_px,
    )
    _append_option(
        argv,
        "--drag-min-duration-ms",
        args.drag_min_duration_ms,
        default=DEFAULT_INTERPRETATION_CONFIG.drag_min_duration_ms,
    )
    _append_flag(argv, "--show-events", getattr(args, "show_events", False))
    return argv


def _shaping_argv(args: argparse.Namespace) -> list[str]:
    argv = _interpretation_argv(args)
    _append_flag(argv, "--show-actions", getattr(args, "show_actions", False))
    _append_flag(argv, "--no-delays", args.no_delays)
    _append_option(
        argv,
        "--min-delay-ms",
        args.min_delay_ms,
        default=DEFAULT_SHAPING_CONFIG.min_delay_ms,
    )
    _append_option(
        argv,
        "--max-delay-ms",
        args.max_delay_ms,
        default=DEFAULT_SHAPING_CONFIG.max_delay_ms,
    )
    _append_flag(argv, "--no-collapse-delays", args.no_collapse_delays)
    _append_flag(argv, "--no-mouse-moves", args.no_mouse_moves)
    _append_flag(argv, "--only-click-positions", args.only_click_positions)
    _append_flag(argv, "--no-collapse-mouse-moves", args.no_collapse_mouse_moves)
    _append_flag(argv, "--no-collapse-clicks", args.no_collapse_clicks)
    _append_option(
        argv,
        "--click-collapse-distance-px",
        args.click_collapse_distance_px,
        default=DEFAULT_SHAPING_CONFIG.click_collapse_distance_px,
    )
    _append_option(
        argv,
        "--click-collapse-max-duration-ms",
        args.click_collapse_max_duration_ms,
        default=DEFAULT_SHAPING_CONFIG.click_collapse_max_duration_ms,
    )
    _append_flag(argv, "--no-collapse-text-input", args.no_collapse_text_input)
    _append_option(
        argv,
        "--keyboard-output-style",
        args.keyboard_output_style,
        default=DEFAULT_SHAPING_CONFIG.keyboard_output_style,
    )
    return argv


def _generation_argv(args: argparse.Namespace) -> list[str]:
    argv = _shaping_argv(args)
    _append_option(argv, "--output", args.output, default=None)
    _append_flag(
        argv,
        "--no-header-comments",
        args.no_header_comments,
        default=not DEFAULT_SCRIPT_GENERATION_CONFIG.include_header_comments,
    )
    _append_flag(
        argv,
        "--no-source-summary",
        args.no_source_summary,
        default=not DEFAULT_SCRIPT_GENERATION_CONFIG.include_source_summary,
    )
    _append_flag(
        argv,
        "--no-script-delays",
        args.no_script_delays,
        default=not DEFAULT_SCRIPT_GENERATION_CONFIG.emit_delays,
    )
    _append_flag(
        argv,
        "--emit-unsupported-comments",
        args.emit_unsupported_comments,
        default=DEFAULT_SCRIPT_GENERATION_CONFIG.emit_metadata_comments,
    )
    _append_option(
        argv,
        "--line-ending",
        args.line_ending,
        default="lf" if DEFAULT_SCRIPT_GENERATION_CONFIG.line_ending == "\n" else "crlf",
    )
    _append_flag(argv, "--force", args.force)
    return argv


def _open_script_argv(args: argparse.Namespace) -> list[str]:
    argv = _generation_argv(args)
    _append_flag(argv, "--show-diagnostics", args.show_diagnostics)
    _append_flag(argv, "--show-formatted", args.show_formatted)
    return argv


def _play_argv(args: argparse.Namespace) -> list[str]:
    argv = [args.source_kind, args.input]
    _append_option(argv, "--mode", args.mode, default="preview")
    _append_option(argv, "--repeat", args.repeat, default=1)
    _append_flag(argv, "--step", args.step)
    _append_option(argv, "--delay-ms", args.delay_ms, default=0)
    _append_option(argv, "--settle-ms", args.settle_ms, default=0)
    _append_flag(argv, "--show-events", args.show_events)
    _append_flag(argv, "--demo-live", args.demo_live)
    _append_flag(argv, "--ass-play", args.ass_play)
    return argv


def _debug_argv(args: argparse.Namespace) -> list[str]:
    argv = ["script", args.input]
    _append_flag(argv, "--step", args.step)
    for line in args.breakpoint:
        argv.extend(["--breakpoint", str(line)])
    _append_flag(argv, "--ass-play", args.ass_play)
    return argv


def _filter_argv(args: argparse.Namespace) -> list[str]:
    argv: list[str] = []
    if args.list_profiles:
        argv.append("--list-profiles")
        return argv

    if not args.input:
        raise ValueError("--input is required unless --list-profiles is set.")
    if not args.profile:
        raise ValueError("--profile is required unless --list-profiles is set.")

    argv.append(args.input)
    _append_option(argv, "--profile", args.profile, default=None)
    _append_option(argv, "--output", args.output, default=None)
    return argv


def _run_record(args: argparse.Namespace) -> int:
    return _dispatch_backend("record", _recording_argv(args))


def _run_interpret(args: argparse.Namespace) -> int:
    return _dispatch_backend("interpret", _interpretation_argv(args))


def _run_record_interpret(args: argparse.Namespace) -> int:
    backend_argv = _recording_argv(args)
    backend_argv.extend(_interpretation_argv(args, include_input=False))
    return _dispatch_backend("record-interpret", backend_argv)


def _run_shape(args: argparse.Namespace) -> int:
    return _dispatch_backend("shape", _shaping_argv(args))


def _run_generate(args: argparse.Namespace) -> int:
    return _dispatch_backend("generate", _generation_argv(args))


def _run_open_script(args: argparse.Namespace) -> int:
    return _dispatch_backend("open-script", _open_script_argv(args))


def _run_play(args: argparse.Namespace) -> int:
    return _dispatch_backend("play", _play_argv(args))


def _run_debug(args: argparse.Namespace) -> int:
    return _dispatch_backend("debug", _debug_argv(args))


def _run_filter_recording(args: argparse.Namespace) -> int:
    return _dispatch_backend("filter-recording", _filter_argv(args))


def _run_filter_interpretation(args: argparse.Namespace) -> int:
    return _dispatch_backend("filter-interpretation", _filter_argv(args))


def _run_filter_shaping(args: argparse.Namespace) -> int:
    return _dispatch_backend("filter-shaping", _filter_argv(args))


def _run_filter_document(args: argparse.Namespace) -> int:
    return _dispatch_backend("filter-document", _filter_argv(args))


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args._runner(args)
    except ValueError as exc:
        parser.error(str(exc))


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
