"""Snapshot ViewModel throttling, V1 unknowns, ring bounds, and GUI flow."""

from datetime import UTC, datetime
from time import monotonic_ns
from typing import cast

from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.gui.shell import MainWindow
from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel
from zeroarm_desktop.transport.mock import MockTransport


def _snapshot(generation: int) -> RobotSnapshot:
    joints = (generation, -generation, generation * 2, 0, 5, -6)
    return RobotSnapshot(
        generation=generation,
        received_monotonic_ns=monotonic_ns() - generation * 1_000_000,
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
    # Windows may process one timer tick on each side of the measured wait window.
    assert len(renders) <= 8
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


def test_dashboard_shows_profile_readiness_and_unavailable_axes(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.connection_page.connect_button.click()
    window.snapshot_view_model.render_now()

    profile = window.findChild(QLabel, "dashboard_profile")
    readiness = window.findChild(QLabel, "dashboard_readiness")
    j2 = window.findChild(QLabel, "dashboard_joint_2")
    j6 = window.findChild(QLabel, "dashboard_joint_6")
    j1 = window.findChild(QLabel, "dashboard_joint_1")
    assert profile is not None and readiness is not None
    assert j2 is not None and j6 is not None and j1 is not None
    assert "zeroarm_g474_v1_partial" in profile.text()
    assert "J2/J6 Unavailable" in profile.text()
    assert "运动已授权" in readiness.text()
    assert "未回零" in readiness.text()
    assert "Unavailable" in j2.text()
    assert "Unavailable" in j6.text()
    assert "Unavailable" not in j1.text()
    auto_home = window.findChild(QLabel, "dashboard_auto_home")
    assert auto_home is not None
    assert "20 秒" in auto_home.text()
    window.snapshot_view_model.close()


def test_dashboard_shows_startup_fault_and_not_authorized(qtbot: QtBot) -> None:
    window = MainWindow(confirm_fault_exit=lambda title, text: True)
    qtbot.addWidget(window)
    window.show()
    window.connection_page.connect_button.click()
    session = window.connection_page.session
    assert session is not None
    device = cast(MockTransport, session._transport).device
    device.simulate_startup_limits_missing()
    session.poll_once()
    window.snapshot_view_model.render_now()

    run_state = window.findChild(QLabel, "dashboard_run_state")
    fault_names = window.findChild(QLabel, "dashboard_fault_names")
    readiness = window.findChild(QLabel, "dashboard_readiness")
    assert run_state is not None and fault_names is not None and readiness is not None
    assert "FAULT" in run_state.text()
    assert "STARTUP" in fault_names.text()
    assert "运动未授权" in readiness.text()
    assert "RESET-REQUIRED" in readiness.text()
    window.close()
    assert session.state.value == "disconnected"


def test_dashboard_shows_estop_fault(qtbot: QtBot) -> None:
    window = MainWindow(confirm_fault_exit=lambda title, text: True)
    qtbot.addWidget(window)
    window.show()
    window.connection_page.connect_button.click()
    session = window.connection_page.session
    assert session is not None
    device = cast(MockTransport, session._transport).device
    device.trigger_estop()
    session.poll_once()
    window.snapshot_view_model.render_now()

    fault_names = window.findChild(QLabel, "dashboard_fault_names")
    readiness = window.findChild(QLabel, "dashboard_readiness")
    assert fault_names is not None and readiness is not None
    assert "ESTOP" in fault_names.text()
    assert "运动未授权" in readiness.text()
    assert "RESET-REQUIRED" in readiness.text()
    window.close()
    assert session.state.value == "disconnected"


def test_dashboard_shows_unknown_fields(qtbot: QtBot) -> None:
    view_model = SnapshotViewModel(render_fps=60)
    unknown = _snapshot(1)
    unknown = RobotSnapshot(
        generation=unknown.generation,
        received_monotonic_ns=unknown.received_monotonic_ns,
        received_wall_utc=unknown.received_wall_utc,
        device_time_ms=unknown.device_time_ms,
        sample_sequence=unknown.sample_sequence,
        run_state_raw=12345,
        target_joint_urad=unknown.target_joint_urad,
        actual_joint_urad=unknown.actual_joint_urad,
        enabled_mask=unknown.enabled_mask,
        homed_mask=unknown.homed_mask,
        moving_mask=unknown.moving_mask,
        online_mask=unknown.online_mask,
        teach_mask=unknown.teach_mask,
        fault_flags_raw=0x8000,
        velocity_urad_s=unknown.velocity_urad_s,
        current_ma=unknown.current_ma,
    )
    view_model.ingest_snapshot(unknown)
    state = view_model.current_state()
    assert "UNKNOWN" in state.run_state_text
    assert state.fault_names == ()
    assert state.fault_unknown_bits == 0x8000
    view_model.close()


def test_dashboard_freshness_is_bounded_positive(qtbot: QtBot) -> None:
    view_model = SnapshotViewModel(render_fps=60)
    view_model.ingest_snapshot(_snapshot(1))
    state = view_model.current_state()
    assert state.snapshot_age_ms is not None
    assert 0 <= state.snapshot_age_ms < 60_000
    view_model.close()
