from __future__ import annotations

import pytest

from core.scripting import ast_nodes as ast
from core.scripting.lexer import lex
from core.scripting.parser import Parser


@pytest.mark.parametrize(
    ("script", "expected_target"),
    [
        ("Continue\n", None),
        ("Continue For\n", "for"),
        ("Continue While\n", "while"),
        ("Continue Loop\n", "loop"),
        ("ContinueLoop\n", "loop"),
    ],
)
def test_continue_statement_parser_recognizes_targeted_forms(
    script: str,
    expected_target: str | None,
) -> None:
    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.ContinueStatement)
    assert statement.target == expected_target
