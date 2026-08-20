from __future__ import annotations

import difflib
import struct
from dataclasses import dataclass
from typing import Optional

from core.scripting import CANONICAL_TYPE_NAMES
from core.scripting import ast_nodes as ast
from core.scripting import normalize_type_name
from core.runtime.builtins.builtin_registry import (
    BUILTIN_FUNCTION_NAMES,
    format_builtin_function_name,
)
from core.scripting.diagnostics import (
    DiagnosticBag,
    TextSpan,
    make_external_function_alias_empty,
    make_external_function_calling_convention_unsupported,
    make_external_function_duplicate_parameter,
    make_external_function_library_name_empty,
    make_external_function_name_collision,
    make_external_function_parameter_default_disallowed,
    make_external_function_recursive_layout,
    make_external_function_string_buffer_size_invalid,
    make_external_function_string_buffer_size_missing,
    make_external_function_struct_not_layout_safe,
    make_external_function_struct_return_not_supported,
    make_external_function_type_not_allowed,
    make_external_function_unknown_type,
    make_invalid_external_function_declaration,
    make_duplicate_label,
    make_enum_member_name_collision,
    make_enum_name_collision,
    make_illegal_goto_target,
    make_loop_control_error,
    make_missing_goto_target,
    make_struct_layout_clause_invalid,
    make_struct_layout_clauses_mutually_exclusive,
    make_struct_layout_value_must_be_positive,
    make_struct_layout_value_must_be_power_of_two,
    make_record_name_collision,
    make_record_field_type_not_defined,
    make_record_recursive_layout,
    make_return_outside_function,
    make_unsupported_function,
    make_undefined_variable,
)
from editor.language_services.script_document_analysis import ScriptDocumentAnalysis


@dataclass(frozen=True, slots=True)
class _LabelInfo:
    name: str
    ancestry: tuple[str, ...]
    span: TextSpan


@dataclass(frozen=True, slots=True)
class _StructLayoutSummary:
    name: str
    is_layout_safe: bool
    is_blittable: bool
    size: int | None
    alignment: int | None
    packing: int | None = None
    alignment_override: int | None = None
    field_offsets: tuple[int, ...] = ()
    field_sizes: tuple[int, ...] = ()
    field_alignments: tuple[int, ...] = ()
    field_blittable: tuple[bool, ...] = ()
    field_type_names: tuple[str, ...] = ()
    cycle_path: tuple[str, ...] | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedExternalType:
    name: str
    kind: str
    is_layout_safe: bool
    is_blittable: bool
    is_byref_eligible: bool
    is_return_eligible: bool
    size: int | None = None
    alignment: int | None = None
    struct_summary: _StructLayoutSummary | None = None


def _build_builtin_argument_map(
    *tables: tuple[tuple[str, tuple[int, ...]], ...],
) -> dict[str, tuple[int, ...]]:
    mapping: dict[str, tuple[int, ...]] = {}
    for table in tables:
        for name, indexes in table:
            merged_indexes = tuple(dict.fromkeys((*mapping.get(name, ()), *indexes)))
            mapping[name] = merged_indexes
    return mapping


def _build_builtin_layout_policy() -> dict[str, tuple[int | None, int | None, bool, bool, bool, bool]]:
    pointer_size = max(1, struct.calcsize("P"))
    return {
        "Int8": (1, 1, True, True, True, True),
        "UInt8": (1, 1, True, True, True, True),
        "Int16": (2, 2, True, True, True, True),
        "UInt16": (2, 2, True, True, True, True),
        "Int32": (4, 4, True, True, True, True),
        "UInt32": (4, 4, True, True, True, True),
        "Int64": (8, 8, True, True, True, True),
        "UInt64": (8, 8, True, True, True, True),
        "Float32": (4, 4, True, True, True, True),
        "Float64": (8, 8, True, True, True, True),
        "Bool": (4, 4, True, True, True, True),
        "Char": (2, 2, True, True, True, True),
        "Ptr": (pointer_size, pointer_size, True, True, True, True),
        "IntPtr": (pointer_size, pointer_size, True, True, True, True),
        "String": (None, None, False, False, False, False),
    }


class SemanticAnalysisService:
    # Declarative source of truth for builtin argument slots we want to sanity-check.
    # Keep the categories aligned with runtime intent:
    # - integer: whole-number slots like coordinates, counts, delays, and bitwise inputs
    # - numeric: slots that accept general numeric values, including floats
    # - flags: integer-valued mode/option fields
    _INTEGER_BUILTIN_ARGUMENT_RULES: tuple[tuple[str, tuple[int, ...]], ...] = (
        ("binarymid", (1, 2)),
        ("bitand", (0, 1)),
        ("bitnot", (0,)),
        ("bitnotunsigned", (0,)),
        ("bitor", (0, 1)),
        ("bitrotate", (0, 1)),
        ("bitshift", (0, 1)),
        ("bitxor", (0, 1)),
        ("chr", (0,)),
        ("chrw", (0,)),
        ("keypress", (1,)),
        ("mousemove", (0, 1, 2)),
        ("mouseclick", (1, 2, 3, 4)),
        ("mouseclickdrag", (1, 2, 3, 4, 5)),
        ("mousedrag", (1, 2, 3, 4, 5)),
        ("setmousemovespeed", (0,)),
        ("mousewheel", (0,)),
        ("msgbox", (3, 4)),
        ("pixelgetcolor", (0, 1, 2)),
        ("pixelsearch", (0, 1, 2, 3, 4, 5, 6, 7)),
        ("setcurrenteventdelay", (0,)),
        ("sleep", (0,)),
        ("stringcompare", (2,)),
        ("stringinstr", (2, 3, 4, 5)),
        ("stringleft", (1,)),
        ("stringmid", (1, 2)),
        ("stringreplace", (1, 3, 4)),
        ("stringright", (1,)),
        ("stringtrimleft", (1,)),
        ("stringtrimright", (1,)),
        ("round", (1,)),
    )
    _NUMERIC_BUILTIN_ARGUMENT_RULES: tuple[tuple[str, tuple[int, ...]], ...] = (
        ("abs", (0,)),
        ("ceiling", (0,)),
        ("exp", (0,)),
        ("floor", (0,)),
        ("int", (0,)),
        ("round", (0,)),
        ("mod", (0, 1)),
    )
    _FLAG_BUILTIN_ARGUMENT_RULES: tuple[tuple[str, tuple[int, ...]], ...] = (
        ("binarytostring", (1,)),
        ("msgbox", (0,)),
    )
    _BUILTIN_ARGUMENT_INDEXES: dict[str, tuple[int, ...]] = _build_builtin_argument_map(
        _INTEGER_BUILTIN_ARGUMENT_RULES,
        _NUMERIC_BUILTIN_ARGUMENT_RULES,
        _FLAG_BUILTIN_ARGUMENT_RULES,
    )
    _BUILTIN_LAYOUT_POLICY = _build_builtin_layout_policy()
    _FUNCTION_REPLACEMENT_SIMILARITY_THRESHOLD_BY_LENGTH: tuple[tuple[int, float], ...] = (
        (4, 0.88),
        (8, 0.8),
        (12, 0.76),
    )

    def __init__(self) -> None:
        self._scope_counter = 0
        self._function_scope_keys: dict[int, tuple[str, ...]] = {}
        self._function_declarations: list[ast.FunctionDecl] = []
        self._struct_declarations: list[ast.StructDecl] = []
        self._record_declarations: list[ast.RecordDecl] = []
        self._enum_declarations: list[ast.EnumDecl] = []
        self._external_function_declarations: list[ast.ExternalFunctionDecl] = []
        self._struct_declarations_by_name: dict[str, ast.StructDecl] = {}
        self._record_declarations_by_name: dict[str, ast.RecordDecl] = {}
        self._enum_declarations_by_name: dict[str, ast.EnumDecl] = {}
        self._declared_function_names: set[str] = set()
        self._declared_function_display_names: dict[str, str] = {}
        self._declared_struct_names: set[str] = set()
        self._declared_struct_display_names: dict[str, str] = {}
        self._declared_record_names: set[str] = set()
        self._declared_record_display_names: dict[str, str] = {}
        self._declared_enum_names: set[str] = set()
        self._declared_enum_display_names: dict[str, str] = {}
        self._declared_external_function_names: set[str] = set()
        self._declared_external_function_display_names: dict[str, str] = {}
        self._struct_layout_cache: dict[str, _StructLayoutSummary] = {}
        self._struct_layout_in_progress: set[str] = set()
        self._struct_layout_stack: list[str] = []
        self._document_source_name: str | None = None

    def analyze(self, analysis: ScriptDocumentAnalysis) -> DiagnosticBag:
        diagnostics = DiagnosticBag()
        labels_by_scope: dict[tuple[str, ...], dict[str, _LabelInfo]] = {}
        global_names = self._collect_global_names(analysis.root.statements)
        self._scope_counter = 0
        self._function_scope_keys.clear()
        self._function_declarations.clear()
        self._struct_declarations.clear()
        self._record_declarations.clear()
        self._enum_declarations.clear()
        self._external_function_declarations.clear()
        self._struct_declarations_by_name.clear()
        self._record_declarations_by_name.clear()
        self._enum_declarations_by_name.clear()
        self._struct_layout_cache.clear()
        self._struct_layout_in_progress.clear()
        self._struct_layout_stack.clear()
        self._document_source_name = analysis.document_id

        global_scope = ("global",)
        self._collect_scope(
            analysis.root.statements,
            scope_key=global_scope,
            ancestry=global_scope,
            labels_by_scope=labels_by_scope,
            diagnostics=diagnostics,
        )
        self._validate_scope(
            analysis.root.statements,
            scope_key=global_scope,
            ancestry=global_scope,
            labels_by_scope=labels_by_scope,
            diagnostics=diagnostics,
            function_depth=0,
            loop_stack=(),
        )
        self._declared_function_names = self._collect_declared_function_names()
        self._declared_function_display_names = self._collect_declared_function_display_names()
        self._declared_struct_names = self._collect_declared_struct_names()
        self._declared_struct_display_names = self._collect_declared_struct_display_names()
        self._declared_record_names = self._collect_declared_record_names()
        self._declared_record_display_names = self._collect_declared_record_display_names()
        self._declared_enum_names = self._collect_declared_enum_names()
        self._declared_enum_display_names = self._collect_declared_enum_display_names()
        self._declared_external_function_names = self._collect_declared_external_function_names()
        self._declared_external_function_display_names = (
            self._collect_declared_external_function_display_names()
        )
        self._validate_sleep_calls(
            analysis.root.statements,
            visible_names=set(global_names),
            global_names=global_names,
            diagnostics=diagnostics,
        )
        self._collect_struct_declaration_map()
        self._collect_record_declaration_map()
        self._collect_enum_declaration_map()
        self._validate_struct_layout_clauses(diagnostics)
        self._validate_record_definitions(diagnostics)
        self._validate_enum_definitions(diagnostics)
        self._validate_external_function_declarations(diagnostics)
        return diagnostics

    def _collect_global_names(self, statements: list[ast.Statement]) -> set[str]:
        names: set[str] = set()
        self._collect_scope_names(statements, names)
        return names

    def _collect_scope_names(self, statements: list[ast.Statement], names: set[str]) -> None:
        for statement in statements:
            if isinstance(statement, ast.VarDecl):
                for declarator in statement.declarators:
                    name = self._normalize_lookup_name(declarator.name)
                    if name is not None:
                        names.add(name)
                continue

            if isinstance(statement, ast.ConstDecl):
                for declarator in statement.declarators:
                    name = self._normalize_lookup_name(declarator.name)
                    if name is not None:
                        names.add(name)
                continue

            if isinstance(statement, ast.EnumDecl):
                for member in statement.members:
                    name = self._normalize_lookup_name(member.name)
                    if name is not None:
                        names.add(name)
                continue

            if isinstance(statement, ast.ForStatement):
                variable_name = self._statement_identifier_name(statement.variable)
                if variable_name is not None:
                    names.add(variable_name)
                self._collect_scope_names(statement.body.statements, names)
                continue

            if isinstance(statement, ast.IfStatement):
                self._collect_scope_names(statement.then_branch.statements, names)
                if statement.else_branch is not None:
                    self._collect_scope_names(statement.else_branch.statements, names)
                continue

            if isinstance(statement, ast.SelectStatement):
                for case_arm in statement.cases:
                    self._collect_scope_names(case_arm.body.statements, names)
                continue

            if isinstance(statement, ast.WhileStatement):
                self._collect_scope_names(statement.body.statements, names)
                continue

            if isinstance(statement, ast.LoopStatement):
                self._collect_scope_names(statement.body.statements, names)
                continue

            if isinstance(statement, ast.Block):
                self._collect_scope_names(statement.statements, names)

    def _validate_sleep_calls(
        self,
        statements: list[ast.Statement],
        *,
        visible_names: set[str],
        global_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.VarDecl):
                for declarator in statement.declarators:
                    self._validate_sleep_calls_in_expression(
                        declarator.initializer,
                        visible_names=visible_names,
                        diagnostics=diagnostics,
                    )
                    name = self._normalize_lookup_name(declarator.name)
                    if name is not None:
                        visible_names.add(name)
                continue

            if isinstance(statement, ast.ConstDecl):
                for declarator in statement.declarators:
                    self._validate_sleep_calls_in_expression(
                        declarator.initializer,
                        visible_names=visible_names,
                        diagnostics=diagnostics,
                    )
                    name = self._normalize_lookup_name(declarator.name)
                    if name is not None:
                        visible_names.add(name)
                continue

            if isinstance(statement, ast.EnumDecl):
                for member in statement.members:
                    self._validate_sleep_calls_in_expression(
                        member.initializer,
                        visible_names=visible_names,
                        diagnostics=diagnostics,
                    )
                    name = self._normalize_lookup_name(member.name)
                    if name is not None:
                        visible_names.add(name)
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._validate_function_scope_sleep_calls(
                    statement,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.StructDecl):
                self._validate_struct_field_defaults(
                    statement.fields,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.IfStatement):
                self._validate_sleep_calls_in_expression(
                    statement.condition,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls(
                    statement.then_branch.statements,
                    visible_names=visible_names,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                if statement.else_branch is not None:
                    self._validate_sleep_calls(
                        statement.else_branch.statements,
                        visible_names=visible_names,
                        global_names=global_names,
                        diagnostics=diagnostics,
                    )
                continue

            if isinstance(statement, ast.SelectStatement):
                self._validate_sleep_calls_in_expression(
                    statement.expression,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                for case_arm in statement.cases:
                    for condition in case_arm.conditions:
                        if isinstance(condition, ast.SelectCaseValue):
                            self._validate_sleep_calls_in_expression(
                                condition.expression,
                                visible_names=visible_names,
                                diagnostics=diagnostics,
                            )
                        elif isinstance(condition, ast.SelectCaseRange):
                            self._validate_sleep_calls_in_expression(
                                condition.start,
                                visible_names=visible_names,
                                diagnostics=diagnostics,
                            )
                            self._validate_sleep_calls_in_expression(
                                condition.end,
                                visible_names=visible_names,
                                diagnostics=diagnostics,
                            )
                        elif isinstance(condition, ast.SelectCaseComparison):
                            self._validate_sleep_calls_in_expression(
                                condition.expression,
                                visible_names=visible_names,
                                diagnostics=diagnostics,
                            )
                        elif isinstance(condition, ast.SelectCaseLike):
                            self._validate_sleep_calls_in_expression(
                                condition.pattern,
                                visible_names=visible_names,
                                diagnostics=diagnostics,
                            )
                    self._validate_sleep_calls(
                        case_arm.body.statements,
                        visible_names=visible_names,
                        global_names=global_names,
                        diagnostics=diagnostics,
                    )
                continue

            if isinstance(statement, ast.ForStatement):
                self._validate_sleep_calls_in_expression(
                    statement.start,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls_in_expression(
                    statement.stop,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls_in_expression(
                    statement.step,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                variable_name = self._statement_identifier_name(statement.variable)
                if variable_name is not None:
                    visible_names.add(variable_name)
                self._validate_sleep_calls(
                    statement.body.statements,
                    visible_names=visible_names,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.WhileStatement):
                self._validate_sleep_calls_in_expression(
                    statement.condition,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls(
                    statement.body.statements,
                    visible_names=visible_names,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.LoopStatement):
                self._validate_sleep_calls_in_expression(
                    statement.condition,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls(
                    statement.body.statements,
                    visible_names=visible_names,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.Block):
                self._validate_sleep_calls(
                    statement.statements,
                    visible_names=visible_names,
                    global_names=global_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.ReturnStatement):
                self._validate_sleep_calls_in_expression(
                    statement.value,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.ScriptQuitStatement):
                self._validate_sleep_calls_in_expression(
                    statement.value,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.Assignment):
                self._validate_assignment_target(
                    statement.target,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                self._validate_sleep_calls_in_expression(
                    statement.value,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.ExpressionStatement):
                self._validate_sleep_calls_in_expression(
                    statement.expression,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )

    def _validate_function_scope_sleep_calls(
        self,
        statement: ast.FunctionDecl,
        *,
        global_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        visible_names = set(global_names)
        for param in statement.params:
            self._validate_sleep_calls_in_expression(
                param.default,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            name = self._normalize_lookup_name(param.name)
            if name is not None:
                visible_names.add(name)

        self._validate_sleep_calls(
            statement.body.statements,
            visible_names=visible_names,
            global_names=global_names,
            diagnostics=diagnostics,
        )

    def _validate_struct_field_defaults(
        self,
        fields: list[ast.StructFieldDecl],
        *,
        visible_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        for field in fields:
            self._validate_sleep_calls_in_expression(
                field.initializer,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )

    def _validate_struct_layout_clauses(self, diagnostics: DiagnosticBag) -> None:
        for declaration in self._struct_declarations:
            span = self._span(declaration)
            has_packing = declaration.packing is not None
            has_alignment = declaration.alignment is not None

            if has_packing and has_alignment:
                diagnostics.add(
                    make_struct_layout_clauses_mutually_exclusive(
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                continue

            if has_packing:
                self._validate_struct_layout_clause_value(
                    declaration,
                    clause_name="Packed",
                    value=declaration.packing,
                    diagnostics=diagnostics,
                )
                continue

            if has_alignment:
                self._validate_struct_layout_clause_value(
                    declaration,
                    clause_name="Align",
                    value=declaration.alignment,
                    diagnostics=diagnostics,
                )
                summary = self._build_struct_layout_summary(declaration.name)
                if summary.rejection_reason == (
                    f"Struct alignment cannot be honored by the current runtime: "
                    f"Align({declaration.alignment})"
                ):
                    diagnostics.error(
                        "SEM027",
                        summary.rejection_reason,
                        span,
                    source_name=self._source_name(declaration),
                )

    def _validate_record_definitions(self, diagnostics: DiagnosticBag) -> None:
        seen_record_names: set[str] = set()
        for declaration in self._record_declarations:
            span = self._span(declaration)
            name = self._normalize_name(declaration.name)
            if name is None:
                continue

            normalized_name = name.lower()
            if (
                normalized_name in seen_record_names
                or normalized_name in BUILTIN_FUNCTION_NAMES
                or normalized_name in self._declared_function_names
                or normalized_name in self._declared_struct_names
                or normalized_name in self._declared_external_function_names
                or normalized_name in self._declared_enum_names
            ):
                diagnostics.add(
                    make_record_name_collision(
                        name,
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                continue

            seen_record_names.add(normalized_name)
            self._validate_record_field_defaults(
                declaration.fields,
                visible_names=set(),
                diagnostics=diagnostics,
            )

        self._validate_record_field_types(diagnostics)
        self._validate_record_layout_cycles(diagnostics)

    def _validate_enum_definitions(self, diagnostics: DiagnosticBag) -> None:
        seen_enum_names: set[str] = set()
        for declaration in self._enum_declarations:
            span = self._span(declaration)
            name = self._normalize_name(declaration.name)
            if name is None:
                continue

            normalized_name = name.lower()
            if (
                normalized_name in seen_enum_names
                or normalized_name in BUILTIN_FUNCTION_NAMES
                or normalized_name in self._declared_function_names
                or normalized_name in self._declared_struct_names
                or normalized_name in self._declared_record_names
                or normalized_name in self._declared_external_function_names
            ):
                diagnostics.add(
                    make_enum_name_collision(
                        name,
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                continue

            seen_enum_names.add(normalized_name)
            seen_member_names: set[str] = set()
            for member in declaration.members:
                member_name = self._normalize_name(member.name)
                if member_name is None:
                    continue
                normalized_member_name = member_name.lower()
                if (
                    normalized_member_name in seen_member_names
                    or normalized_member_name == normalized_name
                    or normalized_member_name in BUILTIN_FUNCTION_NAMES
                    or normalized_member_name in self._declared_function_names
                    or normalized_member_name in self._declared_struct_names
                    or normalized_member_name in self._declared_record_names
                    or normalized_member_name in self._declared_external_function_names
                    or normalized_member_name in self._declared_enum_names
                ):
                    member_span = self._span(member)
                    diagnostics.add(
                        make_enum_member_name_collision(
                            name,
                            member_name,
                            member_span.start,
                            member_span.end,
                            source_name=self._source_name(member),
                        )
                    )
                    continue
                seen_member_names.add(normalized_member_name)

    def _validate_struct_layout_clause_value(
        self,
        declaration: ast.StructDecl,
        *,
        clause_name: str,
        value: int | None,
        diagnostics: DiagnosticBag,
    ) -> None:
        span = self._span(declaration)
        clause = f"{clause_name}({value})"
        if value is None:
            diagnostics.add(
                make_struct_layout_clause_invalid(
                    clause,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        if value <= 0:
            diagnostics.add(
                make_struct_layout_value_must_be_positive(
                    clause,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        if value & (value - 1) != 0:
            diagnostics.add(
                make_struct_layout_value_must_be_power_of_two(
                    clause,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )

    def _validate_record_field_defaults(
        self,
        fields: list[ast.RecordFieldDecl],
        *,
        visible_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        for field in fields:
            self._validate_sleep_calls_in_expression(
                field.initializer,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )

    def _validate_record_field_types(self, diagnostics: DiagnosticBag) -> None:
        for declaration in self._record_declarations:
            span = self._span(declaration)
            for field in declaration.fields:
                expected_type_name = normalize_type_name(field.type_name)
                if not expected_type_name:
                    diagnostics.add(
                        make_record_field_type_not_defined(
                            declaration.name,
                            field.name,
                            field.type_name,
                            span.start,
                            span.end,
                            source_name=self._source_name(declaration),
                        )
                    )
                    continue

                if (
                    expected_type_name in CANONICAL_TYPE_NAMES
                    or expected_type_name.lower() in self._declared_enum_names
                ):
                    continue

                if (
                    expected_type_name.lower() not in self._declared_struct_names
                    and expected_type_name.lower() not in self._declared_record_names
                ):
                    diagnostics.add(
                        make_record_field_type_not_defined(
                            declaration.name,
                            field.name,
                            expected_type_name,
                            span.start,
                            span.end,
                            source_name=self._source_name(declaration),
                        )
                    )

    def _validate_record_layout_cycles(self, diagnostics: DiagnosticBag) -> None:
        adjacency: dict[str, tuple[str, ...]] = {}
        for declaration in self._record_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            referenced_records: list[str] = []
            for field in declaration.fields:
                expected_type_name = normalize_type_name(field.type_name)
                if expected_type_name is None:
                    continue
                if (
                    expected_type_name.lower() in self._declared_record_names
                    or expected_type_name.lower() in self._declared_enum_names
                ):
                    referenced_records.append(expected_type_name.lower())
            adjacency[normalized_name] = tuple(dict.fromkeys(referenced_records))

        visited: set[str] = set()
        active: set[str] = set()
        path: list[str] = []

        def visit(record_name: str) -> None:
            if record_name in active:
                cycle_start = path.index(record_name)
                cycle = path[cycle_start:] + [record_name]
                declaration = self._record_declarations_by_name.get(record_name)
                span = self._span(declaration) if declaration is not None else TextSpan(0, 1)
                diagnostics.add(
                    make_record_recursive_layout(
                        " -> ".join(self._display_record_name(name) for name in cycle),
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration) if declaration is not None else self._document_source_name,
                    )
                )
                return

            if record_name in visited:
                return

            visited.add(record_name)
            active.add(record_name)
            path.append(record_name)
            try:
                for referenced_name in adjacency.get(record_name, ()):
                    visit(referenced_name.lower())
            finally:
                path.pop()
                active.remove(record_name)

        for record_name in adjacency:
            if record_name not in visited:
                visit(record_name)

    def _validate_sleep_calls_in_expression(
        self,
        expression: ast.Expression | None,
        *,
        visible_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        if expression is None:
            return

        if isinstance(expression, ast.Identifier):
            return

        if isinstance(expression, ast.HostIdentifier):
            return

        if isinstance(expression, ast.ParenExpr):
            self._validate_sleep_calls_in_expression(
                expression.expression,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        if isinstance(expression, ast.UnaryExpr):
            self._validate_sleep_calls_in_expression(
                expression.operand,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        if isinstance(expression, ast.BinaryExpr):
            self._validate_sleep_calls_in_expression(
                expression.left,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            if expression.operator != ".":
                self._validate_sleep_calls_in_expression(
                    expression.right,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
            return

        if isinstance(expression, ast.TernaryExpr):
            self._validate_sleep_calls_in_expression(
                expression.condition,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            self._validate_sleep_calls_in_expression(
                expression.true_expression,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            self._validate_sleep_calls_in_expression(
                expression.false_expression,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        if isinstance(expression, ast.CallExpr):
            self._validate_known_function_call(
                expression,
                diagnostics=diagnostics,
            )
            self._validate_numeric_builtin_call_arguments(
                expression,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            self._validate_sleep_calls_in_expression(
                expression.callee,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            for arg in expression.args:
                self._validate_sleep_calls_in_expression(
                    arg,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
            return

        if isinstance(expression, ast.IndexExpr):
            self._validate_sleep_calls_in_expression(
                expression.base,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            self._validate_sleep_calls_in_expression(
                expression.index,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        if isinstance(expression, ast.ArrayLiteral):
            for item in expression.items:
                self._validate_sleep_calls_in_expression(
                    item,
                    visible_names=visible_names,
                    diagnostics=diagnostics,
                )
            return

        if isinstance(expression, ast.InterpolatedStringLiteral):
            for part in expression.parts:
                if isinstance(part, ast.InterpolationPart):
                    self._validate_sleep_calls_in_expression(
                        part.expression,
                        visible_names=visible_names,
                        diagnostics=diagnostics,
                    )

    def _validate_known_function_call(
        self,
        expression: ast.CallExpr,
        *,
        diagnostics: DiagnosticBag,
    ) -> None:
        callee = expression.callee
        if not isinstance(callee, ast.Identifier):
            return

        function_name = str(callee.name).strip()
        if not function_name:
            return

        normalized_name = function_name.lower()
        if normalized_name in BUILTIN_FUNCTION_NAMES:
            return
        if normalized_name in self._declared_function_names:
            return
        if normalized_name in self._declared_struct_names:
            return
        if normalized_name in self._declared_record_names:
            return
        if normalized_name in self._declared_external_function_names:
            return

        span = self._span(callee)
        diagnostics.add(
            make_unsupported_function(
                function_name,
                span.start,
                span.end,
                source_name=self._source_name(callee),
                suggested_replacement=self._suggest_function_replacement(normalized_name),
            )
        )

    def _validate_numeric_builtin_call_arguments(
        self,
        expression: ast.CallExpr,
        *,
        visible_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        callee = expression.callee
        if not isinstance(callee, ast.Identifier):
            return

        argument_indexes = self._BUILTIN_ARGUMENT_INDEXES.get(callee.name.strip().lower())
        if argument_indexes is None:
            return

        for index in argument_indexes:
            if index >= len(expression.args):
                continue
            argument = expression.args[index]
            while isinstance(argument, ast.ParenExpr) and argument.expression is not None:
                argument = argument.expression
            if not isinstance(argument, ast.Identifier):
                continue

            name = self._normalize_name(argument.name)
            lookup_name = self._normalize_lookup_name(argument.name)
            if lookup_name is None or lookup_name in visible_names:
                continue

            span = self._span(argument)
            diagnostics.add(
                make_undefined_variable(
                    name,
                    span.start,
                    span.end,
                    source_name=self._source_name(argument),
                )
            )

    def _validate_assignment_target(
        self,
        target: ast.Expression | None,
        *,
        visible_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        if target is None or isinstance(target, ast.Identifier):
            return

        if isinstance(target, ast.BinaryExpr) and target.operator == ".":
            self._validate_sleep_calls_in_expression(
                target.left,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        if isinstance(target, ast.IndexExpr):
            self._validate_sleep_calls_in_expression(
                target.base,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            self._validate_sleep_calls_in_expression(
                target.index,
                visible_names=visible_names,
                diagnostics=diagnostics,
            )
            return

        self._validate_sleep_calls_in_expression(
            target,
            visible_names=visible_names,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _normalize_name(name: str | None) -> str | None:
        if name is None:
            return None
        normalized = str(name).strip()
        return normalized or None

    @staticmethod
    def _normalize_lookup_name(name: str | None) -> str | None:
        normalized = SemanticAnalysisService._normalize_name(name)
        if normalized is None:
            return None
        return normalized.lower()

    @staticmethod
    def _statement_identifier_name(expression: ast.Expression | None) -> str | None:
        if isinstance(expression, ast.Identifier):
            normalized = str(expression.name).strip().lower()
            return normalized or None
        return None

    def _collect_scope(
        self,
        statements: list[ast.Statement],
        *,
        scope_key: tuple[str, ...],
        ancestry: tuple[str, ...],
        labels_by_scope: dict[tuple[str, ...], dict[str, _LabelInfo]],
        diagnostics: DiagnosticBag,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.LabelStatement):
                self._collect_label(
                    statement,
                    scope_key=scope_key,
                    ancestry=ancestry,
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.FunctionDecl):
                self._function_declarations.append(statement)
                child_scope_key = self._allocate_scope_key(statement.name)
                self._function_scope_keys[id(statement)] = child_scope_key
                self._collect_scope(
                    statement.body.statements,
                    scope_key=child_scope_key,
                    ancestry=child_scope_key,
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.StructDecl):
                self._struct_declarations.append(statement)
                continue

            if isinstance(statement, ast.RecordDecl):
                self._record_declarations.append(statement)
                continue

            if isinstance(statement, ast.EnumDecl):
                self._enum_declarations.append(statement)
                continue

            if isinstance(statement, ast.ExternalFunctionDecl):
                self._external_function_declarations.append(statement)
                continue

            if isinstance(statement, ast.IfStatement):
                self._collect_scope(
                    statement.then_branch.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("then",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                if statement.else_branch is not None:
                    self._collect_scope(
                        statement.else_branch.statements,
                        scope_key=scope_key,
                        ancestry=ancestry + ("else",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.SelectStatement):
                select_ancestry = ancestry + ("select",)
                for case_index, case_arm in enumerate(statement.cases):
                    case_ancestry = select_ancestry + (f"case:{case_index}",)
                    self._collect_scope(
                        case_arm.body.statements,
                        scope_key=scope_key,
                        ancestry=case_ancestry,
                        labels_by_scope=labels_by_scope,
                        diagnostics=diagnostics,
                    )
                continue

            if isinstance(statement, ast.ForStatement):
                self._collect_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("for",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.WhileStatement):
                self._collect_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("while",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.LoopStatement):
                self._collect_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("loop",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.Block):
                self._collect_scope(
                    statement.statements,
                    scope_key=scope_key,
                    ancestry=ancestry,
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                )

    def _collect_declared_function_names(self) -> set[str]:
        names: set[str] = set()
        for declaration in self._function_declarations:
            name = self._normalize_name(declaration.name)
            if name is not None:
                names.add(name.lower())
        return names

    def _collect_declared_function_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for declaration in self._function_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            names.setdefault(normalized_name, name)
        return names

    def _collect_declared_struct_names(self) -> set[str]:
        names: set[str] = set()
        for declaration in self._struct_declarations:
            name = self._normalize_name(declaration.name)
            if name is not None:
                names.add(name.lower())
        return names

    def _collect_declared_struct_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for declaration in self._struct_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            names.setdefault(normalized_name, name)
        return names

    def _collect_declared_record_names(self) -> set[str]:
        names: set[str] = set()
        for declaration in self._record_declarations:
            name = self._normalize_name(declaration.name)
            if name is not None:
                names.add(name.lower())
        return names

    def _collect_declared_record_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for declaration in self._record_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            names.setdefault(normalized_name, name)
        return names

    def _collect_declared_enum_names(self) -> set[str]:
        names: set[str] = set()
        for declaration in self._enum_declarations:
            name = self._normalize_name(declaration.name)
            if name is not None:
                names.add(name.lower())
        return names

    def _collect_declared_enum_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for declaration in self._enum_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            names.setdefault(normalized_name, name)
        return names

    def _collect_declared_external_function_names(self) -> set[str]:
        names: set[str] = set()
        for declaration in self._external_function_declarations:
            name = self._normalize_name(declaration.name)
            if name is not None:
                names.add(name.lower())
        return names

    def _collect_declared_external_function_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for declaration in self._external_function_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            normalized_name = name.lower()
            names.setdefault(normalized_name, name)
        return names

    def _collect_struct_declaration_map(self) -> None:
        self._struct_declarations_by_name.clear()
        for declaration in self._struct_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            self._struct_declarations_by_name.setdefault(name.lower(), declaration)

    def _collect_record_declaration_map(self) -> None:
        self._record_declarations_by_name.clear()
        for declaration in self._record_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            self._record_declarations_by_name.setdefault(name.lower(), declaration)

    def _collect_enum_declaration_map(self) -> None:
        self._enum_declarations_by_name.clear()
        for declaration in self._enum_declarations:
            name = self._normalize_name(declaration.name)
            if name is None:
                continue
            self._enum_declarations_by_name.setdefault(name.lower(), declaration)

    def _display_struct_name(self, normalized_name: str) -> str:
        declaration = self._struct_declarations_by_name.get(normalized_name.lower())
        if declaration is not None:
            display_name = self._normalize_name(declaration.name)
            if display_name is not None:
                return display_name
        return normalized_name

    def _display_record_name(self, normalized_name: str) -> str:
        declaration = self._record_declarations_by_name.get(normalized_name.lower())
        if declaration is not None:
            display_name = self._normalize_name(declaration.name)
            if display_name is not None:
                return display_name
        return normalized_name

    def _display_enum_name(self, normalized_name: str) -> str:
        declaration = self._enum_declarations_by_name.get(normalized_name.lower())
        if declaration is not None:
            display_name = self._normalize_name(declaration.name)
            if display_name is not None:
                return display_name
        return normalized_name

    def _validate_external_function_declarations(self, diagnostics: DiagnosticBag) -> None:
        seen_external_names: set[str] = set()
        for declaration in self._external_function_declarations:
            self._validate_external_function_decl(
                declaration,
                seen_external_names=seen_external_names,
                diagnostics=diagnostics,
            )

    def _validate_external_function_decl(
        self,
        declaration: ast.ExternalFunctionDecl,
        *,
        seen_external_names: set[str],
        diagnostics: DiagnosticBag,
    ) -> None:
        span = self._span(declaration)
        name = self._normalize_name(declaration.name)
        if name is None:
            diagnostics.add(
                make_invalid_external_function_declaration(
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        normalized_name = name.lower()
        if (
            normalized_name in seen_external_names
            or normalized_name in BUILTIN_FUNCTION_NAMES
            or normalized_name in self._declared_function_names
            or normalized_name in self._declared_struct_names
            or normalized_name in self._declared_record_names
        ):
            diagnostics.add(
                make_external_function_name_collision(
                    name,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        seen_external_names.add(normalized_name)

        if not str(declaration.library_name).strip():
            diagnostics.add(
                make_external_function_library_name_empty(
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        if declaration.export_name is not None and not str(declaration.export_name).strip():
            diagnostics.add(
                make_external_function_alias_empty(
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        normalized_calling_convention = str(getattr(declaration, "calling_convention", "winapi") or "winapi").strip().lower()
        if normalized_calling_convention not in {"default", "winapi", "stdcall", "cdecl"}:
            diagnostics.add(
                make_external_function_calling_convention_unsupported(
                    normalized_calling_convention,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        seen_params: set[str] = set()
        for param in declaration.params:
            param_name = self._normalize_name(param.name)
            if param_name is None:
                diagnostics.add(
                    make_invalid_external_function_declaration(
                        self._span(param).start,
                        self._span(param).end,
                        source_name=self._source_name(param),
                    )
                )
                return

            normalized_param_name = param_name.lower()
            if normalized_param_name in seen_params:
                param_span = self._span(param)
                diagnostics.add(
                    make_external_function_duplicate_parameter(
                        param_name,
                        param_span.start,
                        param_span.end,
                        source_name=self._source_name(param),
                    )
                )
                return
            seen_params.add(normalized_param_name)

            if param.default is not None:
                param_span = self._span(param)
                diagnostics.add(
                    make_external_function_parameter_default_disallowed(
                        param_name,
                        param_span.start,
                        param_span.end,
                        source_name=self._source_name(param),
                    )
                )
                return

            buffer_size = self._normalize_external_string_buffer_size(param.string_buffer_size)
            if param.string_buffer_size is not None and buffer_size is None:
                param_span = self._span(param)
                diagnostics.add(
                    make_external_function_string_buffer_size_invalid(
                        param_name,
                        param_span.start,
                        param_span.end,
                        source_name=self._source_name(param),
                    )
                )
                return

            resolved_type = self._resolve_external_type(param.type_name)
            if resolved_type is None:
                param_span = self._span(param)
                diagnostics.add(
                    make_external_function_unknown_type(
                        str(param.type_name).strip() or "<unknown>",
                        param_span.start,
                        param_span.end,
                        source_name=self._source_name(param),
                    )
                )
                return

            if resolved_type.name == "String":
                if param.is_byref:
                    if buffer_size is None:
                        param_span = self._span(param)
                        diagnostics.add(
                            make_external_function_string_buffer_size_missing(
                                param_name,
                                param_span.start,
                                param_span.end,
                                source_name=self._source_name(param),
                            )
                        )
                        return
                    if buffer_size is not None and buffer_size <= 0:
                        param_span = self._span(param)
                        diagnostics.add(
                            make_external_function_string_buffer_size_invalid(
                                param_name,
                                param_span.start,
                                param_span.end,
                                source_name=self._source_name(param),
                            )
                        )
                        return
                continue

            if not resolved_type.is_layout_safe or not resolved_type.is_blittable:
                param_span = self._span(param)
                if resolved_type.kind == "builtin":
                    diagnostics.add(
                        make_external_function_type_not_allowed(
                            resolved_type.name,
                            param_span.start,
                            param_span.end,
                            source_name=self._source_name(param),
                        )
                    )
                elif resolved_type.struct_summary is not None and resolved_type.struct_summary.cycle_path is not None:
                    diagnostics.add(
                        make_external_function_recursive_layout(
                            " -> ".join(resolved_type.struct_summary.cycle_path),
                            param_span.start,
                            param_span.end,
                            source_name=self._source_name(param),
                        )
                    )
                else:
                    diagnostics.add(
                        make_external_function_struct_not_layout_safe(
                            resolved_type.name,
                            param_span.start,
                            param_span.end,
                            source_name=self._source_name(param),
                        )
                    )
                return

        if not declaration.return_type_name:
            if getattr(declaration, "is_sub", False):
                return
            diagnostics.add(
                make_invalid_external_function_declaration(
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        resolved_return_type = self._resolve_external_type(declaration.return_type_name)
        if resolved_return_type is None:
            diagnostics.add(
                make_external_function_unknown_type(
                    declaration.return_type_name,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

        if resolved_return_type.name == "String":
            return

        if resolved_return_type.kind == "struct":
            pointer_size = max(1, struct.calcsize("P"))
            if (
                resolved_return_type.struct_summary is None
                or resolved_return_type.struct_summary.size is None
                or resolved_return_type.struct_summary.size > pointer_size
            ):
                diagnostics.add(
                    make_external_function_struct_return_not_supported(
                        resolved_return_type.name,
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                return

        if not resolved_return_type.is_layout_safe or not resolved_return_type.is_blittable:
            if resolved_return_type.kind == "builtin":
                diagnostics.add(
                    make_external_function_type_not_allowed(
                        resolved_return_type.name,
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                return

            if resolved_return_type.struct_summary is not None and resolved_return_type.struct_summary.cycle_path is not None:
                diagnostics.add(
                    make_external_function_recursive_layout(
                        " -> ".join(resolved_return_type.struct_summary.cycle_path),
                        span.start,
                        span.end,
                        source_name=self._source_name(declaration),
                    )
                )
                return

            diagnostics.add(
                make_external_function_struct_not_layout_safe(
                    resolved_return_type.name,
                    span.start,
                    span.end,
                    source_name=self._source_name(declaration),
                )
            )
            return

    def _resolve_external_type(self, type_name: str) -> _ResolvedExternalType | None:
        normalized_name = normalize_type_name(type_name)
        if not normalized_name:
            return None

        if normalized_name == "String":
            pointer_size = max(1, struct.calcsize("P"))
            return _ResolvedExternalType(
                name="String",
                kind="builtin",
                is_layout_safe=False,
                is_blittable=False,
                is_byref_eligible=True,
                is_return_eligible=True,
                size=pointer_size,
                alignment=pointer_size,
            )

        if normalized_name.lower() in self._declared_enum_names:
            size, alignment, is_layout_safe, is_blittable, is_byref_eligible, is_return_eligible = self._BUILTIN_LAYOUT_POLICY["Int32"]
            return _ResolvedExternalType(
                name=normalized_name,
                kind="builtin",
                is_layout_safe=is_layout_safe,
                is_blittable=is_blittable,
                is_byref_eligible=is_byref_eligible,
                is_return_eligible=is_return_eligible,
                size=size,
                alignment=alignment,
            )

        builtin_policy = self._BUILTIN_LAYOUT_POLICY.get(normalized_name)
        if builtin_policy is not None:
            size, alignment, is_layout_safe, is_blittable, is_byref_eligible, is_return_eligible = builtin_policy
            return _ResolvedExternalType(
                name=normalized_name,
                kind="builtin",
                is_layout_safe=is_layout_safe,
                is_blittable=is_blittable,
                is_byref_eligible=is_byref_eligible,
                is_return_eligible=is_return_eligible,
                size=size,
                alignment=alignment,
            )

        struct_decl = self._struct_declarations_by_name.get(normalized_name.lower())
        if struct_decl is None:
            return None

        summary = self._build_struct_layout_summary(normalized_name)
        return _ResolvedExternalType(
            name=normalized_name,
            kind="struct",
            is_layout_safe=summary.is_layout_safe,
            is_blittable=summary.is_blittable,
            is_byref_eligible=summary.is_layout_safe and summary.is_blittable,
            is_return_eligible=(
                summary.is_layout_safe
                and summary.is_blittable
                and summary.size is not None
                and summary.size <= max(1, struct.calcsize("P"))
            ),
            size=summary.size,
            alignment=summary.alignment,
            struct_summary=summary,
        )

    @staticmethod
    def _normalize_external_string_buffer_size(buffer_size: object) -> int | None:
        if buffer_size is None:
            return None
        try:
            return int(buffer_size)
        except (TypeError, ValueError):
            return None

    def _build_struct_layout_summary(self, struct_name: str) -> _StructLayoutSummary:
        normalized_name = normalize_type_name(struct_name).lower()
        cached_summary = self._struct_layout_cache.get(normalized_name)
        if cached_summary is not None:
            return cached_summary

        if normalized_name in self._struct_layout_in_progress:
            cycle_start = self._struct_layout_stack.index(normalized_name)
            cycle_path = tuple(
                self._display_struct_name(name)
                for name in (*self._struct_layout_stack[cycle_start:], normalized_name)
            )
            summary = _StructLayoutSummary(
                name=self._display_struct_name(normalized_name),
                is_layout_safe=False,
                is_blittable=False,
                size=None,
                alignment=None,
                cycle_path=cycle_path,
                rejection_reason="Recursive struct layout detected",
            )
            self._struct_layout_cache[normalized_name] = summary
            return summary

        struct_decl = self._struct_declarations_by_name.get(normalized_name)
        if struct_decl is None:
            summary = _StructLayoutSummary(
                name=self._display_struct_name(normalized_name),
                is_layout_safe=False,
                is_blittable=False,
                size=None,
                alignment=None,
                rejection_reason="Struct not declared",
            )
            self._struct_layout_cache[normalized_name] = summary
            return summary

        self._struct_layout_in_progress.add(normalized_name)
        self._struct_layout_stack.append(normalized_name)
        try:
            summary = self._compute_struct_layout_summary(struct_decl)
            self._struct_layout_cache[normalized_name] = summary
            return summary
        finally:
            self._struct_layout_stack.pop()
            self._struct_layout_in_progress.remove(normalized_name)

    def _compute_struct_layout_summary(self, declaration: ast.StructDecl) -> _StructLayoutSummary:
        field_offsets: list[int] = []
        field_sizes: list[int] = []
        field_alignments: list[int] = []
        field_blittable: list[bool] = []
        field_type_names: list[str] = []

        offset = 0
        struct_alignment = 1
        packing = declaration.packing
        alignment_override = declaration.alignment

        for field in declaration.fields:
            field_type_name = normalize_type_name(field.type_name)
            field_type_names.append(field_type_name)
            resolved_type = self._resolve_external_type(field_type_name)

            if resolved_type is None:
                return _StructLayoutSummary(
                    name=normalize_type_name(declaration.name),
                    is_layout_safe=False,
                    is_blittable=False,
                    size=None,
                    alignment=None,
                    packing=packing,
                    alignment_override=alignment_override,
                    field_offsets=tuple(field_offsets),
                    field_sizes=tuple(field_sizes),
                    field_alignments=tuple(field_alignments),
                    field_blittable=tuple(field_blittable),
                    field_type_names=tuple(field_type_names),
                    rejection_reason=f"Field '{field.name}' uses unknown type '{field_type_name}'",
                )

            if resolved_type.kind == "builtin":
                if not resolved_type.is_layout_safe or resolved_type.size is None or resolved_type.alignment is None:
                    return _StructLayoutSummary(
                        name=normalize_type_name(declaration.name),
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        rejection_reason=f"Field '{field.name}' uses non-layout-safe type '{field_type_name}'",
                    )

                field_size = resolved_type.size
                field_alignment = resolved_type.alignment
                field_is_blittable = resolved_type.is_blittable
            else:
                summary = resolved_type.struct_summary
                if summary is None:
                    return _StructLayoutSummary(
                        name=normalize_type_name(declaration.name),
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        rejection_reason=f"Field '{field.name}' uses non-layout-safe struct type '{field_type_name}'",
                    )
                if summary.cycle_path is not None:
                    return _StructLayoutSummary(
                        name=normalize_type_name(declaration.name),
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        cycle_path=summary.cycle_path,
                        rejection_reason="Recursive struct layout detected",
                    )
                if not summary.is_layout_safe or not summary.is_blittable or summary.size is None or summary.alignment is None:
                    return _StructLayoutSummary(
                        name=normalize_type_name(declaration.name),
                        is_layout_safe=False,
                        is_blittable=False,
                        size=None,
                        alignment=None,
                        packing=packing,
                        alignment_override=alignment_override,
                        field_offsets=tuple(field_offsets),
                        field_sizes=tuple(field_sizes),
                        field_alignments=tuple(field_alignments),
                        field_blittable=tuple(field_blittable),
                        field_type_names=tuple(field_type_names),
                        rejection_reason=f"Field '{field.name}' uses non-layout-safe struct type '{field_type_name}'",
                    )
                field_size = summary.size
                field_alignment = summary.alignment
                field_is_blittable = summary.is_blittable

            if packing is not None:
                field_alignment = min(field_alignment, packing)

            struct_alignment = max(struct_alignment, field_alignment)
            offset = self._align_up(offset, field_alignment)
            field_offsets.append(offset)
            field_sizes.append(field_size)
            field_alignments.append(field_alignment)
            field_blittable.append(field_is_blittable)
            offset += field_size

        final_alignment = struct_alignment
        if packing is not None:
            final_alignment = min(final_alignment, packing)
        if alignment_override is not None and alignment_override > struct_alignment:
            return _StructLayoutSummary(
                name=self._normalize_name(declaration.name) or normalize_type_name(declaration.name),
                is_layout_safe=False,
                is_blittable=False,
                size=None,
                alignment=None,
                packing=packing,
                alignment_override=alignment_override,
                field_offsets=tuple(field_offsets),
                field_sizes=tuple(field_sizes),
                field_alignments=tuple(field_alignments),
                field_blittable=tuple(field_blittable),
                field_type_names=tuple(field_type_names),
                rejection_reason=(
                    "Struct alignment cannot be honored by the current runtime: "
                    f"Align({alignment_override})"
                ),
            )

        final_size = self._align_up(offset, final_alignment)
        is_blittable = all(field_blittable)

        return _StructLayoutSummary(
            name=self._normalize_name(declaration.name) or normalize_type_name(declaration.name),
            is_layout_safe=True,
            is_blittable=is_blittable,
            size=final_size,
            alignment=final_alignment,
            packing=packing,
            alignment_override=alignment_override,
            field_offsets=tuple(field_offsets),
            field_sizes=tuple(field_sizes),
            field_alignments=tuple(field_alignments),
            field_blittable=tuple(field_blittable),
            field_type_names=tuple(field_type_names),
        )

    @staticmethod
    def _align_up(value: int, alignment: int) -> int:
        if alignment <= 1:
            return value
        return ((value + alignment - 1) // alignment) * alignment

    def _suggest_function_replacement(self, normalized_name: str) -> str | None:
        candidates: dict[str, str] = {}
        for builtin_name in BUILTIN_FUNCTION_NAMES:
            candidates.setdefault(builtin_name, format_builtin_function_name(builtin_name))
        for normalized_candidate, display_name in self._declared_function_display_names.items():
            candidates.setdefault(normalized_candidate, display_name)
        for normalized_candidate, display_name in self._declared_struct_display_names.items():
            candidates.setdefault(normalized_candidate, display_name)
        for normalized_candidate, display_name in self._declared_external_function_display_names.items():
            candidates.setdefault(normalized_candidate, display_name)

        best_candidate: str | None = None
        best_score = 0.0
        for candidate_name, display_name in candidates.items():
            if candidate_name == normalized_name:
                continue
            score = difflib.SequenceMatcher(None, normalized_name, candidate_name).ratio()
            threshold = self._function_replacement_similarity_threshold(candidate_name)
            if score < threshold:
                continue
            if score > best_score:
                best_candidate = display_name
                best_score = score

        return best_candidate

    def _function_replacement_similarity_threshold(self, candidate_name: str) -> float:
        length = len(candidate_name.strip())
        for max_length, threshold in self._FUNCTION_REPLACEMENT_SIMILARITY_THRESHOLD_BY_LENGTH:
            if length <= max_length:
                return threshold
        return 0.72

    def _collect_label(
        self,
        statement: ast.LabelStatement,
        *,
        scope_key: tuple[str, ...],
        ancestry: tuple[str, ...],
        labels_by_scope: dict[tuple[str, ...], dict[str, _LabelInfo]],
        diagnostics: DiagnosticBag,
    ) -> None:
        label_name = statement.name.strip()
        if not label_name:
            return

        scope_labels = labels_by_scope.setdefault(scope_key, {})
        normalized_name = label_name.lower()
        span = self._span(statement)
        if normalized_name in scope_labels:
            diagnostics.add(
                make_duplicate_label(
                    label_name,
                    span.start,
                    span.end,
                    source_name=self._source_name(statement),
                )
            )
            return

        scope_labels[normalized_name] = _LabelInfo(
            name=label_name,
            ancestry=ancestry,
            span=span,
        )

    def _validate_scope(
        self,
        statements: list[ast.Statement],
        *,
        scope_key: tuple[str, ...],
        ancestry: tuple[str, ...],
        labels_by_scope: dict[tuple[str, ...], dict[str, _LabelInfo]],
        diagnostics: DiagnosticBag,
        function_depth: int,
        loop_stack: tuple[str, ...],
    ) -> None:
        scope_labels = labels_by_scope.get(scope_key, {})

        for statement in statements:
            if isinstance(statement, ast.FunctionDecl):
                child_scope_key = self._function_scope_keys[id(statement)]
                self._validate_scope(
                    statement.body.statements,
                    scope_key=child_scope_key,
                    ancestry=child_scope_key,
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth + 1,
                    loop_stack=(),
                )
                continue

            if isinstance(statement, ast.StructDecl):
                continue

            if isinstance(statement, ast.EnumDecl):
                continue

            if isinstance(statement, ast.IfStatement):
                self._validate_scope(
                    statement.then_branch.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("then",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth,
                    loop_stack=loop_stack,
                )
                if statement.else_branch is not None:
                    self._validate_scope(
                        statement.else_branch.statements,
                        scope_key=scope_key,
                        ancestry=ancestry + ("else",),
                        labels_by_scope=labels_by_scope,
                        diagnostics=diagnostics,
                        function_depth=function_depth,
                        loop_stack=loop_stack,
                    )
                continue

            if isinstance(statement, ast.SelectStatement):
                select_ancestry = ancestry + ("select",)
                for case_index, case_arm in enumerate(statement.cases):
                    case_ancestry = select_ancestry + (f"case:{case_index}",)
                    self._validate_scope(
                        case_arm.body.statements,
                        scope_key=scope_key,
                        ancestry=case_ancestry,
                        labels_by_scope=labels_by_scope,
                        diagnostics=diagnostics,
                        function_depth=function_depth,
                        loop_stack=loop_stack,
                    )
                continue

            if isinstance(statement, ast.ForStatement):
                self._validate_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("for",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth,
                    loop_stack=loop_stack + ("for",),
                )
                continue

            if isinstance(statement, ast.WhileStatement):
                self._validate_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("while",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth,
                    loop_stack=loop_stack + ("while",),
                )
                continue

            if isinstance(statement, ast.LoopStatement):
                self._validate_scope(
                    statement.body.statements,
                    scope_key=scope_key,
                    ancestry=ancestry + ("loop",),
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth,
                    loop_stack=loop_stack + ("loop",),
                )
                continue

            if isinstance(statement, ast.Block):
                self._validate_scope(
                    statement.statements,
                    scope_key=scope_key,
                    ancestry=ancestry,
                    labels_by_scope=labels_by_scope,
                    diagnostics=diagnostics,
                    function_depth=function_depth,
                    loop_stack=loop_stack,
                )
                continue

            if isinstance(statement, ast.ReturnStatement):
                if function_depth <= 0:
                    span = self._span(statement)
                    diagnostics.add(
                        make_return_outside_function(
                            span.start,
                            span.end,
                            source_name=self._source_name(statement),
                        )
                    )
                continue

            if isinstance(statement, ast.ExitStatement):
                self._validate_loop_control(
                    statement,
                    keyword="Exit",
                    loop_stack=loop_stack,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.ContinueStatement):
                self._validate_loop_control(
                    statement,
                    keyword="Continue",
                    loop_stack=loop_stack,
                    diagnostics=diagnostics,
                )
                continue

            if isinstance(statement, ast.GotoStatement):
                self._validate_goto(
                    statement,
                    scope_labels=scope_labels,
                    ancestry=ancestry,
                    diagnostics=diagnostics,
                )

    def _validate_goto(
        self,
        statement: ast.GotoStatement,
        *,
        scope_labels: dict[str, _LabelInfo],
        ancestry: tuple[str, ...],
        diagnostics: DiagnosticBag,
    ) -> None:
        label_name = statement.label.strip()
        if not label_name:
            return

        label_info = scope_labels.get(label_name.lower())
        span = self._span(statement)
        if label_info is None:
            diagnostics.add(
                make_missing_goto_target(
                    label_name,
                    span.start,
                    span.end,
                    source_name=self._source_name(statement),
                )
            )
            return

        if not self._goto_target_is_legal(
            source_ancestry=ancestry,
            target_ancestry=label_info.ancestry,
        ):
            diagnostics.add(
                make_illegal_goto_target(
                    label_name,
                    span.start,
                    span.end,
                    source_name=self._source_name(statement),
                )
            )

    def _validate_loop_control(
        self,
        statement: ast.ExitStatement | ast.ContinueStatement,
        *,
        keyword: str,
        loop_stack: tuple[str, ...],
        diagnostics: DiagnosticBag,
    ) -> None:
        target = self._normalize_loop_target(statement.target)
        if target is None:
            if not loop_stack:
                span = self._span(statement)
                diagnostics.add(
                    make_loop_control_error(
                        keyword,
                        None,
                        span.start,
                        span.end,
                        source_name=self._source_name(statement),
                    )
                )
            return

        if target not in {"for", "while", "loop"}:
            span = self._span(statement)
            diagnostics.add(
                make_loop_control_error(
                    keyword,
                    statement.target,
                    span.start,
                    span.end,
                    source_name=self._source_name(statement),
                )
            )
            return

        if target == "loop":
            if not loop_stack:
                span = self._span(statement)
                diagnostics.add(
                    make_loop_control_error(
                        keyword,
                        statement.target,
                        span.start,
                        span.end,
                        source_name=self._source_name(statement),
                    )
                )
            return

        if target not in loop_stack:
            span = self._span(statement)
            diagnostics.add(
                make_loop_control_error(
                    keyword,
                    statement.target,
                    span.start,
                    span.end,
                    source_name=self._source_name(statement),
                )
            )

    def _allocate_scope_key(self, name: str) -> tuple[str, ...]:
        safe_name = name.strip().lower() or "anonymous"
        key = (f"scope:{self._scope_counter}:{safe_name}",)
        self._scope_counter += 1
        return key

    @staticmethod
    def _normalize_loop_target(target: str | None) -> str | None:
        if target is None:
            return None
        normalized = str(target).strip().lower()
        return normalized or None

    @staticmethod
    def _goto_target_is_legal(
        *,
        source_ancestry: tuple[str, ...],
        target_ancestry: tuple[str, ...],
    ) -> bool:
        if source_ancestry == target_ancestry:
            return True
        if len(target_ancestry) > len(source_ancestry):
            return False
        return source_ancestry[: len(target_ancestry)] == target_ancestry

    def _source_name(self, node: ast.AstNode | None) -> str | None:
        _ = node
        return self._document_source_name

    @staticmethod
    def _span(node: ast.AstNode | None) -> TextSpan:
        if node is not None and node.span is not None:
            return node.span
        return TextSpan(0, 0)
