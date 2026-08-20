from __future__ import annotations

import json

from apps.cli.record_interpret_command import build_parser, run


def test_record_interpret_parser_accepts_show_events_flag() -> None:
    args = build_parser().parse_args(["--show-events"])

    assert args.show_events is True
    assert args.stop_hotkey == "Shift+Esc"


def test_record_interpret_parser_defaults_to_session_json() -> None:
    args = build_parser().parse_args([])

    assert args.save_raw == r".\session.json"


def test_record_interpret_parser_accepts_save_raw_path() -> None:
    args = build_parser().parse_args(["--save-raw", "session.json"])

    assert args.save_raw == "session.json"


def test_record_interpret_parser_accepts_no_save_flag() -> None:
    args = build_parser().parse_args(["--no-save"])

    assert args.no_save is True


def test_record_interpret_parser_accepts_threshold_overrides() -> None:
    args = build_parser().parse_args(
        [
            "--drag-min-distance-px",
            "20",
            "--double-click-max-interval-ms",
            "250",
        ]
    )

    assert args.drag_min_distance_px == 20
    assert args.double_click_max_interval_ms == 250


def test_record_interpret_threshold_flags_change_output(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "mouse_down",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 100,
                }
            )
            on_event(
                {
                    "type": "mouse_move",
                    "x": 11,
                    "y": 10,
                    "timestamp_ms": 110,
                }
            )
            on_event(
                {
                    "type": "mouse_up",
                    "button": "left",
                    "x": 11,
                    "y": 10,
                    "timestamp_ms": 130,
                }
            )
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run(["--click-max-move-distance-px", "0"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "mouse_click" not in captured.out
    assert "mouse_down: 1" in captured.out
    assert "mouse_move: 1" in captured.out
    assert "mouse_up: 1" in captured.out


def test_record_interpret_command_prints_recording_and_interpretation_summary(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "mouse_down",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 100,
                }
            )
            on_event(
                {
                    "type": "mouse_up",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 130,
                }
            )
            on_event({"type": "key_down", "key": "ctrl", "timestamp_ms": 150})
            on_event({"type": "key_down", "key": "c", "timestamp_ms": 160})
            on_event({"type": "key_up", "key": "c", "timestamp_ms": 170})
            on_event({"type": "key_up", "key": "ctrl", "timestamp_ms": 190})
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run(["--session-id", "session-1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Recording output will be saved to .\\session.json and interpreted afterward."
        in captured.out
    )
    assert "Recording stopped." in captured.out
    assert "Session ID                : session-1" in captured.out
    assert "Recorded raw event count  : 6" in captured.out
    assert "Saved raw session   : .\\session.json" in captured.out
    assert "Interpreted event count   : 2" in captured.out
    assert "mouse_click: 1" in captured.out
    assert "hotkey: 1" in captured.out


def test_record_interpret_command_can_save_raw_session_json(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "mouse_down",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 100,
                }
            )
            on_event(
                {
                    "type": "mouse_up",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 130,
                }
            )
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )

    output_path = tmp_path / "saved-session.json"
    exit_code = run(["--session-id", "session-2", "--save-raw", str(output_path)])
    captured = capsys.readouterr()

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (
        f"Recording output will be saved to {output_path} and interpreted afterward."
        in captured.out
    )
    assert f"Saved raw session   : {output_path}" in captured.out
    assert payload["session_id"] == "session-2"
    assert payload["state"] == "stopped"
    assert len(payload["events"]) == 2
    assert payload["events"][0]["type"] == "mouse_down"


def test_record_interpret_command_can_skip_saving_with_no_save(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "mouse_down",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 100,
                }
            )
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"
    exit_code = run(["--session-id", "session-2", "--no-save"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recording output will be saved" not in captured.out
    assert "Saved raw session" not in captured.out
    assert not output_path.exists()


def test_record_interpret_command_refuses_to_overwrite_existing_raw_session_without_force(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "mouse_down",
                    "button": "left",
                    "x": 10,
                    "y": 10,
                    "timestamp_ms": 100,
                }
            )
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"
    output_path.write_text("existing", encoding="utf-8")

    exit_code = run(["--session-id", "session-2"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Recording output will be saved to .\\session.json and interpreted afterward."
        in captured.out
    )
    assert "Refusing to overwrite" in captured.err
    assert "Saved raw session" not in captured.out
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_record_interpret_show_events_prints_readable_lines(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    class FakeBackend:
        def __init__(
            self,
            *,
            config,
            suppress=False,
            stop_hotkey="Shift+Esc",
            on_stop_requested=None,
            debug_stop_hotkey=False,
        ) -> None:
            self.on_stop_requested = on_stop_requested

        def start(self, on_event) -> None:
            on_event(
                {
                    "type": "key_down",
                    "key": "ctrl",
                    "timestamp_ms": 100,
                }
            )
            on_event(
                {
                    "type": "key_down",
                    "key": "c",
                    "timestamp_ms": 110,
                }
            )
            on_event(
                {
                    "type": "key_up",
                    "key": "c",
                    "timestamp_ms": 140,
                }
            )
            on_event(
                {
                    "type": "key_up",
                    "key": "ctrl",
                    "timestamp_ms": 160,
                }
            )
            if self.on_stop_requested is not None:
                self.on_stop_requested()

        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.cli.record_interpret_command.PynputCaptureBackend",
        FakeBackend,
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run(["--show-events"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[01] hotkey" in captured.out
    assert "ctrl + c" in captured.out
    assert "source=0-3 (4 events)" in captured.out
