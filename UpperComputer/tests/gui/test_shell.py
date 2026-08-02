"""GUI shell navigation, theme, global safety, and shutdown tests."""

from pathlib import Path

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


def test_gui_shell_global_stop_is_visible_and_mock_scoped(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    stop = window.findChild(QPushButton, "global_stop_button")
    assert stop is not None
    assert stop.isEnabled()
    assert "非急停" in stop.text()


def test_gui_shell_calls_bounded_shutdown(qtbot: QtBot) -> None:
    calls: list[str] = []
    window = MainWindow(shutdown=lambda: calls.append("shutdown"))
    qtbot.addWidget(window)
    window.close()
    assert calls == ["shutdown"]
    assert window.findChild(QWidget, "page_connection") is not None


def test_gui_shell_surfaces_recording_start_failure(qtbot: QtBot, tmp_path: Path) -> None:
    invalid_parent = tmp_path / "not-a-directory"
    invalid_parent.write_text("occupied", encoding="utf-8")
    window = MainWindow(session_database_path=invalid_parent / "sessions.sqlite3")
    qtbot.addWidget(window)

    window.connection_page.connect_button.click()

    assert window.connection_page.session is not None
    assert "Recorder 不可用" in window.notification_center.text()
