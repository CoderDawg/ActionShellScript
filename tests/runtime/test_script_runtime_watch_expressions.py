from __future__ import annotations

import pytest

from core.runtime.execution_context import ExecutionContext
from core.runtime.script_runtime import ScriptRuntime
from core.scripting.lexer import lex
from core.scripting.parser import Parser


def test_evaluate_debug_expression_uses_current_locals_and_globals() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_global("x", 3)
    context.push_call_frame("Helper", {"y": 4})

    assert runtime.evaluate_debug_expression("x + y * 2", context) == 11
    assert runtime.evaluate_debug_expression('y & "!"', context) == "4!"


def test_evaluate_debug_expression_supports_ternary_conditionals() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_global("score", 72)

    assert runtime.evaluate_debug_expression('(score >= 50) ? "Pass" : "Fail"', context) == "Pass"

    context.set_global("score", 41)
    assert runtime.evaluate_debug_expression('(score >= 50) ? "Pass" : "Fail"', context) == "Fail"


def test_evaluate_debug_expression_supports_increment_and_decrement() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_global("counter", 3)

    prefix_expression = Parser(lex("++counter")).parse_expression_only()
    postfix_expression = Parser(lex("counter--")).parse_expression_only()

    assert runtime._evaluate_expression(prefix_expression, context) == 4
    assert context.get_variable("counter") == 4

    assert runtime._evaluate_expression(postfix_expression, context) == 4
    assert context.get_variable("counter") == 3


def test_evaluate_debug_expression_rejects_function_calls() -> None:
    runtime = ScriptRuntime()
    context = ExecutionContext()
    context.set_global("x", 3)

    with pytest.raises(RuntimeError, match="cannot call functions"):
        runtime.evaluate_debug_expression("WriteLn(x)", context)
