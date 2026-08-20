"""Abstract syntax tree node definitions for the scripting frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Optional

from .diagnostics import TextSpan

# -----------------------------------------------------------------------------
# Base node types
# -----------------------------------------------------------------------------
@dataclass
class AstNode:
    span: Optional[TextSpan] = None

    @property
    def kind(self) -> str:
        return type(self).__name__

    def children(self) -> Iterable["AstNode"]:
        return ()

@dataclass
class Statement(AstNode):
    pass

@dataclass
class Expression(AstNode):
    pass


# -----------------------------------------------------------------------------
# Program / block nodes
# -----------------------------------------------------------------------------
@dataclass
class Program(AstNode):
    statements: list[Statement] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.statements


@dataclass
class Block(Statement):
    statements: list[Statement] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.statements


# -----------------------------------------------------------------------------
# Declarations
# -----------------------------------------------------------------------------
@dataclass
class Declarator(AstNode):
    name: str = ""
    type_name: Optional[str] = None
    initializer: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.initializer is not None:
            yield self.initializer


@dataclass
class ParamDecl(AstNode):
    name: str = ""
    type_name: Optional[str] = None
    string_buffer_size: Optional[int] = None
    default: Optional[Expression] = None
    is_byval: bool = False
    is_byref: bool = False
    is_const: bool = False

    def children(self) -> Iterable[AstNode]:
        if self.default is not None:
            yield self.default


@dataclass
class StructFieldDecl(AstNode):
    name: str = ""
    type_name: str = ""
    initializer: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.initializer is not None:
            yield self.initializer


@dataclass
class RecordFieldDecl(AstNode):
    name: str = ""
    type_name: str = ""
    initializer: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.initializer is not None:
            yield self.initializer


@dataclass
class EnumMemberDecl(AstNode):
    name: str = ""
    initializer: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.initializer is not None:
            yield self.initializer


@dataclass
class VarDecl(Statement):
    storage_kind: str = "dim"
    declarators: list[Declarator] = field(default_factory=list)
    
    def children(self) -> Iterable[AstNode]:
        return self.declarators


@dataclass
class ConstDecl(Statement):
    declarators: list[Declarator] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.declarators


@dataclass
class FunctionDecl(Statement):
    name: str = ""
    params: list[ParamDecl] = field(default_factory=list)
    body: Block = field(default_factory=Block)

    def children(self) -> Iterable[AstNode]:
        for param in self.params:
            yield param
        yield self.body


@dataclass
class ExternalFunctionDecl(Statement):
    name: str = ""
    library_name: str = ""
    export_name: Optional[str] = None
    params: list[ParamDecl] = field(default_factory=list)
    return_type_name: str = ""
    is_sub: bool = False
    calling_convention: str = "winapi"

    def children(self) -> Iterable[AstNode]:
        return self.params


@dataclass
class LabelStatement(Statement):
    name: str = ""


@dataclass
class StructDecl(Statement):
    name: str = ""
    packing: Optional[int] = None
    alignment: Optional[int] = None
    fields: list[StructFieldDecl] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.fields


@dataclass
class RecordDecl(Statement):
    name: str = ""
    fields: list[RecordFieldDecl] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.fields


@dataclass
class EnumDecl(Statement):
    name: str = ""
    members: list[EnumMemberDecl] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.members


# -----------------------------------------------------------------------------
# Statements
# -----------------------------------------------------------------------------
@dataclass
class Assignment(Statement):
    target: Optional[Expression] = None
    value: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.target is not None:
            yield self.target
        if self.value is not None:
            yield self.value


@dataclass
class ExpressionStatement(Statement):
    expression: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression


@dataclass
class IfStatement(Statement):
    condition: Optional[Expression] = None
    then_branch: Block = field(default_factory=Block)
    else_branch: Optional[Block] = None

    def children(self) -> Iterable[AstNode]:
        if self.condition is not None:
            yield self.condition
        yield self.then_branch
        if self.else_branch is not None:
            yield self.else_branch


@dataclass
class SelectCaseCondition(AstNode):
    pass


@dataclass
class SelectCaseValue(SelectCaseCondition):
    expression: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression


@dataclass
class SelectCaseRange(SelectCaseCondition):
    start: Optional[Expression] = None
    end: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.start is not None:
            yield self.start
        if self.end is not None:
            yield self.end


@dataclass
class SelectCaseComparison(SelectCaseCondition):
    operator: str = ""
    expression: Optional[Expression] = None
    is_negated: bool = False

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression


@dataclass
class SelectCaseLike(SelectCaseCondition):
    pattern: Optional[Expression] = None
    is_negated: bool = False

    def children(self) -> Iterable[AstNode]:
        if self.pattern is not None:
            yield self.pattern


@dataclass
class SelectCaseArm(AstNode):
    conditions: list[SelectCaseCondition] = field(default_factory=list)
    body: Block = field(default_factory=Block)
    is_else: bool = False

    def children(self) -> Iterable[AstNode]:
        return [*self.conditions, self.body]


@dataclass
class SelectStatement(Statement):
    expression: Optional[Expression] = None
    cases: list[SelectCaseArm] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression
        for case in self.cases:
            yield case


@dataclass
class WhileStatement(Statement):
    condition: Optional[Expression] = None
    body: Block = field(default_factory=Block)

    def children(self) -> Iterable[AstNode]:
        if self.condition is not None:
            yield self.condition
        yield self.body


@dataclass
class ForStatement(Statement):
    variable: Optional[Expression] = None
    start: Optional[Expression] = None
    stop: Optional[Expression] = None
    step: Optional[Expression] = None
    body: Block = field(default_factory=Block)

    def children(self) -> Iterable[AstNode]:
        if self.variable is not None:
            yield self.variable
        if self.start is not None:
            yield self.start
        if self.stop is not None:
            yield self.stop
        if self.step is not None:
            yield self.step
        yield self.body


@dataclass
class LoopStatement(Statement):
    condition: Optional[Expression] = None
    body: Block = field(default_factory=Block)
    is_until: bool = False

    def children(self) -> Iterable[AstNode]:
        if self.condition is not None:
            yield self.condition
        yield self.body


@dataclass
class ReturnStatement(Statement):
    value: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.value is not None:
            yield self.value


@dataclass
class ScriptQuitStatement(Statement):
    value: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.value is not None:
            yield self.value


@dataclass
class ExitStatement(Statement):
    target: Optional[str] = None


@dataclass
class ContinueStatement(Statement):
    target: Optional[str] = None


@dataclass
class GotoStatement(Statement):
    label: str = ""


@dataclass
class GosubStatement(Statement):
    label: str = ""


# -----------------------------------------------------------------------------
# Expressions
# -----------------------------------------------------------------------------
@dataclass
class Identifier(Expression):
    name: str = ""


@dataclass
class IntegerLiteral(Expression):
    value: int = 0


@dataclass
class FloatLiteral(Expression):
    value: float = 0.0


@dataclass
class StringLiteral(Expression):
    value: str = ""
    is_raw: bool = False


@dataclass
class InterpolatedStringPart(AstNode):
    pass


@dataclass
class InterpolatedTextPart(InterpolatedStringPart):
    value: str = ""


@dataclass
class InterpolationPart(InterpolatedStringPart):
    expression: Optional[Expression] = None
    format_spec: Optional[str] = None

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression


@dataclass
class InterpolatedStringLiteral(Expression):
    parts: list[InterpolatedStringPart] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.parts


@dataclass
class BooleanLiteral(Expression):
    value: bool = False


@dataclass
class NullLiteral(Expression):
    pass


@dataclass
class HostIdentifier(Expression):
    name: str = ""


@dataclass
class ArrayLiteral(Expression):
    items: list[Expression] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        return self.items


@dataclass
class UnaryExpr(Expression):
    operator: str = ""
    operand: Optional[Expression] = None
    is_postfix: bool = False

    def children(self) -> Iterable[AstNode]:
        if self.operand is not None:
            yield self.operand


@dataclass
class BinaryExpr(Expression):
    left: Optional[Expression] = None
    operator: str = ""
    right: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.left is not None:
            yield self.left
        if self.right is not None:
            yield self.right


@dataclass
class TernaryExpr(Expression):
    condition: Optional[Expression] = None
    true_expression: Optional[Expression] = None
    false_expression: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.condition is not None:
            yield self.condition
        if self.true_expression is not None:
            yield self.true_expression
        if self.false_expression is not None:
            yield self.false_expression


@dataclass
class CallExpr(Expression):
    callee: Optional[Expression] = None
    args: list[Expression] = field(default_factory=list)

    def children(self) -> Iterable[AstNode]:
        if self.callee is not None:
            yield self.callee
        for arg in self.args:
            yield arg


@dataclass
class IndexExpr(Expression):
    base: Optional[Expression] = None
    index: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.base is not None:
            yield self.base
        if self.index is not None:
            yield self.index


@dataclass
class ParenExpr(Expression):
    expression: Optional[Expression] = None

    def children(self) -> Iterable[AstNode]:
        if self.expression is not None:
            yield self.expression


# -----------------------------------------------------------------------------
# Compatibility aliases
# -----------------------------------------------------------------------------
# Keep this alias while newer code settles on FunctionDecl as the canonical name.
FunctionDeclaration = FunctionDecl


# -----------------------------------------------------------------------------
# AST helpers
# -----------------------------------------------------------------------------
def walk(root: AstNode | None) -> Iterator[AstNode]:
    """
    Depth-first preorder traversal of the AST.

    This helper is intentionally simple and relies on each node's children()
    implementation. It is used by later analysis passes such as metadata cleanup.
    """
    if root is None:
        return

    stack: list[AstNode] = [root]
    while stack:
        node = stack.pop()
        yield node

        child_nodes = list(node.children())
        stack.extend(reversed(child_nodes))


__all__ = [
    "AstNode",
    "Statement",
    "Expression",
    "Program",
    "Block",
    "Declarator",
    "ParamDecl",
    "StructFieldDecl",
    "VarDecl",
    "ConstDecl",
    "FunctionDecl",
    "ExternalFunctionDecl",
    "StructDecl",
    "EnumDecl",
    "EnumMemberDecl",
    "FunctionDeclaration",
    "LabelStatement",
    "Assignment",
    "ExpressionStatement",
    "IfStatement",
    "SelectCaseCondition",
    "SelectCaseValue",
    "SelectCaseRange",
    "SelectCaseComparison",
    "SelectCaseLike",
    "SelectCaseArm",
    "SelectStatement",
    "WhileStatement",
    "ForStatement",
    "LoopStatement",
    "ReturnStatement",
    "ScriptQuitStatement",
    "ExitStatement",
    "ContinueStatement",
    "GotoStatement",
    "GosubStatement",
    "Identifier",
    "IntegerLiteral",
    "FloatLiteral",
    "StringLiteral",
    "BooleanLiteral",
    "NullLiteral",
    "ArrayLiteral",
    "UnaryExpr",
    "BinaryExpr",
    "TernaryExpr",
    "CallExpr",
    "IndexExpr",
    "ParenExpr",
    "walk",
]
