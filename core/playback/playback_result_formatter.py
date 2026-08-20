from __future__ import annotations

from dataclasses import dataclass

from core.playback.playback_result import PlaybackResult


@dataclass(frozen=True, slots=True)
class PlaybackFailureDetails:
    error_line: int | None = None
    error_message: str | None = None

    def as_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {}
        if self.error_line is not None:
            fields["error_line"] = self.error_line
        if self.error_message:
            fields["error_message"] = self.error_message
        return fields

    def format_lines(self) -> list[str]:
        lines: list[str] = []
        if self.error_line is not None:
            lines.append(f"Playback error line    : {self.error_line}")
        if self.error_message:
            lines.append(f"Playback error         : {self.error_message}")
        return lines


def playback_failure_details(result: PlaybackResult) -> PlaybackFailureDetails:
    return PlaybackFailureDetails(
        error_line=result.error_line,
        error_message=result.error_message,
    )


def format_playback_failure(result: PlaybackResult) -> list[str]:
    return playback_failure_details(result).format_lines()


def playback_failure_fields(result: PlaybackResult) -> dict[str, object]:
    return playback_failure_details(result).as_fields()
