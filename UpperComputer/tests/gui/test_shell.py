"""GUI shell navigation, theme, global safety, and shutdown tests."""

from pathlib import Path

from PySide6.QtWidgets import QFrame, QPushButton, QScrollArea, QWidget
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


def test_navigation_is_scrollable_at_minimum_window_height(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1280, 720)
    window.show()
    qtbot.wait(50)

    navigation = window.findChild(QScrollArea, "navigation_scroll")
    firmware = window.findChild(QPushButton, "nav_firmware")

    assert navigation is not None and firmware is not None
    navigation.ensureWidgetVisible(firmware)
    assert navigation.verticalScrollBar().maximum() > 0


def test_dashboard_uses_status_card_information_hierarchy(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.findChild(QFrame, "dashboard_state_card") is not None
    assert window.findChild(QFrame, "dashboard_fault_card") is not None


def test_dangerous_action_buttons_follow_mock_operator_readiness(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    preview = window.findChild(QPushButton, "preview_joint_button")
    home = window.findChild(QPushButton, "home_start_button")
    playback = window.findChild(QPushButton, "playback_start_button")
    validate = window.findChild(QPushButton, "trajectory_validate_button")
    assert None not in (preview, home, playback, validate)
    assert preview is not None and home is not None and playback is not None
    assert validate is not None

    assert not preview.isEnabled()
    assert not home.isEnabled()
    assert not playback.isEnabled()
    assert validate.isEnabled()

    window.connection_page.connect_button.click()
    assert not preview.isEnabled()
    window.mode_selector.setCurrentText("Operator")
    assert preview.isEnabled()
    assert home.isEnabled()
    assert playback.isEnabled()
    window.mode_selector.setCurrentText("Observer")
    assert not preview.isEnabled()


def test_action_buttons_expose_clear_visual_roles(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    send = window.findChild(QPushButton, "send_joint_button")
    home = window.findChild(QPushButton, "home_start_button")
    abort = window.findChild(QPushButton, "playback_abort_button")
    assert send is not None and home is not None and abort is not None

    assert send.property("role") == "primary"
    assert home.property("role") == "warning"
    assert abort.property("role") == "danger"
