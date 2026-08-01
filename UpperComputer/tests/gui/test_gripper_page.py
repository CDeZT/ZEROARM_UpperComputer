"""Gripper/bench readonly diagnostics and action-gate tests."""

from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def _connected(window: MainWindow) -> None:
    window.connection_page.connect_button.click()
    window.navigate("gripper")


def test_gripper_page__ping_and_bench_query_mock(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected(window)
    ping = window.findChild(QPushButton, "gripper_ping_button")
    query = window.findChild(QPushButton, "bench_query_button")
    protection = window.findChild(QPushButton, "bench_protection_button")
    status = window.findChild(QLabel, "gripper_status")
    audit = window.findChild(QLabel, "gripper_audit")
    assert None not in (ping, query, protection, status, audit)
    assert ping is not None and query is not None and protection is not None
    assert status is not None and audit is not None

    ping.click()
    assert "Gripper" in status.text()
    assert "GRIPPER_PING" in audit.text()
    query.click()
    assert "Bench motor=1" in status.text()
    assert "BENCH_QUERY" in audit.text()
    session = window.connection_page.session
    assert session is not None
    protection_value = session.send_bench_get_protection(3)
    assert protection_value.motor_id == 3
    assert protection_value.temperature_c == 100


def test_gripper_page__action_gate_denies_uncalibrated(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected(window)
    probe = window.findChild(QPushButton, "gripper_action_probe_button")
    status = window.findChild(QLabel, "gripper_status")
    assert probe is not None and status is not None
    probe.click()
    assert "夹爪动作门拒绝" in status.text()
    assert "gripper_not_calibrated" in status.text()


def test_protocol_console__bench_and_gripper_readonly(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.connect_button.click()
    window.navigate("protocol_console")
    from PySide6.QtWidgets import QComboBox

    command = window.findChild(QComboBox, "console_command")
    send = window.findChild(QPushButton, "console_send")
    result = window.findChild(QLabel, "console_result")
    assert command is not None and send is not None and result is not None
    command.setCurrentText("GRIPPER_PING")
    send.click()
    assert "GRIPPER_PING" in result.text()
    command.setCurrentText("BENCH_QUERY")
    send.click()
    assert "BENCH_QUERY" in result.text()
