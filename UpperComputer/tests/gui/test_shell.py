"""GUI shell navigation, theme, global safety, and shutdown tests."""

from PySide6.QtWidgets import QPushButton, QWidget
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def test_gui_shell_navigates_real_page_stack(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    dashboard_button = window.findChild(QPushButton, "nav_dashboard")
    assert dashboard_button is not None
    dashboard_button.click()
    assert window.page_stack.currentWidget().objectName() == "page_dashboard"
    monitor_button = window.findChild(QPushButton, "nav_joint_monitor")
    assert monitor_button is not None
    monitor_button.click()
    assert window.page_stack.currentWidget().objectName() == "page_joint_monitor"


def test_gui_shell_global_stop_is_visible_and_disabled(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    stop = window.findChild(QPushButton, "global_stop_button")
    assert stop is not None
    assert not stop.isEnabled()
    assert "非急停" in stop.text()


def test_gui_shell_calls_bounded_shutdown(qtbot: QtBot) -> None:
    calls: list[str] = []
    window = MainWindow(shutdown=lambda: calls.append("shutdown"))
    qtbot.addWidget(window)
    window.close()
    assert calls == ["shutdown"]
    assert window.findChild(QWidget, "page_connection") is not None
