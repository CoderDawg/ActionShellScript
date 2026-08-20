"""
Runtime error messages.
**COPIED FROM**
packages/app_core/runtime/runtime_errors.py
"""
from __future__ import annotations

from core.runtime.builtins.builtin_registry import format_builtin_function_name


def _display_name(name: str) -> str:
    return format_builtin_function_name(name)

class RuntimeErrorMessages:
    VARIABLE_NAME_EMPTY = "Variable name must not be empty"

    EXPRESSION_MUST_NOT_BE_EMPTY = "Expression must not be empty"
    UNARY_OPERATOR_REQUIRES_NUMERIC_OPERAND = (
        "Unary operator requires numeric operand"
    )

    FOR_LOOP_VARIABLE_MUST_BE_IDENTIFIER = (
        "For loop variable must be an identifier in Phase 3"
    )
    FOR_LOOP_START_MUST_BE_INTEGER = "For loop start value must be an integer"
    FOR_LOOP_STOP_MUST_BE_INTEGER = "For loop stop value must be an integer"
    FOR_LOOP_STEP_MUST_BE_INTEGER = "For loop step value must be an integer"
    FOR_LOOP_STEP_MUST_NOT_BE_ZERO = "For loop step must not be zero"

    SLEEP_DELAY_MUST_BE_NON_NEGATIVE = "Sleep delay must be >= 0"
    CURRENT_EVENT_DELAY_MUST_BE_NON_NEGATIVE = "Current event delay must be >= 0"
    TEXT_ARGUMENT_1_MUST_NOT_BE_NULL = "Text argument 1 must not be null"

    MOUSE_MOVE_EXPECTS_2_OR_3_ARGUMENTS = "MouseMove expects 2 or 3 arguments"
    MOUSE_CLICK_EXPECTS_4_OR_5_ARGUMENTS = "MouseClick expects 4 or 5 arguments"
    MOUSE_CLICK_DRAG_EXPECTS_5_OR_6_ARGUMENTS = "MouseClickDrag expects 5 or 6 arguments"
    MOUSE_DRAG_EXPECTS_6_OR_7_ARGUMENTS = "MouseDrag expects 6 or 7 arguments"
    MOUSE_WHEEL_EXPECTS_1_OR_3_ARGUMENTS = "MouseWheel expects 1 or 3 arguments"
    MOUSE_MOVE_SPEED_RANGE = "MouseMove speed must be between 0 and 100"
    MOUSE_CLICK_CLICKS_MUST_BE_POSITIVE = "MouseClick clicks must be >= 1"
    MOUSE_DRAG_DURATION_MUST_BE_NON_NEGATIVE = "MouseDrag duration must be >= 0"
    MSGBOX_TIMEOUT_MUST_BE_NON_NEGATIVE = "MsgBox timeout must be >= 0"
    PIXEL_SEARCH_SHADE_VARIATION_RANGE = (
        "PixelSearch shade variation must be between 0 and 255"
    )
    PIXEL_SEARCH_STEP_MUST_BE_AT_LEAST_1 = "PixelSearch step must be >= 1"

    CALL_STACK_UNDERFLOW = "Call stack underflow"
    CONSTANT_CANNOT_BE_ASSIGNED = "Cannot assign to constant"

    @staticmethod
    def undefined_variable(name: str) -> str:
        return f"Undefined variable: {name}"

    @staticmethod
    def unsupported_statement(phase: str, kind: str) -> str:
        return f"Unsupported statement in {phase}: {kind}"

    @staticmethod
    def unsupported_expression_type(phase: str, kind: str) -> str:
        return f"Unsupported expression type in {phase}: {kind}"

    @staticmethod
    def unknown_host_identifier(name: str) -> str:
        return f"Unknown host identifier: @{name}"

    @staticmethod
    def unsupported_unary_operator(phase: str, op: str) -> str:
        return f"Unsupported unary operator in {phase}: {op}"

    @staticmethod
    def unsupported_binary_operator(phase: str, op: str) -> str:
        return f"Unsupported binary operator in {phase}: {op}"

    @staticmethod
    def unknown_format_specifier(spec: str) -> str:
        return f"Unknown format specifier '{spec}'"

    @staticmethod
    def format_specifier_requires_integer(spec: str, kind: str) -> str:
        return f"Format specifier '{spec}' requires an integer value, got {kind}"

    @staticmethod
    def format_specifier_requires_numeric(spec: str, kind: str) -> str:
        return f"Format specifier '{spec}' requires a numeric value, got {kind}"

    @staticmethod
    def invalid_if_branch_shape(phase: str) -> str:
        return f"Invalid If/ElseIf branch shape in {phase}"

    @staticmethod
    def loop_iteration_limit_exceeded(loop_kind: str, limit: int) -> str:
        return f"{loop_kind} loop exceeded maximum iteration limit of {limit}"

    @staticmethod
    def unsupported_function(name: str) -> str:
        return f"Unsupported function: {_display_name(name)}"

    @staticmethod
    def expects_argument_count(name: str, count: int) -> str:
        return f"{_display_name(name)} expects {count} argument(s)"

    @staticmethod
    def expects_argument_range(name: str, minimum: int, maximum: int) -> str:
        return f"{_display_name(name)} expects between {minimum} and {maximum} argument(s)"

    @staticmethod
    def expects_argument_counts(name: str, *counts: int) -> str:
        if not counts:
            return f"{_display_name(name)} argument count is invalid"
        if len(counts) == 1:
            return RuntimeErrorMessages.expects_argument_count(name, counts[0])
        values = " or ".join(str(count) for count in counts)
        return f"{_display_name(name)} expects {values} arguments"

    @staticmethod
    def expects_at_least_arguments(name: str, minimum: int) -> str:
        return f"{_display_name(name)} expects at least {minimum} argument(s)"

    @staticmethod
    def argument_must_be_number(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a number"

    @staticmethod
    def argument_must_be_integer(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be an integer"

    @staticmethod
    def argument_must_be_string(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a string"

    @staticmethod
    def argument_must_be_string_or_number(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a string or number"

    @staticmethod
    def argument_must_be_datetime_value(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a number or tm struct"

    @staticmethod
    def argument_must_be_binary(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be binary"

    @staticmethod
    def argument_must_be_array(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be an array"

    @staticmethod
    def argument_must_not_be_empty(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must not be empty"

    @staticmethod
    def argument_must_be_single_character(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a single character"

    @staticmethod
    def character_must_be_ascii(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be an ASCII character"

    @staticmethod
    def argument_must_be_ascii_code(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be an ASCII code between 0 and 127"

    @staticmethod
    def argument_must_be_unicode_code_point(name: str, index: int) -> str:
        return f"{_display_name(name)} argument {index} must be a Unicode code point between 0 and 1114111"

    @staticmethod
    def invalid_sendkeys_sequence(details: str) -> str:
        return f"SendKeys invalid sequence: {details}"

    @staticmethod
    def argument_must_be_one_of_strings(name: str, index: int, allowed: list[str] | tuple[str, ...]) -> str:
        values = ", ".join(str(value) for value in allowed)
        return f"{_display_name(name)} argument {index} must be one of: {values}"

    @staticmethod
    def file_not_found(name: str, path: str) -> str:
        return f"{_display_name(name)} file not found: {path}"

    @staticmethod
    def path_not_found(name: str, path: str) -> str:
        return f"{_display_name(name)} path not found: {path}"

    @staticmethod
    def path_is_directory(name: str, path: str) -> str:
        return f"{_display_name(name)} path is a directory: {path}"

    @staticmethod
    def path_exists_and_is_not_directory(name: str, path: str) -> str:
        return f"{_display_name(name)} path exists and is not a directory: {path}"

    @staticmethod
    def directory_not_found(name: str, path: str) -> str:
        return f"{_display_name(name)} directory not found: {path}"

    @staticmethod
    def directory_not_empty(name: str, path: str) -> str:
        return f"{_display_name(name)} directory is not empty: {path}"

    @staticmethod
    def path_already_exists(name: str, path: str) -> str:
        return f"{_display_name(name)} path already exists: {path}"

    @staticmethod
    def parent_directory_not_found(name: str, path: str) -> str:
        return f"{_display_name(name)} parent directory not found: {path}"

    @staticmethod
    def unsupported_encoding(name: str, encoding: str) -> str:
        return f"{_display_name(name)} unsupported encoding: {encoding}"

    @staticmethod
    def decode_failed(name: str, path: str, encoding: str) -> str:
        return f"{_display_name(name)} failed to decode file '{path}' with encoding '{encoding}'"

    @staticmethod
    def invalid_hex_text(name: str) -> str:
        return f"{_display_name(name)} text is not valid hexadecimal"

    @staticmethod
    def invalid_base64_text(name: str) -> str:
        return f"{_display_name(name)} text is not valid base64"

    @staticmethod
    def invalid_regular_expression(name: str, details: str) -> str:
        return f"{_display_name(name)} invalid regular expression: {details}"

    @staticmethod
    def invalid_regex_option(name: str, option: str) -> str:
        return f"{_display_name(name)} invalid regex option: {option}"

    @staticmethod
    def invalid_date_time_text(name: str, text: str) -> str:
        return f"{_display_name(name)} text is not a valid date/time: {text}"

    @staticmethod
    def argument_must_be_one_of(name: str, index: int, allowed: list[int] | tuple[int, ...]) -> str:
        values = ", ".join(str(value) for value in allowed)
        return f"{name} argument {index} must be one of: {values}"

    @staticmethod
    def argument_must_be_at_least(name: str, index: int, minimum: int) -> str:
        return f"{name} argument {index} must be >= {minimum}"

    @staticmethod
    def binary_decode_failed(name: str, encoding_label: str) -> str:
        return f"{_display_name(name)} failed to decode binary data as {encoding_label}"

    @staticmethod
    def access_denied(name: str, path: str) -> str:
        return f"{_display_name(name)} access denied: {path}"

    @staticmethod
    def operation_failed(name: str, path: str) -> str:
        return f"{_display_name(name)} failed: {path}"

    @staticmethod
    def argument_must_be_allowed_button(name: str, index: int, allowed) -> str:
        values = ", ".join(sorted(allowed))
        return f"{_display_name(name)} argument {index} must be one of: {values}"

    @staticmethod
    def host_service_not_available(name: str) -> str:
        return f"Host service not available: {_display_name(name)}"

    @staticmethod
    def host_service_must_return_integer(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return an integer"

    @staticmethod
    def host_service_must_return_bool(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a boolean"

    @staticmethod
    def host_service_must_return_point_pair(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return [x, y] or Null"

    @staticmethod
    def host_service_must_return_point(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a cursor point mapping"

    @staticmethod
    def host_service_must_return_rect(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a window rect mapping"

    @staticmethod
    def host_service_must_return_client_rect(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a client rect mapping"

    @staticmethod
    def host_service_must_return_string(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a string"

    @staticmethod
    def host_service_must_return_class_name(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a class name string"

    @staticmethod
    def host_service_must_return_window_placement(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a window placement mapping"

    @staticmethod
    def host_service_must_return_monitor_info(name: str) -> str:
        return f"Host service '{_display_name(name)}' must return a monitor info mapping"

    @staticmethod
    def cannot_assign_to_constant(name: str) -> str:
        return f"Cannot assign to constant: {_display_name(name)}"

    @staticmethod
    def byref_argument_must_be_variable(parameter: str) -> str:
        return f"ByRef argument for parameter '{parameter}' must be a writable variable or index target"

    @staticmethod
    def cannot_pass_constant_byref(name: str) -> str:
        return f"Cannot pass constant ByRef: {_display_name(name)}"

    @staticmethod
    def index_target_must_be_integer() -> str:
        return "Index target must use an integer index"

    @staticmethod
    def value_not_indexable(kind: str) -> str:
        return f"Value is not indexable: {kind}"

    @staticmethod
    def index_out_of_range(index: int) -> str:
        return f"Index out of range: {index}"

    @staticmethod
    def assignment_target_not_writable(kind: str) -> str:
        return f"Assignment target is not writable: {kind}"

    @staticmethod
    def runtime_value_is_read_only(name: str) -> str:
        return f"Runtime value is read-only: @{name}"

    @staticmethod
    def struct_not_defined(name: str) -> str:
        return f"Struct not defined: {_display_name(name)}"

    @staticmethod
    def struct_field_type_not_defined(struct_name: str, field_name: str, type_name: str) -> str:
        return (
            f"Struct '{_display_name(struct_name)}' field '{field_name}' uses unknown type: {type_name}"
        )

    @staticmethod
    def struct_field_type_mismatch(
        struct_name: str,
        field_name: str,
        expected_type: str,
        actual_type: str,
    ) -> str:
        return (
            f"Struct '{_display_name(struct_name)}' field '{field_name}' expects {expected_type}"
            f" but got {actual_type}"
        )

    @staticmethod
    def recursive_struct_layout_detected(cycle: list[str] | tuple[str, ...]) -> str:
        cycle_text = " -> ".join(str(name) for name in cycle)
        return f"Recursive struct layout detected: {cycle_text}"

    @staticmethod
    def struct_constructor_argument_count_mismatch(name: str, expected: int, actual: int) -> str:
        return f"{_display_name(name)} struct constructor expected {expected} argument(s) but got {actual}"

    @staticmethod
    def struct_constructor_missing_required_field(struct_name: str, field_name: str) -> str:
        return f"Struct '{_display_name(struct_name)}' missing required field: {field_name}"

    @staticmethod
    def struct_field_not_defined(struct_name: str, field_name: str) -> str:
        return f"Struct '{_display_name(struct_name)}' has no field named '{field_name}'"

    @staticmethod
    def struct_fields_are_immutable(struct_name: str, field_name: str) -> str:
        return f"Struct '{_display_name(struct_name)}' field '{field_name}' is immutable"

    @staticmethod
    def record_not_defined(name: str) -> str:
        return f"Record not defined: {_display_name(name)}"

    @staticmethod
    def enum_not_defined(name: str) -> str:
        return f"Enum not defined: {_display_name(name)}"

    @staticmethod
    def struct_name_collision(name: str) -> str:
        return f"Struct already declared: {_display_name(name)}"

    @staticmethod
    def enum_name_collision(name: str) -> str:
        return f"Enum already declared: {_display_name(name)}"

    @staticmethod
    def enum_member_name_collision(enum_name: str, member_name: str) -> str:
        return f"Enum '{_display_name(enum_name)}' member already declared: {_display_name(member_name)}"

    @staticmethod
    def enum_member_value_must_be_integer(enum_name: str, member_name: str) -> str:
        return f"Enum '{_display_name(enum_name)}' member '{member_name}' must evaluate to an integer"

    @staticmethod
    def record_name_collision(name: str) -> str:
        return f"Record already declared: {str(name).strip()}"

    @staticmethod
    def record_field_type_not_defined(record_name: str, field_name: str, type_name: str) -> str:
        return (
            f"Record '{_display_name(record_name)}' field '{field_name}' uses unknown type: {type_name}"
        )

    @staticmethod
    def record_field_type_mismatch(
        record_name: str,
        field_name: str,
        expected_type: str,
        actual_type: str,
    ) -> str:
        return (
            f"Record '{_display_name(record_name)}' field '{field_name}' expects {expected_type}"
            f" but got {actual_type}"
        )

    @staticmethod
    def recursive_record_layout_detected(cycle: list[str] | tuple[str, ...]) -> str:
        cycle_text = " -> ".join(str(name) for name in cycle)
        return f"Recursive record layout detected: {cycle_text}"

    @staticmethod
    def record_constructor_argument_count_mismatch(name: str, expected: int, actual: int) -> str:
        return f"{_display_name(name)} record constructor expected {expected} argument(s) but got {actual}"

    @staticmethod
    def record_constructor_missing_required_field(record_name: str, field_name: str) -> str:
        return f"Record '{_display_name(record_name)}' missing required field: {field_name}"

    @staticmethod
    def record_field_not_defined(record_name: str, field_name: str) -> str:
        return f"Record '{_display_name(record_name)}' has no field named '{field_name}'"

    @staticmethod
    def record_fields_are_immutable(record_name: str, field_name: str) -> str:
        return f"Record '{_display_name(record_name)}' field '{field_name}' is immutable"

    @staticmethod
    def external_function_not_defined(name: str) -> str:
        return f"External function not defined: {_display_name(name)}"

    @staticmethod
    def external_function_name_collision(name: str) -> str:
        return f"External function already declared: {_display_name(name)}"

    @staticmethod
    def external_function_library_name_empty() -> str:
        return "External function library name must not be empty"

    @staticmethod
    def external_function_alias_empty() -> str:
        return "External function alias must not be empty"

    @staticmethod
    def external_function_duplicate_parameter(name: str) -> str:
        return f"External function parameter name is duplicated: {name}"

    @staticmethod
    def external_function_parameter_default_disallowed(name: str) -> str:
        return f"External function parameter default values are not allowed: {name}"

    @staticmethod
    def external_function_unknown_type(type_name: str) -> str:
        return f"External function type is unknown: {type_name}"

    @staticmethod
    def external_function_type_not_allowed(type_name: str) -> str:
        return f"External function type is not allowed in DLL signatures: {type_name}"

    @staticmethod
    def external_function_struct_not_layout_safe(type_name: str) -> str:
        return f"External function struct type is not layout-safe: {type_name}"

    @staticmethod
    def external_function_struct_return_not_supported(type_name: str) -> str:
        return f"External function struct return is not supported by the current runtime: {type_name}"

    @staticmethod
    def external_function_recursive_layout(cycle: str) -> str:
        return f"External function signature contains a recursive struct layout: {cycle}"

    @staticmethod
    def external_function_library_load_failed(library_name: str) -> str:
        return f"External function library failed to load: {library_name}"

    @staticmethod
    def external_function_export_not_found(export_name: str, library_name: str) -> str:
        return f"External function export not found: {export_name} in {library_name}"

    @staticmethod
    def external_function_unsupported_calling_convention(convention: str) -> str:
        return f"External function calling convention is not supported: {convention}"

    @staticmethod
    def external_function_argument_count_mismatch(name: str, expected: int, actual: int) -> str:
        return f"{_display_name(name)} external function expected {expected} argument(s) but got {actual}"

    @staticmethod
    def external_function_argument_type_mismatch(
        name: str,
        parameter: str,
        expected_type: str,
        actual_type: str,
    ) -> str:
        return (
            f"{_display_name(name)} external parameter '{parameter}' expects {expected_type}"
            f" but got {actual_type}"
        )

    @staticmethod
    def external_function_byref_argument_must_be_writable(name: str, parameter: str) -> str:
        return f"{_display_name(name)} external parameter '{parameter}' must be passed by reference from a writable variable or index target"

    @staticmethod
    def return_outside_function() -> str:
        return "Return statement used outside of function"

    @staticmethod
    def script_quit_exit_code_must_be_integer() -> str:
        return "ExitScript exit code must be an integer"

    @staticmethod
    def script_quit_exit_code_out_of_range() -> str:
        return "ExitScript exit code must be a signed 32-bit integer"

    @staticmethod
    def function_not_defined(name: str) -> str:
        return f"Function not defined: {_display_name(name)}"

    @staticmethod
    def function_argument_count_mismatch(name: str, expected: int, actual: int) -> str:
        return f"{_display_name(name)} expected {expected} argument(s) but got {actual}"

    @staticmethod
    def function_missing_required_argument(name: str, parameter: str) -> str:
        return f"{_display_name(name)} missing required argument: {parameter}"

    @staticmethod
    def with_call_stack(message: str, stack_text: str) -> str:
        return f"{message}\n{stack_text}"

    @staticmethod
    def maximum_call_depth_exceeded(function_name: str) -> str:
        return f"Maximum call depth exceeded in function: {_display_name(function_name)}"
