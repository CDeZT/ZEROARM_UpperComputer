"""Navigation shell and stable global status surface."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.gui.theme import DARK_THEME, LIGHT_THEME
from zeroarm_desktop.version import __version__


def _placeholder(object_name: str, title: str, detail: str) -> QWidget:
    page = QWidget()
    page.setObjectName(object_name)
    heading = QLabel(title)
    heading.setObjectName("page_title")
    description = QLabel(detail)
    description.setWordWrap(True)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(36, 32, 36, 32)
    layout.addWidget(heading)
    layout.addWidget(description)
    layout.addStretch()
    return page


class MainWindow(QMainWindow):
    """Application shell with deterministic routing and safe global controls."""

    page_changed = Signal(str)

    def __init__(self, *, shutdown: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._shutdown = shutdown
        self._pages: dict[str, int] = {}
        self._buttons: dict[str, QPushButton] = {}
        self.setObjectName("main_window")
        self.setWindowTitle(f"ZeroArm Desktop {__version__}")
        self.setMinimumSize(1280, 720)
        self.resize(1440, 900)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_navigation())
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("page_stack")
        body.addWidget(self.page_stack, 1)
        root_layout.addLayout(body, 1)
        root_layout.addWidget(self._build_status_bar())
        self.setCentralWidget(root)

        self.register_page(
            "connection",
            _placeholder(
                "page_connection", "连接与设备", "Mock 与 Serial 连接将在当前 Demo 中启用。"
            ),
        )
        self.register_page(
            "dashboard",
            _placeholder("page_dashboard", "系统总览", "连接后展示只读设备状态与链路健康。"),
        )
        self.register_page(
            "joint_monitor",
            _placeholder("page_joint_monitor", "六轴监控", "连接后展示六轴目标、反馈和有界曲线。"),
        )
        self.navigate("connection")
        self.apply_theme("dark")
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(lambda: self.navigate("connection"))

    def register_page(self, route: str, page: QWidget) -> None:
        if route in self._pages:
            old = self.page_stack.widget(self._pages[route])
            self.page_stack.removeWidget(old)
            old.deleteLater()
        self._pages[route] = self.page_stack.addWidget(page)

    def navigate(self, route: str) -> None:
        index = self._pages[route]
        self.page_stack.setCurrentIndex(index)
        for name, button in self._buttons.items():
            button.setChecked(name == route)
        self.page_changed.emit(route)

    def apply_theme(self, theme: str) -> None:
        if theme not in {"dark", "light"}:
            raise ValueError("theme must be dark or light")
        self.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)

    def set_connection_text(self, text: str) -> None:
        self.connection_badge.setText(text)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        product = QLabel(f"ZEROARM DESKTOP  {__version__}")
        product.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(product)
        layout.addStretch()
        self.connection_badge = QLabel("未连接")
        self.connection_badge.setObjectName("connection_badge")
        self.firmware_badge = QLabel("固件未知")
        self.firmware_badge.setObjectName("firmware_badge")
        self.snapshot_age_badge = QLabel("状态 --")
        self.snapshot_age_badge.setObjectName("snapshot_age_badge")
        self.fault_badge = QLabel("FAULT --")
        self.fault_badge.setObjectName("fault_badge")
        for badge in (
            self.connection_badge,
            self.firmware_badge,
            self.snapshot_age_badge,
            self.fault_badge,
        ):
            badge.setProperty("class", "badge")
            layout.addWidget(badge)
        stop = QPushButton("软件停止尚未启用 (非急停)")
        stop.setObjectName("global_stop_button")
        stop.setEnabled(False)
        layout.addWidget(stop)
        return header

    def _build_navigation(self) -> QFrame:
        navigation = QFrame()
        navigation.setObjectName("navigation")
        navigation.setFixedWidth(220)
        layout = QVBoxLayout(navigation)
        layout.setContentsMargins(18, 24, 18, 24)
        for route, text in (
            ("connection", "连接与设备"),
            ("dashboard", "系统总览"),
            ("joint_monitor", "六轴监控"),
        ):
            button = QPushButton(text)
            button.setObjectName(f"nav_{route}")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=route: self.navigate(name))
            self._buttons[route] = button
            layout.addWidget(button)
        layout.addStretch()
        theme = QPushButton("切换深浅主题")
        theme.clicked.connect(self._toggle_theme)
        layout.addWidget(theme)
        return navigation

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("status_bar")
        layout = QHBoxLayout(bar)
        self.link_status = QLabel("RX 0 B  |  TX 0 B  |  Snapshot 0 Hz")
        self.link_status.setObjectName("link_status")
        self.notification_center = QLabel("Observer 模式 | 动作能力锁定")
        self.notification_center.setObjectName("notification_center")
        layout.addWidget(self.link_status)
        layout.addStretch()
        layout.addWidget(self.notification_center)
        return bar

    def _toggle_theme(self) -> None:
        current = self.styleSheet()
        self.setStyleSheet(LIGHT_THEME if current == DARK_THEME else DARK_THEME)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._shutdown is not None:
            self._shutdown()
        event.accept()
