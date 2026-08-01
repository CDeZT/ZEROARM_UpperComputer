"""HOME wizard Mock E2E, fault clear, and serial-readonly denial tests."""

from typing import cast

from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.transport.mock import MockTransport


def _connected_operator(window: MainWindow) -> None:
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("home")


def _mock_device(window: MainWindow) -> MockTransport:
    session = window.connection_page.session
    assert session is not None
    return cast(MockTransport, session._transport)


def test_home_wizard_mock_e2e_homes_0x1d_in_order(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)

    status = window.findChild(QLabel, "home_status")
    progress = window.findChild(QLabel, "home_progress")
    start = window.findChild(QPushButton, "home_start_button")
    order = window.findChild(QLabel, "home_order")
    assert status is not None and progress is not None and start is not None
    assert order is not None
    assert "J5 → J4 → J3 → J1" in order.text()

    start.click()
    qtbot.waitUntil(lambda: "回零完成" in status.text(), timeout=5000)
    assert "0x1D" in progress.text()
    session = window.connection_page.session
    assert session is not None and session.latest_snapshot is not None
    assert session.latest_snapshot.homed_mask == 0x1D


def test_home_wizard_shows_homing_progress_order(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    start = window.findChild(QPushButton, "home_start_button")
    status = window.findChild(QLabel, "home_status")
    assert start is not None and status is not None
    start.click()
    assert "已请求回零 0x1D" in status.text()
    assert "顺序 J5 -> J4 -> J3 -> J1" in status.text()


def test_home_wizard_observer_mode_is_denied(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.connect_button.click()
    window.navigate("home")
    start = window.findChild(QPushButton, "home_start_button")
    status = window.findChild(QLabel, "home_status")
    assert start is not None and status is not None
    start.click()
    assert "operator_mode_required" in status.text()


def test_home_estop_shows_reset_required_hint(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    start = window.findChild(QPushButton, "home_start_button")
    status = window.findChild(QLabel, "home_status")
    assert start is not None and status is not None
    _mock_device(window).device.trigger_estop()
    session = window.connection_page.session
    assert session is not None
    session.poll_once()
    start.click()
    assert "拒绝" in status.text() or "run_state_unsafe" in status.text()


def test_home_clear_fault_clears_clearable_fault(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    clear = window.findChild(QPushButton, "home_clear_fault_button")
    status = window.findChild(QLabel, "home_status")
    assert clear is not None and status is not None
    clear.click()
    assert "CLEAR_FAULT" in status.text()
