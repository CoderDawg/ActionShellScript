from __future__ import annotations

import argparse
import os
import subprocess
import sys
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Protocol

import tkinter as tk
from tkinter import ttk, messagebox

from core.playback.playback_result import PlaybackResult
from core.playback.playback_result_bus import subscribe_playback_result
from core.playback.playback_result_formatter import format_playback_failure


_DETACHED_ENV_VAR = "ASS_TEST_GUI_V3_DETACHED"


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


class DiagnosticSink(Protocol):
    def write(self, event: DiagnosticEvent) -> None: ...


class StdoutDiagnosticSink:
    def __init__(self, *, timestamp_format: DiagnosticTimestampFormat) -> None:
        self._timestamp_format = timestamp_format

    def write(self, event: DiagnosticEvent) -> None:
        try:
            print(format_diagnostic_event(event, timestamp_format=self._timestamp_format))
        except Exception:
            pass


class FileDiagnosticSink:
    def __init__(self, path: Path, *, timestamp_format: DiagnosticTimestampFormat) -> None:
        self._path = Path(path)
        self._timestamp_format = timestamp_format

    def write(self, event: DiagnosticEvent) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(format_diagnostic_event(event, timestamp_format=self._timestamp_format))
                handle.write("\n")
        except Exception:
            pass


_diagnostic_config = DiagnosticConfig()
_diagnostic_lock = threading.RLock()


def _format_timestamp(event: DiagnosticEvent, timestamp_format: DiagnosticTimestampFormat) -> str:
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
        text += f" fields={json.dumps(event.fields, sort_keys=True, default=str)}"

    return text


def set_diagnostic_config(config: DiagnosticConfig) -> None:
    global _diagnostic_config
    with _diagnostic_lock:
        _diagnostic_config = DiagnosticConfig(
            enabled=bool(config.enabled),
            min_severity=DiagnosticSeverity(config.min_severity),
            max_detail=DiagnosticDetail(config.max_detail),
            timestamp_format=DiagnosticTimestampFormat(config.timestamp_format),
            log_to_stdout=bool(config.log_to_stdout),
            log_to_file=bool(config.log_to_file),
            log_path=Path(config.log_path) if config.log_path is not None else None,
        )


def get_diagnostic_config() -> DiagnosticConfig:
    with _diagnostic_lock:
        return _diagnostic_config


def diagnostics_enabled() -> bool:
    return get_diagnostic_config().enabled


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
    return True


def _default_log_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"actionshellscript_diagnostics_Test_GUI_V3_{stamp}.log"
    #return Path(__file__).resolve().with_name(filename)
    return Path(tempfile.gettempdir()) / filename


def _build_sinks(config: DiagnosticConfig) -> list[DiagnosticSink]:
    sinks: list[DiagnosticSink] = []
    if config.log_to_stdout:
        sinks.append(StdoutDiagnosticSink(timestamp_format=config.timestamp_format))
    if config.log_to_file:
        sinks.append(FileDiagnosticSink(config.log_path or _default_log_path(), timestamp_format=config.timestamp_format))
    return sinks


def emit_diagnostic_event(event: DiagnosticEvent) -> None:
    try:
        config = get_diagnostic_config()
        if not _should_emit(config, event):
            return
        for sink in _build_sinks(config):
            sink.write(event)
    except Exception:
        return


class DiagnosticLogger:
    def __init__(self, subsystem: str) -> None:
        self.subsystem = (subsystem or "general").strip() or "general"

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

    def debug(self, message: str, *, detail: DiagnosticDetail = DiagnosticDetail.SUMMARY, event_id: str | None = None, category: str | None = None, **fields: object) -> None:
        self.emit(message, severity=DiagnosticSeverity.DEBUG, detail=detail, event_id=event_id, category=category, **fields)

    def info(self, message: str, *, detail: DiagnosticDetail = DiagnosticDetail.SUMMARY, event_id: str | None = None, category: str | None = None, **fields: object) -> None:
        self.emit(message, severity=DiagnosticSeverity.INFO, detail=detail, event_id=event_id, category=category, **fields)

    def warning(self, message: str, *, detail: DiagnosticDetail = DiagnosticDetail.ESSENTIAL, event_id: str | None = None, category: str | None = None, **fields: object) -> None:
        self.emit(message, severity=DiagnosticSeverity.WARNING, detail=detail, event_id=event_id, category=category, **fields)

    def error(self, message: str, *, detail: DiagnosticDetail = DiagnosticDetail.ESSENTIAL, event_id: str | None = None, category: str | None = None, **fields: object) -> None:
        self.emit(message, severity=DiagnosticSeverity.ERROR, detail=detail, event_id=event_id, category=category, **fields)


def format_playback_status_lines(result: PlaybackResult) -> list[str]:
    lines = [
        f"Playback success       : {result.success}",
        f"Executed event count   : {result.executed_event_count}",
    ]
    lines.extend(format_playback_failure(result))
    return lines


class GUITestApp:
    def __init__(self, root, *, diagnostic_logger=None):
        self.root = root
        self.root.title("GUI Test Application")
        self.service_logger = DiagnosticLogger("playback_service")
        self.runtime_logger = DiagnosticLogger("script_runtime")
        self.engine_logger = diagnostic_logger or DiagnosticLogger("playback_engine")
        self._playback_result_unsubscribe = None
        
        # Variable for the "always on top" checkbox
        self.always_on_top = tk.BooleanVar(value=True)
        self.root.attributes('-topmost', True)
        
        # Variable for the slider
        self.slider_value = tk.DoubleVar(value=50)
        
        # Variables for keyboard testing
        self.last_key_pressed = tk.StringVar(value="None")
        self.key_press_count = 0
        
        # Variables for multi-selection elements
        self.combo_var = tk.StringVar(value="Select an option...")
        self.radio_var = tk.StringVar(value="option1")
        self.listbox_selections = []
        
        # Counter for double-clicks
        self.double_click_count = 0
        
        self.create_widgets()
        self._playback_result_unsubscribe = subscribe_playback_result(
            self.update_playback_status
        )
        self.setup_keyboard_events()
        self.create_context_menu()
        self.set_initial_window_size()
        self.log_event(
            "Building GUI playback plan from script authority",
            subsystem="playback_service",
            event_id="playback.plan.gui.build",
            source_id=str(Path(__file__).resolve()),
            source_kind="script_document",
            window_title="GUI Test Application",
        )

    def log_event(
        self,
        message,
        *,
        subsystem="playback_engine",
        severity=DiagnosticSeverity.INFO,
        detail=DiagnosticDetail.SUMMARY,
        event_id=None,
        category=None,
        **fields,
    ):
        logger = {
            "playback_service": self.service_logger,
            "script_runtime": self.runtime_logger,
            "playback_engine": self.engine_logger,
        }.get(subsystem, self.engine_logger)
        logger.emit(
            message,
            severity=severity,
            detail=detail,
            event_id=event_id,
            category=category,
            **fields,
        )
        
    def create_widgets(self):
        # Create main scrollable frame
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Main content frame
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Text area with scrollbars
        text_label = ttk.Label(main_frame, text="Text Area (with scrollbars):")
        text_label.pack(anchor="w", pady=(0, 5))
        
        # Create text area with explicit scrollbars
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.text_area = tk.Text(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=8,
            font=('Arial', 10)
        )
        
        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=v_scrollbar.set)
        
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text_area.xview)
        self.text_area.configure(xscrollcommand=h_scrollbar.set)
        
        # Pack the text widget and scrollbars
        self.text_area.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        
        # Add some sample text
        self.text_area.insert(tk.END, "This is a sample text area with both horizontal and vertical scrollbars.\n\n")
        self.text_area.insert(tk.END, "You can type and edit text here. Try typing a very long line to see the horizontal scrollbar in action when word wrap is disabled.\n\n")
        self.text_area.insert(tk.END, "Add more lines to see the vertical scrollbar.\n" * 10)
        
        # Add right-click context menu to text area
        self.text_area.bind("<Button-3>", self.show_context_menu)
        
        # Drag and drop area
        drag_frame = ttk.LabelFrame(main_frame, text="Drag & Drop Area", padding="10")
        drag_frame.pack(fill="x", pady=(0, 10))
        
        self.drag_label = ttk.Label(
            drag_frame, 
            text="Drag this text around!\nClick and drag to move.",
            background="lightblue",
            relief="raised",
            padding="10"
        )
        self.drag_label.pack(pady=10)
        
        # Make the label draggable and double-clickable
        self.drag_label.bind("<Button-1>", self.start_drag)
        self.drag_label.bind("<B1-Motion>", self.on_drag)
        self.drag_label.bind("<Double-Button-1>", self.on_double_click)
        self.drag_label.bind("<Button-3>", self.show_context_menu)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 10))
        
        # Clear text button
        clear_btn = ttk.Button(button_frame, text="Clear Text", command=self.clear_text)
        clear_btn.pack(side="left", padx=(0, 10))
        
        # Message box button
        msg_btn = ttk.Button(button_frame, text="Show Message", command=self.show_message)
        msg_btn.pack(side="left", padx=(0, 10))
        
        # Exit button
        exit_btn = ttk.Button(button_frame, text="Exit", command=self.exit_app)
        exit_btn.pack(side="left")
        
        # Checkbox for "always on top"
        self.always_on_top_cb = ttk.Checkbutton(
            main_frame, 
            text="Keep window on top", 
            variable=self.always_on_top,
            command=self.toggle_always_on_top
        )
        self.always_on_top_cb.pack(anchor="w", pady=(0, 10))
        
        # Slider with tooltip
        slider_frame = ttk.Frame(main_frame)
        slider_frame.pack(fill="x", pady=(0, 10))
        
        slider_label = ttk.Label(slider_frame, text="Volume/Zoom Slider:")
        slider_label.pack(anchor="w")
        
        slider_container = ttk.Frame(slider_frame)
        slider_container.pack(fill="x", pady=(5, 0))
        
        self.slider = ttk.Scale(
            slider_container, 
            from_=0, 
            to=100, 
            orient=tk.HORIZONTAL,
            variable=self.slider_value,
            command=self.update_slider_tooltip
        )
        self.slider.pack(side="left", fill="x", expand=True)
        
        # Tooltip label for slider
        self.slider_tooltip = ttk.Label(slider_container, text="Value: 50")
        self.slider_tooltip.pack(side="right", padx=(10, 0))
        
        # Bind mouse events for hover tooltip effect
        self.slider.bind("<Enter>", self.show_slider_tooltip)
        self.slider.bind("<Leave>", self.hide_slider_tooltip)
        
        # Double-click test area
        double_click_frame = ttk.LabelFrame(main_frame, text="Double-Click Test Area", padding="10")
        double_click_frame.pack(fill="x", pady=(0, 10))
        
        self.double_click_label = ttk.Label(
            double_click_frame,
            text="Double-click me to test!\nClick count: 0",
            background="lightgreen",
            relief="raised",
            padding="10"
        )
        self.double_click_label.pack(pady=10)
        
        # Bind double-click event
        self.double_click_label.bind("<Double-Button-1>", self.on_double_click_test)
        
        # Keyboard testing area
        keyboard_frame = ttk.LabelFrame(main_frame, text="Keyboard Event Testing", padding="10")
        keyboard_frame.pack(fill="x", pady=(0, 10))
        
        # Instructions
        kb_instruction = ttk.Label(keyboard_frame, text="Click in the window and press any key (try Ctrl+S, F1, Escape, etc.):")
        kb_instruction.pack(anchor="w", pady=(0, 5))
        
        # Key display container
        key_container = ttk.Frame(keyboard_frame)
        key_container.pack(fill="x")
        
        # Display last key pressed
        self.key_display = ttk.Label(
            key_container,
            textvariable=self.last_key_pressed,
            background="lightyellow",
            relief="sunken",
            padding="5",
            font=('Arial', 10, 'bold')
        )
        self.key_display.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Key press counter
        self.key_counter_label = ttk.Label(key_container, text="Keys pressed: 0")
        self.key_counter_label.pack(side="right")
        
        # Multi-selection elements frame
        multi_frame = ttk.LabelFrame(main_frame, text="Multi-Selection Elements", padding="15")
        multi_frame.pack(fill="x", pady=(0, 10))
        
        # Create three columns for multi-selection elements
        multi_container = ttk.Frame(multi_frame)
        multi_container.pack(fill="both", expand=True)
        
        # Listbox with multiple selection
        listbox_frame = ttk.Frame(multi_container)
        listbox_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))
        
        listbox_label = ttk.Label(listbox_frame, text="Multi-Select Listbox:")
        listbox_label.pack(anchor="w", pady=(0, 5))
        
        # Create listbox with scrollbar
        listbox_container = ttk.Frame(listbox_frame)
        listbox_container.pack(fill="both", expand=True)
        
        self.listbox = tk.Listbox(
            listbox_container,
            selectmode=tk.EXTENDED,  # Allow multiple selections
            height=8,
            width=20
        )
        scrollbar_lb = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar_lb.set)
        
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar_lb.pack(side="right", fill="y")
        
        # Populate listbox
        listbox_items = [
            "Apple", "Banana", "Cherry", "Date", "Elderberry",
            "Fig", "Grape", "Honeydew", "Kiwi", "Lemon",
            "Mango", "Orange", "Papaya", "Quince", "Raspberry"
        ]
        for item in listbox_items:
            self.listbox.insert(tk.END, item)
            
        # Bind selection event
        self.listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        
        # Button to show selections
        show_selections_btn = ttk.Button(listbox_frame, text="Show Selections", command=self.show_listbox_selections)
        show_selections_btn.pack(pady=(10, 0))
        
        # Combobox/dropdown menu
        combo_frame = ttk.Frame(multi_container)
        combo_frame.pack(side="left", fill="both", expand=True, padx=(7, 7))
        
        combo_label = ttk.Label(combo_frame, text="Combobox/Dropdown:")
        combo_label.pack(anchor="w", pady=(0, 5))
        
        self.combobox = ttk.Combobox(
            combo_frame,
            textvariable=self.combo_var,
            values=[
                "Select a language...",
                "Python", "JavaScript", "Java", "C++", "C#",
                "Go", "Rust", "Swift", "Kotlin", "TypeScript"
            ],
            state="readonly",  # Prevents typing, dropdown only
            width=20
        )
        self.combobox.pack(fill="x", pady=(0, 10))
        self.combobox.bind('<<ComboboxSelected>>', self.on_combo_select)
        
        # Button to show combo selection
        show_combo_btn = ttk.Button(combo_frame, text="Show Selection", command=self.show_combo_selection)
        show_combo_btn.pack(pady=(5, 10))
        
        # Create editable combobox
        combo_label2 = ttk.Label(combo_frame, text="Editable Combobox:")
        combo_label2.pack(anchor="w", pady=(0, 5))
        
        self.combo_var2 = tk.StringVar(value="Type or select...")
        self.combobox2 = ttk.Combobox(
            combo_frame,
            textvariable=self.combo_var2,
            values=["Custom Option 1", "Custom Option 2", "Custom Option 3"],
            width=20
        )
        self.combobox2.pack(fill="x")
        
        # Radio buttons group
        radio_frame = ttk.Frame(multi_container)
        radio_frame.pack(side="left", fill="both", expand=True, padx=(15, 0))
        
        radio_label = ttk.Label(radio_frame, text="Radio Button Group:")
        radio_label.pack(anchor="w", pady=(0, 5))
        
        # Create radio buttons
        self.radio1 = ttk.Radiobutton(
            radio_frame,
            text="Option 1: Fast",
            variable=self.radio_var,
            value="option1",
            command=self.on_radio_select
        )
        self.radio1.pack(anchor="w", pady=3)
        
        self.radio2 = ttk.Radiobutton(
            radio_frame,
            text="Option 2: Reliable",
            variable=self.radio_var,
            value="option2",
            command=self.on_radio_select
        )
        self.radio2.pack(anchor="w", pady=3)
        
        self.radio3 = ttk.Radiobutton(
            radio_frame,
            text="Option 3: Cheap",
            variable=self.radio_var,
            value="option3",
            command=self.on_radio_select
        )
        self.radio3.pack(anchor="w", pady=3)
        
        self.radio4 = ttk.Radiobutton(
            radio_frame,
            text="Option 4: All of the above",
            variable=self.radio_var,
            value="option4",
            command=self.on_radio_select
        )
        self.radio4.pack(anchor="w", pady=3)
        
        # Button to show radio selection
        show_radio_btn = ttk.Button(radio_frame, text="Show Selection", command=self.show_radio_selection)
        show_radio_btn.pack(pady=(15, 0))
        
        # Status display for multi-selection elements
        status_frame = ttk.Frame(multi_frame)
        status_frame.pack(fill="x", pady=(15, 0))
        
        status_label = ttk.Label(status_frame, text="Selection Status:")
        status_label.pack(anchor="w", pady=(0, 5))
        
        self.selection_status = tk.Text(
            status_frame,
            height=4,
            wrap=tk.WORD,
            font=('Arial', 9),
            bg="lightyellow"
        )
        self.selection_status.pack(fill="x", pady=(0, 0))

        playback_status_frame = ttk.Frame(multi_frame)
        playback_status_frame.pack(fill="x", pady=(15, 0))

        playback_status_label = ttk.Label(playback_status_frame, text="Playback Status:")
        playback_status_label.pack(anchor="w", pady=(0, 5))

        self.playback_status = tk.Text(
            playback_status_frame,
            height=4,
            wrap=tk.WORD,
            font=('Arial', 9),
            bg="lightyellow"
        )
        self.playback_status.pack(fill="x", pady=(0, 0))
        self.playback_status.insert(
            1.0,
            "Playback status will appear here when a playback result is available.",
        )
        
        # Initial status
        self.update_selection_status()
        self.log_event(
            "GUI widgets created",
            subsystem="playback_service",
            event_id="playback.service.widgets.created",
            source_id=str(Path(__file__).resolve()),
            source_kind="script_document",
            text_area_lines=int(self.text_area.index("end-1c").split(".")[0]),
            listbox_items=self.listbox.size(),
        )
        
    def start_drag(self, event):
        # Record the starting position
        self.start_x = event.x
        self.start_y = event.y
        self.log_event(
            "Drag started",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.drag.start",
            widget=str(event.widget),
            x=event.x,
            y=event.y,
        )
        
    def on_drag(self, event):
        # Calculate the distance moved
        x = self.drag_label.winfo_x() - self.start_x + event.x
        y = self.drag_label.winfo_y() - self.start_y + event.y
        
        # Move the label (using place for positioning)
        self.drag_label.place(x=x, y=y)
        self.log_event(
            "Drag moved",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.drag.move",
            widget=str(event.widget),
            x=x,
            y=y,
            detail=DiagnosticDetail.TRACE,
        )
        
    def on_double_click(self, event):
        """Handle double-click on draggable label"""
        self.log_event(
            "Draggable label double-clicked",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.double_click",
            widget=str(event.widget),
            x=event.x,
            y=event.y,
        )
        messagebox.showinfo("Double-Click Detected", "You double-clicked the draggable label!")
        
    def on_double_click_test(self, event):
        """Handle double-click on the test area"""
        self.double_click_count += 1
        self.double_click_label.config(text=f"Double-click me to test!\nClick count: {self.double_click_count}")
        self.log_event(
            "Double-click test label activated",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.double_click",
            click_count=self.double_click_count,
            widget=str(event.widget),
        )
        
        # Show a message every 5 double-clicks
        if self.double_click_count % 5 == 0:
            messagebox.showinfo("Milestone!", f"You've double-clicked {self.double_click_count} times!")
        
    def clear_text(self):
        """Clear all text from the text area"""
        current_text = self.text_area.get("1.0", tk.END)
        self.log_event(
            "Text area cleared",
            subsystem="playback_engine",
            event_id="playback.engine.text.clear",
            previous_char_count=max(0, len(current_text.rstrip("\n"))),
        )
        self.text_area.delete(1.0, tk.END)
        
    def show_message(self):
        """Show a message box"""
        self.log_event("Message dialog requested", subsystem="playback_engine", event_id="playback.engine.dialog.show_message")
        messagebox.showinfo("Test Message", "This is a test message box!\nClick OK to close.")
        
    def exit_app(self):
        """Exit the application"""
        self.log_event("Application exit requested", subsystem="playback_engine", event_id="playback.engine.app.exit")
        if self._playback_result_unsubscribe is not None:
            self._playback_result_unsubscribe()
            self._playback_result_unsubscribe = None
        self.root.quit()
        self.root.destroy()
        
    def toggle_always_on_top(self):
        """Toggle the always on top setting"""
        value = self.always_on_top.get()
        self.root.attributes('-topmost', value)
        self.log_event(
            "Window topmost toggled",
            subsystem="playback_engine",
            event_id="playback.engine.window.topmost.toggle",
            enabled=bool(value),
        )
        
    def update_slider_tooltip(self, value):
        """Update the slider tooltip with current value"""
        numeric_value = int(float(value))
        self.slider_tooltip.config(text=f"Value: {numeric_value}")
        self.log_event(
            "Slider value updated",
            subsystem="script_runtime",
            event_id="runtime.input.slider.change",
            value=numeric_value,
            detail=DiagnosticDetail.TRACE,
        )
        
    def show_slider_tooltip(self, event):
        """Show enhanced tooltip on hover"""
        current_value = int(self.slider_value.get())
        self.slider_tooltip.config(text=f"Value: {current_value} (0-100)")
        self.log_event(
            "Slider hover entered",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.enter",
            widget=str(event.widget),
            value=current_value,
            detail=DiagnosticDetail.TRACE,
        )
        
    def hide_slider_tooltip(self, event):
        """Hide enhanced tooltip"""
        current_value = int(self.slider_value.get())
        self.slider_tooltip.config(text=f"Value: {current_value}")
        self.log_event(
            "Slider hover exited",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.leave",
            widget=str(event.widget),
            value=current_value,
            detail=DiagnosticDetail.TRACE,
        )
        
    def on_listbox_select(self, event):
        """Handle listbox selection changes"""
        selection = self.listbox.curselection()
        self.listbox_selections = [self.listbox.get(i) for i in selection]
        self.log_event(
            "Listbox selection changed",
            subsystem="playback_engine",
            event_id="playback.engine.selection.listbox.changed",
            selected_items=self.listbox_selections,
            selected_count=len(self.listbox_selections),
        )
        self.update_selection_status()
        
    def show_listbox_selections(self):
        """Show current listbox selections"""
        self.log_event(
            "Listbox selection summary requested",
            subsystem="playback_engine",
            event_id="playback.engine.action.listbox.show_selections",
            selected_count=len(self.listbox_selections),
        )
        if self.listbox_selections:
            selections_text = "\n".join([f"• {item}" for item in self.listbox_selections])
            messagebox.showinfo("Listbox Selections", f"Selected items ({len(self.listbox_selections)}):\n\n{selections_text}")
        else:
            messagebox.showinfo("Listbox Selections", "No items selected.\n\nTip: Hold Ctrl and click to select multiple items,\nor hold Shift and click to select a range.")
            
    def on_combo_select(self, event):
        """Handle combobox selection"""
        self.log_event(
            "Combobox selection changed",
            subsystem="playback_engine",
            event_id="playback.engine.selection.combobox.changed",
            value=self.combo_var.get(),
        )
        self.update_selection_status()
        
    def show_combo_selection(self):
        """Show current combobox selection"""
        selection = self.combo_var.get()
        self.log_event(
            "Combobox selection summary requested",
            subsystem="playback_engine",
            event_id="playback.engine.action.combobox.show_selection",
            value=selection,
        )
        messagebox.showinfo("Combobox Selection", f"Selected: {selection}")
        
    def on_radio_select(self):
        """Handle radio button selection"""
        self.log_event(
            "Radio selection changed",
            subsystem="playback_engine",
            event_id="playback.engine.selection.radio.changed",
            value=self.radio_var.get(),
        )
        self.update_selection_status()
        
    def show_radio_selection(self):
        """Show current radio button selection"""
        selection = self.radio_var.get()
        self.log_event(
            "Radio selection summary requested",
            subsystem="playback_engine",
            event_id="playback.engine.action.radio.show_selection",
            value=selection,
        )
        option_text = {
            "option1": "Option 1: Fast",
            "option2": "Option 2: Reliable", 
            "option3": "Option 3: Cheap",
            "option4": "Option 4: All of the above"
        }
        messagebox.showinfo("Radio Button Selection", f"Selected: {option_text.get(selection, selection)}")
        
    def update_selection_status(self):
        """Update the selection status display"""
        self.selection_status.delete(1.0, tk.END)
        
        # Listbox status
        if self.listbox_selections:
            listbox_text = f"Listbox: {len(self.listbox_selections)} items selected ({', '.join(self.listbox_selections[:3])}{'...' if len(self.listbox_selections) > 3 else ''})"
        else:
            listbox_text = "Listbox: No selections"
            
        # Combobox status
        combo_text = f"Combobox: {self.combo_var.get()}"
        
        # Radio button status
        radio_options = {
            "option1": "Fast",
            "option2": "Reliable",
            "option3": "Cheap", 
            "option4": "All of the above"
        }
        radio_text = f"Radio: {radio_options.get(self.radio_var.get(), 'None')}"
        
        status_text = f"{listbox_text}\n{combo_text}\n{radio_text}"
        self.selection_status.insert(1.0, status_text)
        self.log_event(
            "Selection status updated",
            subsystem="playback_engine",
            event_id="playback.engine.state.selection_status.updated",
            listbox_selection_count=len(self.listbox_selections),
            combo_value=self.combo_var.get(),
            radio_value=self.radio_var.get(),
            detail=DiagnosticDetail.TRACE,
        )

    def update_playback_status(self, result: PlaybackResult):
        """Update the playback status display using the shared failure formatter."""
        self.playback_status.delete(1.0, tk.END)
        self.playback_status.insert(1.0, "\n".join(format_playback_status_lines(result)))
        self.log_event(
            "Playback status updated",
            subsystem="playback_service",
            event_id="playback.service.state.playback_status.updated",
            success=bool(result.success),
            executed_event_count=int(result.executed_event_count),
            error_line=result.error_line,
            detail=DiagnosticDetail.TRACE,
        )
        
    def setup_keyboard_events(self):
        """Set up keyboard event bindings"""
        # Bind to the main window to capture all key events
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind_all('<Button-1>', self.on_mouse_click, add='+')
        self.root.bind('<Control-s>', self.on_ctrl_s)
        self.root.bind('<Control-S>', self.on_ctrl_s)
        self.root.bind('<F1>', self.on_f1)
        self.root.bind('<Escape>', self.on_escape)
        self.root.bind('<Control-q>', self.on_ctrl_q)
        self.root.bind('<Control-Q>', self.on_ctrl_q)
        
        # Make sure the window can receive focus
        self.root.focus_set()
        self.log_event(
            "Keyboard and mouse bindings configured",
            subsystem="playback_service",
            event_id="playback.service.bindings.ready",
        )

    def on_mouse_click(self, event):
        """Log pointer clicks across the UI."""
        self.log_event(
            "Mouse click detected",
            subsystem="script_runtime",
            event_id="runtime.input.mouse.click",
            widget=str(event.widget),
            x=event.x,
            y=event.y,
            root_x=event.x_root,
            root_y=event.y_root,
            detail=DiagnosticDetail.TRACE,
        )
        
    def on_key_press(self, event):
        """Handle general key press events"""
        self.key_press_count += 1
        
        # Format the key information
        key_info = f"Key: '{event.keysym}'"
        if event.state & 0x4:  # Ctrl key
            key_info += " + Ctrl"
        if event.state & 0x8:  # Alt key
            key_info += " + Alt"
        if event.state & 0x1:  # Shift key
            key_info += " + Shift"

        self.last_key_pressed.set(key_info)
        self.key_counter_label.config(text=f"Keys pressed: {self.key_press_count}")
        self.log_event(
            "Key press detected",
            subsystem="script_runtime",
            event_id="runtime.input.keyboard.key_press",
            widget=str(event.widget),
            keysym=event.keysym,
            keycode=event.keycode,
            char=event.char,
            state=event.state,
            key_info=key_info,
            detail=DiagnosticDetail.TRACE,
        )
        
    def on_ctrl_s(self, event):
        """Handle Ctrl+S shortcut"""
        self.log_event(
            "Ctrl+S shortcut detected",
            subsystem="script_runtime",
            event_id="runtime.input.keyboard.shortcut.ctrl_s",
            widget=str(event.widget),
        )
        messagebox.showinfo("Keyboard Shortcut", "Ctrl+S pressed!\nThis could trigger a 'Save' action.")
        return "break"  # Prevent default behavior
        
    def on_f1(self, event):
        """Handle F1 key (Help)"""
        self.log_event("F1 shortcut detected", subsystem="script_runtime", event_id="runtime.input.keyboard.shortcut.f1", widget=str(event.widget))
        help_text = """GUI Test Application - Help

Keyboard Shortcuts:
• Ctrl+S: Save action (demo)
• F1: Show this help
• Escape: Focus main window
• Ctrl+Q: Quick exit

Mouse Actions:
• Right-click: Context menu
• Double-click: Various actions
• Drag: Move blue label

Features:
• Text editing with scrollbars
• Drag and drop
• Button controls
• Checkbox and slider
• Keyboard and mouse event testing
• Multi-selection elements"""
        messagebox.showinfo("Help - F1", help_text)
        return "break"
        
    def on_escape(self, event):
        """Handle Escape key"""
        self.root.focus_set()
        self.log_event("Escape shortcut detected", subsystem="script_runtime", event_id="runtime.input.keyboard.shortcut.escape", widget=str(event.widget))
        messagebox.showinfo("Escape Key", "Escape pressed!\nWindow focus reset.")
        return "break"
        
    def on_ctrl_q(self, event):
        """Handle Ctrl+Q shortcut for quick exit"""
        self.log_event("Ctrl+Q shortcut detected", subsystem="script_runtime", event_id="runtime.input.keyboard.shortcut.ctrl_q", widget=str(event.widget))
        if messagebox.askyesno("Quick Exit", "Exit application? (Ctrl+Q)"):
            self.exit_app()
        return "break"
        
    def create_context_menu(self):
        """Create the right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_text)
        self.context_menu.add_command(label="Paste", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self.select_all_text)
        self.context_menu.add_command(label="Clear", command=self.clear_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Insert Sample Text", command=self.insert_sample_text)
        self.context_menu.add_command(label="Show Info", command=self.show_context_info)
        self.log_event("Context menu created", subsystem="playback_service", event_id="playback.service.context_menu.created")
        
    def show_context_menu(self, event):
        """Show the context menu at mouse position"""
        self.log_event(
            "Context menu opened",
            subsystem="playback_service",
            event_id="playback.service.context_menu.open",
            widget=str(event.widget),
            x=event.x_root,
            y=event.y_root,
        )
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
            
    def copy_text(self):
        """Copy selected text to clipboard"""
        try:
            self.root.clipboard_clear()
            selected_text = self.text_area.selection_get()
            self.root.clipboard_append(selected_text)
            self.log_event(
                "Text copied to clipboard",
                subsystem="playback_engine",
                event_id="playback.engine.action.copy",
                selected_char_count=len(selected_text),
            )
            messagebox.showinfo("Copy", f"Copied {len(selected_text)} characters to clipboard")
        except tk.TclError:
            self.log_event("Copy requested with no text selected", subsystem="playback_engine", event_id="playback.engine.action.copy.empty", severity=DiagnosticSeverity.WARNING)
            messagebox.showwarning("Copy", "No text selected")
            
    def paste_text(self):
        """Paste text from clipboard"""
        try:
            clipboard_text = self.root.clipboard_get()
            self.text_area.insert(tk.INSERT, clipboard_text)
            self.log_event(
                "Text pasted from clipboard",
                subsystem="playback_engine",
                event_id="playback.engine.action.paste",
                pasted_char_count=len(clipboard_text),
            )
            messagebox.showinfo("Paste", f"Pasted {len(clipboard_text)} characters from clipboard")
        except tk.TclError:
            self.log_event("Paste requested with empty clipboard", subsystem="playback_engine", event_id="playback.engine.action.paste.empty", severity=DiagnosticSeverity.WARNING)
            messagebox.showwarning("Paste", "Nothing to paste")
            
    def select_all_text(self):
        """Select all text in the text area"""
        self.log_event("Select all requested", subsystem="playback_engine", event_id="playback.engine.action.select_all")
        self.text_area.tag_add(tk.SEL, "1.0", tk.END)
        self.text_area.mark_set(tk.INSERT, "1.0")
        self.text_area.see(tk.INSERT)
        
    def insert_sample_text(self):
        """Insert sample text at cursor position"""
        sample_text = "\n--- Sample text inserted via context menu ---\n"
        self.text_area.insert(tk.INSERT, sample_text)
        self.log_event(
            "Sample text inserted",
            subsystem="playback_engine",
            event_id="playback.engine.action.insert_sample_text",
            inserted_char_count=len(sample_text),
        )
        
    def show_context_info(self):
        """Show information about the context menu"""
        self.log_event("Context menu info requested", subsystem="playback_service", event_id="playback.service.context_menu.info_requested")
        messagebox.showinfo("Context Menu Info", "This is a right-click context menu!\n\nTry right-clicking on:\n• The text area\n• The draggable label\n\nFeatures:\n• Copy/Paste functionality\n• Text selection\n• Custom actions")

    def set_initial_window_size(self):
        """Open the window large enough to fit the interface without going fullscreen."""
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Keep the window comfortably wide, but much narrower than fullscreen.
        width = min(max(760, int(screen_width * 0.40)), screen_width - 120)
        height = min(max(950, int(screen_height * 0.86)), screen_height - 140)

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.root.state("normal")
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.log_event(
            "Initial window size applied",
            subsystem="playback_service",
            event_id="playback.service.window.initial_size",
            screen_width=screen_width,
            screen_height=screen_height,
            window_width=width,
            window_height=height,
            window_x=x,
            window_y=y,
        )

def parse_args():
    parser = argparse.ArgumentParser(description="GUI test application with optional diagnostics.")
    parser.add_argument(
        "--diagnostic-logging",
        action="store_true",
        help="Enable structured diagnostic logging to a file.",
    )
    parser.add_argument(
        "--diagnostic-log-path",
        default=None,
        help="Write diagnostics to this file path instead of the default log name.",
    )
    parser.add_argument(
        "--diagnostic-stdout",
        action="store_true",
        help="Mirror diagnostic events to stdout as well as the log file.",
    )
    return parser.parse_args()


def build_diagnostic_config(args) -> DiagnosticConfig:
    enabled = bool(args.diagnostic_logging or args.diagnostic_stdout)
    if not enabled:
        return DiagnosticConfig(
            enabled=False,
            log_to_file=bool(args.diagnostic_log_path),
            log_path=(
                Path(args.diagnostic_log_path).expanduser().resolve()
                if args.diagnostic_log_path
                else None
            ),
        )

    log_path = (
        Path(args.diagnostic_log_path).expanduser().resolve()
        if args.diagnostic_log_path
        else _default_log_path()
    )
    return DiagnosticConfig(
        enabled=True,
        log_to_stdout=bool(args.diagnostic_stdout),
        log_to_file=True,
        log_path=log_path,
    )


def _announce_diagnostic_destination() -> None:
    config = get_diagnostic_config()
    if not config.enabled:
        return

    log_path = config.log_path or _default_log_path()
    print(f"Diagnostics log file   : {log_path}", flush=True)
    print(flush=True)


def _run_application(args) -> int:
    set_diagnostic_config(build_diagnostic_config(args))

    startup_logger = DiagnosticLogger("playback_service")
    source_path = Path(__file__).resolve()
    source_text = source_path.read_text(encoding="utf-8")
    if diagnostics_enabled():
        startup_logger.info(
            "Structured diagnostics enabled",
            event_id="playback.service.diagnostics.enabled",
            log_to_file=True,
            log_to_stdout=get_diagnostic_config().log_to_stdout,
            log_path=str(get_diagnostic_config().log_path or _default_log_path()),
        )

    startup_logger.info(
        "Building GUI playback plan from script authority",
        event_id="playback.plan.gui.build",
        source_id=str(source_path),
        source_kind="script_document",
    )
    startup_logger.info(
        "Runtime execution started",
        subsystem="script_runtime",
        event_id="runtime.execute.start",
        debugger_attached=False,
        source_length=len(source_text),
    )
    root = tk.Tk()
    app = GUITestApp(root, diagnostic_logger=startup_logger)
    startup_logger.info(
        "Runtime execution completed",
        subsystem="script_runtime",
        event_id="runtime.execute.completed",
        diagnostic_count=0,
        emitted_event_count=0,
        script_exit_code=0,
    )
    startup_logger.info(
        "Built GUI playback plan from script authority",
        event_id="playback.plan.gui.built",
        event_count=0,
        source_id=str(source_path),
        source_kind="script_document",
    )
    startup_logger.info(
        "Executing GUI playback plan",
        event_id="playback.execute.request",
        event_count=0,
        mode="live",
        repeat_count=1,
        source_id=str(source_path),
        source_kind="script_document",
    )
    startup_logger.info(
        "GUI engine starting execution",
        subsystem="playback_engine",
        event_id="playback.engine.start",
        delay_ms=0,
        event_count=0,
        repeat_count=1,
        source_id=str(source_path),
        source_kind="script_document",
        step_mode=False,
    )
    startup_logger.info(
        "GUI engine finished execution successfully",
        subsystem="playback_engine",
        event_id="playback.engine.success",
        executed_event_count=0,
        source_id=str(source_path),
        source_kind="script_document",
    )
    startup_logger.info(
        "GUI playback plan executed successfully",
        event_id="playback.execute.success",
        executed_event_count=0,
        source_id=str(source_path),
        source_kind="script_document",
    )
    root.mainloop()
    return 0


def _launch_detached(argv: list[str]) -> int:
    env = os.environ.copy()
    env[_DETACHED_ENV_VAR] = "1"

    launcher = sys.executable
    if os.name == "nt":
        launcher = shutil.which("pythonw.exe") or shutil.which("pythonw") or launcher

    kwargs: dict[str, object] = {
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    subprocess.Popen([launcher, str(Path(__file__).resolve()), *argv], **kwargs)
    return 0


def main():
    args = parse_args()
    config = build_diagnostic_config(args)

    if os.getenv(_DETACHED_ENV_VAR) != "1":
        if config.enabled:
            set_diagnostic_config(config)
            _announce_diagnostic_destination()
        return _launch_detached(sys.argv[1:])

    return _run_application(args)

if __name__ == "__main__":
    main()
