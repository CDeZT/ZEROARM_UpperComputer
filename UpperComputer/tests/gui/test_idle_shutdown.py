"""Operator-idle auto-home, countdown, and controlled-shutdown tests."""

from typing import cast

from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.gui.viewmodels.idle_monitor import OPERATOR_IDLE_TIMEOUT_MS
from zeroarm_desktop.transport.mock import MockTransport


def _connected_operator(window: MainWindow) -> None:
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")


def _mock_device(window: MainWindow) -> MockTransport:
    session = window.connection_page.session
    assert session is not None
    return cast(MockTransport, session._transport)


def test_idle_monitor_counts_down_and_triggers_home(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    assert window.idle_monitor.active
    window.idle_monitor._timeout_ms = 300
    window.idle_monitor.note_activity()
    qtbot.waitUntil(lambda: "触发自动回零" in window.notification_center.text(), timeout=5000)
    session = window.connection_page.session
    assert session is not None
    qtbot.waitUntil(
        lambda: session.latest_snapshot is not None and session.latest_snapshot.homed_mask == 0x1D,
        timeout=5000,
    )


def test_polling_does_not_block_operator_idle_home(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    session = window.connection_page.session
    assert session is not None
    window.idle_monitor._timeout_ms = 300
    window.idle_monitor.note_activity()
    while window.idle_monitor._remaining_s() > 0:
        session.poll_once()
        qtbot.wait(50)
    qtbot.waitUntil(
        lambda: session.latest_snapshot is not None and session.latest_snapshot.homed_mask == 0x1D,
        timeout=5000,
    )


def test_user_activity_resets_idle_timer(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    window.idle_monitor._timeout_ms = OPERATOR_IDLE_TIMEOUT_MS
    window.idle_monitor.note_activity()
    remaining_before = window.idle_monitor._remaining_s()
    assert remaining_before > 15
    window.manual_view_model.status_changed.emit("user action")
    remaining_after = window.idle_monitor._remaining_s()
    assert remaining_after >= remaining_before


def test_idle_monitor_never_sends_on_serial_readonly(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.transport_selector.setCurrentText("Serial")
    window.connection_page.connect_button.click()
    session = window.connection_page.session
    assert session is not None
    assert not session.actions_allowed
    window.idle_monitor._timeout_ms = 300
    window.idle_monitor.note_activity()
    qtbot.waitUntil(lambda: "跳过" in window.notification_center.text(), timeout=5000)
    session = window.connection_page.session
    assert session is not None
    assert session.actions_allowed is False


def test_controlled_shutdown_homes_before_closing(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    session = window.connection_page.session
    assert session is not None
    assert (session.latest_snapshot and session.latest_snapshot.homed_mask) == 0
    window.close()
    assert (session.latest_snapshot and session.latest_snapshot.homed_mask) == 0x1D
    assert session.state.value == "disconnected"


def test_estop_blocked_shutdown_requires_confirmation(qtbot: QtBot) -> None:
    window = MainWindow(confirm_fault_exit=lambda title, text: False)
    qtbot.addWidget(window)
    _connected_operator(window)
    window.show()
    session = window.connection_page.session
    assert session is not None
    _mock_device(window).device.trigger_estop()
    session.poll_once()
    window.close()
    assert window.isVisible()
    assert session.state.value != "disconnected"

    def confirm_exit(_title: str, _text: str) -> bool:
        return True

    window._confirm_fault_exit = confirm_exit
    window.close()
    assert not window.isVisible()
    assert session.state.value == "disconnected"
