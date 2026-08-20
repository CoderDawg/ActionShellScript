from __future__ import annotations

from core.playback.builders.from_recording_builder import PlaybackPlanFromRecordingBuilder
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from core.playback.playback_plan import PlaybackPlan
from core.recording.recording_session import RecordingSession
from editor.document.script_document import ScriptDocument


class PlaybackBuilder:
    def __init__(
        self,
        *,
        from_recording: PlaybackPlanFromRecordingBuilder | None = None,
        from_script: PlaybackPlanFromScriptBuilder | None = None,
    ) -> None:
        self._from_recording = from_recording or PlaybackPlanFromRecordingBuilder()
        self._from_script = from_script or PlaybackPlanFromScriptBuilder()

    def build_from_recording(
        self,
        session: RecordingSession,
    ) -> PlaybackPlan:
        return self._from_recording.build(session)

    def build_from_script(
        self,
        document: ScriptDocument,
    ) -> PlaybackPlan:
        return self._from_script.build(document)
