"""Application startup and shutdown smoke tests."""

from PySide6.QtWidgets import QApplication, QLabel
from pytestqt.qtbot import QtBot

from zeroarm_desktop.bootstrap import create_qt_application
from zeroarm_desktop.gui.main_window import MainWindow
from zeroarm_desktop.version import __version__


def test_main_window_starts_without_hardware(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.show()

    assert window.isVisible()
    assert window.windowTitle() == f"ZeroArm Desktop {__version__}"
    status = window.findChild(QLabel, "connection_status")
    assert status is not None
    assert "尚未连接" in status.text()
    assert window.findChild(QLabel, "application_title") is not None
    assert window.findChild(QLabel, "active_navigation") is not None
    assert window.minimumWidth() >= 900

    window.close()
    assert not window.isVisible()


def test_bootstrap_configures_application(qapp: QApplication) -> None:
    app, window = create_qt_application(["zeroarm-desktop"])

    assert app is qapp
    assert app.applicationName() == "ZeroArm Desktop"
    assert app.organizationName() == "ZeroArm"
    assert isinstance(window, MainWindow)

    window.close()
