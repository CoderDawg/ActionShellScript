from __future__ import annotations

import json

from apps.cli.interpret_command import build_parser, run


def test_interpret_command_parser_defaults_to_session_json() -> None:
    args = build_parser().parse_args([])

    assert args.session_path == r".\session.json"


def test_interpret_command_parser_accepts_threshold_overrides() -> None:
    args = build_parser().parse_args(
        [
            "session.json",
            "--click-max-move-distance-px",
            "0",
            "--drag-min-distance-px",
            "12",
        ]
    )

    assert args.click_max_move_distance_px == 0
    assert args.drag_min_distance_px == 12


def test_interpret_command_prints_summary_from_session_json(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "state": "stopped",
                "started_at_ms": 100,
                "stopped_at_ms": 180,
                "events": [
                    {
                        "type": "mouse_down",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 100,
                    },
                    {
                        "type": "mouse_up",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 130,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run([str(session_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Session ID             : session-1" in captured.out
    assert "mouse_click: 1" in captured.out


def test_interpret_command_uses_default_session_json_when_input_is_omitted(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-default",
                "state": "stopped",
                "started_at_ms": 100,
                "stopped_at_ms": 180,
                "events": [
                    {
                        "type": "mouse_down",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 100,
                    },
                    {
                        "type": "mouse_up",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 130,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Session ID             : session-default" in captured.out


def test_interpret_command_threshold_flags_change_output(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-2",
                "state": "stopped",
                "started_at_ms": 100,
                "stopped_at_ms": 180,
                "events": [
                    {
                        "type": "mouse_down",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 100,
                    },
                    {
                        "type": "mouse_move",
                        "x": 11,
                        "y": 10,
                        "timestamp_ms": 110,
                    },
                    {
                        "type": "mouse_up",
                        "button": "left",
                        "x": 11,
                        "y": 10,
                        "timestamp_ms": 130,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run([str(session_path), "--click-max-move-distance-px", "0"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "mouse_click" not in captured.out
    assert "mouse_down: 1" in captured.out
    assert "mouse_move: 1" in captured.out
    assert "mouse_up: 1" in captured.out


def test_interpret_command_show_events_prints_readable_lines(
    tmp_path,
    capsys,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-3",
                "state": "stopped",
                "events": [
                    {
                        "type": "mouse_down",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 100,
                    },
                    {
                        "type": "mouse_up",
                        "button": "left",
                        "x": 10,
                        "y": 10,
                        "timestamp_ms": 130,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run([str(session_path), "--show-events"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[01] mouse_click" in captured.out
    assert "1x left at (10, 10)" in captured.out
    assert "source=0-1 (2 events)" in captured.out
