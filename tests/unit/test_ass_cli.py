from __future__ import annotations

import sys

import pytest

from apps.cli import ass_cli


def test_ass_cli_main_dispatches_uniform_frontend_arguments(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_loader(module_name: str, attribute_name: str):
        def runner(argv: list[str] | None) -> int:
            calls.append((f"{module_name}:{attribute_name}", list(argv or [])))
            return 0

        return runner

    monkeypatch.setattr(ass_cli, "_load_runner", fake_loader)

    def invoke(argv: list[str]) -> int:
        monkeypatch.setattr(sys, "argv", ["ass-cli", *argv])
        return ass_cli.main()

    assert invoke(["interpret", "--click-max-move-distance-px", "2"]) == 0
    assert invoke(["record"]) == 0
    assert (
        invoke(
            [
                "play",
                "recording",
                "--mode",
                "live",
                "--demo-live",
                "--ass-play",
            ]
        )
        == 0
    )
    assert (
        invoke(
            [
                "record-interpret",
                "--session-id",
                "session-1",
                "--no-save",
                "--show-events",
                "--click-max-move-distance-px",
                "3",
            ]
        )
        == 0
    )
    assert invoke(["record", "--no-save"]) == 0
    assert (
        invoke(
            [
                "generate",
                "--output",
                "generated.ass",
                "--no-script-delays",
            ]
        )
        == 0
    )
    assert (
        invoke(
            [
                "open-script",
                "--show-diagnostics",
                "--show-formatted",
            ]
        )
        == 0
    )
    assert (
        invoke(
            [
                "debug",
                "--input",
                "generated.ass",
                "--step",
                "--breakpoint",
                "12",
                "--ass-play",
            ]
        )
        == 0
    )
    assert (
        invoke(
            [
                "filter-recording",
                "--profile",
                "clean",
            ]
        )
        == 0
    )
    assert invoke(["filter-recording", "--list-profiles"]) == 0

    assert calls == [
        (
            "apps.cli.interpret_command:run",
            [r".\session.json", "--click-max-move-distance-px", "2"],
        ),
        (
            "apps.cli.record_command:run",
            [],
        ),
        (
            "apps.cli.play_command:run",
            [
                "recording",
                r".\session.json",
                "--mode",
                "live",
                "--demo-live",
                "--ass-play",
            ],
        ),
        (
            "apps.cli.record_interpret_command:run",
            [
                "--session-id",
                "session-1",
                "--no-save",
                "--click-max-move-distance-px",
                "3",
                "--show-events",
            ],
        ),
        ("apps.cli.record_command:run", ["--no-save"]),
        (
            "apps.cli.generate_command:run",
            [r".\session.json", "--output", "generated.ass", "--no-script-delays"],
        ),
        (
            "apps.cli.document_command:run",
            [r".\session.json", "--show-diagnostics", "--show-formatted"],
        ),
        (
            "apps.cli.debug_command:run",
            ["script", "generated.ass", "--step", "--breakpoint", "12", "--ass-play"],
        ),
        (
            "apps.cli.filter_recording_command:run",
            [r".\session.json", "--profile", "clean"],
        ),
        ("apps.cli.filter_recording_command:run", ["--list-profiles"]),
    ]


@pytest.mark.parametrize(
    ("argv", "source_kind", "source_path"),
    [
        (
            [
                "play",
                "recording",
                "session.json",
                "--mode",
                "preview",
                "--repeat",
                "2",
                "--ass-play",
            ],
            "recording",
            "session.json",
        ),
        (
            ["play", "script", "playback.ass", "--mode", "live", "--demo-live"],
            "script",
            "playback.ass",
        ),
    ],
)
def test_ass_cli_play_parser_uses_source_selection_then_source_path(
    argv: list[str],
    source_kind: str,
    source_path: str,
) -> None:
    args = ass_cli.build_parser().parse_args(argv)

    assert args.subcommand == "play"
    assert args.source_kind == source_kind
    assert args.input == source_path

    if source_kind == "recording":
        assert args.mode == "preview"
        assert args.repeat == 2
        assert args.demo_live is False
        assert args.ass_play is True
    else:
        assert args.mode == "live"
        assert args.repeat == 1
        assert args.demo_live is True


def test_ass_cli_play_help_shows_source_selector_and_source_path(capsys) -> None:
    with pytest.raises(SystemExit):
        ass_cli.build_parser().parse_args(["play", "--help"])

    captured = capsys.readouterr()

    assert "recording" in captured.out
    assert "script" in captured.out
    assert "--source-kind" not in captured.out


def test_ass_cli_record_defaults_to_session_json_output() -> None:
    args = ass_cli.build_parser().parse_args(["record"])

    assert args.subcommand == "record"
    assert args.save_raw == r".\session.json"


def test_ass_cli_record_accepts_no_save_flag() -> None:
    args = ass_cli.build_parser().parse_args(["record", "--no-save"])

    assert args.subcommand == "record"
    assert args.no_save is True


def test_ass_cli_record_interpret_accepts_no_save_flag() -> None:
    args = ass_cli.build_parser().parse_args(["record-interpret", "--no-save"])

    assert args.subcommand == "record-interpret"
    assert args.no_save is True


def test_ass_cli_debug_parser_accepts_sendkeys_key_tap_flag() -> None:
    args = ass_cli.build_parser().parse_args(
        [
            "debug",
            "--input",
            "generated.ass",
            "--step",
            "--breakpoint",
            "12",
            "--ass-play",
        ]
    )

    assert args.subcommand == "debug"
    assert args.input == "generated.ass"
    assert args.step is True
    assert args.breakpoint == [12]
    assert args.ass_play is True
