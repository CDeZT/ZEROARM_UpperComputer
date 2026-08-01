"""Manual Mock control SafetyGate, ghost, hold, release, and disconnect tests."""

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def _connected_operator(window: MainWindow) -> None:
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("manual_joint")


def test_manual_joint_axis_dropdown_only_lists_available_axes(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    axis = window.findChild(QComboBox, "manual_axis")
    assert axis is not None
    assert [axis.itemText(index) for index in range(axis.count())] == ["J1", "J3", "J4", "J5"]


def test_manual_joint_unavailable_axis_preview_is_rejected(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    status = window.findChild(QLabel, "manual_joint_status")
    assert status is not None
    with pytest.raises(ValueError, match="不可用"):
        window.manual_view_model.preview(1, 10_000, relative=True)
    with pytest.raises(ValueError, match="不可用"):
        window.manual_view_model.preview(5, 10_000, relative=True)


def test_manual_joint_interlock_denial_is_visible(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    status = window.findChild(QLabel, "manual_joint_status")
    assert status is not None
    preview = window.manual_view_model.preview(3, 100_000, relative=True)
    assert not preview.decision.allowed
    assert "j4_move_requires_j3_already_clear" in preview.decision.denials
    assert "j4_requires_j3_clear" in preview.decision.denials


def test_manual_joint_completion_reports_arrival(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    status = window.findChild(QLabel, "manual_joint_status")
    assert status is not None
    preview = window.manual_view_model.preview(0, 20_000, relative=True)
    assert preview.decision.allowed
    window.manual_view_model.arm()
    window.manual_view_model.send()
    qtbot.waitUntil(lambda: "目标到达" in status.text(), timeout=5000)


def test_manual_joint_preview_arm_send_mock_e2e(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    preview = window.findChild(QPushButton, "preview_joint_button")
    arm = window.findChild(QPushButton, "arm_joint_button")
    send = window.findChild(QPushButton, "send_joint_button")
    assert preview is not None and arm is not None and send is not None
    preview.click()
    assert window.workspace_view_model.render_now().ghost_links
    arm.click()
    initial_session = window.connection_page.session
    assert initial_session is not None and initial_session.latest_snapshot is not None
    generation = initial_session.latest_snapshot.generation
    send.click()
    session = window.connection_page.session
    assert session is not None and session.latest_snapshot is not None
    assert session.latest_snapshot.generation > generation
    status = window.findChild(QLabel, "manual_joint_status")
    assert status is not None
    assert "Mock已接受" in status.text()


def test_manual_joint_observer_mode_is_denied(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.connect_button.click()
    window.navigate("manual_joint")
    preview = window.findChild(QPushButton, "preview_joint_button")
    assert preview is not None
    preview.click()
    status = window.findChild(QLabel, "manual_joint_status")
    assert status is not None
    assert "operator_mode_required" in status.text()


def test_hold_release_and_disconnect_stop_scheduling(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    positive = window.findChild(QPushButton, "hold_positive")
    assert positive is not None
    positive.pressed.emit()
    assert window.manual_view_model.holding
    positive.released.emit()
    assert not window.manual_view_model.holding
    positive.pressed.emit()
    assert window.manual_view_model.holding
    window.connection_page.toggle_connection()
    assert not window.manual_view_model.holding


def test_global_stop_and_navigation_cancel_hold(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    positive = window.findChild(QPushButton, "hold_positive")
    assert positive is not None
    positive.pressed.emit()
    window.stop_button.click()
    assert not window.manual_view_model.holding
    session = window.connection_page.session
    assert session is not None
    assert "STOP" in session.command_audit
    positive.pressed.emit()
    window.navigate("dashboard")
    assert not window.manual_view_model.holding


def test_window_focus_loss_cancels_hold_without_auto_resume(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    positive = window.findChild(QPushButton, "hold_positive")
    assert positive is not None
    positive.pressed.emit()
    assert window.manual_view_model.holding
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
    assert not window.manual_view_model.holding
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
    assert not window.manual_view_model.holding
