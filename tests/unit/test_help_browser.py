import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

import apps.desktop.help_browser as help_browser_module  # noqa: E402
from apps.desktop.documentation_messages import docs_index_path  # noqa: E402
from apps.desktop.icon_assets import DesktopAsset, desktop_asset_path  # noqa: E402
from apps.desktop.help_browser import ActionShellScriptHelpBrowser  # noqa: E402


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeWebView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.page = None
        self.html_calls: list[tuple[str, str | None]] = []
        self.loaded_urls: list[str] = []
        self.back_calls = 0
        self.forward_calls = 0
        self.reload_calls = 0
        self.stop_calls = 0

    def setPage(self, page) -> None:  # noqa: N802
        self.page = page

    def setHtml(self, html: str, base_url: QUrl | None = None) -> None:  # noqa: N802
        self.html_calls.append((html, base_url.toString() if base_url is not None else None))

    def load(self, url: QUrl) -> None:
        self.loaded_urls.append(url.toString())

    def back(self) -> None:
        self.back_calls += 1

    def forward(self) -> None:
        self.forward_calls += 1

    def reload(self) -> None:
        self.reload_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


def _topic_item(browser: ActionShellScriptHelpBrowser, title: str):
    for index in range(browser.toc_tree.topLevelItemCount()):
        section_item = browser.toc_tree.topLevelItem(index)
        for child_index in range(section_item.childCount()):
            child = section_item.child(child_index)
            if child.text(0) == title:
                return child
    raise AssertionError(f"Missing topic item: {title}")


def test_help_browser_builds_home_page_and_filters_toc(monkeypatch) -> None:
    app = _app()
    repo_root = Path(__file__).resolve().parents[2]
    ass_cli_spec_path = (repo_root / "docs" / "user" / "ass_cli_spec.md").resolve()
    builtin_coverage_path = (repo_root / "docs" / "user" / "builtin_coverage_map.md").resolve()
    struct_quickstart_path = (repo_root / "docs" / "user" / "struct_and_dll_quickstart.md").resolve()
    structs_and_dlls_path = (repo_root / "docs" / "user" / "structs_and_dlls.md").resolve()
    struct_layout_contract_path = (repo_root / "docs" / "user" / "struct_layout_contract.md").resolve()
    gui_preference_spec_path = (repo_root / "docs" / "user" / "gui_preference_spec.md").resolve()
    samples_readme_path = (repo_root / "samples" / "README.md").resolve()
    date_time_demo_path = samples_readme_path
    enum_examples_demo_path = samples_readme_path
    table_api_path = (repo_root / "apps" / "desktop" / "table_api" / "README.md").resolve()

    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()

    assert isinstance(browser.browser, FakeWebView)
    assert browser.browser.html_calls
    assert "QToolBar#helpToolbar" in browser.help_toolbar.styleSheet()
    assert "QFrame#helpNavHeader" in browser.help_nav_header.styleSheet()
    assert browser.help_toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert browser.windowIcon().isNull() is False
    assert browser.back_action.icon().isNull() is False
    assert browser.forward_action.icon().isNull() is False
    assert browser.reload_action.icon().isNull() is False
    assert browser.home_action.icon().isNull() is False
    assert browser.back_action.toolTip() == "Back"
    assert browser.home_action.toolTip() == "Home"
    assert browser.toc_tree.wordWrap() is True
    assert browser.toc_tree.indentation() == 16
    assert browser.toc_tree.columnCount() == 1
    start_here_color = browser.section_icon_color("Start Here")
    guides_color = browser.section_icon_color("User Guides")
    assert start_here_color.isValid() is True
    assert guides_color.isValid() is True
    assert len({start_here_color.name(), guides_color.name()}) == 2
    start_badge_bg, start_badge_border, start_badge_text = browser.section_badge_colors("Start Here")
    guides_badge_bg, guides_badge_border, guides_badge_text = browser.section_badge_colors("User Guides")
    assert start_badge_bg.isValid() is True
    assert guides_badge_bg.isValid() is True
    assert len({start_badge_bg.name(), guides_badge_bg.name()}) == 2
    assert len({start_badge_border.name(), guides_badge_border.name()}) == 2
    assert help_browser_module._contrast_ratio(start_badge_text, start_badge_bg) >= 4.5
    assert help_browser_module._contrast_ratio(guides_badge_text, guides_badge_bg) >= 4.5
    assert browser.section_icon("Start Here").isNull() is False
    assert browser.section_icon("User Guides").isNull() is False
    assert browser.section_icon("Desktop UI").isNull() is False
    section_item = browser.toc_tree.topLevelItem(0)
    assert section_item is not None
    assert browser.section_expand_progress(section_item.text(0)) == 1.0
    home_html, base_url = browser.browser.html_calls[-1]
    assert "ActionShellScript Help" in home_html
    assert desktop_asset_path(DesktopAsset.CODERDAWG_LOGO).as_uri() in home_html
    assert 'class="hero-logo"' in home_html
    assert 'class="quick-links"' in home_html
    assert "quick-link-card " in home_html
    assert 'class="quick-link-card guide' in home_html
    assert 'class="quick-link-card reference' in home_html
    assert 'class="quick-link-icon"' in home_html
    assert 'class="quick-link-hint"' in home_html
    assert "Begin with the project overview and launch commands." in home_html
    assert "See how to open and inspect" in home_html
    assert "Reference the desktop table editing helpers." in home_html
    assert "&#x1F4D6;" in home_html
    assert "&#x1F4D0;" in home_html
    assert "Architecture" not in home_html
    assert home_html.find("Pixel Inspector Guide") < home_html.find("Desktop Table API")
    assert "accent-callout" in home_html
    assert "user/open_script_guide.md#what-ass-open-script-does" in home_html
    assert "user/struct_and_dll_quickstart.md#what-you-can-write" in home_html
    assert "user/structs_and_dlls.md#monitor-info-wrapper-path" in home_html
    assert "user/struct_layout_contract.md#abi-notes" in home_html
    assert "../samples/README.md#monitor-info-wrapper-demo" in home_html
    assert "../samples/README.md#readfile-demo" in home_html
    assert "../samples/README.md#date-and-time-demo" in home_html
    assert "../samples/README.md#enum-examples-demo" in home_html
    assert "user/pixel_inspector_guide.md#main-controls" in home_html
    assert "Exclude main window during recording" in home_html
    assert "apps/desktop/table_api/README.md" in home_html
    assert base_url.endswith("/docs/")
    assert len(browser._topics) == 20
    assert browser.topic_count_label.text() == f"{len(browser._topics)} topics available"
    assert browser.toc_tree.topLevelItemCount() == 3

    topic_titles = {topic.title for topic in browser._topics}
    assert {
        "ASS CLI Quickstart",
        "ASS CLI Spec",
        "Builtin Coverage Map",
        "Desktop Table API",
        "Language Reference",
        "Struct and DLL Quickstart",
        "Structs and DLL Interop",
        "Struct Layout Contract",
        "Monitor Info Wrapper Demo",
        "ReadFile Demo",
        "Date and Time Demo",
        "Enum Examples Demo",
        "String Helper Examples",
    }.issubset(topic_titles)
    assert all(topic.section != "Architecture" for topic in browser._topics)

    home_item = browser._item_by_path[(repo_root / "docs" / "index.md").resolve()]
    gui_preference_item = browser._item_by_path[gui_preference_spec_path]
    table_api_item = browser._item_by_path[table_api_path]
    browser.search_box.setText("single-cell shortcut capture")
    assert browser.topic_count_label.text().startswith("1 of ")
    assert browser.toc_tree.itemDelegate() is browser._toc_delegate
    assert table_api_item.isHidden() is False
    assert table_api_item.parent().text(0) == "Desktop UI"
    assert "single-cell shortcut capture" in str(table_api_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(table_api_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("consistent command shape")
    ass_cli_spec_item = browser._item_by_path[ass_cli_spec_path]
    assert ass_cli_spec_item.isHidden() is False
    assert ass_cli_spec_item.parent().text(0) == "User Guides"
    assert "consistent command shape" in str(ass_cli_spec_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(ass_cli_spec_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("wrapper guidance")
    monitor_info_flow_item = _topic_item(browser, "Monitor Info Wrapper Demo")
    assert monitor_info_flow_item.isHidden() is False
    assert monitor_info_flow_item.parent().text(0) == "User Guides"
    assert int(monitor_info_flow_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("readfile")
    readfile_flow_item = _topic_item(browser, "ReadFile Demo")
    assert readfile_flow_item.isHidden() is False
    assert readfile_flow_item.parent().text(0) == "User Guides"
    assert "readfile" in str(readfile_flow_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(readfile_flow_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("dateadd")
    date_time_flow_item = _topic_item(browser, "Date and Time Demo")
    assert date_time_flow_item.isHidden() is False
    assert date_time_flow_item.parent().text(0) == "User Guides"
    assert "parsedatetime" in str(date_time_flow_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(date_time_flow_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("namespace-qualified members")
    enum_examples_flow_item = _topic_item(browser, "Enum Examples Demo")
    assert enum_examples_flow_item.isHidden() is False
    assert enum_examples_flow_item.parent().text(0) == "User Guides"
    assert "namespace-qualified members" in str(enum_examples_flow_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(enum_examples_flow_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("getmonitorinfoex exception")
    struct_layout_contract_item = browser._item_by_path[struct_layout_contract_path]
    assert struct_layout_contract_item.isHidden() is False
    assert struct_layout_contract_item.parent().text(0) == "User Guides"
    assert int(struct_layout_contract_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("working example first")
    struct_quickstart_item = browser._item_by_path[struct_quickstart_path]
    assert struct_quickstart_item.isHidden() is False
    assert struct_quickstart_item.parent().text(0) == "User Guides"
    assert int(struct_quickstart_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("windows wrapper surface")
    structs_and_dlls_item = browser._item_by_path[structs_and_dlls_path]
    assert structs_and_dlls_item.isHidden() is False
    assert structs_and_dlls_item.parent().text(0) == "User Guides"
    assert int(structs_and_dlls_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("runtime implementation status")
    builtin_coverage_item = browser._item_by_path[builtin_coverage_path]
    assert builtin_coverage_item.isHidden() is False
    assert builtin_coverage_item.parent().text(0) == "User Guides"
    assert "runtime implementation status" in str(builtin_coverage_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert int(builtin_coverage_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("workspace tab visibility controls")
    assert home_item.isHidden() is False
    assert "workspace tab visibility controls" in str(home_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert home_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) > 0
    browser.search_box.setText("enum examples demo")
    assert home_item.isHidden() is False
    assert int(home_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    browser.search_box.setText("exclude main window during recording")
    assert gui_preference_item.isHidden() is False
    assert gui_preference_item.parent().text(0) == "User Guides"
    assert "recording exclusion" in str(gui_preference_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE)).casefold()
    assert "status and document summaries" in browser._topic_by_path[gui_preference_spec_path].search_text
    assert int(gui_preference_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0
    assert browser._topic_by_title("ReadFile Demo").path == samples_readme_path
    assert browser._topic_by_title("Date and Time Demo").path == date_time_demo_path
    assert browser._topic_by_title("Enum Examples Demo").path == enum_examples_demo_path
    styles = help_browser_module._theme_accent_styles(browser.toc_tree.palette(), selected=False)
    rendered_snippet = browser._toc_delegate._build_html(
        home_item.text(0),
        styles=styles,
        subtitle=str(home_item.data(0, help_browser_module.HelpTopicDelegate.SUBTITLE_ROLE) or ""),
        match_count=int(home_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0),
    )
    assert "match-count-badge" in rendered_snippet
    assert "match-term" in rendered_snippet
    generate_item = browser._item_by_path[
        (repo_root / "docs" / "user" / "generate_script_guide.md").resolve()
    ]
    assert generate_item.isHidden() is True

    browser.toc_tree.collapseItem(section_item)
    QTest.qWait(220)
    app.processEvents()
    assert browser.section_expand_progress(section_item.text(0)) == 0.0
    assert section_item.isExpanded() is False

    browser.toc_tree.expandItem(section_item)
    QTest.qWait(220)
    app.processEvents()
    assert browser.section_expand_progress(section_item.text(0)) == 1.0
    assert section_item.isExpanded() is True

    browser.search_box.setFocus()
    QTest.keyClick(browser.search_box, Qt.Key.Key_Down)
    assert browser.toc_tree.currentItem() is home_item

    html_call_count = len(browser.browser.html_calls)
    QTest.keyClick(browser.search_box, Qt.Key.Key_Return)
    assert len(browser.browser.html_calls) > html_call_count

    browser.search_box.setText("definitely-not-a-doc-term")
    empty_html, _ = browser.browser.html_calls[-1]
    assert "No help topics found" in empty_html
    assert "accent-callout" in empty_html

    browser.open_at_section(
        repo_root / "docs" / "user" / "pixel_inspector_guide.md",
        "main-controls",
        anchor_text="Main Controls",
    )
    section_html, _ = browser.browser.html_calls[-1]
    assert 'id="main-controls"' in section_html
    assert "Main Controls" in section_html

    browser._open_topic_by_path(
        (repo_root / "docs" / "user" / "generate_script_guide.md").resolve()
    )
    assert browser._pending_anchor_id == "what-ass-generate-does"
    assert browser._pending_anchor_text == "What `ass-generate` Does"
    browser._open_topic(browser._topic_by_title("ReadFile Demo"))
    assert browser._pending_anchor_id == "readfile-demo"
    assert browser._pending_anchor_text == "ReadFile Demo"
    browser._open_topic(browser._topic_by_title("Date and Time Demo"))
    assert browser._pending_anchor_id == "date-and-time-demo"
    assert browser._pending_anchor_text == "Date and Time Demo"
    browser._open_topic(browser._topic_by_title("Enum Examples Demo"))
    assert browser._pending_anchor_id == "enum-examples-demo"
    assert browser._pending_anchor_text == "Enum Examples Demo"

    browser.close()
    assert browser.browser.stop_calls == 1


def test_help_browser_indexes_string_runtime_topics(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    language_reference_path = (repo_root / "docs" / "user" / "language_reference.md").resolve()
    string_examples_path = (repo_root / "docs" / "user" / "string_helpers_examples.md").resolve()

    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()

    string_topic = browser._topic_by_path[string_examples_path]
    language_topic = browser._topic_by_path[language_reference_path]

    assert string_topic.title == "String Helper Examples"
    assert "stringinstr" in string_topic.search_text
    assert "@scriptname" in language_topic.search_text
    assert "@scriptdirectory" in language_topic.search_text
    assert "@workingdir" in language_topic.search_text
    assert "@crlf" in language_topic.search_text

    string_examples_item = browser._item_by_path[string_examples_path]
    language_reference_item = browser._item_by_path[language_reference_path]

    browser.search_box.setText("StringInStr")
    assert string_examples_item.isHidden() is False
    assert string_examples_item.parent().text(0) == "User Guides"
    assert int(string_examples_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0

    browser.search_box.setText("@ScriptDirectory")
    assert language_reference_item.isHidden() is False
    assert language_reference_item.parent().text(0) == "User Guides"
    assert int(language_reference_item.data(0, help_browser_module.HelpTopicDelegate.MATCH_COUNT_ROLE) or 0) > 0

    browser.open_document(string_examples_path)
    html, _ = browser.browser.html_calls[-1]
    assert "StringInStr" in html
    assert "StringCompare" in html

    browser.close()


def test_help_browser_refuses_unsupported_docs_suffix(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()
    unsupported_path = (repo_root / "docs" / "user" / "blocked.txt").resolve()

    assert browser.open_document(unsupported_path) is False
    assert browser.browser.html_calls[-1][0].find("ActionShellScript Help") != -1

    browser.close()


def test_help_browser_clicking_readfile_demo_row_opens_readme_anchor(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()

    class FakePage:
        def __init__(self) -> None:
            self.scripts: list[str] = []

        def runJavaScript(self, script: str) -> None:  # noqa: N802
            self.scripts.append(script)

    fake_page = FakePage()
    browser.browser.page = lambda: fake_page  # type: ignore[assignment]

    readfile_item = _topic_item(browser, "ReadFile Demo")
    browser.show()
    app.processEvents()
    browser.toc_tree.scrollToItem(readfile_item)
    app.processEvents()
    rect = browser.toc_tree.visualItemRect(readfile_item)
    QTest.mouseClick(browser.toc_tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    app.processEvents()

    assert browser.toc_tree.currentItem() is not None
    assert browser.toc_tree.currentItem().text(0) == "ReadFile Demo"
    assert browser._pending_anchor_id == "readfile-demo"
    assert browser._pending_anchor_text == "ReadFile Demo"
    assert browser.browser.html_calls[-1][1].endswith("/samples/")
    assert "ReadFile Demo" in browser.browser.html_calls[-1][0]
    assert "read_file_demo.txt" in browser.browser.html_calls[-1][0].casefold()

    browser._handle_browser_load_finished(True)

    assert fake_page.scripts
    assert "readfile-demo" in fake_page.scripts[-1]
    assert "ReadFile Demo" in fake_page.scripts[-1]

    browser.close()


def test_help_browser_clicking_date_time_demo_row_opens_readme_anchor(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()

    class FakePage:
        def __init__(self) -> None:
            self.scripts: list[str] = []

        def runJavaScript(self, script: str) -> None:  # noqa: N802
            self.scripts.append(script)

    fake_page = FakePage()
    browser.browser.page = lambda: fake_page  # type: ignore[assignment]

    date_time_item = _topic_item(browser, "Date and Time Demo")
    browser.show()
    app.processEvents()
    browser.toc_tree.scrollToItem(date_time_item)
    app.processEvents()
    rect = browser.toc_tree.visualItemRect(date_time_item)
    QTest.mouseClick(browser.toc_tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    app.processEvents()

    assert browser.toc_tree.currentItem() is not None
    assert browser.toc_tree.currentItem().text(0) == "Date and Time Demo"
    assert browser._pending_anchor_id == "date-and-time-demo"
    assert browser._pending_anchor_text == "Date and Time Demo"
    assert browser.browser.html_calls[-1][1].endswith("/samples/")
    assert "Date and Time Demo" in browser.browser.html_calls[-1][0]
    assert "date_time_demo.ass" in browser.browser.html_calls[-1][0].casefold()

    browser._handle_browser_load_finished(True)

    assert fake_page.scripts
    assert "date-and-time-demo" in fake_page.scripts[-1]
    assert "Date and Time Demo" in fake_page.scripts[-1]

    browser.close()


def test_help_browser_clicking_enum_examples_demo_row_opens_readme_anchor(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()

    class FakePage:
        def __init__(self) -> None:
            self.scripts: list[str] = []

        def runJavaScript(self, script: str) -> None:  # noqa: N802
            self.scripts.append(script)

    fake_page = FakePage()
    browser.browser.page = lambda: fake_page  # type: ignore[assignment]

    enum_examples_item = _topic_item(browser, "Enum Examples Demo")
    browser.show()
    app.processEvents()
    browser.toc_tree.scrollToItem(enum_examples_item)
    app.processEvents()
    rect = browser.toc_tree.visualItemRect(enum_examples_item)
    QTest.mouseClick(browser.toc_tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    app.processEvents()

    assert browser.toc_tree.currentItem() is not None
    assert browser.toc_tree.currentItem().text(0) == "Enum Examples Demo"
    assert browser._pending_anchor_id == "enum-examples-demo"
    assert browser._pending_anchor_text == "Enum Examples Demo"
    assert browser.browser.html_calls[-1][1].endswith("/samples/")
    assert "Enum Examples Demo" in browser.browser.html_calls[-1][0]
    assert "enum_examples_demo.ass" in browser.browser.html_calls[-1][0].casefold()

    browser._handle_browser_load_finished(True)

    assert fake_page.scripts
    assert "enum-examples-demo" in fake_page.scripts[-1]
    assert "Enum Examples Demo" in fake_page.scripts[-1]

    browser.close()


def test_help_browser_defers_local_link_navigation(monkeypatch) -> None:
    scheduled: list[tuple[int, object]] = []

    def fake_single_shot(delay: int, callback) -> None:
        scheduled.append((delay, callback))

    class DummyOwner:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, str | None]] = []

        def open_document(self, path: Path, *, anchor_id: str | None = None, anchor_text: str | None = None) -> bool:
            self.calls.append((path, anchor_id))
            return True

    monkeypatch.setattr(help_browser_module.QTimer, "singleShot", fake_single_shot)

    fake_page = type("FakePage", (), {})()
    fake_page._owner = DummyOwner()

    target_path = docs_index_path().resolve()
    help_browser_module._HelpBrowserPage._open_local_link(fake_page, target_path, "start-here")

    assert scheduled and scheduled[0][0] == 0
    assert fake_page._owner.calls == []
    scheduled[0][1]()
    assert fake_page._owner.calls == [(target_path, "start-here")]


def test_help_browser_only_opens_safe_external_schemes(monkeypatch) -> None:
    opened_urls: list[str] = []

    def fake_open_url(url: QUrl) -> bool:
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(help_browser_module.QDesktopServices, "openUrl", fake_open_url)

    dummy_self = type("DummyPage", (), {})()
    navigation_type = help_browser_module.QWebEnginePage.NavigationType.NavigationTypeLinkClicked

    assert (
        help_browser_module._HelpBrowserPage.acceptNavigationRequest(
            dummy_self,
            QUrl("https://example.com/docs"),
            navigation_type,
            True,
        )
        is False
    )
    assert opened_urls == ["https://example.com/docs"]

    opened_urls.clear()
    assert (
        help_browser_module._HelpBrowserPage.acceptNavigationRequest(
            dummy_self,
            QUrl("javascript:alert(1)"),
            navigation_type,
            True,
        )
        is False
    )
    assert opened_urls == []


def test_help_browser_opens_repo_local_docs_link(monkeypatch) -> None:
    monkeypatch.setattr(help_browser_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())

    browser = ActionShellScriptHelpBrowser()
    repo_root = Path(__file__).resolve().parents[2]
    table_api_path = (repo_root / "apps" / "desktop" / "table_api" / "README.md").resolve()

    assert browser.open_document(table_api_path) is True

    html, base_url = browser.browser.html_calls[-1]
    assert "PySide6 Table API" in html
    assert "shortcut editor" in html.casefold()
    assert base_url.endswith("/apps/desktop/table_api/")
