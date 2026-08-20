from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from apps.desktop.bootstrap import (
    apply_desktop_widget_styles,
    ensure_qt_font_directory,
    ensure_repo_root_on_path,
    install_qt_message_filter,
)
from apps.desktop.icon_assets import DesktopAsset, desktop_asset_path
from apps.desktop.documentation_messages import (
    docs_index_path,
    documentation_unavailable_message,
    documentation_unavailable_status,
    system_viewer_fallback_status,
)

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox


ensure_repo_root_on_path()


def _emit_status(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _open_docs_fallback(target_path: Path, error: Exception) -> int:
    target_url = QUrl.fromLocalFile(str(target_path))
    if QDesktopServices.openUrl(target_url):
        _emit_status(system_viewer_fallback_status())
        return 0

    _emit_status(documentation_unavailable_status())
    QMessageBox.warning(
        None,
        "Documentation Unavailable",
        documentation_unavailable_message(error, target_path),
    )
    return 1


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-help",
        description="Launch the ActionShellScript help browser.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional docs file to open on startup.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    ensure_qt_font_directory()

    install_qt_message_filter()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ActionShellScript Help")
    app.setOrganizationName("ActionShellScript")
    app.setWindowIcon(QIcon(str(desktop_asset_path(DesktopAsset.FROG_ICON_ICO))))
    apply_desktop_widget_styles()

    target_path = Path(args.path).expanduser().resolve() if args.path else docs_index_path()

    try:
        from apps.desktop.help_browser import ActionShellScriptHelpBrowser

        browser = ActionShellScriptHelpBrowser()
        if args.path and not browser.open_document(target_path):
            print(f"Unable to open help document: {target_path}", file=sys.stderr)
            return 2
        browser.present()
        return app.exec()
    except Exception as exc:  # pragma: no cover - import/runtime environment failure
        return _open_docs_fallback(target_path, exc)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
