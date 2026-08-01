"""Trajectory page navigation, processing, and ghost cursor tests."""

from PySide6.QtWidgets import QPushButton, QTableWidget
from pytestqt.qtbot import QtBot

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
