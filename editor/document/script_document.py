from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .document_version import DocumentVersion


_RECORDING_CONVERSION_ROUTE_PREFIX = "# Recording conversion route:"
_SOURCE_CAPTURE_EXCLUDED_PREFIX = "# Source capture excluded main window:"


@dataclass(slots=True)
class ScriptDocument:
    document_id: str
    text: str
    version: DocumentVersion = field(default_factory=DocumentVersion)
    is_dirty: bool = False
    last_saved_version: int | None = None

    source_session_id: str | None = None
    source_action_count: int | None = None
    generated_from_recording: bool = False
    recording_conversion_route: str | None = None
    source_capture_excluded_main_window: bool | None = None
    source_path: str | None = None

    def line_count(self) -> int:
        if not self.text:
            return 0
        return len(self.text.splitlines())

    def source_name(self) -> str | None:
        if self.source_path is None:
            return None
        return Path(self.source_path).name

    def source_directory(self) -> str | None:
        if self.source_path is None:
            return None
        return str(Path(self.source_path).parent)

    def replace_text(self, new_text: str) -> None:
        if new_text == self.text:
            return
        self.text = new_text
        self.version = self.version.next()
        self.is_dirty = True

    def mark_saved(self) -> None:
        self.is_dirty = False
        self.last_saved_version = self.version.value


def build_recording_provenance_header(
    *,
    recording_conversion_route: str | None,
    source_capture_excluded_main_window: bool | None,
) -> str:
    lines: list[str] = []
    if recording_conversion_route is not None:
        lines.append(
            f"{_RECORDING_CONVERSION_ROUTE_PREFIX} {recording_conversion_route}"
        )
    if source_capture_excluded_main_window is not None:
        lines.append(
            f"{_SOURCE_CAPTURE_EXCLUDED_PREFIX} "
            f"{'true' if source_capture_excluded_main_window else 'false'}"
        )
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


def strip_recording_provenance_header(text: str) -> str:
    header_end = 0
    found_header = False
    for line in text.splitlines(keepends=True):
        if not line.startswith("#"):
            break

        stripped = line[1:].strip()
        if stripped.startswith(_RECORDING_CONVERSION_ROUTE_PREFIX[1:].strip()):
            found_header = True
            header_end += len(line)
            continue

        if stripped.startswith(_SOURCE_CAPTURE_EXCLUDED_PREFIX[1:].strip()):
            found_header = True
            header_end += len(line)
            continue

        break

    if not found_header:
        return text

    if text.startswith("\r\n", header_end):
        header_end += 2
    elif text.startswith("\n", header_end) or text.startswith("\r", header_end):
        header_end += 1

    return text[header_end:]


def parse_recording_provenance_header(
    text: str,
) -> tuple[str | None, bool | None]:
    recording_conversion_route: str | None = None
    source_capture_excluded_main_window: bool | None = None

    for line in text.splitlines():
        if not line:
            break
        if not line.startswith("#"):
            break

        stripped = line[1:].strip()
        if stripped.startswith(_RECORDING_CONVERSION_ROUTE_PREFIX[1:].strip()):
            _, _, value = stripped.partition(":")
            value = value.strip()
            if value:
                recording_conversion_route = value
            continue

        if stripped.startswith(_SOURCE_CAPTURE_EXCLUDED_PREFIX[1:].strip()):
            _, _, value = stripped.partition(":")
            value = value.strip().lower()
            if value in {"true", "yes", "1"}:
                source_capture_excluded_main_window = True
            elif value in {"false", "no", "0"}:
                source_capture_excluded_main_window = False

    return recording_conversion_route, source_capture_excluded_main_window
