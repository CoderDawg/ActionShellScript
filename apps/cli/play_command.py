from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
import tempfile
from pathlib import Path

from application.interpretation_service import InterpretationService
from application.playback_service import PlaybackService
from application.script_document_service import ScriptDocumentService
from application.script_generation_service import ScriptGenerationService
from application.shaping_service import ShapingService
from apps.cli.generation_args import add_generation_arguments, build_generation_config
from apps.cli.interpret_command import load_session
from apps.cli.interpretation_args import add_interpretation_arguments, build_interpretation_config
from apps.cli.io_announcements import print_input_output
from apps.cli.io_announcements import resolve_display_path
from apps.cli.record_command import DEFAULT_RAW_SESSION_PATH
from core.playback.playback_builder import PlaybackBuilder
from core.playback.playback_engine import PlaybackEngine
from core.playback.playback_mode import PlaybackMode
from core.playback.playback_request import PlaybackRequest
from core.playback.playback_events import playback_event_to_dict
from core.playback.builders.from_script_builder import PlaybackPlanFromScriptBuilder
from core.playback.executors.live_input_executor import LiveInputExecutor
from core.playback.executors.preview_input_executor import PreviewInputExecutor
from core.playback.playback_result_formatter import format_playback_failure
from apps.cli.shaping_args import add_shaping_arguments, build_shaping_config
from apps.desktop.presentation import normalize_output_chunks
from editor.document.script_document import ScriptDocument
from core.runtime.script_runtime import ScriptRuntime
from infrastructure.debug_logger import get_diagnostic_config
from infrastructure.debug_logger import get_diagnostic_logger
from infrastructure.debug_logger import set_diagnostic_config
from infrastructure.persistence.script_document_file_store import (
    ScriptDocumentFileStore,
)


log = get_diagnostic_logger("playback_engine")


class _UnavailableLiveExecutor:
    def execute(self, event) -> None:
        raise RuntimeError(
            "Live playback executor is unavailable for this run. Use --mode live "
            "with a configured live input host."
        )


class _DemoLivePlaybackAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
        call = {"action": "move_mouse", "x": int(x), "y": int(y)}
        if speed is not None:
            call["speed"] = max(0, min(100, int(speed)))
        self.calls.append(call)

    def mouse_down(self, button: str) -> None:
        self.calls.append({"action": "mouse_down", "button": str(button)})

    def mouse_up(self, button: str) -> None:
        self.calls.append({"action": "mouse_up", "button": str(button)})

    def mouse_click(self, button: str, clicks: int) -> None:
        self.calls.append(
            {
                "action": "mouse_click",
                "button": str(button),
                "clicks": max(1, int(clicks)),
            }
        )

    def mouse_wheel(self, delta: int) -> None:
        self.calls.append({"action": "mouse_wheel", "delta": int(delta)})

    def key_down(self, key: str) -> None:
        self.calls.append({"action": "key_down", "key": str(key)})

    def key_up(self, key: str) -> None:
        self.calls.append({"action": "key_up", "key": str(key)})

    def send_text(self, text: str) -> None:
        self.calls.append({"action": "send_text", "text": str(text)})

    def sleep_ms(self, duration_ms: int) -> None:
        self.calls.append({"action": "sleep_ms", "duration_ms": max(0, int(duration_ms))})


class _TracingPlaybackHost:
    def __init__(self, host) -> None:
        self._host = host
        self.calls: list[dict[str, object]] = []
        self._call_index = 0

    def _trace(self, action: str, **fields: object) -> None:
        self._call_index += 1
        payload = {"action": action, **fields}
        self.calls.append(payload)
        log.info(
            "Live host call dispatched",
            event_id="playback.live.dispatched",
            action=action,
            call_index=self._call_index,
            **fields,
        )
        print(
            f"Live dispatch {self._call_index:02d}: {json.dumps(payload, sort_keys=True)}",
            flush=True,
        )

    def move_mouse(self, x: int, y: int, *, speed: int | None = None) -> None:
        payload = {"x": int(x), "y": int(y)}
        if speed is not None:
            payload["speed"] = max(0, min(100, int(speed)))
        self._trace("move_mouse", **payload)
        self._host.move_mouse(x, y, speed=speed)

    def mouse_down(self, button: str) -> None:
        self._trace("mouse_down", button=str(button))
        self._host.mouse_down(button)

    def mouse_up(self, button: str) -> None:
        self._trace("mouse_up", button=str(button))
        self._host.mouse_up(button)

    def mouse_click(self, button: str, clicks: int) -> None:
        self._trace(
            "mouse_click",
            button=str(button),
            clicks=max(1, int(clicks)),
        )
        self._host.mouse_click(button, clicks)

    def mouse_wheel(self, delta: int) -> None:
        self._trace("mouse_wheel", delta=int(delta))
        self._host.mouse_wheel(delta)

    def key_down(self, key: str) -> None:
        self._trace("key_down", key=str(key))
        self._host.key_down(key)

    def key_up(self, key: str) -> None:
        self._trace("key_up", key=str(key))
        self._host.key_up(key)

    def send_text(self, text: str) -> None:
        self._trace("send_text", text=str(text))
        self._host.send_text(text)

    def sleep_ms(self, duration_ms: int) -> None:
        self._trace("sleep_ms", duration_ms=max(0, int(duration_ms)))
        self._host.sleep_ms(duration_ms)


def _add_playback_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in PlaybackMode],
        default=PlaybackMode.PREVIEW.value,
        help="Choose preview or live execution. Default: preview.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="How many times to execute the derived playback plan.",
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Pause before each playback event and wait for Enter.",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=0,
        help="Sleep for this many milliseconds before each playback event.",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=0,
        help="Sleep for this many milliseconds after mouse moves before mouse button actions.",
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print the derived preview/live playback events after execution.",
    )
    parser.add_argument(
        "--demo-live",
        action="store_true",
        help=(
            "Use a deterministic in-memory live host for the live demo path. "
            "Pairs with --mode live."
        ),
    )
    parser.add_argument(
        "--ass-play",
        action="store_true",
        help=(
            "Emit SendKeys printable characters as key taps instead of text "
            "events."
        ),
    )
    return parser


def _add_recording_conversion_arguments(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--recording-conversion-mode",
        choices=["promote_generated", "direct_import"],
        default=None,
        help=(
            "Optionally convert a recording into a ScriptDocument before "
            "playback. Default: keep the current recording playback path."
        ),
    )
    return parser


def _recording_route_label(args: argparse.Namespace) -> str:
    if args.recording_conversion_mode is None:
        return "Raw recording path"
    return f"Converted document path ({args.recording_conversion_mode})"


def _resolve_diagnostic_log_path() -> Path | None:
    config = get_diagnostic_config()
    if not config.enabled:
        return None

    if config.log_path is not None:
        resolved = Path(config.log_path).resolve()
        if resolved != config.log_path:
            set_diagnostic_config(replace(config, log_path=resolved))
        return resolved

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    resolved = Path(tempfile.gettempdir()) / f"actionshellscript_diagnostics_{stamp}.log"
    set_diagnostic_config(replace(config, log_path=resolved))
    return resolved


def _runtime_special_values(args: argparse.Namespace) -> dict[str, object]:
    return {
        "PlaybackSendKeyTapsInsteadOfText": bool(args.ass_play),
    }


def _sendkeys_transport_label(use_key_taps: bool) -> str:
    return "key taps" if use_key_taps else "text events"


def build_parser() -> argparse.ArgumentParser:
    phase_6_parser = argparse.ArgumentParser(add_help=False)
    phase_6_parser = _add_playback_arguments(phase_6_parser)
    parser = argparse.ArgumentParser(
        prog="ass-cli play",
        description=(
            "Build and execute a derived playback plan from an explicit recording "
            "or script authority source. Use --demo-live for a deterministic "
            "in-memory live demo path."
        ),
        parents=[phase_6_parser],
    )

    subparsers = parser.add_subparsers(dest="source_kind", required=True)

    recording_parser = subparsers.add_parser(
        "recording",
        help="Build playback from a saved RecordingSession JSON file.",
        parents=[phase_6_parser],
    )
    add_interpretation_arguments(recording_parser)
    add_shaping_arguments(recording_parser)
    add_generation_arguments(recording_parser)
    _add_recording_conversion_arguments(recording_parser)
    recording_parser.add_argument(
        "source_path",
        nargs="?",
        default=DEFAULT_RAW_SESSION_PATH,
        help=(
            "Path to a raw recording session JSON file. "
            f"Default: {DEFAULT_RAW_SESSION_PATH}."
        ),
    )

    script_parser = subparsers.add_parser(
        "script",
        help="Build playback from a script document file.",
        parents=[phase_6_parser],
    )
    script_parser.add_argument(
        "source_path",
        help="Path to a script document text file.",
    )

    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    diagnostic_log_path = _resolve_diagnostic_log_path()
    preview_executor = PreviewInputExecutor()
    demo_live_adapter: _DemoLivePlaybackAdapter | None = None
    traced_live_host: _TracingPlaybackHost | None = None

    try:
        if args.mode == PlaybackMode.LIVE.value:
            if args.demo_live:
                demo_live_adapter = _DemoLivePlaybackAdapter()
                live_host = demo_live_adapter
            else:
                from infrastructure.input.pynput_playback_adapter import (
                    PynputPlaybackAdapter,
                )

                live_host = PynputPlaybackAdapter()
            traced_live_host = _TracingPlaybackHost(live_host) if args.show_events else None
            live_executor = LiveInputExecutor(
                traced_live_host or live_host,
                mouse_settle_ms=args.settle_ms,
            )
        else:
            live_executor = _UnavailableLiveExecutor()

        service = PlaybackService(
            builder=PlaybackBuilder(
                from_script=PlaybackPlanFromScriptBuilder(
                    runtime=ScriptRuntime(
                        default_current_event_delay_ms=args.delay_ms,
                        special_values=_runtime_special_values(args),
                    )
                ),
            ),
            live_engine=PlaybackEngine(live_executor),
            preview_engine=PlaybackEngine(preview_executor),
        )
        document_service = ScriptDocumentService()
        mode = PlaybackMode(args.mode)

        if args.source_kind == "recording":
            session = load_session(args.source_path)
            if args.recording_conversion_mode is None:
                plan = service.build_plan_from_recording(session)
                request = PlaybackRequest(
                    source_kind=plan.source_kind,
                    source_id=plan.source_id,
                    mode=mode,
                    repeat_count=args.repeat,
                    step_mode=args.step,
                    delay_ms=(
                        plan.delay_ms_override
                        if plan.delay_ms_override is not None
                        else args.delay_ms
                    ),
                    sendkeys_transport=_sendkeys_transport_label(bool(args.ass_play)),
                )
                result = service.play_plan(plan, request)
            else:
                if args.recording_conversion_mode == "direct_import":
                    document = document_service.import_recording_session(
                        session,
                        recording_conversion_route="direct_import",
                    )
                else:
                    interpretation_service = InterpretationService(
                        config=build_interpretation_config(args)
                    )
                    shaping_service = ShapingService(
                        config=build_shaping_config(args)
                    )
                    generation_service = ScriptGenerationService(
                        config=build_generation_config(args)
                    )
                    interpreted = interpretation_service.interpret_recording(session)
                    shaped = shaping_service.shape_recording(interpreted)
                    generated = generation_service.generate_script(shaped)
                    document = document_service.promote_generated_script(
                        generated,
                        recording_conversion_route="promote_generated",
                    )

                plan = service.build_plan_from_script(document)
                request = PlaybackRequest(
                    source_kind=plan.source_kind,
                    source_id=plan.source_id,
                    mode=mode,
                    repeat_count=args.repeat,
                    step_mode=args.step,
                    delay_ms=(
                        plan.delay_ms_override
                        if plan.delay_ms_override is not None
                        else args.delay_ms
                    ),
                    sendkeys_transport=_sendkeys_transport_label(bool(args.ass_play)),
                )
                result = service.play_plan(plan, request)
        else:
            document = _load_script_document(args.source_path)
            plan = service.build_plan_from_script(document)
            request = PlaybackRequest(
                source_kind=plan.source_kind,
                source_id=plan.source_id,
                mode=mode,
                repeat_count=args.repeat,
                step_mode=args.step,
                delay_ms=(
                    plan.delay_ms_override
                    if plan.delay_ms_override is not None
                    else args.delay_ms
                ),
                sendkeys_transport=_sendkeys_transport_label(bool(args.ass_play)),
            )
            result = service.play_plan(plan, request)
    except Exception as exc:
        print(f"Playback failed: {exc}", file=sys.stderr)
        return 1

    if diagnostic_log_path is not None:
        print(f"Diagnostics log file   : {diagnostic_log_path}", flush=True)
        print(flush=True)

    if args.source_kind == "recording":
        source_label = f"recording file {resolve_display_path(args.source_path)}"
    else:
        source_label = f"script file {resolve_display_path(args.source_path)}"
    output_label = (
        "preview playback engine"
        if mode == PlaybackMode.PREVIEW
        else "live input host"
    )
    print_input_output(
        input_label="Input source",
        input_value=source_label,
        output_label="Output destination",
        output_value=output_label,
    )

    summary = service.summarize_plan(plan)
    if args.source_kind == "recording":
        print(f"Recording route        : {_recording_route_label(args)}", flush=True)
    print(f"Source kind            : {summary.source_kind}", flush=True)
    print(f"Source ID              : {summary.source_id}", flush=True)
    print(f"Playback mode          : {result.playback_mode or '<unknown>'}", flush=True)
    print(f"SendKeys transport     : {result.sendkeys_transport}", flush=True)
    print(f"Planned event count    : {summary.event_count}", flush=True)
    print(f"Repeat count           : {request.repeat_count}", flush=True)
    print(f"Step mode              : {request.step_mode}", flush=True)
    print(f"Delay per event (ms)   : {request.delay_ms}", flush=True)
    print(f"Mouse settle (ms)      : {args.settle_ms}", flush=True)
    print(f"Executed event count   : {result.executed_event_count}", flush=True)
    print(f"Playback success       : {result.success}", flush=True)
    for line in format_playback_failure(result):
        print(line, flush=True)

    def _print_output_section(title: str, chunks: list[str]) -> None:
        if not chunks:
            return
        print(flush=True)
        print(f"{title}:", flush=True)
        for chunk in normalize_output_chunks(chunks):
            print(chunk, flush=True)

    _print_output_section("Console output", summary.console_output)

    if args.show_events:
        events = (
            preview_executor.executed_events
            if request.mode == PlaybackMode.PREVIEW
            else traced_live_host.calls
            if traced_live_host is not None
            else plan.events
        )
        print(flush=True)
        if result.sendkeys_transport == "key taps":
            print(
                (
                    "Playback events (SendKeys key taps mode):"
                    if request.mode == PlaybackMode.PREVIEW
                    else "Dispatched host calls (SendKeys key taps mode):"
                ),
                flush=True,
            )
        else:
            print(
                "Playback events:" if request.mode == PlaybackMode.PREVIEW else "Dispatched host calls:",
                flush=True,
            )
        for index, event in enumerate(events, start=1):
            payload = (
                json.dumps(playback_event_to_dict(event), sort_keys=True)
                if request.mode == PlaybackMode.PREVIEW
                else json.dumps(event, sort_keys=True)
            )
            print(f"{index:02d}. {payload}", flush=True)

    return 0 if result.success else 1


def _load_script_document(path_text: str) -> ScriptDocument:
    path = Path(path_text).resolve()
    document = ScriptDocumentFileStore().load(path)
    document.document_id = str(path)
    document.source_path = str(path)
    return document


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

