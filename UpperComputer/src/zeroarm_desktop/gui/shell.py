"""Navigation shell and stable global status surface."""

from collections.abc import Callable
from time import monotonic, sleep

from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.domain.safety import AppMode
from zeroarm_desktop.gui.pages.calibration import CalibrationPage
from zeroarm_desktop.gui.pages.cartesian import CartesianPage
from zeroarm_desktop.gui.pages.connection import ConnectionPage
from zeroarm_desktop.gui.pages.dashboard import DashboardPage
from zeroarm_desktop.gui.pages.dataset import DatasetPage
from zeroarm_desktop.gui.pages.diagnostics import DiagnosticsPage, ProtocolConsolePage
from zeroarm_desktop.gui.pages.firmware import FirmwarePage
from zeroarm_desktop.gui.pages.gamepad_recipe import GamepadRecipePage
from zeroarm_desktop.gui.pages.home import HomePage
from zeroarm_desktop.gui.pages.joint_monitor import JointMonitorPage
from zeroarm_desktop.gui.pages.manual_joint import ManualJointPage
from zeroarm_desktop.gui.pages.teach import TeachPage
from zeroarm_desktop.gui.pages.trajectory import TrajectoryPage
from zeroarm_desktop.gui.pages.workspace3d import Workspace3DPage
from zeroarm_desktop.gui.theme import DARK_THEME, LIGHT_THEME
from zeroarm_desktop.gui.viewmodels.home import HomeViewModel
from zeroarm_desktop.gui.viewmodels.idle_monitor import OperatorIdleHomeMonitor
from zeroarm_desktop.gui.viewmodels.manual_joint import ManualJointViewModel
from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel, SnapshotViewState
from zeroarm_desktop.gui.viewmodels.trajectory import TrajectoryViewModel
from zeroarm_desktop.gui.viewmodels.workspace3d import Workspace3DViewModel
from zeroarm_desktop.infrastructure.paths import robot_model_root
from zeroarm_desktop.model3d.fk import UrdfForwardKinematics
from zeroarm_desktop.model3d.ik import NumericalIkSolver
from zeroarm_desktop.model3d.scene import RobotSceneBuilder
from zeroarm_desktop.version import __version__

RESET_REQUIRED_MASK = 0x0E00
CONTROLLED_SHUTDOWN_HOME_TIMEOUT_S = 5.0


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

    def __init__(
        self,
        *,
        shutdown: Callable[[], None] | None = None,
        confirm_fault_exit: Callable[[str, str], bool] | None = None,
    ) -> None:
        super().__init__()
        self._shutdown = shutdown
        self._confirm_fault_exit = (
            confirm_fault_exit
            if confirm_fault_exit is not None
            else self._default_fault_exit_confirm
        )
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

        self.connection_page = ConnectionPage()
        self.connection_page.connection_text_changed.connect(self.set_connection_text)
        self.snapshot_view_model = SnapshotViewModel()
        self.snapshot_view_model.state_changed.connect(self._apply_snapshot_state)
        self.connection_page.session_changed.connect(self.snapshot_view_model.bind_session)
        asset_root = robot_model_root()
        urdf = asset_root / "URDF_XG_Robot_Arm_Urdf_V1_1/urdf" / "URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
        kinematics = UrdfForwardKinematics(urdf)
        self.workspace_view_model = Workspace3DViewModel(RobotSceneBuilder(kinematics))
        self.connection_page.session_changed.connect(self.workspace_view_model.bind_session)
        self.manual_view_model = ManualJointViewModel(self.connection_page)
        self.manual_view_model.ghost_target_changed.connect(
            self.workspace_view_model.set_ghost_target
        )
        self.connection_page.session_changed.connect(
            lambda session: self.manual_view_model.stop_hold("connection_changed")
        )
        self.trajectory_view_model = TrajectoryViewModel(self.connection_page)
        self.trajectory_view_model.ghost_changed.connect(self.workspace_view_model.set_ghost_target)
        self.register_page("connection", self.connection_page)
        self.register_page("dashboard", DashboardPage(self.snapshot_view_model))
        self.register_page("joint_monitor", JointMonitorPage(self.snapshot_view_model))
        self.register_page("workspace_3d", Workspace3DPage(self.workspace_view_model, asset_root))
        self.register_page("manual_joint", ManualJointPage(self.manual_view_model))
        self.register_page("trajectory", TrajectoryPage(self.trajectory_view_model))
        self.teach_page = TeachPage(self.connection_page)
        self.register_page("teach", self.teach_page)
        self.register_page(
            "cartesian",
            CartesianPage(
                NumericalIkSolver(kinematics),
                self.connection_page,
                self.workspace_view_model.set_ghost_target,
            ),
        )
        self.register_page("calibration", CalibrationPage())
        self.home_view_model = HomeViewModel(self.connection_page)
        self.register_page("home", HomePage(self.home_view_model))
        self.connection_page.session_changed.connect(
            lambda session: self.home_view_model.set_mode(
                AppMode.OPERATOR
                if self.mode_selector.currentText() == "Operator"
                else AppMode.OBSERVER
            )
        )
        self.idle_monitor = OperatorIdleHomeMonitor(self.connection_page, self.home_view_model)
        self.idle_monitor.countdown_changed.connect(self._apply_idle_countdown)
        self.idle_monitor.home_triggered.connect(
            lambda text: self.notification_center.setText(text)
        )
        self.connection_page.session_changed.connect(
            lambda session: self.idle_monitor.start()
            if session is not None
            else self.idle_monitor.stop()
        )
        self.manual_view_model.status_changed.connect(self.idle_monitor.note_activity)
        self.page_changed.connect(lambda route: self.idle_monitor.note_activity())
        self.register_page("diagnostics", DiagnosticsPage(self.connection_page))
        self.register_page("protocol_console", ProtocolConsolePage(self.connection_page))
        self.register_page("gamepad_recipe", GamepadRecipePage())
        self.register_page("dataset", DatasetPage())
        self.register_page("firmware", FirmwarePage())
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
        if self.page_stack.currentWidget() is not None and route != "manual_joint":
            self.manual_view_model.stop_hold("navigation")
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
        self.mode_selector = QComboBox()
        self.mode_selector.setObjectName("mode_selector")
        self.mode_selector.addItems(["Observer", "Operator"])
        self.mode_selector.currentTextChanged.connect(self._mode_changed)
        layout.addWidget(self.mode_selector)
        self.stop_button = QPushButton("停止Mock点动 (软件停止 / 非急停)")
        self.stop_button.setObjectName("global_stop_button")
        self.stop_button.clicked.connect(lambda: self.manual_view_model.stop_hold("global_stop"))
        layout.addWidget(self.stop_button)
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
            ("workspace_3d", "3D 工作区"),
            ("manual_joint", "手动关节 (Mock)"),
            ("trajectory", "轨迹编辑器"),
            ("teach", "拖动示教 (Mock)"),
            ("cartesian", "Cartesian离线IK"),
            ("calibration", "标定"),
            ("home", "回零向导 (Mock)"),
            ("diagnostics", "诊断"),
            ("protocol_console", "安全协议终端"),
            ("gamepad_recipe", "手柄/Recipe"),
            ("dataset", "数据集"),
            ("firmware", "固件升级"),
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
        self.status_bar_layout = QHBoxLayout(bar)
        layout = self.status_bar_layout
        self.link_status = QLabel("RX 0 B  |  TX 0 B  |  Snapshot 0 Hz")
        self.link_status.setObjectName("link_status")
        self.notification_center = QLabel("Observer 模式 | 动作能力锁定")
        self.notification_center.setObjectName("notification_center")
        self.auto_home_badge = QLabel("自动回零 --")
        self.auto_home_badge.setObjectName("auto_home_badge")
        self.auto_home_badge.setProperty("class", "badge")
        layout.addWidget(self.link_status)
        layout.addStretch()
        layout.addWidget(self.auto_home_badge)
        layout.addWidget(self.notification_center)
        return bar

    def _toggle_theme(self) -> None:
        current = self.styleSheet()
        self.setStyleSheet(LIGHT_THEME if current == DARK_THEME else DARK_THEME)

    def _mode_changed(self, text: str) -> None:
        self.trajectory_view_model.abort_playback("mode_changed")
        mode = AppMode.OPERATOR if text == "Operator" else AppMode.OBSERVER
        self.manual_view_model.set_mode(mode)
        self.home_view_model.set_mode(mode)
        self.notification_center.setText(f"{text} 模式 | Serial动作始终禁用")

    def _apply_idle_countdown(self, remaining_s: int) -> None:
        if remaining_s > 0:
            self.auto_home_badge.setText(f"自动回零 {remaining_s}s")
        else:
            self.auto_home_badge.setText("自动回零 触发中")

    def _apply_snapshot_state(self, state: SnapshotViewState) -> None:
        generation = "--" if state.generation is None else str(state.generation)
        self.snapshot_age_badge.setText(f"Snapshot #{generation}")
        fault = "--" if state.fault_flags_raw is None else f"0x{state.fault_flags_raw:08X}"
        self.fault_badge.setText(f"FAULT {fault}")
        session = self.connection_page.session
        if session is not None:
            statistics = session.statistics
            self.link_status.setText(
                f"Requests {statistics.requests_sent} | "
                f"Responses {statistics.responses_received} | "
                f"Snapshots {statistics.snapshots_published}"
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.idle_monitor.stop()
        self.snapshot_view_model.close()
        self.workspace_view_model.close()
        self.manual_view_model.stop_hold("shutdown")
        self.trajectory_view_model.abort_playback("shutdown")
        session = self.connection_page.session
        if (
            session is not None
            and session.state is SessionState.READONLY_READY
            and not self._controlled_shutdown(session, event)
        ):
            return
        self.connection_page.close_session()
        if self._shutdown is not None:
            self._shutdown()
        event.accept()

    def _controlled_shutdown(self, session: DeviceSession, event: QCloseEvent) -> bool:
        snapshot = session.latest_snapshot
        fault = snapshot.fault_flags_raw if snapshot is not None else 0
        if fault & RESET_REQUIRED_MASK:
            confirmed = self._confirm_fault_exit(
                "无法安全归零退出",
                f"检测到 RESET-REQUIRED 故障 (0x{fault:08X}), 无法自动回零。\n"
                "请断电复位 MCU 并确认机械状态后再退出。是否仍然退出?",
            )
            if not confirmed:
                event.ignore()
                return False
            return True
        if not session.actions_allowed:
            return True
        if (
            snapshot is not None
            and snapshot.run_state_raw == 1
            and fault == 0
            and (snapshot.homed_mask or 0) != 0x1D
        ):
            self.notification_center.setText("受控退出: 请求回零 0x1D")
            session.pause_polling()
            session.send_home(0x1D)
            deadline = monotonic() + CONTROLLED_SHUTDOWN_HOME_TIMEOUT_S
            while monotonic() < deadline:
                QCoreApplication.processEvents()
                sleep(0.01)
                session.poll_once()
                latest = session.latest_snapshot
                if latest is not None and (latest.homed_mask or 0) == 0x1D:
                    self.notification_center.setText("受控退出: 回零完成证据已记录")
                    return True
        return True

    def _default_fault_exit_confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.warning(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer is QMessageBox.StandardButton.Yes

    def event(self, event: QEvent) -> bool:
        if event.type() in {
            QEvent.Type.WindowDeactivate,
            QEvent.Type.ApplicationDeactivate,
        } and hasattr(self, "manual_view_model"):
            self.manual_view_model.stop_hold("focus_loss")
            self.trajectory_view_model.abort_playback("focus_loss")
        return super().event(event)
