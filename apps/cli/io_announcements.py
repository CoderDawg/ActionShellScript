from __future__ import annotations

from pathlib import Path


def resolve_display_path(path_text: str) -> str:
    return str(Path(path_text).resolve())


def print_input_output(
    *,
    input_label: str,
    input_value: str,
    output_label: str | None = None,
    output_value: str | None = None,
) -> None:
    print(f"{input_label:<22}: {input_value}", flush=True)
    if output_label is not None:
        print(f"{output_label:<22}: {output_value or '<none>'}", flush=True)
