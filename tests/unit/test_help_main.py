from __future__ import annotations

from pathlib import Path

import apps.desktop.help_browser as help_browser_module
from apps.desktop.documentation_messages import (
    documentation_unavailable_status,
    system_viewer_fallback_status,
)
from apps.desktop import help_main


class FakeIcon:
    def __init__(self, path: str) -> None:
        self.path = path

    def isNull(self) -> bool:  # noqa: N802
        return False


def test_help_main_launches_standalone_browser_and_opens_optional_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    opened_paths: list[Path] = []
    present_calls: list[int] = []

    class FakeHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            self.on_close = on_close

        def open_document(self, path: Path, *, anchor_id=None, anchor_text=None) -> bool:
            opened_paths.append(path)
            return True

        def present(self) -> None:
            present_calls.append(1)

    class FakeQApplication:
        _instance = None

        def __init__(self, argv) -> None:
            self.argv = list(argv)
            self.exec_calls = 0
            self.window_icon = None
            FakeQApplication._instance = self

        @staticmethod
        def instance():
            return FakeQApplication._instance

        def setApplicationName(self, name: str) -> None:  # noqa: N802
            self.application_name = name

        def setOrganizationName(self, name: str) -> None:  # noqa: N802
            self.organization_name = name

        def setWindowIcon(self, icon) -> None:  # noqa: N802
            self.window_icon = icon

        def processEvents(self) -> None:  # noqa: N802
            return None

        def exec(self) -> int:
            self.exec_calls += 1
            return 0

    monkeypatch.setattr(help_main, "ensure_qt_font_directory", lambda: None)
    monkeypatch.setattr(help_main, "install_qt_message_filter", lambda: None)
    monkeypatch.setattr(help_main, "apply_desktop_widget_styles", lambda: None)
    monkeypatch.setattr(help_main, "QApplication", FakeQApplication)
    monkeypatch.setattr(help_main, "QIcon", FakeIcon)
    monkeypatch.setattr(help_browser_module, "ActionShellScriptHelpBrowser", FakeHelpBrowser)

    docs_path = tmp_path / "standalone-help.md"
    docs_path.write_text("# Standalone Help\n", encoding="utf-8")

    exit_code = help_main.run([str(docs_path)])

    assert exit_code == 0
    assert opened_paths == [docs_path.resolve()]
    assert present_calls == [1]
    assert FakeQApplication._instance is not None
    assert FakeQApplication._instance.window_icon is not None
    assert FakeQApplication._instance.window_icon.isNull() is False
    assert FakeQApplication._instance.exec_calls == 1


def test_help_main_falls_back_to_external_docs_when_browser_creation_fails(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    opened_urls: list[str] = []
    docs_path = tmp_path / "shared-docs.md"
    docs_path.write_text("# Shared Docs\n", encoding="utf-8")

    class FakeQApplication:
        _instance = None

        def __init__(self, argv) -> None:
            self.argv = list(argv)
            self.exec_calls = 0
            self.window_icon = None
            FakeQApplication._instance = self

        @staticmethod
        def instance():
            return FakeQApplication._instance

        def setApplicationName(self, name: str) -> None:  # noqa: N802
            self.application_name = name

        def setOrganizationName(self, name: str) -> None:  # noqa: N802
            self.organization_name = name

        def setWindowIcon(self, icon) -> None:  # noqa: N802
            self.window_icon = icon

        def exec(self) -> int:
            self.exec_calls += 1
            return 0

    class BrokenHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            raise RuntimeError("web engine unavailable")

    def fake_open_url(url) -> bool:
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(help_main, "ensure_qt_font_directory", lambda: None)
    monkeypatch.setattr(help_main, "install_qt_message_filter", lambda: None)
    monkeypatch.setattr(help_main, "apply_desktop_widget_styles", lambda: None)
    monkeypatch.setattr(help_main, "QApplication", FakeQApplication)
    monkeypatch.setattr(help_main, "QIcon", FakeIcon)
    monkeypatch.setattr(help_browser_module, "ActionShellScriptHelpBrowser", BrokenHelpBrowser)
    monkeypatch.setattr(help_main.QDesktopServices, "openUrl", fake_open_url)
    monkeypatch.setattr(help_main, "docs_index_path", lambda: docs_path)

    exit_code = help_main.run([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(opened_urls) == 1
    assert opened_urls[0].endswith("/shared-docs.md")
    assert system_viewer_fallback_status() in captured.err
    assert FakeQApplication._instance is not None
    assert FakeQApplication._instance.exec_calls == 0


def test_help_main_fallback_warning_when_external_docs_cannot_open(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    warnings: list[tuple[str, str]] = []
    docs_path = tmp_path / "shared-docs.md"

    class FakeQApplication:
        _instance = None

        def __init__(self, argv) -> None:
            self.argv = list(argv)
            self.exec_calls = 0
            self.window_icon = None
            FakeQApplication._instance = self

        @staticmethod
        def instance():
            return FakeQApplication._instance

        def setApplicationName(self, name: str) -> None:  # noqa: N802
            self.application_name = name

        def setOrganizationName(self, name: str) -> None:  # noqa: N802
            self.organization_name = name

        def setWindowIcon(self, icon) -> None:  # noqa: N802
            self.window_icon = icon

        def exec(self) -> int:
            self.exec_calls += 1
            return 0

    class BrokenHelpBrowser:
        def __init__(self, *, on_close=None) -> None:
            raise RuntimeError("web engine unavailable")

    monkeypatch.setattr(help_main, "ensure_qt_font_directory", lambda: None)
    monkeypatch.setattr(help_main, "install_qt_message_filter", lambda: None)
    monkeypatch.setattr(help_main, "apply_desktop_widget_styles", lambda: None)
    monkeypatch.setattr(help_main, "QApplication", FakeQApplication)
    monkeypatch.setattr(help_main, "QIcon", FakeIcon)
    monkeypatch.setattr(help_browser_module, "ActionShellScriptHelpBrowser", BrokenHelpBrowser)
    monkeypatch.setattr(help_main.QDesktopServices, "openUrl", lambda url: False)
    monkeypatch.setattr(help_main, "docs_index_path", lambda: docs_path)
    monkeypatch.setattr(
        help_main.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    exit_code = help_main.run([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert warnings
    assert warnings[0][0] == "Documentation Unavailable"
    assert "web engine unavailable" in warnings[0][1]
    assert str(docs_path) in warnings[0][1]
    assert documentation_unavailable_status() in captured.err
