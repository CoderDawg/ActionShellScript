from __future__ import annotations

import json

from apps.cli.shape_command import build_parser, run


def test_shape_command_parser_defaults_to_session_json() -> None:
    args = build_parser().parse_args([])

    assert args.session_path == r".\session.json"


def test_shape_command_parser_accepts_shaping_flags() -> None:
    args = build_parser().parse_args(
        [
            "session.json",
            "--keyboard-output-style",
            "text",
            "--no-collapse-clicks",
            "--no-mouse-moves",
        ]
    )

    assert args.keyboard_output_style == "text"
    assert args.no_collapse_clicks is True
    assert args.no_mouse_moves is True


def test_shape_command_runs_interpretation_into_shaping(tmp_path, capsys) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "session-3",
                "state": "stopped",
                "events": [
                    {"type": "key_down", "key": "h", "timestamp_ms": 100},
                    {"type": "key_up", "key": "h", "timestamp_ms": 120},
                    {"type": "key_down", "key": "i", "timestamp_ms": 130},
                    {"type": "key_up", "key": "i", "timestamp_ms": 150},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run(
        [
            str(session_path),
            "--keyboard-output-style",
            "text",
            "--show-actions",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Session ID               : session-3" in captured.out
    assert "Interpreted event count  : 2" in captured.out
    assert "Shaped action count      : 1" in captured.out
    assert "text: 1" in captured.out
    assert "[01] text" in captured.out
    assert "text='hi'" in captured.out


def test_shape_command_uses_default_session_json_when_input_is_omitted(
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
                "events": [
                    {"type": "key_down", "key": "h", "timestamp_ms": 100},
                    {"type": "key_up", "key": "h", "timestamp_ms": 120},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = run(["--keyboard-output-style", "text"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Session ID               : session-default" in captured.out
