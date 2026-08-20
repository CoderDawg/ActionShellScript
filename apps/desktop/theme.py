from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QFont, QColor


@dataclass(slots=True)
class DirtyIndicatorTheme:
    text: str = "#7a4a00"
    accent: str = "#8b6a2f"
    background: str = "#fff5e3"
    selected_background: str = "#f0ddb4"
    border: str = "#ead8b6"


@dataclass(slots=True)
class WorkspaceTabAttentionTheme:
    enabled: bool = True
    accent: str = "#2b7de9"


@dataclass(slots=True)
class EditorAppearanceTheme:
    background: str = "#ffffff"
    text: str = "#000000"
    gutter_background: str = "#f2f2f2"
    gutter_text: str = "#202020"
    current_line_foreground: str = "#000000"
    current_line_highlight: str = "#fff4c2"


@dataclass(slots=True)
class SyntaxHighlightTheme:
    keyword: str = "#005cc5"
    string: str = "#0b7a75"
    comment: str = "#6a737d"
    number: str = "#b31d28"


@dataclass(slots=True)
class SearchResultsTheme:
    header_active: str = "#d7e9ff"
    header_hovered: str = "#e0efff"
    header_active_hovered: str = "#b9d9ff"
    header_radius: str = "4px"
    header_padding: str = "1px 4px"
    header_text: str = "#666666"
    line_text: str = "#222222"
    hit_text: str = "#666666"
    child_border_color: str = "#8fb6e8"
    child_border_width: str = "2px"
    child_padding_left: int = 8
    child_margin_left: int = 4


@dataclass(slots=True)
class AppearanceTheme:
    editor: EditorAppearanceTheme = field(default_factory=EditorAppearanceTheme)
    syntax_highlighting: SyntaxHighlightTheme = field(default_factory=SyntaxHighlightTheme)
    dirty_indicators: DirtyIndicatorTheme = field(default_factory=DirtyIndicatorTheme)
    workspace_tab_attention: WorkspaceTabAttentionTheme = field(
        default_factory=WorkspaceTabAttentionTheme
    )


@dataclass(slots=True)
class FontSettings:
    family: str = "Consolas"
    size: int = 11
    weight: int = 400
    line_spacing_multiplier: float = 1.0

    def to_qfont(self) -> QFont:
        point_size = max(1, int(self.size))
        font = QFont()
        if self.family:
            font.setFamily(self.family)
        font.setPointSize(point_size)
        font.setWeight(QFont.Weight(self.weight))
        return font


@dataclass(slots=True)
class ScriptingSettings:
    language: str = "ActionShellScript"
    indent_width: int = 4
    use_spaces: bool = True
    auto_indent: bool = True
    auto_format_on_save: bool = False


@dataclass(slots=True)
class DesktopPreferences:
    appearance: AppearanceTheme = field(default_factory=AppearanceTheme)
    scripting: ScriptingSettings = field(default_factory=ScriptingSettings)
    font: FontSettings = field(default_factory=FontSettings)
    search_results: SearchResultsTheme = field(default_factory=SearchResultsTheme)


def _color_from_hex(value: str) -> QColor | None:
    color = QColor(str(value).strip())
    if not color.isValid():
        return None
    return color


def _contrast_luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        normalized = value / 255.0
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
    lighter = max(_contrast_luminance(foreground), _contrast_luminance(background))
    darker = min(_contrast_luminance(foreground), _contrast_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _readability_issue(label: str, foreground: str, background: str, *, minimum_ratio: float) -> str | None:
    fg = _color_from_hex(foreground)
    bg = _color_from_hex(background)
    if fg is None:
        return f"{label} uses an invalid foreground color: {foreground!r}."
    if bg is None:
        return f"{label} uses an invalid background color: {background!r}."
    ratio = _contrast_ratio(fg, bg)
    if ratio >= minimum_ratio:
        return None
    return (
        f"{label} contrast is only {ratio:.2f}:1 against {background}; "
        f"raise it to at least {minimum_ratio:.1f}:1 for readability."
    )


def validate_desktop_preferences_readability(
    preferences: DesktopPreferences,
) -> list[str]:
    issues: list[str] = []
    editor = preferences.appearance.editor
    syntax = preferences.appearance.syntax_highlighting
    dirty = preferences.appearance.dirty_indicators
    attention = preferences.appearance.workspace_tab_attention
    search_results = preferences.search_results

    checks = [
        ("Editor text", editor.text, editor.background, 4.5),
        ("Editor gutter text", editor.gutter_text, editor.gutter_background, 4.5),
        (
            "Editor current-line text",
            editor.current_line_foreground,
            editor.current_line_highlight,
            4.5,
        ),
        ("Keyword color", syntax.keyword, editor.background, 4.5),
        ("String color", syntax.string, editor.background, 4.5),
        ("Comment color", syntax.comment, editor.background, 4.5),
        ("Number color", syntax.number, editor.background, 4.5),
        ("Dirty indicator text", dirty.text, dirty.background, 4.5),
        ("Dirty indicator accent", dirty.accent, dirty.background, 3.0),
        (
            "Search-results header text",
            search_results.header_text,
            search_results.header_active,
            3.0,
        ),
        (
            "Search-results hover header text",
            search_results.header_text,
            search_results.header_hovered,
            3.0,
        ),
        (
            "Search-results active hover header text",
            search_results.header_text,
            search_results.header_active_hovered,
            3.0,
        ),
    ]
    if attention.enabled:
        checks.append(
            (
                "Workspace tab attention accent",
                attention.accent,
                "#ffffff",
                3.0,
            )
        )
    for label, foreground, background, minimum_ratio in checks:
        issue = _readability_issue(label, foreground, background, minimum_ratio=minimum_ratio)
        if issue is not None:
            issues.append(issue)
    return issues
