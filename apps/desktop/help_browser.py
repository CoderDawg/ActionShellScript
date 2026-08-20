from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QUrl, Qt, QRectF, QSize, QEvent, QObject, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QColor,
    QIcon,
    QPalette,
    QPainter,
    QPainterPath,
    QPen,
    QTextDocument,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QLineEdit,
    QMainWindow,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QSizePolicy,
)

from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from apps.desktop.icon_assets import DesktopAsset, desktop_asset_path


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs"


def _repo_root() -> Path:
    return _docs_root().parent


@dataclass(frozen=True, slots=True)
class HelpTopic:
    title: str
    path: Path
    section: str
    description: str = ""
    default_anchor_id: str | None = None
    default_anchor_text: str | None = None
    content_text: str = ""
    search_text: str = ""


def _help_topics() -> list[HelpTopic]:
    docs_root = _docs_root()
    repo_root = _repo_root()
    topics = [
        HelpTopic(
            "Home",
            docs_root / "index.md",
            "Start Here",
            "Project overview, launch points, and desktop entrypoints.",
        ),
        HelpTopic(
            "Generate Script Guide",
            docs_root / "user" / "generate_script_guide.md",
            "User Guides",
            default_anchor_id="what-ass-generate-does",
            default_anchor_text="What `ass-generate` Does",
        ),
        HelpTopic(
            "Open Script Guide",
            docs_root / "user" / "open_script_guide.md",
            "User Guides",
            default_anchor_id="what-ass-open-script-does",
            default_anchor_text="What `ass-open-script` Does",
        ),
        HelpTopic(
            "GUI Preference Spec",
            docs_root / "user" / "gui_preference_spec.md",
            "User Guides",
            "Recording conversion and exclusion settings, including how status and document summaries report them.",
            default_anchor_id="goal",
            default_anchor_text="Goal",
        ),
        HelpTopic(
            "Pixel Inspector Guide",
            docs_root / "user" / "pixel_inspector_guide.md",
            "User Guides",
            default_anchor_id="main-controls",
            default_anchor_text="Main Controls",
        ),
        HelpTopic(
            "CLI Cheat Sheet",
            docs_root / "user" / "cli_cheat_sheet.md",
            "User Guides",
            default_anchor_id="phase-1-record",
            default_anchor_text="Phase 1: Record",
        ),
        HelpTopic(
            "ASS CLI Quickstart",
            docs_root / "user" / "ass_cli_quickstart.md",
            "User Guides",
        ),
        HelpTopic(
            "Struct and DLL Quickstart",
            docs_root / "user" / "struct_and_dll_quickstart.md",
            "User Guides",
            "Working example first, ABI details second; includes the monitor-info wrapper path.",
            default_anchor_id="what-you-can-write",
            default_anchor_text="What You Can Write",
        ),
        HelpTopic(
            "Structs and DLL Interop",
            docs_root / "user" / "structs_and_dlls.md",
            "User Guides",
            "Walkthrough of Struct, Record, Declare Func/Sub, and the Windows wrapper surface.",
            default_anchor_id="monitor-info-wrapper-path",
            default_anchor_text="Monitor Info Wrapper Path",
        ),
        HelpTopic(
            "Struct Layout Contract",
            docs_root / "user" / "struct_layout_contract.md",
            "User Guides",
            "Exact ABI contract, layout rules, and the GetMonitorInfoEx exception.",
            default_anchor_id="abi-notes",
            default_anchor_text="ABI Notes",
        ),
        HelpTopic(
            "Monitor Info Wrapper Demo",
            repo_root / "samples" / "README.md",
            "User Guides",
            "Runnable GetMonitorInfo and GetMonitorInfoEx flow with the wrapper guidance.",
            default_anchor_id="monitor-info-wrapper-demo",
            default_anchor_text="Monitor Info Wrapper Demo",
        ),
        HelpTopic(
            "ReadFile Demo",
            repo_root / "samples" / "README.md",
            "User Guides",
            "Runnable ReadFile() sample that prints each line with WriteLn().",
            default_anchor_id="readfile-demo",
            default_anchor_text="ReadFile Demo",
        ),
        HelpTopic(
            "Date and Time Demo",
            repo_root / "samples" / "README.md",
            "User Guides",
            "Runnable date and time smoke test for `Time()`, `LocalTime()`, `UTCTime()`, `ParseDateTime()`, `FormatDateTime()`, `DateAdd()`, and `DateDiff()`.",
            default_anchor_id="date-and-time-demo",
            default_anchor_text="Date and Time Demo",
        ),
        HelpTopic(
            "Enum Examples Demo",
            repo_root / "samples" / "README.md",
            "User Guides",
            "Runnable enum sample that exercises namespace-qualified members, direct member names, and label helpers.",
            default_anchor_id="enum-examples-demo",
            default_anchor_text="Enum Examples Demo",
        ),
        HelpTopic(
            "Language Reference",
            docs_root / "user" / "language_reference.md",
            "User Guides",
            default_anchor_id="syntax-overview",
            default_anchor_text="Syntax Overview",
        ),
        HelpTopic(
            "ASS CLI Spec",
            docs_root / "user" / "ass_cli_spec.md",
            "User Guides",
        ),
        HelpTopic(
            "Math Builtin Examples",
            docs_root / "user" / "math_builtin_examples.md",
            "User Guides",
        ),
        HelpTopic(
            "String Helper Examples",
            docs_root / "user" / "string_helpers_examples.md",
            "User Guides",
            "Runnable examples for `StringCompare()`, `StringInStr()`, `StringReplace()`, string slicing and trimming helpers, and string runtime values.",
        ),
        HelpTopic(
            "Builtin Coverage Map",
            docs_root / "user" / "builtin_coverage_map.md",
            "User Guides",
        ),
        HelpTopic(
            "Desktop Table API",
            repo_root / "apps" / "desktop" / "table_api" / "README.md",
            "Desktop UI",
            "Reusable table widgets, delegates, and the hotkey editor.",
        ),
    ]
    return [_topic_with_search_text(topic) for topic in topics]


def _topic_with_search_text(topic: HelpTopic) -> HelpTopic:
    try:
        text = topic.path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    searchable = "\n".join(
        [
            topic.title,
            topic.section,
            topic.description,
            text,
        ]
    ).casefold()
    return HelpTopic(
        title=topic.title,
        path=topic.path,
        section=topic.section,
        description=topic.description,
        default_anchor_id=topic.default_anchor_id,
        default_anchor_text=topic.default_anchor_text,
        content_text=text,
        search_text=searchable,
    )


def _color_luminance(color) -> float:
    def channel(value: int) -> float:
        normalized = value / 255.0
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _is_dark_color(color) -> bool:
    return _color_luminance(color) < 0.5


def _contrast_ratio(foreground, background) -> float:
    lighter = max(_color_luminance(foreground), _color_luminance(background))
    darker = min(_color_luminance(foreground), _color_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _rgba(color, alpha: float) -> str:
    alpha = max(0.0, min(1.0, alpha))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.3f})"


def _best_contrast_color(background, *candidates):
    if not candidates:
        return background
    return max(candidates, key=lambda color: _contrast_ratio(color, background))


_SUPPORTED_HELP_SUFFIXES = {".md", ".markdown", ".html", ".htm"}
_ALLOWED_EXTERNAL_HELP_SCHEMES = {"http", "https"}


def _heading_anchor_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug or "section"


def _theme_accent_styles(palette: QPalette, *, selected: bool) -> dict[str, str]:
    highlight = palette.color(QPalette.ColorRole.Highlight)
    highlighted_text = palette.color(QPalette.ColorRole.HighlightedText)
    text = palette.color(QPalette.ColorRole.Text)
    window_text = palette.color(QPalette.ColorRole.WindowText)
    base = palette.color(QPalette.ColorRole.Base)
    window = palette.color(QPalette.ColorRole.Window)
    surface_text = _best_contrast_color(window, window_text, text, highlighted_text)

    if selected:
        term_bg = _rgba(highlight, 0.35 if _is_dark_color(base) else 0.26)
        term_fg = _rgba(highlighted_text, 1.0)
        badge_bg = _rgba(highlight, 0.22 if _is_dark_color(base) else 0.18)
        badge_fg = _rgba(highlighted_text, 1.0)
        badge_border = _rgba(highlight, 0.55)
    else:
        term_bg = _rgba(highlight, 0.24 if _is_dark_color(base) else 0.18)
        term_fg = _rgba(text if _contrast_ratio(text, highlight) > _contrast_ratio(highlighted_text, highlight) else highlighted_text, 1.0)
        badge_bg = _rgba(highlight, 0.14 if _is_dark_color(base) else 0.11)
        badge_fg = _rgba(text, 1.0)
        badge_border = _rgba(highlight, 0.42)

    return {
        "term": (
            f"background-color: {term_bg}; color: {term_fg}; font-weight: 800; "
            f"border-radius: 4px; padding: 0 2px; box-shadow: inset 0 0 0 1px {_rgba(highlight, 0.24)};"
        ),
        "badge": (
            f"display: inline-block; margin-left: 8px; padding: 1px 7px; border-radius: 999px; "
            f"background-color: {badge_bg}; color: {badge_fg}; border: 1px solid {badge_border}; "
            "font-size: 10px; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase;"
        ),
        "accent": _rgba(highlight, 0.92 if _is_dark_color(base) else 0.74),
        "accent_soft": _rgba(highlight, 0.18 if _is_dark_color(base) else 0.10),
        "accent_border": _rgba(highlight, 0.42 if _is_dark_color(base) else 0.26),
        "accent_ink": _rgba(surface_text, 1.0),
        "surface_ink": _rgba(surface_text, 1.0),
        "surface_muted": _rgba(surface_text, 0.72 if _is_dark_color(base) else 0.64),
        "surface_soft": _rgba(surface_text, 0.58 if _is_dark_color(base) else 0.50),
    }


class HelpTopicDelegate(QStyledItemDelegate):
    MATCH_COUNT_ROLE = Qt.ItemDataRole.UserRole + 1
    SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._highlight_terms: tuple[str, ...] = ()

    def set_search_query(self, query: str) -> None:
        terms = {term.casefold() for term in query.split() if term.strip()}
        self._highlight_terms = tuple(sorted(terms, key=len, reverse=True))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        text = view_option.text
        view_option.text = ""
        match_count = int(index.data(self.MATCH_COUNT_ROLE) or 0)
        styles = _theme_accent_styles(
            view_option.palette,
            selected=bool(view_option.state & QStyle.StateFlag.State_Selected),
        )

        if not index.parent().isValid():
            self._paint_section_header(painter, view_option, index, text)
            return

        if not text:
            return

        subtitle = str(index.data(self.SUBTITLE_ROLE) or "")
        row_rect = view_option.rect.adjusted(6, 1, -6, -1)
        is_selected = bool(view_option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(view_option.state & QStyle.StateFlag.State_MouseOver)
        base_color = view_option.palette.color(QPalette.ColorRole.Base)
        row_fill = QColor(base_color)
        row_fill.setAlpha(0)
        if is_selected:
            row_fill = QColor(view_option.palette.color(QPalette.ColorRole.Highlight))
            row_fill.setAlpha(20 if _is_dark_color(base_color) else 15)
        elif is_hovered:
            row_fill = QColor(255, 255, 255, 228)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(row_fill)
        painter.drawRoundedRect(row_rect, 9, 9)
        painter.restore()

        doc = QTextDocument()
        doc.setDefaultFont(view_option.font)
        doc.setDocumentMargin(0)
        doc.setTextWidth(self._topic_row_width(view_option))
        doc.setHtml(
            self._build_html(
                text,
                styles=styles,
                subtitle=subtitle,
                match_count=match_count,
            )
        )

        painter.save()
        painter.translate(row_rect.topLeft())
        clip = QRectF(0, 0, row_rect.width(), row_rect.height())
        doc.drawContents(painter, clip)
        painter.restore()

    def _paint_section_header(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
        text: str,
    ) -> None:
        rect = option.rect.adjusted(6, 2, -6, -2)
        count = max(0, index.model().rowCount(index) if index.isValid() else 0)
        widget = option.widget
        is_expanded = bool(widget.isExpanded(index)) if widget is not None and hasattr(widget, "isExpanded") else True
        owner = getattr(widget, "_help_browser_owner", None)
        progress = 1.0 if is_expanded else 0.0
        if owner is not None and hasattr(owner, "section_expand_progress"):
            progress = float(owner.section_expand_progress(text))
        background = QColor(255, 255, 255, 242)
        border = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        border.setAlpha(150)
        title_color = QColor(option.palette.color(QPalette.ColorRole.WindowText))
        title_color.setAlpha(245)
        count_bg = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        count_border = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        count_text = QColor(option.palette.color(QPalette.ColorRole.WindowText))
        if owner is not None and hasattr(owner, "section_badge_colors"):
            count_bg, count_border, count_text = owner.section_badge_colors(text)
        else:
            count_bg.setAlpha(30 if _is_dark_color(option.palette.color(QPalette.ColorRole.Base)) else 26)
            count_border.setAlpha(120)
            count_text = _best_contrast_color(
                count_bg,
                option.palette.color(QPalette.ColorRole.WindowText),
                option.palette.color(QPalette.ColorRole.Text),
                option.palette.color(QPalette.ColorRole.HighlightedText),
            )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 9, 9)

        stripe_color = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        stripe_color.setAlpha(180)
        stripe_rect = rect.adjusted(0, 0, -rect.width() + 5, 0)
        painter.fillRect(stripe_rect, stripe_color)

        icon_size = 15
        icon_rect = QRectF(
            rect.left() + 10,
            rect.center().y() - icon_size / 2,
            icon_size,
            icon_size,
        )
        section_icon = None
        if owner is not None and hasattr(owner, "section_icon"):
            section_icon = owner.section_icon(text)
        if section_icon is not None and not section_icon.isNull():
            icon_bg = QColor(option.palette.color(QPalette.ColorRole.Highlight))
            icon_bg.setAlpha(36 if _is_dark_color(option.palette.color(QPalette.ColorRole.Base)) else 46)
            icon_border = QColor(option.palette.color(QPalette.ColorRole.Highlight))
            icon_border.setAlpha(90)
            painter.setPen(icon_border)
            painter.setBrush(icon_bg)
            painter.drawRoundedRect(icon_rect.adjusted(-1, -1, 1, 1), 5, 5)
            section_icon.paint(
                painter,
                icon_rect.toRect(),
                Qt.AlignmentFlag.AlignCenter,
            )

        chevron_size = 14
        chevron_rect = QRectF(
            rect.left() + 34,
            rect.center().y() - chevron_size / 2,
            chevron_size,
            chevron_size,
        )
        chevron_border = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        chevron_border.setAlpha(int(150 + (65 * progress)))
        chevron_pen = QPen(
            chevron_border,
            1.55,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.save()
        painter.translate(chevron_rect.center())
        painter.rotate(90.0 * progress)
        painter.setPen(chevron_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        caret = QPainterPath()
        caret.moveTo(-3.2, -2.9)
        caret.lineTo(2.4, 0.0)
        caret.lineTo(-3.2, 2.9)
        painter.drawPath(caret)
        painter.restore()

        badge_rect = None
        if count > 0:
            badge_text = f"{count} topic{'s' if count != 1 else ''}"
            badge_metrics = painter.fontMetrics()
            badge_width = badge_metrics.horizontalAdvance(badge_text) + 18
            badge_height = max(20, badge_metrics.height() + 8)
            badge_rect = QRectF(
                rect.right() - badge_width - 12,
                rect.center().y() - badge_height / 2 + 1,
                badge_width,
                badge_height,
            )

        content_right = badge_rect.left() - 8 if badge_rect is not None else rect.right() - 12
        content_rect = QRectF(rect.left() + 58, rect.top() + 7, max(1.0, content_right - (rect.left() + 58)), rect.height() - 14)
        painter.setPen(title_color)
        section_font = painter.font()
        section_font.setBold(True)
        section_font.setLetterSpacing(section_font.SpacingType.AbsoluteSpacing, 0.45)
        painter.setFont(section_font)
        title_metrics = painter.fontMetrics()
        elided_title = title_metrics.elidedText(text.upper(), Qt.TextElideMode.ElideRight, int(content_rect.width()))
        painter.drawText(
            content_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_title,
        )

        if badge_rect is not None:
            badge_text = f"{count} topic{'s' if count != 1 else ''}"
            painter.setPen(count_border)
            painter.setBrush(count_bg)
            painter.drawRoundedRect(badge_rect, 9, 9)
            badge_font = painter.font()
            badge_font.setBold(True)
            badge_font.setPointSize(max(1, badge_font.pointSize() - 1))
            painter.setFont(badge_font)
            painter.setPen(count_text)
            painter.drawText(
                badge_rect,
                Qt.AlignmentFlag.AlignCenter,
                badge_text,
            )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)

        if not index.parent().isValid():
            return QSize(max(1, view_option.rect.width()), max(1, view_option.fontMetrics.height() + 14))

        doc = QTextDocument()
        doc.setDefaultFont(view_option.font)
        doc.setDocumentMargin(0)
        doc.setTextWidth(self._topic_row_width(view_option))
        doc.setHtml(
            self._build_html(
                view_option.text,
                subtitle=str(index.data(self.SUBTITLE_ROLE) or ""),
                styles=_theme_accent_styles(view_option.palette, selected=False),
                match_count=int(index.data(self.MATCH_COUNT_ROLE) or 0),
            )
        )
        size = doc.size().toSize()
        return QSize(max(1, size.width()), max(1, size.height()) + 4)

    def _topic_row_width(self, option: QStyleOptionViewItem) -> float:
        widget = option.widget
        viewport_width = widget.viewport().width() if widget is not None and hasattr(widget, "viewport") else 0
        width = viewport_width or option.rect.width() or 280
        return max(180.0, float(width) - 72.0)

    def _build_html(
        self,
        text: str,
        *,
        styles: dict[str, str],
        subtitle: str = "",
        match_count: int = 0,
    ) -> str:
        escaped_text = html.escape(text)
        escaped_subtitle = html.escape(subtitle)
        badge_html = ""
        if match_count > 0:
            badge_html = (
                f'<span class="match-count-badge" style="{styles["badge"]}">{match_count} '
                f'match{"es" if match_count != 1 else ""}</span>'
            )
        title_html = escaped_text
        if not self._highlight_terms:
            title_html = f"{escaped_text} {badge_html}".strip()
            subtitle_html = escaped_subtitle
        else:
            pattern = re.compile("|".join(re.escape(term) for term in self._highlight_terms), re.IGNORECASE)

            def replace(match: re.Match[str]) -> str:
                return (
                    f'<span class="match-term" style="{styles["term"]}">'
                    f"{html.escape(match.group(0))}"
                    "</span>"
                )

            title_html = f"{pattern.sub(replace, escaped_text)} {badge_html}".strip()
            subtitle_html = pattern.sub(replace, escaped_subtitle) if escaped_subtitle else ""

        subtitle_block = (
            f'<div class="topic-row-subtitle" style="color: {styles["surface_soft"]}; font-size: 10.5px; line-height: 1.05; margin: 0;">{subtitle_html}</div>'
            if subtitle_html
            else ""
        )

        return (
            '<div class="topic-row" style="line-height: 1.08; margin: 0; padding: 0;">'
            f'<div class="topic-row-title" style="font-weight: 600; font-size: 12.25px; margin: 0 0 1px 0;">{title_html}</div>'
            f"{subtitle_block}"
            "</div>"
        )


class _HelpBrowserPage(QWebEnginePage):
    def __init__(self, owner: "ActionShellScriptHelpBrowser") -> None:
        super().__init__(owner.browser)
        self._owner = owner

    def _open_local_link(self, path: Path, anchor_id: str | None) -> None:
        QTimer.singleShot(
            0,
            lambda path=path, anchor_id=anchor_id: self._owner.open_document(path, anchor_id=anchor_id),
        )

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QUrl,
        navigation_type: QWebEnginePage.NavigationType,
        isMainFrame: bool,
    ) -> bool:
        if navigation_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                anchor_id = url.fragment().strip() or None
                self._open_local_link(path, anchor_id)
                return False
            if url.scheme().casefold() in _ALLOWED_EXTERNAL_HELP_SCHEMES:
                QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, navigation_type, isMainFrame)


class ActionShellScriptHelpBrowser(QMainWindow):
    def __init__(self, *, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._on_close = on_close
        self._home_file = _docs_root() / "index.md"
        self._topics = _help_topics()
        self._topic_by_path: dict[Path, HelpTopic] = {}
        for topic in self._topics:
            self._topic_by_path.setdefault(topic.path.resolve(), topic)
        self._item_by_path: dict[Path, QTreeWidgetItem] = {}
        self._item_by_topic: dict[HelpTopic, QTreeWidgetItem] = {}
        self._pending_anchor_id: str | None = None
        self._pending_anchor_text: str | None = None
        self._section_expand_progress_map: dict[str, float] = {}
        self._section_expand_animations: dict[str, QVariantAnimation] = {}

        self.setWindowTitle("Help")
        self.setWindowIcon(QIcon(str(desktop_asset_path(DesktopAsset.FROG_ICON_ICO))))
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(1120, 780)
        self.setMinimumSize(860, 620)

        self.browser = QWebEngineView(self)
        self.browser.setPage(_HelpBrowserPage(self))
        load_finished = getattr(self.browser, "loadFinished", None)
        if load_finished is not None and hasattr(load_finished, "connect"):
            load_finished.connect(self._handle_browser_load_finished)

        self._build_actions()
        self._build_ui()
        self._populate_toc()
        self._apply_toc_filter("")
        self.go_home()

    def _build_actions(self) -> None:
        self.back_action = QAction("Back", self)
        self.back_action.setIcon(self._toolbar_icon("mdi6.arrow-left"))
        self.back_action.setToolTip("Back")
        self.back_action.setStatusTip("Back")
        self.back_action.triggered.connect(self.browser.back)

        self.forward_action = QAction("Forward", self)
        self.forward_action.setIcon(self._toolbar_icon("mdi6.arrow-right"))
        self.forward_action.setToolTip("Forward")
        self.forward_action.setStatusTip("Forward")
        self.forward_action.triggered.connect(self.browser.forward)

        self.reload_action = QAction("Reload", self)
        self.reload_action.setIcon(self._toolbar_icon("mdi6.reload"))
        self.reload_action.setToolTip("Reload")
        self.reload_action.setStatusTip("Reload")
        self.reload_action.triggered.connect(self.browser.reload)

        self.home_action = QAction("Home", self)
        self.home_action.setIcon(self._toolbar_icon("mdi6.home-variant"))
        self.home_action.setToolTip("Home")
        self.home_action.setStatusTip("Home")
        self.home_action.triggered.connect(self.go_home)

    def _build_ui(self) -> None:
        accent_styles = self._accent_styles()
        toolbar = QToolBar("Help", self)
        self.help_toolbar = toolbar
        toolbar.setObjectName("helpToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.addAction(self.back_action)
        toolbar.addAction(self.forward_action)
        toolbar.addAction(self.reload_action)
        toolbar.addSeparator()
        toolbar.addAction(self.home_action)
        toolbar.setStyleSheet(self._help_toolbar_style_sheet(accent_styles))
        self.addToolBar(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet(self._help_splitter_style_sheet(accent_styles))

        nav_panel = QFrame(splitter)
        nav_panel.setObjectName("helpNavPanel")
        nav_panel.setFrameShape(QFrame.Shape.StyledPanel)
        nav_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        nav_panel.setStyleSheet(self._help_nav_panel_style_sheet(accent_styles))
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(12, 12, 12, 12)
        nav_layout.setSpacing(10)

        nav_header = QFrame(nav_panel)
        self.help_nav_header = nav_header
        nav_header.setObjectName("helpNavHeader")
        nav_header.setStyleSheet(self._help_nav_header_style_sheet(accent_styles))
        nav_header_layout = QVBoxLayout(nav_header)
        nav_header_layout.setContentsMargins(12, 10, 12, 10)
        nav_header_layout.setSpacing(2)

        nav_title = QLabel("Help Topics", nav_header)
        nav_title.setObjectName("helpTopicsTitle")
        nav_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        nav_header_layout.addWidget(nav_title)

        nav_subtitle = QLabel("Searchable docs and guided browsing", nav_header)
        nav_subtitle.setObjectName("helpTopicsSubtitle")
        nav_subtitle.setStyleSheet("font-size: 10px; letter-spacing: 0.02em;")
        nav_header_layout.addWidget(nav_subtitle)

        nav_layout.addWidget(nav_header)

        nav_section_caption = QLabel("Browse topics", nav_panel)
        nav_section_caption.setObjectName("helpSectionCaption")
        nav_section_caption.setStyleSheet(self._help_section_caption_style_sheet(accent_styles))
        nav_layout.addWidget(nav_section_caption)

        self.search_box = QLineEdit(nav_panel)
        self.search_box.setObjectName("helpSearchBox")
        self.search_box.setPlaceholderText("Search docs, commands, and guides")
        self.search_box.textChanged.connect(self._apply_toc_filter)
        self.search_box.installEventFilter(self)
        self.search_box.setStyleSheet(self._help_search_style_sheet(accent_styles))
        nav_layout.addWidget(self.search_box)

        self.toc_tree = QTreeWidget(nav_panel)
        self.toc_tree.setObjectName("helpTocTree")
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setAlternatingRowColors(True)
        self.toc_tree.setWordWrap(True)
        self.toc_tree.setIndentation(16)
        self.toc_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.toc_tree.setAnimated(True)
        self.toc_tree.itemSelectionChanged.connect(self._on_toc_selection_changed)
        self.toc_tree.itemExpanded.connect(self._on_toc_section_expanded)
        self.toc_tree.itemCollapsed.connect(self._on_toc_section_collapsed)
        self._toc_delegate = HelpTopicDelegate(self.toc_tree)
        self.toc_tree._help_browser_owner = self
        self.toc_tree.setItemDelegate(self._toc_delegate)
        self.toc_tree.setStyleSheet(self._help_toc_style_sheet(accent_styles))
        self.toc_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        nav_layout.addWidget(self.toc_tree, 1)

        self.topic_count_label = QLabel(nav_panel)
        self.topic_count_label.setObjectName("helpTopicCountLabel")
        self.topic_count_label.setWordWrap(True)
        self.topic_count_label.setStyleSheet(
            f"color: {accent_styles['surface_muted']}; font-size: 10px;"
        )
        nav_layout.addWidget(self.topic_count_label)

        self.browser_container = QWidget(splitter)
        browser_layout = QVBoxLayout(self.browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)
        browser_layout.addWidget(self.browser, 1)

        splitter.addWidget(nav_panel)
        splitter.addWidget(self.browser_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 820])

        self.setCentralWidget(splitter)

    def _populate_toc(self) -> None:
        self.toc_tree.clear()
        self._item_by_path.clear()
        self._item_by_topic.clear()
        self._section_expand_progress_map.clear()
        self.toc_tree.setColumnCount(1)

        sections: dict[str, QTreeWidgetItem] = {}
        for topic in self._topics:
            section_item = sections.get(topic.section)
            if section_item is None:
                section_item = QTreeWidgetItem(self.toc_tree, [topic.section])
                section_item.setFirstColumnSpanned(True)
                section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                sections[topic.section] = section_item

            child = QTreeWidgetItem(section_item, [topic.title])
            child.setToolTip(0, topic.description or topic.title)
            child.setData(0, Qt.ItemDataRole.UserRole, topic)
            child.setData(0, HelpTopicDelegate.SUBTITLE_ROLE, topic.description or self._first_body_line(topic.content_text))
            self._item_by_path[topic.path.resolve()] = child
            self._item_by_topic[topic] = child

        self.toc_tree.blockSignals(True)
        try:
            self.toc_tree.expandAll()
        finally:
            self.toc_tree.blockSignals(False)
        self.toc_tree.resizeColumnToContents(0)
        for section_title in sections:
            self._section_expand_progress_map[section_title] = 1.0
        self.toc_tree.viewport().update()

    def _apply_toc_filter(self, text: str) -> None:
        query = text.strip().casefold()
        self._toc_delegate.set_search_query(query)
        visible_topics = 0

        for index in range(self.toc_tree.topLevelItemCount()):
            section_item = self.toc_tree.topLevelItem(index)
            section_visible = False
            for child_index in range(section_item.childCount()):
                child = section_item.child(child_index)
                topic_value = child.data(0, Qt.ItemDataRole.UserRole)
                topic = topic_value if isinstance(topic_value, HelpTopic) else None
                path = topic.path if topic is not None else None
                haystack = " ".join(
                    filter(
                        None,
                        [
                            child.text(0),
                            path.name if path is not None else "",
                            topic.description if topic is not None else "",
                            topic.section if topic is not None else section_item.text(0),
                            topic.content_text if topic is not None else "",
                            topic.search_text if topic is not None else "",
                        ],
                    )
                ).casefold()
                match = not query or query in haystack
                child.setHidden(not match)
                child.setData(0, HelpTopicDelegate.SUBTITLE_ROLE, self._build_topic_snippet(topic, query) if topic is not None else "")
                child.setData(0, HelpTopicDelegate.MATCH_COUNT_ROLE, self._count_topic_matches(topic, query) if topic is not None else 0)
                section_visible = section_visible or match
                visible_topics += 1 if match else 0
            section_item.setHidden(not section_visible)
            if section_visible:
                section_item.setExpanded(True)

        total_topics = len(self._topics)
        self.topic_count_label.setText(
            f"{visible_topics} of {total_topics} topics visible"
            if query
            else f"{total_topics} topics available"
        )

        if query and visible_topics == 0:
            self._show_empty_search_state(query)

    def _count_topic_matches(self, topic: HelpTopic, query: str) -> int:
        if not query:
            return 0

        searchable = " ".join(
            [
                topic.title,
                topic.section,
                topic.description,
                topic.content_text,
            ]
        ).casefold()
        count = 0
        for term in {term.casefold() for term in query.split() if term.strip()}:
            count += len(re.findall(re.escape(term), searchable))
        return count

    def _build_topic_snippet(self, topic: HelpTopic, query: str) -> str:
        if not query:
            return topic.description or self._first_body_line(topic.content_text)

        text = topic.content_text.strip()
        if not text:
            return topic.description or ""

        match_index = self._find_snippet_anchor(text, query)
        if match_index < 0:
            return topic.description or self._first_body_line(text)

        # Keep enough surrounding context for long sample sentences so
        # related helpers that appear earlier in the paragraph remain visible.
        snippet_start = max(0, match_index - 130)
        snippet_end = min(len(text), match_index + max(len(query), 140))
        snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()
        if snippet_start > 0:
            snippet = "… " + snippet
        if snippet_end < len(text):
            snippet = snippet + " …"
        return snippet

    def _find_snippet_anchor(self, text: str, query: str) -> int:
        query_text = query.strip()
        if not query_text:
            return -1

        lowered = text.casefold()
        phrase = query_text.casefold()

        # Prefer an exact phrase match so short terms such as "tab" do not
        # anchor the snippet inside unrelated words like "documentation".
        phrase_match = re.search(rf"\b{re.escape(phrase)}\b", lowered)
        if phrase_match is not None:
            return phrase_match.start()

        query_terms = [term.casefold() for term in query_text.split() if term.strip()]
        positions = []
        for term in query_terms:
            term_match = re.search(rf"\b{re.escape(term)}\b", lowered)
            if term_match is not None:
                positions.append(term_match.start())
        if positions:
            return min(positions)
        return lowered.find(phrase)

    def _first_body_line(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            return stripped
        return ""

    def _show_empty_search_state(self, query: str) -> None:
        accent_styles = self._accent_styles()
        self.browser.setHtml(
            self._wrap_document_html(
                "No help topics found",
                (
                    "<section class=\"help-section accent-callout\">"
                    "<h2>No help topics found</h2>"
                    f"<p>No help topics matched <code>{html.escape(query)}</code>.</p>"
                    "<p>Try a shorter term or clear the search box to see all topics.</p>"
                    "</section>"
                ),
                accent_styles=accent_styles,
            ),
            self._docs_base_url(self._home_file),
        )

    def _on_toc_selection_changed(self) -> None:
        items = self.toc_tree.selectedItems()
        if not items:
            return
        item = items[0]
        topic_value = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(topic_value, HelpTopic):
            return
        self._open_topic(topic_value)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.search_box and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent):
                if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
                    self._focus_first_visible_topic()
                    return True
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._activate_first_visible_topic()
                    return True
        return super().eventFilter(obj, event)

    def _visible_topic_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for index in range(self.toc_tree.topLevelItemCount()):
            section_item = self.toc_tree.topLevelItem(index)
            for child_index in range(section_item.childCount()):
                child = section_item.child(child_index)
                if not child.isHidden():
                    items.append(child)
        return items

    def _focus_first_visible_topic(self) -> None:
        first_item = self._first_visible_topic()
        if first_item is None:
            return
        self.toc_tree.setFocus(Qt.FocusReason.TabFocusReason)
        self.toc_tree.setCurrentItem(first_item)

    def _activate_first_visible_topic(self) -> None:
        first_item = self._first_visible_topic()
        if first_item is None:
            return
        topic_value = first_item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(topic_value, HelpTopic):
            return
        self._open_topic(topic_value)

    def _first_visible_topic(self) -> QTreeWidgetItem | None:
        items = self._visible_topic_items()
        return items[0] if items else None

    def _docs_base_url(self, path: Path) -> QUrl:
        return QUrl.fromLocalFile(str(path.parent.resolve()) + os.sep)

    def _load_markdown(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        document = QTextDocument()
        document.setMarkdown(source)
        rendered = self._inject_heading_ids(document.toHtml(), source)
        self.browser.setHtml(rendered, self._docs_base_url(path))

    def _load_html(self, path: Path) -> None:
        self.browser.load(QUrl.fromLocalFile(str(path)))

    def _load_error_page(self, path: Path, *, topic_title: str | None = None) -> None:
        heading_html = (
            f"<h2>{html.escape(topic_title)}</h2>"
            if topic_title is not None
            else "<h2>Help page not found</h2>"
        )
        self.browser.setHtml(
            self._wrap_document_html(
                "Help page not found",
                f"{heading_html}<p>The file <code>{html.escape(str(path))}</code> could not be found.</p>",
            ),
            self._docs_base_url(path),
        )

    def _render_home_page(self) -> str:
        accent_styles = self._accent_styles()
        quick_links = [
            (
                "Start Here",
                self._topic_href(self._topic_by_title("Home")),
                "Begin with the project overview and launch commands.",
                "&#x1F3E0;",
                "reference",
            ),
            (
                "Open Script Guide",
                self._topic_href(self._topic_by_title("Open Script Guide")),
                "See how to open and inspect `.ass` files end to end.",
                "&#x1F4D6;",
                "guide",
            ),
            (
                "Generate Script Guide",
                self._topic_href(self._topic_by_title("Generate Script Guide")),
                "Walk from captured input to generated script text.",
                "&#x2728;",
                "guide",
            ),
            (
                "Struct and DLL Quickstart",
                self._topic_href(self._topic_by_title("Struct and DLL Quickstart")),
                "Follow the shortest path to `Struct` and `Declare`.",
                "&#x1F9F0;",
                "guide",
            ),
            (
                "Monitor Info Wrapper Demo",
                self._topic_href(self._topic_by_title("Monitor Info Wrapper Demo")),
                "Use the runnable demo to validate wrapper behavior.",
                "&#x1F5A5;",
                "guide",
            ),
            (
                "Date and Time Demo",
                self._topic_href(self._topic_by_title("Date and Time Demo")),
                "Exercise the time helpers in a live sample.",
                "&#x23F0;",
                "guide",
            ),
            (
                "Enum Examples Demo",
                self._topic_href(self._topic_by_title("Enum Examples Demo")),
                "Try namespace-qualified members and labels in one place.",
                "&#x1F52C;",
                "guide",
            ),
            (
                "Pixel Inspector Guide",
                self._topic_href(self._topic_by_title("Pixel Inspector Guide")),
                "Learn the inspector controls and pixel readouts.",
                "&#x1F50D;",
                "guide",
            ),
            (
                "Structs and DLL Interop",
                self._topic_href(self._topic_by_title("Structs and DLL Interop")),
                "See the wrapper rules that keep declarations stable.",
                "&#x1F9E9;",
                "guide",
            ),
            (
                "Struct Layout Contract",
                self._topic_href(self._topic_by_title("Struct Layout Contract")),
                "Check the ABI contract before you wire a new type.",
                "&#x1F4D0;",
                "reference",
            ),
            (
                "Desktop Table API",
                self._topic_href(self._topic_by_title("Desktop Table API")),
                "Reference the desktop table editing helpers.",
                "&#x1F4CB;",
                "reference",
            ),
        ]
        sections = {
            "Quick Start": [
                "Use the search box on the left to filter docs instantly.",
                "Open a topic in the table of contents to load it in the reader.",
                "Use Home to return to this overview page at any time.",
            ],
            "Best Starting Points": [
                "The docs landing page gives the big-picture workflow and launch commands.",
                "The user guides cover the most common GUI and CLI tasks.",
                "The Recording page includes `Exclude main window during recording`, and the Document Status dialog reports whether the current document came from that capture mode.",
            ],
            "Search Tips": [
                "Search matches content inside the docs, not just the topic names.",
                "Try a phrase from a command example, a setting name, or a section heading.",
            ],
        }
        nav_cards = "\n".join(
            (
                f'<a class="quick-link-card {html.escape(kind)}{" featured" if icon else ""}" href="{html.escape(link)}">'
                f'<span class="quick-link-top">'
                + (f'<span class="quick-link-icon" aria-hidden="true">{icon}</span>' if icon else "")
                + f'<span class="quick-link-title">{html.escape(title)}</span>'
                "</span>"
                f'<span class="quick-link-hint">{html.escape(hint)}</span>'
                "</a>"
            )
            for title, link, hint, icon, kind in quick_links
        )
        section_html = "\n".join(
            "<section class=\"help-section\">"
            f"<h2>{html.escape(title)}</h2>"
            + "".join(f"<p>{html.escape(item)}</p>" for item in body)
            + "</section>"
            for title, body in sections.items()
        )
        logo_src = desktop_asset_path(DesktopAsset.CODERDAWG_LOGO).as_uri()
        topic_cards = "\n".join(
            self._render_topic_card(topic)
            for topic in self._topics
            if topic.section in {"Start Here", "User Guides", "Desktop UI"}
        )
        return self._wrap_document_html(
            "ActionShellScript Help",
            (
                "<div class=\"home-grid\">"
                "<section class=\"hero\">"
                f'<img class="hero-logo" src="{html.escape(logo_src)}" alt="CoderDawg logo" />'
                "<h1>ActionShellScript Help</h1>"
                "<p>Browse the docs, filter topics, and jump straight to the guide you need.</p>"
                "<div class=\"quick-links\">"
                f"{nav_cards}"
                "</div>"
                "</section>"
                f"{section_html}"
                "<section class=\"help-section accent-callout\">"
                "<h2>Popular Topics</h2>"
                f"<div class=\"cards\">{topic_cards}</div>"
                "</section>"
                "</div>"
            ),
            accent_styles=accent_styles,
        )

    def _render_topic_card(self, topic: HelpTopic) -> str:
        href = self._topic_href_from_docs_root(topic.path)
        if topic.default_anchor_id:
            href = f"{href}#{html.escape(topic.default_anchor_id)}"
        return (
            '<a class="topic-card" href="'
            f'{html.escape(href)}">'
            f"<strong>{html.escape(topic.title)}</strong>"
            f"<span>{html.escape(topic.section)}</span>"
            "</a>"
        )

    def _topic_href(self, topic: HelpTopic | None) -> str:
        if topic is None:
            return ""
        relative = self._topic_href_from_docs_root(topic.path)
        if topic.default_anchor_id:
            return f"{relative}#{topic.default_anchor_id}"
        return relative

    def _topic_href_from_docs_root(self, path: Path) -> str:
        return Path(os.path.relpath(path, _docs_root())).as_posix()

    def _topic_by_title(self, title: str) -> HelpTopic | None:
        return next((topic for topic in self._topics if topic.title == title), None)

    def _topic_for_path(self, path: Path, *, anchor_id: str | None = None) -> HelpTopic | None:
        resolved = path.resolve()
        if anchor_id is not None:
            for topic in self._topics:
                if topic.path.resolve() == resolved and topic.default_anchor_id == anchor_id:
                    return topic
        return self._topic_by_path.get(resolved)

    def _open_topic(self, topic: HelpTopic) -> None:
        if topic.default_anchor_id:
            self.open_at_section(
                topic.path,
                topic.default_anchor_id,
                anchor_text=topic.default_anchor_text,
            )
            return
        self.open_document(topic.path)

    def _open_topic_by_path(self, path: Path) -> None:
        topic = self._topic_for_path(path)
        if topic is not None:
            self._open_topic(topic)
            return
        self.open_document(path)

    def _accent_styles(self) -> dict[str, str]:
        return _theme_accent_styles(self.palette(), selected=False)

    def _toolbar_icon(self, icon_name: str):
        color = self.palette().color(QPalette.ColorRole.WindowText)
        try:
            return qta.icon(icon_name, color=color)
        except Exception:
            return qta.icon("mdi6.circle-outline", color=color)

    def section_icon(self, section_title: str) -> QIcon:
        cache = getattr(self, "_section_icon_cache", None)
        if cache is None:
            cache = {}
            self._section_icon_cache = cache
        color = self.section_icon_color(section_title)
        cache_key = (section_title, color.name())
        icon = cache.get(cache_key)
        if icon is not None:
            return icon

        icon_name = {
            "Start Here": "mdi6.home-variant",
            "User Guides": "mdi6.book-open-page-variant",
            "Desktop UI": "mdi6.table-large",
        }.get(section_title, "mdi6.circle-outline")
        try:
            icon = qta.icon(icon_name, color=color)
        except Exception:
            icon = qta.icon("mdi6.circle-outline", color=color)
        cache[cache_key] = icon
        return icon

    def section_icon_color(self, section_title: str) -> QColor:
        base_color = self.palette().color(QPalette.ColorRole.Highlight)
        tint_map = {
            "Start Here": "#2F7A4B",
            "User Guides": "#2D6CDF",
            "Desktop UI": "#7A4BC2",
        }
        color = QColor(tint_map.get(section_title, base_color.name()))
        if not color.isValid():
            color = QColor(base_color)
        if color.name().lower() == base_color.name().lower():
            return color
        mix = 0.18
        blended = QColor(
            round(color.red() * (1 - mix) + base_color.red() * mix),
            round(color.green() * (1 - mix) + base_color.green() * mix),
            round(color.blue() * (1 - mix) + base_color.blue() * mix),
        )
        return blended if blended.isValid() else QColor(base_color)

    def section_badge_colors(self, section_title: str) -> tuple[QColor, QColor, QColor]:
        tint = self.section_icon_color(section_title)
        base = self.palette().color(QPalette.ColorRole.Base)
        mix = 0.16 if _is_dark_color(base) else 0.22
        count_bg = QColor(
            round(tint.red() * (1 - mix) + base.red() * mix),
            round(tint.green() * (1 - mix) + base.green() * mix),
            round(tint.blue() * (1 - mix) + base.blue() * mix),
        )
        count_border = QColor(
            round(tint.red() * 0.92 + base.red() * 0.08),
            round(tint.green() * 0.92 + base.green() * 0.08),
            round(tint.blue() * 0.92 + base.blue() * 0.08),
        )
        count_text = _best_contrast_color(
            count_bg,
            self.palette().color(QPalette.ColorRole.WindowText),
            self.palette().color(QPalette.ColorRole.Text),
            self.palette().color(QPalette.ColorRole.HighlightedText),
        )
        return count_bg, count_border, count_text

    def section_expand_progress(self, section_title: str) -> float:
        return float(self._section_expand_progress_map.get(section_title, 1.0))

    def _on_toc_section_expanded(self, item: QTreeWidgetItem) -> None:
        self._animate_section_progress(item, 1.0)

    def _on_toc_section_collapsed(self, item: QTreeWidgetItem) -> None:
        self._animate_section_progress(item, 0.0)

    def _animate_section_progress(self, item: QTreeWidgetItem, target: float) -> None:
        section_title = item.text(0)
        start = self._section_expand_progress_map.get(section_title, 1.0 if item.isExpanded() else 0.0)
        target = max(0.0, min(1.0, float(target)))
        if abs(start - target) < 0.001:
            self._section_expand_progress_map[section_title] = target
            self.toc_tree.viewport().update()
            return

        existing = self._section_expand_animations.get(section_title)
        if existing is not None:
            existing.stop()

        animation = QVariantAnimation(self)
        animation.setStartValue(start)
        animation.setEndValue(target)
        animation.setDuration(120)
        animation.setEasingCurve(QEasingCurve.Type.OutSine)

        def update_progress(value) -> None:
            self._section_expand_progress_map[section_title] = float(value)
            self.toc_tree.viewport().update()

        def finish() -> None:
            self._section_expand_progress_map[section_title] = target
            self.toc_tree.viewport().update()
            self._section_expand_animations.pop(section_title, None)

        animation.valueChanged.connect(update_progress)
        animation.finished.connect(finish)
        self._section_expand_animations[section_title] = animation
        animation.start()

    def _inject_heading_ids(self, rendered_html: str, markdown_source: str) -> str:
        heading_ids = self._markdown_heading_ids(markdown_source)
        if not heading_ids:
            return rendered_html

        remaining_ids = iter(heading_ids)
        heading_pattern = re.compile(r"<h([1-6])([^>]*)>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)

        def replace(match: re.Match[str]) -> str:
            try:
                heading_id = next(remaining_ids)
            except StopIteration:
                return match.group(0)

            tag_level = match.group(1)
            attrs = match.group(2) or ""
            if re.search(r'\sid\s*=', attrs, re.IGNORECASE):
                return match.group(0)
            return f'<h{tag_level}{attrs} id="{html.escape(heading_id)}">{match.group(3)}</h{tag_level}>'

        return heading_pattern.sub(replace, rendered_html)

    def _markdown_heading_ids(self, markdown_source: str) -> list[str]:
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+\s*)?$")
        ids: list[str] = []
        seen: dict[str, int] = {}
        for line in markdown_source.splitlines():
            match = heading_pattern.match(line.strip())
            if match is None:
                continue
            heading_text = re.sub(r"`([^`]*)`", r"\1", match.group(2))
            heading_text = re.sub(r"[*_~\[\]\(\)!<>#]", "", heading_text).strip()
            heading_id = _heading_anchor_id(heading_text)
            occurrence = seen.get(heading_id, 0)
            seen[heading_id] = occurrence + 1
            if occurrence:
                heading_id = f"{heading_id}-{occurrence + 1}"
            ids.append(heading_id)
        return ids

    def _help_toolbar_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QToolBar#helpToolbar {"
            f" background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, {accent_styles['accent_soft']} 100%);"
            f" border: 1px solid {accent_styles['accent_border']};"
            " border-radius: 12px;"
            " spacing: 6px;"
            " padding: 5px 8px;"
            f" color: {accent_styles['surface_ink']};"
            " }"
            "QToolBar#helpToolbar QToolButton {"
            f" color: {accent_styles['surface_ink']};"
            " background: transparent;"
            " border: 1px solid transparent;"
            " border-radius: 8px;"
            " padding: 5px 10px;"
            " font-weight: 600;"
            " }"
            "QToolBar#helpToolbar QToolButton:hover {"
            f" background-color: {accent_styles['accent_soft']};"
            f" border-color: {accent_styles['accent_border']};"
            " }"
            "QToolBar#helpToolbar QToolButton:pressed {"
            f" background-color: {accent_styles['accent_soft']};"
            f" border-color: {accent_styles['accent_border']};"
            " }"
            "QToolBar#helpToolbar::separator {"
            f" background: {accent_styles['accent_border']};"
            " width: 1px;"
            " margin: 4px 4px;"
            " }"
        )

    def _help_nav_panel_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QFrame#helpNavPanel {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 rgba(255, 255, 255, 0.86), stop:1 rgba(245, 240, 228, 0.94));"
            f" border: 1px solid {accent_styles['accent_border']};"
            f" border-left: 5px solid {accent_styles['accent']};"
            " border-radius: 18px;"
            " }"
        )

    def _help_splitter_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QSplitter::handle:horizontal {"
            f" background: {accent_styles['accent_border']};"
            " margin: 0 1px;"
            " border-radius: 3px;"
            " }"
            "QSplitter::handle:horizontal:hover {"
            f" background: {accent_styles['accent']};"
            " }"
        )

    def _help_nav_header_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QFrame#helpNavHeader {"
            f" background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, {accent_styles['accent_soft']} 100%);"
            f" border: 1px solid {accent_styles['accent_border']};"
            " border-radius: 14px;"
            " }"
            "QFrame#helpNavHeader QLabel {"
            f" color: {accent_styles['surface_ink']};"
            " background: transparent;"
            " }"
            "QFrame#helpNavHeader QLabel#helpTopicsSubtitle {"
            f" color: {accent_styles['surface_muted']};"
            " }"
        )

    def _help_section_caption_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QLabel#helpSectionCaption {"
            f" color: {accent_styles['surface_muted']};"
            " font-size: 10px;"
            " font-weight: 800;"
            " letter-spacing: 0.12em;"
            " text-transform: uppercase;"
            " padding-left: 4px;"
            " }"
        )

    def _help_search_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QLineEdit#helpSearchBox {"
            " background: rgba(255, 255, 255, 0.95);"
            f" color: {accent_styles['surface_ink']};"
            f" border: 1px solid {accent_styles['accent_border']};"
            " border-radius: 10px;"
            " padding: 8px 11px;"
            " }"
            "QLineEdit#helpSearchBox:focus {"
            f" border: 1px solid {accent_styles['accent']};"
            f" background: rgba(255, 255, 255, 1.0);"
            " }"
            "QLineEdit#helpSearchBox::placeholder {"
            f" color: {accent_styles['surface_muted']};"
            " }"
        )

    def _help_toc_style_sheet(self, accent_styles: dict[str, str]) -> str:
        return (
            "QTreeWidget#helpTocTree {"
            " background: rgba(255, 255, 255, 0.9);"
            f" color: {accent_styles['surface_ink']};"
            f" border: 1px solid {accent_styles['accent_border']};"
            " border-radius: 14px;"
            " padding: 6px;"
            " outline: 0;"
            " }"
            "QTreeWidget#helpTocTree::branch {"
            " background: transparent;"
            " }"
            "QTreeWidget#helpTocTree::indicator {"
            " width: 0px;"
            " height: 0px;"
            " }"
            "QTreeWidget#helpTocTree::item:!selected {"
            f" color: {accent_styles['surface_ink']};"
            " }"
            "QTreeWidget#helpTocTree::item {"
            " padding: 4px 6px;"
            " margin: 0;"
            " border: 0;"
            " background: transparent;"
            " }"
            "QTreeWidget#helpTocTree::item:selected {"
            " background: transparent;"
            " color: inherit;"
            " border: 0;"
            " }"
            "QTreeWidget#helpTocTree::item:hover:!selected {"
                " background: transparent;"
                " color: inherit;"
            " }"
        )

    def _wrap_document_html(self, title: str, body_html: str, *, accent_styles: dict[str, str] | None = None) -> str:
        accent_styles = accent_styles or self._accent_styles()
        return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{html.escape(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7f5ef;
        --panel: #ffffff;
        --panel-border: #ddd8cc;
        --ink: #1f1f1f;
        --muted: #656565;
        --accent: {accent_styles["accent"]};
        --accent-soft: {accent_styles["accent_soft"]};
        --accent-border: {accent_styles["accent_border"]};
        --accent-ink: {accent_styles["surface_ink"]};
      }}
      body {{
        margin: 0;
        padding: 0;
        background:
          radial-gradient(circle at top right, rgba(47, 111, 79, 0.08), transparent 28%),
          linear-gradient(180deg, #faf8f2 0%, var(--bg) 100%);
        color: var(--ink);
        font-family: "Segoe UI", "Aptos", sans-serif;
      }}
      .page {{
        max-width: 1060px;
        margin: 0 auto;
        padding: 28px 30px 40px;
      }}
      .hero, .help-section {{
        background: var(--panel);
        border: 1px solid var(--panel-border);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(20, 20, 20, 0.04);
        padding: 22px 24px;
      }}
      .hero {{
        margin-bottom: 16px;
        text-align: center;
      }}
      .hero-logo {{
        display: block;
        width: min(100%, 420px);
        max-width: 420px;
        height: auto;
        margin: 0 auto 14px;
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 34px;
        letter-spacing: -0.03em;
      }}
      h2 {{
        margin: 0 0 10px;
        font-size: 20px;
      }}
      p {{
        line-height: 1.55;
        margin: 0 0 12px;
        color: var(--ink);
      }}
      .quick-links {{
        margin: 18px 0 0;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        text-align: left;
      }}
      .quick-link-card {{
        display: block;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid var(--panel-border);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(247, 244, 233, 0.98) 100%);
        color: var(--ink);
        box-shadow: 0 6px 18px rgba(20, 20, 20, 0.04);
        line-height: 1.35;
        font-weight: 600;
      }}
      .quick-link-card.guide {{
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(236, 248, 243, 0.98) 100%);
      }}
      .quick-link-card.reference {{
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(242, 244, 248, 0.98) 100%);
      }}
      .quick-link-card:hover {{
        border-color: var(--accent-border);
        background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, var(--accent-soft) 100%);
        text-decoration: none;
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(20, 20, 20, 0.07);
      }}
      .quick-link-card.featured {{
        border-color: var(--accent-border);
        background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, var(--accent-soft) 100%);
      }}
      .quick-link-top {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
      }}
      .quick-link-icon {{
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent-ink);
        font-size: 15px;
        line-height: 1;
      }}
      .quick-link-card.reference .quick-link-icon {{
        background: rgba(255, 255, 255, 0.92);
        color: var(--accent);
      }}
      .quick-link-card.guide .quick-link-icon {{
        background: rgba(255, 255, 255, 0.94);
        color: var(--accent-ink);
      }}
      .quick-link-title {{
        color: var(--ink);
      }}
      .quick-link-hint {{
        display: block;
        color: var(--muted);
        font-size: 12px;
        font-weight: 500;
      }}
      a {{
        color: var(--accent);
        text-decoration: none;
      }}
      a:hover {{
        text-decoration: underline;
      }}
      .home-grid {{
        display: grid;
        gap: 16px;
      }}
      @media (max-width: 760px) {{
        .quick-links {{
          grid-template-columns: 1fr;
        }}
      }}
      .cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 12px;
      }}
      .topic-card {{
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 14px 16px;
        border-radius: 12px;
        border: 1px solid var(--accent-border);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, var(--accent-soft) 100%);
        color: var(--ink);
        box-shadow: 0 6px 18px rgba(20, 20, 20, 0.04);
      }}
      .topic-card strong {{
        font-size: 15px;
      }}
      .topic-card span {{
        color: var(--muted);
        font-size: 12px;
      }}
      .accent-callout {{
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, var(--accent-soft) 100%);
        border-color: var(--accent-border);
      }}
      .accent-callout h2 {{
        color: var(--accent-ink);
      }}
      .accent-callout code {{
        background: var(--accent-soft);
        color: var(--accent-ink);
        border: 1px solid var(--accent-border);
      }}
      code {{
        padding: 0 4px;
        border-radius: 4px;
        background: var(--accent-soft);
      }}
    </style>
  </head>
  <body>
    <div class="page">
      {body_html}
    </div>
  </body>
</html>
"""

    def open_document(
        self,
        path: Path,
        *,
        anchor_id: str | None = None,
        anchor_text: str | None = None,
    ) -> bool:
        resolved = path.resolve()
        docs_root = _docs_root().resolve()
        if resolved not in self._topic_by_path:
            try:
                resolved.relative_to(docs_root)
            except ValueError:
                return False
        if resolved.suffix.lower() not in _SUPPORTED_HELP_SUFFIXES:
            return False
        if not resolved.exists():
            topic = self._topic_for_path(resolved, anchor_id=anchor_id)
            self._pending_anchor_id = None
            self._pending_anchor_text = None
            self._load_error_page(resolved, topic_title=topic.title if topic is not None else None)
            self._select_topic(resolved, anchor_id=anchor_id)
            return True

        self._pending_anchor_id = anchor_id.strip() if anchor_id else None
        self._pending_anchor_text = anchor_text.strip() if anchor_text else None
        if self.search_box.text():
            self.search_box.setText("")
        if resolved == self._home_file.resolve():
            self.browser.setHtml(self._render_home_page(), self._docs_base_url(resolved))
        elif resolved.suffix.lower() in {".md", ".markdown"}:
            self._load_markdown(resolved)
        elif resolved.suffix.lower() in {".html", ".htm"}:
            self._load_html(resolved)
        else:
            self._load_html(resolved)

        self._select_topic(resolved, anchor_id=anchor_id)
        return True

    def _handle_browser_load_finished(self, ok: bool) -> None:
        if not ok:
            self._pending_anchor_id = None
            self._pending_anchor_text = None
            return

        anchor_id = self._pending_anchor_id
        anchor_text = self._pending_anchor_text
        self._pending_anchor_id = None
        self._pending_anchor_text = None
        if not anchor_id and not anchor_text:
            return

        page = self.browser.page() if hasattr(self.browser, "page") else None
        if page is None or not hasattr(page, "runJavaScript"):
            return

        script = (
            "(function() {"
            f"const targetId = {json.dumps(anchor_id)};"
            f"const targetText = {json.dumps(anchor_text)};"
            "const scrollTarget = (target) => {"
            "if (target) { target.scrollIntoView({block: 'start', behavior: 'auto'}); }"
            "};"
            "if (targetId) {"
            "const idTarget = document.getElementById(targetId);"
            "if (idTarget) { scrollTarget(idTarget); return; }"
            "}"
            "if (targetText) {"
            "const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'));"
            "const target = headings.find((heading) => heading.textContent.trim() === targetText);"
            "scrollTarget(target);"
            "}"
            "})();"
        )
        page.runJavaScript(script)

    def open_at_section(
        self,
        path: Path,
        section_id: str,
        *,
        anchor_text: str | None = None,
    ) -> bool:
        return self.open_document(path, anchor_id=section_id, anchor_text=anchor_text)

    def _select_topic(self, path: Path, *, anchor_id: str | None = None) -> None:
        topic = self._topic_for_path(path, anchor_id=anchor_id)
        item = self._item_by_topic.get(topic) if topic is not None else None
        if item is None:
            return
        self.toc_tree.blockSignals(True)
        try:
            self.toc_tree.setCurrentItem(item)
        finally:
            self.toc_tree.blockSignals(False)

    def go_home(self) -> None:
        self.open_document(self._home_file)

    def present(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.browser.stop()
        if self._on_close is not None:
            self._on_close()
        super().closeEvent(event)
