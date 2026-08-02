"""Connection page Mock handshake and Serial discovery tests."""

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.gui.pages.connection import ConnectionPage
from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.transport.mock import MockSettings, MockTransport


def test_gui_connect_disconnect__mock_v1_handshake(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    button = window.findChild(QPushButton, "connect_button")
    assert button is not None
    button.click()
    session = window.connection_page.session
    assert session is not None
    assert session.state is SessionState.READONLY_READY
    assert button.text() == "断开"
    assert "只读" in window.connection_badge.text()
    timeline = window.findChild(QLabel, "handshake_timeline")
    assert timeline is not None
    assert "readonly_ready" in timeline.text()
    assert "ZEROARM/1.0" in window.connection_page.identity.text()
    button.click()
    assert window.connection_page.session is None
    assert button.text() == "连接"


def test_gui_port_refresh_handles_no_hardware(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    selector = window.findChild(QComboBox, "transport_selector")
    assert selector is not None
    selector.setCurrentText("Serial")
    refresh = window.findChild(QPushButton, "refresh_ports_button")
    assert refresh is not None
    refresh.click()
    ports = window.findChild(QComboBox, "port_selector")
    assert ports is not None
    assert ports.count() >= 1


def test_handshake_can_be_cancelled_without_waiting_for_timeout(qtbot: QtBot) -> None:
    page = ConnectionPage(
        session_factory=lambda: DeviceSession(
            MockTransport(MockSettings(response_delay_ms=200)),
            actions_allowed=True,
        )
    )
    qtbot.addWidget(page)

    page.connect_button.click()

    assert page.session is not None
    assert page.session.state is SessionState.HANDSHAKING
    assert page.connect_button.isEnabled()
    assert page.connect_button.text() == "取消连接"

    page.connect_button.click()
    assert page.session is None
