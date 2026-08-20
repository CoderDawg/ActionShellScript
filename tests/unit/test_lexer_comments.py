from __future__ import annotations

from core.scripting.lexer import lex
from core.scripting.tokens import TokenType


def test_lexer_skips_c_style_block_comments() -> None:
    tokens = lex("Hotkey(\"ctrl\", \"c\") /* comment\nstill comment */ Hotkey(\"alt\", \"v\")\n")

    assert [token.type for token in tokens if token.type != TokenType.EOF] == [
        TokenType.IDENTIFIER,
        TokenType.LPAREN,
        TokenType.STRING,
        TokenType.COMMA,
        TokenType.STRING,
        TokenType.RPAREN,
        TokenType.IDENTIFIER,
        TokenType.LPAREN,
        TokenType.STRING,
        TokenType.COMMA,
        TokenType.STRING,
        TokenType.RPAREN,
        TokenType.NEWLINE,
    ]
