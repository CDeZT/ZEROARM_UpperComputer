"""Application composition and process entry point."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from zeroarm_desktop.cli import LaunchOptions, parse_launch_options
from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.version import __version__


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_qt_application(
    argv: Sequence[str],
    *,
    options: LaunchOptions | None = None,
) -> tuple[QApplication, MainWindow]:
    """Create the Qt application and its root window."""
    existing_app = QApplication.instance()
    if existing_app is None:
        app = QApplication(list(argv))
    elif isinstance(existing_app, QApplication):
        app = existing_app
    else:
        raise RuntimeError("A non-GUI Qt application already exists")

    app.setApplicationName("ZeroArm Desktop")
    app.setApplicationDisplayName("ZeroArm Desktop")
    app.setOrganizationName("ZeroArm")
    app.setApplicationVersion(__version__)

    window = MainWindow(launch_options=options)
    return app, window


def main(argv: Sequence[str] | None = None) -> int:
    """Run ZeroArm Desktop and return the Qt process exit code."""
    raw = list(sys.argv[1:] if argv is None else argv)
    options = parse_launch_options(raw)
    if options.show_version:
        print(f"ZeroArm Desktop {__version__}")
        return 0
    configure_logging(options.log_level)
    app, window = create_qt_application(
        sys.argv if argv is None else ["zeroarm-desktop", *raw],
        options=options,
    )
    if options.diagnostics:
        window.navigate("diagnostics")
    elif options.mock:
        window.navigate("connection")
    window.show()
    return app.exec()
