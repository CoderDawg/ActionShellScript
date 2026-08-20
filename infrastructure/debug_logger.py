"""Structured project-wide diagnostic logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
import json
import os
import re
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Protocol
from collections.abc import Callable


class DiagnosticSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticDetail(IntEnum):
    ESSENTIAL = 0
    SUMMARY = 1
    DECISION = 2
    TRACE = 3


class DiagnosticTimestampFormat(StrEnum):
    EPOCH_MS = "epoch_ms"
    ISO8601 = "iso8601"


@dataclass(slots=True)
class DiagnosticEvent:
    subsystem: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    detail: DiagnosticDetail = DiagnosticDetail.SUMMARY
    event_id: str | None = None
    category: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    thread_name: str | None = None


@dataclass(slots=True)
class DiagnosticConfig:
    enabled: bool = False
    min_severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    max_detail: DiagnosticDetail = DiagnosticDetail.SUMMARY
    timestamp_format: DiagnosticTimestampFormat = DiagnosticTimestampFormat.EPOCH_MS
    log_to_stdout: bool = False
    log_to_file: bool = False
    log_path: Path | None = None
    enabled_subsystems: set[str] | None = None


class DiagnosticSink(Protocol):
    def write(self, event: DiagnosticEvent) -> None: ...


class StdoutDiagnosticSink:
    def __init__(self, *, timestamp_format: DiagnosticTimestampFormat) -> None:
        self._timestamp_format = timestamp_format

    def write(self, event: DiagnosticEvent) -> None:
        try:
            print(
                format_diagnostic_event(
                    event,
                    timestamp_format=self._timestamp_format,
                )
            )
        except Exception:
            pass


class FileDiagnosticSink:
    def __init__(
        self,
        path: Path,
        *,
        timestamp_format: DiagnosticTimestampFormat,
    ) -> None:
        self._path = Path(path)
        self._timestamp_format = timestamp_format

    def write(self, event: DiagnosticEvent) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    format_diagnostic_event(
                        event,
                        timestamp_format=self._timestamp_format,
                    )
                )
                handle.write("\n")
        except Exception:
            pass


_config: DiagnosticConfig | None = None
_config_lock = threading.RLock()
_event_subscribers: list[Callable[[DiagnosticEvent], None]] = []


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_csv_set(name: str) -> set[str] | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    values = {part.strip().lower() for part in raw.split(",") if part.strip()}
    return values or None


def _parse_int_enum_value(raw: str) -> int | None:
    normalized = raw.strip()
    if not normalized:
        return None

    range_match = re.fullmatch(r"(-?\d+)\s*\.\.\s*(-?\d+)", normalized)
    if range_match:
        return int(range_match.group(2), 10)

    try:
        return int(normalized, 10)
    except ValueError:
        return None


def _env_enum(name: str, enum_type, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if issubclass(enum_type, IntEnum):
        numeric_value = _parse_int_enum_value(normalized)
        if numeric_value is not None:
            try:
                return enum_type(numeric_value)
            except ValueError:
                pass
    for item in enum_type:
        if item.value == normalized or item.name.lower() == normalized:
            return item
    return default


def _parse_timestamp_format(raw: str | None) -> DiagnosticTimestampFormat:
    if raw is None:
        return DiagnosticTimestampFormat.EPOCH_MS

    normalized = raw.strip().lower()
    if normalized in {"", "epoch", "epoch_ms", "millis", "milliseconds"}:
        return DiagnosticTimestampFormat.EPOCH_MS
    if normalized in {"iso", "iso8601", "iso8601_ms", "iso8601-milliseconds"}:
        return DiagnosticTimestampFormat.ISO8601
    return DiagnosticTimestampFormat.EPOCH_MS


def _default_log_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"actionshellscript_diagnostics_{stamp}.log"
    return Path(tempfile.gettempdir()) / filename


def resolve_diagnostic_log_path(config: DiagnosticConfig | None = None) -> Path:
    resolved_config = config or get_diagnostic_config()
    if resolved_config.log_path is None:
        return _default_log_path()
    return Path(resolved_config.log_path).expanduser().resolve()


def load_diagnostic_config_from_env() -> DiagnosticConfig:
    enabled = _env_flag("ASS_DIAGNOSTICS", default=False)
    min_severity = _env_enum(
        "ASS_DIAGNOSTIC_MIN_SEVERITY",
        DiagnosticSeverity,
        DiagnosticSeverity.INFO,
    )
    max_detail = _env_enum(
        "ASS_DIAGNOSTIC_MAX_DETAIL",
        DiagnosticDetail,
        DiagnosticDetail.SUMMARY,
    )
    timestamp_format = _parse_timestamp_format(
        os.getenv("ASS_DIAGNOSTIC_TIMESTAMP_FORMAT")
    )
    log_to_file = _env_flag("ASS_DIAGNOSTIC_FILE", default=enabled)
    log_to_stdout = _env_flag("ASS_DIAGNOSTIC_STDOUT", default=False)
    enabled_subsystems = _env_csv_set("ASS_DIAGNOSTIC_SUBSYSTEMS")

    raw_path = os.getenv("ASS_DIAGNOSTIC_PATH", "").strip()
    log_path = Path(raw_path).expanduser().resolve() if raw_path else _default_log_path()

    return DiagnosticConfig(
        enabled=enabled,
        min_severity=min_severity,
        max_detail=max_detail,
        timestamp_format=timestamp_format,
        log_to_stdout=log_to_stdout,
        log_to_file=log_to_file,
        log_path=log_path,
        enabled_subsystems=enabled_subsystems,
    )


def get_diagnostic_config() -> DiagnosticConfig:
    global _config
    with _config_lock:
        if _config is None:
            _config = load_diagnostic_config_from_env()
        return _config


def set_diagnostic_config(config: DiagnosticConfig) -> None:
    global _config

    def _coerce_severity(value: object) -> DiagnosticSeverity:
        if isinstance(value, DiagnosticSeverity):
            return value
        return DiagnosticSeverity(str(value).strip().lower() or DiagnosticSeverity.INFO.value)

    def _coerce_detail(value: object) -> DiagnosticDetail:
        if isinstance(value, DiagnosticDetail):
            return value

        raw = str(value).strip().lower()
        if raw in {"", "summary"}:
            return DiagnosticDetail.SUMMARY
        if raw in {"essential", "0"}:
            return DiagnosticDetail.ESSENTIAL
        if raw in {"decision", "2"}:
            return DiagnosticDetail.DECISION
        if raw in {"trace", "3"}:
            return DiagnosticDetail.TRACE
        try:
            return DiagnosticDetail(int(raw, 10))
        except (TypeError, ValueError):
            return DiagnosticDetail.SUMMARY

    with _config_lock:
        _config = DiagnosticConfig(
            enabled=bool(config.enabled),
            min_severity=_coerce_severity(config.min_severity),
            max_detail=_coerce_detail(config.max_detail),
            timestamp_format=DiagnosticTimestampFormat(config.timestamp_format),
            log_to_stdout=bool(config.log_to_stdout),
            log_to_file=bool(config.log_to_file),
            log_path=(
                Path(config.log_path).expanduser().resolve()
                if config.log_path is not None
                else None
            ),
            enabled_subsystems=(
                {item.strip().lower() for item in config.enabled_subsystems}
                if config.enabled_subsystems
                else None
            ),
        )


def reset_diagnostic_config() -> None:
    global _config
    with _config_lock:
        _config = None


def subscribe_diagnostic_events(
    callback: Callable[[DiagnosticEvent], None],
) -> Callable[[], None]:
    with _config_lock:
        _event_subscribers.append(callback)

    def unsubscribe() -> None:
        with _config_lock:
            try:
                _event_subscribers.remove(callback)
            except ValueError:
                pass

    return unsubscribe


def diagnostics_enabled() -> bool:
    return get_diagnostic_config().enabled


def _format_timestamp(
    event: DiagnosticEvent,
    timestamp_format: DiagnosticTimestampFormat,
) -> str:
    if timestamp_format == DiagnosticTimestampFormat.ISO8601:
        return datetime.fromtimestamp(event.timestamp, tz=timezone.utc).astimezone().isoformat(
            timespec="milliseconds"
        )
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.timestamp))


def format_diagnostic_event(
    event: DiagnosticEvent,
    *,
    timestamp_format: DiagnosticTimestampFormat = DiagnosticTimestampFormat.EPOCH_MS,
) -> str:
    timestamp = _format_timestamp(event, timestamp_format)
    timestamp_ms = int(event.timestamp * 1000)
    thread_name = event.thread_name or threading.current_thread().name
    subsystem = (event.subsystem or "general").strip() or "general"

    parts = [
        f"[{timestamp}]",
        f"[{timestamp_ms}ms]",
        f"[{subsystem}]",
        f"[{event.severity.value.upper()}]",
        f"[D{int(event.detail)}]",
        f"[{thread_name}]",
    ]

    if event.event_id:
        parts.append(f"[{event.event_id}]")

    text = " ".join(parts) + f" {event.message}"

    if event.category:
        text += f" category={event.category}"

    if event.fields:
        serialized = json.dumps(event.fields, sort_keys=True, default=str)
        text += f" fields={serialized}"

    return text


def _severity_rank(severity: DiagnosticSeverity) -> int:
    if severity == DiagnosticSeverity.DEBUG:
        return 10
    if severity == DiagnosticSeverity.INFO:
        return 20
    if severity == DiagnosticSeverity.WARNING:
        return 30
    return 40


def _should_emit(config: DiagnosticConfig, event: DiagnosticEvent) -> bool:
    if not config.enabled:
        return False
    if _severity_rank(event.severity) < _severity_rank(config.min_severity):
        return False
    if event.detail > config.max_detail:
        return False

    if config.enabled_subsystems is not None:
        if event.subsystem.strip().lower() not in config.enabled_subsystems:
            return False

    return True


def _build_sinks(config: DiagnosticConfig) -> list[DiagnosticSink]:
    sinks: list[DiagnosticSink] = []
    if config.log_to_stdout:
        sinks.append(StdoutDiagnosticSink(timestamp_format=config.timestamp_format))
    if config.log_to_file:
        sinks.append(
            FileDiagnosticSink(
                resolve_diagnostic_log_path(config),
                timestamp_format=config.timestamp_format,
            )
        )
    return sinks


def emit_diagnostic_event(event: DiagnosticEvent) -> None:
    try:
        config = get_diagnostic_config()
        if not _should_emit(config, event):
            return

        for sink in _build_sinks(config):
            sink.write(event)
        with _config_lock:
            subscribers = tuple(_event_subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                pass
    except Exception:
        return


class DiagnosticLogger:
    def __init__(self, subsystem: str) -> None:
        normalized = (subsystem or "general").strip() or "general"
        self.subsystem = normalized

    def emit(
        self,
        message: str,
        *,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        detail: DiagnosticDetail = DiagnosticDetail.SUMMARY,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        emit_diagnostic_event(
            DiagnosticEvent(
                subsystem=self.subsystem,
                message=str(message),
                severity=severity,
                detail=detail,
                event_id=event_id,
                category=category,
                fields=dict(fields),
                thread_name=threading.current_thread().name,
            )
        )

    def debug(
        self,
        message: str,
        *,
        detail: DiagnosticDetail = DiagnosticDetail.SUMMARY,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.DEBUG,
            detail=detail,
            event_id=event_id,
            category=category,
            **fields,
        )

    def info(
        self,
        message: str,
        *,
        detail: DiagnosticDetail = DiagnosticDetail.SUMMARY,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.INFO,
            detail=detail,
            event_id=event_id,
            category=category,
            **fields,
        )

    def warning(
        self,
        message: str,
        *,
        detail: DiagnosticDetail = DiagnosticDetail.ESSENTIAL,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.WARNING,
            detail=detail,
            event_id=event_id,
            category=category,
            **fields,
        )

    def error(
        self,
        message: str,
        *,
        detail: DiagnosticDetail = DiagnosticDetail.ESSENTIAL,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.ERROR,
            detail=detail,
            event_id=event_id,
            category=category,
            **fields,
        )

    def exception(
        self,
        message: str,
        exc: BaseException,
        *,
        detail: DiagnosticDetail = DiagnosticDetail.ESSENTIAL,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            f"{message}: {exc.__class__.__name__}: {exc}",
            severity=DiagnosticSeverity.ERROR,
            detail=detail,
            event_id=event_id,
            category=category,
            exception_type=exc.__class__.__name__,
            **fields,
        )

    def decision(
        self,
        message: str,
        *,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.DEBUG,
            detail=DiagnosticDetail.DECISION,
            event_id=event_id,
            category=category,
            **fields,
        )

    def trace(
        self,
        message: str,
        *,
        event_id: str | None = None,
        category: str | None = None,
        **fields: object,
    ) -> None:
        self.emit(
            message,
            severity=DiagnosticSeverity.DEBUG,
            detail=DiagnosticDetail.TRACE,
            event_id=event_id,
            category=category,
            **fields,
        )


def get_diagnostic_logger(subsystem: str) -> DiagnosticLogger:
    return DiagnosticLogger(subsystem)


# Backward-compatible aliases for older docs/plans still referring to debug logger names.
LoggerConfig = DiagnosticConfig
get_debug_logger = get_diagnostic_logger
load_logger_config_from_env = load_diagnostic_config_from_env
get_logger_config = get_diagnostic_config
set_logger_config = set_diagnostic_config
reset_logger_config = reset_diagnostic_config
logging_enabled = diagnostics_enabled
