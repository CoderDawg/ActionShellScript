from __future__ import annotations

import argparse

from core.shaping.shaping_config import ShapingConfig


DEFAULT_SHAPING_CONFIG = ShapingConfig()


def add_shaping_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--no-delays",
        action="store_true",
        help="Drop delay actions from shaped output.",
    )
    parser.add_argument(
        "--min-delay-ms",
        type=int,
        default=DEFAULT_SHAPING_CONFIG.min_delay_ms,
        help="Discard delays shorter than this many milliseconds.",
    )
    parser.add_argument(
        "--max-delay-ms",
        type=int,
        default=DEFAULT_SHAPING_CONFIG.max_delay_ms,
        help="Clamp emitted delays to this maximum duration.",
    )
    parser.add_argument(
        "--no-collapse-delays",
        action="store_true",
        help="Keep consecutive delay actions separate.",
    )
    parser.add_argument(
        "--no-mouse-moves",
        action="store_true",
        help="Drop mouse_move actions from shaped output.",
    )
    parser.add_argument(
        "--only-click-positions",
        action="store_true",
        help="Drop free mouse_move actions and keep click/drag position-bearing actions.",
    )
    parser.add_argument(
        "--no-collapse-mouse-moves",
        action="store_true",
        help="Keep consecutive mouse_move actions separate.",
    )
    parser.add_argument(
        "--no-collapse-clicks",
        action="store_true",
        help="Preserve detailed click fields instead of simplifying simple clicks.",
    )
    parser.add_argument(
        "--click-collapse-distance-px",
        type=int,
        default=DEFAULT_SHAPING_CONFIG.click_collapse_distance_px,
        help="Only simplify clicks whose max movement stays within this distance.",
    )
    parser.add_argument(
        "--click-collapse-max-duration-ms",
        type=int,
        default=DEFAULT_SHAPING_CONFIG.click_collapse_max_duration_ms,
        help="Only simplify clicks whose duration stays within this limit.",
    )
    parser.add_argument(
        "--no-collapse-text-input",
        action="store_true",
        help="Keep printable key holds as structured keyboard actions.",
    )
    parser.add_argument(
        "--keyboard-output-style",
        choices=["structured", "text"],
        default=DEFAULT_SHAPING_CONFIG.keyboard_output_style,
        help="Choose whether printable keyboard output stays structured or collapses into text.",
    )
    return parser


def build_shaping_config(args: argparse.Namespace) -> ShapingConfig:
    return ShapingConfig(
        emit_delays=not args.no_delays,
        min_delay_ms=args.min_delay_ms,
        max_delay_ms=args.max_delay_ms,
        collapse_consecutive_delays=not args.no_collapse_delays,
        emit_mouse_moves=not args.no_mouse_moves,
        emit_only_click_positions=args.only_click_positions,
        collapse_consecutive_mouse_moves=not args.no_collapse_mouse_moves,
        collapse_simple_click_sequences=not args.no_collapse_clicks,
        click_collapse_distance_px=args.click_collapse_distance_px,
        click_collapse_max_duration_ms=args.click_collapse_max_duration_ms,
        collapse_text_input=not args.no_collapse_text_input,
        keyboard_output_style=args.keyboard_output_style,
    )
