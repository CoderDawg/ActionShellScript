from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.persistence.persistence_models import SaveRequirement


def add_force_argument(
    parser: argparse.ArgumentParser,
    help_text: str,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--force",
        action="store_true",
        help=help_text,
    )
    return parser


def refuse_unless_forced(
    *,
    target: Path,
    requirement: SaveRequirement,
    force: bool,
    target_description: str,
) -> bool:
    if not requirement.requires_save or force:
        return False

    reason = requirement.reason or f"{target_description} already exists."
    print(
        f"Refusing to overwrite {target} because {reason} Use --force to replace it.",
        file=sys.stderr,
    )
    return True
