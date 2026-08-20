"""
Recursive-descent parser for the scripting frontend.

- Consume the canonical Token / TokenType contract from tokens.py.
- Build AST nodes from ast_nodes.py.
- Report syntax diagnostics through diagnostics.py.
- Stay frontend-only; no semantic analysis, label binding, or type inference.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Any, Optional, Sequence

from . import ast_nodes as ast
from .lexer import lex
from .type_names import normalize_type_name
from .tokens import Token, TokenType
from .diagnostics import (
    DiagnosticBag,
    TextSpan,
    make_expected_expression,
    make_missing_token,
    make_syntax_error,
    make_expected_statement,
    make_unexpected_token,
    make_struct_layout_clause_invalid,
    make_struct_layout_clause_duplicated,
)

@dataclass(frozen=True)
class ParseResult:
    root: ast.Program
    diagnostics: DiagnosticBag


@dataclass(frozen=True)
class InterpolationReadResult:
    expression_text: str
    expression_span_start: int
    expression_span_end: int
    format_spec: str | None
    format_span_start: int | None
    format_span_end: int | None
    next_index: int


EOF_TYPES = {TokenType.EOF}
NEWLINE_TYPES = {TokenType.NEWLINE}
IDENT_TYPES = {TokenType.IDENTIFIER, TokenType.HOST_IDENTIFIER}
STRING_TYPES = {TokenType.STRING, TokenType.INTERP_STRING}
NUMBER_TYPES = {TokenType.NUMBER}
BOOLEAN_TYPES = {TokenType.BOOLEAN, TokenType.TRUE, TokenType.FALSE}
COMMA_TYPES = {TokenType.COMMA}
COLON_TYPES = {TokenType.COLON}
LPAREN_TYPES = {TokenType.LPAREN}
RPAREN_TYPES = {TokenType.RPAREN}
LBRACKET_TYPES = {TokenType.LBRACKET}
RBRACKET_TYPES = {TokenType.RBRACKET}
DOT_TYPES = {TokenType.DOT}

BLOCK_TERMINATORS = {
    TokenType.ENDIF,
    TokenType.ELSE,
    TokenType.ELSEIF,
    TokenType.WEND,
    TokenType.UNTIL,
    TokenType.NEXT,
    TokenType.END,
    TokenType.ENDFUNC,
    TokenType.ENDRECORD,
    TokenType.CASE,
    TokenType.ENDSELECT,
    TokenType.ENDSTRUCT,
    TokenType.ENDENUM,
}

KEYWORD_TOKEN_MAP = {
    "IF": TokenType.IF,
    "THEN": TokenType.THEN,
    "ELSE": TokenType.ELSE,
    "ELSEIF": TokenType.ELSEIF,
    "ENDIF": TokenType.ENDIF,
    "WHILE": TokenType.WHILE,
    "WEND": TokenType.WEND,
    "DO": TokenType.DO,
    "UNTIL": TokenType.UNTIL,
    "FOR": TokenType.FOR,
    "TO": TokenType.TO,
    "STEP": TokenType.STEP,
    "NEXT": TokenType.NEXT,
    "SELECT": TokenType.SELECT,
    "CASE": TokenType.CASE,
    "ENDSELECT": TokenType.ENDSELECT,
    "END": TokenType.END,
    "FUNC": TokenType.FUNC,
    "ENDFUNC": TokenType.ENDFUNC,
    "STRUCT": TokenType.STRUCT,
    "ENDSTRUCT": TokenType.ENDSTRUCT,
    "ENDENUM": TokenType.ENDENUM,
    "RETURN": TokenType.RETURN,
    "EXITSCRIPT": TokenType.EXITSCRIPT,
    "SCRIPTQUIT": TokenType.EXITSCRIPT,
    "DIM": TokenType.DIM,
    "LOCAL": TokenType.LOCAL,
    "GLOBAL": TokenType.GLOBAL,
    "CONST": TokenType.CONST,
    "REDIM": TokenType.REDIM,
    "AS": TokenType.AS,
    "BYVAL": TokenType.BYVAL,
    "BYREF": TokenType.BYREF,
    "ENUM": TokenType.ENUM,
    "CONTINUE": TokenType.CONTINUE,
    "CONTINUELOOP": TokenType.CONTINUELOOP,
    "EXIT": TokenType.EXIT,
    "EXITLOOP": TokenType.EXITLOOP,
    "EXITFOR": TokenType.EXITFOR,
    "EXITWHILE": TokenType.EXITWHILE,
    "GOTO": TokenType.GOTO,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
    "NOT": TokenType.NOT,
    "TRUE": TokenType.TRUE,
    "FALSE": TokenType.FALSE,
    "NULL": TokenType.NULL,
}

BINARY_PRECEDENCE = {
    TokenType.OR: 1,
    TokenType.AND: 2,
    TokenType.EQ: 3,
    TokenType.NE: 3,
    TokenType.LT: 4,
    TokenType.LTE: 4,
    TokenType.GT: 4,
    TokenType.GTE: 4,
    TokenType.AMPERSAND: 5,
    TokenType.PLUS: 6,
    TokenType.MINUS: 6,
    TokenType.STAR: 7,
    TokenType.SLASH: 7,
    TokenType.PERCENT: 7,
}

TERNARY_PRECEDENCE = 0

BINARY_OPERATOR_TEXT = {
    TokenType.OR: "OR",
    TokenType.AND: "AND",
    TokenType.EQ: "==",
    TokenType.NE: "<>",
    TokenType.LT: "<",
    TokenType.LTE: "<=",
    TokenType.GT: ">",
    TokenType.GTE: ">=",
    TokenType.AMPERSAND: "&",
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.PERCENT: "%",
}

UNARY_OPERATORS = {
    TokenType.NOT: "NOT",
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.INCREMENT: "++",
    TokenType.DECREMENT: "--",
}

POSTFIX_UNARY_OPERATORS = {
    TokenType.INCREMENT: "++",
    TokenType.DECREMENT: "--",
}


class Parser:
    def __init__(
        self,
        tokens: Sequence[Token],
        diagnostics: Optional[DiagnosticBag] = None,
        source_name: str = "<memory>",
    ) -> None:

        self.tokens = list(tokens) if tokens else [
            Token(
                type=TokenType.EOF,
                value="",
                line=1,
                column=1,
                end_line=1,
                end_column=1,
                start_index=0,
                end_index=0,
            )
        ]
        self.index = 0
        self.diagnostics = diagnostics if diagnostics is not None else DiagnosticBag()
        self.source_name = source_name

    def parse(self) -> ast.Program:
        statements: list[ast.Statement] = []
        self._consume_separators()

        while not self._at_end():
            if self._token_type(self._peek()) in BLOCK_TERMINATORS:
                self._unexpected_statement_terminator()
                self._advance()
                self._consume_separators()
                continue

            statement = self.parse_statement()
            if statement is not None:
                statements.append(statement)

            self._require_statement_separator_after_statement()
            self._consume_separators()

        return ast.Program(
            statements=statements,
            span=self._span_from_nodes(*statements),
        )
 
    def parse_expression_only(self) -> ast.Expression:
        self._consume_separators()
        expression = self.parse_expression()
        self._consume_separators()
        if not self._at_end():
            self._error_unexpected_current("end of expression")
        return expression

    def parse_statement(self) -> Optional[ast.Statement]:
        token_type = self._token_type(self._peek())

        if token_type == TokenType.IF:
            return self._parse_if_statement()
        if token_type == TokenType.SELECT:
            return self._parse_select_statement()
        if token_type == TokenType.WHILE:
            return self._parse_while_statement()
        if token_type == TokenType.DO:
            return self._parse_do_until_statement()
        if token_type == TokenType.FOR:
            return self._parse_for_statement()
        if token_type == TokenType.DECLARE:
            return self._parse_external_decl()
        if token_type == TokenType.FUNC:
            return self._parse_function_decl()
        if token_type == TokenType.STRUCT:
            return self._parse_struct_decl()
        if token_type == TokenType.ENUM:
            return self._parse_enum_decl()
        if token_type == TokenType.RECORD:
            return self._parse_record_decl()
        if token_type == TokenType.RETURN:
            return self._parse_return_statement()
        if token_type == TokenType.EXITSCRIPT:
            return self._parse_script_quit_statement()
        if token_type in {TokenType.DIM, TokenType.LOCAL, TokenType.GLOBAL, TokenType.REDIM}:
            return self._parse_var_decl()
        if token_type == TokenType.CONST:
            return self._parse_const_decl()
        if token_type == TokenType.GOTO:
            self._advance()
            return self._parse_goto_statement()
        if token_type in {TokenType.CONTINUE, TokenType.CONTINUELOOP}:
            keyword = self._advance()
            return self._parse_continue_statement(keyword)
        if token_type in {TokenType.EXIT, TokenType.EXITLOOP, TokenType.EXITFOR, TokenType.EXITWHILE}:
            self._advance()
            return self._parse_exit_statement()
        if token_type == TokenType.IDENTIFIER and self._check_type_in(COLON_TYPES, 1):
            return self._parse_label_statement()
        if token_type in BLOCK_TERMINATORS:
            self._unexpected_statement_terminator()
            self._advance()
            return None
        if self._looks_like_assignment():
            return self._parse_assignment_statement()
        if self._can_start_expression(self._peek()):
            expr = self.parse_expression()
            return ast.ExpressionStatement(
                expression=expr,
                span=self._span_from_node(expr),
            )        

        self._error_expected_statement_current()
        self._skip_to_statement_boundary()
        return None

    def parse_expression(self, min_precedence: int = 0) -> ast.Expression:
        left = self._parse_unary_expression()

        while True:
            token_type = self._token_type(self._peek())
            precedence = BINARY_PRECEDENCE.get(token_type)
            if precedence is None or precedence < min_precedence:
                break

            self._advance()
            operator_text = BINARY_OPERATOR_TEXT[token_type]
            right = self.parse_expression(precedence + 1)
            left = ast.BinaryExpr(
                left=left,
                operator=operator_text,
                right=right,
                span=self._span_from_nodes(left, right),
            )

        if min_precedence <= TERNARY_PRECEDENCE and self._match_type(TokenType.QUESTION):
            true_expression = self.parse_expression()
            self._expect_type(TokenType.COLON, "Expected ':' after ternary expression")
            false_expression = self.parse_expression()
            left = ast.TernaryExpr(
                condition=left,
                true_expression=true_expression,
                false_expression=false_expression,
                span=self._span_from_nodes(left, false_expression),
            )

        return left

    def _parse_if_statement(self) -> ast.IfStatement:
        if_token = self._expect_keyword("IF", "Expected 'If'")
        condition = self.parse_expression()
        self._expect_keyword("THEN", "Expected 'Then' after If condition")
        self._consume_separators(required=True, message="Expected newline after If ... Then")

        then_branch_statements = self._parse_block_until({TokenType.ELSE, TokenType.ELSEIF, TokenType.ENDIF})
        then_branch = ast.Block(
            statements=then_branch_statements,
            span=self._span_from_nodes(*then_branch_statements),
        )
        else_branch: Optional[ast.Block] = None

        if self._match_keyword("ELSEIF"):
            nested_if = self._parse_if_tail_after_elseif()
            else_branch = ast.Block(statements=[nested_if], span=self._span_from_node(nested_if))
        elif self._match_keyword("ELSE"):
            self._consume_separators(required=True, message="Expected newline after Else")
            else_branch_statements = self._parse_block_until({TokenType.ENDIF})
            else_branch = ast.Block(
                statements=else_branch_statements,
                span=self._span_from_nodes(*else_branch_statements),
            )

        endif_token = self._expect_if_terminator()
        return ast.IfStatement(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            span=self._span_from_tokens(if_token, endif_token),
        )

    def _parse_if_tail_after_elseif(self) -> ast.IfStatement:
        elseif_token = self._peek(-1)
        condition = self.parse_expression()
        self._expect_keyword("THEN", "Expected 'Then' after ElseIf condition")
        self._consume_separators(required=True, message="Expected newline after ElseIf ... Then")

        then_branch_statements = self._parse_block_until({TokenType.ELSE, TokenType.ELSEIF, TokenType.ENDIF})
        then_branch = ast.Block(
            statements=then_branch_statements,
            span=self._span_from_nodes(*then_branch_statements),
        )
        else_branch: Optional[ast.Block] = None

        if self._match_keyword("ELSEIF"):
            nested_if = self._parse_if_tail_after_elseif()
            else_branch = ast.Block(statements=[nested_if], span=self._span_from_node(nested_if))
        elif self._match_keyword("ELSE"):
            self._consume_separators(required=True, message="Expected newline after Else")
            else_branch_statements = self._parse_block_until({TokenType.ENDIF})
            else_branch = ast.Block(
                statements=else_branch_statements,
                span=self._span_from_nodes(*else_branch_statements),
            )

        end_span = self._span_from_node(else_branch) or self._span_from_node(then_branch)
        return ast.IfStatement(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            span=self._merge_spans(self._span_from_token(elseif_token), end_span),
        )

    def _parse_select_statement(self) -> ast.SelectStatement:
        select_token = self._expect_keyword("SELECT", "Expected 'Select'")
        self._expect_keyword("CASE", "Expected 'Case' after Select")
        expression = self.parse_expression()
        self._consume_separators(required=True, message="Expected newline after Select Case expression")

        cases: list[ast.SelectCaseArm] = []
        end_token: Token | None = None

        while not self._at_end():
            if self._is_block_terminator({TokenType.ENDSELECT}):
                end_token = self._expect_select_terminator()
                break

            if self._check_type(TokenType.CASE):
                cases.append(self._parse_select_case_arm())
                continue

            self._error_unexpected_current("'Case' or 'End Select'")
            self._skip_to_statement_boundary()

        if end_token is None:
            end_token = self._expect_select_terminator()

        return ast.SelectStatement(
            expression=expression,
            cases=cases,
            span=self._span_from_tokens(select_token, end_token),
        )

    def _parse_select_case_arm(self) -> ast.SelectCaseArm:
        case_token = self._expect_keyword("CASE", "Expected 'Case'")
        conditions: list[ast.SelectCaseCondition] = []
        is_else = self._match_keyword("ELSE")

        if not is_else:
            while True:
                if self._match_keyword("IS"):
                    is_token = self._peek(-1)
                    is_not = self._match_keyword("NOT")
                    if self._check_keyword("LIKE"):
                        self._advance()
                        pattern_expr = self.parse_expression()
                        conditions.append(
                            ast.SelectCaseLike(
                                pattern=pattern_expr,
                                is_negated=is_not,
                                span=self._merge_spans(
                                    self._span_from_token(is_token),
                                    self._span_from_node(pattern_expr),
                                ),
                            )
                        )
                    else:
                        operator_text = "="
                        if self._peek_is_select_case_operator():
                            operator_text = self._parse_select_case_comparison_operator_text()
                        comparison_expr = self.parse_expression()
                        conditions.append(
                            ast.SelectCaseComparison(
                                operator=operator_text,
                                expression=comparison_expr,
                                is_negated=is_not,
                                span=self._merge_spans(
                                    self._span_from_token(is_token),
                                    self._span_from_node(comparison_expr),
                                ),
                            )
                        )
                elif self._check_keyword("NOT") and self._check_keyword("LIKE", 1):
                    not_token = self._advance()
                    like_token = self._advance()
                    pattern_expr = self.parse_expression()
                    conditions.append(
                        ast.SelectCaseLike(
                            pattern=pattern_expr,
                            is_negated=True,
                            span=self._merge_spans(
                                self._span_from_token(not_token),
                                self._span_from_node(pattern_expr),
                            ),
                        )
                    )
                elif self._match_keyword("LIKE"):
                    pattern_expr = self.parse_expression()
                    conditions.append(
                        ast.SelectCaseLike(
                            pattern=pattern_expr,
                            span=self._span_from_node(pattern_expr),
                        )
                    )
                else:
                    condition_start = self.parse_expression()
                    if self._match_keyword("TO"):
                        condition_end = self.parse_expression()
                        conditions.append(
                            ast.SelectCaseRange(
                                start=condition_start,
                                end=condition_end,
                                span=self._span_from_nodes(condition_start, condition_end),
                            )
                        )
                    else:
                        conditions.append(
                            ast.SelectCaseValue(
                                expression=condition_start,
                                span=self._span_from_node(condition_start),
                            )
                        )

                if not self._match_type(TokenType.COMMA):
                    break

        self._consume_separators(required=True, message="Expected newline after Case clause")
        body_statements = self._parse_block_until({TokenType.CASE, TokenType.ENDSELECT})
        body = ast.Block(
            statements=body_statements,
            span=self._span_from_nodes(*body_statements),
        )

        return ast.SelectCaseArm(
            conditions=conditions,
            body=body,
            is_else=is_else,
            span=self._merge_spans(self._span_from_token(case_token), self._span_from_node(body)),
        )

    def _parse_select_case_comparison_operator_text(self) -> str:
        token = self._peek()
        token_type = self._token_type(token)
        if token_type == TokenType.LT:
            self._advance()
            if self._match_type(TokenType.ASSIGN):
                return "<="
            return "<"
        if token_type == TokenType.GT:
            self._advance()
            if self._match_type(TokenType.ASSIGN):
                return ">="
            return ">"
        if token_type == TokenType.ASSIGN:
            self._advance()
            return "="
        if token_type == TokenType.EQ:
            self._advance()
            return "="
        if token_type == TokenType.LTE:
            self._advance()
            return "<="
        if token_type == TokenType.GTE:
            self._advance()
            return ">="
        if token_type == TokenType.NE:
            self._advance()
            return "<>"

        self._error_expected_expression_current()
        return "="

    def _peek_is_select_case_operator(self) -> bool:
        token_type = self._token_type(self._peek())
        return token_type in {
            TokenType.LT,
            TokenType.GT,
            TokenType.ASSIGN,
            TokenType.EQ,
            TokenType.LTE,
            TokenType.GTE,
            TokenType.NE,
        }

    def _parse_while_statement(self) -> ast.WhileStatement:
        while_token = self._expect_keyword("WHILE", "Expected 'While'")
        condition = self.parse_expression()
        self._consume_separators(required=True, message="Expected newline after While condition")
        body_statements = self._parse_block_until({TokenType.WEND})
        body = ast.Block(
            statements=body_statements,
            span=self._span_from_nodes(*body_statements),
        )
 
        wend_token = self._expect_keyword("WEND", "Expected 'WEnd' to close While block")
 
        return ast.WhileStatement(
            condition=condition,
            body=body,
            span=self._span_from_tokens(while_token, wend_token),
        )        

    def _parse_do_until_statement(self) -> ast.LoopStatement:
        do_token = self._expect_keyword("DO", "Expected 'Do'")
        self._consume_separators(required=True, message="Expected newline after Do")
        body_statements = self._parse_block_until({TokenType.UNTIL})
        body = ast.Block(
            statements=body_statements,
            span=self._span_from_nodes(*body_statements),
        )
        until_token = self._expect_keyword("UNTIL", "Expected 'Until' to close Do block")
        condition = self.parse_expression() if not self._statement_terminator_ahead() else None
        return ast.LoopStatement(
            condition=condition,
            body=body,
            is_until=True,
            span=self._merge_spans(
                self._span_from_token(do_token),
                self._span_from_node(condition),
            ) if condition is not None else self._span_from_tokens(do_token, until_token),
        )

    def _parse_for_statement(self) -> ast.ForStatement:
        for_token = self._expect_keyword("FOR", "Expected 'For'")
        variable_token = self._expect_identifier_token("Expected loop variable after For")
        variable_name = variable_token.value
        variable_node = ast.Identifier(
            name=variable_name,
            span=self._span_from_token(variable_token),
        )

        self._expect_type(TokenType.ASSIGN, "Expected '=' after For loop variable")
        start_expr = self.parse_expression()
        self._expect_keyword("TO", "Expected 'To' in For statement")
        stop_expr = self.parse_expression()

        step_expr = None
        if self._match_keyword("STEP"):
            step_expr = self.parse_expression()

        self._consume_separators(required=True, message="Expected newline after For header")
        body_statements = self._parse_block_until({TokenType.NEXT})
        body = ast.Block(
            statements=body_statements,
            span=self._span_from_nodes(*body_statements),
        )

        next_token = self._expect_keyword("NEXT", "Expected 'Next' to close For loop")
        end_token = next_token
        if self._check_identifier_value(variable_name):
            end_token = self._advance()

        return ast.ForStatement(
            variable=variable_node,
            start=start_expr,
            stop=stop_expr,
            step=step_expr,
            body=body,
            span=self._span_from_tokens(for_token, end_token),
        )

    def _parse_function_decl(self) -> ast.FunctionDecl:
        func_token = self._expect_keyword("FUNC", "Expected 'Func'")
        name_token = self._expect_identifier_token("Expected function name after Func")
        name = name_token.value

        params: list[ast.ParamDecl] = []
        if self._function_header_allows_parameter_list():
            params = self._parse_parameter_list()

        self._consume_separators(
            required=True,
            message="Expected newline after Func header",
        )

        body_statements = self._parse_block_until({TokenType.ENDFUNC})
        endfunc_token = self._expect_function_terminator()

        body = ast.Block(
            statements=body_statements,
            span=self._span_from_nodes(*body_statements),
        )

        return ast.FunctionDecl(
            name=name,
            params=params,
            body=body,
            span=self._span_from_tokens(func_token, endfunc_token),
        )

    def _parse_external_decl(self) -> ast.ExternalFunctionDecl:
        declare_token = self._expect_keyword("DECLARE", "Expected 'Declare'")
        kind_token = self._advance()
        if kind_token.type not in {TokenType.FUNC, TokenType.SUB}:
            self._error_expected_current("'Func' or 'Sub'")
        is_sub = kind_token.type == TokenType.SUB
        name_token = self._expect_identifier_token("Expected function name after Declare Func")
        name = name_token.value

        self._expect_keyword("LIB", "Expected 'Lib' after external function name")
        library_token = self._expect_type(TokenType.STRING, "Expected DLL/library name string")
        library_name = self._decode_string_literal(library_token.value)
        export_name: str | None = None
        calling_convention = "winapi"
        while True:
            if self._check_keyword("ALIAS"):
                self._advance()
                alias_token = self._expect_type(TokenType.STRING, "Expected alias string after Alias")
                export_name = self._decode_string_literal(alias_token.value)
                continue

            if self._check_type_in({TokenType.DEFAULT, TokenType.WINAPI, TokenType.STDCALL, TokenType.CDECL}, 0):
                convention_token = self._advance()
                calling_convention = self._normalize_calling_convention_token(convention_token.type)
                continue

            break

        params: list[ast.ParamDecl] = []
        self._expect_type(TokenType.LPAREN, "Expected '(' after external function declaration")
        if not self._check_type(TokenType.RPAREN):
            while True:
                modifier_token = None
                is_byval = False
                is_byref = False
                if self._check_keyword("BYVAL"):
                    modifier_token = self._advance()
                    is_byval = True
                elif self._check_keyword("BYREF"):
                    modifier_token = self._advance()
                    is_byref = True

                param_name_token = self._expect_identifier_token("Expected parameter name")
                type_name, string_buffer_size = self._parse_external_required_type_annotation()
                param_span = self._span_from_token(modifier_token or param_name_token)

                params.append(
                    ast.ParamDecl(
                        name=param_name_token.value,
                        type_name=type_name,
                        string_buffer_size=string_buffer_size,
                        default=None,
                        is_byval=is_byval,
                        is_byref=is_byref,
                        span=param_span,
                    )
                )

                if not self._match_type(TokenType.COMMA):
                    break
        self._expect_type(TokenType.RPAREN, "Expected ')' after external parameter list")

        return_type_name = ""
        if not is_sub:
            self._expect_keyword("AS", "Expected 'As' return type annotation")
            return_type_token = self._expect_identifier_token("Expected return type name")
            return_type_name = normalize_type_name(return_type_token.value)
        else:
            return_type_token = None

        return ast.ExternalFunctionDecl(
            name=name,
            library_name=library_name,
            export_name=export_name,
            params=params,
            return_type_name=return_type_name,
            is_sub=is_sub,
            calling_convention=calling_convention,
            span=self._span_from_tokens(declare_token, return_type_token or kind_token),
        )

    def _parse_struct_decl(self) -> ast.StructDecl:
        struct_token = self._expect_keyword("STRUCT", "Expected 'Struct'")
        name_token = self._expect_identifier_token("Expected struct name after Struct")
        name = name_token.value
        packing: int | None = None
        alignment: int | None = None

        if self._check_type_in({TokenType.PACKED, TokenType.ALIGN}, 0):
            layout_token = self._advance()
            layout_value = self._parse_struct_layout_clause(layout_token)
            if layout_value is not None:
                if layout_token.type == TokenType.PACKED:
                    packing = layout_value
                else:
                    alignment = layout_value

            if self._check_type_in({TokenType.PACKED, TokenType.ALIGN}, 0):
                duplicate_token = self._peek()
                duplicate_span = self._span_from_token(duplicate_token)
                self.diagnostics.add(
                    make_struct_layout_clause_duplicated(
                        duplicate_token.value,
                        duplicate_span.start,
                        duplicate_span.end,
                        source_name=self.source_name,
                    )
                )
                self._skip_to_statement_boundary()

        self._consume_separators(
            required=True,
            message="Expected newline after Struct header",
        )

        fields = self._parse_struct_fields()
        endstruct_token = self._expect_struct_terminator()

        return ast.StructDecl(
            name=name,
            packing=packing,
            alignment=alignment,
            fields=fields,
            span=self._span_from_tokens(struct_token, endstruct_token),
        )

    def _parse_record_decl(self) -> ast.RecordDecl:
        record_token = self._expect_keyword("RECORD", "Expected 'Record'")
        name_token = self._expect_identifier_token("Expected record name after Record")
        name = name_token.value
        self._consume_separators(
            required=True,
            message="Expected newline after Record header",
        )

        fields = self._parse_record_fields()
        endrecord_token = self._expect_record_terminator()

        return ast.RecordDecl(
            name=name,
            fields=fields,
            span=self._span_from_tokens(record_token, endrecord_token),
        )

    def _parse_enum_decl(self) -> ast.EnumDecl:
        enum_token = self._expect_keyword("ENUM", "Expected 'Enum'")
        name_token = self._expect_identifier_token("Expected enum name after Enum")
        name = name_token.value
        self._consume_separators(
            required=True,
            message="Expected newline after Enum header",
        )

        members = self._parse_enum_members()
        endenum_token = self._expect_enum_terminator()

        return ast.EnumDecl(
            name=name,
            members=members,
            span=self._span_from_tokens(enum_token, endenum_token),
        )

    def _parse_struct_layout_clause(self, layout_token: Token) -> int | None:
        layout_name = "Packed" if layout_token.type == TokenType.PACKED else "Align"
        clause_start = self._span_from_token(layout_token).start

        self._expect_type(TokenType.LPAREN, f"Expected '(' after {layout_name}")
        if not self._check_type(TokenType.NUMBER):
            clause_end = self._span_from_token(self._peek()).end
            self.diagnostics.add(
                make_struct_layout_clause_invalid(
                    f"{layout_name}(...)",
                    clause_start,
                    clause_end,
                    source_name=self.source_name,
                )
            )
            self._skip_to_statement_boundary()
            return None

        size_token = self._advance()
        self._expect_type(TokenType.RPAREN, f"Expected ')' after {layout_name} value")
        try:
            return int(str(size_token.value).replace("_", ""))
        except ValueError:
            clause_end = self._span_from_token(size_token).end
            self.diagnostics.add(
                make_struct_layout_clause_invalid(
                    f"{layout_name}({size_token.value})",
                    clause_start,
                    clause_end,
                    source_name=self.source_name,
                )
            )
            self._skip_to_statement_boundary()
            return None

    def _normalize_calling_convention_token(self, token_type: TokenType) -> str:
        if token_type == TokenType.DEFAULT:
            return "default"
        if token_type == TokenType.CDECL:
            return "cdecl"
        if token_type == TokenType.STDCALL:
            return "stdcall"
        if token_type == TokenType.WINAPI:
            return "winapi"
        return "winapi"

    def _expect_function_terminator(self) -> Token:
        if self._check_keyword("ENDFUNC"):
            return self._advance()

        if self._is_spaced_function_terminator():
            end_token = self._advance()
            func_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDFUNC,
                "End Function",
                start_token=end_token,
                end_token=func_token,
            )

        self._error_unexpected_current(repr("ENDFUNC"))
        return self._synthetic_token(TokenType.ENDFUNC, "EndFunc")

    def _expect_if_terminator(self) -> Token:
        if self._check_keyword("ENDIF"):
            return self._advance()

        if self._is_spaced_if_terminator():
            end_token = self._advance()
            if_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDIF,
                "End If",
                start_token=end_token,
                end_token=if_token,
            )

        self._error_unexpected_current(repr("ENDIF"))
        return self._synthetic_token(TokenType.ENDIF, "EndIf")

    def _expect_select_terminator(self) -> Token:
        if self._check_keyword("ENDSELECT"):
            return self._advance()

        if self._is_spaced_select_terminator():
            end_token = self._advance()
            select_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDSELECT,
                "End Select",
                start_token=end_token,
                end_token=select_token,
            )

        self._error_unexpected_current(repr("ENDSELECT"))
        return self._synthetic_token(TokenType.ENDSELECT, "EndSelect")

    def _expect_struct_terminator(self) -> Token:
        if self._check_keyword("ENDSTRUCT"):
            return self._advance()

        if self._is_spaced_struct_terminator():
            end_token = self._advance()
            struct_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDSTRUCT,
                "End Struct",
                start_token=end_token,
                end_token=struct_token,
            )

        self._error_unexpected_current(repr("ENDSTRUCT"))
        return self._synthetic_token(TokenType.ENDSTRUCT, "EndStruct")

    def _expect_record_terminator(self) -> Token:
        if self._check_keyword("ENDRECORD"):
            return self._advance()

        if self._is_spaced_record_terminator():
            end_token = self._advance()
            record_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDRECORD,
                "End Record",
                start_token=end_token,
                end_token=record_token,
            )

        self._error_unexpected_current(repr("ENDRECORD"))
        return self._synthetic_token(TokenType.ENDRECORD, "EndRecord")

    def _parse_return_statement(self) -> ast.ReturnStatement:
        return_token = self._expect_keyword("RETURN", "Expected 'Return'")

        if self._statement_terminator_ahead():
            return ast.ReturnStatement(
                value=None,
                span=self._span_from_token(return_token),
            )

        value = self.parse_expression()
        return ast.ReturnStatement(
            value=value,
            span=self._span_from_token_to_node(return_token, value),
        )

    def _parse_script_quit_statement(self) -> ast.ScriptQuitStatement:
        script_quit_token = self._expect_keyword("EXITSCRIPT", "Expected 'ExitScript'")

        if self._statement_terminator_ahead():
            return ast.ScriptQuitStatement(
                value=None,
                span=self._span_from_token(script_quit_token),
            )

        value = self.parse_expression()
        return ast.ScriptQuitStatement(
            value=value,
            span=self._span_from_token_to_node(script_quit_token, value),
        )

    def _parse_exit_statement(self) -> ast.ExitStatement:
        exit_token = self._peek(-1)
        previous_type = self._token_type(exit_token)

        if previous_type == TokenType.EXITFOR:
            return ast.ExitStatement(target="for", span=self._span_from_token(exit_token))
        if previous_type == TokenType.EXITWHILE:
            return ast.ExitStatement(target="while", span=self._span_from_token(exit_token))
        if previous_type == TokenType.EXITLOOP:
            return ast.ExitStatement(target="loop", span=self._span_from_token(exit_token))

        if self._statement_terminator_ahead():
            return ast.ExitStatement(target=None, span=self._span_from_token(exit_token))
        if self._check_keyword("FOR"):
            target_token = self._advance()
            return ast.ExitStatement(target="for", span=self._span_from_tokens(exit_token, target_token))
        if self._check_keyword("WHILE"):
            target_token = self._advance()
            return ast.ExitStatement(target="while", span=self._span_from_tokens(exit_token, target_token))
        if self._check_identifier():
            target_token = self._advance()
            return ast.ExitStatement(target=target_token.value, span=self._span_from_tokens(exit_token, target_token))
        return ast.ExitStatement(target=None, span=self._span_from_token(exit_token))

    def _parse_continue_statement(self, continue_token: Token) -> ast.ContinueStatement:
        previous_type = self._token_type(continue_token)

        if previous_type == TokenType.CONTINUELOOP:
            return ast.ContinueStatement(target="loop", span=self._span_from_token(continue_token))

        if self._statement_terminator_ahead():
            return ast.ContinueStatement(target=None, span=self._span_from_token(continue_token))
        if self._check_keyword("FOR"):
            target_token = self._advance()
            return ast.ContinueStatement(target="for", span=self._span_from_tokens(continue_token, target_token))
        if self._check_keyword("WHILE"):
            target_token = self._advance()
            return ast.ContinueStatement(target="while", span=self._span_from_tokens(continue_token, target_token))
        if self._check_identifier_value("loop"):
            target_token = self._advance()
            return ast.ContinueStatement(target="loop", span=self._span_from_tokens(continue_token, target_token))
        return ast.ContinueStatement(target=None, span=self._span_from_token(continue_token))

    def _parse_goto_statement(self) -> ast.GotoStatement:
        goto_token = self._peek(-1)
        label_token = self._expect_identifier_token("Expected label name after Goto")
        return ast.GotoStatement(
            label=label_token.value,
            span=self._span_from_tokens(goto_token, label_token),
        )

    def _parse_label_statement(self) -> ast.LabelStatement:
        name_token = self._expect_identifier_token("Expected label name")
        colon_token = self._expect_type(TokenType.COLON, "Expected ':' after label name")
        return ast.LabelStatement(
            name=name_token.value,
            span=self._span_from_tokens(name_token, colon_token),
        )

    def _parse_assignment_statement(self) -> ast.Assignment:
        target = self._parse_assignment_target()
        self._expect_type(TokenType.ASSIGN, "Expected '=' in assignment")
        value = self.parse_expression()
        return ast.Assignment(
            target=target,
            value=value,
            span=self._span_from_nodes(target, value),
        )

    def _parse_var_decl(self) -> ast.VarDecl:
        decl_token = self._advance()    # consume Dim / Local / Global / Redim
        declarators = self._parse_declarator_list()

        span = self._span_from_token(decl_token)
        for declarator in declarators:
            span = self._merge_spans(span, self._span_from_node(declarator))

        return ast.VarDecl(
            storage_kind=decl_token.value.lower(),
            declarators=declarators,
            span=span,
        )

    def _parse_const_decl(self) -> ast.ConstDecl:
        const_token = self._expect_keyword("CONST", "Expected 'Const'")
        declarators = self._parse_declarator_list(require_initializer=True)

        span = self._span_from_token(const_token)
        for declarator in declarators:
            span = self._merge_spans(span, self._span_from_node(declarator))

        return ast.ConstDecl(
            declarators=declarators,
            span=span,
        )

    def _parse_declarator_list(self, require_initializer: bool = False) -> list[ast.Declarator]:
        declarators: list[ast.Declarator] = []

        while True:
            name_token = self._expect_identifier_token("Expected variable name")
            type_name = self._parse_optional_type_annotation()
            initializer = None
            declarator_span = self._span_from_token(name_token)

            if self._match_type(TokenType.ASSIGN):
                initializer = self.parse_expression()
                declarator_span = self._merge_spans(
                    declarator_span,
                    self._span_from_node(initializer),
                )
            elif require_initializer:
                self._error_unexpected_current("'=' followed by an initializer")

            declarators.append(
                ast.Declarator(
                    name=name_token.value,
                    type_name=type_name,
                    initializer=initializer,
                    span=declarator_span,
                )
            )

            if not self._match_type(TokenType.COMMA):
                break

        return declarators

    def _function_header_allows_parameter_list(self) -> bool:
        return self._check_type(TokenType.LPAREN)

    def _parse_parameter_list(self) -> list[ast.ParamDecl]:
        params: list[ast.ParamDecl] = []

        if not self._match_type(TokenType.LPAREN):
            return params

        if not self._check_type(TokenType.RPAREN):
            while True:
                modifier_token = None
                is_byval = False
                is_byref = False
                if self._check_keyword("BYVAL"):
                    modifier_token = self._advance()
                    is_byval = True
                elif self._check_keyword("BYREF"):
                    modifier_token = self._advance()
                    is_byref = True

                name_token = self._expect_identifier_token("Expected parameter name")
                type_name = self._parse_optional_type_annotation()
                default_value = None

                param_span = self._span_from_token(modifier_token or name_token)

                if self._match_type(TokenType.ASSIGN):
                    default_value = self.parse_expression()
                    param_span = self._merge_spans(param_span, self._span_from_node(default_value))

                params.append(
                    ast.ParamDecl(
                        name=name_token.value,
                        type_name=type_name,
                        default=default_value,
                        is_byval=is_byval,
                        is_byref=is_byref,
                        span=param_span,
                    )
                )

                if not self._match_type(TokenType.COMMA):
                    break

        self._expect_type(TokenType.RPAREN, "Expected ')' after parameter list")
        return params

    def _parse_struct_fields(self) -> list[ast.StructFieldDecl]:
        fields: list[ast.StructFieldDecl] = []
        self._consume_separators()

        while not self._at_end() and not self._is_block_terminator({TokenType.ENDSTRUCT}):
            field = self._parse_struct_field_decl()
            fields.append(field)
            self._require_statement_separator_after_statement(end_tokens={TokenType.ENDSTRUCT})
            self._consume_separators()

        if self._at_end():
            self._error_unexpected_current("ENDSTRUCT")

        return fields

    def _parse_record_fields(self) -> list[ast.RecordFieldDecl]:
        fields: list[ast.RecordFieldDecl] = []
        self._consume_separators()

        while not self._at_end() and not self._is_block_terminator({TokenType.ENDRECORD}):
            field = self._parse_record_field_decl()
            fields.append(field)
            self._require_statement_separator_after_statement(end_tokens={TokenType.ENDRECORD})
            self._consume_separators()

        if self._at_end():
            self._error_unexpected_current("ENDRECORD")

        return fields

    def _parse_enum_members(self) -> list[ast.EnumMemberDecl]:
        members: list[ast.EnumMemberDecl] = []
        self._consume_separators()

        while not self._at_end() and not self._is_enum_terminator_ahead():
            member_token = self._expect_identifier_token("Expected enum member name")
            initializer = None
            member_span = self._span_from_token(member_token)

            if self._match_type(TokenType.ASSIGN):
                initializer = self.parse_expression()
                member_span = self._merge_spans(member_span, self._span_from_node(initializer))

            members.append(
                ast.EnumMemberDecl(
                    name=member_token.value,
                    initializer=initializer,
                    span=member_span,
                )
            )

            if self._is_enum_terminator_ahead():
                break

            self._require_statement_separator_after_statement(end_tokens={TokenType.ENDENUM})
            self._consume_separators()

        if self._at_end():
            self._error_unexpected_current("ENDENUM")

        return members

    def _parse_struct_field_decl(self) -> ast.StructFieldDecl:
        name_token = self._expect_identifier_token("Expected field name")
        type_name = self._parse_required_type_annotation()
        initializer = None
        field_span = self._span_from_token(name_token)

        if self._match_type(TokenType.ASSIGN):
            initializer = self.parse_expression()
            field_span = self._merge_spans(field_span, self._span_from_node(initializer))

        return ast.StructFieldDecl(
            name=name_token.value,
            type_name=type_name,
            initializer=initializer,
            span=field_span,
        )

    def _parse_record_field_decl(self) -> ast.RecordFieldDecl:
        name_token = self._expect_identifier_token("Expected field name")
        type_name = self._parse_required_type_annotation()
        initializer = None
        field_span = self._span_from_token(name_token)

        if self._match_type(TokenType.ASSIGN):
            initializer = self.parse_expression()
            field_span = self._merge_spans(field_span, self._span_from_node(initializer))

        return ast.RecordFieldDecl(
            name=name_token.value,
            type_name=type_name,
            initializer=initializer,
            span=field_span,
        )

    def _parse_block_until(self, end_tokens: set[TokenType]) -> list[ast.Statement]:
        statements: list[ast.Statement] = []
        self._consume_separators()

        while not self._at_end() and not self._is_block_terminator(end_tokens):
            statement = self.parse_statement()
            if statement is not None:
                statements.append(statement)
            self._require_statement_separator_after_statement(end_tokens=end_tokens)
            self._consume_separators()

        if self._at_end() and end_tokens:
            expected = " or ".join(sorted(token.name for token in end_tokens))
            self._error_unexpected_current(expected)

        return statements

    def _parse_unary_expression(self) -> ast.Expression:
        token_type = self._token_type(self._peek())
        operator_text = UNARY_OPERATORS.get(token_type)
        if operator_text is not None:
            operator_token = self._advance()
            operand = self._parse_unary_expression()
            return ast.UnaryExpr(
                operator=operator_text,
                operand=operand,
                span=self._span_from_token_to_node(operator_token, operand),
            )

        return self._parse_postfix_expression()

    def _parse_postfix_expression(self) -> ast.Expression:
        expr = self._parse_primary_expression()

        while True:
            token_type = self._token_type(self._peek())

            if self._match_type(TokenType.LPAREN):
                args = self._finish_parenthesized_arguments()
                closing_token = self._peek(-1)
                expr = ast.CallExpr(
                    callee=expr,
                    args=args,
                    span=self._span_from_node_to_token(expr, closing_token),
                )
                continue

            if self._match_type(TokenType.LBRACKET):
                index_expr = self.parse_expression()
                rbracket_token = self._expect_type(TokenType.RBRACKET, "Expected ']' after index expression")
                expr = ast.IndexExpr(
                    base=expr,
                    index=index_expr,
                    span=self._span_from_node_to_token(expr, rbracket_token),
                )
                continue

            if self._match_type(TokenType.DOT):
                member_token = self._expect_identifier_token("Expected member name after '.'")
                expr = ast.BinaryExpr(
                    left=expr,
                    operator=".",
                    right=ast.Identifier(
                        name=member_token.value,
                        span=self._span_from_token(member_token),
                    ),
                    span=self._span_from_node_to_token(expr, member_token),
                )
                continue

            postfix_operator_text = POSTFIX_UNARY_OPERATORS.get(token_type)
            if postfix_operator_text is not None:
                operator_token = self._advance()
                expr = ast.UnaryExpr(
                    operator=postfix_operator_text,
                    operand=expr,
                    is_postfix=True,
                    span=self._span_from_node_to_token(expr, operator_token),
                )
                continue

            break

        return expr

    def _parse_primary_expression(self) -> ast.Expression:
        token = self._peek()
        token_type = self._token_type(token)
        token_value = token.value
        upper = token_value.upper()

        if token_type == TokenType.IDENTIFIER:
            self._advance()
            if upper == "NULL":
                return ast.NullLiteral(span=self._span_from_token(token))
            if upper == "TRUE":
                 return ast.BooleanLiteral(value=True, span=self._span_from_token(token))
            if upper == "FALSE":
                 return ast.BooleanLiteral(value=False, span=self._span_from_token(token))
            
            return ast.Identifier(
                name=token_value,
                span=self._span_from_token(token),
            )

        if token_type == TokenType.HOST_IDENTIFIER:
            self._advance()
            return ast.HostIdentifier(
                name=token_value[1:],
                span=self._span_from_token(token),
            )

        if token_type == TokenType.NUMBER:
            self._advance()
            return self._parse_number_literal(token)

        if token_type == TokenType.STRING:
            self._advance()
            return ast.StringLiteral(
                value=self._decode_string_literal(token_value),
                is_raw=(len(token_value) >= 2 and token_value[0] == "'" and token_value[-1] == "'"),
                span=self._span_from_token(token),
            )

        if token_type == TokenType.INTERP_STRING:
            self._advance()
            return self._parse_interpolated_string_literal(token)

        if token_type == TokenType.TRUE:
            self._advance()
            return ast.BooleanLiteral(
                value=True,
                span=self._span_from_token(token),
            )

        if token_type == TokenType.FALSE:
            self._advance()
            return ast.BooleanLiteral(
                value=False,
                span=self._span_from_token(token),
            )

        if token_type == TokenType.BOOLEAN:
            self._advance()
            return ast.BooleanLiteral(
                value=(upper == "TRUE"),
                span=self._span_from_token(token),
            )

        if token_type == TokenType.NULL:
            self._advance()
            return ast.NullLiteral(
                span=self._span_from_token(token),
            )

        if token_type == TokenType.LPAREN:
            lparen_token = self._advance()
            expr = self.parse_expression()
            rparen_token = self._expect_type(TokenType.RPAREN, "Expected ')' after expression")
            return ast.ParenExpr(
                expression=expr,
                span=self._span_from_tokens(lparen_token, rparen_token),
            )

        if token_type == TokenType.LBRACKET:
            return self._parse_array_literal()

        self._error_expected_expression_current()
        self._advance()
        return ast.Identifier(name="<error>")

    def _parse_array_literal(self) -> ast.ArrayLiteral:
        lbracket_token = self._expect_type(TokenType.LBRACKET, "Expected '['")
        items: list[ast.Expression] = []

        if not self._check_type(TokenType.RBRACKET):
            while True:
                items.append(self.parse_expression())
                if not self._match_type(TokenType.COMMA):
                    break

        rbracket_token = self._expect_type(TokenType.RBRACKET, "Expected ']' after array literal")
        return ast.ArrayLiteral(
            items=items,
            span=self._span_from_tokens(lbracket_token, rbracket_token),
        )

    def _finish_parenthesized_arguments(self) -> list[ast.Expression]:
        args: list[ast.Expression] = []
        self._consume_separators()
        if not self._check_type(TokenType.RPAREN):
            while True:
                args.append(self.parse_expression())
                self._consume_separators()
                if not self._match_type(TokenType.COMMA):
                    break
                self._consume_separators()
        self._expect_type(TokenType.RPAREN, "Expected ')' after arguments")
        return args

    def _parse_assignment_target(self) -> ast.Expression:
        if not self._check_type_in({TokenType.IDENTIFIER, TokenType.HOST_IDENTIFIER}):
            self._error_unexpected_current("assignment target")
            return ast.Identifier(name="<error>")

        name_token = self._advance()
        if self._token_type(name_token) == TokenType.HOST_IDENTIFIER:
            target: ast.Expression = ast.HostIdentifier(
                name=name_token.value[1:],
                span=self._span_from_token(name_token),
            )
        else:
            target = ast.Identifier(
                name=name_token.value,
                span=self._span_from_token(name_token),
            )

        while True:
            if self._match_type(TokenType.LBRACKET):
                index_expr = self.parse_expression()
                rbracket_token = self._expect_type(TokenType.RBRACKET, "Expected ']' after target index")
                target = ast.IndexExpr(
                    base=target,
                    index=index_expr,
                    span=self._span_from_node_to_token(target, rbracket_token),
                )
                continue

            if self._match_type(TokenType.DOT):
                member_token = self._expect_identifier_token("Expected member name after '.'")
                target = ast.BinaryExpr(
                    left=target,
                    operator=".",
                    right=ast.Identifier(
                        name=member_token.value,
                        span=self._span_from_token(member_token),
                    ),
                    span=self._span_from_node_to_token(target, member_token),
                )
                continue

            break
        
        return target

    def _skip_to_statement_boundary(self) -> None:
        while not self._at_end():
            token_type = self._token_type(self._peek())
            if token_type in NEWLINE_TYPES or token_type in BLOCK_TERMINATORS:
                return
            self._advance()

    def _unexpected_statement_terminator(self) -> None:
        self._error_expected_statement_current()

    def _unsupported_statement(self, statement_name: str) -> None:
        token = self._peek()
        self.diagnostics.error(
            "PAR004",
            f"'{statement_name}' statements are not implemented yet.",
            span=self._span_from_token(token),
            source_name=self.source_name,
        )

    def _error_unexpected_current(self, expected: str) -> None:
        token = self._peek()
        start, end = self._token_span(token)
        actual_type = self._token_type(token)
        actual_name = actual_type.name if actual_type is not None else "unknown"
        self.diagnostics.add(
            make_unexpected_token(expected, actual_name, start, end, source_name=self.source_name)
        )

    def _error_expected_expression_current(self) -> None:
        token = self._peek()
        start, end = self._token_span(token)
        self.diagnostics.add(make_expected_expression(start, end, source_name=self.source_name))

    def _error_expected_statement_current(self) -> None:
        token = self._peek()
        start, end = self._token_span(token)
        self.diagnostics.add(make_expected_statement(start, end, source_name=self.source_name))

    def _peek(self, offset: int = 0) -> Token:
        idx = self.index + offset
        if idx < 0:
            idx = 0
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        token = self._peek()
        if not self._at_end():
            self.index += 1
        return token

    def _at_end(self) -> bool:
        return self._token_type(self._peek()) == TokenType.EOF

    def _token_type(self, token: Any) -> TokenType | None:
        return getattr(token, "type", None)

    def _token_value(self, token: Any) -> str:
        return str(getattr(token, "value", ""))

    def _check_type(self, token_type: TokenType, offset: int = 0) -> bool:
        return self._token_type(self._peek(offset)) == token_type

    def _check_type_in(self, token_types: set[TokenType], offset: int = 0) -> bool:
        return self._token_type(self._peek(offset)) in token_types

    def _match_type(self, token_type: TokenType) -> bool:
        if self._check_type(token_type):
            self._advance()
            return True
        return False

    def _check_keyword(self, keyword: str, offset: int = 0) -> bool:
        expected_type = KEYWORD_TOKEN_MAP.get(keyword.upper())
        token = self._peek(offset)
        token_type = self._token_type(token)
        token_text = self._token_value(token).upper()
        if expected_type is not None and token_type == expected_type:
            return True
        return token_text == keyword.upper()

    def _match_keyword(self, keyword: str) -> bool:
        if self._check_keyword(keyword):
            self._advance()
            return True
        return False

    def _expect_keyword(self, keyword: str, message: str) -> Token:
        if self._check_keyword(keyword):
            return self._advance()
        self._error_unexpected_current(repr(keyword))
        return self._synthetic_token(KEYWORD_TOKEN_MAP.get(keyword.upper(), TokenType.IDENTIFIER), keyword)

    def _expect_type(self, token_type: TokenType, message: str) -> Token:
        if self._check_type(token_type):
            return self._advance()
        self._error_unexpected_current(token_type.name)
        return self._synthetic_token(token_type, "")

    def _expect_identifier(self, message: str) -> str:
        return self._expect_identifier_token(message).value

    def _expect_identifier_token(self, message: str) -> Token:
        if self._check_identifier():
            return self._advance()
        self._error_unexpected_current("identifier")
        return self._synthetic_token(TokenType.IDENTIFIER, "<error>")

    def _check_identifier(self, offset: int = 0) -> bool:
        return self._check_type(TokenType.IDENTIFIER, offset)

    def _check_identifier_value(self, value: str, offset: int = 0) -> bool:
        token = self._peek(offset)
        return (
            self._token_type(token) == TokenType.IDENTIFIER
            and self._token_value(token).lower() == value.lower()
        )

    def _consume_separators(self, required: bool = False, message: str = "Expected statement separator") -> None:
        consumed = False
        while self._check_type(TokenType.NEWLINE):
            self._advance()
            consumed = True
        if required and not consumed:
            self._error_unexpected_current("newline")

    def _require_statement_separator_after_statement(
        self,
        *,
        end_tokens: set[TokenType] | None = None,
    ) -> None:
        if self._at_end() or self._statement_terminator_ahead():
            return
        if end_tokens is not None and self._is_block_terminator(end_tokens):
            return

        self.diagnostics.add(
            make_missing_token(
                "newline",
                self._token_span(self._peek())[0],
                self._token_span(self._peek())[1],
                source_name=self.source_name,
            )
        )
        self._skip_to_statement_boundary()

    def _statement_terminator_ahead(self) -> bool:
        token_type = self._token_type(self._peek())
        return (
            token_type == TokenType.EOF
            or token_type == TokenType.NEWLINE
            or token_type in BLOCK_TERMINATORS
            or self._is_spaced_function_terminator()
            or self._is_spaced_if_terminator()
            or self._is_spaced_select_terminator()
            or self._is_spaced_struct_terminator()
            or self._is_spaced_record_terminator()
            or self._is_spaced_enum_terminator()
        )

    def _is_block_terminator(self, end_tokens: set[TokenType]) -> bool:
        token_type = self._token_type(self._peek())
        if token_type in end_tokens:
            return True

        return (
            (TokenType.ENDFUNC in end_tokens and self._is_spaced_function_terminator())
            or (TokenType.ENDIF in end_tokens and self._is_spaced_if_terminator())
            or (TokenType.ENDSELECT in end_tokens and self._is_spaced_select_terminator())
            or (TokenType.ENDSTRUCT in end_tokens and self._is_spaced_struct_terminator())
            or (TokenType.ENDRECORD in end_tokens and self._is_spaced_record_terminator())
            or (TokenType.ENDENUM in end_tokens and self._is_spaced_enum_terminator())
        )

    def _is_spaced_function_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("FUNC", 1)

    def _is_spaced_if_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("IF", 1)

    def _is_spaced_select_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("SELECT", 1)

    def _is_spaced_struct_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("STRUCT", 1)

    def _is_spaced_record_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("RECORD", 1)

    def _is_spaced_enum_terminator(self) -> bool:
        return self._check_keyword("END") and self._check_keyword("ENUM", 1)

    def _is_enum_terminator_ahead(self) -> bool:
        return self._check_type(TokenType.ENDENUM) or self._is_spaced_enum_terminator()

    def _expect_enum_terminator(self) -> Token:
        if self._check_keyword("ENDENUM"):
            return self._advance()

        if self._is_spaced_enum_terminator():
            end_token = self._advance()
            enum_token = self._advance()
            return self._synthetic_token_from_bounds(
                TokenType.ENDENUM,
                "End Enum",
                start_token=end_token,
                end_token=enum_token,
            )

        self._error_unexpected_current(repr("ENDENUM"))
        return self._synthetic_token(TokenType.ENDENUM, "EndEnum")

    def _parse_optional_type_annotation(self) -> str | None:
        if not self._match_type(TokenType.AS):
            return None
        return self._parse_type_name()

    def _parse_required_type_annotation(self) -> str:
        self._expect_type(TokenType.AS, "Expected 'As'")
        return self._parse_type_name()

    def _parse_external_required_type_annotation(self) -> tuple[str, int | None]:
        self._expect_type(TokenType.AS, "Expected 'As'")
        return self._parse_type_annotation_with_optional_string_buffer_size()

    def _parse_type_name(self) -> str:
        type_token = self._expect_identifier_token("Expected type name")
        return normalize_type_name(type_token.value)

    def _parse_type_annotation_with_optional_string_buffer_size(self) -> tuple[str, int | None]:
        type_name = self._parse_type_name()
        string_buffer_size: int | None = None

        if type_name == "String" and self._check_type(TokenType.LPAREN):
            self._advance()
            size_token = self._expect_type(TokenType.NUMBER, "Expected string buffer size")
            try:
                string_buffer_size = int(str(size_token.value).replace("_", ""))
            except ValueError:
                self._error_unexpected_current("a valid string buffer size")
                string_buffer_size = None
            self._expect_type(TokenType.RPAREN, "Expected ')' after string buffer size")

        return type_name, string_buffer_size

    def _looks_like_assignment(self) -> bool:
        save = self.index
        try:
            if not self._check_type_in({TokenType.IDENTIFIER, TokenType.HOST_IDENTIFIER}):
                return False
            self._advance()
            while True:
                if self._match_type(TokenType.DOT):
                    if not self._check_identifier():
                        return False
                    self._advance()
                    continue
                if self._match_type(TokenType.LBRACKET):
                    depth = 1
                    while depth > 0 and not self._at_end():
                        if self._match_type(TokenType.LBRACKET):
                            depth += 1
                        elif self._match_type(TokenType.RBRACKET):
                            depth -= 1
                        else:
                            self._advance()
                    continue
                break
            return self._check_type(TokenType.ASSIGN)
        finally:
            self.index = save

    def _can_start_expression(self, token: Token) -> bool:
        token_type = self._token_type(token)
        token_text = self._token_value(token).upper()
        return (
            token_type in IDENT_TYPES
            or token_type in NUMBER_TYPES
            or token_type in STRING_TYPES
            or token_type in BOOLEAN_TYPES
            or token_type == TokenType.NULL
            or token_type in {TokenType.LPAREN, TokenType.LBRACKET}
            or token_type in UNARY_OPERATORS
            or token_text == "NULL"
        )

    def _parse_number_literal(self, token: Token) -> ast.Expression:
        token_value = token.value
        text = token_value.replace("_", "")
        span = self._span_from_token(token)
        try:
            if text.lower().startswith("0x"):
                return ast.IntegerLiteral(value=int(text, 16), span=span)
            if any(ch in text for ch in ".eE"):
                return ast.FloatLiteral(value=float(text), span=span)
            return ast.IntegerLiteral(value=int(text, 10), span=span)
        except ValueError:
            return (
                ast.FloatLiteral(value=0.0, span=span)
                if any(ch in text for ch in ".eE")
                else ast.IntegerLiteral(value=0, span=span)
            )

    def _decode_string_literal(self, token_value: str) -> str:
        if len(token_value) >= 2 and token_value[0] == "'" and token_value[-1] == "'":
            return token_value[1:-1]

        if len(token_value) >= 2 and token_value[0] == '"' and token_value[-1] == '"':
            return self._decode_escaped_string_content(token_value[1:-1])

        return token_value

    def _parse_interpolated_string_literal(self, token: Token) -> ast.Expression:
        token_value = token.value
        span = self._span_from_token(token)

        if not (len(token_value) >= 3 and token_value.startswith('$"') and token_value.endswith('"')):
            self.diagnostics.add(
                make_syntax_error(
                    "Invalid interpolated string literal.",
                    token.start_index,
                    token.end_index,
                    source_name=self.source_name,
                )
            )
            return ast.InterpolatedStringLiteral(span=span)

        inner = token_value[2:-1]
        parts: list[ast.InterpolatedStringPart] = []
        text_buffer: list[str] = []
        index = 0
        length = len(inner)

        while index < length:
            ch = inner[index]

            if ch == "{":
                if index + 1 < length and inner[index + 1] == "{":
                    text_buffer.append("{")
                    index += 2
                    continue

                if text_buffer:
                    parts.append(
                        ast.InterpolatedTextPart(
                            value=self._decode_escaped_string_content("".join(text_buffer))
                        )
                    )
                    text_buffer = []

                item = self._read_interpolation_item(
                    inner,
                    index,
                    token,
                )
                if item is None:
                    return ast.InterpolatedStringLiteral(parts=parts, span=span)

                expression = self._parse_interpolation_expression(
                    item.expression_text,
                    expression_span_start=item.expression_span_start,
                    expression_span_end=item.expression_span_end,
                )
                parts.append(
                    ast.InterpolationPart(
                        expression=expression,
                        format_spec=item.format_spec,
                    )
                )
                index = item.next_index
                continue

            if ch == "}":
                if index + 1 < length and inner[index + 1] == "}":
                    text_buffer.append("}")
                    index += 2
                    continue

                self.diagnostics.add(
                    make_syntax_error(
                        "Single '}' is not allowed in interpolated string text.",
                        self._interpolated_inner_absolute_index(token, index),
                        self._interpolated_inner_absolute_index(token, index) + 1,
                        source_name=self.source_name,
                    )
                )
                text_buffer.append("}")
                index += 1
                continue

            text_buffer.append(ch)
            index += 1

        if text_buffer:
            parts.append(
                ast.InterpolatedTextPart(
                    value=self._decode_escaped_string_content("".join(text_buffer))
                )
            )

        return ast.InterpolatedStringLiteral(parts=parts, span=span)

    def _read_interpolation_item(
        self,
        inner: str,
        start_index: int,
        token: Token,
    ) -> InterpolationReadResult | None:
        index = start_index + 1
        expression_chars: list[str] = []
        quote_char: str | None = None
        format_spec: str | None = None
        paren_depth = 0
        bracket_depth = 0
        expression_start = index

        while index < len(inner):
            ch = inner[index]

            if quote_char is not None:
                expression_chars.append(ch)
                if quote_char == '"' and ch == "\\" and index + 1 < len(inner):
                    index += 1
                    expression_chars.append(inner[index])
                elif quote_char == '"' and ch == '"' and index + 1 < len(inner) and inner[index + 1] == '"':
                    index += 1
                    expression_chars.append(inner[index])
                elif ch == quote_char:
                    quote_char = None
                index += 1
                continue

            if ch in {'"', "'"}:
                quote_char = ch
                expression_chars.append(ch)
                index += 1
                continue

            if ch == "(":
                paren_depth += 1
                expression_chars.append(ch)
                index += 1
                continue

            if ch == ")" and paren_depth > 0:
                paren_depth -= 1
                expression_chars.append(ch)
                index += 1
                continue

            if ch == "[":
                bracket_depth += 1
                expression_chars.append(ch)
                index += 1
                continue

            if ch == "]" and bracket_depth > 0:
                bracket_depth -= 1
                expression_chars.append(ch)
                index += 1
                continue

            if ch == ":" and paren_depth == 0 and bracket_depth == 0:
                expression_text = "".join(expression_chars)
                expression_end = index
                index += 1
                format_start = index
                while index < len(inner) and inner[index] != "}":
                    index += 1
                if index >= len(inner):
                    self.diagnostics.add(
                        make_missing_token(
                            "}",
                            self._interpolated_inner_absolute_index(token, start_index),
                            token.end_index,
                            source_name=self.source_name,
                        )
                    )
                    return None
                format_spec = inner[format_start:index].strip() or None
                if format_spec is not None and not self._is_valid_interpolation_format_spec(format_spec):
                    self.diagnostics.add(
                        make_syntax_error(
                            f"Invalid interpolation format specifier '{format_spec}'.",
                            self._interpolated_inner_absolute_index(token, format_start),
                            self._interpolated_inner_absolute_index(token, index),
                            source_name=self.source_name,
                        )
                    )
                return InterpolationReadResult(
                    expression_text=expression_text,
                    expression_span_start=self._interpolated_inner_absolute_index(token, expression_start),
                    expression_span_end=self._interpolated_inner_absolute_index(token, expression_end),
                    format_spec=format_spec,
                    format_span_start=self._interpolated_inner_absolute_index(token, format_start),
                    format_span_end=self._interpolated_inner_absolute_index(token, index),
                    next_index=index + 1,
                )

            if ch == "}" and paren_depth == 0 and bracket_depth == 0:
                expression_text = "".join(expression_chars)
                return InterpolationReadResult(
                    expression_text=expression_text,
                    expression_span_start=self._interpolated_inner_absolute_index(token, expression_start),
                    expression_span_end=self._interpolated_inner_absolute_index(token, index),
                    format_spec=format_spec,
                    format_span_start=None,
                    format_span_end=None,
                    next_index=index + 1,
                )

            expression_chars.append(ch)
            index += 1

        self.diagnostics.add(
            make_missing_token(
                "}",
                self._interpolated_inner_absolute_index(token, start_index),
                token.end_index,
                source_name=self.source_name,
            )
        )
        return None

    def _decode_escaped_string_content(self, inner: str) -> str:
        result: list[str] = []
        index = 0
        length = len(inner)

        while index < length:
            ch = inner[index]

            if ch == '"' and index + 1 < length and inner[index + 1] == '"':
                result.append('"')
                index += 2
                continue

            if ch == "\\" and index + 1 < length:
                escape = inner[index + 1]

                if escape == "r":
                    result.append("\r")
                    index += 2
                    continue
                if escape == "n":
                    result.append("\n")
                    index += 2
                    continue
                if escape == "t":
                    result.append("\t")
                    index += 2
                    continue
                if escape == "0":
                    result.append("\0")
                    index += 2
                    continue
                if escape == "\\":
                    result.append("\\")
                    index += 2
                    continue
                if escape == '"':
                    result.append('"')
                    index += 2
                    continue

            result.append(ch)
            index += 1

        return "".join(result)

    def _parse_interpolation_expression(
        self,
        expression_text: str,
        *,
        expression_span_start: int,
        expression_span_end: int,
    ) -> ast.Expression:
        if not expression_text.strip():
            self.diagnostics.add(
                make_expected_expression(
                    expression_span_start,
                    expression_span_end,
                    source_name=self.source_name,
                )
            )
            return ast.Identifier(
                name="<error>",
                span=TextSpan(
                    expression_span_start,
                    max(expression_span_start + 1, expression_span_end),
                ),
            )

        trimmed_expression = expression_text.lstrip()
        leading_trim = len(expression_text) - len(trimmed_expression)
        nested_source_start = expression_span_start + leading_trim

        nested_diagnostics = DiagnosticBag()
        nested_tokens = lex(
            trimmed_expression,
            diagnostics=nested_diagnostics,
            source_name=self.source_name,
        )
        nested_parser = Parser(
            nested_tokens,
            diagnostics=nested_diagnostics,
            source_name=self.source_name,
        )
        expression = nested_parser.parse_expression_only()
        for diagnostic in nested_diagnostics.items:
            self.diagnostics.add(
                self._shift_diagnostic_span(diagnostic, nested_source_start)
            )
        return expression

    @staticmethod
    def _shift_diagnostic_span(diagnostic, offset: int):
        if diagnostic.span is None:
            return diagnostic
        return replace(
            diagnostic,
            span=TextSpan(
                diagnostic.span.start + offset,
                diagnostic.span.end + offset,
            ),
        )

    @staticmethod
    def _interpolated_inner_absolute_index(token: Token, inner_offset: int) -> int:
        return token.start_index + 2 + inner_offset

    @staticmethod
    def _is_valid_interpolation_format_spec(format_spec: str) -> bool:
        if format_spec in {"d", "x", "X", "o", "b", "f"}:
            return True
        if (
            len(format_spec) >= 3
            and format_spec[0] == "."
            and format_spec[-1] == "f"
            and format_spec[1:-1].isdigit()
        ):
            return True
        return False

    def _token_span(self, token: Any) -> tuple[int, int]:
        start = getattr(token, "start_index", None)
        end = getattr(token, "end_index", None)
        if start is None or end is None:
            raise ValueError("Parser expects tokens to carry start_index/end_index offsets.")
        return int(start), max(int(start), int(end))


    def _span_from_token(self, token) -> TextSpan | None:
        if token is None:
            return None

        start, end = self._token_span(token)
        return TextSpan(start, end)


    def _span_from_tokens(self, start_token, end_token) -> TextSpan | None:
        if start_token is None and end_token is None:
            return None
        if start_token is None:
            return self._span_from_token(end_token)
        if end_token is None:
            return self._span_from_token(start_token)

        start, _ = self._token_span(start_token)
        _, end = self._token_span(end_token)
        return TextSpan(start, max(start, end))


    def _merge_spans(self, left: TextSpan | None, right: TextSpan | None) -> TextSpan | None:
        if left is None:
            return right
        if right is None:
            return left
        return TextSpan(min(left.start, right.start), max(left.end, right.end))


    def _span_from_node(self, node) -> TextSpan | None:
        if node is None:
            return None
        return getattr(node, "span", None)


    def _span_from_nodes(self, *nodes) -> TextSpan | None:
        span = None
        for node in nodes:
            span = self._merge_spans(span, self._span_from_node(node))
        return span


    def _span_from_node_to_token(self, node, token) -> TextSpan | None:
        return self._merge_spans(
            self._span_from_node(node),
            self._span_from_token(token),
        )


    def _span_from_token_to_node(self, token, node) -> TextSpan | None:
        return self._merge_spans(
            self._span_from_token(token),
            self._span_from_node(node),
        )

    def _synthetic_token(self, token_type: TokenType, value: str) -> Token:
        token = self._peek()
        line = getattr(token, "line", 1)
        column = getattr(token, "column", 1)
        end_line = getattr(token, "end_line", line)
        end_column = getattr(token, "end_column", column)

        return Token(
            type=token_type,
            value=value,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            start_index=token.start_index,
            end_index=token.start_index,
        )

    def _synthetic_token_from_bounds(
        self,
        token_type: TokenType,
        value: str,
        *,
        start_token: Token,
        end_token: Token,
    ) -> Token:
        start_line = getattr(start_token, "line", 1)
        start_column = getattr(start_token, "column", 1)
        end_line = getattr(end_token, "end_line", getattr(end_token, "line", 1))
        end_column = getattr(end_token, "end_column", getattr(end_token, "column", 1))

        return Token(
            type=token_type,
            value=value,
            line=start_line,
            column=start_column,
            end_line=end_line,
            end_column=end_column,
            start_index=start_token.start_index,
            end_index=end_token.end_index,
        )

def parse(
    tokens: Sequence[Token],
    diagnostics: Optional[DiagnosticBag] = None,
    source_name: str = "<memory>",
) -> ast.Program:
    parser = Parser(tokens, diagnostics=diagnostics, source_name=source_name)
    return parser.parse()

def parse_expression(
    tokens: Sequence[Token],
    diagnostics: Optional[DiagnosticBag] = None,
    source_name: str = "<memory>",
) -> ast.Expression:
    parser = Parser(tokens, diagnostics=diagnostics, source_name=source_name)
    return parser.parse_expression_only()


def parse_with_diagnostics(
    tokens: Sequence[Token],
    diagnostics: Optional[DiagnosticBag] = None,
    source_name: str = "<memory>",
) -> ParseResult:
    bag = diagnostics if diagnostics is not None else DiagnosticBag()
    parser = Parser(tokens, diagnostics=bag, source_name=source_name)
    root = parser.parse()
    return ParseResult(root=root, diagnostics=bag)


__all__ = [
    "ParseResult",
    "Parser",
    "parse",
    "parse_expression",
    "parse_with_diagnostics",
]
