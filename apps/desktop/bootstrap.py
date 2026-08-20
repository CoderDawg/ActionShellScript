from __future__ import annotations

import os
import sys
from pathlib import Path

from apps.desktop.icon_assets import DesktopAsset, desktop_asset_path


DESKTOP_COMBO_BOX_STYLE = """
/* ActionShellScript combo box readability fix */
QComboBox {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #8a8a8a;
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 22px;
}
QComboBox:hover {
    border-color: #5a646e;
}
QComboBox:focus {
    border-color: #1565c0;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
}
QComboBox::down-arrow {
    image: url(__COMBO_ARROW__);
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #202020;
    selection-background-color: #dce9f8;
    selection-color: #202020;
    outline: 0;
}
"""


def ensure_repo_root_on_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)
    return repo_root


def ensure_qt_font_directory() -> None:
    platform = os.environ.get("QT_QPA_PLATFORM", "").strip().casefold()
    if platform not in {"offscreen", "minimal"}:
        return
    if os.environ.get("QT_QPA_FONTDIR"):
        return

    windows_fonts = Path(r"C:\Windows\Fonts")
    if windows_fonts.exists():
        os.environ["QT_QPA_FONTDIR"] = str(windows_fonts)


def qt_message_handler(_mode, context, message) -> None:
    if (
        getattr(context, "category", "") == "qt.qpa.window"
        and "SetProcessDpiAwarenessContext() failed: Access is denied." in message
    ):
        return
    if message.startswith("QFont::setPointSize: Point size <= 0"):
        return
    print(message, file=sys.stderr)


def install_qt_message_filter() -> None:
    try:
        from PySide6.QtCore import qInstallMessageHandler
    except Exception:
        return

    qInstallMessageHandler(qt_message_handler)


def apply_desktop_widget_styles() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        return

    app = QApplication.instance()
    if app is None:
        return

    style_sheet = app.styleSheet()
    if "ActionShellScript combo box readability fix" in style_sheet:
        return

    arrow_path = desktop_asset_path(DesktopAsset.COMBO_BOX_ARROW).as_posix()
    combined_style_sheet = style_sheet.rstrip()
    if combined_style_sheet:
        combined_style_sheet += "\n\n"
    combined_style_sheet += DESKTOP_COMBO_BOX_STYLE.replace("__COMBO_ARROW__", arrow_path).strip()
    app.setStyleSheet(combined_style_sheet)
