"""
Lexical analysis for the scripting frontend.

Responsibilities
----------------
- Convert source text into the canonical Token / TokenType stream from tokens.py.
- Report lexical diagnostics through diagnostics.py.
- Preserve the frontend token contract used by parsing and document services.

Notes
-----
- This lexer intentionally uses the canonical token vocabulary only.
- Variables like $name lex as IDENTIFIER with the leading '$' preserved in Token.value.
- Numeric literals all lex as TokenType.NUMBER.
- Boolean keywords True/False lex as TokenType.BOOLEAN for easier parser handling.
- Line separators supported:
    * newline characters
    * `;` end-of-line markers
- Comments supported:
    * // line comment
    * # line comment
    * /* ... */ block comment
    * #comments-start ... #comments-end block comment
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .tokens import (
    KEYWORDS,
    MULTI_CHAR_TOKENS,
    SINGLE_CHAR_TOKENS,
    Token,
    TokenType,
)

from .diagnostics import (
    DiagnosticBag,
    make_invalid_number,
    make_unexpected_character,
    make_unterminated_string,
)

@dataclass(frozen=True, slots=True)
class SourcePosition:
    """Absolute index plus cached 1-based line/column for lexer bookkeeping."""

    index: int
    line: int
    column: int

class Lexer:
    def __init__(
        self,
        source: str,
        diagnostics: Optional[DiagnosticBag] = None,
        source_name: str = "<memory>",
    ) -> None:
        self.source = source or ""
        self.length = len(self.source)
        self.index = 0
        self.line = 1
        self.column = 1
        self.diagnostics = diagnostics if diagnostics is not None else DiagnosticBag()
        self.source_name = source_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def lex(self) -> list[Token]:
        tokens: list[Token] = []

        while not self._at_end():
            self._skip_horizontal_whitespace()
            if self._at_end():
                break

            ch = self._peek()
            start = self._pos()

            if ch in "\r\n":
                tokens.append(self._lex_newline())
                continue

            if ch == ";":
                tokens.append(self._lex_statement_separator())
                continue

            if self._starts_line_comment() or self._starts_block_comment() or self._starts_c_style_block_comment():
                self._skip_comment()
                continue

            if ch == '"':
                tokens.append(self._lex_string())
                continue

            if ch == "'":
                tokens.append(self._lex_raw_string())
                continue

            if ch == "$":
                token = self._lex_dollar_construct()
                if token is not None:
                    tokens.append(token)
                continue

            if ch == "@":
                token = self._lex_host_identifier()
                if token is not None:
                    tokens.append(token)
                continue

            if self._is_identifier_start(ch):
                tokens.append(self._lex_identifier_or_keyword())
                continue

            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                tokens.append(self._lex_number())
                continue

            multi = self._match_multi_char_operator()
            if multi is not None:
                end = self._pos()
                tokens.append(self.make_token(multi[0], multi[1], start, end))
                continue

            single_type = SINGLE_CHAR_TOKENS.get(ch)
            if single_type is not None:
                self._advance()
                end = self._pos()
                tokens.append(self.make_token(single_type, ch, start, end))
                continue

            self.diagnostics.add(
                make_unexpected_character(ch, start.index, source_name=self.source_name)
            )
            self._advance()

        pos = self._pos()
        tokens.append(self.make_token(TokenType.EOF, "", pos, pos))
        return tokens

    # ------------------------------------------------------------------
    # Token construction / navigation
    # ------------------------------------------------------------------
    def make_token(
        self,
        token_type: TokenType,
        value: str,
        start: SourcePosition,
        end: SourcePosition,
    ) -> Token:
        return Token(
            type=token_type,
            value=value,
            line=start.line,
            column=start.column,
            end_line=end.line,
            end_column=end.column,
            start_index=start.index,
            end_index=end.index,
        )

    def _pos(self) -> SourcePosition:
        return SourcePosition(index=self.index, line=self.line, column=self.column)

    def _at_end(self) -> bool:
        return self.index >= self.length

    def _peek(self, offset: int = 0) -> str:
        idx = self.index + offset
        if idx < 0 or idx >= self.length:
            return "\0"
        return self.source[idx]

    def _advance(self) -> str:
        if self._at_end():
            return "\0"

        ch = self.source[self.index]
        self.index += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._peek() != expected:
            return False
        self._advance()
        return True

    # ------------------------------------------------------------------
    # Skipping helpers
    # ------------------------------------------------------------------
    def _skip_horizontal_whitespace(self) -> None:
        while not self._at_end() and self._peek() in {" ", "\t", "\f", "\v"}:
            self._advance()

    def _starts_line_comment(self) -> bool:
        ch = self._peek()
        if ch == "#":
            return not self._starts_block_comment()
        return ch == "/" and self._peek(1) == "/"

    def _starts_block_comment(self) -> bool:
        return self.source[self.index : self.index + 15].lower() == "#comments-start"

    def _starts_c_style_block_comment(self) -> bool:
        return self._peek() == "/" and self._peek(1) == "*"

    def _skip_comment(self) -> None:
        if self._starts_line_comment():
            while not self._at_end() and self._peek() not in {"\r", "\n"}:
                self._advance()
            return

        if self._starts_block_comment():
            terminator = "#comments-end"
            for _ in range(len("#comments-start")):
                self._advance()

            while not self._at_end():
                if self.source[self.index : self.index + len(terminator)].lower() == terminator:
                    for _ in range(len(terminator)):
                        self._advance()
                    return
                self._advance()
            return

        if self._starts_c_style_block_comment():
            terminator = "*/"
            self._advance()
            self._advance()

            while not self._at_end():
                if self._peek() == "*" and self._peek(1) == "/":
                    self._advance()
                    self._advance()
                    return
                self._advance()
            return

    # ------------------------------------------------------------------
    # Lexers
    # ------------------------------------------------------------------
    def _lex_statement_separator(self) -> Token:
        start = self._pos()
        self._advance()
        end = self._pos()
        return self.make_token(TokenType.NEWLINE, ";", start, end)

    def _lex_newline(self) -> Token:
        start = self._pos()
        if self._peek() == "\r":
            self._advance()
            if self._peek() == "\n":
                self._advance()

            end = self._pos()
            return self.make_token(TokenType.NEWLINE, "\n", start, end)

        self._advance()  # \n
        end = self._pos()
        return self.make_token(TokenType.NEWLINE, "\n", start, end)

    def _lex_dollar_construct(self) -> Optional[Token]:
        start = self._pos()
        self._advance()  # consume '$'

        if self._peek() == '"':
            return self._lex_interpolated_string(start)

        if not self._is_identifier_start(self._peek()):
            self.diagnostics.add(
                make_unexpected_character("$", start.index, source_name=self.source_name)
            )
            return None

        while self._is_identifier_part(self._peek()):
            self._advance()

        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.IDENTIFIER, lexeme, start, end)

    def _lex_host_identifier(self) -> Optional[Token]:
        start = self._pos()
        self._advance()  # consume '@'

        if not self._is_identifier_start(self._peek()):
            self.diagnostics.add(
                make_unexpected_character("@", start.index, source_name=self.source_name)
            )
            return None

        while self._is_identifier_part(self._peek()):
            self._advance()

        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.HOST_IDENTIFIER, lexeme, start, end)

    def _lex_identifier_or_keyword(self) -> Token:
        start = self._pos()
        self._advance()
        while self._is_identifier_part(self._peek()):
            self._advance()

        end = self._pos()
        lexeme = self.source[start.index : end.index]
        lowered = lexeme.lower()

        token_type = KEYWORDS.get(lowered)
        if token_type is None:
            return self.make_token(TokenType.IDENTIFIER, lexeme, start, end)

        if token_type in {TokenType.TRUE, TokenType.FALSE}:
            return self.make_token(TokenType.BOOLEAN, lowered, start, end)

        return self.make_token(token_type, lexeme, start, end)

    def _lex_number(self) -> Token:
        start = self._pos()
        saw_dot = False

        if (
            self._peek() == "0"
            and self._peek(1) in {"x", "X"}
            and self._peek(2).isalnum()
        ):
            self._advance()
            self._advance()
            saw_hex_digit = False
            while True:
                ch = self._peek()
                if ch.isdigit() or ("a" <= ch.lower() <= "f"):
                    saw_hex_digit = True
                    self._advance()
                    continue
                break

            if not saw_hex_digit:
                self.diagnostics.add(
                    make_invalid_number(start.index, self.index, source_name=self.source_name)
                )

            if self._is_identifier_start(self._peek()):
                while self._is_identifier_part(self._peek()):
                    self._advance()
                self.diagnostics.add(
                    make_invalid_number(start.index, self.index, source_name=self.source_name)
                )

            end = self._pos()
            lexeme = self.source[start.index : end.index]
            return self.make_token(TokenType.NUMBER, lexeme, start, end)

        if self._peek() == ".":
            saw_dot = True
            self._advance()
            if not self._peek().isdigit():
                self.diagnostics.add(
                    make_invalid_number(start.index, self.index, source_name=self.source_name)
                )
                end = self._pos()
                return self.make_token(
                    TokenType.NUMBER,
                    self.source[start.index : end.index],
                    start,
                    end,
                )

        while self._peek().isdigit():
            self._advance()

        if self._peek() == "." and self._peek(1).isdigit() and not saw_dot:
            saw_dot = True
            self._advance()
            while self._peek().isdigit():
                self._advance()

        if self._peek() in {"e", "E"}:
            self._advance()
            if self._peek() in {"+", "-"}:
                self._advance()
            if not self._peek().isdigit():
                self.diagnostics.add(
                    make_invalid_number(start.index, self.index, source_name=self.source_name)
                )
            else:
                while self._peek().isdigit():
                    self._advance()

        if self._is_identifier_start(self._peek()):
            while self._is_identifier_part(self._peek()):
                self._advance()
            self.diagnostics.add(
                make_invalid_number(start.index, self.index, source_name=self.source_name)
            )

        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.NUMBER, lexeme, start, end)

    def _lex_string(self) -> Token:
        start = self._pos()
        self._advance()  # opening quote

        while not self._at_end():
            ch = self._peek()
            if ch == '"':
                if self._peek(1) == '"':
                    self._advance()
                    self._advance()
                    continue

                self._advance()
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.STRING, lexeme, start, end)

            if ch == "\\":
                self._advance()
                if not self._at_end():
                    self._advance()
                continue

            if ch in {"\r", "\n"}:
                self.diagnostics.add(
                    make_unterminated_string(start.index, self.index, source_name=self.source_name)
                )
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.STRING, lexeme, start, end)

            self._advance()

        self.diagnostics.add(
            make_unterminated_string(start.index, self.index, source_name=self.source_name)
        )
        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.STRING, lexeme, start, end)

    def _lex_raw_string(self) -> Token:
        start = self._pos()
        self._advance()  # opening quote

        while not self._at_end():
            ch = self._peek()
            if ch == "'":
                self._advance()
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.STRING, lexeme, start, end)

            if ch in {"\r", "\n"}:
                self.diagnostics.add(
                    make_unterminated_string(start.index, self.index, source_name=self.source_name)
                )
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.STRING, lexeme, start, end)

            self._advance()

        self.diagnostics.add(
            make_unterminated_string(start.index, self.index, source_name=self.source_name)
        )
        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.STRING, lexeme, start, end)

    def _lex_interpolated_string(self, start: SourcePosition) -> Token:
        self._advance()  # opening quote after $
        brace_depth = 0
        nested_quote: str | None = None

        while not self._at_end():
            ch = self._peek()

            if nested_quote is not None:
                if nested_quote == '"' and ch == "\\":
                    self._advance()
                    if not self._at_end():
                        self._advance()
                    continue
                if nested_quote == '"' and ch == '"' and self._peek(1) == '"':
                    self._advance()
                    self._advance()
                    continue
                self._advance()
                if ch == nested_quote:
                    nested_quote = None
                continue

            if brace_depth > 0 and ch in {'"', "'"}:
                nested_quote = ch
                self._advance()
                continue

            if ch == "{":
                if self._peek(1) == "{":
                    self._advance()
                    self._advance()
                    continue
                brace_depth += 1
                self._advance()
                continue

            if ch == "}" and brace_depth > 0:
                if self._peek(1) == "}":
                    self._advance()
                    self._advance()
                    continue
                brace_depth -= 1
                self._advance()
                continue

            if ch == '"':
                if self._peek(1) == '"':
                    self._advance()
                    self._advance()
                    continue

                self._advance()
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.INTERP_STRING, lexeme, start, end)

            if ch == "\\":
                self._advance()
                if not self._at_end():
                    self._advance()
                continue

            if ch in {"\r", "\n"}:
                self.diagnostics.add(
                    make_unterminated_string(start.index, self.index, source_name=self.source_name)
                )
                end = self._pos()
                lexeme = self.source[start.index : end.index]
                return self.make_token(TokenType.INTERP_STRING, lexeme, start, end)

            self._advance()

        self.diagnostics.add(
            make_unterminated_string(start.index, self.index, source_name=self.source_name)
        )
        end = self._pos()
        lexeme = self.source[start.index : end.index]
        return self.make_token(TokenType.INTERP_STRING, lexeme, start, end)

    def _match_multi_char_operator(self) -> Optional[tuple[TokenType, str]]:
        for text in sorted(MULTI_CHAR_TOKENS.keys(), key=len, reverse=True):
            if self.source.startswith(text, self.index):
                for _ in range(len(text)):
                    self._advance()
                return MULTI_CHAR_TOKENS[text], text
        return None

    # ------------------------------------------------------------------
    # Character classification
    # ------------------------------------------------------------------
    @staticmethod
    def _is_identifier_start(ch: str) -> bool:
        return ch == "_" or ch.isalpha()

    @staticmethod
    def _is_identifier_part(ch: str) -> bool:
        return ch == "_" or ch.isalpha() or ch.isdigit()

# ------------------------------------------------------------------
# Public API for external callers
# ------------------------------------------------------------------
def lex(source: str, diagnostics: Optional[DiagnosticBag] = None, source_name: str = "<memory>") -> list[Token]:
    return Lexer(source, diagnostics=diagnostics, source_name=source_name).lex()
