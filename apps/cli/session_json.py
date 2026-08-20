from __future__ import annotations

from apps.cli.filter_artifact_io import save_recording_session
from core.recording.recording_session import RecordingSession


def save_raw_session(session: RecordingSession, output_path: str) -> None:
    save_recording_session(session, output_path)
