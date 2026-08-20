
"""
Canonical token definitions for the scripting frontend.

This module is the single source of truth for:
- TokenType enum members
- Token dataclass shape
- keyword/operator lookup tables
- parser helper token sets

Frontend contract:
    source text -> lexer -> Token stream -> parser -> AST + diagnostics

Notes
-----
- Keep token names canonical. Do not add compatibility aliases such as
  INTEGER, REAL, VARIABLE, EQUAL, LESS_EQUAL, GREATER_EQUAL, AMP,
  or KW_* names.
- Numeric literals are represented by TokenType.NUMBER.
- Variables like $name still lex as IDENTIFIER unless the language later
  introduces a dedicated VARIABLE token kind on purpose.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final


class TokenType(Enum):
    # Special
    EOF = auto()
    NEWLINE = auto()

    # Identifiers / literals
    IDENTIFIER = auto()
    HOST_IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    INTERP_STRING = auto()
    BOOLEAN = auto()
    NULL = auto()

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    QUESTION = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    INCREMENT = auto()
    DECREMENT = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    AMPERSAND = auto()

    ASSIGN = auto()   # =
    EQ = auto()       # ==
    NE = auto()       # <>
    LT = auto()       # <
    LTE = auto()      # <=
    GT = auto()       # >
    GTE = auto()      # >=

    # Keywords / logical operators / control flow
    AND = auto()
    OR = auto()
    NOT = auto()

    IF = auto()
    THEN = auto()
    ELSE = auto()
    ELSEIF = auto()
    ENDIF = auto()

    WHILE = auto()
    WEND = auto()

    FOR = auto()
    TO = auto()
    STEP = auto()
    NEXT = auto()

    DO = auto()
    UNTIL = auto()

    SELECT = auto()
    CASE = auto()
    ENDSELECT = auto()
    END = auto()

    FUNC = auto()
    ENDFUNC = auto()
    DECLARE = auto()
    RECORD = auto()
    ENDRECORD = auto()
    SUB = auto()
    LIB = auto()
    ALIAS = auto()
    DEFAULT = auto()
    PACKED = auto()
    ALIGN = auto()
    WINAPI = auto()
    STDCALL = auto()
    CDECL = auto()
    STRUCT = auto()
    ENDSTRUCT = auto()
    ENDENUM = auto()
    RETURN = auto()
    EXITSCRIPT = auto()

    LOCAL = auto()
    GLOBAL = auto()
    CONST = auto()
    DIM = auto()
    REDIM = auto()
    AS = auto()

    BYVAL = auto()
    BYREF = auto()
    ENUM = auto()

    EXIT = auto()
    CONTINUE = auto()

    EXITLOOP = auto()
    CONTINUELOOP = auto()
    EXITFOR = auto()
    EXITWHILE = auto()

    GOTO = auto()

    TRUE = auto()
    FALSE = auto()

@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: str

    # 1-based user-facing coordinates
    line: int
    column: int
    end_line: int
    end_column: int

    # 0-based absolute offsets into source text
    start_index: int
    end_index: int

    def __repr__(self) -> str:
        return (
            f"Token(type={self.type.name}, value={self.value!r}, "
            f"line={self.line}, column={self.column}, "
            f"end_line={self.end_line}, end_column={self.end_column}, "
            f"start_index={self.start_index}, end_index={self.end_index})"
        )

    @property
    def length(self) -> int:
        return self.end_index - self.start_index

KEYWORDS: Final[dict[str, TokenType]] = {
    # logical / literals
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,

    # control flow
    "if": TokenType.IF,
    "then": TokenType.THEN,
    "else": TokenType.ELSE,
    "elseif": TokenType.ELSEIF,
    "endif": TokenType.ENDIF,
    "while": TokenType.WHILE,
    "wend": TokenType.WEND,
    "for": TokenType.FOR,
    "to": TokenType.TO,
    "step": TokenType.STEP,
    "next": TokenType.NEXT,
    "do": TokenType.DO,
    "until": TokenType.UNTIL,
    "select": TokenType.SELECT,
    "case": TokenType.CASE,
    "endselect": TokenType.ENDSELECT,
    "end": TokenType.END,
    "func": TokenType.FUNC,
    "function": TokenType.FUNC,
    "endenum": TokenType.ENDENUM,
    "record": TokenType.RECORD,
    "endrecord": TokenType.ENDRECORD,
    "sub": TokenType.SUB,
    "endfunc": TokenType.ENDFUNC,
    "endfunction": TokenType.ENDFUNC,
    "declare": TokenType.DECLARE,
    "lib": TokenType.LIB,
    "alias": TokenType.ALIAS,
    "default": TokenType.DEFAULT,
    "packed": TokenType.PACKED,
    "align": TokenType.ALIGN,
    "winapi": TokenType.WINAPI,
    "stdcall": TokenType.STDCALL,
    "cdecl": TokenType.CDECL,
    "struct": TokenType.STRUCT,
    "endstruct": TokenType.ENDSTRUCT,
    "return": TokenType.RETURN,
    "exitscript": TokenType.EXITSCRIPT,
    "scriptquit": TokenType.EXITSCRIPT,

    # declarations
    "local": TokenType.LOCAL,
    "global": TokenType.GLOBAL,
    "const": TokenType.CONST,
    "dim": TokenType.DIM,
    "redim": TokenType.REDIM,
    "as": TokenType.AS,
    "byval": TokenType.BYVAL,
    "byref": TokenType.BYREF,
    "enum": TokenType.ENUM,

    # flow modifiers
    "exit": TokenType.EXIT,
    "continue": TokenType.CONTINUE,
    "exitloop": TokenType.EXITLOOP,
    "continueloop": TokenType.CONTINUELOOP,
    "exitfor": TokenType.EXITFOR,
    "exitwhile": TokenType.EXITWHILE,
    "goto": TokenType.GOTO,
}


# Tokens emitted directly by the lexer for one-character operators/punctuation.
SINGLE_CHAR_TOKENS: Final[dict[str, TokenType]] = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
    ".": TokenType.DOT,
    "?": TokenType.QUESTION,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "&": TokenType.AMPERSAND,
    "=": TokenType.ASSIGN,
    "<": TokenType.LT,
    ">": TokenType.GT,
}


# Tokens emitted directly by the lexer for multi-character operators.
MULTI_CHAR_TOKENS: Final[dict[str, TokenType]] = {
    "++": TokenType.INCREMENT,
    "--": TokenType.DECREMENT,
    "==": TokenType.EQ,
    "!=": TokenType.NE,
    "<>": TokenType.NE,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
}


STATEMENT_START_KEYWORDS: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.IF,
        TokenType.WHILE,
        TokenType.FOR,
        TokenType.DO,
        TokenType.SELECT,
        TokenType.FUNC,
        TokenType.DECLARE,
        TokenType.RETURN,
        TokenType.EXITSCRIPT,
        TokenType.LOCAL,
        TokenType.GLOBAL,
        TokenType.CONST,
        TokenType.DIM,
        TokenType.REDIM,
        TokenType.STRUCT,
        TokenType.EXIT,
        TokenType.CONTINUE,
        TokenType.EXITLOOP,
        TokenType.CONTINUELOOP,
        TokenType.EXITFOR,
        TokenType.EXITWHILE,
        TokenType.GOTO,
        TokenType.ENUM,
    }
)


BLOCK_START_TOKENS: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.IF,
        TokenType.WHILE,
        TokenType.FOR,
        TokenType.DO,
        TokenType.SELECT,
        TokenType.FUNC,
        TokenType.ENUM,
    }
)


BLOCK_END_TOKENS: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.ENDIF,
        TokenType.WEND,
        TokenType.NEXT,
        TokenType.UNTIL,
        TokenType.ENDSELECT,
        TokenType.ENDFUNC,
        TokenType.ENDSTRUCT,
        TokenType.ENDENUM,
        TokenType.ELSE,
        TokenType.ELSEIF,
        TokenType.CASE,
        TokenType.EOF,
    }
)


ASSIGNMENT_TOKEN_TYPES: Final[frozenset[TokenType]] = frozenset({TokenType.ASSIGN})

COMPARISON_TOKEN_TYPES: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.EQ,
        TokenType.NE,
        TokenType.LT,
        TokenType.LTE,
        TokenType.GT,
        TokenType.GTE,
    }
)

ARITHMETIC_TOKEN_TYPES: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.STAR,
        TokenType.SLASH,
        TokenType.PERCENT,
        TokenType.AMPERSAND,
    }
)

LITERAL_TOKEN_TYPES: Final[frozenset[TokenType]] = frozenset(
    {
        TokenType.NUMBER,
        TokenType.STRING,
        TokenType.INTERP_STRING,
        TokenType.TRUE,
        TokenType.FALSE,
        TokenType.NULL,
        TokenType.BOOLEAN,
    }
)


__all__ = [
    "ARITHMETIC_TOKEN_TYPES",
    "ASSIGNMENT_TOKEN_TYPES",
    "BLOCK_END_TOKENS",
    "BLOCK_START_TOKENS",
    "COMPARISON_TOKEN_TYPES",
    "KEYWORDS",
    "LITERAL_TOKEN_TYPES",
    "MULTI_CHAR_TOKENS",
    "SINGLE_CHAR_TOKENS",
    "STATEMENT_START_KEYWORDS",
    "Token",
    "TokenType",
]
