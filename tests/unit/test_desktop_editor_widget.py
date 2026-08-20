from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QColor, QKeyEvent, QPalette, QPixmap, QTextBlockFormat, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from apps.desktop.editor_widget import CodeEditor  # noqa: E402
from apps.desktop.theme import (  # noqa: E402
    AppearanceTheme,
    DesktopPreferences,
    EditorAppearanceTheme,
    FontSettings,
    ScriptingSettings,
    SyntaxHighlightTheme,
)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _render_line_number_area(editor: CodeEditor) -> QPixmap:
    app = _app()
    app.processEvents()
    pixmap = QPixmap(editor._line_number_area.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    editor._line_number_area.render(pixmap)
    return pixmap


def test_code_editor_breakpoints_toggle_and_width_changes() -> None:
    _app()

    short_editor = CodeEditor()
    short_editor.setPlainText("one line\n")
    short_width = short_editor.lineNumberAreaWidth()

    long_editor = CodeEditor()
    long_editor.setPlainText("\n".join(f"line {index}" for index in range(1, 125)) + "\n")
    long_width = long_editor.lineNumberAreaWidth()

    long_editor.toggleDebugBreakpoint(12)

    assert long_width > short_width
    assert long_editor.debugBreakpointLines() == {12}
    assert long_editor.currentLineNumber() == 1


def test_code_editor_gutter_keeps_plain_background_without_breakpoints() -> None:
    app = _app()

    editor = CodeEditor()
    editor.setPlainText("one\ntwo\nthree\n")
    editor.resize(240, 120)
    editor.show()
    app.processEvents()

    image = _render_line_number_area(editor).toImage()
    block = editor.document().findBlockByNumber(1)
    sample_y = int(editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top())
    sample_y += max(1, editor.fontMetrics().height() // 2)

    assert image.pixelColor(6, sample_y) == editor._style.background_color


def test_code_editor_gutter_renders_breakpoint_asset_when_breakpoint_is_set() -> None:
    app = _app()

    editor = CodeEditor()
    editor.setPlainText("one\ntwo\nthree\n")
    editor.resize(240, 120)
    editor.show()
    editor.setDebugBreakpoints({2})
    app.processEvents()

    image = _render_line_number_area(editor).toImage()
    block = editor.document().findBlockByNumber(1)
    sample_y = int(editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top())
    sample_y += max(1, editor.fontMetrics().height() // 2)
    sample_color = image.pixelColor(6, sample_y)

    assert sample_color != editor._style.background_color
    assert sample_color.red() > sample_color.green()
    assert sample_color.red() > sample_color.blue()


def test_code_editor_apply_preferences_updates_palette_and_highlight() -> None:
    _app()

    editor = CodeEditor()
    preferences = DesktopPreferences(
        appearance=AppearanceTheme(
            editor=EditorAppearanceTheme(
                background="#101820",
                text="#f5f7fa",
                gutter_background="#22303c",
                gutter_text="#f5f7fa",
                current_line_foreground="#112233",
                current_line_highlight="#ffeeaa",
            ),
        ),
        font=FontSettings(
            family="Courier New",
            size=13,
            weight=600,
            line_spacing_multiplier=1.5,
        ),
    )

    editor.apply_preferences(preferences)

    assert editor.palette().color(QPalette.Base).name() == "#101820"
    assert editor.palette().color(QPalette.Text).name() == "#f5f7fa"
    assert editor.font().pointSize() == 13
    assert editor.font().family() == "Courier New"
    assert editor.font().weight() == 600
    assert editor.extraSelections()[0].format.foreground().color().name() == "#112233"
    assert editor.extraSelections()[0].format.background().color().name() == "#ffeeaa"
    assert editor.document().firstBlock().blockFormat().lineHeightType() == (
        QTextBlockFormat.ProportionalHeight.value
    )
    assert editor.document().firstBlock().blockFormat().lineHeight() == 150.0


def test_code_editor_highlights_script_tokens_using_syntax_preferences() -> None:
    _app()

    editor = CodeEditor()
    preferences = DesktopPreferences(
        appearance=AppearanceTheme(
            syntax_highlighting=SyntaxHighlightTheme(
                keyword="#111111",
                string="#222222",
                comment="#333333",
                number="#444444",
            )
        )
    )

    editor.apply_preferences(preferences)
    editor.setPlainText(
        'if value == 42\n"hello" # note\n/* block\ncomment */\n#comments-start\nblock\n#comments-end\n'
    )

    def format_map(block_text: str, block_number: int) -> dict[str, str]:
        block = editor.document().findBlockByNumber(block_number)
        ranges = {}
        for rng in block.layout().formats():
            token_text = block_text[rng.start : rng.start + rng.length]
            ranges[token_text] = rng.format.foreground().color().name()
        return ranges

    first_block = editor.document().findBlockByNumber(0).text()
    second_block = editor.document().findBlockByNumber(1).text()
    third_block = editor.document().findBlockByNumber(2).text()
    fourth_block = editor.document().findBlockByNumber(3).text()
    fifth_block = editor.document().findBlockByNumber(4).text()
    sixth_block = editor.document().findBlockByNumber(5).text()
    seventh_block = editor.document().findBlockByNumber(6).text()

    assert format_map(first_block, 0)["if"] == "#111111"
    assert format_map(first_block, 0)["42"] == "#444444"
    assert format_map(second_block, 1)['"hello"'] == "#222222"
    assert format_map(second_block, 1)["# note"] == "#333333"
    assert format_map(third_block, 2)["/* block"] == "#333333"
    assert format_map(fourth_block, 3)["comment */"] == "#333333"
    assert format_map(fifth_block, 4)["#comments-start"] == "#333333"
    assert format_map(sixth_block, 5)["block"] == "#333333"
    assert format_map(seventh_block, 6)["#comments-end"] == "#333333"


def test_code_editor_uses_formatting_preferences_for_tab_width_and_tab_insertion() -> None:
    app = _app()

    editor = CodeEditor()
    preferences = DesktopPreferences(
        scripting=ScriptingSettings(
            indent_width=2,
            use_spaces=True,
        )
    )

    editor.apply_preferences(preferences)
    expected_tab_stop = float(editor.fontMetrics().horizontalAdvance(" ") * 2)
    assert editor.tabStopDistance() == expected_tab_stop

    editor.setPlainText("alpha\n")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    tab_event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Tab), Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(editor, tab_event)

    assert editor.toPlainText() == "alpha\n  "

    editor.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=2,
                use_spaces=False,
            )
        )
    )
    editor.setPlainText("beta\n")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    QApplication.sendEvent(editor, tab_event)

    assert editor.toPlainText() == "beta\n\t"


def test_code_editor_indents_and_dedents_multi_line_selections() -> None:
    _app()

    editor = CodeEditor()
    editor.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=2,
                use_spaces=True,
            )
        )
    )
    editor.setPlainText("alpha\nbeta\ngamma\n")

    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(17, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    indent_event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_Tab),
        Qt.KeyboardModifier.NoModifier,
    )
    dedent_event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_Tab),
        Qt.KeyboardModifier.ShiftModifier,
    )

    QApplication.sendEvent(editor, indent_event)
    assert editor.toPlainText() == "alpha\n  beta\n  gamma\n"

    QApplication.sendEvent(editor, dedent_event)
    assert editor.toPlainText() == "alpha\nbeta\ngamma\n"


def test_code_editor_auto_indents_new_lines_when_enabled() -> None:
    _app()

    editor = CodeEditor()
    editor.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=4,
                use_spaces=True,
                auto_indent=True,
            )
        )
    )
    editor.setPlainText("    alpha")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    enter_event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_Return),
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(editor, enter_event)

    assert editor.toPlainText() == "    alpha\n    "


def test_code_editor_can_disable_auto_indent_for_enter() -> None:
    _app()

    editor = CodeEditor()
    editor.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=4,
                use_spaces=True,
                auto_indent=False,
            )
        )
    )
    editor.setPlainText("    alpha")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    enter_event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_Return),
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(editor, enter_event)

    assert editor.toPlainText() == "    alpha\n"


def test_code_editor_enters_wrap_selected_blocks_with_newlines() -> None:
    _app()

    editor = CodeEditor()
    editor.apply_preferences(
        DesktopPreferences(
            scripting=ScriptingSettings(
                indent_width=4,
                use_spaces=True,
                auto_indent=True,
            )
        )
    )
    editor.setPlainText("alpha\n    beta\n    gamma\n")

    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(24, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    enter_event = QKeyEvent(
        QEvent.Type.KeyPress,
        int(Qt.Key.Key_Return),
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(editor, enter_event)

    assert editor.toPlainText() == "alpha\n    \n    beta\n    gamma\n\n"
    assert editor.textCursor().position() == 10
    assert editor.textCursor().block().text() == "    "
