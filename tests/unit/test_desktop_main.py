from __future__ import annotations

import os
from types import SimpleNamespace
from pathlib import Path

from PySide6.QtWidgets import QApplication

from apps.desktop import bootstrap as desktop_bootstrap
from apps.desktop import icon_assets as desktop_icon_assets
from apps.desktop import main as desktop_main
import apps.desktop.window as desktop_window_module
from apps import shared_assets as shared_assets_module
from application.persistence.desktop_settings_service import DesktopSettingsService
from application.script_document_language_service import ScriptDocumentLanguageService
from application.script_document_service import ScriptDocumentService
from editor.language_services.formatting_service import FormattingService
from infrastructure.persistence.script_document_file_store import ScriptDocumentFileStore


def test_qt_message_handler_suppresses_known_dpi_warning(capsys) -> None:
    context = SimpleNamespace(category="qt.qpa.window")

    desktop_bootstrap.qt_message_handler(
        None,
        context,
        "SetProcessDpiAwarenessContext() failed: Access is denied.",
    )

    captured = capsys.readouterr()
    assert captured.err == ""


def test_qt_message_handler_preserves_other_messages(capsys) -> None:
    context = SimpleNamespace(category="qt.qpa.window")

    desktop_bootstrap.qt_message_handler(None, context, "Some other Qt warning")

    captured = capsys.readouterr()
    assert captured.err.strip() == "Some other Qt warning"


def test_qt_message_handler_suppresses_point_size_warning(capsys) -> None:
    context = SimpleNamespace(category="qt.qpa.window")

    desktop_bootstrap.qt_message_handler(
        None,
        context,
        "QFont::setPointSize: Point size <= 0 (-1), must be greater than 0",
    )

    captured = capsys.readouterr()
    assert captured.err == ""


def test_ensure_qt_font_directory_sets_windows_fonts_for_offscreen(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)
    monkeypatch.setattr(desktop_bootstrap.Path, "exists", lambda self: True)

    desktop_bootstrap.ensure_qt_font_directory()

    assert os.environ["QT_QPA_FONTDIR"] == r"C:\Windows\Fonts"


def test_ensure_qt_font_directory_preserves_existing_value(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_QPA_FONTDIR", r"D:\Fonts")

    desktop_bootstrap.ensure_qt_font_directory()

    assert os.environ["QT_QPA_FONTDIR"] == r"D:\Fonts"


def test_desktop_asset_helpers_point_into_shared_asset_directory() -> None:
    asset_dir = Path(desktop_icon_assets.__file__).resolve().parent / "assets"
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON) == asset_dir / desktop_icon_assets.DesktopAsset.FROG_ICON.value
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON_ICO) == asset_dir / desktop_icon_assets.DesktopAsset.FROG_ICON_ICO.value
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.COMBO_BOX_ARROW) == asset_dir / desktop_icon_assets.DesktopAsset.COMBO_BOX_ARROW.value


def test_desktop_asset_helpers_prefer_frozen_bundle_assets(monkeypatch, tmp_path) -> None:
    source_asset_dir = Path(desktop_icon_assets.__file__).resolve().parent / "assets"
    bundle_root = tmp_path / "bundle"
    bundle_asset_dir = bundle_root / "apps" / "desktop" / "assets"
    bundle_asset_dir.mkdir(parents=True)

    frog_name = desktop_icon_assets.DesktopAsset.FROG_ICON.value
    bundle_asset_path = bundle_asset_dir / frog_name
    bundle_asset_path.write_bytes((source_asset_dir / frog_name).read_bytes())

    frog_ico_name = desktop_icon_assets.DesktopAsset.FROG_ICON_ICO.value
    bundle_asset_ico_path = bundle_asset_dir / frog_ico_name
    bundle_asset_ico_path.write_bytes((source_asset_dir / frog_ico_name).read_bytes())

    monkeypatch.setattr(shared_assets_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "_MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "executable", str(bundle_root / "ass-gui.exe"), raising=False)

    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON_ICO) == bundle_asset_ico_path
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON) == bundle_asset_path


def test_desktop_asset_helpers_handle_nested_frozen_bundle_assets(monkeypatch, tmp_path) -> None:
    source_asset_dir = Path(desktop_icon_assets.__file__).resolve().parent / "assets"
    bundle_root = tmp_path / "bundle"
    bundle_asset_dir = bundle_root / "apps" / "desktop" / "assets"
    bundle_asset_dir.mkdir(parents=True)

    frog_name = desktop_icon_assets.DesktopAsset.FROG_ICON.value
    nested_asset_dir = bundle_asset_dir / frog_name
    nested_asset_dir.mkdir()
    nested_asset_path = nested_asset_dir / frog_name
    nested_asset_path.write_bytes((source_asset_dir / frog_name).read_bytes())

    frog_ico_name = desktop_icon_assets.DesktopAsset.FROG_ICON_ICO.value
    nested_asset_ico_dir = bundle_asset_dir / frog_ico_name
    nested_asset_ico_dir.mkdir()
    nested_asset_ico_path = nested_asset_ico_dir / frog_ico_name
    nested_asset_ico_path.write_bytes((source_asset_dir / frog_ico_name).read_bytes())

    monkeypatch.setattr(shared_assets_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "_MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "executable", str(bundle_root / "ass-gui.exe"), raising=False)

    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON_ICO) == nested_asset_ico_path
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON) == nested_asset_path


def test_desktop_asset_helpers_prefer_explicit_bundle_root_env_var(monkeypatch, tmp_path) -> None:
    source_asset_dir = Path(desktop_icon_assets.__file__).resolve().parent / "assets"
    asset_root = tmp_path / "explicit-assets"
    asset_root.mkdir(parents=True)

    frog_name = desktop_icon_assets.DesktopAsset.FROG_ICON.value
    explicit_asset_path = asset_root / frog_name
    explicit_asset_path.write_bytes((source_asset_dir / frog_name).read_bytes())

    frog_ico_name = desktop_icon_assets.DesktopAsset.FROG_ICON_ICO.value
    explicit_asset_ico_path = asset_root / frog_ico_name
    explicit_asset_ico_path.write_bytes((source_asset_dir / frog_ico_name).read_bytes())

    monkeypatch.setenv("ASS_DESKTOP_ASSET_ROOT", str(asset_root))

    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON_ICO) == explicit_asset_ico_path
    assert desktop_icon_assets.desktop_asset_path(desktop_icon_assets.DesktopAsset.FROG_ICON) == explicit_asset_path


def _smoke_services() -> desktop_window_module.DesktopServices:
    return desktop_window_module.DesktopServices(
        document_service=ScriptDocumentService(),
        language_service=ScriptDocumentLanguageService(),
        formatting_service=FormattingService(),
        document_store=ScriptDocumentFileStore(),
    )


def _smoke_window(tmp_path: Path, monkeypatch) -> desktop_window_module.ActionShellScriptDesktopWindow:
    monkeypatch.setattr(
        desktop_window_module,
        "DesktopSettingsService",
        lambda: DesktopSettingsService(config_dir=tmp_path),
    )
    return desktop_window_module.ActionShellScriptDesktopWindow(services=_smoke_services())


def test_desktop_source_smoke_loads_frog_icon_at_runtime(monkeypatch, tmp_path) -> None:
    app = QApplication.instance() or QApplication([])

    desktop_main._configure_application(app)
    window = _smoke_window(tmp_path, monkeypatch)

    try:
        assert app.windowIcon().isNull() is False
        assert window.windowIcon().isNull() is False
        assert window._about_frog_pixmap().isNull() is False
    finally:
        window.close()


def test_desktop_frozen_smoke_loads_frog_icon_from_ass_gui_exe_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    source_asset_dir = Path(desktop_icon_assets.__file__).resolve().parent / "assets"
    bundle_root = tmp_path / "bundle"
    bundle_asset_dir = bundle_root / "apps" / "desktop" / "assets"
    bundle_asset_dir.mkdir(parents=True)

    for asset_name in (
        desktop_icon_assets.DesktopAsset.FROG_ICON.value,
        desktop_icon_assets.DesktopAsset.FROG_ICON_ICO.value,
    ):
        (bundle_asset_dir / asset_name).write_bytes((source_asset_dir / asset_name).read_bytes())

    monkeypatch.setattr(shared_assets_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "_MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setattr(shared_assets_module.sys, "executable", str(bundle_root / "ass-gui.exe"), raising=False)

    app = QApplication.instance() or QApplication([])

    desktop_main._configure_application(app)
    window = _smoke_window(tmp_path, monkeypatch)

    try:
        assert app.windowIcon().isNull() is False
        assert window.windowIcon().isNull() is False
        assert window._about_frog_pixmap().isNull() is False
    finally:
        window.close()
