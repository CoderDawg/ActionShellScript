"""
Text-formatting helpers for the ASS macro language.

Phase 5 formatting now has an explicit document-facing contract:

- `FormattingService` formats `ScriptDocument.text` through this module.
- Text formatting performs normalization and indentation cleanup.
- AST-to-script formatting is intentionally deferred until ASS has a
  dedicated formatter for the current parser AST.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FormatOptions:
    indent: str = "    "
    newline: str = "\n"
    max_blank_lines: int = 1
    keyword_case: str = "canonical"
    final_newline: bool = True


class ScriptFormatter:
    def __init__(
        self,
        options: FormatOptions | None = None,
        parser: Callable[[str], Any] | None = None,
    ) -> None:
        self.options = options or FormatOptions()
        self.parser = parser

    def format_script(self, text: str) -> str:
        normalized = self._normalize_basic(text)

        if self.parser is not None:
            self.parser(normalized)

        reindented = self._reindent(normalized)
        return self._ensure_final_newline(reindented)

    def format_ast(self, node: Any) -> str:
        raise NotImplementedError(
            "AST formatting is intentionally deferred until ASS has a "
            "dedicated renderer for the current parser AST."
        )

    def _normalize_basic(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]

        collapsed: list[str] = []
        blank_run = 0

        for line in lines:
            if line.strip() == "":
                blank_run += 1
                if blank_run <= self.options.max_blank_lines:
                    collapsed.append("")
            else:
                blank_run = 0
                collapsed.append(self._normalize_line_spacing(line.strip()))

        return "\n".join(collapsed).strip("\n")

    def _normalize_line_spacing(self, line: str) -> str:
        if not line:
            return line

        lower = line.lower()

        if lower.startswith("func "):
            line = self._normalize_func_header(line)
        elif lower.startswith("record "):
            line = self._normalize_record_header(line)
        elif lower.startswith("dim "):
            line = re.sub(r"\s*=\s*", " = ", line)
            line = re.sub(r",\s*", ", ", line)
        elif " as " in lower:
            line = re.sub(r"\s*=\s*", " = ", line)
            line = re.sub(r",\s*", ", ", line)
        else:
            line = re.sub(r",\s*", ", ", line)

        line = re.sub(r"\s+as\s+", " As ", line, flags=re.IGNORECASE)
        line = re.sub(r"\bString\s*\(\s*(\d+)\s*\)", r"String(\1)", line, flags=re.IGNORECASE)
        line = re.sub(
            r"\b(packed|align)\s*\(\s*(\d+)\s*\)",
            lambda match: f"{match.group(1).capitalize()}({match.group(2)})",
            line,
            flags=re.IGNORECASE,
        )

        return line

    def _normalize_func_header(self, line: str) -> str:
        open_idx = line.find("(")
        close_idx = line.rfind(")")
        if open_idx == -1 or close_idx == -1 or close_idx < open_idx:
            return line

        prefix = line[:open_idx].rstrip()
        inside = line[open_idx + 1 : close_idx]
        suffix = line[close_idx + 1 :].strip()

        params = []
        for raw in inside.split(","):
            piece = raw.strip()
            if piece:
                params.append(piece)

        if params:
            rebuilt = f"{prefix}( " + ", ".join(params) + " )"
        else:
            rebuilt = f"{prefix}()"

        if suffix:
            rebuilt += f" {suffix}"

        return rebuilt

    def _normalize_record_header(self, line: str) -> str:
        parts = line.split(None, 1)
        if len(parts) < 2:
            return "Record"
        return f"{parts[0]} {parts[1].strip()}"

    def _reindent(self, text: str) -> str:
        lines = text.split("\n")
        out: list[str] = []
        level = 0
        select_levels: list[int] = []

        for raw in lines:
            stripped = raw.strip()
            if stripped == "":
                out.append("")
                continue

            lowered = stripped.lower()

            if lowered.startswith(("endif", "endfunc", "end struct", "endstruct", "end record", "endrecord", "next", "wend", "until")):
                level = max(0, level - 1)
            elif lowered.startswith(("endselect", "end select")):
                if select_levels:
                    level = select_levels.pop()
                else:
                    level = max(0, level - 1)
            elif lowered.startswith("case ") or lowered == "case" or lowered.startswith("case else"):
                if select_levels:
                    level = select_levels[-1] + 1
                else:
                    level = max(0, level - 1)
            elif lowered == "else":
                level = max(0, level - 1)

            out.append(f"{self.options.indent * level}{stripped}")

            if lowered.startswith("func "):
                level += 1
            elif lowered.startswith("record "):
                level += 1
            elif lowered.startswith("struct "):
                level += 1
            elif lowered.startswith("if ") and lowered.endswith(" then"):
                level += 1
            elif lowered.startswith("while "):
                level += 1
            elif lowered.startswith("for "):
                level += 1
            elif lowered.startswith("select case"):
                select_levels.append(level)
                level += 1
            elif lowered == "else":
                level += 1
            elif lowered.startswith("case ") or lowered == "case" or lowered.startswith("case else"):
                level += 1

        return "\n".join(out)

    def _ensure_final_newline(self, text: str) -> str:
        if self.options.final_newline and not text.endswith(self.options.newline):
            return text + self.options.newline
        return text


def format_script(text: str, options: FormatOptions | None = None) -> str:
    return ScriptFormatter(options=options).format_script(text)


def format_ast(node: Any, options: FormatOptions | None = None) -> str:
    return ScriptFormatter(options=options).format_ast(node)
