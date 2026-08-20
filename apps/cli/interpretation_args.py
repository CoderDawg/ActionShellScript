from __future__ import annotations

import argparse

from core.interpretation.interpretation_config import InterpretationConfig

DEFAULT_INTERPRETATION_CONFIG = InterpretationConfig()


def add_interpretation_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--click-max-move-distance-px",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.click_max_move_distance_px,
        help="Maximum pointer travel allowed for click recognition.",
    )
    parser.add_argument(
        "--double-click-max-interval-ms",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_interval_ms,
        help="Maximum total time allowed from first press to second release.",
    )
    parser.add_argument(
        "--double-click-max-distance-px",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_distance_px,
        help="Maximum distance allowed between click anchor points.",
    )
    parser.add_argument(
        "--double-click-max-pause-ms",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_pause_ms,
        help="Maximum pause allowed between the first release and second press.",
    )
    parser.add_argument(
        "--double-click-max-inter-click-move-distance-px",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.double_click_max_inter_click_move_distance_px,
        help="Maximum pointer drift allowed between two clicks in a double-click.",
    )
    parser.add_argument(
        "--drag-min-distance-px",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.drag_min_distance_px,
        help="Minimum pointer travel required to recognize a drag.",
    )
    parser.add_argument(
        "--drag-min-duration-ms",
        type=int,
        default=DEFAULT_INTERPRETATION_CONFIG.drag_min_duration_ms,
        help="Minimum press duration required to recognize a drag.",
    )
    return parser


def build_interpretation_config(args: argparse.Namespace) -> InterpretationConfig:
    return InterpretationConfig(
        click_max_move_distance_px=args.click_max_move_distance_px,
        double_click_max_interval_ms=args.double_click_max_interval_ms,
        double_click_max_distance_px=args.double_click_max_distance_px,
        double_click_max_pause_ms=args.double_click_max_pause_ms,
        double_click_max_inter_click_move_distance_px=(
            args.double_click_max_inter_click_move_distance_px
        ),
        drag_min_distance_px=args.drag_min_distance_px,
        drag_min_duration_ms=args.drag_min_duration_ms,
    )
