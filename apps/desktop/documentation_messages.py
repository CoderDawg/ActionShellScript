from __future__ import annotations

from pathlib import Path


def docs_index_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "index.md"


def pixel_inspector_guide_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "user" / "pixel_inspector_guide.md"


def system_viewer_fallback_status() -> str:
    return "Opened documentation in the system viewer"


def ass_help_fallback_status() -> str:
    return "Opened documentation in ass-help"


def documentation_unavailable_status() -> str:
    return "Documentation unavailable"


def documentation_unavailable_message(error: Exception, docs_path: Path) -> str:
    return (
        "The embedded help browser could not start, and the system viewer fallback "
        f"also failed.\n\nError: {error}\n\nDocs path: {docs_path}"
    )
