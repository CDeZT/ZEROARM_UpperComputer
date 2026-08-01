"""Global shortcut tests: Ctrl+D diagnostics and Space software stop."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from zeroarm_desktop.gui.shell import MainWindow


def test_ctrl_d_navigates_to_diagnostics(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    QApplication.processEvents()
    assert window.page_stack.currentWidget().objectName() == "page_connection"
    QTest.keyClick(window, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert window.page_stack.currentWidget().objectName() == "page_diagnostics"
    assert window._buttons["diagnostics"].isChecked()


def test_space_triggers_global_software_stop(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    QApplication.processEvents()
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.manual_view_model.start_hold(0, 1, 17_453)
    assert window.manual_view_model.holding
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert not window.manual_view_model.holding
    assert "软件 STOP" in window.notification_center.text()


def test_stop_button_uses_global_stop_handler(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.connection_page.connect_button.click()
    window.mode_selector.setCurrentText("Operator")
    window.manual_view_model.start_hold(0, 1, 17_453)
    window.stop_button.click()
    assert not window.manual_view_model.holding
    assert "软件 STOP" in window.notification_center.text()
