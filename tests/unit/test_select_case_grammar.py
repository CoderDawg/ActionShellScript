from __future__ import annotations

from core.scripting import ast_nodes as ast
from core.scripting.lexer import lex
from core.scripting.parser import Parser


def test_select_case_grammar_parses_case_values_ranges_and_else() -> None:
    script = (
        "Select Case mode\n"
        "Case 1, 2\n"
        "WriteLn(\"low\")\n"
        "Case 3 To 5\n"
        "WriteLn(\"mid\")\n"
        "Case Else\n"
        "WriteLn(\"other\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert isinstance(statement.expression, ast.Identifier)
    assert statement.expression.name == "mode"
    assert len(statement.cases) == 3

    first_case = statement.cases[0]
    assert first_case.is_else is False
    assert [type(condition) for condition in first_case.conditions] == [
        ast.SelectCaseValue,
        ast.SelectCaseValue,
    ]

    second_case = statement.cases[1]
    assert second_case.is_else is False
    assert [type(condition) for condition in second_case.conditions] == [
        ast.SelectCaseRange,
    ]

    third_case = statement.cases[2]
    assert third_case.is_else is True
    assert third_case.conditions == []


def test_select_case_grammar_parses_is_comparisons_and_like_patterns() -> None:
    script = (
        "Select Case value\n"
        "Case Is < 10, Is >= 20\n"
        "WriteLn(\"range\")\n"
        "Case Like \"A*\"\n"
        "WriteLn(\"pattern\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert [type(condition) for condition in statement.cases[0].conditions] == [
        ast.SelectCaseComparison,
        ast.SelectCaseComparison,
    ]
    assert [condition.operator for condition in statement.cases[0].conditions] == [
        "<",
        ">=",
    ]
    assert [type(condition) for condition in statement.cases[1].conditions] == [
        ast.SelectCaseLike,
    ]


def test_select_case_grammar_parses_is_not_comparisons() -> None:
    script = (
        "Select Case value\n"
        "Case Is Not < 10\n"
        "WriteLn(\"not-small\")\n"
        "Case Is Not 20\n"
        "WriteLn(\"not-twenty\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert [type(condition) for condition in statement.cases[0].conditions] == [
        ast.SelectCaseComparison,
    ]
    assert statement.cases[0].conditions[0].is_negated is True
    assert statement.cases[0].conditions[0].operator == "<"
    assert statement.cases[1].conditions[0].is_negated is True
    assert statement.cases[1].conditions[0].operator == "="


def test_select_case_grammar_parses_not_like_patterns() -> None:
    script = (
        "Select Case value\n"
        "Case Not Like \"A*\"\n"
        "WriteLn(\"other\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert [type(condition) for condition in statement.cases[0].conditions] == [
        ast.SelectCaseLike,
    ]
    assert statement.cases[0].conditions[0].is_negated is True


def test_select_case_grammar_parses_is_not_like_patterns() -> None:
    script = (
        "Select Case value\n"
        "Case Is Not Like \"A*\"\n"
        "WriteLn(\"other\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert [type(condition) for condition in statement.cases[0].conditions] == [
        ast.SelectCaseLike,
    ]
    assert statement.cases[0].conditions[0].is_negated is True


def test_select_case_grammar_parses_is_not_like_spelled_explicitly() -> None:
    script = (
        "Select Case value\n"
        "Case Is Not Like \"A*\"\n"
        "WriteLn(\"other\")\n"
        "End Select\n"
    )

    program = Parser(lex(script)).parse()

    statement = program.statements[0]
    assert isinstance(statement, ast.SelectStatement)
    assert [type(condition) for condition in statement.cases[0].conditions] == [
        ast.SelectCaseLike,
    ]
    assert statement.cases[0].conditions[0].is_negated is True
