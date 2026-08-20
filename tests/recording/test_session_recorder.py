from __future__ import annotations

import itertools

import pytest

from core.recording.input_capture import InputCapture
from core.recording.recorder_config import RecorderConfig
from core.recording.recording_session import RecordingState
from core.recording.session_recorder import SessionRecorder

from tests.recording.fakes import FakeInputCaptureBackend


def test_start_success_registers_active_session() -> None:
    backend = FakeInputCaptureBackend()
    recorder = SessionRecorder(
        config=RecorderConfig(),
        capture=InputCapture(backend=backend),
    )

    session = recorder.start(session_id="session-1")

    assert session.session_id == "session-1"
    assert session.state is RecordingState.RECORDING
    assert recorder.session is session
    assert recorder.is_recording is True
    assert backend.started is True


def test_start_rolls_back_when_capture_start_fails() -> None:
    backend = FakeInputCaptureBackend(fail_on_start=RuntimeError("boom"))
    recorder = SessionRecorder(
        config=RecorderConfig(),
        capture=InputCapture(backend=backend),
    )

    with pytest.raises(RuntimeError, match="boom"):
        recorder.start(session_id="session-1")

    assert recorder.session is None
    assert recorder.is_recording is False


def test_stop_success_returns_completed_session() -> None:
    backend = FakeInputCaptureBackend()
    recorder = SessionRecorder(
        config=RecorderConfig(),
        capture=InputCapture(backend=backend),
    )
    recorder.start(session_id="session-1")

    session = recorder.stop()

    assert session.state is RecordingState.STOPPED
    assert session.stopped_at_ms is not None
    assert backend.stopped is True
    assert recorder.session is session


def test_reset_stops_active_session_and_clears_current_session() -> None:
    backend = FakeInputCaptureBackend()
    recorder = SessionRecorder(
        config=RecorderConfig(),
        capture=InputCapture(backend=backend),
    )
    recorder.start(session_id="session-1")

    recorder.reset()

    assert backend.stopped is True
    assert recorder.session is None
    assert recorder.is_recording is False


def test_filtering_by_config_flags() -> None:
    backend = FakeInputCaptureBackend()
    recorder = SessionRecorder(
        config=RecorderConfig(
            capture_mouse_moves=False,
            capture_mouse_buttons=True,
            capture_mouse_wheel=False,
            capture_keyboard=True,
        ),
        capture=InputCapture(backend=backend),
    )
    recorder.start(session_id="session-1")

    backend.emit({"type": "mouse_move", "x": 10, "y": 20, "timestamp_ms": 5})
    backend.emit({"type": "mouse_down", "button": "left", "x": 10, "y": 20, "timestamp_ms": 10})
    backend.emit({"type": "mouse_wheel", "dx": 0, "dy": 1, "timestamp_ms": 15})
    backend.emit({"type": "key_down", "key": "a", "timestamp_ms": 20})
    session = recorder.stop()

    assert [event["type"] for event in session.events] == ["mouse_down", "key_down"]


def test_missing_timestamps_fall_back_to_relative_elapsed_time() -> None:
    backend = FakeInputCaptureBackend()
    times = itertools.count(start=1000, step=25)
    recorder = SessionRecorder(
        config=RecorderConfig(),
        capture=InputCapture(backend=backend),
        clock=lambda: next(times),
    )
    recorder.start(session_id="session-1")

    backend.emit({"type": "key_down", "key": "a"})
    session = recorder.stop()

    assert session.events[0]["timestamp_ms"] == 25
