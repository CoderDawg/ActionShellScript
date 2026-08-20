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

try:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - import/runtime environment failure
    QApplication = None
    QIcon = None


ensure_repo_root_on_path()


def _configure_application(app) -> None:
    app.setApplicationName("ActionShellScript")
    app.setOrganizationName("ActionShellScript")
    app.setWindowIcon(QIcon(str(desktop_asset_path(DesktopAsset.FROG_ICON))))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ass-gui",
        description="Launch the ActionShellScript desktop frontend.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional .ass script document to open on startup.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    ensure_qt_font_directory()

    if QApplication is None or QIcon is None:
        print("Unable to start the desktop frontend: PySide6 is unavailable.", file=sys.stderr)
        return 1

    try:
        from apps.desktop.window import ActionShellScriptDesktopWindow
    except Exception as exc:  # pragma: no cover - import/runtime environment failure
        print(f"Unable to start the desktop frontend: {exc}", file=sys.stderr)
        return 1

    install_qt_message_filter()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    _configure_application(app)
    apply_desktop_widget_styles()

    window = ActionShellScriptDesktopWindow(
        initial_path=Path(args.path).expanduser().resolve() if args.path else None
    )
    window.show()
    return app.exec()


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
