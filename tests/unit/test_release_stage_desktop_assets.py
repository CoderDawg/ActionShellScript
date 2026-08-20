from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import apps.desktop.help_browser as help_browser_module
import apps.desktop.icon_assets as desktop_icon_assets
import apps.shared_assets as shared_assets_module
from apps.desktop.help_browser import ActionShellScriptHelpBrowser


ROOT = Path(__file__).resolve().parents[2]


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _resolve_pwsh() -> str | None:
    for candidate in ("pwsh", "powershell"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def _build_release_stage(tmp_path: Path) -> Path:
    pwsh = _resolve_pwsh()
    if pwsh is None:
        pytest.skip("PowerShell is required to stage the release tree.")

    stage_root = ROOT / "tmp_pytest_release_stage" / f"{tmp_path.name}_{os.urandom(4).hex()}"
    result = subprocess.run(
        [
            pwsh,
            "-File",
            str(ROOT / "packaging" / "scripts" / "build_release.ps1"),
            "-Stage",
            "-PyInstaller",
            "-Clean",
            "-StageRoot",
            str(stage_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    return stage_root


def test_release_stage_pyinstaller_tree_contains_frog_assets_before_launch(
    tmp_path: Path,
) -> None:
    stage_root = _build_release_stage(tmp_path)
    try:
        dist_root = stage_root / "dist" / "ass-gui"
        stage_docs_internal = stage_root / "docs" / "internal"
        bundled_docs_internal = dist_root / "_internal" / "docs" / "internal"
        internal_assets = dist_root / "_internal" / "apps" / "desktop" / "assets"
        frog_png = internal_assets / "retro_pixelated_teal_smiling_frog.png"
        frog_ico = internal_assets / "retro_pixelated_teal_smiling_frog.ico"
        ass_gui_exe = dist_root / "ass-gui.exe"

        assert ass_gui_exe.is_file()
        assert not stage_docs_internal.exists()
        assert not bundled_docs_internal.exists()
        assert frog_png.is_file()
        assert frog_ico.is_file()
        assert frog_png.read_bytes() == (ROOT / "apps" / "desktop" / "assets" / frog_png.name).read_bytes()
        assert frog_ico.read_bytes() == (ROOT / "apps" / "desktop" / "assets" / frog_ico.name).read_bytes()
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


def test_release_stage_pyinstaller_tree_strips_qtwebengine_debug_payloads(
    tmp_path: Path,
) -> None:
    stage_root = _build_release_stage(tmp_path)
    try:
        dist_root = stage_root / "dist"
        debug_payload_names = {
            "qtwebengine_devtools_resources.debug.pak",
            "qtwebengine_resources.debug.pak",
            "qtwebengine_resources_200p.debug.pak",
            "qtwebengine_resources_100p.debug.pak",
            "v8_context_snapshot.debug.bin",
        }
        leaked_payloads = sorted(
            path.relative_to(dist_root).as_posix()
            for path in dist_root.rglob("*")
            if path.is_file() and path.name in debug_payload_names
        )

        assert not leaked_payloads, f"Unexpected QtWebEngine debug payloads in staged dist: {leaked_payloads}"
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


class _FakeWebView(QWidget):
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

    def setHtml(self, html: str, base_url=None) -> None:  # noqa: N802
        self.html_calls.append((html, base_url.toString() if base_url is not None else None))

    def load(self, url) -> None:
        self.loaded_urls.append(url.toString())

    def back(self) -> None:
        self.back_calls += 1

    def forward(self) -> None:
        self.forward_calls += 1

    def reload(self) -> None:
        self.reload_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


def test_release_stage_ass_help_tree_contains_logo_and_home_page_resolves_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()
    stage_root = _build_release_stage(tmp_path)
    try:
        dist_root = stage_root / "dist" / "ass-help"
        stage_docs_internal = stage_root / "docs" / "internal"
        bundled_docs_internal = dist_root / "_internal" / "docs" / "internal"
        internal_assets = dist_root / "_internal" / "apps" / "desktop" / "assets"
        logo_path = internal_assets / desktop_icon_assets.DesktopAsset.CODERDAWG_LOGO.value
        ass_help_exe = dist_root / "ass-help.exe"

        assert ass_help_exe.is_file()
        assert not stage_docs_internal.exists()
        assert not bundled_docs_internal.exists()
        assert logo_path.is_file()
        assert logo_path.read_bytes() == (
            ROOT / "apps" / "desktop" / "assets" / logo_path.name
        ).read_bytes()

        monkeypatch.setattr(help_browser_module, "QWebEngineView", _FakeWebView)
        monkeypatch.setattr(help_browser_module, "_HelpBrowserPage", lambda owner: object())
        monkeypatch.setattr(shared_assets_module.sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            shared_assets_module.sys,
            "_MEIPASS",
            str(dist_root / "_internal"),
            raising=False,
        )
        monkeypatch.setattr(
            shared_assets_module.sys,
            "executable",
            str(ass_help_exe),
            raising=False,
        )

        browser = ActionShellScriptHelpBrowser()
        assert isinstance(browser.browser, _FakeWebView)
        assert browser.browser.html_calls

        home_html, _ = browser.browser.html_calls[-1]
        assert "ActionShellScript Help" in home_html
        assert 'class="hero-logo"' in home_html
        assert desktop_icon_assets.desktop_asset_path(
            desktop_icon_assets.DesktopAsset.CODERDAWG_LOGO
        ).resolve() == logo_path.resolve()
        assert logo_path.as_uri() in home_html
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
