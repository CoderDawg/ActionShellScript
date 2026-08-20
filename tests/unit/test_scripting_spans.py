from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.scripting.diagnostics import TextSpan, span_from_legacy_token, span_from_token
from core.scripting import ast_nodes as ast
from core.scripting.lexer import lex
from core.scripting.parser import Parser
from core.scripting.tokens import TokenType


def test_span_from_token_prefers_absolute_offsets() -> None:
    token = lex("foo")[0]

    assert span_from_token(token) == TextSpan(0, 3)


def test_span_from_token_requires_explicit_legacy_fallback_when_offsets_are_missing() -> None:
    @dataclass
    class LegacyToken:
        value: str
        line: int
        column: int

    token = LegacyToken(value="abc", line=2, column=4)

    with pytest.raises(ValueError, match="start_index/end_index"):
        span_from_token(token)

    assert span_from_legacy_token(token, line_width=100) == TextSpan(103, 106)


def test_parser_synthetic_tokens_anchor_at_the_current_offset() -> None:
    tokens = lex("Dim = 1\n")
    parser = Parser(tokens)
    parser._advance()  # Skip the Dim token so the current token is '='.

    synthetic_identifier = parser._synthetic_token(TokenType.IDENTIFIER, "<error>")
    equals_token = tokens[1]

    assert synthetic_identifier.start_index == equals_token.start_index
    assert synthetic_identifier.end_index == equals_token.start_index


def test_parser_synthetic_tokens_from_bounds_preserve_real_token_offsets() -> None:
    tokens = lex("End Function\n")
    parser = Parser(tokens)

    synthetic_terminator = parser._synthetic_token_from_bounds(
        TokenType.ENDFUNC,
        "End Function",
        start_token=tokens[0],
        end_token=tokens[1],
    )

    assert synthetic_terminator.start_index == tokens[0].start_index
    assert synthetic_terminator.end_index == tokens[1].end_index


def test_parser_treats_crlf_runtime_value_as_host_identifier() -> None:
    expression = Parser(lex("@CRLF")).parse_expression_only()

    assert isinstance(expression, ast.HostIdentifier)
    assert expression.name == "CRLF"


def test_parser_parses_ternary_expression_with_right_associative_false_branch() -> None:
    expression = Parser(lex('score >= 50 ? "Pass" : score >= 40 ? "Retry" : "Fail"')).parse_expression_only()

    assert isinstance(expression, ast.TernaryExpr)
    assert isinstance(expression.condition, ast.BinaryExpr)
    assert expression.condition.operator == ">="
    assert isinstance(expression.true_expression, ast.StringLiteral)
    assert expression.true_expression.value == "Pass"
    assert isinstance(expression.false_expression, ast.TernaryExpr)
    assert isinstance(expression.false_expression.condition, ast.BinaryExpr)
    assert expression.false_expression.condition.operator == ">="


def test_parser_parses_prefix_and_postfix_increment_decrement() -> None:
    prefix = Parser(lex("++counter")).parse_expression_only()
    postfix = Parser(lex("counter--")).parse_expression_only()
    mixed = Parser(lex("counter++ + 1")).parse_expression_only()

    assert isinstance(prefix, ast.UnaryExpr)
    assert prefix.operator == "++"
    assert prefix.is_postfix is False
    assert isinstance(prefix.operand, ast.Identifier)
    assert prefix.operand.name == "counter"

    assert isinstance(postfix, ast.UnaryExpr)
    assert postfix.operator == "--"
    assert postfix.is_postfix is True
    assert isinstance(postfix.operand, ast.Identifier)
    assert postfix.operand.name == "counter"

    assert isinstance(mixed, ast.BinaryExpr)
    assert mixed.operator == "+"
    assert isinstance(mixed.left, ast.UnaryExpr)
    assert mixed.left.is_postfix is True
