"""3D workspace routing and offscreen fallback tests."""

from PySide6.QtWidgets import QLabel, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def test_workspace_3d_page_is_routed_and_headless_safe(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    button = window.findChild(QPushButton, "nav_workspace_3d")
    assert button is not None
    button.click()
    assert window.page_stack.currentWidget().objectName() == "page_workspace_3d"
    status = window.findChild(QLabel, "workspace_3d_status")
    assert status is not None
    assert "Offscreen" in status.text()
    assert window.findChild(QWidget, "workspace_3d_view") is None


def test_mock_snapshot_builds_workspace_scene(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.connection_page.connect_button.click()
    scene = window.workspace_view_model.render_now()
    assert len(scene.actual_links) == 7
    assert scene.generation is not None
