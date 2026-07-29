"""Snapshot ViewModel throttling, V1 unknowns, ring bounds, and GUI flow."""

from datetime import UTC, datetime

from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel


def _snapshot(generation: int) -> RobotSnapshot:
    joints = (generation, -generation, generation * 2, 0, 5, -6)
    return RobotSnapshot(
        generation=generation,
        received_monotonic_ns=generation * 10_000_000,
        received_wall_utc=datetime.now(UTC),
        device_time_ms=None,
        sample_sequence=None,
        run_state_raw=1,
        target_joint_urad=joints,
        actual_joint_urad=(0, 0, 0, 0, 0, 0),
        enabled_mask=0,
        homed_mask=0,
        moving_mask=0,
        online_mask=None,
        teach_mask=None,
        fault_flags_raw=0,
        velocity_urad_s=None,
        current_ma=None,
    )


def test_bounded_plot_ring_and_v1_unknown_fields(qtbot: QtBot) -> None:
    view_model = SnapshotViewModel(capacity=100, render_fps=60)
    for generation in range(250):
        view_model.ingest_snapshot(_snapshot(generation))
    state = view_model.current_state()
    assert view_model.sample_count == 100
    assert state.generation == 249
    assert state.joints[0].velocity_text == "-- / V1 未提供"
    assert state.joints[0].current_text == "-- / V1 未提供"
    assert state.joints[0].online_text == "-- / V1 未提供"
    view_model.close()


def test_100hz_input_is_rendered_at_no_more_than_60fps(qtbot: QtBot) -> None:
    view_model = SnapshotViewModel(capacity=6000, render_fps=60)
    renders: list[object] = []
    view_model.state_changed.connect(renders.append)
    for generation in range(1000):
        view_model.ingest_snapshot(_snapshot(generation))
    qtbot.wait(100)
    assert view_model.sample_count == 1000
    assert len(renders) <= 7
    assert view_model.current_state().generation == 999
    view_model.close()


def test_mock_demo_updates_dashboard_and_monitor(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    connect = window.findChild(QPushButton, "connect_button")
    assert connect is not None
    connect.click()
    window.snapshot_view_model.render_now()
    run_state = window.findChild(QLabel, "dashboard_run_state")
    assert run_state is not None
    assert "READY" in run_state.text()
    velocity = window.findChild(QLabel, "joint_1_column_4")
    assert velocity is not None
    assert "V1 未提供" in velocity.text()
    session = window.connection_page.session
    assert session is not None
    session.poll_once()
    window.snapshot_view_model.render_now()
    assert "Snapshots" in window.link_status.text()
