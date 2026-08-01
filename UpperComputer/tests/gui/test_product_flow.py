"""Cross-page Mock product flow: recorder, teach→trajectory, recipe, dataset, calibration."""

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from zeroarm_desktop.domain.trajectory import trajectory_from_json, trajectory_to_json
from zeroarm_desktop.gui.shell import MainWindow


def _window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow(session_database_path=tmp_path / "gui-sessions.sqlite3")
    qtbot.addWidget(window)
    return window


def test_teach_save_loads_trajectory_editor(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("teach")
    support = window.findChild(QCheckBox, "teach_support_confirmed")
    preview = window.findChild(QPushButton, "teach_preview_button")
    arm = window.findChild(QPushButton, "teach_arm_button")
    start = window.findChild(QPushButton, "teach_start_button")
    stop = window.findChild(QPushButton, "teach_stop_button")
    save = window.findChild(QPushButton, "teach_save_button")
    assert None not in (support, preview, arm, start, stop, save)
    assert support is not None and preview is not None and arm is not None
    assert start is not None and stop is not None and save is not None
    support.setChecked(True)
    preview.click()
    arm.click()
    start.click()
    session = window.connection_page.session
    assert session is not None
    for _ in range(3):
        session.poll_once()
    stop.click()
    save.click()
    assert window.trajectory_view_model.trajectory.source == "processed"
    assert "parent_raw_sha256" in window.trajectory_view_model.trajectory.metadata
    assert len(window.evidence_log.items) >= 1


def test_trajectory_import_export_roundtrip(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    original = window.trajectory_view_model.trajectory
    text = trajectory_to_json(original)
    loaded = trajectory_from_json(text)
    window.trajectory_view_model.load_trajectory(loaded)
    assert window.trajectory_view_model.trajectory.name == original.name
    exported = window.trajectory_view_model.export_json_text()
    assert trajectory_from_json(exported).points == original.points


def test_recipe_run_loads_and_starts_playback(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("gamepad_recipe")
    validate = window.findChild(QPushButton, "validate_recipe_button")
    run = window.findChild(QPushButton, "run_recipe_button")
    status = window.findChild(QLabel, "gamepad_recipe_status")
    assert validate is not None and run is not None and status is not None
    validate.click()
    assert "READY" in status.text() or "有效" in status.text()
    run.click()
    assert "回放" in status.text() or "points=" in status.text()
    qtbot.waitUntil(
        lambda: window.trajectory_view_model.playback.progress.state.value
        in {"completed", "playing", "aborted"},
        timeout=5000,
    )


def test_dataset_from_teach_and_calibration_home(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.navigate("calibration")
    home = window.findChild(QPushButton, "mock_home_button")
    status = window.findChild(QLabel, "calibration_status")
    order = window.findChild(QLabel, "calibration_home_order")
    assert home is not None and status is not None and order is not None
    assert "J5" in order.text()
    home.click()
    qtbot.waitUntil(lambda: "回零" in status.text(), timeout=5000)

    window.navigate("dataset")
    from_teach = window.findChild(QPushButton, "dataset_from_teach_button")
    dataset_status = window.findChild(QLabel, "dataset_status")
    assert from_teach is not None and dataset_status is not None
    from_teach.click()
    assert "无示教记录" in dataset_status.text()


def test_session_recorder_binds_on_connect(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window.connection_page.connect_button.click()
    assert window.recording.session_id is not None
    session = window.connection_page.session
    assert session is not None
    session.poll_once()
    window.navigate("diagnostics")
    refresh = window.findChild(QPushButton, "refresh_diagnostics")
    text = window.findChild(QLabel, "diagnostics_text")
    assert refresh is not None and text is not None
    refresh.click()
    assert "Recorder session=" in text.text()
