"""Trajectory page navigation, processing, and ghost cursor tests."""

from PySide6.QtWidgets import QPushButton, QTableWidget
from pytestqt.qtbot import QtBot

from zeroarm_desktop.application.playback import PlaybackState
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint
from zeroarm_desktop.gui.shell import MainWindow


def test_trajectory_page_edits_and_updates_ghost(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    navigation = window.findChild(QPushButton, "nav_trajectory")
    assert navigation is not None
    navigation.click()
    assert window.page_stack.currentWidget().objectName() == "page_trajectory"
    table = window.findChild(QTableWidget, "trajectory_table")
    assert table is not None and table.rowCount() == 3
    table.setCurrentCell(1, 0)
    assert window.workspace_view_model._ghost == (87_266, 0, 0, 0, 0, 0)
    resample = window.findChild(QPushButton, "trajectory_resample_button")
    assert resample is not None
    resample.click()
    assert table.rowCount() == 21
    undo = window.findChild(QPushButton, "trajectory_undo_button")
    assert undo is not None
    undo.click()
    assert table.rowCount() == 3


def test_trajectory_mock_playback_records_evidence_and_completes(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("trajectory")
    view_model = window.trajectory_view_model
    short = Trajectory(
        1,
        "short",
        (
            TrajectoryPoint(0, (0, 0, 0, 0, 0, 0), 0),
            TrajectoryPoint(250_000_000, (20_000, 0, 0, 0, 0, 0), 0),
            TrajectoryPoint(500_000_000, (0, 0, 0, 0, 0, 0), 0),
        ),
        "test",
        {},
    )
    view_model.editor.apply(short)
    view_model.start_playback()
    qtbot.waitUntil(
        lambda: view_model.playback.progress.state is PlaybackState.COMPLETED,
        timeout=10_000,
    )
    qtbot.waitUntil(
        lambda: any(evidence.outcome == "completed" for evidence in view_model.evidence),
        timeout=10_000,
    )
    accepted = [evidence for evidence in view_model.evidence if evidence.outcome == "accepted"]
    assert len(accepted) >= 1
    assert len(accepted) == view_model.playback.progress.points_sent
    assert accepted[0].result_raw == 0
    assert all(evidence.playback_id == accepted[0].playback_id for evidence in view_model.evidence)
    assert view_model.playback.progress.state is PlaybackState.COMPLETED
    assert view_model._poller_paused is False
