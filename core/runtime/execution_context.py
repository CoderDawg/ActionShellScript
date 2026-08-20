"""
Runtime execution context.
**COPIED FROM**
packages/app_core/runtime/execution_context.py  
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from core.debugging.breakpoints import BreakpointSet
from core.debugging.call_stack import CallFrame, CallStack
from core.runtime.external_values import ExternalFunctionBinding
from core.runtime.struct_values import StructDefinition
from core.runtime.struct_values import RecordDefinition
from core.runtime.struct_values import clone_runtime_value

from .runtime_errors import RuntimeErrorMessages


@dataclass
class VariableReference:
    getter: Any
    setter: Any

    def get(self) -> Any:
        return self.getter()

    def set(self, value: Any) -> None:
        self.setter(value)


class ExecutionContext:
    """
    Runtime execution context.

    Phase 1:
    - stores emitted playback events
    - stores diagnostics

    Phase 2:
    - adds a flat variable table for assignment / identifier lookup

    Milestone 67:
    - adds function registry
    - adds local scope stack for function execution
    - preserves current flat-variable behavior for existing runtime phases

    Milestone 68 / call stack trace debugger:
    - upgrades raw local scopes to structured call frames
    - adds call stack formatting helpers
    - adds optional structured call trace recording

    Milestone 69 / debugger integration:
    - adds optional debugger reference
    - formalizes breakpoint manager support
    - upgrades internal call stack storage to CallStack / CallFrame
    - preserves existing public helper behavior where possible
    """

    DEFAULT_MOUSE_MOVE_SPEED = 10
    MIN_MOUSE_MOVE_SPEED = 0
    MAX_MOUSE_MOVE_SPEED = 100

    def __init__(
        self,
        *,
        default_mouse_move_speed: int = DEFAULT_MOUSE_MOVE_SPEED,
        default_current_event_delay_ms: int = 0,
    ) -> None:
        self.playback_events: list[dict[str, Any]] = []
        self.diagnostics: list[str] = []
        self.console_output: list[str] = []
        self.script_exit_code: int = 0

        self.variables: dict[str, Any] = {}
        self.constants: dict[str, Any] = {}
        self.host_values: dict[str, Any] = {}
        self.special_values: dict[str, Any] = {
            "Error": 0,
            "Extended": 0,
            "CR": "\r",
            "LF": "\n",
            "CRLF": "\r\n",
            "TAB": "\t",
            "ScriptName": "<script>",
            "ScriptDirectory": "",
            "WorkingDir": os.getcwd(),
        }
        self.host_services: dict[str, Any] = {}
        self.functions: dict[str, Any] = {}
        self.external_functions: dict[str, ExternalFunctionBinding] = {}
        self.enums: dict[str, Any] = {}
        self.structs: dict[str, StructDefinition] = {}
        self.records: dict[str, RecordDefinition] = {}
        self.call_stack: CallStack = CallStack()
        self.max_call_depth: int = 100

        self.trace_enabled: bool = False
        self._trace_messages: list[str] = []

        self.debugger: Any | None = None
        self.breakpoints = BreakpointSet(document_id="<runtime>")

        self.current_source_line: int | None = None
        self._source_line_stack: list[int | None] = []
        self._default_mouse_move_speed: int = self._clamp_mouse_move_speed(
            default_mouse_move_speed
        )
        self._mouse_move_speed_override: int | None = None
        self._default_current_event_delay_ms: int = self._clamp_non_negative_int(
            default_current_event_delay_ms
        )
        self._current_event_delay_override: int | None = None

    def set_current_source_line(self, line: int | None) -> int | None:
        resolved = self._resolve_positive_line(line)
        self.current_source_line = resolved
        return self.current_source_line

    def push_source_line(self, line: int | None = None) -> int | None:
        self._source_line_stack.append(self.current_source_line)
        if line is not None:
            self.set_current_source_line(line)
        return self.current_source_line

    def pop_source_line(self) -> int | None:
        if not self._source_line_stack:
            return self.current_source_line
        self.current_source_line = self._source_line_stack.pop()
        return self.current_source_line

    def emit_event(self, event: dict[str, Any]) -> None:
        if isinstance(event, dict) and self.current_source_line is not None:
            event["_source_line"] = self.current_source_line
        if isinstance(event, dict):
            snapshot = self.export_debug_context_snapshot()
            if snapshot:
                event["_debug_context"] = snapshot
        self.playback_events.append(event)

    def emit_control_event(
        self,
        control_kind: str,
        *,
        source_line: int | None = None,
        structure_kind: str | None = None,
        structure_id: str | None = None,
        iteration_index: int | None = None,
        loop_header_line: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "type": "control",
            "control_kind": str(control_kind),
            "_debug_boundary": True,
        }

        resolved_source_line = self._resolve_positive_line(
            source_line,
            fallback=self.current_source_line,
        )
        if resolved_source_line is not None:
            event["_source_line"] = resolved_source_line

        if isinstance(structure_kind, str) and structure_kind.strip():
            event["_structure_kind"] = structure_kind.strip()

        if isinstance(structure_id, str) and structure_id.strip():
            event["_structure_id"] = structure_id.strip()

        if isinstance(iteration_index, int) and iteration_index >= 0:
            event["_iteration_index"] = iteration_index
            event["_iteration_display"] = iteration_index + 1

        resolved_loop_header_line = self._resolve_positive_line(loop_header_line)
        if resolved_loop_header_line is not None:
            event["_loop_header_line"] = resolved_loop_header_line

        if isinstance(payload, dict) and payload:
            event["_control_payload"] = dict(payload)

        snapshot = self.export_debug_context_snapshot()
        if snapshot:
            event["_debug_context"] = snapshot

        self.playback_events.append(event)

    def add_diagnostic(self, message: str) -> None:
        self.diagnostics.append(str(message))

    def add_output(self, message: str) -> None:
        self.console_output.append(str(message))

    def _clamp_mouse_move_speed(self, speed: int) -> int:
        return max(
            self.MIN_MOUSE_MOVE_SPEED,
            min(self.MAX_MOUSE_MOVE_SPEED, int(speed)),
        )

    def _clamp_non_negative_int(self, value: int) -> int:
        return max(0, int(value))

    def get_default_mouse_move_speed(self) -> int:
        return int(self._default_mouse_move_speed)

    def set_default_mouse_move_speed(self, speed: int) -> None:
        self._default_mouse_move_speed = self._clamp_mouse_move_speed(speed)

    def set_mouse_move_speed_override(self, speed: int | None) -> None:
        if speed is None:
            self._mouse_move_speed_override = None
            return
        self._mouse_move_speed_override = self._clamp_mouse_move_speed(speed)

    def has_mouse_move_speed_override(self) -> bool:
        return self._mouse_move_speed_override is not None

    def get_mouse_move_speed_override(self) -> int | None:
        if self._mouse_move_speed_override is None:
            return None
        return int(self._mouse_move_speed_override)

    def get_effective_mouse_move_speed(self) -> int:
        if self._mouse_move_speed_override is not None:
            return int(self._mouse_move_speed_override)
        return int(self._default_mouse_move_speed)

    def get_current_event_delay(self) -> int:
        if self._current_event_delay_override is not None:
            return int(self._current_event_delay_override)
        return int(self._default_current_event_delay_ms)

    def set_current_event_delay(self, delay_ms: int | None) -> None:
        if delay_ms is None:
            self._current_event_delay_override = None
            return
        self._current_event_delay_override = self._clamp_non_negative_int(delay_ms)

    def has_current_event_delay_override(self) -> bool:
        return self._current_event_delay_override is not None

    def get_current_event_delay_override(self) -> int | None:
        if self._current_event_delay_override is None:
            return None
        return int(self._current_event_delay_override)

    def set_debugger(self, debugger: Any | None) -> None:
        self.debugger = debugger

    def record_exception(self, exc: BaseException, node: Any | None = None) -> None:
        message = str(exc) or exc.__class__.__name__
        line = self._get_line(node)
        if line is not None:
            self.add_diagnostic(f"Exception at line {line}: {message}")
        else:
            self.add_diagnostic(f"Exception: {message}")
        if self.debugger is not None:
            on_exception = getattr(self.debugger, "on_exception", None)
            if callable(on_exception):
                on_exception(exc, node, self)

    def set_variable(self, name: str, value: Any) -> None:
        variable_name = self._normalize_name(name)
        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            raise RuntimeError(
                RuntimeErrorMessages.cannot_assign_to_constant(constant_name)
            )
        value = clone_runtime_value(value)
        frame = self.current_frame()
        if frame is not None:
            byref_name = self._find_existing_name(frame.byref_bindings, variable_name)
            if byref_name is not None:
                frame.byref_bindings[byref_name].set(value)
                return
            local_name = self._find_existing_name(frame.locals, variable_name)
            if local_name is not None:
                frame.locals[local_name] = value
                return
            frame.locals[variable_name] = value
            return
        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is None:
            self.variables[variable_name] = value
        else:
            self.variables[global_name] = value

    def set_local(self, name: str, value: Any) -> None:
        variable_name = self._normalize_name(name)
        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            raise RuntimeError(
                RuntimeErrorMessages.cannot_assign_to_constant(constant_name)
            )
        value = clone_runtime_value(value)
        frame = self.current_frame()
        if frame is not None:
            byref_name = self._find_existing_name(frame.byref_bindings, variable_name)
            if byref_name is not None:
                frame.byref_bindings[byref_name].set(value)
                return
            local_name = self._find_existing_name(frame.locals, variable_name)
            if local_name is not None:
                frame.locals[local_name] = value
                return
            frame.locals[variable_name] = value
            return
        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is None:
            self.variables[variable_name] = value
        else:
            self.variables[global_name] = value

    def set_global(self, name: str, value: Any) -> None:
        variable_name = self._normalize_name(name)
        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            raise RuntimeError(
                RuntimeErrorMessages.cannot_assign_to_constant(constant_name)
            )
        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is None:
            self.variables[variable_name] = clone_runtime_value(value)
        else:
            self.variables[global_name] = clone_runtime_value(value)

    def has_variable(self, name: str) -> bool:
        variable_name = self._normalize_name(name)
        frame = self.current_frame()
        if frame is not None and self._find_existing_name(frame.byref_bindings, variable_name) is not None:
            return True
        if frame is not None and self._find_existing_name(frame.locals, variable_name) is not None:
            return True
        if self._find_existing_name(self.constants, variable_name) is not None:
            return True
        return self._find_existing_name(self.variables, variable_name) is not None

    def set_constant(self, name: str, value: Any) -> None:
        constant_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.constants, constant_name)
        if existing_name is None:
            self.constants[constant_name] = clone_runtime_value(value)
        else:
            self.constants[existing_name] = clone_runtime_value(value)

    def has_constant(self, name: str) -> bool:
        constant_name = self._normalize_name(name)
        return self._find_existing_name(self.constants, constant_name) is not None

    def set_host_value(self, name: str, value: Any) -> None:
        host_name = self._normalize_name(name)
        special_name = self._find_existing_name(self.special_values, host_name)
        if special_name is not None:
            self.set_special_value(special_name, value)
            return
        existing_name = self._find_existing_name(self.host_values, host_name)
        if existing_name is None:
            self.host_values[host_name] = value
        else:
            self.host_values[existing_name] = value

    def set_special_value(self, name: str, value: Any) -> None:
        special_name = self._normalize_name(name)
        # Special values are set by the host/runtime, not by script code.
        existing_name = self._find_existing_name(self.special_values, special_name)
        if existing_name is None:
            self.special_values[special_name] = value
            self.host_values[special_name] = value
        else:
            self.special_values[existing_name] = value
            self.host_values[existing_name] = value

    def has_special_value(self, name: str) -> bool:
        special_name = self._normalize_name(name)
        return self._find_existing_name(self.special_values, special_name) is not None

    def get_special_value(self, name: str) -> Any:
        special_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.special_values, special_name)
        if existing_name is None:
            raise RuntimeError(RuntimeErrorMessages.unknown_host_identifier(special_name))
        return self.special_values[existing_name]

    def set_error(self, value: Any = 0) -> None:
        self.set_special_value("Error", value)

    def get_error(self) -> Any:
        return self.get_special_value("Error")

    def set_host_service(self, name: str, service: Any) -> None:
        service_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.host_services, service_name)
        if existing_name is None:
            self.host_services[service_name] = service
        else:
            self.host_services[existing_name] = service

    def has_host_service(self, name: str) -> bool:
        service_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.host_services, service_name)
        return callable(self.host_services.get(existing_name)) if existing_name is not None else False

    def call_host_service(self, name: str, *args: Any, **kwargs: Any) -> Any:
        service_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.host_services, service_name)
        service = self.host_services.get(existing_name) if existing_name is not None else None
        if not callable(service):
            raise RuntimeError(
                RuntimeErrorMessages.host_service_not_available(service_name)
            )
        return service(*args, **kwargs)

    def resolve_host_identifier(self, name: str) -> Any:
        host_name = self._normalize_name(name)
        special_name = self._find_existing_name(self.special_values, host_name)
        if special_name is not None:
            return self.special_values[special_name]
        host_value_name = self._find_existing_name(self.host_values, host_name)
        if host_value_name is not None:
            return self.host_values[host_value_name]
        raise RuntimeError(RuntimeErrorMessages.unknown_host_identifier(host_name))

    def get_variable(self, name: str) -> Any:
        variable_name = self._normalize_name(name)
        frame = self.current_frame()

        if frame is not None:
            byref_name = self._find_existing_name(frame.byref_bindings, variable_name)
            if byref_name is not None:
                return frame.byref_bindings[byref_name].get()

            local_name = self._find_existing_name(frame.locals, variable_name)
            if local_name is not None:
                return frame.locals[local_name]

        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            return self.constants[constant_name]

        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is not None:
            return self.variables[global_name]

        raise RuntimeError(RuntimeErrorMessages.undefined_variable(variable_name))

    def register_function(self, name: str, func_node: Any) -> None:
        function_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.functions, function_name)
        if existing_name is None:
            self.functions[function_name] = func_node
        else:
            self.functions[existing_name] = func_node

    def register_external_function(self, name: str, binding: ExternalFunctionBinding) -> None:
        function_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.external_functions, function_name)
        if existing_name is None:
            self.external_functions[function_name] = binding
        else:
            self.external_functions[existing_name] = binding

    def register_struct(self, name: str, struct_def: StructDefinition) -> None:
        struct_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.structs, struct_name)
        if existing_name is None:
            self.structs[struct_name] = struct_def
        else:
            self.structs[existing_name] = struct_def

    def register_enum(self, name: str, enum_def: Any) -> None:
        enum_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.enums, enum_name)
        if existing_name is None:
            self.enums[enum_name] = enum_def
        else:
            self.enums[existing_name] = enum_def

    def register_record(self, name: str, record_def: RecordDefinition) -> None:
        record_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.records, record_name)
        if existing_name is None:
            self.records[record_name] = record_def
        else:
            self.records[existing_name] = record_def

    def has_struct(self, name: str) -> bool:
        struct_name = self._normalize_name(name)
        return self._find_existing_name(self.structs, struct_name) is not None

    def has_enum(self, name: str) -> bool:
        enum_name = self._normalize_name(name)
        return self._find_existing_name(self.enums, enum_name) is not None

    def has_record(self, name: str) -> bool:
        record_name = self._normalize_name(name)
        return self._find_existing_name(self.records, record_name) is not None

    def get_struct(self, name: str) -> StructDefinition:
        struct_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.structs, struct_name)
        if existing_name is None:
            raise RuntimeError(RuntimeErrorMessages.struct_not_defined(struct_name))
        return self.structs[existing_name]

    def get_enum(self, name: str) -> Any:
        enum_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.enums, enum_name)
        if existing_name is None:
            raise RuntimeError(RuntimeErrorMessages.enum_not_defined(enum_name))
        return self.enums[existing_name]

    def get_record(self, name: str) -> RecordDefinition:
        record_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.records, record_name)
        if existing_name is None:
            raise RuntimeError(RuntimeErrorMessages.record_not_defined(record_name))
        return self.records[existing_name]

    def has_function(self, name: str) -> bool:
        function_name = self._normalize_name(name)
        return self._find_existing_name(self.functions, function_name) is not None

    def has_external_function(self, name: str) -> bool:
        function_name = self._normalize_name(name)
        return self._find_existing_name(self.external_functions, function_name) is not None

    def get_external_function(self, name: str) -> ExternalFunctionBinding:
        function_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.external_functions, function_name)
        if existing_name is None:
            raise RuntimeError(
                RuntimeErrorMessages.external_function_not_defined(function_name)
            )
        return self.external_functions[existing_name]

    def get_function(self, name: str) -> Any:
        function_name = self._normalize_name(name)
        existing_name = self._find_existing_name(self.functions, function_name)
        if existing_name is None:
            raise RuntimeError(
                RuntimeErrorMessages.function_not_defined(function_name)
            )
        return self.functions[existing_name]

    def call_depth(self) -> int:
        return self.call_stack.depth()

    def in_function_scope(self) -> bool:
        return self.current_frame() is not None

    def push_call_frame(
        self,
        function_name: str,
        locals_dict: dict[str, Any] | None = None,
        *,
        byref_bindings: dict[str, VariableReference] | None = None,
        node: Any | None = None,
        arguments: dict[str, Any] | None = None,
        line: int | None = None,
    ) -> CallFrame:
        cloned_locals = {name: clone_runtime_value(value) for name, value in dict(locals_dict or {}).items()}
        cloned_arguments = {name: clone_runtime_value(value) for name, value in dict(arguments or {}).items()}
        normalized_function_name = self._normalize_name(function_name)
        frame = CallFrame(
            function_name=normalized_function_name,
            locals=cloned_locals,
            byref_bindings=dict(byref_bindings or {}),
            node=node,
            arguments=cloned_arguments,
            line=line if isinstance(line, int) else self._get_line(node),
        )
        self.call_stack.push(frame)

        if self.debugger is not None:
            on_function_call = getattr(self.debugger, "on_function_call", None)
            if callable(on_function_call):
                on_function_call(frame.function_name, self)

        return frame

    def pop_call_frame(self, return_value: Any = None) -> CallFrame:
        if not self.call_stack:
            raise RuntimeError(RuntimeErrorMessages.CALL_STACK_UNDERFLOW)

        frame = self.call_stack.pop()

        if self.debugger is not None:
            on_function_return = getattr(self.debugger, "on_function_return", None)
            if callable(on_function_return):
                on_function_return(frame.function_name, return_value, self)

        return frame

    def current_frame(self) -> CallFrame | None:
        return self.call_stack.current()

    def current_function_name(self) -> str | None:
        frame = self.current_frame()
        if frame is None:
            return None
        return frame.function_name

    def current_locals(self) -> dict[str, Any] | None:
        frame = self.current_frame()
        if frame is None:
            return None
        resolved = {name: clone_runtime_value(value) for name, value in frame.locals.items()}
        for name, reference in frame.byref_bindings.items():
            resolved[name] = clone_runtime_value(reference.get())
        return resolved

    def resolve_variable_reference(self, name: str) -> VariableReference:
        variable_name = self._normalize_name(name)
        frame = self.current_frame()

        if frame is not None:
            byref_name = self._find_existing_name(frame.byref_bindings, variable_name)
            if byref_name is not None:
                return frame.byref_bindings[byref_name]

            local_name = self._find_existing_name(frame.locals, variable_name)
            if local_name is not None:
                return VariableReference(
                    getter=lambda frame=frame, local_name=local_name: frame.locals[local_name],
                    setter=lambda value, frame=frame, local_name=local_name: frame.locals.__setitem__(local_name, value),
                )

        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            raise RuntimeError(
                RuntimeErrorMessages.cannot_pass_constant_byref(constant_name)
            )

        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is not None:
            return VariableReference(
                getter=lambda global_name=global_name: self.variables[global_name],
                setter=lambda value, global_name=global_name: self.variables.__setitem__(global_name, value),
            )

        raise RuntimeError(RuntimeErrorMessages.undefined_variable(variable_name))

    def resolve_assignment_reference(self, name: str) -> VariableReference:
        variable_name = self._normalize_name(name)
        frame = self.current_frame()

        constant_name = self._find_existing_name(self.constants, variable_name)
        if constant_name is not None:
            raise RuntimeError(
                RuntimeErrorMessages.cannot_assign_to_constant(constant_name)
            )

        if frame is not None:
            byref_name = self._find_existing_name(frame.byref_bindings, variable_name)
            if byref_name is not None:
                return frame.byref_bindings[byref_name]

            local_name = self._find_existing_name(frame.locals, variable_name)
            if local_name is not None:
                return VariableReference(
                    getter=lambda frame=frame, local_name=local_name: frame.locals.get(local_name),
                    setter=lambda value, frame=frame, local_name=local_name: frame.locals.__setitem__(local_name, value),
                )
            return VariableReference(
                getter=lambda frame=frame, variable_name=variable_name: frame.locals.get(variable_name),
                setter=lambda value, frame=frame, variable_name=variable_name: frame.locals.__setitem__(variable_name, value),
            )

        global_name = self._find_existing_name(self.variables, variable_name)
        if global_name is not None:
            return VariableReference(
                getter=lambda global_name=global_name: self.variables.get(global_name),
                setter=lambda value, global_name=global_name: self.variables.__setitem__(global_name, value),
            )

        return VariableReference(
            getter=lambda variable_name=variable_name: self.variables.get(variable_name),
            setter=lambda value, variable_name=variable_name: self.variables.__setitem__(variable_name, value),
        )

    def export_debug_context_snapshot(self) -> dict[str, Any]:
        frames = self.call_stack.snapshot()
        for index, frame in enumerate(frames):
            if isinstance(frame, dict):
                frame["depth"] = index
                frame.setdefault("globals", dict(self.variables))

        snapshot: dict[str, Any] = {
            "call_stack": frames,
            "variables": dict(self.variables),
            "special_values": dict(self.special_values),
        }

        if isinstance(self.current_source_line, int) and self.current_source_line >= 1:
            snapshot["current_source_line"] = self.current_source_line

        return snapshot

    def get_call_stack_names(self) -> list[str]:
        return [frame.function_name for frame in self.call_stack]

    def format_call_stack(self) -> str:
        names = self.get_call_stack_names()
        if not names:
            return "Call stack: <empty>"
        return "Call stack: Main -> " + " -> ".join(names)

    def enforce_call_depth_limit(self) -> None:
        if self.call_depth() <= self.max_call_depth:
            return

        function_name = self.current_function_name() or "<unknown>"
        if hasattr(RuntimeErrorMessages, "maximum_call_depth_exceeded"):
            raise RuntimeError(
                RuntimeErrorMessages.maximum_call_depth_exceeded(function_name)
            )
        raise RuntimeError(f"Maximum call depth exceeded in function: {function_name}")

    def push_scope(self, initial_scope: dict[str, Any] | None = None) -> dict[str, Any]:
        frame = self.push_call_frame("<anonymous>", initial_scope)
        return frame.locals

    def pop_scope(self) -> dict[str, Any]:
        frame = self.pop_call_frame()
        return frame.locals

    def trace_call_enter(self, function_name: str, args: dict[str, Any]) -> None:
        if not self.trace_enabled:
            return

        depth = self.call_depth()

        formatted_args = ", ".join(f"{k}={v}" for k, v in args.items())
        message = f"CALL enter depth={depth} function={function_name} args={{{formatted_args}}}"

        self._trace_messages.append(message)

    def trace_call_return(self, function_name: str, value: Any) -> None:
        if not self.trace_enabled:
            return

        depth = self.call_depth()

        message = f"CALL return depth={depth} function={function_name} value={value}"
        self._trace_messages.append(message)

    def trace_call_exit(self, function_name: str) -> None:
        if not self.trace_enabled:
            return

        depth = self.call_depth()

        message = f"CALL exit depth={depth} function={function_name}"
        self._trace_messages.append(message)

    def trace_call_error(self, function_name: str, message: str) -> None:
        if not self.trace_enabled:
            return
        self._trace_messages.append(
            f"ERROR {self._normalize_name(function_name)} message={str(message)}"
        )

    def get_trace_messages(self) -> list[str]:
        return list(self._trace_messages)

    def set_breakpoints(self, lines: list[int] | set[int] | tuple[int, ...]) -> None:
        self.breakpoints.clear()
        for line in lines:
            if isinstance(line, int) and line > 0:
                self.breakpoints.add(line)

    def add_breakpoint(self, line: int) -> None:
        if isinstance(line, int) and line > 0:
            self.breakpoints.add(line)

    def remove_breakpoint(self, line: int) -> None:
        if isinstance(line, int) and line > 0:
            self.breakpoints.remove(line)

    def clear_breakpoints(self) -> None:
        self.breakpoints.clear()

    def get_breakpoints(self) -> list[int]:
        return sorted(self.breakpoints.lines())

    def has_breakpoint(self, line: int) -> bool:
        if not isinstance(line, int) or line <= 0:
            return False
        return self.breakpoints.has(line)

    def _normalize_name(self, name: str) -> str:
        return str(name).strip()

    def _find_existing_name(self, mapping: dict[str, Any], name: str) -> str | None:
        target = self._normalize_name(name)
        if not target:
            return None
        normalized = target.lower()
        for existing_name in mapping:
            if str(existing_name).strip().lower() == normalized:
                return str(existing_name)
        return None

    def _get_line(self, node: Any | None) -> int | None:
        if node is None:
            return None
        line = getattr(node, "line", None)
        if isinstance(line, int):
            return line
        return None

    def _resolve_positive_line(
        self,
        value: Any,
        *,
        fallback: int | None = None,
    ) -> int | None:
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(fallback, int) and fallback > 0:
            return fallback
        return None
