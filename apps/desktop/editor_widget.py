from __future__ import annotations

from dataclasses import dataclass, field
import re

from PySide6.QtCore import QMimeData, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPalette,
    QKeyEvent,
    QKeySequence,
    QSyntaxHighlighter,
    QPixmap,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from apps.desktop.theme import DesktopPreferences
from apps.shared_assets import shared_asset_path
from core.scripting.tokens import KEYWORDS, TokenType

BLOCK_COMMENT_START = "#comments-start"
BLOCK_COMMENT_END = "#comments-end"
CPP_BLOCK_COMMENT_START = "/*"
CPP_BLOCK_COMMENT_END = "*/"
_BREAKPOINT_ICON_PATH = shared_asset_path("icons/msc_debug-breakpoint.png")


def _make_text_format(color: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    return fmt


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.lineNumberAreaPaintEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._editor.isReadOnly():
            event.ignore()
            return
        line_number = self._editor.lineAtY(int(event.position().y()))
        if line_number is not None:
            self._editor.toggleDebugBreakpoint(line_number)
        event.accept()


@dataclass(frozen=True, slots=True)
class BreakpointPaintStyle:
    text_color: QColor = field(default_factory=lambda: QColor("#d9d9d9"))
    background_color: QColor = field(default_factory=lambda: QColor("#1f2329"))
    breakpoint_color: QColor = field(default_factory=lambda: QColor("#d14d4d"))
    current_line_color: QColor = field(default_factory=lambda: QColor("#2c3440"))


class ScriptSyntaxHighlighter(QSyntaxHighlighter):
    BLOCK_COMMENT_STATE = 1
    C_STYLE_BLOCK_COMMENT_STATE = 2

    def __init__(self, document) -> None:
        super().__init__(document)
        self._keyword_format = _make_text_format("#005cc5")
        self._string_format = _make_text_format("#0b7a75")
        self._comment_format = _make_text_format("#6a737d")
        self._number_format = _make_text_format("#b31d28")

    def apply_preferences(self, preferences: DesktopPreferences) -> None:
        syntax = preferences.appearance.syntax_highlighting
        self._keyword_format = _make_text_format(syntax.keyword)
        self._string_format = _make_text_format(syntax.string)
        self._comment_format = _make_text_format(syntax.comment)
        self._number_format = _make_text_format(syntax.number)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        index = 0
        if self.previousBlockState() == self.BLOCK_COMMENT_STATE:
            end = self._find_block_comment_end(text, 0)
            if end is None:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(self.BLOCK_COMMENT_STATE)
                return
            self.setFormat(0, end, self._comment_format)
            index = end
        elif self.previousBlockState() == self.C_STYLE_BLOCK_COMMENT_STATE:
            end = self._find_c_style_block_comment_end(text, 0)
            if end is None:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(self.C_STYLE_BLOCK_COMMENT_STATE)
                return
            self.setFormat(0, end, self._comment_format)
            index = end

        self.setCurrentBlockState(0)
        while index < len(text):
            if text[index : index + len(BLOCK_COMMENT_START)].lower() == BLOCK_COMMENT_START:
                end = self._find_block_comment_end(text, index + len(BLOCK_COMMENT_START))
                if end is None:
                    self.setFormat(index, len(text) - index, self._comment_format)
                    self.setCurrentBlockState(self.BLOCK_COMMENT_STATE)
                    return
                self.setFormat(index, end - index, self._comment_format)
                index = end
                continue

            if text[index : index + len(CPP_BLOCK_COMMENT_START)] == CPP_BLOCK_COMMENT_START:
                end = self._find_c_style_block_comment_end(text, index + len(CPP_BLOCK_COMMENT_START))
                if end is None:
                    self.setFormat(index, len(text) - index, self._comment_format)
                    self.setCurrentBlockState(self.C_STYLE_BLOCK_COMMENT_STATE)
                    return
                self.setFormat(index, end - index, self._comment_format)
                index = end
                continue

            ch = text[index]
            if ch in {'"', "'"}:
                index = self._highlight_string(text, index, ch)
                continue

            if ch == "#":
                self.setFormat(index, len(text) - index, self._comment_format)
                return

            if ch == "/" and index + 1 < len(text) and text[index + 1] == "/":
                self.setFormat(index, len(text) - index, self._comment_format)
                return

            number_end = self._match_number(text, index)
            if number_end is not None:
                self.setFormat(index, number_end - index, self._number_format)
                index = number_end
                continue

            identifier_end = self._match_identifier(text, index)
            if identifier_end is not None:
                token_text = text[index:identifier_end]
                token = KEYWORDS.get(token_text.casefold())
                if token is not None and token not in {TokenType.IDENTIFIER, TokenType.HOST_IDENTIFIER}:
                    self.setFormat(index, identifier_end - index, self._keyword_format)
                index = identifier_end
                continue

            index += 1

    def _highlight_string(self, text: str, start: int, quote: str) -> int:
        index = start + 1
        if quote == '"':
            while index < len(text):
                ch = text[index]
                if ch == "\\":
                    index += 2
                    continue
                if ch == '"' and index + 1 < len(text) and text[index + 1] == '"':
                    index += 2
                    continue
                if ch == '"':
                    index += 1
                    self.setFormat(start, index - start, self._string_format)
                    return index
                index += 1
            self.setFormat(start, len(text) - start, self._string_format)
            return len(text)

        while index < len(text):
            ch = text[index]
            if ch == "'":
                index += 1
                self.setFormat(start, index - start, self._string_format)
                return index
            index += 1

        self.setFormat(start, len(text) - start, self._string_format)
        return len(text)

    def _find_block_comment_end(self, text: str, start: int) -> int | None:
        index = text.lower().find(BLOCK_COMMENT_END, start)
        if index < 0:
            return None
        return index + len(BLOCK_COMMENT_END)

    def _find_c_style_block_comment_end(self, text: str, start: int) -> int | None:
        index = text.find(CPP_BLOCK_COMMENT_END, start)
        if index < 0:
            return None
        return index + len(CPP_BLOCK_COMMENT_END)

    def _match_identifier(self, text: str, start: int) -> int | None:
        if start >= len(text):
            return None
        ch = text[start]
        if not (ch == "_" or ch.isalpha()):
            return None
        index = start + 1
        while index < len(text) and (text[index] == "_" or text[index].isalpha() or text[index].isdigit()):
            index += 1
        return index

    def _match_number(self, text: str, start: int) -> int | None:
        if start >= len(text):
            return None
        match = re.match(r"^(?:0[xX][0-9A-Fa-f]+|(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)", text[start:])
        if match is None:
            return None
        return start + len(match.group(0))


class CodeEditor(QPlainTextEdit):
    breakpointLinesChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabChangesFocus(False)
        self._line_number_area = LineNumberArea(self)
        self._breakpoints: set[int] = set()
        self._mutations_locked = False
        self._current_line_highlight_enabled = True
        self._debug_line: int | None = None
        self._style = BreakpointPaintStyle()
        self._preferences = DesktopPreferences()
        self._syntax_highlighter = ScriptSyntaxHighlighter(self.document())
        self._breakpoint_marker_cache: dict[tuple[str, str], QPixmap] = {}

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self._update_line_number_area_width(0)
        self.highlightCurrentLine()
        self.apply_preferences(self._preferences)

    def set_mutations_locked(self, locked: bool) -> None:
        self._mutations_locked = bool(locked)

    def _should_block_mutation_key(self, event: QKeyEvent) -> bool:
        if not self._mutations_locked:
            return False

        if event.matches(QKeySequence.StandardKey.Undo):
            return True
        if event.matches(QKeySequence.StandardKey.Redo):
            return True
        if event.matches(QKeySequence.StandardKey.Cut):
            return True
        if event.matches(QKeySequence.StandardKey.Paste):
            return True
        if event.matches(QKeySequence.StandardKey.Delete):
            return True

        if event.key() in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            return True

        text = event.text()
        if text and not event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return True

        return False

    def lineNumberAreaWidth(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _block_count: int) -> None:
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self._style.background_color)
        breakpoint_marker = self._breakpoint_marker_pixmap()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self._style.text_color)
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

                if (block_number + 1) in self._breakpoints:
                    marker_y = top + max(0, (self.fontMetrics().height() - breakpoint_marker.height()) // 2)
                    painter.drawPixmap(1, marker_y, breakpoint_marker)

            block = block.next()
            top = bottom
            if block.isValid():
                bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _breakpoint_marker_pixmap(self) -> QPixmap:
        cache_key = (self._style.breakpoint_color.name(), str(self.font().pointSizeF()))
        cached = self._breakpoint_marker_cache.get(cache_key)
        if cached is not None:
            return cached

        source = QPixmap(str(_BREAKPOINT_ICON_PATH))
        if source.isNull():
            marker = QPixmap(8, 8)
            marker.fill(Qt.GlobalColor.transparent)
            painter = QPainter(marker)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._style.breakpoint_color)
                painter.drawEllipse(0, 0, 8, 8)
            finally:
                painter.end()
            self._breakpoint_marker_cache[cache_key] = marker
            return marker

        marker_size = QSize(8, 8)
        marker = source.scaled(
            marker_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        tinted = QPixmap(marker.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        try:
            painter.drawPixmap(0, 0, marker)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), self._style.breakpoint_color)
        finally:
            painter.end()
        self._breakpoint_marker_cache[cache_key] = tinted
        return tinted

    def highlightCurrentLine(self) -> None:
        extra_selections = []
        if not self._current_line_highlight_enabled and self._debug_line is None:
            self.setExtraSelections(extra_selections)
            return

        line_number = self._debug_line
        if line_number is None and self._current_line_highlight_enabled:
            line_number = self.currentLineNumber()
        if line_number is not None and 1 <= line_number <= self.blockCount():
            block = self.document().findBlockByNumber(line_number - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setForeground(QColor(self._preferences.appearance.editor.current_line_foreground))
                selection.format.setBackground(self._style.current_line_color)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selection.cursor = QTextCursor(block)
                selection.cursor.clearSelection()
                extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def setDebugCurrentLine(self, line_number: int | None) -> None:
        if isinstance(line_number, int) and line_number >= 1:
            self._debug_line = line_number
        else:
            self._debug_line = None
        self.highlightCurrentLine()

    def setHighlightedLine(self, line_number: int | None) -> None:
        self.setDebugCurrentLine(line_number)

    def highlightedLine(self) -> int | None:
        return self._debug_line

    def clearHighlightedLine(self) -> None:
        self._debug_line = None
        self.highlightCurrentLine()

    def setCurrentLineHighlightEnabled(self, enabled: bool) -> None:
        self._current_line_highlight_enabled = enabled
        self.highlightCurrentLine()

    def apply_preferences(self, preferences: DesktopPreferences) -> None:
        self._preferences = preferences
        editor = preferences.appearance.editor
        self._style = BreakpointPaintStyle(
            text_color=QColor(editor.gutter_text),
            background_color=QColor(editor.gutter_background),
            breakpoint_color=QColor("#d14d4d"),
            current_line_color=QColor(editor.current_line_highlight),
        )
        self._syntax_highlighter.apply_preferences(preferences)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(editor.background))
        palette.setColor(QPalette.ColorRole.Text, QColor(editor.text))
        palette.setColor(QPalette.ColorRole.Window, QColor(editor.background))
        self.setPalette(palette)
        self.setFont(preferences.font.to_qfont())
        self._apply_indentation_preferences()
        self._apply_line_spacing_multiplier(preferences.font.line_spacing_multiplier)
        self._line_number_area.update()
        self.highlightCurrentLine()
        self.viewport().update()

    def _apply_indentation_preferences(self) -> None:
        indent_width = max(1, int(self._preferences.scripting.indent_width))
        space_width = max(1, self.fontMetrics().horizontalAdvance(" "))
        self.setTabStopDistance(float(space_width * indent_width))

    def _indent_unit(self) -> str:
        scripting = self._preferences.scripting
        return " " * max(1, int(scripting.indent_width)) if scripting.use_spaces else "\t"

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._should_block_mutation_key(event):
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            if self._preferences.scripting.auto_indent:
                cursor = self.textCursor()
                if cursor.hasSelection():
                    self._wrap_selected_block_with_newlines(cursor)
                else:
                    self._insert_auto_indented_newline()
                return
        if event.key() == Qt.Key.Key_Tab and event.modifiers() in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selected_lines(cursor)
            else:
                cursor.insertText(self._indent_unit())
                self.setTextCursor(cursor)
            return
        if event.key() == Qt.Key.Key_Backtab or (
            event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._dedent_selected_lines(cursor)
            else:
                self._unindent_current_line()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        if self._mutations_locked:
            return
        super().insertFromMimeData(source)

    def undo(self) -> None:
        if self._mutations_locked:
            return
        super().undo()

    def redo(self) -> None:
        if self._mutations_locked:
            return
        super().redo()

    def cut(self) -> None:
        if self._mutations_locked:
            return
        super().cut()

    def paste(self) -> None:
        if self._mutations_locked:
            return
        super().paste()

    def _insert_auto_indented_newline(self) -> None:
        cursor = self.textCursor()
        indent = self._current_line_indent(cursor)
        cursor.insertText(f"\n{indent}")
        self.setTextCursor(cursor)

    def _wrap_selected_block_with_newlines(self, cursor: QTextCursor) -> None:
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        if selection_start == selection_end:
            return

        start_block = self.document().findBlock(selection_start)
        start_indent = self._leading_whitespace(start_block.text())
        content_start = start_block.position() + len(start_indent)
        wrap_start = max(selection_start, content_start)
        caret_position = wrap_start if selection_start < content_start else wrap_start + len(start_indent) + 1

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        try:
            edit_cursor.setPosition(selection_end)
            edit_cursor.insertText("\n")
            edit_cursor.setPosition(wrap_start)
            edit_cursor.insertText(f"\n{start_indent}")
        finally:
            edit_cursor.endEditBlock()

        cursor.setPosition(caret_position)
        self.setTextCursor(cursor)

    def _current_line_indent(self, cursor: QTextCursor) -> str:
        position = cursor.position()
        return self._leading_whitespace(self.document().findBlock(position).text())

    def _leading_whitespace(self, text: str) -> str:
        index = 0
        while index < len(text) and text[index] in (" ", "\t"):
            index += 1
        return text[:index]

    def _selected_line_blocks(self, cursor: QTextCursor) -> list:
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if start == end:
            return []

        document = self.document()
        first_block = document.findBlock(start)
        last_block = document.findBlock(max(start, end - 1))

        blocks = []
        block = first_block
        while block.isValid():
            blocks.append(block)
            if block.blockNumber() == last_block.blockNumber():
                break
            block = block.next()

        return blocks

    def _indent_selected_lines(self, cursor: QTextCursor) -> None:
        blocks = self._selected_line_blocks(cursor)
        if not blocks:
            return

        indent_unit = self._indent_unit()
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        line_count = len(blocks)

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        try:
            for block in reversed(blocks):
                edit_cursor.setPosition(block.position())
                edit_cursor.insertText(indent_unit)
        finally:
            edit_cursor.endEditBlock()

        cursor.setPosition(selection_start + len(indent_unit))
        cursor.setPosition(selection_end + (len(indent_unit) * line_count), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def _dedent_selected_lines(self, cursor: QTextCursor) -> None:
        blocks = self._selected_line_blocks(cursor)
        if not blocks:
            return

        indent_unit = self._indent_unit()
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        removed_from_first_line = 0
        removed_total = 0
        first_block_number = blocks[0].blockNumber()

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        try:
            for block in reversed(blocks):
                removed = self._leading_indent_removal_count(block.text(), indent_unit)
                if removed:
                    edit_cursor.setPosition(block.position())
                    edit_cursor.movePosition(
                        QTextCursor.MoveOperation.Right,
                        QTextCursor.MoveMode.KeepAnchor,
                        removed,
                    )
                    edit_cursor.removeSelectedText()
                if block.blockNumber() == first_block_number:
                    removed_from_first_line = removed
                removed_total += removed
        finally:
            edit_cursor.endEditBlock()

        selection_start = max(blocks[0].position(), selection_start - removed_from_first_line)
        selection_end = max(selection_start, selection_end - removed_total)
        cursor.setPosition(selection_start)
        cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def _leading_indent_removal_count(self, block_text: str, indent_unit: str) -> int:
        if not block_text:
            return 0
        if indent_unit == "\t":
            return 1 if block_text.startswith("\t") else 0
        if block_text.startswith(indent_unit):
            return len(indent_unit)
        leading_spaces = len(block_text) - len(block_text.lstrip(" "))
        return min(leading_spaces, len(indent_unit))

    def _unindent_current_line(self) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_text = cursor.block().text()
            indent_unit = self._indent_unit()

            if block_text.startswith(indent_unit):
                if indent_unit == "\t":
                    cursor.deleteChar()
                else:
                    self._delete_characters(cursor, len(indent_unit))
                self.setTextCursor(cursor)
                return

            if indent_unit == "\t":
                return

            leading_spaces = len(block_text) - len(block_text.lstrip(" "))
            if leading_spaces:
                self._delete_characters(cursor, min(leading_spaces, len(indent_unit)))
                self.setTextCursor(cursor)
        finally:
            cursor.endEditBlock()

    def _delete_characters(self, cursor: QTextCursor, count: int) -> None:
        for _ in range(max(0, count)):
            cursor.deleteChar()

    def _apply_line_spacing_multiplier(self, multiplier: float) -> None:
        multiplier = max(0.5, float(multiplier))
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        try:
            cursor.select(QTextCursor.Document)
            block_format = QTextBlockFormat()
            block_format.setLineHeight(multiplier * 100.0, QTextBlockFormat.ProportionalHeight.value)
            cursor.mergeBlockFormat(block_format)
        finally:
            cursor.endEditBlock()

    def lineAtY(self, y: int) -> int | None:
        block = self.firstVisibleBlock()
        block_number = block.blockNumber() + 1
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid():
            if block.isVisible() and top <= y < bottom:
                return block_number
            block = block.next()
            block_number += 1
            top = bottom
            if block.isValid():
                bottom = top + int(self.blockBoundingRect(block).height())
        return None

    def currentLineNumber(self) -> int:
        return self.textCursor().blockNumber() + 1

    def toggleDebugBreakpoint(self, line_number: int) -> None:
        if line_number < 1 or line_number > self.blockCount():
            return

        if line_number in self._breakpoints:
            self._breakpoints.remove(line_number)
        else:
            self._breakpoints.add(line_number)

        self._line_number_area.update()
        self.breakpointLinesChanged.emit()

    def setDebugBreakpoints(self, lines: set[int]) -> None:
        self._breakpoints = {line for line in lines if line >= 1}
        self._line_number_area.update()
        self.breakpointLinesChanged.emit()

    def clearDebugBreakpoints(self) -> None:
        if not self._breakpoints:
            return
        self._breakpoints.clear()
        self._line_number_area.update()
        self.breakpointLinesChanged.emit()

    def debugBreakpointLines(self) -> set[int]:
        return set(self._breakpoints)
