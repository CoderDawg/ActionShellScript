from __future__ import annotations

from core.recording.input_capture import InputCapture

from tests.recording.fakes import FakeInputCaptureBackend


def test_input_capture_delegates_start_and_stop() -> None:
    backend = FakeInputCaptureBackend()
    capture = InputCapture(backend=backend)
    observed: list[dict[str, object]] = []

    capture.start(observed.append)
    backend.emit({"type": "mouse_move", "timestamp_ms": 10})
    capture.stop()

    assert backend.started is False
    assert backend.stopped is True
    assert observed == [{"type": "mouse_move", "timestamp_ms": 10}]
