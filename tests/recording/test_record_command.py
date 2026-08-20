from __future__ import annotations

import json

import pytest

from apps.cli.record_command import build_parser, run


def test_stop_hotkey_defaults_to_shift_esc() -> None:
    args = build_parser().parse_args([])

    assert args.stop_hotkey == "Shift+Esc"


def test_stop_hotkey_help_mentions_alternate_chords() -> None:
    parser = build_parser()
    stop_hotkey_action = next(
        action for action in parser._actions if action.dest == "stop_hotkey"
    )

    assert stop_hotkey_action.help == (
        "Chord that stops recording without Ctrl+C. Use | to add alternate "
        "chords, such as Shift+Esc|Ctrl+C. Default: Shift+Esc."
    )


def test_debug_stop_hotkey_flag_parses() -> None:
    args = build_parser().parse_args(["--debug-stop-hotkey"])

    assert args.debug_stop_hotkey is True


def test_save_raw_defaults_to_session_json() -> None:
    args = build_parser().parse_args([])

    assert args.save_raw == r".\session.json"


def test_save_raw_flag_parses() -> None:
    args = build_parser().parse_args(["--save-raw", "session.json"])

    assert args.save_raw == "session.json"


def test_no_save_flag_parses() -> None:
    args = build_parser().parse_args(["--no-save"])

    assert args.no_save is True


def test_save_raw_and_no_save_are_mutually_exclusive() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--no-save", "--save-raw", "session.json"])


def test_force_flag_parses() -> None:
    args = build_parser().parse_args(["--force"])

    assert args.force is True


def test_record_command_can_save_raw_session_json(
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

    monkeypatch.setattr("apps.cli.record_command.PynputCaptureBackend", FakeBackend)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"
    exit_code = run(["--session-id", "session-raw"])
    captured = capsys.readouterr()

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Recording output will be saved to .\\session.json." in captured.out
    assert "Recording started. Press Shift+Esc or Ctrl+C to stop." in captured.out
    assert "Saved raw session   : .\\session.json" in captured.out
    assert payload["session_id"] == "session-raw"
    assert payload["state"] == "stopped"
    assert len(payload["events"]) == 2
    assert payload["events"][1]["type"] == "mouse_up"


def test_record_command_refuses_to_overwrite_existing_raw_session_without_force(
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

    monkeypatch.setattr("apps.cli.record_command.PynputCaptureBackend", FakeBackend)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"
    output_path.write_text("existing", encoding="utf-8")

    exit_code = run(["--session-id", "session-raw"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Recording output will be saved to .\\session.json." in captured.out
    assert "Refusing to overwrite" in captured.err
    assert "Saved raw session" not in captured.out
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_record_command_overwrites_existing_raw_session_with_force(
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

    monkeypatch.setattr("apps.cli.record_command.PynputCaptureBackend", FakeBackend)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"
    output_path.write_text("existing", encoding="utf-8")

    exit_code = run(
        [
            "--session-id",
            "session-raw",
            "--force",
        ]
    )
    captured = capsys.readouterr()

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["session_id"] == "session-raw"
    assert payload["state"] == "stopped"
    assert len(payload["events"]) == 2
    assert "Saved raw session   : .\\session.json" in captured.out


def test_record_command_can_skip_saving_with_no_save(
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

    monkeypatch.setattr("apps.cli.record_command.PynputCaptureBackend", FakeBackend)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "session.json"

    exit_code = run(["--session-id", "session-raw", "--no-save"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recording output will be saved" not in captured.out
    assert "Saved raw session" not in captured.out
    assert not output_path.exists()
