"""Teach mask, support gate, Mock E2E record/stop review tests."""

from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def _connected_operator(window: MainWindow) -> None:
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("teach")


def test_teach_page__support_required_before_start(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    preview = window.findChild(QPushButton, "teach_preview_button")
    status = window.findChild(QLabel, "teach_status")
    assert preview is not None and status is not None
    preview.click()
    assert "gravity_support_required" in status.text()


def test_teach_page__unavailable_axis_mask_rejected(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    status = window.findChild(QLabel, "teach_status")
    assert status is not None
    try:
        window.teach_view_model.set_joint_mask(0x02)
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert window.teach_view_model.joint_mask == 0x1D


def test_teach_page__mock_e2e_record_stop_review_and_save(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _connected_operator(window)
    support = window.findChild(QCheckBox, "teach_support_confirmed")
    preview = window.findChild(QPushButton, "teach_preview_button")
    arm = window.findChild(QPushButton, "teach_arm_button")
    start = window.findChild(QPushButton, "teach_start_button")
    stop = window.findChild(QPushButton, "teach_stop_button")
    save = window.findChild(QPushButton, "teach_save_button")
    status = window.findChild(QLabel, "teach_status")
    state = window.findChild(QLabel, "teach_state")
    review = window.findChild(QLabel, "teach_review")
    assert None not in (support, preview, arm, start, stop, save, status, state, review)
    assert support is not None and preview is not None and arm is not None
    assert start is not None and stop is not None and save is not None
    assert status is not None and state is not None and review is not None

    support.setChecked(True)
    preview.click()
    assert "预览通过" in status.text()
    arm.click()
    assert "armed" in state.text()
    start.click()
    assert "RECORDING" in status.text() or "recording" in state.text()
    session = window.connection_page.session
    assert session is not None
    for _ in range(5):
        session.poll_once()
    stop.click()
    assert "REVIEW" in status.text() or "review" in state.text()
    assert "不自动ENABLE" in status.text()
    assert "disabled_ok=True" in review.text()
    save.click()
    trajectory = window.teach_view_model.saved_trajectory
    assert trajectory is not None
    assert trajectory.metadata["parent_raw_sha256"]
    assert len(trajectory.points) >= 1
    recording = window.teach_view_model.recorder.last_recording
    assert recording is not None
    assert recording.samples[0].device_time_ms is None


def test_teach_page__observer_mode_denied(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.connect_button.click()
    window.navigate("teach")
    support = window.findChild(QCheckBox, "teach_support_confirmed")
    preview = window.findChild(QPushButton, "teach_preview_button")
    status = window.findChild(QLabel, "teach_status")
    assert support is not None and preview is not None and status is not None
    support.setChecked(True)
    preview.click()
    assert "operator_mode_required" in status.text()


def test_teach_page__serial_actions_denied_message(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.mode_selector.setCurrentText("Operator")
    window.navigate("teach")
    support = window.findChild(QCheckBox, "teach_support_confirmed")
    preview = window.findChild(QPushButton, "teach_preview_button")
    status = window.findChild(QLabel, "teach_status")
    assert support is not None and preview is not None and status is not None
    support.setChecked(True)
    preview.click()
    assert "请先连接" in status.text() or "Session" in status.text() or "连接" in status.text()
