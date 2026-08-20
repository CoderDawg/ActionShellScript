from __future__ import annotations

from core.recording.recording_session import RecordingSession, RecordingState

from ..filter_profile import FilterProfile


class MouseJitterCleanupFilter:
    filter_id = "mouse_jitter_cleanup"

    def apply(
        self,
        source: RecordingSession,
        profile: FilterProfile,
    ) -> RecordingSession:
        threshold_px = int(profile.settings.get("move_distance_threshold_px", 1))
        threshold_sq = threshold_px * threshold_px

        cleaned_events: list[dict[str, object]] = []
        last_move_x: int | None = None
        last_move_y: int | None = None

        for event in source.events:
            current = dict(event)
            event_type = str(current.get("type", "")).strip().lower()

            if event_type != "mouse_move":
                cleaned_events.append(current)
            if event_type not in {"mouse_move"}:
                last_move_x = None
                last_move_y = None
                continue

            x = int(current.get("x", 0))
            y = int(current.get("y", 0))

            if last_move_x is not None and last_move_y is not None:
                dx = x - last_move_x
                dy = y - last_move_y
                if (dx * dx) + (dy * dy) <= threshold_sq:
                    continue

            cleaned_events.append(current)
            last_move_x = x
            last_move_y = y

        return RecordingSession(
            session_id=source.session_id,
            state=RecordingState(source.state.value),
            started_at_ms=source.started_at_ms,
            stopped_at_ms=source.stopped_at_ms,
            events=cleaned_events,
        )
