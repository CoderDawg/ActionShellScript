from __future__ import annotations

from datetime import datetime, timezone
import time

import pytest

import infrastructure.debug_logger as debug_logger
from infrastructure.debug_logger import (
    DiagnosticConfig,
    DiagnosticDetail,
    DiagnosticEvent,
    DiagnosticSeverity,
    DiagnosticTimestampFormat,
    format_diagnostic_event,
    load_diagnostic_config_from_env,
    subscribe_diagnostic_events,
)


def test_format_diagnostic_event_includes_human_readable_and_millisecond_timestamps(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        debug_logger.time,
        "localtime",
        lambda timestamp: time.struct_time((2024, 1, 2, 3, 4, 5, 1, 2, -1)),
    )
    event = DiagnosticEvent(
        subsystem="runtime",
        message="hello",
        timestamp=1_700_000_000.123,
        thread_name="MainThread",
    )

    formatted = format_diagnostic_event(event)

    assert "[2024-01-02 03:04:05]" in formatted
    assert "[1700000000123ms]" in formatted
    assert "[runtime]" in formatted
    assert formatted.endswith(" hello")


def test_format_diagnostic_event_can_emit_iso8601_timestamp(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        debug_logger.time,
        "localtime",
        lambda timestamp: time.struct_time((2024, 1, 2, 3, 4, 5, 1, 2, -1)),
    )
    event = DiagnosticEvent(
        subsystem="runtime",
        message="hello",
        timestamp=1_700_000_000.123,
        thread_name="MainThread",
    )

    formatted = format_diagnostic_event(
        event,
        timestamp_format=DiagnosticTimestampFormat.ISO8601,
    )

    expected_iso = datetime.fromtimestamp(
        event.timestamp,
        tz=timezone.utc,
    ).astimezone().isoformat(timespec="milliseconds")

    assert f"[{expected_iso}]" in formatted
    assert "[1700000000123ms]" in formatted


def test_load_diagnostic_config_from_env_supports_iso8601_timestamp_format(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASS_DIAGNOSTICS", "1")
    monkeypatch.setenv("ASS_DIAGNOSTIC_TIMESTAMP_FORMAT", "iso8601")

    config = load_diagnostic_config_from_env()

    assert config.enabled is True
    assert config.timestamp_format == DiagnosticTimestampFormat.ISO8601


@pytest.mark.parametrize(
    ("severity", "detail", "expected_severity", "expected_detail"),
    [
        ("debug", "3", DiagnosticSeverity.DEBUG, DiagnosticDetail.TRACE),
        ("debug", "0..3", DiagnosticSeverity.DEBUG, DiagnosticDetail.TRACE),
        ("warning", "0", DiagnosticSeverity.WARNING, DiagnosticDetail.ESSENTIAL),
    ],
)
def test_load_diagnostic_config_from_env_accepts_numeric_detail_levels(
    monkeypatch,
    severity: str,
    detail: str,
    expected_severity: DiagnosticSeverity,
    expected_detail: DiagnosticDetail,
) -> None:
    monkeypatch.setenv("ASS_DIAGNOSTICS", "1")
    monkeypatch.setenv("ASS_DIAGNOSTIC_MIN_SEVERITY", severity)
    monkeypatch.setenv("ASS_DIAGNOSTIC_MAX_DETAIL", detail)

    config = load_diagnostic_config_from_env()

    assert config.enabled is True
    assert config.min_severity == expected_severity
    assert config.max_detail == expected_detail


def test_load_diagnostic_config_from_env_accepts_on_off_and_text_detail_levels(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASS_DIAGNOSTICS", "ON")
    monkeypatch.setenv("ASS_DIAGNOSTIC_MIN_SEVERITY", "warning")
    monkeypatch.setenv("ASS_DIAGNOSTIC_MAX_DETAIL", "trace")
    monkeypatch.setenv("ASS_DIAGNOSTIC_FILE", "OFF")
    monkeypatch.setenv("ASS_DIAGNOSTIC_STDOUT", "ON")

    config = load_diagnostic_config_from_env()

    assert config.enabled is True
    assert config.min_severity == DiagnosticSeverity.WARNING
    assert config.max_detail == DiagnosticDetail.TRACE
    assert config.log_to_file is False
    assert config.log_to_stdout is True


def test_emit_diagnostic_event_notifies_subscribers_even_without_log_sinks() -> None:
    debug_logger.reset_diagnostic_config()
    debug_logger.set_diagnostic_config(
        DiagnosticConfig(
            enabled=True,
            log_to_file=False,
            log_to_stdout=False,
        )
    )

    received: list[DiagnosticEvent] = []
    unsubscribe = subscribe_diagnostic_events(received.append)
    try:
        debug_logger.emit_diagnostic_event(
            DiagnosticEvent(
                subsystem="tests",
                message="diagnostic event",
            )
        )
    finally:
        unsubscribe()
        debug_logger.reset_diagnostic_config()

    assert len(received) == 1
    assert received[0].subsystem == "tests"
    assert received[0].message == "diagnostic event"
