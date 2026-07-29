"""Application composition and process entry point."""

from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from zeroarm_desktop.gui.shell import MainWindow


def create_qt_application(argv: Sequence[str]) -> tuple[QApplication, MainWindow]:
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

    window = MainWindow()
    return app, window


def main(argv: Sequence[str] | None = None) -> int:
    """Run ZeroArm Desktop and return the Qt process exit code."""
    import sys

    app, window = create_qt_application(sys.argv if argv is None else argv)
    window.show()
    return app.exec()
